from pathlib import Path
import shutil, json, hashlib, re
v510=Path(r"C:\DutySolverDemo\dyzury-v5.10-ortools")
v511=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
bak=v511/"data"/"predeploy-v511"
bak.mkdir(parents=True,exist_ok=True)
for name in ("state.json","seed.json","teacher_registry.json"):
    cur=v511/"data"/name
    if cur.exists(): shutil.copy2(cur,bak/name)
    src=v510/"data"/name
    if src.exists(): shutil.copy2(src,cur)

sha=hashlib.sha256((v511/"data"/"seed.json").read_bytes()).hexdigest()
cfg=v511/"worker_embedded_config.py"
text=cfg.read_text(encoding="utf-8")
text=re.sub(r'^SEED_SHA=.*$',f'SEED_SHA="{sha}"',text,flags=re.M)
cfg.write_text(text,encoding="utf-8")

import sys
sys.path.insert(0,str(v511))
import app
st=app.load_state()
st["version"]="5.11"
app.save_state(st)
print(json.dumps({"seed_sha":sha,"state_school":len(st.get("school_assignments",[])),"rows13":len(st.get("last_13_assignments",[])),"farm":app._farm_config()},ensure_ascii=False))
