import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")


def line_start(prefix):
    return next(x for x in HTML.splitlines() if x.strip().startswith(prefix))


class TestLiveSourceAllScreens558(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,58))

    def test_global_live_follow_is_default(self):
        self.assertIn("followSolverEverywhere:true",HTML)
        self.assertIn('<input type="checkbox" checked disabled>',HTML)
        self.assertNotIn('v-model="followSolverEverywhere" @change="refreshEpoch++"',HTML)

    def test_live_source_requires_complete_both_scopes(self):
        line=line_start("livePlanVariant(){")
        self.assertIn("this.effectivePlan",line)
        import inspect
        selector=inspect.getsource(app._current_live_variant_v573)
        self.assertIn('v.get("live_eligible") is True',selector)
        self.assertIn('v.get("result_13")',selector)
        self.assertIn('v.get("result_school")',selector)
        backend=inspect.getsource(app._live_eligibility_v565)
        self.assertIn('not q.get("full")',backend)
        self.assertIn('int(q.get("missing",10**9)',backend)
        self.assertIn("stale_due_to_manual_edit",selector)
        self.assertIn("cancelled",selector)
        self.assertIn("failed",selector)

    def test_source_banner_covers_every_admin_plan_view(self):
        self.assertIn("['13','school','teachers','stats','mapka','diagnostics'].includes(mainTab)",HTML)
        self.assertIn("effectivePlan?.source?.source_id",HTML)
        self.assertIn("{{planSourceLabel}}",HTML)

    def test_both_main_matrices_use_unified_live_source(self):
        a13=line_start("rows13PlanDisplay(){")
        school=line_start("schoolPlanDisplay(){")
        self.assertIn("this.liveDisplaySnapshot",a13)
        self.assertIn("this.liveDisplaySnapshot",school)
        self.assertIn(':assign13="rows13PlanDisplay"',HTML)
        self.assertIn(':school="schoolFor13PlanDisplay"',HTML)
        self.assertIn(':school="schoolPlanDisplay"',HTML)
        self.assertIn("(livePlanVariant?.id||'base')",HTML)

    def test_school_map_uses_same_live_source(self):
        line=line_start("schoolWho(dc,loc,slot){")
        self.assertIn("this.schoolPlanDisplay",line)

    def test_teacher_plans_use_same_live_source(self):
        duty=line_start("dutyText(name,dc,slot){")
        records=line_start("teacherDutyRecords(name,dc,slot){")
        self.assertIn("this.rows13PlanDisplay",duty)
        self.assertIn("this.schoolPlanDisplay",duty)
        self.assertIn("this.rows13PlanDisplay",records)
        self.assertIn("this.schoolPlanDisplay",records)
        self.assertIn(':disabled="!!livePlanVariant"',HTML)

    def test_statistics_charts_and_table_use_same_live_source(self):
        self.assertIn("statsAssignments13(){return this.rows13PlanDisplay}",HTML)
        self.assertIn("statsAssignmentsSchool(){return this.schoolPlanDisplay}",HTML)
        stats=line_start("statisticsRows(){")
        self.assertIn("this.statsAssignments13",stats)
        self.assertIn("this.statsAssignmentsSchool",stats)
        self.assertIn("statsChartRows(){return [...this.statisticsRows]",HTML)
        self.assertIn("statsDutyChartRows(){return [...this.statisticsRows]",HTML)

    def test_kpis_and_wait_lists_follow_live_source(self):
        self.assertIn("displaySummary13",HTML)
        self.assertIn("displaySummarySchool",HTML)
        self.assertIn("displayWaits13",HTML)
        self.assertIn("displayWaitsSchool",HTML)
        self.assertIn('v-if="showMissingSchool && !livePlanVariant',HTML)

    def test_polling_refresh_signature_tracks_full_live_variant(self):
        sig=line_start("repairPreviewSignature(job){")
        self.assertIn("let full=a.find",sig)
        self.assertIn("v.live_eligible===true",sig)
        self.assertIn("let fp=w=>",sig)
        self.assertIn("x.location,x.teacher",sig)
        self.assertIn("x.station,x.teacher",sig)
        setter=line_start("setRepairJob(next){")
        self.assertIn("before!==after",setter)
        self.assertIn("this.refreshEpoch++",setter)
        self.assertIn("setTimeout(()=>this.pollRepair(),900)",HTML)

    def test_plan_view_templates_do_not_bind_raw_saved_arrays(self):
        import re
        markers=[
            ("13","<template v-if=\"cfg && mainTab==='13'\">","<template v-if=\"cfg && mainTab==='school'\">"),
            ("school","<template v-if=\"cfg && mainTab==='school'\">","<template v-if=\"cfg && mainTab==='stats'\">"),
            ("stats","<template v-if=\"cfg && mainTab==='stats'\">","<template v-if=\"cfg && mainTab==='teachers'\">"),
            ("teachers","<template v-if=\"cfg && mainTab==='teachers'\">","<template v-if=\"cfg && mainTab==='teacherAdmin'\">"),
        ]
        forbidden=[r"\brows13\b",r"\bschoolCurrent\b",r"\bsum13\b",r"\bsumSchool\b",r"\bwaits13\b",r"\bwaitsSchool\b"]
        for name,start,end in markers:
            block=HTML.split(start,1)[1].split(end,1)[0]
            for pattern in forbidden:
                self.assertIsNone(re.search(pattern,block),f"{name} view still binds raw source {pattern}")

    def test_outputs_export_what_user_sees(self):
        self.assertIn("assignments_13:this.rows13PlanDisplay,school_assignments:this.schoolPlanDisplay",HTML)
        self.assertIn("for(let r of this.rows13PlanDisplay)",HTML)
        self.assertIn("this.schoolPlanDisplay.find",HTML)
        self.assertIn("school_assignments:this.schoolPlanDisplay",HTML)

    def test_manual_edit_cannot_silently_mutate_uncommitted_live_draft(self):
        adopt=line_start("async adoptVisiblePlanForManualEdit(){")
        self.assertIn("this.livePlanVariant",adopt)
        self.assertIn("Użyć dokładnie tego szkicu jako bazy",adopt)
        preview=line_start("async previewLocalRepair(name){")
        self.assertIn("if(this.livePlanVariant)",preview)


class TestLegacyPreviewSeparation558(unittest.TestCase):
    def test_diagnostics_working_preview_remains_diagnostics_only(self):
        line=line_start("workingPreview(){")
        self.assertIn("this.mainTab!=='diagnostics'",line)

    def test_live_plan_does_not_depend_on_diagnostics_preview_toggle(self):
        line=line_start("livePlanVariant(){")
        self.assertNotIn("previewWorkingDraft",line)
        self.assertNotIn("workingPreviewId",line)


if __name__=="__main__":
    unittest.main()
