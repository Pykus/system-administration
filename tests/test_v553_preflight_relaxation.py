import copy
import inspect
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app


def hard_state(keys):
    s=copy.deepcopy(app.load_state())
    by={r.get("key"):r for r in s.get("global_constraints",[])}
    for key in keys:
        if key not in by:
            s.setdefault("global_constraints",[]).append({"key":key,"label":key})
            by[key]=s["global_constraints"][-1]
        by[key].update({"enabled":True,"kind":"hard","priority":5})
    return s


class TestPreflightRelaxationPolicy553(unittest.TestCase):
    def test_system_and_offday_rules_are_never_auto_relaxed(self):
        s=hard_state(["offday_duty","no_lesson_overlap"])
        self.assertFalse(app._preflight_soften_global_v553(s,"offday_duty"))
        self.assertFalse(app._preflight_soften_global_v553(s,"no_lesson_overlap"))
        self.assertEqual(app._global_row(s,"offday_duty")["kind"],"hard")
        self.assertEqual(app._global_row(s,"no_lesson_overlap")["kind"],"hard")

    def test_comfort_hard_becomes_highest_soft(self):
        s=hard_state(["after_last_long"])
        self.assertTrue(app._preflight_soften_global_v553(s,"after_last_long"))
        r=app._global_row(s,"after_last_long")
        self.assertEqual(r["kind"],"soft")
        self.assertEqual(r["priority"],5)

    def test_constraint_shortage_never_creates_staffing_reduction_candidate(self):
        src=inspect.getsource(app._slot_feasibility_v524)
        self.assertNotIn('f"m13:',src)
        self.assertNotIn('f"ms:',src)
        self.assertIn("shortage never reduces required staffing",src)


class TestMinimalCostCombination553(unittest.TestCase):
    def setUp(self):
        self.orig=app._preflight_effective_shortages_v553

    def tearDown(self):
        app._preflight_effective_shortages_v553=self.orig

    def test_synergistic_hard_rules_are_found_as_a_combination(self):
        s=hard_state(["before_first_long","after_last_long","avoid_wait"])
        def fake(st,e13,es):
            b=app._global_row(st,"before_first_long")
            a=app._global_row(st,"after_last_long")
            solved=(app.normalize_kind(b.get("kind"))=="soft" and
                    app.normalize_kind(a.get("kind"))=="soft")
            score=0 if solved else 1
            rows=[] if solved else [{"scope":"school","abbr":"Pn","slot":"3/4",
                                      "required":1,"effective_possible":0,
                                      "effective_shortage":1}]
            return score,rows,{"problems":rows}
        app._preflight_effective_shortages_v553=fake
        changes=app._auto_relax_edge_constraints_v553(s,[],[])
        keys={x["key"] for x in changes}
        self.assertEqual(keys,{"before_first_long","after_last_long"})
        self.assertEqual(app._global_row(s,"before_first_long")["kind"],"soft")
        self.assertEqual(app._global_row(s,"after_last_long")["kind"],"soft")
        self.assertEqual(app._global_row(s,"avoid_wait")["kind"],"hard")
    def test_cheaper_rule_is_selected_when_either_one_would_fix_shortage(self):
        s=hard_state(["after_last_long","avoid_wait"])
        def fake(st,e13,es):
            after_soft=app.normalize_kind(app._global_row(st,"after_last_long").get("kind"))=="soft"
            wait_soft=app.normalize_kind(app._global_row(st,"avoid_wait").get("kind"))=="soft"
            solved=after_soft or wait_soft
            score=0 if solved else 1
            rows=[] if solved else [{"scope":"school","abbr":"Pn","slot":"3/4",
                                      "required":1,"effective_possible":0,
                                      "effective_shortage":1}]
            return score,rows,{"problems":rows}
        app._preflight_effective_shortages_v553=fake
        changes=app._auto_relax_edge_constraints_v553(s,[],[])
        self.assertEqual([x["key"] for x in changes],["after_last_long"])
        self.assertEqual(app._global_row(s,"avoid_wait")["kind"],"hard")


