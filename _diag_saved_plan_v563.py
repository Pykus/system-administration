import json,sys
sys.path.insert(0,r"C:\DutySolverDemo\dyzury-v5.63-ortools")
import app
s=app.load_state()
a13=[]
for r in s.get("last_13_assignments",[]) or []:
    for a in r.get("assignments",[]) or []:
        if a.get("teacher"): a13.append({**a,"abbr":r.get("abbr"),"slot":r.get("label")})
ev={"school13":{"assignments":a13,"waits":[]},"school":{"assignments":s.get("school_assignments",[]) or [],"waits":[]}}
m=app._draft_metrics_v527(ev,[])
print(json.dumps({k:m.get(k) for k in ("after_last_long","before_first_long","wait_lessons_total","consecutive_pairs","home_group_foreign_13","home_group_foreign_13_wf")},ensure_ascii=False,indent=2))
