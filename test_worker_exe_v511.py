from pathlib import Path
import json, subprocess, sys, time, os
ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
sys.path.insert(0,str(ROOT))
import app, repair_farm
cfg=app._farm_config()
broker=subprocess.Popen([sys.executable,str(ROOT/"worker_broker.py"),"--port",str(cfg["port"]),"--token",cfg["token"],"--version","5.11","--seed-sha",app._seed_sha()],
                        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
worker=subprocess.Popen([str(ROOT/"dist_worker"/"DEMO-DutySolver-Worker-v1.0.exe")],cwd=ROOT,
                        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace")
try:
    deadline=time.time()+30
    registered=False
    while time.time()<deadline:
        st=repair_farm.status()
        if any(w.get("online") and w.get("version")=="5.11" for w in st["workers"]):
            registered=True;break
        time.sleep(.5)
    if not registered: raise RuntimeError("worker did not register")
    s=app.load_state()
    tid=repair_farm.enqueue("exe-smoke","5.11",app._seed_sha(),{"state":s,"e13":s.get("enabled_teachers_13",[]),"es":s.get("enabled_teachers_school",[]),"tokens":["gval:max_day_13:5"]})
    deadline=time.time()+90
    row=None
    while time.time()<deadline:
        row=repair_farm.get_task(tid)
        if row and row.get("status") in ("done","failed"):break
        time.sleep(.5)
    if not row or row.get("status")!="done":
        raise RuntimeError("worker task failed: "+repr(row))
    print(json.dumps({"registered":registered,"task_status":row["status"],"result":row["result"]},ensure_ascii=False,indent=2))
finally:
    for p in (worker,broker):
        try:p.terminate();p.wait(5)
        except Exception:
            try:p.kill()
            except Exception:pass
