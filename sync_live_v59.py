from pathlib import Path
import json, shutil, datetime
src=Path(r"C:\DutySolverDemo\dyzury-v5.8-ortools\data")
dst=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools\data")
stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
bak=dst/("predeploy-v59-"+stamp)
bak.mkdir(parents=True,exist_ok=True)
for name in ("state.json","seed.json","teacher_registry.json"):
    cur=dst/name
    if cur.exists(): shutil.copy2(cur,bak/name)
    live=src/name
    if live.exists(): shutil.copy2(live,cur)
state=dst/"state.json"
s=json.loads(state.read_text(encoding="utf-8"))
s["version"]="5.9"
changed=False
for r in s.get("global_constraints",[]):
    if r.get("key")=="workload_fairness" and r.get("enabled") and str(r.get("kind","")).lower()=="hard":
        r["kind"]="soft"; changed=True
state.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding="utf-8")
print("SYNC_OK", "workload_to_soft="+str(changed), "school="+str(len(s.get("school_assignments",[]))), "rows13="+str(len(s.get("last_13_assignments",[]))))
