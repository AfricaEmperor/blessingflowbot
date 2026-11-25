"""Persistent Flame Loop mission, proof, outcome and next-mission records.

Uses the existing BlessingFlowBot SQLite database. Proofs are self-reported and
remain explicitly unverified until an independent chain verifier is implemented.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from db.memory import DB_PATH, init_db


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def active_mission():
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM missions WHERE status='active' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_mission(mission_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
    return dict(row) if row else None


def create_mission(title, objective=None, channel="Telegram", status="active", parent_mission_id=None):
    title = (title or "").strip()
    if not title:
        raise ValueError("Mission title is required")
    with _connect() as conn:
        active = conn.execute("SELECT mission_id FROM missions WHERE status='active'").fetchone()
        if status == "active" and active:
            raise ValueError(f"Active mission already exists: {active['mission_id']}. Close it before creating another.")
        last = conn.execute("SELECT mission_id FROM missions ORDER BY created_at DESC LIMIT 1").fetchone()
        n = int(last["mission_id"].split("-")[-1]) + 1 if last else 1
        mission_id = f"FLAME-{n:03d}"
        conn.execute(
            """INSERT INTO missions
            (mission_id,title,objective,channel,status,blockers,next_move,parent_mission_id,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (mission_id,title,objective or title,channel,status,json.dumps([]), "Define deliverable and launch", parent_mission_id,_now(),_now())
        )
        return get_mission(mission_id)


def update_mission(mission_id, **fields):
    allowed = {"status", "blockers", "next_move", "objective", "channel", "title"}
    values = {k:v for k,v in fields.items() if k in allowed and v is not None}
    if "blockers" in values and not isinstance(values["blockers"], str):
        values["blockers"] = json.dumps(values["blockers"])
    if not values:
        return get_mission(mission_id)
    values["updated_at"] = _now()
    with _connect() as conn:
        row = conn.execute("SELECT mission_id FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE missions SET " + ",".join(f"{k}=?" for k in values) + " WHERE mission_id=?",
            (*values.values(), mission_id)
        )
    return get_mission(mission_id)


def record_proof(user_id, proof_hash, blessing, mission_id=None):
    mission = get_mission(mission_id) if mission_id else active_mission()
    linked_id = mission["mission_id"] if mission else None
    with _connect() as conn:
        cursor = conn.execute(
            """INSERT INTO proof_events
            (mission_id,user_id,proof_hash,blessing,verification_status,created_at)
            VALUES (?,?,?,?,?,?)""",
            (linked_id,user_id,proof_hash,blessing,"unverified",_now())
        )
        proof_id = cursor.lastrowid
    return {"proof_id":proof_id,"mission_id":linked_id,"verification_status":"unverified"}


def mission_proofs(mission_id):
    with _connect() as conn:
        rows=conn.execute(
            "SELECT proof_id,blessing,verification_status,created_at FROM proof_events WHERE mission_id=? ORDER BY proof_id",
            (mission_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def generate_outcome(mission_id):
    mission=get_mission(mission_id)
    if not mission:
        raise ValueError("Mission not found")
    proofs=mission_proofs(mission_id)
    verified=sum(1 for p in proofs if p["verification_status"]=="verified")
    unverified=len(proofs)-verified
    outcome={
        "mission_id":mission_id,
        "title":mission["title"],
        "objective":mission["objective"],
        "status":mission["status"],
        "proof_count":len(proofs),
        "verified_proofs":verified,
        "unverified_proofs":unverified,
        "evidence_limitations":"Proof submissions are logged but not independently verified on-chain.",
        "interpretation":"Participation evidence is limited to proof submissions captured by the bot. No reach or engagement metrics are integrated.",
        "decision":"Review the drop and community response manually; choose the next mission based on observed evidence.",
        "generated_at":_now()
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO mission_outcomes (mission_id,outcome_json,created_at) VALUES (?,?,?)",
            (mission_id,json.dumps(outcome,ensure_ascii=False),outcome["generated_at"])
        )
    return outcome


def latest_outcome(mission_id):
    with _connect() as conn:
        row=conn.execute(
            "SELECT outcome_json FROM mission_outcomes WHERE mission_id=? ORDER BY outcome_id DESC LIMIT 1",
            (mission_id,)
        ).fetchone()
    return json.loads(row["outcome_json"]) if row else None


def generate_next_mission(mission_id):
    outcome=latest_outcome(mission_id)
    if not outcome:
        outcome=generate_outcome(mission_id)
    proposal={
        "parent_mission_id":mission_id,
        "title":f"Follow-up to {mission_id}: {outcome['decision']}",
        "objective":f"Review {outcome['proof_count']} proof submission(s) ({outcome['verified_proofs']} verified, {outcome['unverified_proofs']} unverified) and run the next iteration based on manual review.",
        "channel":"Telegram",
        "status":"proposed",
        "requires_human_approval":True,
        "created_at":_now()
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO next_mission_proposals (parent_mission_id,proposal_json,created_at) VALUES (?,?,?)",
            (mission_id,json.dumps(proposal,ensure_ascii=False),proposal["created_at"])
        )
    return proposal
