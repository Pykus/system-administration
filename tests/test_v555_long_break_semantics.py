import copy
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")


class TestLongBreakUi555(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,55))

    def test_ui_separates_proven_minimum_candidates_and_actual_draft(self):
        self.assertIn("Udowodnione minimum przez preflight",HTML)
        self.assertIn("Kandydaci wskazani przez preflight do koniecznych wyjątków",HTML)
        self.assertIn("W tym konkretnym szkicu faktycznie",HTML)
        self.assertIn("Poniższa lista nie jest listą kandydatów",HTML)

    def test_chip_says_draft_not_minimum_and_counts_unique_breaks(self):
        self.assertIn("Stan TEGO szkicu, nie minimum",HTML)
        self.assertIn("after_last_long_unique_breaks",HTML)
        self.assertIn("różnych przerw",HTML)


class TestDraftLongBreakMetrics555(unittest.TestCase):
    def test_assignment_totals_equal_teacher_and_slot_breakdowns(self):
        s=app.load_state()
        flat13=[]
        for row in s.get("last_13_assignments",[]) or []:
            for a in row.get("assignments",[]) or []:
                if a.get("teacher"):
                    flat13.append({**a,"abbr":row.get("abbr"),"slot":row.get("label")})
        ev={
            "school13":{"waits":[],"assignments":flat13},
            "school":{"waits":[],"assignments":s.get("school_assignments",[]) or []},
        }
        m=app._draft_metrics_v527(ev,[])
        self.assertEqual(sum(x["cases"] for x in m["after_last_long_teachers"]),m["after_last_long"])
        self.assertEqual(sum(x["cases"] for x in m["after_last_long_slots"]),m["after_last_long"])
        self.assertEqual(len(m["after_last_long_slots"]),m["after_last_long_unique_breaks"])
        self.assertLessEqual(m["after_last_long_unique_breaks"],m["after_last_long"])


class TestLongBreakNecessityProof555(unittest.TestCase):
    def test_one_required_position_with_only_after_last_candidates_proves_one_exception(self):
        teachers=[n for n in sorted(app.ALL) if app.GROUP.get(n)=="school"][:2]
        self.assertEqual(len(teachers),2)
        originals={n:copy.deepcopy(app.TBY[n]["lessons"]) for n in teachers}
        br=next(b for b in app.SEED["breaks"] if b.get("abbr")=="Pn" and b.get("label")=="6/7")
        try:
            for n in teachers:
                app.TBY[n]["lessons"]={d:{} for d in ["Pn","Wt","Śr","Czw","Pi"]}
                app.TBY[n]["lessons"]["Pn"]={"6":[{"class":"TDD","subject":"test","room":"100","source":"TDD"}]}

            s=copy.deepcopy(app.load_state())
            s["excluded_teachers"]=[n for n in app.ALL if n not in teachers]
            s["enabled_teachers_school"]=teachers
            s["enabled_teachers_13"]=[]
            s["freeze_pool_school"]=True
            s["freeze_pool_13"]=True
            s["manual_blocks"]={}
            s["locked_assignments"]=[]
            s["individual_constraints"]=[]
            row=app._global_row(s,"after_last_long")
            row.update({"enabled":True,"kind":"hard","priority":5})
            pos={"day":br["day"],"abbr":"Pn","slot":"6/7","location":"TDD","break":br}
            with patch.object(app,"_diag_positions_13",return_value=([],[],{})),                  patch.object(app,"_school_positions",return_value=([pos],{},[],[])):
                proof=app._edge_rule_exception_proof_v555(s,[],teachers,"after_last_long")

            self.assertTrue(proof["required"])
            self.assertEqual(proof["minimum_teachers"],1)
            self.assertEqual(proof["minimum_exception_assignments"],1)
            self.assertEqual({x["teacher"] for x in proof["candidate_teachers"]},set(teachers))
            self.assertEqual(len(proof["affected_slots"]),1)
            self.assertEqual(proof["affected_slots"][0]["minimum_exceptions"],1)
        finally:
            for n in teachers:
                app.TBY[n]["lessons"]=originals[n]


if __name__=="__main__":
    unittest.main()
