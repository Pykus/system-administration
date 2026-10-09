from pathlib import Path
import shutil,sys,json
src=Path(r"C:\DutySolverDemo\dyzury-v5.10-ortools\data")
dst=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools\data")
for name in ("state.json","teacher_registry.json"):
    if (src/name).exists(): shutil.copy2(src/name,dst/name)
sys.path.insert(0,str(dst.parent))
import app
st=app.load_state();st["version"]="5.11";app.save_state(st)
cfg=app._farm_config();cfg["enabled"]=False;cfg["broker_pid"]=0;cfg["local_workers"]=4;app._save_farm_config(cfg)
print(json.dumps({"school":len(st.get("school_assignments",[])),"rows13":len(st.get("last_13_assignments",[])),
                  "consecutive":next((x for x in st.get("global_constraints",[]) if x.get("key")=="max_consecutive_duties"),None),
                  "farm":{k:v for k,v in cfg.items() if k!="token"}},ensure_ascii=False))
