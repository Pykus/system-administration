from pathlib import Path
import json

ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools")

# One-time migration of the current broken configuration only.
state_path=ROOT/"data"/"state.json"
st=json.loads(state_path.read_text(encoding="utf-8"))
st["version"]="5.9"
migrated=False
for row in st.get("global_constraints",[]):
    if row.get("key")=="workload_fairness" and row.get("enabled") and str(row.get("kind")).lower()=="hard":
        row["kind"]="soft"
        migrated=True
state_path.write_text(json.dumps(st,ensure_ascii=False,indent=2),encoding="utf-8")

# Extend regression tests with functional teacher-portal lock synchronization.
p=ROOT/"test_v59.py"
s=p.read_text(encoding="utf-8")
if "test_portal_lock_is_functional" not in s:
    s=s.replace("import unittest\n", "import unittest\nimport copy\n")
    anchor='''    def test_teacher_portal_lock_contract(self):
'''
    test='''    def test_portal_lock_is_functional(self):
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

'''
    s=s.replace(anchor,test+anchor)
p.write_text(s,encoding="utf-8")

notes=ROOT/"RELEASE-NOTES-v5.9.md"
txt=notes.read_text(encoding="utf-8")
txt += f"""
## Audyt konfiguracji przed wdrożeniem
- Zapisany plan: 23 nauczycieli z 0 dyżurów, maksimum 10.
- Symulacja z workload_fairness=MUSI BYĆ: 1–3 = 0/95; reguła faktycznie blokowała rozwiązanie.
- Symulacja z workload_fairness=ZALECANE: 1–3 = 91/95; liczba nauczycieli z 0 dyżurów w nowym wyniku spada do 2.
- Dlatego wykonano jednorazową migrację bieżącego workload_fairness z MUSI BYĆ na ZALECANE: {migrated}.
- Pozostałe 4 braki 1–3 blokuje twarda reguła dodatkowego oczekiwania; nie zmieniono jej automatycznie.
- Długie przerwy jako MUSI BYĆ powodują 3 braki w całej szkole; po zmianie tych reguł na ZALECANE symulacja daje 354/354. Reguły są od v5.9 normalnie edytowalne.
"""
notes.write_text(txt,encoding="utf-8")
print("POST_PATCH_V59_OK workload_migrated=",migrated)
