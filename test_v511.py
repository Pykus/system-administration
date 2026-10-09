import unittest
from pathlib import Path
import app, repair_farm

ROOT=Path(__file__).parent

class TestV511(unittest.TestCase):
    def test_version(self):
        self.assertEqual(app.app.version,"5.11")
        self.assertEqual(app.health()["version"],"5.11")

    def test_wait_is_absolute_last_candidate_stage(self):
        st=app.load_state()
        base=app._joint_coverage_v2(st,st.get("enabled_teachers_13",[]),st.get("enabled_teachers_school",[]),False)
        cs=app._repair_candidates_v2(st,st.get("enabled_teachers_13",[]),st.get("enabled_teachers_school",[]),base)
        waits=[c for c in cs if c.get("token")=="gsoft:avoid_wait"]
        if waits:
            self.assertEqual(waits[0]["search_stage"],3)
            self.assertTrue(waits[0]["wait_relax"])
            self.assertEqual(cs[-1]["search_stage"],3)

    def test_farm_defaults(self):
        cfg=app._farm_config()
        self.assertEqual(cfg["port"],8093)
        self.assertGreaterEqual(cfg["local_workers"],1)
        self.assertLessEqual(cfg["local_workers"],8)

    def test_worker_status_contract(self):
        st=repair_farm.status()
        self.assertIn("workers",st)
        self.assertIn("tasks",st)

    def test_ui_contract(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for phrase in ("Dyżury v5.11","Umożliw pracę zdalnym workerom","Lokalne zadania równoległe",
                       "Przejrzyj wariant / zwiń szczegóły","OSTATNIA MOŻLIWOŚĆ: oczekiwanie",
                       "Kolejność wyszukiwania"):
            self.assertIn(phrase,h)
        self.assertNotIn('id="repairReview"',h)
        self.assertIn(".card:empty{display:none}",h)

    def test_worker_sources_exist(self):
        for name in ("repair_farm.py","worker_broker.py","worker_main.py"):
            self.assertTrue((ROOT/name).exists(),name)

if __name__=="__main__":
    unittest.main(verbosity=2)
