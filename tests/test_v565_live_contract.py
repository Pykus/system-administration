import copy, unittest, sys, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
SOLVER=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")

def baseq():
    return {
        "full":True,"missing":0,
        "coverage13":{"filled":80,"required":80},
        "coverageSchool":{"filled":385,"required":385},
        "result_13":[{"teacher":"A"}],"result_school":[{"teacher":"B"}],
        "_result13":[{"teacher":"A","abbr":"Pn","slot":"1/2","station":"A"}],
        "_resultSchool":[{"teacher":"B","abbr":"Pn","slot":"1/2","location":"wej?cie"}],
        "human_guardrail_ok":True,"fairness_grossly_unbalanced":False,
        "after_last_long":0,"before_first_long":0,
        "after_last_long_lex_proven":True,"before_first_long_lex_proven":True,
        "wait_lessons_total":0,"consecutive_pairs":0,
        "home_group_foreign_13":0,"home_group_foreign_13_wf":0,
        "home_group_foreign_school":0,"fairness_enabled":False,
        "temporary_relaxations_count":0,
    }

class TestLiveContract565(unittest.TestCase):
    def test_feasible_is_not_frozen_as_exact_minimum(self):
        self.assertIn("if st!=cp_model.OPTIMAL and coverage_only",SOLVER)
        self.assertIn("model.Add(expr<=best)",SOLVER)
        self.assertIn("if st==cp_model.OPTIMAL:",SOLVER)
        self.assertNotIn("model.Add(sum(after_last_long_vars)==best_after_last_long)",SOLVER)

    def test_bad_edge_candidate_is_rejected_by_backend(self):
        q=baseq(); q.update(after_last_long=37,after_last_long_lex_proven=False,
                            after_last_long_lex_statuses=["FEASIBLE","OPTIMAL"])
        e=app._live_eligibility_v565(q,{"accepted_compromises":[],"after_last_long_unlocked":True})
        self.assertFalse(e["ok"])
        self.assertIn("after_last_long_not_proven_minimum",e["reasons"])

    def test_proven_edge_minimum_can_be_live(self):
        q=baseq(); q.update(after_last_long=9,after_last_long_lex_proven=True)
        e=app._live_eligibility_v565(q,{"accepted_compromises":[],"after_last_long_unlocked":True})
        self.assertTrue(e["ok"])

    def test_job_add_cannot_publish_unproven_full_coverage(self):
        q=baseq(); q.update(after_last_long=37,after_last_long_lex_proven=False,
                            after_last_long_lex_statuses=["FEASIBLE","FEASIBLE"])
        job={"accepted_compromises":[],"after_last_long_unlocked":True}
        self.assertFalse(app._job_add_working_v527(job,q,"TDD"))
        self.assertEqual(job.get("working_variants",[]),[])
        self.assertEqual(job.get("working_rejected_live_contract_total"),1)

    def test_frontend_uses_backend_live_flag_only(self):
        self.assertIn("v.live_eligible===true",HTML)
        self.assertNotIn("after_last_long_proof?.minimum_exception_assignments",HTML)

    def test_checkpoint_seed_rejects_legacy_full_variant_without_live_flag(self):
        legacy=baseq()
        legacy.update(id="legacy",seq=1)
        # public checkpoint shape
        legacy.pop("_result13"); legacy.pop("_resultSchool")
        from unittest.mock import patch
        cp={"plan_revision":7,"working_variants":[legacy]}
        with patch.object(app,"_latest_repair_checkpoint",return_value=cp):
            self.assertEqual(app._checkpoint_live_seed({"plan_revision":7}),[])

    def test_quick_lane_has_real_edge_retry_budget(self):
        src=(ROOT/"app.py").read_text(encoding="utf-8")
        self.assertIn('trial["solver_edge_lex_seconds"]=4',src)
        self.assertIn('trial["solver_edge_lex_retry_seconds"]=15',src)


    def test_missing_status_is_not_proof_for_scope_with_edge_exceptions(self):
        src=(ROOT/"app.py").read_text(encoding="utf-8")
        self.assertIn('count==0 or diags[i].get(status_key)=="OPTIMAL"',src)
        self.assertNotIn('in (None,"OPTIMAL")',src)

if __name__=="__main__":
    unittest.main(verbosity=2)
