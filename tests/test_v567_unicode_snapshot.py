import unittest,sys,json,inspect
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")

class TestUnicodeSnapshot567(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,67))

    def test_known_mojibake_is_repaired(self):
        cases=[
            ("wej\u00c5\u009bcie","wej\u015bcie"),
            ("sto\u00c5\u0082\u00c3\u00b3wka","sto\u0142\u00f3wka"),
            ("Poniedzia\u00c5\u0082ek","Poniedzia\u0142ek"),
            ("Ma\u00c5\u0082gorzata","Ma\u0142gorzata"),
            ("Wywi\u00c3\u00b3rska","Wywi\u00f3rska"),
        ]
        for broken,good in cases:
            self.assertEqual(app._repair_mojibake_text_v567(broken),good)

    def test_correct_polish_is_not_changed(self):
        for x in ["wej?cie","sto??wka","?roda","Ma?gorzata","Wywi?rska","Aleksandra"]:
            self.assertEqual(app._repair_mojibake_text_v567(x),x)

    def test_checkpoint_seed_is_normalized_and_matches_current_staffing(self):
        s=app.load_state()
        seed=app._checkpoint_live_seed(s)
        if not seed:
            self.skipTest("no current checkpoint seed")
        w=seed[0]
        cnt=Counter((x.get("abbr"),x.get("slot"),str(x.get("location"))) for x in w.get("result_school",[]) if x.get("teacher"))
        missing=[]
        for k,v in (s.get("min_people_school") or {}).items():
            req=int(v or 0)
            if req<=0: continue
            ab,slot,loc=k.split("|",2)
            if cnt[(ab,slot,loc)]<req:
                missing.append((k,req,cnt[(ab,slot,loc)]))
        self.assertEqual(missing,[])

    def test_frontend_uses_single_live_snapshot(self):
        self.assertIn("liveDisplaySnapshot()",HTML)
        self.assertIn("rows13PlanDisplay(){let s=this.liveDisplaySnapshot",HTML)
        self.assertIn("schoolPlanDisplay(){let s=this.liveDisplaySnapshot",HTML)
        self.assertIn("displaySummary13(){let s=this.liveDisplaySnapshot",HTML)
        self.assertIn("displaySummarySchool(){let s=this.liveDisplaySnapshot",HTML)

    def test_refresh_signature_tracks_assignment_content(self):
        self.assertIn("let fp=w=>",HTML)
        self.assertIn("x.location,x.teacher",HTML)
        self.assertIn("x.station,x.teacher",HTML)
        self.assertIn("v.live_eligible===true",HTML)

if __name__=="__main__":
    unittest.main(verbosity=2)
