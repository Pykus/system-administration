import unittest,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
APP=(ROOT/"app.py").read_text(encoding="utf-8")
SOLVER=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")

class TestWfLateFallback577(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,77))

    def test_primary_pool_filters_wf_but_keeps_admin_lock(self):
        import inspect
        run=inspect.getsource(app._run_repair_job)
        self.assertNotIn('_primary_pool_without_wf_v577(',run)
        self.assertIn('e13=[n for n in ALL if n not in inactive]',run)
        self.assertIn('es=list(e13)',run)

    def test_wf_candidates_are_stage4(self):
        fake={"obvious_candidates":[{"token":"addschool:Demo","label":"legacy","human_cost":1},{"token":"add13group:wf","label":"legacy2","human_cost":1}]}
        out=app._repair_candidates_v2(app.load_state(),list(app.ALL),list(app.ALL),{},fake)
        self.assertFalse(any(str(x.get("token","")).startswith(("addschool:","add13:","add13group:","move13:","moveschool:")) for x in out))

    def test_order_is_wf_then_after_last_then_wait(self):
        self.assertIn("lexicographic_fallback_outside_wf_only_places",APP)
        self.assertIn('stage=6 if key=="avoid_wait" else (5 if key=="after_last_long"',APP)
        self.assertIn("native_cp_sat_matrix",APP)
        self.assertIn('if group.get(n)=="wf" and not required and exclusive_group!="wf":',SOLVER)

    def test_live_gate_requires_phase_and_proven_minimum(self):
        q={'full':True,'missing':0,'human_guardrail_ok':True,'after_last_long':0,'before_first_long':0,'wf_assignments_total':1,'wf_fallback_lex_proven':False}
        e=app._live_eligibility_v565(q,{'wf_locked_baseline':0})
        self.assertFalse(e['ok']);self.assertIn('wf_fallback_not_proven_minimum',e['reasons'])
        q['wf_fallback_lex_proven']=True
        e=app._live_eligibility_v565(q,{'wf_locked_baseline':0})
        self.assertTrue(e['ok'],e)

    def test_quality_prefers_wf_over_after_last_but_non_wf_over_wf(self):
        base={"wait_lessons_total":0,"after_last_long":0,"wf_assignments_total":0,
              "before_first_long":0,"consecutive_pairs":0,"home_group_foreign_13":20,
              "home_group_foreign_school":20,"fairness_enabled":True,
              "fairness_normalized_deviation":9.0,"fairness_max_ratio":9.0,
              "temporary_relaxations_count":0}
        wf=dict(base,wf_assignments_total=1,home_group_foreign_13=0,home_group_foreign_school=0,
                fairness_normalized_deviation=0.0,fairness_max_ratio=0.0)
        edge=dict(base,after_last_long=1,wf_assignments_total=0)
        self.assertLess(app._working_quality_key_v559(base,{}),app._working_quality_key_v559(wf,{}))
        self.assertLess(app._working_quality_key_v559(wf,{}),app._working_quality_key_v559(edge,{}))

    def test_cp_sat_school_prefers_general_over_wf(self):
        s=copy.deepcopy(app.load_state())
        row=app._global_row(s,"prefer_home_group");row.update({"enabled":True,"kind":"soft","priority":5})
        pool=[n for n in app.ALL if n not in set(s.get("excluded_teachers",[]))]
        found=None
        for pos in app._school_positions(s)[0]:
            legal=app._preflight_teacher_allowed_v524(s,"szko\u0142a",pos,pool)
            general=[n for n in legal if app.GROUP.get(n)=="school"]
            wf=[n for n in legal if app.GROUP.get(n)=="wf"]
            if general and wf:
                found=(pos,general[0],wf[0]);break
        self.assertIsNotNone(found,"no school slot with both general and WF candidate")
        pos,general,wf=found
        for r in s["global_constraints"]:
            if r.get("kind")=="soft" and r.get("key")!="prefer_home_group": r["enabled"]=False
        s["solver_working_optimize"]=False
        a,_,missing,meta=app.solve_positions(s,"szko\u0142a",[pos],{general,wf},[],None,coverage_only=True)
        self.assertFalse(missing);self.assertEqual(a[0]["teacher"],general)
        self.assertEqual(meta["diagnostics"]["minimum_wf_fallback_assignments"],0)
        a,_,missing,meta=app.solve_positions(s,"szko\u0142a",[pos],{wf},[],None,coverage_only=True)
        self.assertFalse(missing);self.assertEqual(a[0]["teacher"],wf)
        self.assertEqual(meta["diagnostics"]["minimum_wf_fallback_assignments"],1)

    def test_solver_minimizes_wf_in_every_scope(self):
        self.assertIn('wf_fallback_vars=[]',SOLVER)
        self.assertIn('if group.get(n)=="wf" and not required and exclusive_group!="wf":',SOLVER)
        self.assertIn('"minimum_wf_fallback_assignments":best_wf_fallback',SOLVER)
        self.assertIn('"wf_fallback_scope":scope',SOLVER)

    def test_documentation_records_global_wf_policy(self):
        docs=[
            ROOT/"README.md",
            ROOT/"RELEASE-NOTES-v5.77.md",
            ROOT/"docs"/"ARCHITECTURE.md",
            ROOT/"docs"/"CONSTRAINT-ARCHITECTURE.md",
            ROOT/"docs"/"USER_GUIDE.md",
            ROOT/"docs"/"CHANGELOG.md",
        ]
        for path in docs:
            text=path.read_text(encoding="utf-8")
            self.assertIn("WF",text,path.name)
        release=(ROOT/"RELEASE-NOTES-v5.77.md").read_text(encoding="utf-8")
        self.assertIn("4. WF emergency fallback.",release)
        self.assertIn("5. after_last_long",release)
        self.assertIn("6. avoid_wait",release)
        arch=(ROOT/"docs"/"ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertIn("WF",arch)
        self.assertIn("effective-plan",arch)

if __name__=="__main__":
    unittest.main(verbosity=2)
