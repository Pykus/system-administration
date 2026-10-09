import unittest
from pathlib import Path
import sys, math

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")


class TestFairnessGate559(unittest.TestCase):
    def setUp(self):
        self.state=app.load_state()
        self.eligible=set(app.ALL)-set(self.state.get("excluded_teachers",[]) or [])-set(self.state.get("absent_teachers",[]) or [])

    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,59))

    def test_configured_fairness_is_enabled_priority_five(self):
        row=app._global_row(self.state,"lesson_load_fairness")
        self.assertTrue(row.get("enabled"))
        self.assertEqual(row.get("kind"),"soft")
        self.assertEqual(int(row.get("priority") or 0),5)

    def test_extreme_concentration_is_rejected(self):
        teacher=max(self.eligible,key=lambda n:sum(len(v or {}) for v in app.TBY[n].get("lessons",{}).values()))
        assignments=[{"teacher":teacher} for _ in range(455)]
        m=app._fairness_profile_v559(self.state,assignments,self.eligible)
        self.assertTrue(m["fairness_grossly_unbalanced"])
        self.assertGreater(m["fairness_normalized_deviation"],0.75)
        self.assertGreater(m["fairness_top10_share"],0.55)

    def test_proportional_distribution_is_not_rejected(self):
        factors={}
        for n in self.eligible:
            lessons=sum(len(v or {}) for v in app.TBY[n].get("lessons",{}).values())
            manual=max(0.1,float((self.state.get("teacher_workload",{}) or {}).get(n,1.0)))
            factors[n]=lessons*manual
        sf=sum(factors.values())
        raw={n:455*factors[n]/sf for n in self.eligible}
        counts={n:int(math.floor(v)) for n,v in raw.items()}
        left=455-sum(counts.values())
        for n in sorted(self.eligible,key=lambda n:raw[n]-counts[n],reverse=True)[:left]:
            counts[n]+=1
        assignments=[{"teacher":n} for n,c in counts.items() for _ in range(c)]
        m=app._fairness_profile_v559(self.state,assignments,self.eligible)
        self.assertFalse(m["fairness_grossly_unbalanced"])
        self.assertLess(m["fairness_normalized_deviation"],0.10)

    def test_bad_fairness_is_warning_not_live_blocker(self):
        job={"after_last_long_unlocked":False}
        q={"full":True,"missing":0,"human_guardrail_ok":True,"after_last_long":0,"before_first_long":0,
           "fairness_grossly_unbalanced":True,"fairness_normalized_deviation":1.18,"fairness_max_ratio":4.5,
           "fairness_max_excess":28.0,"fairness_top10_share":0.64,"fairness_rejection_reasons":["test"],
           "_result13":[{"abbr":"Pn","slot":"1/2","station":"A","teacher":"X"}],"_resultSchool":[]}
        self.assertTrue(app._job_add_working_v527(job,q,"test"))
        self.assertEqual(job.get("working_fairness_warning_total"),1)
        self.assertTrue(job.get("working_variants"))

    def test_working_rank_uses_edge_comfort_before_fairness(self):
        job={}
        good={"wait_lessons_total":0,"fairness_enabled":True,"fairness_normalized_deviation":0.40,
              "fairness_max_ratio":2.0,"after_last_long":20,"before_first_long":10,
              "consecutive_pairs":20,"temporary_relaxations_count":5}
        bad={"wait_lessons_total":0,"fairness_enabled":True,"fairness_normalized_deviation":0.60,
             "fairness_max_ratio":2.5,"after_last_long":1,"before_first_long":1,
             "consecutive_pairs":1,"temporary_relaxations_count":1}
        self.assertGreater(app._working_quality_key_v559(good,job),app._working_quality_key_v559(bad,job))

    def test_live_contract_keeps_fairness_as_optimization_only(self):
        import inspect
        src=inspect.getsource(app._live_eligibility_v565)
        self.assertNotIn('reasons.append("fairness")',src)
        self.assertIn("working_fairness_warning_total",inspect.getsource(app._job_add_working_v527))
        line=next(x for x in HTML.splitlines() if x.strip().startswith("livePlanVariant(){"))
        self.assertIn("this.effectivePlan",line)


if __name__=="__main__":
    unittest.main()
