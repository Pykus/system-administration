
import sys, json
from pathlib import Path
root=Path(r"C:\DutySolverDemo\dyzury-v5.15-ortools")
sys.path.insert(0,str(root))
import app
from solver_ortools import solve_positions_ortools

ok=[]
def check(name, cond, detail=""):
    if not cond: raise AssertionError(name+": "+str(detail))
    ok.append(name)

s=app.load_state()
one13=next(n for n in app.ALL if app.GROUP.get(n)=="1-3")
check("school_pool_allows_manual_13", one13 in app._school_pool([one13]))

# Empty pools must remain intentionally empty.
e=app.ensure_state_schema({**s,"enabled_teachers_13":[],"enabled_teachers_school":[]})
check("empty_pool_13_preserved", e.get("enabled_teachers_13")==[])
check("empty_pool_school_preserved", e.get("enabled_teachers_school")==[])

# Frozen pools produce no repair candidate that expands a pool.
base={"school13":{"diagnostics":{"unresolved":[]}},"school":{"diagnostics":{"unresolved":[]}}}
f=app.ensure_state_schema({**s,"freeze_pool_13":True,"freeze_pool_school":True})
c=app._repair_candidates_v2(f,[],[],base)
check("frozen_pool_no_add_candidates", not any(x["token"].startswith(("add13:","add13group:","addschool:")) for x in c),
      [x["token"] for x in c if x["token"].startswith("add")][:10])

# Exclusions and selected pool are hard even for a required assignment.
teacher=next(iter(app.ALL))
br=app.SEED["breaks"][0]
pos=[{"day":br["day"],"abbr":br["abbr"],"slot":br["label"],"location":"TEST","break":br,"required_teacher":teacher}]
st=app.ensure_state_schema({**s,"excluded_teachers":[teacher]})
a,w,m,meta=solve_positions_ortools(st,"szkoła",pos,{teacher},[],None,app.SEED,app.GROUP,coverage_only=True,repair_mode=False)
check("excluded_required_is_unfilled", len(m)==1)
reasons=meta.get("diagnostics",{}).get("hard_rejections",[])
check("excluded_reason_visible", any("wykluczony ze wszystkich" in str(x) for x in reasons), reasons)

st2=app.ensure_state_schema({**s,"excluded_teachers":[]})
a,w,m,meta=solve_positions_ortools(st2,"szkoła",pos,set(),[],None,app.SEED,app.GROUP,coverage_only=True,repair_mode=False)
check("outside_pool_required_is_unfilled", len(m)==1)
reasons=meta.get("diagnostics",{}).get("hard_rejections",[])
check("outside_pool_reason_visible", any("poza wybraną pulą" in str(x) for x in reasons), reasons)

# Off-day sentinel 9 is classified separately and never summed as 9 lessons.
impact=app._impact_summary({"teachers":[],"positions_changed":0,"teachers_changed":0},
    [{"teacher":teacher,"wait":9,"wait_kind":"offday","abbr":"Pn","slot":"1/2","scope":"szkoła"}])
row=impact["waiting_teachers"][0]
check("offday_not_nine_lessons", row["wait_lessons_total"]==0 and row["offday_duties"]==1, row)

print(json.dumps({"passed":len(ok),"tests":ok},ensure_ascii=False,indent=2))
