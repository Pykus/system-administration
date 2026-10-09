import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")


class TestStatsTab554(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,54))

    def test_stats_is_third_plan_tab(self):
        group=HTML.split('<span class="tab-group-label">Plan dyżurów</span>',1)[1].split('</div>',1)[0]
        self.assertLess(group.index("mainTab==='13'"),group.index("mainTab==='school'"))
        self.assertLess(group.index("mainTab==='school'"),group.index("mainTab==='stats'"))
        self.assertIn(">Statystyki</button>",group)

    def test_stats_has_direct_noncollapsed_view(self):
        start=HTML.index('<template v-if="cfg && mainTab===\'stats\'">')
        end=HTML.index("<template v-if=\"cfg && mainTab==='teachers'\">",start)
        block=HTML[start:end]
        self.assertNotIn("<details",block)
        self.assertIn("Statystyki obciążenia nauczycieli",block)
        self.assertIn("stats-loadcell",block)

    def test_stats_show_teaching_load_and_normalized_duty_load(self):
        self.assertIn("@click=\"sortStats('lessons')\"",HTML)
        self.assertIn("@click=\"sortStats('minutesPerLesson')\"",HTML)
        self.assertIn("x.minutesPerLesson",HTML)
        self.assertIn("statsMaxMinutes",HTML)

    def test_stats_use_dedicated_live_source_with_saved_fallback(self):
        line=next(x for x in HTML.splitlines() if x.strip().startswith("statisticsRows(){"))
        self.assertIn("this.statsAssignments13",line)
        self.assertIn("this.statsAssignmentsSchool",line)
        school=next(x for x in HTML.splitlines() if x.strip().startswith("statsAssignmentsSchool(){"))
        self.assertIn("this.schoolPlanDisplay",school)
        self.assertNotIn("this.schoolDisplay",line)


class TestActiveRelaxationProvenance554(unittest.TestCase):
    def test_previous_auto_relaxation_survives_next_preflight_if_rule_is_still_soft5(self):
        import copy
        s=copy.deepcopy(app.load_state())
        row=app._global_row(s,"after_last_short")
        row.update({"enabled":True,"kind":"soft","priority":5})
        prev=[{"key":"after_last_short","label":"po ostatniej","minimum_exception_cases":3}]
        active=app._active_auto_relaxations_v554(s,prev,[])
        self.assertEqual(len(active),1)
        self.assertEqual(active[0]["key"],"after_last_short")

    def test_provenance_disappears_when_user_changes_rule_away_from_soft5(self):
        import copy
        s=copy.deepcopy(app.load_state())
        row=app._global_row(s,"after_last_short")
        row.update({"enabled":True,"kind":"hard","priority":5})
        prev=[{"key":"after_last_short","label":"po ostatniej"}]
        self.assertEqual(app._active_auto_relaxations_v554(s,prev,[]),[])


class TestRelaxationVisibility554(unittest.TestCase):
    def test_plan_banner_is_visible_for_both_plans_and_stats(self):
        self.assertIn("['13','school','teachers','stats'].includes(mainTab)",HTML)
        self.assertIn("Plan zawiera konieczne wyjątki od reguł „Musi być”",HTML)
        self.assertIn("Minimum koniecznych wyjątków",HTML)

    def test_banner_filters_to_still_active_soft_priority_5_rules(self):
        line=next(x for x in HTML.splitlines() if x.strip().startswith("activeAutoRelaxations(){"))
        self.assertIn("last_preflight_constraint_relaxations",line)
        self.assertIn("r.kind==='soft'",line)
        self.assertIn("Number(r.priority||0)===5",line)

    def test_preflight_updates_banner_state_immediately(self):
        self.assertIn("this.cfg.state.last_preflight_constraint_relaxations=JSON.parse",HTML)
        self.assertIn("this.cfg.state.global_constraints=JSON.parse",HTML)


if __name__=="__main__":
    unittest.main()
