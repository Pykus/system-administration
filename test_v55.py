import unittest
from unittest.mock import patch
from pathlib import Path
import app
from solver_ortools import _safe_seed

ROOT=Path(__file__).parent

class TestV55(unittest.TestCase):
    def test_version(self):
        self.assertEqual(app.app.version,"5.6")
        self.assertEqual(app.health()["version"],"5.6")

    def test_empty_seed_is_safe(self):
        s=app.ensure_state_schema({"solver_seed":""})
        self.assertEqual(s["solver_seed"],20260918)
        self.assertEqual(_safe_seed(""),20260918)
        self.assertEqual(_safe_seed(None),20260918)
        self.assertEqual(_safe_seed("123"),123)

    def test_repair_semantic_order(self):
        state={"global_constraints":[
            {"key":"avoid_wait","label":"Unikaj dodatkowego oczekiwania","enabled":True,"kind":"hard","priority":5},
            {"key":"max_day_13","label":"Maksimum dziennie","enabled":True,"kind":"hard","priority":4},
        ],"individual_constraints":[]}
        rows=app._repair_candidates(state)
        by={x["token"]:x for x in rows}
        self.assertGreater(by["g:avoid_wait"]["human_cost"],by["g:max_day_13"]["human_cost"])

    def test_partial_repair_is_not_proposed(self):
        candidate={"token":"g:max_day_13","label":"Limit","priority":4,"type":"global","human_cost":300}
        base={"required":10,"filled":8,"missing":2,"assignments":[],"waits":[],"diagnostics":{}}
        partial={"required":10,"filled":9,"missing":1,"assignments":[],"waits":[],"diagnostics":{}}
        with patch.object(app,"_coverage",side_effect=[base,partial]),              patch.object(app,"_repair_candidates",return_value=[candidate]),              patch.object(app,"_relax",side_effect=lambda s,t:s):
            out=app._repair_for_scope({"global_constraints":[],"individual_constraints":[]},"szkoła",["A"])
        self.assertEqual(out["suggestions"],[])
        self.assertIn("Nie proponuję zmian częściowych",out["message"])

    def test_teacher_13_affinity_exists(self):
        a=app._teacher13_affinity()
        self.assertIn("Ewa Majewska",a)
        self.assertGreater(a["Ewa Majewska"]["score"],0)
        self.assertIn("1–3",a["Ewa Majewska"]["reason"])

    def test_ui_is_user_friendly(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for phrase in [
            "Propozycje dojścia do pełnej obsady",
            "Pokazuję tylko warianty, które faktycznie usuwają wszystkie braki",
            "teacherPageSize:12",
            "sortedTeachers()",
            "addGeneral13Emergency",
            "bestRepair13",
            "Uwagi techniczne i szczegółowa diagnostyka solvera",
            "Seed jest ustawiany automatycznie",
        ]:
            self.assertIn(phrase,h)
        self.assertNotIn('Seed solvera<input',h)
        self.assertIn(':teachers="pagedTeachers13"',h)
        self.assertIn(':teachers="pagedTeachersSchool"',h)

    def test_teacher_change_summary(self):
        old={"13|Pn|1/2|A":"A","13|Pn|1/2|B":"B"}
        new={"13|Pn|1/2|A":"A","13|Pn|1/2|B":"C"}
        x=app._teacher_changes(old,new)
        self.assertEqual(x["positions_changed"],1)
        self.assertEqual(x["teachers_changed"],2)
        by={r["teacher"]:r for r in x["teachers"]}
        self.assertEqual(by["B"]["removed"],1)
        self.assertEqual(by["C"]["added"],1)

if __name__=="__main__":
    unittest.main(verbosity=2)
