import unittest
from pathlib import Path
import app
import solver_ortools as so

ROOT=Path(__file__).parent

class TestV58(unittest.TestCase):
    def test_version(self):
        self.assertEqual(app.app.version,"5.8")
        self.assertEqual(app.health()["version"],"5.8")

    def test_first_and_last_mean_day_edges(self):
        tby={"T":{"lessons":{"Pn":{"2":[{}],"4":[{}]}}}}
        self.assertTrue(so._is_before_first_lesson(tby,"T",{"abbr":"Pn","next":2}))
        self.assertFalse(so._is_before_first_lesson(tby,"T",{"abbr":"Pn","next":4}))
        self.assertTrue(so._is_after_last_lesson(tby,"T",{"abbr":"Pn","prev":4}))
        self.assertFalse(so._is_after_last_lesson(tby,"T",{"abbr":"Pn","prev":2}))

    def test_long_edge_policy_is_hard(self):
        st=app.ensure_state_schema({})
        cm={x["key"]:x for x in st["global_constraints"]}
        for key in ("before_first_long","after_last_long"):
            self.assertTrue(cm[key]["enabled"])
            self.assertEqual(cm[key]["kind"],"hard")
            self.assertEqual(cm[key]["priority"],5)
        self.assertIn("before_first_short",cm)
        self.assertIn("after_last_short",cm)

    def test_legacy_before_constraint_removed(self):
        st=app.ensure_state_schema({"global_constraints":[{"key":"no_before_lesson","enabled":True,"kind":"soft","priority":1}]})
        self.assertNotIn("no_before_lesson",{x["key"] for x in st["global_constraints"]})

    def test_lesson_count(self):
        tby={"A":{"lessons":{"Pn":{"1":[],"2":[]},"Wt":{"1":[]} }}}
        self.assertEqual(so._lesson_count(tby,"A"),3)

    def test_ui_contract(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for phrase in ("teacherPageSize:15","Proporcjonalnie do liczby lekcji w planie","Ręczna waga udziału","Efektywny wsp.","0 — brak stanowiska","ustawienie wejściowe"):
            self.assertIn(phrase,h)
        tp=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")
        self.assertIn("Plan tygodnia – lekcje i dyżury w jednej osi czasu",tp)
        self.assertIn("Godzina",tp)
        self.assertNotIn('<div class="grid">',tp)

if __name__=="__main__":
    unittest.main(verbosity=2)
