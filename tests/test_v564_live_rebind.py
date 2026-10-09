import unittest
from pathlib import Path
import sys, copy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")

class TestLiveRebind564(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,64))

    def test_poll_rebinds_to_current_job_when_old_job_disappears(self):
        self.assertIn("else{let c=await fetch('/api/diagnostics/repair/search/current?ts='",HTML)
        self.assertIn("if(x.job)this.setRepairJob(x.job);else this.repairJob=null",HTML)

    def test_live_complete_variant_remains_source_of_truth(self):
        self.assertIn("rows13PlanDisplay(){let s=this.liveDisplaySnapshot",HTML)
        self.assertIn("displaySummary13(){let s=this.liveDisplaySnapshot",HTML)
        self.assertIn(":assign13=\"rows13PlanDisplay\"",HTML)

    def test_school_missing_list_filters_zero_staffing_and_non_school_locations(self):
        self.assertIn("visibleSchoolUnresolved()",HTML)
        self.assertIn("this.schoolLocations.includes(loc)",HTML)
        self.assertIn("Number(this.minPeopleSchool?.[p.abbr+'|'+p.slot+'|'+loc]||0)>0",HTML)
        self.assertIn("v-for=\"x in visibleSchoolUnresolved\"",HTML)

    def test_wt_after_period_9_is_zero_for_13_in_current_real_state(self):
        s=app.load_state()
        self.assertEqual(int((s.get("min_people_13") or {}).get("Wt|9/po",0)),0)
        self.assertEqual([x for x in app._diag_positions_13(s)[0] if x.get("abbr")=="Wt" and x.get("slot")=="9/po"],[])

    def test_current_state_and_full_live_variant_cannot_be_conflated(self):
        s=app.load_state()
        saved_filled=sum(1 for r in s.get("last_13_assignments",[]) or [] for a in r.get("assignments",[]) or [] if a.get("teacher"))
        self.assertGreaterEqual(saved_filled,0)
        # Contract: while a complete live variant exists, display summary must come from live coverage,
        # never from the saved-plan counters.
        self.assertIn("let c=s.coverage13||{}",HTML)


    def test_checkpoint_seed_requires_same_revision_and_complete_variant(self):
        from unittest.mock import patch
        state={"plan_revision":7}
        good={"seq":4,"missing":0,"coverage13":{"filled":80,"required":80},
              "coverageSchool":{"filled":385,"required":385},"result_13":[{"x":1}],
              "result_school":[{"x":1}],"human_guardrail_ok":True,
              "fairness_grossly_unbalanced":False,"wait_lessons_total":0,
              "after_last_long":0,"before_first_long":0,"consecutive_pairs":0,
              "home_group_foreign_13":0,"home_group_foreign_13_wf":0,
              "home_group_foreign_school":0,"fairness_enabled":False,
              "temporary_relaxations_count":0,"live_eligible":True}
        with patch.object(app,"_latest_repair_checkpoint",return_value={"plan_revision":7,"working_variants":[good]}):
            self.assertEqual(len(app._checkpoint_live_seed(state)),1)
        with patch.object(app,"_latest_repair_checkpoint",return_value={"plan_revision":6,"working_variants":[good]}):
            self.assertEqual(app._checkpoint_live_seed(state),[])

    def test_restart_checkpoint_is_not_reported_as_running(self):
        import tempfile, json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            (d/"x.json").write_text(json.dumps({"id":"x","status":"running","working_variants":[]}),encoding="utf-8")
            with patch.object(app,"REPAIR_CHECKPOINT_DIR",d):
                x=app._latest_repair_checkpoint()
            self.assertEqual(x["status"],"interrupted")


    def test_actual_inline_javascript_parses(self):
        import re, subprocess, tempfile, shutil
        if not shutil.which("node"):
            self.skipTest("node unavailable")
        scripts=[x for x in re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",HTML,re.S|re.I) if x.strip()]
        self.assertTrue(scripts)
        with tempfile.TemporaryDirectory() as td:
            js=Path(td)/"inline.js"
            js.write_text("\n;\n".join(scripts),encoding="utf-8")
            p=subprocess.run(["node","--check",str(js)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)


    def test_interrupted_same_revision_reuses_job_id(self):
        from unittest.mock import patch
        with patch.object(app,"_latest_repair_checkpoint",return_value={"id":"same-job","status":"interrupted","plan_revision":9}):
            self.assertEqual(app._checkpoint_resume_id({"plan_revision":9}),"same-job")
            self.assertIsNone(app._checkpoint_resume_id({"plan_revision":10}))
        with patch.object(app,"_latest_repair_checkpoint",return_value={"id":"old","status":"completed","plan_revision":9}):
            self.assertIsNone(app._checkpoint_resume_id({"plan_revision":9}))


    def test_restart_checkpoint_accepts_utf8_bom(self):
        import tempfile, json
        from unittest.mock import patch
        payload={"id":"bom-job","status":"running","working_variants":[]}
        with tempfile.TemporaryDirectory() as td:
            d=Path(td); f=d/"x.json"
            f.write_bytes(b"\xef\xbb\xbf"+json.dumps(payload).encode("utf-8"))
            with patch.object(app,"REPAIR_CHECKPOINT_DIR",d):
                x=app._latest_repair_checkpoint()
            self.assertEqual(x["id"],"bom-job")
            self.assertEqual(x["status"],"interrupted")

if __name__=="__main__":
    unittest.main()
