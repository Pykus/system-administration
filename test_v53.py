import unittest
from copy import deepcopy

import app
from solver_ortools import solve_positions_ortools

def base_state():
    return {
        "global_constraints": [
            {"key":"preference_grid","enabled":True,"kind":"soft","priority":3},
            {"key":"workload_fairness","enabled":False,"kind":"soft","priority":2},
        ],
        "individual_constraints": [],
        "manual_blocks": {},
        "preference_grid": {},
        "teacher_workload": {"T1":1.0,"T2":1.0},
        "location_zones": {},
        "solver_seed": 12345,
        "deterministic_mode": True,
    }

def tiny_seed():
    teachers=[
        {"name":"T1","lessons":{"Pn":{}}},
        {"name":"T2","lessons":{"Pn":{}}},
    ]
    breaks=[]
    for i,label in enumerate(["1/2","2/3","3/4"],1):
        breaks.append({"day":"Poniedziałek","abbr":"Pn","label":label,
                       "prev":i,"next":i+1,"minutes":10,"time":""})
    return {"teachers":teachers,"breaks":breaks}

def positions(seed):
    return [{"day":"Poniedziałek","abbr":"Pn","slot":b["label"],
             "location":"L","break":b} for b in seed["breaks"]]

class TestSchema(unittest.TestCase):
    def test_v53_schema_defaults(self):
        s=app.ensure_state_schema({})
        for key in ["teacher_workload","preference_grid","location_zones",
                    "locked_assignments","absent_teachers","substitution_history"]:
            self.assertIn(key,s)
        keys={x["key"] for x in s["global_constraints"]}
        for key in ["workload_fairness","preference_grid",
                    "day_span_penalty","zone_transition_penalty"]:
            self.assertIn(key,keys)

    def test_lock_lookup(self):
        s={"locked_assignments":[{"scope":"szkoła","abbr":"Pn","slot":"1/2",
                                  "location":"15","teacher":"T1"}]}
        self.assertEqual(app.locked_teacher(s,"szkoła","Pn","1/2","15"),"T1")
        self.assertIsNone(app.locked_teacher(s,"1–3","Pn","1/2","A"))

class TestSolverAdvanced(unittest.TestCase):
    def solve(self,state,pos=None,preserve=None,repair=False):
        seed=tiny_seed()
        return solve_positions_ortools(
            state,"szkoła",pos or positions(seed),{"T1","T2"},[],preserve,
            seed,{"T1":"school","T2":"school"},repair_mode=repair
        )

    def test_preference_grid_prefers_teacher(self):
        s=base_state()
        s["preference_grid"]={"T1":{"Pn|1/2":"prefer"},"T2":{"Pn|1/2":"avoid"}}
        seed=tiny_seed()
        a,_,_,_=self.solve(s,[positions(seed)[0]])
        self.assertEqual(a[0]["teacher"],"T1")

    def test_workload_fairness_uses_factor(self):
        s=base_state()
        s["global_constraints"][1]["enabled"]=True
        s["teacher_workload"]={"T1":2.0,"T2":1.0}
        a,_,_,_=self.solve(s)
        counts={"T1":0,"T2":0}
        for x in a: counts[x["teacher"]]+=1
        self.assertEqual(counts,{"T1":2,"T2":1})

    def test_mpp_preserves_reference(self):
        s=base_state()
        p=positions(tiny_seed())
        preserve={("Pn",x["slot"],"L"):"T1" for x in p}
        a,_,_,meta=self.solve(s,p,preserve,True)
        self.assertTrue(meta["diagnostics"]["mpp_optimized"])
        self.assertEqual(meta["diagnostics"]["stability"]["changed"],0)
        self.assertTrue(all(x["teacher"]=="T1" for x in a))

    def test_absence_forces_minimal_change(self):
        s=base_state(); s["active_absences"]=["T1"]
        p=[positions(tiny_seed())[0]]
        preserve={("Pn","1/2","L"):"T1"}
        a,_,_,meta=self.solve(s,p,preserve,True)
        self.assertEqual(a[0]["teacher"],"T2")
        self.assertEqual(meta["diagnostics"]["stability"]["changed"],1)

    def test_deterministic_repeat(self):
        s=base_state()
        a1,_,_,m1=self.solve(deepcopy(s))
        a2,_,_,m2=self.solve(deepcopy(s))
        self.assertEqual([x["teacher"] for x in a1],[x["teacher"] for x in a2])
        self.assertTrue(m1["diagnostics"]["deterministic_mode"])
        self.assertEqual(m1["diagnostics"]["solver_seed"],12345)

class TestUIAndAPI(unittest.TestCase):
    def test_ui_surfaces(self):
        text=open("static/index.html",encoding="utf-8").read()
        for phrase in ["Planowanie zaawansowane","Wylicz minimalne zastępstwa",
                       "Porównanie wariantów A / B / C","Zamroź"]:
            self.assertIn(phrase,text)

    def test_operational_routes_exist(self):
        paths={r.path for r in app.app.routes}
        self.assertIn("/api/publish",paths)
        self.assertIn("/api/operations/save",paths)

    def test_health_version(self):
        self.assertEqual(app.health()["version"],"5.6")

if __name__=="__main__":
    unittest.main(verbosity=2)
