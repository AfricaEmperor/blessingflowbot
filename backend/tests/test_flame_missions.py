import pytest

from flame import service
from flame.errors import FlameError


@pytest.fixture
def p(tmp_path):
    path = str(tmp_path / "flame.db")
    service.init(path)
    return path


def mk(p, mid="FLAME-001", **kw):
    kw.setdefault("title", "Ignition")
    kw.setdefault("goal", "Light the flame")
    return service.create_mission(mid, path=p, **kw)


def test_create_draft_persists(p):
    m = mk(p, target_proofs=10, owner="Admin")
    assert (m["id"], m["status"], m["target_proofs"], m["owner"]) == ("FLAME-001", "draft", 10, "Admin")
    assert service.get_mission("FLAME-001", p)["goal"] == "Light the flame"


@pytest.mark.parametrize("bad", ["flame-1", "FLAME-1", "MISSION-001", "", "FLAME-001; DROP TABLE missions"])
def test_bad_ids_rejected(p, bad):
    with pytest.raises(FlameError):
        mk(p, bad)


def test_required_fields_and_target(p):
    with pytest.raises(FlameError):
        service.create_mission("FLAME-001", "", "g", path=p)
    with pytest.raises(FlameError):
        service.create_mission("FLAME-001", "t", "", path=p)
    with pytest.raises(FlameError):
        mk(p, target_proofs=0)
    with pytest.raises(FlameError):
        mk(p, target_proofs="many")


def test_duplicate_id_rejected(p):
    mk(p)
    with pytest.raises(FlameError, match="already exists"):
        mk(p)


def test_only_one_active_mission(p):
    mk(p, "FLAME-001")
    mk(p, "FLAME-002")
    service.activate_mission("FLAME-001", path=p)
    with pytest.raises(FlameError, match="already active"):
        service.activate_mission("FLAME-002", path=p)
    service.close_mission("FLAME-001", path=p)
    assert service.activate_mission("FLAME-002", path=p)["status"] == "active"


def test_lifecycle_rules(p):
    mk(p)
    with pytest.raises(FlameError):
        service.close_mission("FLAME-001", path=p)  # draft cannot be closed
    service.activate_mission("FLAME-001", path=p)
    with pytest.raises(FlameError):
        service.activate_mission("FLAME-001", path=p)  # already active
    closed = service.close_mission("FLAME-001", path=p)
    assert closed["status"] == "closed" and closed["closed_at"]
    with pytest.raises(FlameError, match="closed"):
        service.update_mission("FLAME-001", goal="x", path=p)
    with pytest.raises(FlameError):
        service.activate_mission("FLAME-001", path=p)


def test_update_fields_and_blockers(p):
    mk(p)
    m = service.update_mission("FLAME-001", title="New", target_proofs=5, next_move="Post it",
                               add_blocker="Need QR", path=p)
    assert (m["title"], m["target_proofs"], m["next_move"], m["blockers"]) == ("New", 5, "Post it", ["Need QR"])
    m = service.update_mission("FLAME-001", add_blocker="Need audio", path=p)
    assert m["blockers"] == ["Need QR", "Need audio"]
    m = service.update_mission("FLAME-001", clear_blockers=True, path=p)
    assert m["blockers"] == []
    with pytest.raises(FlameError):
        service.update_mission("FLAME-001", path=p)  # nothing to update
    with pytest.raises(FlameError):
        service.update_mission("FLAME-001", status="closed", path=p)  # not an editable field
    with pytest.raises(FlameError):
        service.update_mission("FLAME-009", goal="x", path=p)


def test_state_survives_reconnect(p):
    mk(p)
    service.activate_mission("FLAME-001", path=p)
    assert service.active_mission(p)["id"] == "FLAME-001"  # new connection each call


def test_events_form_an_audit_trail(p):
    mk(p)
    service.activate_mission("FLAME-001", path=p)
    service.close_mission("FLAME-001", path=p)
    from flame.store import connect

    with connect(p) as c:
        kinds = [r[0] for r in c.execute("SELECT kind FROM mission_events ORDER BY id")]
    assert kinds == ["created", "activated", "closed"]


def test_database_itself_enforces_single_active(p):
    """Backstop for races: even bypassing the service, a second active row is refused."""
    import sqlite3

    from flame.store import connect

    mk(p, "FLAME-001")
    mk(p, "FLAME-002")
    service.activate_mission("FLAME-001", path=p)
    with connect(p) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("UPDATE missions SET status='active' WHERE id='FLAME-002'")


def test_racing_activations_yield_exactly_one_active(p):
    import threading

    for i in range(1, 6):
        mk(p, f"FLAME-00{i}")
    results = []

    def go(mid):
        try:
            service.activate_mission(mid, path=p)
            results.append("ok")
        except FlameError:
            results.append("refused")

    threads = [threading.Thread(target=go, args=(f"FLAME-00{i}",)) for i in range(1, 6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == ["ok"] + ["refused"] * 4
    assert sum(m["status"] == "active" for m in service.list_missions(p)) == 1
