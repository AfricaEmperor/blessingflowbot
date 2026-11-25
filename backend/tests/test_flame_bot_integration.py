"""Flame Loop wired into the Telegram handlers."""
import pytest

from flame import service


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    import ai.portal_priest as priest

    monkeypatch.setattr(priest, "get_proof_blessing", lambda b, h, lang, hist: f"RITUAL[{b}]")


@pytest.fixture
def sent(monkeypatch):
    import blessings.dispatcher as dispatcher

    calls = []
    monkeypatch.setattr(dispatcher, "dispatch_blessing", lambda bot, chat, key, lang: calls.append(key))
    return calls


def open_mission(target=2):
    service.create_mission("FLAME-001", "Flame Ignition", "Light it", target_proofs=target)
    service.activate_mission("FLAME-001")


def test_proof_is_linked_and_marked_delivered(main_mod, mk, sent):
    open_mission()
    u = mk.update(user_id=7)
    main_mod.proof(u, mk.context(["HASH1", "courage"]))
    row = service.list_proofs("FLAME-001")[0]
    assert (row["blessing"], row["delivery_status"], row["verification_status"]) == ("courage", "delivered", "unverified")
    assert u.message.reply_text.call_args[0][0] == "RITUAL[courage]"
    assert sent == ["courage"]


def test_legacy_proofs_json_still_written(main_mod, mk, sent):
    import json

    open_mission()
    main_mod.proof(mk.update(user_id=7), mk.context(["HASH1", "flow"]))
    with open(main_mod.LOG_PATH) as f:
        assert json.loads(f.readline()) == {"user_id": 7, "hash": "HASH1", "blessing": "flow"}


def test_dispatch_failure_recorded_not_raised(main_mod, mk, monkeypatch):
    import blessings.dispatcher as dispatcher

    def boom(*a, **k):
        raise FileNotFoundError("assets/flow/flow_qr.png")

    monkeypatch.setattr(dispatcher, "dispatch_blessing", boom)
    open_mission()
    u = mk.update()
    main_mod.proof(u, mk.context(["HASH1", "flow"]))
    row = service.list_proofs("FLAME-001")[0]
    assert row["delivery_status"] == "failed" and "FileNotFoundError" in row["delivery_error"]
    assert u.message.reply_text.called


def test_proof_still_works_if_mission_store_breaks(main_mod, mk, sent, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db locked")

    monkeypatch.setattr(main_mod.flame, "record_proof", boom)
    u = mk.update()
    main_mod.proof(u, mk.context(["HASH1", "flow"]))
    assert u.message.reply_text.call_args[0][0] == "RITUAL[flow]"
    assert sent == ["flow"]


def test_duplicate_proof_still_gets_blessing_but_counts_once(main_mod, mk, sent):
    open_mission()
    main_mod.proof(mk.update(user_id=1), mk.context(["HASH1", "flow"]))
    main_mod.proof(mk.update(user_id=1), mk.context(["HASH1", "flow"]))
    assert len(service.list_proofs("FLAME-001")) == 1
    assert sent == ["flow", "flow"]


def test_proof_with_no_active_mission_is_unlinked(main_mod, mk, sent):
    main_mod.proof(mk.update(), mk.context(["HASH1", "flow"]))
    assert service.snapshot()["unlinked_proofs"] == 1


def test_status_public_view(main_mod, mk, sent):
    open_mission()
    main_mod.proof(mk.update(user_id=7), mk.context(["HASH1", "flow"]))
    u = mk.update(user_id=7)
    main_mod.status_cmd(u, mk.context())
    text = u.message.reply_text.call_args[0][0]
    assert "FLAME-001" in text and "Your proofs: 1" in text and "target" not in text


def test_status_without_mission(main_mod, mk):
    u = mk.update()
    main_mod.status_cmd(u, mk.context())
    assert u.message.reply_text.call_args[0][0] == "No active mission."


def test_status_admin_view(main_mod, mk, sent, monkeypatch):
    monkeypatch.setenv("FLAME_ADMIN_IDS", "99")
    open_mission()
    main_mod.proof(mk.update(user_id=7), mk.context(["HASH1", "flow"]))
    u = mk.update(user_id=99)
    main_mod.status_cmd(u, mk.context())
    assert "1 of 2 target (50%)" in u.message.reply_text.call_args[0][0]


def test_outcome_command_is_admin_only(main_mod, mk, monkeypatch):
    u = mk.update(user_id=5)
    main_mod.outcome_cmd(u, mk.context(["FLAME-001"]))
    assert "Unknown command" in u.message.reply_text.call_args[0][0]
    monkeypatch.setenv("FLAME_ADMIN_IDS", "5")
    u = mk.update(user_id=5)
    main_mod.outcome_cmd(u, mk.context([]))
    assert "No closed mission" in u.message.reply_text.call_args[0][0]


def test_outcome_command_generates_for_admin(main_mod, mk, sent, monkeypatch):
    monkeypatch.setenv("FLAME_ADMIN_IDS", "5")
    open_mission(target=1)
    main_mod.proof(mk.update(user_id=7), mk.context(["HASH1", "flow"]))
    u = mk.update(user_id=5)
    main_mod.outcome_cmd(u, mk.context(["FLAME-001"]))
    assert "close it first" in u.message.reply_text.call_args[0][0].lower()  # still active
    service.close_mission("FLAME-001")
    u = mk.update(user_id=5)
    main_mod.outcome_cmd(u, mk.context([]))
    text = u.message.reply_text.call_args[0][0]
    assert "RESULT" in text and "met" in text and "FLAME-002" in text


def test_new_commands_registered_before_fallback(main_mod):
    handlers = [h for group in main_mod.dispatcher.handlers.values() for h in group]
    order = [tuple(getattr(h, "command", []) or []) for h in handlers]
    flat = [c for t in order for c in t]
    assert "status" in flat and "outcome" in flat
    assert type(handlers[-1]).__name__ == "MessageHandler"  # the unknown-command fallback stays last


def test_help_lists_status(main_mod, mk):
    u = mk.update()
    main_mod.help_cmd(u, mk.context())
    assert "/status" in u.message.reply_text.call_args[0][0]
