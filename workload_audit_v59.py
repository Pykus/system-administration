import copy,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools")
sys.path.insert(0,str(ROOT))
import app

orig_loader=app.load_state
base=orig_loader()

def count_saved(st):
    c=Counter()
    for r in st.get("last_13_assignments",[]):
        for a in r.get("assignments",[]):
            if a.get("teacher"): c[a["teacher"]]+=1
    for a in st.get("school_assignments",[]):
        if a.get("teacher"): c[a["teacher"]]+=1
    return c

def solve_with(st):
    app.load_state=lambda: copy.deepcopy(st)
    r13=app.solve13({"enabled_teachers":st.get("enabled_teachers_13",[]),"manual_blocks":st.get("manual_blocks",{})})
    rs=app.solve_school({"enabled_teachers":st.get("enabled_teachers_school",[]),"manual_blocks":st.get("manual_blocks",{}),"other_rows_13":r13["rows"]})
    c=Counter()
    for r in r13["rows"]:
        for a in r.get("assignments",[]):
            if a.get("teacher"): c[a["teacher"]]+=1
    for a in rs["assignments"]:
        if a.get("teacher"): c[a["teacher"]]+=1
    return c,r13["summary"],rs["summary"]

def summary(c):
    alln=[t["name"] for t in app.SEED["teachers"]]
    vals=[c.get(n,0) for n in alln]
    return {
      "zero":sum(v==0 for v in vals),"active":sum(v>0 for v in vals),
      "min_active":min([v for v in vals if v>0] or [0]),"max":max(vals or [0]),
      "distribution":dict(sorted(Counter(vals).items())),
      "top":[{"name":n,"duties":c.get(n,0),"group":app.GROUP.get(n),
              "lessons":sum(len(ps or {}) for ps in app.TBY[n].get("lessons",{}).values())}
             for n in sorted(alln,key=lambda n:(-c.get(n,0),n))[:12]],
      "zeros_by_group":dict(Counter(app.GROUP.get(n) for n in alln if c.get(n,0)==0))
    }

result={"saved":summary(count_saved(base))}
for mode in ("hard","soft"):
    st=copy.deepcopy(base)
    for row in st.get("global_constraints",[]):
        if row.get("key")=="workload_fairness":
            row["enabled"]=True;row["kind"]=mode
    c,a,b=solve_with(st)
    result["preview_"+mode]={"loads":summary(c),"summary13":a,"summarySchool":b}
app.load_state=orig_loader
print(json.dumps(result,ensure_ascii=False,indent=2))
(ROOT/"WORKLOAD-AUDIT-v5.9.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
