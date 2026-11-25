import sqlite3

import pytest

from flame import migrations, service
from flame.store import connect


@pytest.fixture
def path(tmp_path):
    return str(tmp_path / "flame.db")


def tables(p):
    with connect(p) as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_fresh_db_gets_schema(path):
    assert service.init(path) == 1
    assert {"missions", "mission_proofs", "mission_events", "mission_outcomes",
            "schema_migrations", "flame_meta"} <= tables(path)


def test_apply_twice_is_a_noop(path):
    service.init(path)
    service.init(path)
    with connect(path) as c:
        assert c.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_existing_memory_tables_and_rows_are_untouched(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
                 "role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE TABLE user_prefs (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'en')")
    conn.execute("INSERT INTO conversations (user_id, role, content) VALUES (1,'user','hello')")
    conn.execute("INSERT INTO user_prefs (user_id, lang) VALUES (1,'fr')")
    conn.commit()
    conn.close()
    service.init(path)
    with connect(path) as c:
        assert c.execute("SELECT content FROM conversations").fetchone()[0] == "hello"
        assert c.execute("SELECT lang FROM user_prefs").fetchone()[0] == "fr"
        cols = [r[1] for r in c.execute("PRAGMA table_info(conversations)")]
    assert cols == ["id", "user_id", "role", "content", "created_at"]


def test_failed_migration_rolls_back(path, monkeypatch):
    broken = [(1, "broken", ["CREATE TABLE ok_table (x)", "THIS IS NOT SQL"])]
    monkeypatch.setattr(migrations, "MIGRATIONS", broken)
    with pytest.raises(sqlite3.Error):
        migrations.apply_all(path)
    assert "ok_table" not in tables(path)
    with connect(path) as c:
        assert c.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0


def test_default_db_is_the_memory_db():
    """The loop must share the SQLite file the bot already uses by default."""
    import os

    import db.memory as memory
    from flame import config

    assert config.DEFAULT_DB_PATH == os.path.join(os.path.dirname(memory.__file__), "blessing_memory.db")
