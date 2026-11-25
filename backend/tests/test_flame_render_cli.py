import json

import pytest

from flame import cli, render, service


@pytest.fixture
def p(tmp_path, monkeypatch):
    path = str(tmp_path / "flame.db")
    monkeypatch.setenv("FLAME_DB_PATH", path)
    service.init(path)
    return path


def seeded(p):
    service.create_mission("FLAME-001", "Flame Ignition", "Light it", target_proofs=4, owner="Admin",
                           next_move="Post the drop", path=p)
    service.update_mission("FLAME-001", add_blocker="Need QR", path=p)
    service.activate_mission("FLAME-001", path=p)
    service.record_proof(1, "A", "flow", path=p)
    service.record_proof(2, "B", "courage", path=p)


def test_status_without_mission(p):
    snap = service.snapshot(path=p)
    assert render.render_status(snap, "en") == "No active mission."
    assert "Aucune mission active" in render.render_status(snap, "fr")


def test_public_status_hides_operator_detail(p):
    seeded(p)
    text = render.render_status(service.snapshot(path=p), "en", admin=False, user_proofs=1)
    assert "FLAME-001" in text and "Your proofs: 1" in text
    for secret in ("Need QR", "Post the drop", "participants", "Blessings"):
        assert secret not in text


def test_admin_status_shows_operator_detail(p):
    seeded(p)
    text = render.render_status(service.snapshot(path=p), "en", admin=True)
    for expected in ("2 of 4 target (50%)", "2 participants", "courage 1, flow 1", "0 verified, 2 unverified",
                     "Need QR", "Post the drop"):
        assert expected in text


def test_french_status(p):
    seeded(p)
    text = render.render_status(service.snapshot(path=p), "fr", admin=False, user_proofs=2)
    assert "Vos preuves: 2" in text and "Statut" in text


def test_admin_status_flags_closed_without_outcome_and_drafts(p):
    seeded(p)
    service.close_mission("FLAME-001", path=p)
    text = render.render_status(service.snapshot(path=p), "en", admin=True)
    assert "Closed, outcome not generated: FLAME-001" in text


def test_admin_ids_parsing(monkeypatch):
    from flame import config

    monkeypatch.delenv("FLAME_ADMIN_IDS", raising=False)
    assert config.admin_ids() == frozenset() and not config.is_admin(1)
    monkeypatch.setenv("FLAME_ADMIN_IDS", " 1, 2 ,abc,,-3 ")
    assert config.admin_ids() == frozenset({1, 2, -3})


def test_cli_full_cycle(p, capsys):
    assert cli.main(["create", "FLAME-001", "--title", "Ignition", "--goal", "Light it",
                     "--target-proofs", "2", "--owner", "Admin"]) == 0
    assert cli.main(["activate", "FLAME-001"]) == 0
    service.record_proof(1, "A", "flow", path=p)
    service.record_proof(2, "B", "flow", path=p)
    assert cli.main(["proofs"]) == 0
    assert cli.main(["verify", "1", "verified"]) == 0
    assert cli.main(["close", "FLAME-001"]) == 0
    capsys.readouterr()
    assert cli.main(["outcome", "FLAME-001", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["result"] == "met" and out["next_mission_id"] == "FLAME-002"
    assert cli.main(["outcome", "FLAME-001"]) == 0  # idempotent, text form
    assert "NEXT MISSION (draft" in capsys.readouterr().out
    assert cli.main(["missions"]) == 0


def test_cli_errors_exit_2(p, capsys):
    assert cli.main(["activate", "FLAME-404"]) == 2
    assert "does not exist" in capsys.readouterr().err
    assert cli.main(["create", "bad-id", "--title", "t", "--goal", "g"]) == 2
    assert cli.main(["outcome", "FLAME-404"]) == 2


def test_one_participant_reads_correctly(p):
    service.create_mission("FLAME-001", "t", "g", target_proofs=1, path=p)
    service.activate_mission("FLAME-001", path=p)
    service.record_proof(1, "A", "flow", path=p)
    text = render.render_status(service.snapshot(path=p), "en", admin=True)
    assert "1 participant" in text and "1 participants" not in text
    service.close_mission("FLAME-001", path=p)
    out = service.generate_outcome("FLAME-001", path=p)
    report = render.render_outcome(out, service.get_mission("FLAME-001", p))
    assert "1 proof from 1 participant" in report
