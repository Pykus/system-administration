import copy, json, tempfile, unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

REMOVED="day_span_penalty"

class TestRemovedDaySpan549(unittest.TestCase):
    def test_schema_purges_removed_constraint_everywhere(self):
        teacher=next(iter(sorted(app.ALL)))
        s=app.load_state()
        # Reinsert legacy data deliberately, regardless of candidate's current migration.
        legacy={"key":REMOVED,"label":"Unikaj wydłużania dnia pracy","enabled":True,"kind":"soft","priority":2}
        s["global_constraints"].append(copy.deepcopy(legacy))
        s.setdefault("teacher_relax_order",{})[teacher]=[REMOVED,"avoid_wait"]
        s.setdefault("teacher_relaxed_rules",{})[teacher]=[REMOVED,"after_last_short"]
        s.setdefault("repair_guidance",{})["accepted_compromises"]=[REMOVED,"after_last_long"]
        s.setdefault("solver_weight_overrides",{})[REMOVED]=123
        s["variants"]=[{
            "id":"legacy-v","name":"legacy","global_constraints":[copy.deepcopy(legacy)],
            "settings":{"global_constraints":[copy.deepcopy(legacy)]},
            "school_assignments":[],"assignments_13":[]
        }]
        z=app.ensure_state_schema(s)
        self.assertNotIn(REMOVED,[r.get("key") for r in z.get("global_constraints",[])])
        self.assertNotIn(REMOVED,z.get("teacher_relax_order",{}).get(teacher,[]))
        self.assertNotIn(REMOVED,z.get("teacher_relaxed_rules",{}).get(teacher,[]))
        self.assertNotIn(REMOVED,z.get("repair_guidance",{}).get("accepted_compromises",[]))
        self.assertNotIn(REMOVED,z.get("solver_weight_overrides",{}))
        v=z["variants"][0]
        self.assertNotIn(REMOVED,[r.get("key") for r in v.get("global_constraints",[])])
        self.assertNotIn(REMOVED,[r.get("key") for r in v.get("settings",{}).get("global_constraints",[])])

    def test_normalize_rejects_legacy_constraint(self):
        rows=app.normalize_constraint_rows([
            {"key":"after_last_short","enabled":True,"kind":"soft","priority":1},
            {"key":REMOVED,"enabled":True,"kind":"hard","priority":5}
        ])
        self.assertNotIn(REMOVED,[r.get("key") for r in rows])

    def test_saved_profiles_are_migrated_and_persisted(self):
        old=app.SETTINGS_PROFILES_PATH
        tmp=tempfile.TemporaryDirectory()
        try:
            p=Path(tmp.name)/"settings_profiles.json"
            p.write_text(json.dumps({
                "profiles":[{"id":"p","name":"legacy","settings":{"global_constraints":[
                    {"key":REMOVED,"enabled":True,"kind":"soft","priority":2},
                    {"key":"after_last_short","enabled":True,"kind":"soft","priority":1}
                ]}}],
                "default_id":"p"
            },ensure_ascii=False),encoding="utf-8")
            app.SETTINGS_PROFILES_PATH=p
            raw=app._load_settings_profiles()
            keys=[r.get("key") for r in raw["profiles"][0]["settings"]["global_constraints"]]
            self.assertNotIn(REMOVED,keys)
            persisted=json.loads(p.read_text(encoding="utf-8"))
            keys2=[r.get("key") for r in persisted["profiles"][0]["settings"]["global_constraints"]]
            self.assertNotIn(REMOVED,keys2)
        finally:
            app.SETTINGS_PROFILES_PATH=old
            tmp.cleanup()

    def test_solver_and_interfaces_have_no_day_span_logic(self):
        solver=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")
        html=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        teacher=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")
        appsrc=(ROOT/"app.py").read_text(encoding="utf-8")
        self.assertNotIn(REMOVED,solver)
        self.assertNotIn("_day_span_distance",solver)
        self.assertNotIn(REMOVED,html)
        self.assertNotIn("Unikaj wydłużania dnia pracy",html)
        self.assertNotIn(REMOVED,teacher)
        # One backend occurrence is intentionally retained as a tombstone for migration.
        self.assertEqual(appsrc.count(REMOVED),1)
        self.assertNotIn("Unikaj wydłużania dnia pracy",appsrc)

    def test_teacher_relax_catalog_no_longer_contains_constraint(self):
        self.assertNotIn(REMOVED,[x.get("key") for x in app.TEACHER_RELAX_CATALOG])

if __name__=="__main__":
    unittest.main()
