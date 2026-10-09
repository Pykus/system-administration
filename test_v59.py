import unittest
import copy
from pathlib import Path
import app
from app import _relax,_repair_candidates

ROOT=Path(__file__).parent

class TestV59(unittest.TestCase):
    def test_version(self):
        self.assertEqual(app.app.version,"5.9")
        self.assertEqual(app.health()["version"],"5.9")

    def test_long_edge_constraints_are_editable(self):
        st=app.ensure_state_schema({"global_constraints":[
            {"key":"before_first_long","label":"x","scope":"oba","enabled":False,"kind":"soft","priority":2},
            {"key":"after_last_long","label":"y","scope":"oba","enabled":False,"kind":"soft","priority":2},
        ]})
        cm={x["key"]:x for x in st["global_constraints"]}
        self.assertFalse(cm["before_first_long"]["enabled"])
        self.assertEqual(cm["before_first_long"]["kind"],"soft")
        self.assertFalse(cm["after_last_long"]["enabled"])
        self.assertEqual(cm["after_last_long"]["kind"],"soft")

    def test_individual_edge_names_are_explicit(self):
        st=app.ensure_state_schema({"individual_constraints":[
            {"id":"a","teacher":"T","rule":"no_before_lesson","kind":"hard","enabled":True},
            {"id":"b","teacher":"T","rule":"no_after_lesson","kind":"hard","enabled":True},
        ]})
        rules={x["rule"] for x in st["individual_constraints"]}
        self.assertIn("no_before_first_lesson",rules)
        self.assertIn("no_after_last_lesson",rules)
        self.assertNotIn("no_before_lesson",rules)

    def test_forbidden_teacher_preference_can_be_repair_candidate(self):
        st=app.ensure_state_schema({"global_constraints":[
            {"key":"preference_grid","label":"Preferencje","scope":"oba","enabled":True,"kind":"hard","priority":3},
        ],"preference_grid":{"Jan Kowalski":{"Pn|1/2":"forbid"}}})
        c=_repair_candidates(st)
        token=next(x["token"] for x in c if x["type"]=="teacher_preference")
        out=_relax(st,[token])
        self.assertNotIn("Pn|1/2",out["preference_grid"]["Jan Kowalski"])

    def test_ui_contract(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for phrase in ("Dyżury v5.9","pokaż dyżury","teacherTimelineRows","statsColumnFilters","Ustaw / zmień stały przydział","Preferencje zgłoszone przez nauczycieli"):
            self.assertIn(phrase,h)
        self.assertNotIn("polityka stała",h)
        self.assertNotIn("<div><b>Plan dyżurów</b>",h)

    def test_portal_lock_is_functional(self):
        name,reg=next((n,r) for n,r in app.TEACHER_REGISTRY.items() if r.get("active",True) and r.get("portal_token"))
        fake=app.ensure_state_schema({
            "locked_assignments":[{"scope":"szkoła","abbr":"Pn","slot":"1/2","location":"15","teacher":name}],
            "preference_grid":{name:{"Pn|1/2":"forbid","Wt|2/3":"prefer"}},
        })
        old_load,old_save=app.load_state,app.save_state
        box={}
        app.load_state=lambda: copy.deepcopy(fake)
        app.save_state=lambda x: box.setdefault("state",copy.deepcopy(x))
        try:
            out=app.teacher_portal(reg["portal_token"])
            self.assertEqual(len(out["admin_locks"]),1)
            app.teacher_portal_preferences(reg["portal_token"],{"preferences":{"Pn|1/2":"forbid","Wt|2/3":"avoid"}})
            self.assertNotIn("Pn|1/2",box["state"]["preference_grid"][name])
            self.assertEqual(box["state"]["preference_grid"][name]["Wt|2/3"],"avoid")
        finally:
            app.load_state,app.save_state=old_load,old_save

    def test_teacher_portal_lock_contract(self):
        h=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")
        self.assertIn("stały przydział administratora",h)
        self.assertIn("lockAt(day,slot)",h)
        self.assertIn("disabled",h)

if __name__=="__main__":
    unittest.main(verbosity=2)
