import pytest

from flame import service
from flame.errors import FlameError
from flame.store import connect


@pytest.fixture
def p(tmp_path):
    path = str(tmp_path / "flame.db")
    service.init(path)
    service.create_mission("FLAME-001", "Ignition", "Light it", target_proofs=3, path=path)
    return path


def test_proof_links_to_active_mission(p):
    service.activate_mission("FLAME-001", path=p)
    r = service.record_proof(7, "HASH1", "flow", "en", path=p)
    assert r["mission_id"] == "FLAME-001" and r["linked"] and not r["duplicate"]
    rows = service.list_proofs("FLAME-001", p)
    assert len(rows) == 1 and rows[0]["verification_status"] == "unverified"
    assert rows[0]["delivery_status"] == "pending"


def test_proof_without_active_mission_is_kept_unlinked(p):
    r = service.record_proof(7, "HASH1", "flow", path=p)
    assert r["mission_id"] is None and not r["linked"]
    assert service.snapshot(path=p)["unlinked_proofs"] == 1
    assert len(service.list_proofs(None, p)) == 1


def test_duplicate_hash_not_counted_twice(p):
    service.activate_mission("FLAME-001", path=p)
    first = service.record_proof(7, "HASH1", "flow", path=p)
    again = service.record_proof(8, "HASH1", "courage", path=p)
    assert again["duplicate"] and again["proof_id"] == first["proof_id"]
    assert service.snapshot(path=p)["proofs"]["counted"] == 1


def test_same_hash_allowed_in_a_different_mission(p):
    service.activate_mission("FLAME-001", path=p)
    service.record_proof(7, "HASH1", "flow", path=p)
    service.close_mission("FLAME-001", path=p)
    service.create_mission("FLAME-002", "Two", "Again", path=p)
    service.activate_mission("FLAME-002", path=p)
    assert not service.record_proof(7, "HASH1", "flow", path=p)["duplicate"]


def test_raw_telegram_id_is_never_stored(p):
    service.activate_mission("FLAME-001", path=p)
    service.record_proof(123456789, "HASH1", "flow", path=p)
    with connect(p) as c:
        dump = " ".join(str(tuple(r)) for t in ("mission_proofs", "mission_events", "flame_meta")
                        for r in c.execute(f"SELECT * FROM {t}"))
    assert "123456789" not in dump


def test_participants_are_distinct_users(p):
    service.activate_mission("FLAME-001", path=p)
    service.record_proof(1, "A", "flow", path=p)
    service.record_proof(1, "B", "flow", path=p)
    service.record_proof(2, "C", "courage", path=p)
    stats = service.snapshot(path=p)["proofs"]
    assert (stats["counted"], stats["participants"]) == (3, 2)
    assert service.user_proof_count(1, "FLAME-001", p) == 2
    assert service.user_proof_count(99, "FLAME-001", p) == 0


def test_input_is_validated_and_truncated(p):
    with pytest.raises(FlameError):
        service.record_proof(1, "   ", "flow", path=p)
    with pytest.raises(FlameError):
        service.record_proof(1, "H", "", path=p)
    service.record_proof(1, "X" * 500, "flow", path=p)
    assert len(service.list_proofs(None, p)[0]["proof_hash"]) == 128


def test_delivery_and_verification_updates(p):
    service.activate_mission("FLAME-001", path=p)
    pid = service.record_proof(1, "A", "flow", path=p)["proof_id"]
    assert service.set_delivery(pid, "failed", "FileNotFoundError: x" * 50, p)
    row = service.list_proofs("FLAME-001", p)[0]
    assert row["delivery_status"] == "failed" and len(row["delivery_error"]) <= 300
    service.verify_proof(pid, "verified", path=p)
    assert service.list_proofs("FLAME-001", p)[0]["verification_status"] == "verified"
    with pytest.raises(FlameError):
        service.set_delivery(pid, "weird", path=p)
    with pytest.raises(FlameError):
        service.verify_proof(pid, "maybe", path=p)
    with pytest.raises(FlameError):
        service.verify_proof(9999, "verified", path=p)
    assert service.set_delivery(9999, "delivered", path=p) is False


def test_rejected_proofs_do_not_count(p):
    service.activate_mission("FLAME-001", path=p)
    pid = service.record_proof(1, "A", "flow", path=p)["proof_id"]
    service.record_proof(2, "B", "flow", path=p)
    service.verify_proof(pid, "rejected", path=p)
    stats = service.snapshot(path=p)["proofs"]
    assert (stats["counted"], stats["rejected"], stats["total"]) == (1, 1, 2)


def test_database_itself_enforces_proof_uniqueness(p):
    """Backstop for races: duplicates are refused by the schema, linked or unlinked."""
    import sqlite3

    sql = ("INSERT INTO mission_proofs (mission_id, user_hash, proof_hash, blessing, created_at) "
           "VALUES (?, 'u', 'H', 'flow', 't')")
    with connect(p) as c:
        c.execute(sql, ("FLAME-001",))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(sql, ("FLAME-001",))
        c.execute(sql, (None,))
        with pytest.raises(sqlite3.IntegrityError):  # NULL mission must not bypass uniqueness
            c.execute(sql, (None,))


def test_concurrent_identical_proofs_count_once(p):
    import threading

    service.activate_mission("FLAME-001", path=p)
    out = []
    threads = [threading.Thread(target=lambda u=u: out.append(service.record_proof(u, "SAME", "flow", path=p)))
               for u in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(not r["duplicate"] for r in out) == 1 and sum(r["duplicate"] for r in out) == 11
    assert service.snapshot(path=p)["proofs"]["counted"] == 1
