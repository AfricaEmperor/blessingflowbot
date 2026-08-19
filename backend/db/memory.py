import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "blessing_memory.db")


def init_db():
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
