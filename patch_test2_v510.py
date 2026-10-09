from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v5.10-ortools\test_v510.py")
s=p.read_text(encoding="utf-8")
if "test_consecutive_constraint_is_enforced" not in s:
    s=s.replace("import app\n","import app\nimport solver_ortools as so\n")
    anchor="    def test_ui_progress_contract(self):\n"
    test=r'''    def test_consecutive_constraint_is_enforced(self):
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

'''
    s=s.replace(anchor,test+anchor)
p.write_text(s,encoding="utf-8")
q=Path(r"C:\DutySolverDemo\dyzury-v5.10-ortools\check_v510.py")
q.write_text("""from pathlib import Path
import re
root=Path(r'C:\\Users\\Admin\\Production\\dyzury-v5.10-ortools')
h=(root/'static'/'index.html').read_text(encoding='utf-8')
scripts=re.findall(r'<script(?:\\s[^>]*)?>(.*?)</script>',h,re.S|re.I)
(root/'_ui_check_v510.js').write_text(scripts[-1],encoding='utf-8')
for x in ['Dyżury v5.10','Generator wariantów naprawczych','Pauza','Wznów','max_consecutive_duties']:
    assert x in h,x
print('UI_MARKERS_OK',len(scripts))
""",encoding="utf-8")
print("TESTS_PATCHED")
