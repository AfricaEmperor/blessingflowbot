"""Additive, versioned schema migrations.

Rules: never alter or drop the bot's existing tables (conversations,
user_prefs). Each migration runs in one transaction and is recorded in
schema_migrations, so applying twice is a no-op.
"""
from datetime import datetime, timezone

from .store import connect, tx

_V1 = [
    """CREATE TABLE flame_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    """CREATE TABLE missions (
        id TEXT PRIMARY KEY CHECK (id GLOB 'FLAME-[0-9][0-9][0-9]*'),
        title TEXT NOT NULL,
        goal TEXT NOT NULL,
        success_measure TEXT NOT NULL DEFAULT '',
        target_proofs INTEGER CHECK (target_proofs IS NULL OR target_proofs > 0),
        owner TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','closed')),
        next_move TEXT NOT NULL DEFAULT '',
        blockers TEXT NOT NULL DEFAULT '[]',
        parent_mission_id TEXT REFERENCES missions(id),
        created_at TEXT NOT NULL,
        activated_at TEXT,
        closed_at TEXT,
        updated_at TEXT NOT NULL
    )""",
    "CREATE UNIQUE INDEX idx_one_active_mission ON missions(status) WHERE status = 'active'",
    """CREATE TABLE mission_proofs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mission_id TEXT REFERENCES missions(id),
        user_hash TEXT NOT NULL,
        proof_hash TEXT NOT NULL,
        blessing TEXT NOT NULL,
        lang TEXT NOT NULL DEFAULT 'en',
        verification_status TEXT NOT NULL DEFAULT 'unverified'
            CHECK (verification_status IN ('unverified','verified','rejected')),
        delivery_status TEXT NOT NULL DEFAULT 'pending'
            CHECK (delivery_status IN ('pending','delivered','failed')),
        delivery_error TEXT,
        created_at TEXT NOT NULL
    )""",
    "CREATE UNIQUE INDEX idx_proof_unique ON mission_proofs(COALESCE(mission_id, ''), proof_hash)",
    "CREATE INDEX idx_proofs_mission ON mission_proofs(mission_id, created_at)",
    """CREATE TABLE mission_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mission_id TEXT REFERENCES missions(id),
        kind TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX idx_events_mission ON mission_events(mission_id, id)",
    """CREATE TABLE mission_outcomes (
        mission_id TEXT PRIMARY KEY REFERENCES missions(id),
        evidence TEXT NOT NULL,
        result TEXT NOT NULL,
        decision TEXT NOT NULL,
        learning TEXT NOT NULL,
        next_mission_id TEXT REFERENCES missions(id),
        generated_by TEXT NOT NULL DEFAULT 'rules',
        created_at TEXT NOT NULL
    )""",
]

MIGRATIONS = [(1, "flame_loop_v0_1", _V1)]


def current_version(conn) -> int:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if not exists:
        return 0
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return row[0] or 0


def apply_all(path=None) -> int:
    """Apply pending migrations. Returns the schema version after applying."""
    with connect(path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )"""
        )
        applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        for version, name, statements in MIGRATIONS:
            if version in applied:
                continue
            with tx(conn):
                # Re-check under the write lock: another process may have won.
                if conn.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=?", (version,)
                ).fetchone():
                    continue
                for stmt in statements:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?,?,?)",
                    (version, name, datetime.now(timezone.utc).isoformat(timespec="seconds")),
                )
        return current_version(conn)
