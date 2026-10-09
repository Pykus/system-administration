import copy
import tempfile
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
from validation import validate_state
from v578_test_fixture import full_snapshot

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
APP_SOURCE=(ROOT/"app.py").read_text(encoding="utf-8")

class TestDisplaySourceOfTruth(unittest.TestCase):
    def test_working_variant_is_visible_only_in_diagnostics(self):
        self.assertIn("workingPreview(){if(this.mainTab!=='diagnostics'",HTML)

    def test_normal_school_view_uses_full_live_plan_with_saved_fallback(self):
        line=next(x for x in HTML.splitlines() if x.strip().startswith("schoolPlanDisplay(){"))
        self.assertIn("this.liveDisplaySnapshot",line)
        self.assertIn("this.schoolCurrent",line)
        self.assertNotIn("this.workingPreview",line)

class TestSavedAssignmentIntegrity(unittest.TestCase):
    def base_state(self):
        s=copy.deepcopy(app.load_state())
        s["school_assignments"]=[]
        s["last_13_assignments"]=[]
        return s

    def valid_break(self):
        b=app.SEED["breaks"][0]
        return b["abbr"],b["label"]

    def test_same_teacher_cannot_have_two_school_places_in_one_slot(self):
        s=self.base_state(); ab,sl=self.valid_break()
        locs=s.get("school_locations",[])[:2]
        self.assertGreaterEqual(len(locs),2)
        teacher=next(iter(sorted(app.ALL)))
        s["school_assignments"]=[
            {"abbr":ab,"slot":sl,"location":locs[0],"teacher":teacher},
            {"abbr":ab,"slot":sl,"location":locs[1],"teacher":teacher},
        ]
        codes={p["code"] for p in validate_state(s,app.SEED)["problems"]}
        self.assertIn("assignment_double_booked",codes)

    def test_same_school_position_cannot_be_saved_twice(self):
        s=self.base_state(); ab,sl=self.valid_break()
        loc=s.get("school_locations",[])[0]
        teachers=list(sorted(app.ALL))[:2]
        s["school_assignments"]=[
            {"abbr":ab,"slot":sl,"location":loc,"teacher":teachers[0]},
            {"abbr":ab,"slot":sl,"location":loc,"teacher":teachers[1]},
        ]
        codes={p["code"] for p in validate_state(s,app.SEED)["problems"]}
        self.assertIn("duplicate_school_position",codes)

    def test_cross_scope_double_booking_is_rejected(self):
        s=self.base_state(); ab,sl=self.valid_break()
        teacher=next(iter(sorted(app.ALL)))
        loc=s.get("school_locations",[])[0]
        station=(s.get("station_order_13") or ["A"])[0]
        s["school_assignments"]=[{"abbr":ab,"slot":sl,"location":loc,"teacher":teacher}]
        s["last_13_assignments"]=[{"abbr":ab,"label":sl,"assignments":[{"station":station,"teacher":teacher}]}]
        codes={p["code"] for p in validate_state(s,app.SEED)["problems"]}
        self.assertIn("assignment_double_booked",codes)

class TestTeacherPortalUsesEffectivePlan(unittest.TestCase):
    def test_portal_reads_same_effective_plan_as_backend(self):
        r13,school,_=full_snapshot(app,app.load_state())
        names={x.get("teacher") for x in r13+school if x.get("teacher")}
        name=next(n for n,r in app.TEACHER_REGISTRY.items() if r.get("active",True) and r.get("portal_token") and n in names)
        token=app.TEACHER_REGISTRY[name]["portal_token"]
        live={"id":"wrk","seq":3,"live_eligible":True,"result_13":copy.deepcopy(r13),"result_school":copy.deepcopy(school)}
        orig_live=app._current_live_variant_v573
        try:
            app._current_live_variant_v573=lambda:(live,{"id":"job","status":"running"})
            eff=app._effective_plan_v574(app.load_state())
            out=app.teacher_portal(token)
        finally:
            app._current_live_variant_v573=orig_live
        self.assertEqual(eff["source"]["kind"],"live_verified")
        self.assertEqual(out["duty_source"]["source_id"],eff["source"]["source_id"])
        expected=[]
        for x in eff["result_13"]:
            if x.get("teacher")==name: expected.append(("1-3",x.get("abbr"),x.get("slot"),x.get("station")))
        for x in eff["result_school"]:
            if x.get("teacher")==name: expected.append(("school",x.get("abbr"),x.get("slot"),x.get("location")))
        got=[(d["scope"],d["abbr"],d["slot"],d["place"]) for d in out["duties"]]
        self.assertEqual(sorted(got),sorted(expected))



class TestPdfExportContract(unittest.TestCase):
    def test_school_pdf_is_not_split_into_slot_chunks(self):
        self.assertNotIn("chunks=[slots[i:i+5]",APP_SOURCE)
        self.assertIn("One compact A4 landscape page per day",APP_SOURCE)

    def test_pdf_cells_are_left_aligned_and_compact(self):
        self.assertIn('("ALIGN",(0,1),(-1,-1),"LEFT")',APP_SOURCE)
        self.assertIn("first=72; widths=[first]+[(usable-first)/n]*n",APP_SOURCE)
        self.assertIn("station_w=min(155",APP_SOURCE)

if __name__=="__main__":
    unittest.main()