class TestIndividualDirectional553(unittest.TestCase):
    def setUp(self):
        self.orig=app._preflight_effective_shortages_v553

    def tearDown(self):
        app._preflight_effective_shortages_v553=self.orig

    def test_impossible_individual_after_last_is_softened_only_for_that_teacher(self):
        s=copy.deepcopy(app.load_state())
        teacher=next(iter(sorted(app.ALL)))
        s["individual_constraints"]=[
            {"id":"edge1","teacher":teacher,"scope":"szkoła","rule":"no_after_last_lesson",
             "kind":"hard","priority":5,"enabled":True,"day":"","slot":"","location":""},
            {"id":"keep1","teacher":teacher,"scope":"szkoła","rule":"unavailable",
             "kind":"hard","priority":5,"enabled":True,"day":"Wt","slot":"1/2","location":""},
        ]
        def fake(st,e13,es):
            edge=next(r for r in st["individual_constraints"] if r["id"]=="edge1")
            solved=app.normalize_kind(edge.get("kind"))=="soft"
            rows=[] if solved else [{"scope":"school","abbr":"Pn","slot":"3/4",
                                      "required":1,"effective_possible":0,
                                      "effective_shortage":1}]
            return (0 if solved else 1),rows,{"problems":rows}
        app._preflight_effective_shortages_v553=fake
        changes=app._auto_relax_individual_directional_v553(s,[],[])
        self.assertEqual([x["id"] for x in changes],["edge1"])
        edge=next(r for r in s["individual_constraints"] if r["id"]=="edge1")
        keep=next(r for r in s["individual_constraints"] if r["id"]=="keep1")
        self.assertEqual((edge["kind"],edge["priority"]),("soft",5))
        self.assertEqual(keep["kind"],"hard")


class TestNumericCapacity553(unittest.TestCase):
    def test_human_capacity_hard_limit_is_never_auto_softened(self):
        s=hard_state(["max_week"])
        r=app._global_row(s,"max_week")
        r["value"]=2
        changes=app._auto_relax_numeric_v553(s,[{
            "key":"max_week","label":"Maks. tygodniowo",
            "before":2,"after":4,"reason":"minimalna pojemność"
        }])
        self.assertEqual(changes,[])
        self.assertEqual(r["kind"],"hard")
        self.assertEqual(r["value"],2)
        self.assertIn("max_week",app.NEVER_AUTO_RELAX_KEYS)


class TestPreflightEndpointPersistence553(unittest.TestCase):
    def setUp(self):
        self.orig_path=app.STATE_PATH
        self.orig_staff=app._apply_timetable_staffing
        self.orig_slot=app._slot_feasibility_v524
        self.orig_pre=app._repair_preflight_v520
        self.orig_consecutive=app._auto_relax_consecutive_v553
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"state.json"
        s=hard_state(["after_last_long"])
        self.path.write_text(json.dumps(s,ensure_ascii=False),encoding="utf-8")
        app.STATE_PATH=self.path

    def tearDown(self):
        app.STATE_PATH=self.orig_path
        app._apply_timetable_staffing=self.orig_staff
        app._slot_feasibility_v524=self.orig_slot
        app._repair_preflight_v520=self.orig_pre
        app._auto_relax_consecutive_v553=self.orig_consecutive
        self.tmp.cleanup()

    def test_endpoint_persists_only_proven_rule_softening(self):
        app._apply_timetable_staffing=lambda s: []
        app._auto_relax_consecutive_v553=lambda s,e13,es: []
        def slot(st,e13,es):
            soft=app.normalize_kind(app._global_row(st,"after_last_long").get("kind"))=="soft"
            if soft:
                return {"problems":[],"candidates":[]}
            return {"problems":[{"scope":"school","abbr":"Pn","slot":"3/4",
                                  "required":1,"possible_without_relax":0,
                                  "possible_with_pool_expansion":0,
                                  "admin_lock_blocker":False}],
                    "candidates":[]}
        app._slot_feasibility_v524=slot
        app._repair_preflight_v520=lambda st,e13,es,auto=None: {
            "ok":True,"blocking":False,"recommendations":[],"alternatives":[],
            "checks":[],"slot_problems":app._slot_feasibility_v524(st,e13,es)["problems"],
            "obvious_candidates":[],"auto_staffing_changes":list(auto or []),
            "required":{"school13":0,"school":1},"pool_sizes":{"school13":0,"school":1}
        }
        out=app.repair_preflight({})
        self.assertEqual(len(out["auto_constraint_relaxations"]),1)
        self.assertEqual(out["auto_constraint_relaxations"][0]["key"],"after_last_long")
        self.assertTrue(out["constraint_relaxation_policy"]["staffing_reduction_allowed_only_for_inactive_timetable_zone"])
        saved=json.loads(self.path.read_text(encoding="utf-8"))
        rr=next(r for r in saved["global_constraints"] if r.get("key")=="after_last_long")
        self.assertEqual(rr["kind"],"soft")
        self.assertEqual(rr["priority"],5)


if __name__=="__main__":
    unittest.main()
