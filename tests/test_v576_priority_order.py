import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
APP=(ROOT/"app.py").read_text(encoding="utf-8")

class TestPriorityOrder576(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,76))
    def test_startup_has_no_redundant_quick_draft_jumps(self):
        self.assertNotIn("jump_specs=[",APP)
        self.assertIn('startup_jump_policy"]="disabled_v577_redundant_with_broad_probes"',APP)
        self.assertIn('Start: baseline i szerokie testy',APP)

    def test_priority_stages(self):
        self.assertIn('stage=6 if key=="avoid_wait" else (5 if key=="after_last_long" else (3 if key=="before_first_long" else 2))',APP)
        self.assertIn('stage=6 if key=="avoid_wait" else (5 if key=="after_last_long" else 3)',APP)
    def test_after_last_requires_phase_unlock(self):
        q={"full":True,"missing":0,"human_guardrail_ok":True,"fairness_grossly_unbalanced":False,"after_last_long":1,"after_last_long_lex_proven":True,"before_first_long":0}
        self.assertFalse(app._live_eligibility_v565(q,{"after_last_long_unlocked":False})["ok"])
        self.assertTrue(app._live_eligibility_v565(q,{"after_last_long_unlocked":True})["ok"])
    def test_fairness_does_not_block_comfortable_live_plan(self):
        q={"full":True,"missing":0,"human_guardrail_ok":True,"fairness_grossly_unbalanced":True,"after_last_long":0,"before_first_long":0}
        self.assertTrue(app._live_eligibility_v565(q,{})["ok"])
    def test_zero_after_last_beats_prettier_fairness(self):
        a={"wait_lessons_total":0,"after_last_long":0,"before_first_long":0,"consecutive_pairs":0,"home_group_foreign_13":99,"home_group_foreign_13_wf":99,"home_group_foreign_school":99,"fairness_enabled":True,"fairness_normalized_deviation":9.0,"fairness_max_ratio":9.0,"temporary_relaxations_count":0}
        b=dict(a,after_last_long=1,home_group_foreign_13=0,home_group_foreign_13_wf=0,home_group_foreign_school=0,fairness_normalized_deviation=0.0,fairness_max_ratio=0.0)
        self.assertLess(app._working_quality_key_v559(a,{}),app._working_quality_key_v559(b,{}))
