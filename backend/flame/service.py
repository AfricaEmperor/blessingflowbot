"""Mission state, mission-linked proof records, outcome and next-mission generation."""
import hashlib
import json
import re
import secrets
import sqlite3
from datetime import datetime, timezone

from . import config, migrations
from . import outcome as rules
from .errors import FlameError
from .store import connect, tx

ALLOWED_FIELDS = ("title", "goal", "success_measure", "target_proofs", "owner", "next_move")


# --------------------------------------------------------------------- helpers
def _iso(now=None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def _event(conn, mission_id, kind, detail, ts):
    conn.execute(
        "INSERT INTO mission_events (mission_id, kind, detail, created_at) VALUES (?,?,?,?)",
        (mission_id, kind, json.dumps(detail, sort_keys=True), ts),
    )


def _clean(value, name, required=False, limit=config.MAX_TEXT_LEN) -> str:
    text = (value or "").strip()
    if required and not text:
        raise FlameError(f"{name} is required")
    if len(text) > limit:
        raise FlameError(f"{name} is longer than {limit} characters")
    return text


def _target(value):
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise FlameError("target_proofs must be a whole number")
    if number <= 0:
        raise FlameError("target_proofs must be greater than zero")
    return number


def _mission_dict(row):
    if row is None:
        return None
    data = dict(row)
    data["blockers"] = json.loads(data["blockers"] or "[]")
    return data


def _salt(conn) -> str:
    row = conn.execute("SELECT value FROM flame_meta WHERE key='user_hash_salt'").fetchone()
    if row:
        return row[0]
    conn.execute(
        "INSERT OR IGNORE INTO flame_meta (key, value) VALUES ('user_hash_salt', ?)",
        (secrets.token_hex(16),),
    )
    return conn.execute("SELECT value FROM flame_meta WHERE key='user_hash_salt'").fetchone()[0]


def _user_hash(conn, user_id) -> str:
    return hashlib.sha256(f"{_salt(conn)}:{user_id}".encode()).hexdigest()[:16]


# ------------------------------------------------------------------------ setup
def init(path=None) -> int:
    """Apply migrations and make sure the pseudonymisation salt exists."""
    version = migrations.apply_all(path)
    with connect(path) as conn:
        with tx(conn):
            _salt(conn)
    return version


# --------------------------------------------------------------------- missions
def get_mission(mission_id, path=None):
    with connect(path) as conn:
        return _mission_dict(conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone())


def active_mission(path=None):
    with connect(path) as conn:
        return _mission_dict(conn.execute("SELECT * FROM missions WHERE status='active'").fetchone())


def list_missions(path=None):
    with connect(path) as conn:
        return [_mission_dict(r) for r in conn.execute("SELECT * FROM missions ORDER BY id")]


def create_mission(mission_id, title, goal, success_measure="", target_proofs=None, owner="",
                   next_move="", parent=None, *, now=None, path=None):
    if not config.MISSION_ID_RE.match(mission_id or ""):
        raise FlameError("mission id must look like FLAME-001")
    fields = (
        _clean(title, "title", required=True, limit=200),
        _clean(goal, "goal", required=True),
        _clean(success_measure, "success_measure"),
        _target(target_proofs),
        _clean(owner, "owner", limit=200),
        _clean(next_move, "next_move"),
    )
    ts = _iso(now)
    with connect(path) as conn:
        try:
            with tx(conn):
                conn.execute(
                    """INSERT INTO missions (id, title, goal, success_measure, target_proofs, owner,
                       next_move, parent_mission_id, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (mission_id, *fields, parent, ts, ts),
                )
                _event(conn, mission_id, "created", {"parent": parent}, ts)
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc) or "PRIMARY" in str(exc):
                raise FlameError(f"{mission_id} already exists")
            raise FlameError(f"could not create {mission_id}: {exc}")
    return get_mission(mission_id, path)


def update_mission(mission_id, *, add_blocker=None, clear_blockers=False, now=None, path=None, **fields):
    unknown = set(fields) - set(ALLOWED_FIELDS)
    if unknown:
        raise FlameError(f"cannot update: {', '.join(sorted(unknown))}")
    ts = _iso(now)
    with connect(path) as conn:
        with tx(conn):
            row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            if row is None:
                raise FlameError(f"{mission_id} does not exist")
            if row["status"] == "closed":
                raise FlameError(f"{mission_id} is closed and can no longer be edited")
            sets, values = [], []
            for key, value in fields.items():
                if value is None:
                    continue
                if key == "target_proofs":
                    value = _target(value)
                elif key == "title":
                    value = _clean(value, key, required=True, limit=200)
                elif key == "owner":
                    value = _clean(value, key, limit=200)
                else:
                    value = _clean(value, key, required=(key == "goal"))
                sets.append(f"{key}=?")
                values.append(value)
            blockers = json.loads(row["blockers"] or "[]")
            if clear_blockers:
                blockers = []
            if add_blocker:
                blockers.append(_clean(add_blocker, "blocker", required=True, limit=300))
            if clear_blockers or add_blocker:
                sets.append("blockers=?")
                values.append(json.dumps(blockers))
            if not sets:
                raise FlameError("nothing to update")
            sets.append("updated_at=?")
            values.append(ts)
            conn.execute(f"UPDATE missions SET {', '.join(sets)} WHERE id=?", (*values, mission_id))
            _event(conn, mission_id, "updated", {"fields": sorted(k for k, v in fields.items() if v is not None)}, ts)
    return get_mission(mission_id, path)


def activate_mission(mission_id, *, now=None, path=None):
    ts = _iso(now)
    with connect(path) as conn:
        with tx(conn):
            row = conn.execute("SELECT status FROM missions WHERE id=?", (mission_id,)).fetchone()
            if row is None:
                raise FlameError(f"{mission_id} does not exist")
            if row["status"] != "draft":
                raise FlameError(f"{mission_id} is {row['status']}; only a draft can be activated")
            other = conn.execute("SELECT id FROM missions WHERE status='active'").fetchone()
            if other:
                raise FlameError(f"{other['id']} is already active; close it first")
            conn.execute(
                "UPDATE missions SET status='active', activated_at=?, updated_at=? WHERE id=?",
                (ts, ts, mission_id),
            )
            _event(conn, mission_id, "activated", {}, ts)
    return get_mission(mission_id, path)


def close_mission(mission_id, *, now=None, path=None):
    ts = _iso(now)
    with connect(path) as conn:
        with tx(conn):
            row = conn.execute("SELECT status FROM missions WHERE id=?", (mission_id,)).fetchone()
            if row is None:
                raise FlameError(f"{mission_id} does not exist")
            if row["status"] != "active":
                raise FlameError(f"{mission_id} is {row['status']}; only an active mission can be closed")
            conn.execute(
                "UPDATE missions SET status='closed', closed_at=?, updated_at=? WHERE id=?",
                (ts, ts, mission_id),
            )
            _event(conn, mission_id, "closed", {}, ts)
    return get_mission(mission_id, path)


# ----------------------------------------------------------------------- proofs
def record_proof(user_id, proof_hash, blessing, lang="en", *, now=None, path=None) -> dict:
    """Record a proof against the active mission (or unlinked if none is active).

    The same proof hash is recorded once per mission; a repeat is reported as
    duplicate and is not counted twice. The Telegram user id is never stored:
    only a salted hash, enough to count distinct participants.
    """
    proof_hash = (proof_hash or "").strip()[: config.MAX_PROOF_HASH_LEN]
    if not proof_hash:
        raise FlameError("proof hash is empty")
    blessing = _clean(blessing, "blessing", required=True, limit=32)
    ts = _iso(now)
    with connect(path) as conn:
        with tx(conn):
            active = conn.execute("SELECT id FROM missions WHERE status='active'").fetchone()
            mission_id = active["id"] if active else None
            existing = conn.execute(
                "SELECT id FROM mission_proofs WHERE COALESCE(mission_id,'')=? AND proof_hash=?",
                (mission_id or "", proof_hash),
            ).fetchone()
            if existing:
                _event(conn, mission_id, "proof_duplicate", {"proof_id": existing["id"]}, ts)
                return {"proof_id": existing["id"], "mission_id": mission_id,
                        "linked": mission_id is not None, "duplicate": True}
            cur = conn.execute(
                """INSERT INTO mission_proofs (mission_id, user_hash, proof_hash, blessing, lang, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (mission_id, _user_hash(conn, user_id), proof_hash, blessing, lang or "en", ts),
            )
            _event(conn, mission_id, "proof", {"proof_id": cur.lastrowid, "blessing": blessing}, ts)
            return {"proof_id": cur.lastrowid, "mission_id": mission_id,
                    "linked": mission_id is not None, "duplicate": False}


def set_delivery(proof_id, status, error=None, path=None) -> bool:
    if status not in ("pending", "delivered", "failed"):
        raise FlameError("delivery status must be pending, delivered or failed")
    with connect(path) as conn:
        with tx(conn):
            cur = conn.execute(
                "UPDATE mission_proofs SET delivery_status=?, delivery_error=? WHERE id=?",
                (status, (error or "")[:300] or None, proof_id),
            )
            return cur.rowcount == 1


def verify_proof(proof_id, status, *, now=None, path=None) -> bool:
    """A human marks a proof verified or rejected after checking it on-chain."""
    if status not in ("unverified", "verified", "rejected"):
        raise FlameError("verification status must be unverified, verified or rejected")
    ts = _iso(now)
    with connect(path) as conn:
        with tx(conn):
            row = conn.execute("SELECT mission_id FROM mission_proofs WHERE id=?", (proof_id,)).fetchone()
            if row is None:
                raise FlameError(f"proof {proof_id} does not exist")
            conn.execute("UPDATE mission_proofs SET verification_status=? WHERE id=?", (status, proof_id))
            _event(conn, row["mission_id"], "proof_verification", {"proof_id": proof_id, "status": status}, ts)
    return True


def list_proofs(mission_id, path=None):
    with connect(path) as conn:
        rows = conn.execute(
            """SELECT id, mission_id, substr(user_hash,1,8) AS participant, proof_hash, blessing,
                      verification_status, delivery_status, delivery_error, created_at
               FROM mission_proofs WHERE COALESCE(mission_id,'')=? ORDER BY id""",
            (mission_id or "",),
        ).fetchall()
    return [dict(r) for r in rows]


def user_proof_count(user_id, mission_id, path=None) -> int:
    with connect(path) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM mission_proofs WHERE mission_id=? AND user_hash=?",
            (mission_id, _user_hash(conn, user_id)),
        ).fetchone()[0]


def _stats(conn, mission_id):
    rows = conn.execute(
        "SELECT blessing, verification_status v, delivery_status d, user_hash u, created_at t "
        "FROM mission_proofs WHERE mission_id=?",
        (mission_id,),
    ).fetchall()
    counted = [r for r in rows if r["v"] != "rejected"]
    by_blessing = {}
    for r in counted:
        by_blessing[r["blessing"]] = by_blessing.get(r["blessing"], 0) + 1
    times = sorted(r["t"] for r in counted)
    return {
        "total": len(rows),
        "counted": len(counted),
        "participants": len({r["u"] for r in counted}),
        "by_blessing": dict(sorted(by_blessing.items())),
        "verified": sum(1 for r in counted if r["v"] == "verified"),
        "unverified": sum(1 for r in counted if r["v"] == "unverified"),
        "rejected": len(rows) - len(counted),
        "delivered": sum(1 for r in counted if r["d"] == "delivered"),
        "failed": sum(1 for r in counted if r["d"] == "failed"),
        "pending": sum(1 for r in counted if r["d"] == "pending"),
        "first_at": times[0] if times else None,
        "last_at": times[-1] if times else None,
    }


def snapshot(mission_id=None, path=None) -> dict:
    """Operator view: the given mission, else the active one."""
    with connect(path) as conn:
        if mission_id:
            row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            if row is None:
                raise FlameError(f"{mission_id} does not exist")
        else:
            row = conn.execute("SELECT * FROM missions WHERE status='active'").fetchone()
        mission = _mission_dict(row)
        stats = _stats(conn, mission["id"]) if mission else None
        target = mission["target_proofs"] if mission else None
        progress = None
        if mission:
            pct = round(100 * stats["counted"] / target) if target else None
            progress = {"target": target, "counted": stats["counted"], "pct": pct}
        drafts = [r["id"] for r in conn.execute("SELECT id FROM missions WHERE status='draft' ORDER BY id")]
        pending_outcome = [
            r["id"] for r in conn.execute(
                """SELECT m.id FROM missions m LEFT JOIN mission_outcomes o ON o.mission_id=m.id
                   WHERE m.status='closed' AND o.mission_id IS NULL ORDER BY m.id"""
            )
        ]
        unlinked = conn.execute("SELECT COUNT(*) FROM mission_proofs WHERE mission_id IS NULL").fetchone()[0]
    return {"mission": mission, "proofs": stats, "progress": progress, "drafts": drafts,
            "closed_without_outcome": pending_outcome, "unlinked_proofs": unlinked}


# -------------------------------------------------------------------- outcomes
def _next_mission_id(conn) -> str:
    top = 0
    for (mid,) in conn.execute("SELECT id FROM missions"):
        match = re.match(r"^FLAME-(\d+)$", mid)
        if match:
            top = max(top, int(match.group(1)))
    return f"FLAME-{top + 1:03d}"


def _conversation_count(conn, mission):
    """Aggregate message count in the mission window, or None if unavailable."""
    if not mission["activated_at"] or not mission["closed_at"]:
        return None
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='conversations'"
    ).fetchone()
    if not exists:
        return None
    return conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE role='user' "
        "AND datetime(created_at) BETWEEN datetime(?) AND datetime(?)",
        (mission["activated_at"], mission["closed_at"]),
    ).fetchone()[0]


