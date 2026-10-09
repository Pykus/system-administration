import copy
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
import solver_ortools as so

OPENING={"day":"Poniedziałek","abbr":"Pn","label":"0/1","time":"07:25-07:30","prev":0,"next":1,"minutes":5}
EARLY={"name":"Early Teacher","group":"school","lessons":{"Pn":{"1":[{"class":"X","subject":"X","room":"1"}]}}}
LATE={"name":"Late Teacher","group":"school","lessons":{"Pn":{"2":[{"class":"X","subject":"X","room":"1"}]}}}

def base_state():
    return {
        "global_constraints":[
            {"key":"before_first_short","enabled":True,"kind":"hard","priority":5,"value":None},
            {"key":"one_place_per_slot","enabled":True,"kind":"hard","priority":5,"value":None},
        ],
        "individual_constraints":[
            {"teacher":"Early Teacher","scope":"szkoła","rule":"no_before_first_lesson",
             "kind":"hard","priority":5,"enabled":True}
        ],
        "teacher_relaxed_rules":{},
        "manual_blocks":{},"active_absences":[],"absent_teachers":[],"excluded_teachers":[],
        "preference_grid":{},"teacher_workload":{},
        "deterministic_mode":True,"solver_seed":20260921,"solver_internal_workers":1
    }

class TestOpeningSlotPolicy548(unittest.TestCase):
    def test_opening_slot_is_recognized_semantically(self):
        self.assertTrue(so._is_opening_break(OPENING))
        self.assertFalse(so._is_opening_break({**OPENING,"label":"1/2","prev":1,"next":2}))

    def test_solver_ignores_before_first_constraints_for_01_and_chooses_period1_teacher(self):
        seed={"teachers":[copy.deepcopy(EARLY),copy.deepcopy(LATE)],"breaks":[copy.deepcopy(OPENING)]}
        pos=[{"break":copy.deepcopy(OPENING),"abbr":"Pn","slot":"0/1","location":"Hall"}]
        assignments,waits,missing,meta=so.solve_positions_ortools(
            base_state(),"szkoła",pos,["Early Teacher","Late Teacher"],[],None,seed,
            {"Early Teacher":"school","Late Teacher":"school"},coverage_only=False,repair_mode=False)
        self.assertEqual(missing,[])
        self.assertEqual(assignments[0]["teacher"],"Early Teacher")
        self.assertEqual(waits,[])

    def test_solver_never_uses_teacher_starting_later_for_01(self):
        seed={"teachers":[copy.deepcopy(EARLY),copy.deepcopy(LATE)],"breaks":[copy.deepcopy(OPENING)]}
        pos=[{"break":copy.deepcopy(OPENING),"abbr":"Pn","slot":"0/1","location":"Hall"}]
        assignments,waits,missing,meta=so.solve_positions_ortools(
            base_state(),"szkoła",pos,["Late Teacher"],[],None,seed,
            {"Early Teacher":"school","Late Teacher":"school"},coverage_only=False,repair_mode=False)
        self.assertIsNone(assignments[0]["teacher"])
        self.assertEqual(len(missing),1)
        reasons=[x["reason"] for x in meta["diagnostics"]["unresolved"][0]["blocked_reasons"]]
        self.assertTrue(any("1. godzinie" in r or "pierwszym slocie" in r for r in reasons),reasons)

    def test_preflight_and_local_repair_apply_same_opening_policy(self):
        seed={"teachers":[copy.deepcopy(EARLY),copy.deepcopy(LATE)],"breaks":[copy.deepcopy(OPENING)]}
        tby={t["name"]:t for t in seed["teachers"]}
        state=base_state()
        state.update({"school_assignments":[],"last_13_assignments":[],"locked_assignments":[]})
        pos={"break":copy.deepcopy(OPENING),"abbr":"Pn","slot":"0/1","location":"Hall"}
        target={"scope":"szkoła","abbr":"Pn","slot":"0/1","location":"Hall"}
        with patch.object(app,"SEED",seed), patch.object(app,"TBY",tby), \
             patch.object(app,"GROUP",{"Early Teacher":"school","Late Teacher":"school"}), \
             patch.object(app,"ALL",{"Early Teacher","Late Teacher"}):
            allowed=app._preflight_teacher_allowed_v524(state,"szkoła",pos,["Early Teacher","Late Teacher"])
            self.assertIn("Early Teacher",allowed)
            self.assertNotIn("Late Teacher",allowed)
            early=app._local_candidate(state,"Source",target,"Early Teacher",[])
            late=app._local_candidate(state,"Source",target,"Late Teacher",[])
            self.assertIsNotNone(early[0],early)
            self.assertIsNone(late[0],late)

    def test_opening_repeat_minimization_is_in_solver_objective(self):
        src=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")
        self.assertIn("by_opening_week",src)
        self.assertIn("opening_repeat",src)

    def test_interfaces_explain_01_exception(self):
        appsrc=(ROOT/"app.py").read_text(encoding="utf-8")
        html=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        self.assertIn("slotu 0/1",appsrc)
        self.assertIn("z wyjątkiem slotu 0/1",html)
        self.assertIn("bez 0/1",html)

if __name__=="__main__":
    unittest.main()
