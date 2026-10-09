import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")


class TestLiveStats557(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,57))

    def test_live_follow_is_default(self):
        self.assertIn("followSolverEverywhere:true",HTML)

    def test_live_variant_follows_best_current_working_variant(self):
        line=next(x for x in HTML.splitlines() if x.strip().startswith("livePlanVariant(){"))
        self.assertIn("this.effectivePlan",line)
        self.assertNotIn("working_variants",line)
        import inspect
        selector=inspect.getsource(app._current_live_variant_v573)
        self.assertIn('v.get("live_eligible") is True',selector)
        self.assertIn('v.get("result_13")',selector)
        self.assertIn('v.get("result_school")',selector)
        self.assertIn("stale_due_to_manual_edit",selector)
        self.assertIn("cancelled",selector)
        self.assertIn("failed",selector)
        self.assertIn("coverage_not_full",inspect.getsource(app._live_eligibility_v565))

    def test_stats_sources_fall_back_to_saved_plan(self):
        a13=next(x for x in HTML.splitlines() if x.strip().startswith("statsAssignments13(){"))
        school=next(x for x in HTML.splitlines() if x.strip().startswith("statsAssignmentsSchool(){"))
        self.assertIn("this.rows13PlanDisplay",a13)
        self.assertIn("this.schoolPlanDisplay",school)
    def test_table_uses_same_live_source(self):
        row=next(x for x in HTML.splitlines() if x.strip().startswith("statisticsRows(){"))
        self.assertIn("this.statsAssignments13",row)
        self.assertIn("this.statsAssignmentsSchool",row)

    def test_charts_are_present_and_share_statistics_rows(self):
        self.assertIn("Największe obciążenie — minuty dyżurów",HTML)
        self.assertIn("Największe obciążenie — liczba dyżurów",HTML)
        self.assertIn("statsChartRows(){return [...this.statisticsRows]",HTML)
        self.assertIn("statsDutyChartRows(){return [...this.statisticsRows]",HTML)

    def test_live_source_is_visible_to_user(self):
        self.assertIn("{{planSourceLabel}}",HTML)
        self.assertIn("effectivePlan?.source?.source_id",HTML)
        self.assertIn('<input type="checkbox" checked disabled>',HTML)
        self.assertIn("pollRepair(),900",HTML)

    def test_repair_poll_interval_drives_refresh(self):
        self.assertIn("setTimeout(()=>this.pollRepair(),900)",HTML)
        setter=next(x for x in HTML.splitlines() if x.strip().startswith("setRepairJob(next){"))
        self.assertIn("this.repairJob=next",setter)


if __name__=="__main__":
    unittest.main()
