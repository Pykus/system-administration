import copy
import unittest
from pathlib import Path
import app

ROOT=Path(__file__).parent

class TestV57(unittest.TestCase):
    def test_version(self):
        self.assertEqual(app.app.version,"5.7")
        self.assertEqual(app.health()["version"],"5.7")

    def test_school_locations_match_source_plan(self):
        state=app.load_state()
        from_assign={x.get("location") for x in state.get("school_assignments",[]) if x.get("location")}
        self.assertTrue(from_assign)
        self.assertTrue(from_assign.issubset(set(state.get("school_locations",[]))))

    def test_school_staffing_migration_uses_existing_positions(self):
        st=app.ensure_state_schema({"school_assignments":[
            {"day":"Poniedziałek","abbr":"Pn","slot":"1/2","location":"TEST-X","teacher":"A"}
        ],"school_locations":["TEST-X"]})
        self.assertIn("TEST-X",st["school_locations"])
        self.assertEqual(st["min_people_school"]["Pn|1/2|TEST-X"],1)
        self.assertEqual(st["min_people_school"]["Pn|2/3|TEST-X"],0)

    def test_school_position_matrix_controls_solver_positions(self):
        st=app.ensure_state_schema({"school_assignments":[],"school_locations":["TEST-X"],"min_people_school":{}})
        st["min_people_school"]={k:0 for k in st["min_people_school"]}
        st["min_people_school"]["Pn|1/2|TEST-X"]=1
        positions,_,_,_=app._school_positions(st,include_locks=False)
        self.assertEqual(len(positions),1)
        self.assertEqual((positions[0]["abbr"],positions[0]["slot"],positions[0]["location"]),("Pn","1/2","TEST-X"))

    def test_9po_one_person_is_exactly_one_position(self):
        teacher=next(iter(app.ALL))
        st=app.ensure_state_schema({"individual_constraints":[{
            "id":"one-9po","teacher":teacher,"scope":"1–3","rule":"require_slot","kind":"hard",
            "priority":5,"day":"Pn","slot":"9/po","location":"","enabled":True
        }]})
        st["min_people_13"]={b["abbr"]+"|"+b["label"]:2 for b in app.SEED["breaks"]}
        st["min_people_13"]["Pn|9/po"]=1
        positions,_,_=app._diag_positions_13(st)
        rows=[p for p in positions if p["abbr"]=="Pn" and p["slot"]=="9/po"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].get("required_teacher"),teacher)

    def test_ui_v57_contract(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for phrase in [
            "+ nauczyciele ogólni",
            "Minimalna obsada dyżurów – cała szkoła",
            "Przejrzyj wariant",
            "Przegląd wariantu przed zastosowaniem",
            "Lekcji w planie",
            "document.execCommand('copy')",
            "/api/min-people-school",
            "/api/school-locations",
        ]:
            self.assertIn(phrase,h)
        self.assertNotIn("Zastosuj ten wariant",h)

if __name__=="__main__":
    unittest.main(verbosity=2)
