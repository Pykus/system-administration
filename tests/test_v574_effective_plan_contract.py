import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
from v578_test_fixture import full_snapshot
INDEX=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
APP=(ROOT/"app.py").read_text(encoding="utf-8")

class TestEffectivePlan574(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,74))

    def test_backend_effective_plan_has_explicit_source_id(self):
        import copy,tempfile
        from pathlib import Path
        state=copy.deepcopy(app.load_state()); state["plan_revision"]=9
        state["last_13_assignments"]=[]; state["school_assignments"]=[]
        r13,school,_=full_snapshot(app,app.load_state())
        old_live=app._current_live_variant_v573; old_path=app.LAST_GOOD_PLAN_PATH
        try:
            app._current_live_variant_v573=lambda:(None,None)
            with tempfile.TemporaryDirectory() as td:
                app.LAST_GOOD_PLAN_PATH=Path(td)/"none.json"
                saved=app._effective_plan_v574(state)
            self.assertEqual(saved["source"]["source_id"],"invalid-saved:9")
            self.assertFalse(saved["source"]["verified"])
            live={"id":"wrk7","seq":7,"live_eligible":True,"result_13":copy.deepcopy(r13),"result_school":copy.deepcopy(school)}
            app._current_live_variant_v573=lambda:(live,{"id":"job3","status":"running"})
            current=app._effective_plan_v574(app.load_state())
        finally:
            app._current_live_variant_v573=old_live; app.LAST_GOOD_PLAN_PATH=old_path
        self.assertEqual(current["source"]["source_id"],"live:job3:wrk7")
        self.assertEqual(current["source"]["kind"],"live_verified")
        self.assertTrue(current["source"]["verified"])

    def test_main_frontend_fetches_effective_plan_on_poll_and_reload(self):
        self.assertIn("fetch('/api/effective-plan?ts='",INDEX)
        poll=INDEX[INDEX.index("async pollRepair(){"):INDEX.index("async waitForFirstFullRepair",INDEX.index("async pollRepair(){"))]
        reload=INDEX[INDEX.index("async reload(){"):INDEX.index("async mounted(){")]
        self.assertIn("await this.refreshEffectivePlan()",poll)
        self.assertIn("this.refreshEffectivePlan()",reload)
        block=INDEX[INDEX.index("livePlanVariant(){"):INDEX.index("visibleSchoolUnresolved(){")]
        self.assertIn("this.effectivePlan",block)
        self.assertNotIn("working_variants",block)
        self.assertIn("sourceId:e.source?.source_id",block)

    def test_no_user_toggle_can_split_plan_source(self):
        self.assertIn('<input type="checkbox" checked disabled>',INDEX)
        self.assertNotIn('v-model="followSolverEverywhere" @change="refreshEpoch++"',INDEX)

    def test_reset_and_cancel_cannot_leave_stale_effective_plan(self):
        reset=INDEX[INDEX.index("resetDiagnosticsForParameterChange(){"):INDEX.index("async prepareParameterSave",INDEX.index("resetDiagnosticsForParameterChange(){"))]
        cancel=INDEX[INDEX.index("async cancelRepair(){"):INDEX.index("teacherPageLabel(",INDEX.index("async cancelRepair(){"))]
        self.assertIn("this.effectivePlan=null",reset)
        self.assertIn("await this.refreshEffectivePlan()",cancel)

    def test_backend_surfaces_mark_saved_vs_effective(self):
        self.assertIn('"plan_state_source":{"kind":"saved"',APP)
        self.assertIn('"effective_plan_source":eff.get("source")',APP)
        self.assertIn('@app.get("/api/effective-plan")',APP)

    def test_teacher_portal_uses_canonical_effective_plan(self):
        self.assertIn("plan=_effective_plan_v574(state)",APP)
        self.assertIn("duties,duty_source,saved_duties=_teacher_effective_duties_v573",APP)

if __name__=="__main__":
    unittest.main(verbosity=2)
