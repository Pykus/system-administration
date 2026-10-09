import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
APP=(ROOT/"app.py").read_text(encoding="utf-8")
SOLVER=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")
class TestBreakPriority563(unittest.TestCase):
    def test_version_and_thresholds(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,63))
        self.assertEqual(app.SHORT_BREAK_MAX_MINUTES,10)
        self.assertEqual(app.LONG_BREAK_MINUTES,11)
    def test_edge_semantics_are_5_to_10_short_over_10_long(self):
        self.assertIn('edge_short=int(br.get("minutes",0) or 0)<=SHORT_BREAK_MAX_MINUTES',APP)
        self.assertIn('edge_is_short=minutes<=SHORT_BREAK_MAX_MINUTES',SOLVER)
        self.assertIn("przerwa &gt;10 min",HTML)
        self.assertNotIn("takĹĽe 10-minutowÄ…",HTML)
    def test_long_edge_quality_precedes_fairness(self):
        self.assertIn('return (wait,after,wf_total,before,consec,foreign13,foreign_school,fair_dev,fair_ratio,relax)',APP)
    def test_long_edge_teacher_relaxations_are_not_stage2(self):
        self.assertIn('stage=6 if key=="avoid_wait" else (5 if key=="after_last_long" else (3 if key=="before_first_long" else 2))',APP)
    def test_startup_skips_redundant_quick_drafts(self):
        self.assertIn('startup_jump_policy"]="disabled_v577_redundant_with_broad_probes"',APP)
        self.assertNotIn("jump_specs=[",APP)
        self.assertIn('hardened.add("avoid_wait")',APP)
        self.assertIn('stage=6 if key=="avoid_wait" else (5 if key=="after_last_long"',APP)

    def test_late_edge_fallback_compares_both_orders_by_human_quality(self):
        self.assertIn('def attempt_quality(z):',APP)
        self.assertIn('run_attempt("matrix model - 13 first",q13,qschool,"13-first")',APP)
        self.assertIn('run_attempt("matrix model - school first",q13,qschool,"school-first")',APP)
        self.assertIn('int(m.get("wait_lessons_total",10**6) or 0)',APP)
        self.assertIn('int(m.get("after_last_long",10**6) or 0)',APP)
        self.assertIn('int(m.get("before_first_long",10**6) or 0)',APP)

    def test_live_preview_rejects_nonminimal_long_edge_exceptions(self):
        self.assertIn('after_last_long_phase_not_unlocked',APP)
        self.assertIn('after_last_long_not_proven_minimum',APP)
        self.assertIn('before_first_long_not_proven_minimum',APP)
        self.assertIn('after_last_long_lex_proven',APP)
        self.assertIn('v.live_eligible===true',HTML)
    def test_every_new_working_variant_changes_refresh_signature(self):
        self.assertIn("let all=a.map(w=>[w.id,w.seq,w.found_at",HTML)
if __name__=="__main__":
    unittest.main(verbosity=2)

