"""Characterisation tests for the behaviour that existed before Flame Loop v0.1.

These pin what the bot already did so the loop work cannot silently change it.
"""
import json

import pytest


@pytest.fixture
def fake_priest(monkeypatch):
    import ai.portal_priest as priest

    monkeypatch.setattr(priest, "get_proof_blessing", lambda b, h, lang, hist: f"RITUAL[{b}]")
    monkeypatch.setattr(priest, "get_flow_guidance", lambda lang, hist: f"FLOW[{lang}]")
    monkeypatch.setattr(priest, "get_priest_response", lambda text, hist: f"PRIEST[{text}]")
    return priest


@pytest.fixture
def dispatched(monkeypatch):
    import blessings.dispatcher as dispatcher

    calls = []
    monkeypatch.setattr(
        dispatcher, "dispatch_blessing", lambda bot, chat, key, lang: calls.append((chat, key, lang))
    )
    return calls


def test_start_and_language_switch(main_mod, mk):
    u = mk.update()
    main_mod.start(u, mk.context())
    assert "Welcome to BlessingFlowBot" in u.message.reply_text.call_args[0][0]

    main_mod.switch_fr(mk.update(), mk.context())
    u2 = mk.update()
    main_mod.start(u2, mk.context())
    assert "Bienvenue" in u2.message.reply_text.call_args[0][0]

    main_mod.switch_en(mk.update(), mk.context())
    u3 = mk.update()
    main_mod.start(u3, mk.context())
    assert "Welcome" in u3.message.reply_text.call_args[0][0]


def test_help_lists_existing_commands(main_mod, mk):
    u = mk.update()
    main_mod.help_cmd(u, mk.context())
    text = u.message.reply_text.call_args[0][0]
    for cmd in ("/flow", "/proof", "/fr", "/en"):
        assert cmd in text


def test_proof_without_hash_prompts(main_mod, mk, dispatched):
    u = mk.update()
    main_mod.proof(u, mk.context([]))
    assert "/proof <hash>" in u.message.reply_text.call_args[0][0]
    assert dispatched == []


def test_proof_logs_replies_and_dispatches(main_mod, mk, fake_priest, dispatched):
    u = mk.update(user_id=7, chat_id=99)
    main_mod.proof(u, mk.context(["ABC123", "courage"]))

    with open(main_mod.LOG_PATH) as f:
        entry = json.loads(f.readline())
    assert entry == {"user_id": 7, "hash": "ABC123", "blessing": "courage"}
    assert u.message.reply_text.call_args[0][0] == "RITUAL[courage]"
    assert dispatched == [(99, "courage", "en")]


def test_proof_unknown_blessing_defaults_to_flow(main_mod, mk, fake_priest, dispatched):
    main_mod.proof(mk.update(), mk.context(["H1", "not-a-blessing"]))
    assert dispatched[0][1] == "flow"


def test_proof_falls_back_when_ai_unavailable(main_mod, mk, monkeypatch, dispatched):
    import ai.portal_priest as priest

    def boom(*a, **k):
        raise RuntimeError("no api key")

    monkeypatch.setattr(priest, "get_proof_blessing", boom)
    u = mk.update()
    main_mod.proof(u, mk.context(["H2", "clarity"]))
    assert "clarity" in u.message.reply_text.call_args[0][0]
    assert dispatched == [(4242, "clarity", "en")]


def test_conversation_memory_roundtrip(main_mod, mk, fake_priest):
    u = mk.update(user_id=5, text="hello")
    main_mod.handle_message(u, mk.context())
    assert u.message.reply_text.call_args[0][0] == "PRIEST[hello]"
    from db.memory import get_history

    assert [m["role"] for m in get_history(5)] == ["user", "assistant"]


def test_unknown_command_fallback(main_mod, mk):
    u = mk.update()
    main_mod.fallback(u, mk.context())
    assert "Unknown command" in u.message.reply_text.call_args[0][0]


def test_registered_commands_include_originals(main_mod):
    names = set()
    for group in main_mod.dispatcher.handlers.values():
        for h in group:
            names.update(getattr(h, "command", []) or [])
    assert {"start", "flow", "help", "proof", "fr", "en"} <= names


def test_dispatch_failure_is_contained(main_mod, mk, fake_priest):
    """backend/assets/ is not in the repo, so the real dispatcher raises
    FileNotFoundError. Before Flame Loop v0.1 that escaped the handler after
    the reply had been sent. It is now logged and recorded, not raised."""
    u = mk.update()
    main_mod.proof(u, mk.context(["H3", "flow"]))  # must not raise
    assert u.message.reply_text.called


def test_flow_command_replies_with_guidance(main_mod, mk, fake_priest):
    u = mk.update()
    main_mod.flow(u, mk.context())
    assert u.message.reply_text.call_args[0][0] == "FLOW[en]"
