import unittest,sys,ast,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
APP=(ROOT/"app.py").read_text(encoding="utf-8")

class TestStartupLatency566(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,66))
    def test_startup_has_no_redundant_quick_draft_barrier(self):
        self.assertNotIn("jump_specs=[",APP)
        self.assertIn('job["jump_total"]=0',APP)
        self.assertIn('job["jump_checked"]=0',APP)
        self.assertIn('startup_jump_policy"]="disabled_v577_redundant_with_broad_probes"',APP)
        self.assertIn("base=_joint_coverage_v2(base_state,e13,es,optimize=False)",APP)

    def test_after_last_remains_a_later_explicit_phase(self):
        self.assertIn('job["after_last_long_unlocked"]=True',APP)
        self.assertIn('stages_1_4_exhausted',APP)
        self.assertIn('verified_full_plan_exists_before_after_last_long',APP)

    def test_live_contract_still_requires_proven_edge_minimum(self):
        import inspect
        src=inspect.getsource(app._live_eligibility_v565)
        self.assertIn("after_last_long_not_proven_minimum",src)
        self.assertIn("before_first_long_not_proven_minimum",src)


    def test_all_startups_skip_removed_quick_draft_jumps(self):
        self.assertNotIn("jump_specs=[",APP)
        self.assertIn('job["jump_total"]=0',APP)
        self.assertIn('Start: baseline i szerokie testy',APP)


if __name__=="__main__":
    unittest.main(verbosity=2)
