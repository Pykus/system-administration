import copy,time,unittest
from pathlib import Path
import app
import solver_ortools as so

ROOT=Path(__file__).parent

class TestV510(unittest.TestCase):
    def test_version(self):
        self.assertEqual(app.app.version,"5.10")
        self.assertEqual(app.health()["version"],"5.10")

    def test_consecutive_default(self):
        st=app.ensure_state_schema({})
        cm={x["key"]:x for x in st["global_constraints"]}
        self.assertIn("max_consecutive_duties",cm)
        self.assertTrue(cm["max_consecutive_duties"]["enabled"])
        self.assertEqual(cm["max_consecutive_duties"]["value"],1)

    def test_repair_candidates_include_staffing_reduction(self):
        st=app.ensure_state_schema({"min_people_13":{"Pn|1/2":2}})
        baseline={"school13":{"diagnostics":{"unresolved":[{"position":{"abbr":"Pn","slot":"1/2"}}]}},
                  "school":{"diagnostics":{"unresolved":[]}}}
        cs=app._repair_candidates_v2(st,[],[],baseline)
        self.assertTrue(any(x["token"]=="m13:Pn|1/2|1" for x in cs))

    def test_avoid_wait_ranked_after_organizational_changes(self):
        st=app.load_state()
        # Ensure an artificial unresolved 2-person slot gives a structural option.
        st["min_people_13"]["Pn|1/2"]=2
        baseline={"school13":{"diagnostics":{"unresolved":[{"position":{"abbr":"Pn","slot":"1/2"}}]}},
                  "school":{"diagnostics":{"unresolved":[]}}}
        cs=app._repair_candidates_v2(st,st.get("enabled_teachers_13",[]),st.get("enabled_teachers_school",[]),baseline)
        m=next(x for x in cs if x["token"]=="m13:Pn|1/2|1")
        waits=[x for x in cs if x["token"]=="gsoft:avoid_wait"]
        if waits:
            self.assertGreater(waits[0]["human_cost"],m["human_cost"])
            self.assertTrue(waits[0]["comfort_cost"])

    def test_progressive_apply_tokens(self):
        st=app.ensure_state_schema({"min_people_13":{"Pn|1/2":2}})
        ns,p13,ps=app._apply_repair_tokens_v2(st,[],[],["m13:Pn|1/2|1","gval:max_consecutive_duties:2"])
        self.assertEqual(ns["min_people_13"]["Pn|1/2"],1)
        cm={x["key"]:x for x in ns["global_constraints"]}
        self.assertEqual(cm["max_consecutive_duties"]["value"],2)

    def test_consecutive_constraint_is_enforced(self):
        seed={
            "teachers":[{"name":"T","lessons":{"Pn":{}}}],
            "breaks":[
                {"day":"Poniedziałek","abbr":"Pn","label":"1/2","prev":1,"next":2,"minutes":5,"time":""},
                {"day":"Poniedziałek","abbr":"Pn","label":"2/3","prev":2,"next":3,"minutes":5,"time":""},
            ],
        }
        positions=[{"day":"Poniedziałek","abbr":"Pn","slot":b["label"],"location":"L","break":b} for b in seed["breaks"]]
        base={"global_constraints":[
            {"key":"no_lesson_overlap","enabled":True,"kind":"hard","priority":5},
            {"key":"one_place_per_slot","enabled":True,"kind":"hard","priority":5},
            {"key":"cross_scope_conflict","enabled":True,"kind":"hard","priority":5},
            {"key":"manual_blocks","enabled":True,"kind":"hard","priority":5},
            {"key":"max_consecutive_duties","enabled":True,"kind":"hard","priority":4,"value":1},
        ],"individual_constraints":[],"manual_blocks":{},"preference_grid":{}}
        a,_,missing,_=so.solve_positions_ortools(base,"szkoła",positions,{"T"},[],None,seed,{"T":"school"},coverage_only=True)
        self.assertEqual(len(missing),1)
        base["global_constraints"][-1]["value"]=2
        a,_,missing,_=so.solve_positions_ortools(base,"szkoła",positions,{"T"},[],None,seed,{"T":"school"},coverage_only=True)
        self.assertEqual(len(missing),0)

    def test_ui_progress_contract(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for phrase in ("Generator wariantów naprawczych","Pauza","Wznów","estimated_total","max_consecutive_duties","0 — brak stanowiska"):
            self.assertIn(phrase,h)

if __name__=="__main__":
    unittest.main(verbosity=2)
