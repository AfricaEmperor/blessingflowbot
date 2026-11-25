import os
import tempfile
import unittest

from db import memory
import mission_store


class MissionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.NamedTemporaryFile(delete=False)
        self.temp.close()
        self.old_path=memory.DB_PATH
        memory.DB_PATH=self.temp.name
        mission_store.DB_PATH=self.temp.name
        memory.init_db()

    def tearDown(self):
        memory.DB_PATH=self.old_path
        mission_store.DB_PATH=self.old_path
        os.unlink(self.temp.name)

    def test_create_and_active_mission(self):
        mission=mission_store.create_mission("Flame Ignition", "Launch first drop")
        self.assertEqual(mission["mission_id"],"FLAME-001")
        self.assertEqual(mission_store.active_mission()["mission_id"],"FLAME-001")

    def test_prevents_two_active_missions(self):
        mission_store.create_mission("One")
        with self.assertRaises(ValueError):
            mission_store.create_mission("Two")

    def test_proof_links_to_active_mission_and_is_unverified(self):
        mission=mission_store.create_mission("Proof test")
        proof=mission_store.record_proof(123,"0xabc","flow")
        self.assertEqual(proof["mission_id"],mission["mission_id"])
        self.assertEqual(proof["verification_status"],"unverified")
        self.assertEqual(len(mission_store.mission_proofs(mission["mission_id"])),1)

    def test_outcome_and_next_mission_proposal(self):
        mission=mission_store.create_mission("Cycle")
        mission_store.record_proof(1,"hash1","flow")
        outcome=mission_store.generate_outcome(mission["mission_id"])
        self.assertEqual(outcome["proof_count"],1)
        proposal=mission_store.generate_next_mission(mission["mission_id"])
        self.assertEqual(proposal["parent_mission_id"],mission["mission_id"])
        self.assertTrue(proposal["requires_human_approval"])


if __name__=="__main__":
    unittest.main()