def _outcome_dict(row):
    return {
        "mission_id": row["mission_id"],
        "evidence": json.loads(row["evidence"]),
        "result": row["result"],
        "decision": row["decision"],
        "learning": json.loads(row["learning"]),
        "next_mission_id": row["next_mission_id"],
        "generated_by": row["generated_by"],
        "created_at": row["created_at"],
    }


def get_outcome(mission_id, path=None):
    with connect(path) as conn:
        row = conn.execute("SELECT * FROM mission_outcomes WHERE mission_id=?", (mission_id,)).fetchone()
        return _outcome_dict(row) if row else None


def generate_outcome(mission_id, *, now=None, path=None) -> dict:
    """Write the outcome and a DRAFT next mission for a closed mission.

    Idempotent: a second call returns the stored outcome and creates nothing.
    The next mission is only a draft; a human reviews and activates it.
    """
    ts = _iso(now)
    with connect(path) as conn:
        with tx(conn):
            row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            if row is None:
                raise FlameError(f"{mission_id} does not exist")
            mission = _mission_dict(row)
            if mission["status"] != "closed":
                raise FlameError(f"{mission_id} is {mission['status']}; close it before generating the outcome")
            existing = conn.execute("SELECT * FROM mission_outcomes WHERE mission_id=?", (mission_id,)).fetchone()
            if existing:
                return _outcome_dict(existing)
            stats = _stats(conn, mission_id)
            duplicates = conn.execute(
                "SELECT COUNT(*) FROM mission_events WHERE mission_id=? AND kind='proof_duplicate'",
                (mission_id,),
            ).fetchone()[0]
            verdict = rules.evaluate(mission, stats, _conversation_count(conn, mission), duplicates)
            nxt = verdict["next"]
            next_id = _next_mission_id(conn)
            conn.execute(
                """INSERT INTO missions (id, title, goal, success_measure, target_proofs, owner,
                   next_move, parent_mission_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (next_id, nxt["title"], nxt["goal"], nxt["success_measure"], nxt["target_proofs"],
                 nxt["owner"], nxt["next_move"], mission_id, ts, ts),
            )
            _event(conn, next_id, "created", {"parent": mission_id, "draft": True}, ts)
            conn.execute(
                """INSERT INTO mission_outcomes (mission_id, evidence, result, decision, learning,
                   next_mission_id, generated_by, created_at) VALUES (?,?,?,?,?,?,'rules',?)""",
                (mission_id, json.dumps(verdict["evidence"], sort_keys=True), verdict["result"],
                 verdict["decision"], json.dumps(verdict["learning"]), next_id, ts),
            )
            _event(conn, mission_id, "outcome", {"result": verdict["result"], "next": next_id}, ts)
            return _outcome_dict(
                conn.execute("SELECT * FROM mission_outcomes WHERE mission_id=?", (mission_id,)).fetchone()
            )
