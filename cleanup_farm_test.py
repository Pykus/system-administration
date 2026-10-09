from pathlib import Path
import sys,sqlite3,json,subprocess
root=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
sys.path.insert(0,str(root))
import app
try: app._stop_worker_broker()
except Exception: pass
db=root/"data"/"repair_farm.sqlite"
if db.exists():
    c=sqlite3.connect(db);c.execute("DELETE FROM tasks");c.execute("DELETE FROM workers");c.commit();c.close()
cfg=app._farm_config();cfg["enabled"]=False;cfg["broker_pid"]=0;app._save_farm_config(cfg)
print(json.dumps({k:v for k,v in cfg.items() if k!="token"},ensure_ascii=False))
