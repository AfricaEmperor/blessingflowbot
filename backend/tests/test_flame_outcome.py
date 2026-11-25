import pytest

from flame import outcome as rules
from flame import service
from flame.errors import FlameError
from flame.store import connect


@pytest.fixture
def p(tmp_path):
    path = str(tmp_path / "flame.db")
    service.init(path)
    return path


def run_mission(p, proofs, target=4, verify=0, fail=0):
    service.create_mission("FLAME-001", "Ignition", "Light it", "ten people respond", target, "Admin", path=p)
    service.activate_mission("FLAME-001", path=p)
    ids = []
    for i, (user, blessing) in enumerate(proofs):
        ids.append(service.record_proof(user, f"H{i}", blessing, path=p)["proof_id"])
    for i, pid in enumerate(ids):
        service.set_delivery(pid, "failed" if i < fail else "delivered", "boom" if i < fail else None, p)
    for pid in ids[:verify]:
        service.verify_proof(pid, "verified", path=p)
    service.close_mission("FLAME-001", path=p)


def test_requires_a_closed_mission(p):
    service.create_mission("FLAME-001", "t", "g", path=p)
    with pytest.raises(FlameError, match="draft"):
        service.generate_outcome("FLAME-001", path=p)
    service.activate_mission("FLAME-001", path=p)
    with pytest.raises(FlameError, match="active"):
        service.generate_outcome("FLAME-001", path=p)
    with pytest.raises(FlameError, match="does not exist"):
        service.generate_outcome("FLAME-404", path=p)


def test_met_outcome_and_next_draft(p):
    run_mission(p, [(1, "flow"), (2, "flow"), (3, "courage"), (4, "clarity")], target=4, verify=4)
    out = service.generate_outcome("FLAME-001", path=p)
    assert out["result"] == "met"
    assert out["decision"].startswith("Repeat.")
    assert "unverified" not in out["decision"]
    assert out["evidence"]["proofs_counted"] == 4 and out["evidence"]["participants"] == 4
    assert out["evidence"]["by_blessing"] == {"clarity": 1, "courage": 1, "flow": 2}
    assert any("'flow' (2 of 4)" in line for line in out["learning"])
    nxt = service.get_mission(out["next_mission_id"], p)
    assert nxt["id"] == "FLAME-002" and nxt["status"] == "draft" and nxt["parent_mission_id"] == "FLAME-001"
    assert nxt["target_proofs"] == 5  # 4 * 1.25
    assert service.active_mission(p) is None  # a human must activate it


def test_partial_and_not_met(p):
    run_mission(p, [(1, "flow"), (2, "flow")], target=4)
    assert service.generate_outcome("FLAME-001", path=p)["result"] == "partially met"
    assert rules.judge(10, 4) == "not met" and rules.judge(10, 5) == "partially met"


def test_unverified_evidence_is_called_out(p):
    run_mission(p, [(1, "flow"), (2, "flow"), (3, "flow"), (4, "flow")], target=4)
    out = service.generate_outcome("FLAME-001", path=p)
    assert out["result"] == "met"
    assert "self-reported: 4 of 4 proofs are unverified" in out["decision"]
    assert any("None of the 4 proofs were verified" in line for line in out["learning"])


def test_delivery_failures_and_repeat_senders_surface(p):
    run_mission(p, [(1, "flow"), (1, "flow"), (2, "courage")], target=3, fail=2)
    out = service.generate_outcome("FLAME-001", path=p)
    text = " ".join(out["learning"])
    assert "2 blessing deliveries failed" in text
    assert "2 participants, 3 proofs" in text
    assert out["evidence"]["deliveries"] == {"delivered": 1, "failed": 2, "pending": 0}


def test_zero_proofs_holds(p):
    run_mission(p, [], target=4)
    out = service.generate_outcome("FLAME-001", path=p)
    assert out["result"] == "not met" and out["decision"].startswith("Hold.")
    assert out["evidence"]["first_proof_at"] is None
    assert service.get_mission("FLAME-002", p)["target_proofs"] == 4


