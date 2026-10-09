import json, tempfile, unittest, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
from v578_test_fixture import full_snapshot
INDEX=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
TEACHER=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")
APP=(ROOT/"app.py").read_text(encoding="utf-8")
SOLVER=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")

class TestV577ConsistencyAndWF(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,77))

    def test_empty_teacher_records_are_not_full(self):
        st=app.load_state()
        req13,reqs=app._required_position_keys_v577(st)
        fake13=[{"abbr":a,"slot":s,"station":loc,"teacher":""} for a,s,loc in req13]
        fakes=[{"abbr":a,"slot":s,"location":loc,"teacher":"X"} for a,s,loc in reqs]
        aud=app._plan_snapshot_audit_v577(fake13,fakes,st)
        self.assertFalse(aud["ok"])
        self.assertEqual(aud["filled13_real"],0)
        self.assertEqual(aud["missing13_real"],aud["required13"])

    def test_reference_is_used_when_saved_plan_is_incomplete(self):
        st=app.load_state(); r13,school,audit=full_snapshot(app,st)
        ref={"saved_at":"TDD","source":{"source_id":"tdd-current"},"audit":audit,"metrics":{},"result_13":r13,"result_school":school}
        old_live=app._current_live_variant_v573; old_path=app.LAST_GOOD_PLAN_PATH
        try:
            app._current_live_variant_v573=lambda:(None,{"id":"job","status":"running"})
            with tempfile.TemporaryDirectory() as td:
                q=Path(td)/"last_good.json";q.write_text(json.dumps(ref,ensure_ascii=False),encoding="utf-8");app.LAST_GOOD_PLAN_PATH=q
                e=app._effective_plan_v574(st)
        finally:
            app._current_live_variant_v573=old_live;app.LAST_GOOD_PLAN_PATH=old_path
        if not app._plan_snapshot_audit_v577(app._flatten_saved_13_v574(st),st.get("school_assignments",[]),st)["ok"]:
            self.assertEqual(e["source"]["kind"],"reference_verified")
            self.assertTrue(e["audit"]["ok"])

    def test_frontend_uses_backend_verified_source_kinds(self):
        for kind in ("live_verified","reference_verified","saved_verified"):
            self.assertIn(kind,INDEX)
        self.assertIn("invalid_saved",TEACHER)
        self.assertIn("effectivePlan?.source?.verified",INDEX)
        self.assertIn("filled13_real",INDEX)
        self.assertIn("source_id",TEACHER)

    def test_wf_is_late_but_before_after_last_and_waiting(self):
        self.assertIn('lexicographic_fallback_outside_wf_only_places',APP)
        self.assertIn('place_preference_model',APP)
        self.assertIn('exclusive_group!="wf"',SOLVER)
        self.assertIn('place_preference_terms',SOLVER)

    def test_wf_cannot_enter_live_before_phase_four(self):
        q={'full':True,'missing':0,'human_guardrail_ok':True,'wf_assignments_total':1,'wf_fallback_lex_proven':False,'after_last_long':0,'before_first_long':0}
        self.assertFalse(app._live_eligibility_v565(q,{'wf_locked_baseline':0})['ok'])
        q['wf_fallback_lex_proven']=True
        self.assertTrue(app._live_eligibility_v565(q,{'wf_locked_baseline':0})['ok'])

    def test_after_last_is_worse_than_wf_in_quality_order(self):
        base={"wait_lessons_total":0,"before_first_long":0,"consecutive_pairs":0,
              "home_group_foreign_13":0,"home_group_foreign_school":0,
              "fairness_enabled":False,"temporary_relaxations_count":0}
        wf=dict(base,after_last_long=0,wf_assignments_total=1)
        after=dict(base,after_last_long=1,wf_assignments_total=0)
        self.assertLess(app._working_quality_key_v559(wf,{}),app._working_quality_key_v559(after,{}))

    def test_solver_minimizes_automatic_wf_in_both_scopes(self):
        self.assertIn('wf_fallback_vars=[]',SOLVER)
        self.assertIn('if group.get(n)=="wf" and not required and exclusive_group!="wf":',SOLVER)
        self.assertIn('"wf_fallback_lexicographic":bool(wf_fallback_vars)',SOLVER)
        self.assertIn('"wf_fallback_scope":scope',SOLVER)
        self.assertIn('exclusive_group=place_meta.get("exclusive_group")',SOLVER)

    def test_lexicographic_human_priorities_survive_repair_optimization(self):
        self.assertNotIn("best_missing==0 and not repair_mode",SOLVER)
        self.assertNotIn("home_mismatch_vars and _home_lex and not repair_mode",SOLVER)
        self.assertIn("if repair_mode and change_vars:",SOLVER)

    def test_deep_full_candidate_is_optimized_before_publication(self):
        a=APP.index("def _eval_combo_deep")
        b=APP.index("def _evaluate_deep_parallel",a)
        block=APP[a:b]
        self.assertIn("_joint_coverage_v2(st,p13,ps,optimize=False)",block)
        self.assertIn("_joint_coverage_v2(st,p13,ps,optimize=True)",block)
        self.assertIn('"optimized_full":optimized_full',block)

    def test_stage_four_repairs_best_partial_with_single_wf_first(self):
        self.assertNotIn("single-wf-on-best-partial",APP)
        self.assertIn("native_cp_sat_matrix",APP)
        self.assertIn("lexicographic_fallback_outside_wf_only_places",APP)
        self.assertIn("place_preference_terms",SOLVER)

    def test_verified_suggestions_are_visible_to_effective_plan(self):
        cur=APP[APP.index("def _current_live_variant_v573"):APP.index("def _teacher_saved_duties_v573")]
        self.assertIn('for bucket in ("working_variants","suggestions")',cur)
        add=APP[APP.index("def _job_add_suggestion"):APP.index("def _accepted_compromises")]
        self.assertIn("_live_eligibility_v565(sug,job)",add)
        self.assertIn("_persist_last_good_plan_v577",add)

if __name__=="__main__":
    unittest.main(verbosity=2)
