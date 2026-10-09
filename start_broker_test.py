from pathlib import Path
import sqlite3,sys,json
root=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
db=root/"data"/"repair_farm.sqlite"
if db.exists():
    c=sqlite3.connect(db);c.execute("DELETE FROM tasks");c.execute("DELETE FROM workers");c.commit();c.close()
sys.path.insert(0,str(root))
import app
cfg=app._farm_config()
cfg["enabled"]=False;cfg["broker_pid"]=0;app._save_farm_config(cfg)
out=app._start_worker_broker()
print(json.dumps({k:v for k,v in out.items() if k!="token"},ensure_ascii=False))
