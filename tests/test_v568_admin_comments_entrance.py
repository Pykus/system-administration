import unittest,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
APP=(ROOT/"app.py").read_text(encoding="utf-8")

class TestAdminCommentsEntrance568(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,68))

    def test_locked_assignments_have_persistent_comment_field(self):
        s=copy.deepcopy(app.load_state())
        s["locked_assignments"]=[{"scope":"1-3","abbr":"Pn","slot":"1/2","location":"A","teacher":next(iter(app.ALL))}]
        s=app.ensure_state_schema(s)
        self.assertEqual(s["locked_assignments"][0]["comment"],"")
        s["locked_assignments"][0]["comment"]="powod testowy"
        s=app.ensure_state_schema(s)
        self.assertEqual(s["locked_assignments"][0]["comment"],"powod testowy")

    def test_both_admin_scopes_have_comment_and_edit(self):
        self.assertIn('v-if="adminConstraintModal"',HTML)
        self.assertIn('v-model="adminConstraintModal.comment"',HTML)
        self.assertIn("@click=\"openAdminConstraintCell('1-3'",HTML)
        self.assertIn("@click=\"openAdminConstraintCell('school'",HTML)
        self.assertIn("adminCellState(scope,teacher,abbr,slot)",HTML)
        self.assertIn("comment:String(lock.comment||'')",HTML)

    def test_manual_admin_assignment_can_store_comment(self):
        self.assertIn("comment:String(e.comment||'').trim()",HTML)
        self.assertIn('v-model="manualDutyEdit.comment"',HTML)
        self.assertIn('"source":"manual_cell","comment":comment',APP)

    def test_checkpoint_seed_preserves_opening_entrance_duties(self):
        from unittest.mock import patch
        s=app.load_state()
        entrance="wej\u015bcie"
        days=("Pn","Wt","\u015ar","Czw","Pi")
        rows=[{"abbr":ab,"slot":"0/1","location":entrance,"teacher":next(iter(app.ALL))} for ab in days]
        cp={"plan_revision":int(s.get("plan_revision",0) or 0),
            "working_variants":[{"id":"synthetic","seq":1,"live_eligible":True,"missing":0,
                "coverage13":{"filled":1,"required":1},"coverageSchool":{"filled":5,"required":5},
                "result_13":[{"abbr":"Pn","slot":"1/2","station":"A","teacher":next(iter(app.ALL))}],
                "result_school":rows}]}
        with patch.object(app,"_latest_repair_checkpoint",return_value=cp):
            seed=app._checkpoint_live_seed(s)
        self.assertTrue(seed)
        found={x.get("abbr"):x for x in seed[0]["result_school"]
               if x.get("slot")=="0/1" and x.get("location")==entrance and x.get("teacher")}
        self.assertEqual(set(found),set(days))

    def test_opening_entrance_staffing_is_required_every_day(self):
        s=app.load_state()
        entrance="wej\u015bcie"
        for ab in ("Pn","Wt","\u015ar","Czw","Pi"):
            self.assertEqual(int((s.get("min_people_school") or {}).get(f"{ab}|0/1|{entrance}",0)),1)

    def test_mixed_unicode_mojibake_regression(self):
        broken="Regu\u0142a \u2014 Unikaj dy\u00c5\u00bcuru po ostatniej lekcji \u00e2\u0080\u0093 d\u00c5\u0082uga przerwa"
        good="Regu\u0142a \u2014 Unikaj dy\u017curu po ostatniej lekcji \u2013 d\u0142uga przerwa"
        self.assertEqual(app._repair_mojibake_text_v567(broken),good)

    def test_frontend_source_has_no_encoding_artifacts(self):
        self.assertNotIn("\ufffd",HTML)
        self.assertFalse(any(0x80 <= ord(c) <= 0x9f for c in HTML))
        for bad in ("\u00c2","\u00c3","\u00c4","\u00c5"):
            self.assertNotIn(bad,HTML)

if __name__=="__main__":
    unittest.main(verbosity=2)