def test_no_target_is_inconclusive(p):
    service.create_mission("FLAME-001", "t", "g", path=p)
    service.activate_mission("FLAME-001", path=p)
    service.record_proof(1, "A", "flow", path=p)
    service.close_mission("FLAME-001", path=p)
    out = service.generate_outcome("FLAME-001", path=p)
    assert out["result"] == "inconclusive" and out["decision"].startswith("Adjust.")
    assert service.get_mission("FLAME-002", p)["target_proofs"] == 1


def test_idempotent_no_second_draft(p):
    run_mission(p, [(1, "flow")], target=1)
    a = service.generate_outcome("FLAME-001", path=p)
    b = service.generate_outcome("FLAME-001", path=p)
    assert a == b
    assert [m["id"] for m in service.list_missions(p)] == ["FLAME-001", "FLAME-002"]
    assert service.get_outcome("FLAME-001", p) == a


def test_next_id_increments_past_existing_missions(p):
    service.create_mission("FLAME-007", "seven", "g", target_proofs=1, path=p)
    service.activate_mission("FLAME-007", path=p)
    service.close_mission("FLAME-007", path=p)
    assert service.generate_outcome("FLAME-007", path=p)["next_mission_id"] == "FLAME-008"


def test_rejected_proofs_excluded_from_evidence(p):
    run_mission(p, [(1, "flow"), (2, "flow")], target=2)
    first = service.list_proofs("FLAME-001", p)[0]["id"]
    # closed missions can still have a proof re-checked by a human before the outcome
    service.verify_proof(first, "rejected", path=p)
    out = service.generate_outcome("FLAME-001", path=p)
    assert out["evidence"]["proofs_counted"] == 1 and out["evidence"]["rejected"] == 1
    assert out["result"] == "partially met"


def test_conversation_volume_counts_only_the_window(p):
    with connect(p) as c:
        c.execute("CREATE TABLE conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
                  "role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    service.create_mission("FLAME-001", "t", "g", target_proofs=1, path=p)
    service.activate_mission("FLAME-001", path=p)
    with connect(p) as c:  # rows stamped "now", i.e. inside the window
        c.execute("INSERT INTO conversations (user_id, role, content) VALUES (1,'user','a')")
        c.execute("INSERT INTO conversations (user_id, role, content) VALUES (1,'assistant','b')")
        c.execute("INSERT INTO conversations (user_id, role, content, created_at) VALUES (1,'user','old','2000-01-01 00:00:00')")
    service.close_mission("FLAME-001", path=p)
    out = service.generate_outcome("FLAME-001", path=p)
    assert out["evidence"]["conversation_messages"] == 1
    assert "content" not in str(out["evidence"])  # aggregate only, never message text


def test_outcome_has_no_personal_data(p):
    run_mission(p, [(123456789, "flow")], target=1)
    out = service.generate_outcome("FLAME-001", path=p)
    assert "123456789" not in str(out)


def test_pure_rules_edge_cases():
    assert rules.judge(None, 99) == "inconclusive"
    assert rules.next_target("met", 10, 12) == 13
    assert rules.next_target("not met", 10, 2) == 10
    tied = rules.learn({"counted": 2, "by_blessing": {"flow": 1, "courage": 1}, "failed": 0, "pending": 0,
                        "verified": 2, "unverified": 0, "participants": 2}, None, 0)
    assert any("tied" in line and "courage, flow" in line for line in tied)


def test_singular_and_plural_wording():
    one = {"counted": 1, "by_blessing": {"flow": 1}, "failed": 1, "pending": 1, "verified": 1,
           "unverified": 0, "participants": 1}
    text = " ".join(rules.learn(one, 1, 1))
    assert "1 blessing delivery failed" in text and "1 delivery never completed" in text
    assert "1 duplicate submission was ignored" in text and "1 message was exchanged" in text
    many = dict(one, failed=2, pending=2)
    text = " ".join(rules.learn(many, 3, 2))
    assert "2 blessing deliveries failed" in text and "2 deliveries never completed" in text
    assert "2 duplicate submissions were ignored" in text and "3 messages were exchanged" in text
