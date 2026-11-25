import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "blessing_memory.db")


def init_db():
    """Create legacy tables and idempotently migrate the DB for Flame Loop v0.1."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'en'
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_conv ON conversations(user_id, created_at)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS missions (
            mission_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            objective TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'Telegram',
            status TEXT NOT NULL DEFAULT 'active',
            blockers TEXT NOT NULL DEFAULT '[]',
            next_move TEXT NOT NULL DEFAULT '',
            parent_mission_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proof_events (
            proof_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT,
            user_id INTEGER NOT NULL,
            proof_hash TEXT NOT NULL,
            blessing TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'unverified',
            created_at TEXT NOT NULL,
            FOREIGN KEY(mission_id) REFERENCES missions(mission_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_proof_mission ON proof_events(mission_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mission_outcomes (
            outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT NOT NULL,
            outcome_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(mission_id) REFERENCES missions(mission_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS next_mission_proposals (
            proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_mission_id TEXT NOT NULL,
            proposal_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(parent_mission_id) REFERENCES missions(mission_id)
        )
    """)
    conn.commit()
    conn.close()


def get_history(user_id: int, limit: int = 20) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT role, content FROM conversations WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def save_exchange(user_id: int, user_msg: str, assistant_msg: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO conversations (user_id, role, content) VALUES (?, 'user', ?)",
        (user_id, user_msg),
    )
    conn.execute(
        "INSERT INTO conversations (user_id, role, content) VALUES (?, 'assistant', ?)",
        (user_id, assistant_msg),
    )
    conn.commit()
    conn.close()


def get_lang(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT lang FROM user_prefs WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "en"


def save_lang(user_id: int, lang: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO user_prefs (user_id, lang) VALUES (?, ?)",
        (user_id, lang),
    )
    conn.commit()
    conn.close()
