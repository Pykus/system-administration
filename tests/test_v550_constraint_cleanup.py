import copy,json,tempfile,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app, solver_ortools as so

REMOVED={"adjacent_lesson","long_break_penalty","workload_fairness"}

class TestConstraintCleanup550(unittest.TestCase):
    def test_removed_constraints_are_tombstoned_and_purged(self):
        s=app.load_state()
        legacy=[{"key":k,"label":k,"enabled":True,"kind":"soft","priority":3,"value":15 if k=="long_break_penalty" else None} for k in REMOVED]
        s["global_constraints"].extend(copy.deepcopy(legacy))
        n=next(iter(sorted(app.ALL)))
        s.setdefault("teacher_relax_order",{})[n]=["adjacent_lesson","avoid_wait"]
        s.setdefault("teacher_relaxed_rules",{})[n]=["adjacent_lesson"]
        s.setdefault("repair_guidance",{})["accepted_compromises"]=["adjacent_lesson","long_break_penalty"]
        s.setdefault("solver_weight_overrides",{}).update({k:123 for k in REMOVED})
        s["variants"]=[{"id":"legacy","global_constraints":copy.deepcopy(legacy),"settings":{"global_constraints":copy.deepcopy(legacy)}}]
        z=app.ensure_state_schema(s)
        keys={r.get("key") for r in z.get("global_constraints",[])}
        self.assertTrue(REMOVED.isdisjoint(keys),keys)
        self.assertNotIn("adjacent_lesson",z["teacher_relax_order"][n])
        self.assertNotIn("adjacent_lesson",z["teacher_relaxed_rules"][n])
        self.assertTrue(REMOVED.isdisjoint(set(z["repair_guidance"]["accepted_compromises"])))
        self.assertTrue(REMOVED.isdisjoint(set(z["solver_weight_overrides"])))
        self.assertTrue(REMOVED.isdisjoint({r.get("key") for r in z["variants"][0]["global_constraints"]}))
        self.assertTrue(REMOVED.isdisjoint({r.get("key") for r in z["variants"][0]["settings"]["global_constraints"]}))

    def test_single_fairness_constraint_uses_manual_factor_without_second_toggle(self):
        s=app.ensure_state_schema(app.load_state())
        keys=[r.get("key") for r in s["global_constraints"]]
        self.assertIn("lesson_load_fairness",keys)
        self.assertNotIn("workload_fairness",keys)
        row=next(r for r in s["global_constraints"] if r.get("key")=="lesson_load_fairness")
        self.assertIn("obciążenia dydaktycznego",row.get("label","").lower())
        legacy=copy.deepcopy(s)
        lesson=next(r for r in legacy["global_constraints"] if r.get("key")=="lesson_load_fairness")
        lesson.update({"enabled":True,"kind":"soft","priority":3})
        legacy["global_constraints"].append({"key":"workload_fairness","enabled":True,"kind":"soft","priority":5})
        merged=app.ensure_state_schema(legacy)
        merged_row=next(r for r in merged["global_constraints"] if r.get("key")=="lesson_load_fairness")
        self.assertTrue(merged_row["enabled"])
        self.assertEqual(merged_row["kind"],"soft")
        self.assertEqual(merged_row["priority"],5)
        src=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")
        self.assertNotIn("manual_fair=",src)
        self.assertIn('manual=max(0.1,float(state.get("teacher_workload"',src)
        self.assertIn("raw=float(lessons)*manual",src)

    def test_forbid_preferences_are_migrated_to_avoid_and_api_accepts_only_three_states(self):
        s=app.load_state(); n=next(iter(sorted(app.ALL)))
        s.setdefault("preference_grid",{})[n]={"Pn|1/2":"forbid","Wt|1/2":"prefer","Śr|1/2":"neutral"}
        z=app.ensure_state_schema(s)
        self.assertEqual(z["preference_grid"][n].get("Pn|1/2"),"avoid")
        self.assertEqual(z["preference_grid"][n].get("Wt|1/2"),"prefer")
        self.assertNotIn("Śr|1/2",z["preference_grid"][n])
        src=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")
        self.assertNotIn('value=="forbid"',src)
        for f in [ROOT/"static"/"index.html",ROOT/"static"/"teacher.html"]:
            txt=f.read_text(encoding="utf-8")
            self.assertNotIn('value="forbid"',txt)
            self.assertNotIn("zabroniona",txt.lower())

    def test_zone_rule_has_human_name_and_numeric_location_fallback(self):
        s=app.ensure_state_schema(app.load_state())
        row=next(r for r in s["global_constraints"] if r.get("key")=="zone_transition_penalty")
        self.assertEqual(row.get("label"),"Preferuj dyżur blisko sali lekcyjnej")
        tby={"A":{"lessons":{"Pn":{"1":[{"room":"218"}]}}}}
        br={"abbr":"Pn","prev":1,"next":2}
        self.assertEqual(so._zone_distance({"location_zones":{}},tby,"A","szkoła",br,"111"),1)
        self.assertEqual(so._zone_distance({"location_zones":{}},tby,"A","szkoła",br,"217"),0)

    def test_admin_manual_blocks_remain_hard_system_constraint(self):
        s=app.ensure_state_schema(app.load_state())
        r=next(x for x in s["global_constraints"] if x.get("key")=="manual_blocks")
        self.assertTrue(r.get("enabled"))
        self.assertEqual(r.get("kind"),"hard")
        self.assertEqual(int(r.get("priority")),5)

    def test_active_sources_have_no_removed_solver_or_ui_logic(self):
        appsrc=(ROOT/"app.py").read_text(encoding="utf-8")
        solver=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")
        html=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        teacher=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")
        for key in REMOVED:
            self.assertNotIn(key,solver)
            self.assertNotIn(key,html)
            self.assertNotIn(key,teacher)
        # Backend may mention removed keys only in migration code; they must not exist in solver/UI.
        self.assertEqual(appsrc.count("adjacent_lesson"),1)
        self.assertEqual(appsrc.count("long_break_penalty"),1)
        self.assertLessEqual(appsrc.count("workload_fairness"),2)

if __name__=="__main__": unittest.main()
