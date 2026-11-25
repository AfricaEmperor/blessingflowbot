"""Shared fixtures.

main.py has import-time side effects (it creates a Bot and initialises the
SQLite memory DB), so the memory DB path is redirected to a temp directory
*before* main is first imported. Nothing here touches the real database or
the real proofs.json.
"""
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN-NOT-REAL")
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("FLAME_ADMIN_IDS", None)

_SESSION_DIR = tempfile.mkdtemp(prefix="blessingflow-tests-")
os.environ["FLAME_DB_PATH"] = os.path.join(_SESSION_DIR, "session.db")

import db.memory as memory  # noqa: E402

memory.DB_PATH = os.path.join(_SESSION_DIR, "session-memory.db")


@pytest.fixture
def main_mod(tmp_path, monkeypatch):
    """main.py with all persistence redirected into tmp_path."""
    monkeypatch.setattr(memory, "DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("FLAME_DB_PATH", str(tmp_path / "flame.db"))
    memory.init_db()
    import main  # noqa: WPS433

    monkeypatch.setattr(main, "LOG_PATH", str(tmp_path / "proofs.json"))
    if hasattr(main, "flame"):
        main.flame.init()
    return main


def make_update(user_id=42, chat_id=4242, text=""):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=user_id)
    update.effective_chat = SimpleNamespace(id=chat_id)
    update.message.text = text
    return update


def make_context(args=None):
    return SimpleNamespace(args=list(args or []))


@pytest.fixture
def mk():
    return SimpleNamespace(update=make_update, context=make_context)
