import copy,json,sys
from pathlib import Path
ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools")
sys.path.insert(0,str(ROOT))
import app
base=app.load_state()
orig=app.load_state

def run(edge_mode):
    st=copy.deepcopy(base)
    for r in st["global_constraints"]:
        if r.get("key")=="workload_fairness": r["enabled"]=True;r["kind"]="soft"
        if r.get("key") in ("before_first_long","after_last_long") and edge_mode!="hard":
            r["enabled"]=True;r["kind"]=edge_mode
    app.load_state=lambda: copy.deepcopy(st)
    a=app.solve13({"enabled_teachers":st["enabled_teachers_13"],"manual_blocks":st.get("manual_blocks",{})})
    b=app.solve_school({"enabled_teachers":st["enabled_teachers_school"],"manual_blocks":st.get("manual_blocks",{}),"other_rows_13":a["rows"]})
    reasons={}
    for diag in (a.get("diagnostics",{}).get("unresolved",[]),b.get("diagnostics",{}).get("unresolved",[])):
        for u in diag:
            for rr in u.get("blocked_reasons",[]):
                reasons[rr["reason"]]=reasons.get(rr["reason"],0)+rr.get("count",0)
    return {"13":a["summary"],"school":b["summary"],"blocked_reasons":dict(sorted(reasons.items(),key=lambda x:-x[1])[:12])}

out={"edges_hard":run("hard"),"edges_soft":run("soft")}
app.load_state=orig
print(json.dumps(out,ensure_ascii=False,indent=2))
(ROOT/"EDGE-AUDIT-v5.9.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
