import unittest
from unittest.mock import patch
from pathlib import Path
import app

ROOT=Path(__file__).parent

class TestMergeV54(unittest.TestCase):
    def test_version(self):
        self.assertEqual(app.app.version,"5.6")
        self.assertEqual(app.health()["version"],"5.6")

    def test_long_break_ranges_and_defaults(self):
        s=app.ensure_state_schema({})
        by={c["key"]:c for c in s["global_constraints"]}
        self.assertEqual(by["max_long_day"]["value"],1)
        self.assertEqual(by["max_long_week"]["value"],3)
        self.assertEqual(app.normalize_constraint_rows([{"key":"max_long_day","value":99}])[0]["value"],2)
        self.assertEqual(app.normalize_constraint_rows([{"key":"max_long_week","value":99}])[0]["value"],10)
        self.assertEqual(app.normalize_constraint_rows([{"key":"max_long_day","value":-2}])[0]["value"],0)
        self.assertEqual(app.normalize_constraint_rows([{"key":"max_long_week","value":-2}])[0]["value"],0)

    def test_ui_required_surfaces(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for phrase in ["Plany nauczycieli","Diagnostyka","Walidacja konfiguracji","Musi by","Zalecane"]:
            self.assertIn(phrase,h)
        self.assertNotIn("Awaryjnie pozw",h)
        self.assertNotIn("Preferuj zachowanie obecnego planu",h)
        self.assertIn("diagnosticProblemCount",h)
        self.assertIn("badge bad",h)

    def test_fixed_system_rules(self):
        s=app.ensure_state_schema({"global_constraints":[
            {"key":"no_lesson_overlap","enabled":False,"kind":"soft","priority":1},
            {"key":"one_place_per_slot","enabled":False,"kind":"soft","priority":1},
            {"key":"manual_blocks","enabled":False,"kind":"soft","priority":1},
        ]})
        by={c["key"]:c for c in s["global_constraints"]}
        for k in ["no_lesson_overlap","one_place_per_slot","manual_blocks"]:
            self.assertTrue(by[k]["enabled"])
            self.assertEqual(by[k]["kind"],"hard")

    def test_saved_absence_is_used_by_regular_solvers(self):
        state=app.ensure_state_schema({
            "enabled_teachers_13":["A","B"],
            "enabled_teachers_school":["A","B"],
            "absent_teachers":["A"],
            "manual_blocks":{},
            "school_assignments":[],
            "last_13_assignments":[],
            "individual_constraints":[],
            "global_constraints":[]
        })
        fake=([],[],[],{"cost":0,"diagnostics":{}})
        with patch.object(app,"load_state",return_value=state), patch.object(app,"SEED",{"breaks":[]}), patch.object(app,"solve_positions",return_value=fake) as sp:
            app.solve13({"enabled_teachers":["A","B"]})
            self.assertEqual(sp.call_args.args[3],{"B"})
        with patch.object(app,"load_state",return_value=state), patch.object(app,"SEED",{"breaks":[]}), patch.object(app,"solve_positions",return_value=fake) as sp:
            app.solve_school({"enabled_teachers":["A","B"]})
            self.assertEqual(sp.call_args.args[3],{"B"})

    def test_service_points_to_v54(self):
        txt=(ROOT/"start_service.cmd").read_text(encoding="utf-8")
        self.assertIn("dyzury-v5.6-ortools",txt)

if __name__=="__main__":
    unittest.main(verbosity=2)

