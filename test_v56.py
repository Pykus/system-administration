import unittest
from pathlib import Path
import app

ROOT=Path(__file__).parent

class TestV56(unittest.TestCase):
    def test_version(self):
        self.assertIn(app.app.version,("5.6","5.7","5.8"))
        self.assertIn(app.health()["version"],("5.6","5.7"))

    def test_constraint_order_is_preserved(self):
        rows=[
            {"key":"b","kind":"soft","priority":3,"enabled":True},
            {"key":"a","kind":"soft","priority":3,"enabled":True},
        ]
        out=app.normalize_constraint_rows(rows)
        self.assertEqual([x["key"] for x in out],["b","a"])

    def test_descriptions_use_polish_terms(self):
        s=app.ensure_state_schema({"global_constraints":[
            {"key":"custom","label":"X","kind":"soft","priority":3,"enabled":True,"description":"SOFT kara, HARD zakaz"}
        ]})
        x=next(c for c in s["global_constraints"] if c["key"]=="custom")
        self.assertNotIn("SOFT",x["description"].upper())
        self.assertNotIn("HARD",x["description"].upper())
        self.assertIn("Zalecane",x["description"])
        self.assertIn("Musi być",x["description"])

    def test_teacher_registry_and_portal_exist(self):
        self.assertTrue(app.TEACHER_REGISTRY_PATH.exists())
        active=[n for n,r in app.TEACHER_REGISTRY.items() if r.get("active",True)]
        self.assertTrue(active)
        n=active[0]
        token=app.TEACHER_REGISTRY[n]["portal_token"]
        self.assertEqual(app._portal_teacher(token),n)
        self.assertTrue((ROOT/"static"/"teacher.html").exists())

    def test_teacher_changes_include_exact_duties(self):
        old={"13|Pn|1/2|A":{"teacher":"A","scope":"1–3","abbr":"Pn","slot":"1/2","place":"A","wait":0}}
        new={"13|Pn|1/2|A":{"teacher":"B","scope":"1–3","abbr":"Pn","slot":"1/2","place":"A","wait":1}}
        x=app._teacher_changes(old,new)
        by={r["teacher"]:r for r in x["teachers"]}
        self.assertEqual(by["B"]["added_duties"][0]["slot"],"1/2")
        self.assertEqual(by["B"]["added_duties"][0]["wait"],1)
        self.assertEqual(by["A"]["removed_duties"][0]["place"],"A")

    def test_ui_structure_and_language(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        self.assertNotIn("mainTab==='constraints'",h)
        self.assertNotIn("mainTab==='stats'",h)
        for phrase in [
            "Reguły / zasady przydziału",
            "Statystyki nauczycieli",
            "Nauczyciele",
            "Panel nauczyciela",
            "Warianty / pliki • import / eksport",
            "Ustal bieżący plan jako punkt odniesienia dla zastępstw",
            "Kolejność jest zapisywana automatycznie",
            "constraint-disabled",
            "added_duties",
            "width:76px",
            "width:44px",
            "skali 1–10",
        ]:
            self.assertIn(phrase,h)
        self.assertNotIn(">Reguły / constrainty<",h)
        self.assertNotIn(">Statystyki</button>",h)

    def test_teacher_import_classification(self):
        low={"Pn":{"1":[{"class":"1a","subject":"matematyka","room":"122"}]}}
        self.assertIn(app._classify_new_teacher(low),("1-3","school"))
        wf={"Pn":{"1":[{"class":"4a","subject":"WF","room":"sala"}],"2":[{"class":"5a","subject":"WF","room":"sala"}]}}
        self.assertEqual(app._classify_new_teacher(wf),"wf")

if __name__=="__main__":
    unittest.main(verbosity=2)
