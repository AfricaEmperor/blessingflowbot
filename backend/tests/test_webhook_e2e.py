"""POST real Telegram update JSON to the FastAPI /bot webhook.

Goes through FastAPI -> thread executor -> PTB dispatcher -> handler -> SQLite.
Only the outbound Telegram call (bot.send_message) and the AI/asset layers are
replaced.
"""
import pytest
from fastapi.testclient import TestClient

from flame import service


def update_json(update_id, user_id, text):
    entities = []
    if text.startswith("/"):
        entities = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 1700000000,
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "T"},
            "text": text,
            "entities": entities,
        },
    }


@pytest.fixture
def client(main_mod, monkeypatch):
    import ai.portal_priest as priest
    import blessings.dispatcher as dispatcher

    import telegram

    replies = []
    monkeypatch.setattr(
        telegram.Bot, "send_message", lambda self, chat_id, text=None, *a, **k: replies.append(text)
    )
    monkeypatch.setattr(
        telegram.Bot, "get_me", lambda self, *a, **k: telegram.User(1, "Bot", True, username="testbot")
    )
    monkeypatch.setattr(priest, "get_proof_blessing", lambda b, h, lang, hist: f"RITUAL[{b}]")
    monkeypatch.setattr(dispatcher, "dispatch_blessing", lambda bot, chat, key, lang: None)
    c = TestClient(main_mod.app)
    c.replies = replies
    return c


def texts(client):
    return client.replies


def test_full_cycle_through_the_webhook(client, monkeypatch):
    monkeypatch.setenv("FLAME_ADMIN_IDS", "1")
    service.create_mission("FLAME-001", "Flame Ignition", "Light it", target_proofs=2)
    service.activate_mission("FLAME-001")

    for i, user in enumerate((7, 8, 7), start=1):
        r = client.post("/bot", json=update_json(i, user, f"/proof HASH{i} flow"))
        assert r.status_code == 200 and r.json() == {"status": "ok"}

    stats = service.snapshot()["proofs"]
    assert (stats["counted"], stats["participants"], stats["delivered"]) == (3, 2, 3)

    client.post("/bot", json=update_json(10, 7, "/status"))
    assert "Your proofs: 2" in texts(client)[-1]

    client.post("/bot", json=update_json(11, 1, "/status"))
    assert "3 of 2 target" in texts(client)[-1]

    service.close_mission("FLAME-001")
    client.post("/bot", json=update_json(12, 1, "/outcome"))
    report = texts(client)[-1]
    assert "met" in report and "FLAME-002" in report and "self-reported" in report

    client.post("/bot", json=update_json(13, 7, "/outcome"))
    assert "Unknown command" in texts(client)[-1]  # a normal user gets nothing

    assert service.get_mission("FLAME-002")["status"] == "draft"
    assert service.active_mission() is None


def test_legacy_commands_still_answer(client):
    client.post("/bot", json=update_json(1, 7, "/start"))
    client.post("/bot", json=update_json(2, 7, "/help"))
    assert "Welcome to BlessingFlowBot" in texts(client)[0]
    assert "/status" in texts(client)[1]
