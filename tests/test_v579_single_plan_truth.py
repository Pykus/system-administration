import copy, tempfile, unittest, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

INDEX=(ROOT/"static"/"index.html").read_text(encoding="utf-8")

class TestSinglePlanTruth579(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,79))

    def test_unverified_effective_plan_exposes_no_plan_rows(self):
        st=copy.deepcopy(app.load_state())
        st["last_13_assignments"]=[]
        st["school_assignments"]=[]
        old_live,old_path=app._current_live_variant_v573,app.LAST_GOOD_PLAN_PATH
        try:
            app._current_live_variant_v573=lambda:(None,{"id":"x","status":"error"})
            with tempfile.TemporaryDirectory() as td:
                app.LAST_GOOD_PLAN_PATH=Path(td)/"missing.json"
                e=app._effective_plan_v574(st)
        finally:
            app._current_live_variant_v573,app.LAST_GOOD_PLAN_PATH=old_live,old_path
        self.assertFalse(e["source"]["verified"])
        self.assertEqual(e["result_13"],[])
        self.assertEqual(e["result_school"],[])

    def test_frontend_waiting_is_only_backend_verified_contract(self):
        line=next(x for x in INDEX.splitlines() if x.strip().startswith("planAwaitingFreshPlan(){"))
        self.assertIn("!this.effectivePlan?.source?.verified",line)
        self.assertNotIn("recalculating",line)
        self.assertNotIn("repairJob",line)

    def test_success_message_requires_verified_plan(self):
        self.assertIn("else if(this.effectivePlan?.source?.verified)this.calcMessage='Przeliczono zweryfikowany pełny plan.",INDEX)

if __name__=="__main__":
    unittest.main(verbosity=2)
