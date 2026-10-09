import copy, inspect, unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")


class TestHumanRealism560(unittest.TestCase):
    def setUp(self):
        self.state=app.load_state()

    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,60,2))

    def test_quick_drafts_preserve_human_guardrails(self):
        required={"max_consecutive_duties","max_day_13","max_day_school","max_week","max_long_day","max_long_week"}
        self.assertTrue(required.issubset(app.HUMAN_REALISM_HARDENED_V560))
        src=inspect.getsource(app._quick_draft_v527)
        self.assertIn("hardened.update(HUMAN_REALISM_HARDENED_V560)",src)

    def test_one_time_migration_sets_free_break_between_duties(self):
        s=copy.deepcopy(self.state)
        s.pop("human_realism_v560_migrated",None)
        row=next(r for r in s["global_constraints"] if r.get("key")=="max_consecutive_duties")
        row["enabled"]=True;row["kind"]="hard";row["value"]=2
        out=app.ensure_state_schema(s)
        migrated=next(r for r in out["global_constraints"] if r.get("key")=="max_consecutive_duties")
        self.assertEqual(migrated["value"],1)
        self.assertTrue(out["human_realism_v560_migrated"])
        migrated["value"]=2
        out2=app.ensure_state_schema(out)
        self.assertEqual(next(r for r in out2["global_constraints"] if r.get("key")=="max_consecutive_duties")["value"],2)

    def test_adjacent_duties_are_human_guardrail_violation(self):
        s=copy.deepcopy(self.state)
        s["human_realism_v560_migrated"]=True
        row=next(r for r in s["global_constraints"] if r.get("key")=="max_consecutive_duties")
        row["enabled"]=True;row["kind"]="hard";row["value"]=1
        brs=[b for b in app.SEED["breaks"] if b.get("abbr")=="Pn"]
        teacher=next(iter(app.ALL))
        a=[{"teacher":teacher,"abbr":"Pn","slot":brs[0]["label"]},
           {"teacher":teacher,"abbr":"Pn","slot":brs[1]["label"]}]
        p=app._human_guardrail_profile_v560(s,a)
        self.assertFalse(p["human_guardrail_ok"])
        self.assertEqual(p["human_longest_consecutive_duties"],2)

    def test_weekly_limit_is_human_guardrail(self):
        s=copy.deepcopy(self.state)
        cap=next(r for r in s["global_constraints"] if r.get("key")=="max_week")
        cap["enabled"]=True;cap["kind"]="hard";cap["value"]=3
        teacher=next(iter(app.ALL))
        a=[]
        for b in app.SEED["breaks"]:
            a.append({"teacher":teacher,"abbr":b["abbr"],"slot":b["label"]})
            if len(a)==4: break
        p=app._human_guardrail_profile_v560(s,a)
        self.assertFalse(p["human_guardrail_ok"])
        self.assertGreaterEqual(p["human_max_weekly_duties"],4)

    def test_bad_full_draft_is_rejected_before_live(self):
        job={}
        q={"full":True,"human_guardrail_ok":False,
           "human_guardrail_violations":["test"],"human_max_weekly_duties":20,
           "human_max_daily_duties":8,"human_longest_consecutive_duties":7,
           "_result13":[{"abbr":"Pn","slot":"1/2","station":"A","teacher":"X"}],
           "_resultSchool":[]}
        self.assertFalse(app._job_add_working_v527(job,q,"test"))
        self.assertEqual(job.get("working_rejected_human_total"),1)
        self.assertFalse(job.get("working_variants"))

    def test_live_ui_rejects_nonhuman_variant(self):
        line=next(x for x in HTML.splitlines() if x.strip().startswith("livePlanVariant(){"))
        self.assertIn("this.effectivePlan",line)
        import inspect
        self.assertIn('v.get("live_eligible") is True',inspect.getsource(app._current_live_variant_v573))
        self.assertIn('q.get("human_guardrail_ok") is False',inspect.getsource(app._live_eligibility_v565))
        self.assertIn("Filtr realnego planu",HTML)

    def test_constraint_description_explains_rest_break(self):
        row=app._global_row(self.state,"max_consecutive_duties")
        self.assertIn("kolejna przerwa musi by",row.get("description","")); self.assertIn(" wolna",row.get("description",""))

    def test_inactive_13_slot_stays_inactive(self):
        self.assertFalse(app._position_zone_active_13("Wt","9/po"))
        self.assertEqual(app._required_stations_13(self.state,"Wt","9/po"),[])

    def test_inactive_13_slot_cannot_be_reactivated_by_staffing(self):
        s=copy.deepcopy(self.state)
        app._set_required_13_count(s,"Wt","9/po",2)
        self.assertEqual(s["min_people_13"]["Wt|9/po"],0)
        self.assertTrue(all(s["min_people_13_stations"].get(f"Wt|9/po|{sid}",0)==0 for sid in app._stations_13(s)))

    def test_break_after_last_13_lesson_remains_active(self):
        periods=sorted(app._zone_lesson_periods("1-3","Wt"))
        self.assertTrue(periods)
        br=next(b for b in app.SEED["breaks"] if b["abbr"]=="Wt" and b.get("prev")==max(periods))
        self.assertTrue(app._zone_ended_lesson_before_break("1-3","Wt",br["label"]))
        self.assertTrue(app._position_zone_active_13("Wt",br["label"]))


if __name__=="__main__":
    unittest.main()
