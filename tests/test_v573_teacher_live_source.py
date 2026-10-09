import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
from v578_test_fixture import full_snapshot
HTML=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")
APP=(ROOT/"app.py").read_text(encoding="utf-8")

class TestTeacherLiveSource573(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,73))

    def test_effective_duties_prefers_live_variant(self):
        import copy
        r13,school,_=full_snapshot(app,app.load_state())
        names={x.get("teacher") for x in r13+school if x.get("teacher")}
        name=next(iter(names))
        live={"id":"wrk1","seq":7,"live_eligible":True,"result_13":copy.deepcopy(r13),"result_school":copy.deepcopy(school)}
        old=app._current_live_variant_v573
        try:
            app._current_live_variant_v573=lambda:(live,{"id":"job1","status":"running"})
            duties,src,saved=app._teacher_effective_duties_v573(name,app.load_state())
        finally:
            app._current_live_variant_v573=old
        self.assertEqual(src["kind"],"live_verified")
        self.assertTrue(src["unsaved"])
        self.assertEqual(src["seq"],7)
        self.assertTrue(duties)

    def test_incomplete_saved_state_is_explicitly_invalid(self):
        name=next(iter(app.ALL))
        st={"last_13_assignments":[],"school_assignments":[{"day":"X","abbr":"Pn","slot":"1/2","location":"saved","teacher":name}]}
        old_live=app._current_live_variant_v573
        old_path=app.LAST_GOOD_PLAN_PATH
        import tempfile
        from pathlib import Path
        try:
            app._current_live_variant_v573=lambda:(None,None)
            with tempfile.TemporaryDirectory() as td:
                app.LAST_GOOD_PLAN_PATH=Path(td)/"missing.json"
                duties,src,saved=app._teacher_effective_duties_v573(name,st)
        finally:
            app._current_live_variant_v573=old_live
            app.LAST_GOOD_PLAN_PATH=old_path
        self.assertEqual(duties,saved)
        self.assertEqual(src["kind"],"invalid_saved")
        self.assertFalse(src["verified"])

    def test_portal_returns_source_and_saved_duties(self):
        self.assertIn('"saved_duties":saved_duties,"duty_source":duty_source',APP)

    def test_recalc_uses_effective_duties(self):
        self.assertIn("effective_duties,duty_source,_saved=_teacher_effective_duties_v573(name,st)",APP)
        self.assertIn('"duty_source":duty_source',APP)

    def test_teacher_ui_has_source_banner_and_polling(self):
        self.assertIn('id="dutySource"',HTML)
        self.assertIn("function dutySignature",HTML)
        self.assertIn("async function refreshDuties",HTML)
        self.assertIn("setTimeout(refreshDuties,5000)",HTML)
        self.assertIn("Widok roboczy, jeszcze niezapisany.",HTML)

if __name__=="__main__":
    unittest.main(verbosity=2)
