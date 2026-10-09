from __future__ import annotations
import json,re,subprocess,sys,time,urllib.request,shutil
from pathlib import Path
from datetime import datetime

V510=Path(r"C:\DutySolverDemo\dyzury-v5.10-ortools")
V511=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
PY=Path(r"C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe")
STARTUP=Path(r"C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd")
STARTUP_BAK=V511/"STARTUP-pre-v5.11.bak.cmd"

def port_pid(port):
    out=subprocess.run(["netstat","-ano","-p","TCP"],capture_output=True,text=True,errors="replace").stdout
    for line in out.splitlines():
        m=re.search(rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$",line,re.I)
        if m:return int(m.group(1))
    return None
def kill_port(port):
    pid=port_pid(port)
    if pid:
        subprocess.run(["taskkill","/PID",str(pid),"/F"],capture_output=True)
        for _ in range(40):
            if not port_pid(port):break
            time.sleep(.15)
    return pid
def get_json(url):
    with urllib.request.urlopen(url,timeout=8) as r:return json.load(r)
def get_text(url):
    with urllib.request.urlopen(url,timeout=8) as r:return r.read().decode("utf-8",errors="replace")

# Last-second sync of mutable production state only. seed.json is already hash-verified equal.
for name in ("state.json","teacher_registry.json"):
    src=V510/"data"/name
    if src.exists():shutil.copy2(src,V511/"data"/name)

# Persist v5.11 schema without touching assignments.
sys.path.insert(0,str(V511))
import app as app511
st=app511.load_state();st["version"]="5.11";app511.save_state(st)
cfg=app511._farm_config();cfg["enabled"]=False;cfg["broker_pid"]=0;cfg["local_workers"]=4;app511._save_farm_config(cfg)

(V511/"start_service.cmd").write_text(
    '@echo off\r\ncd /d C:\\Users\\Admin\\Production\\dyzury-v5.11-ortools\r\n'
    '"C:\\Users\\Admin\\AppData\\Local\\Programs\\Python\\Python312\\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8091\r\n',
    encoding="ascii")
if STARTUP.exists():STARTUP_BAK.write_text(STARTUP.read_text(encoding="utf-8",errors="replace"),encoding="utf-8")

kill_port(8092)
kill_port(8093)
old_pid=port_pid(8091)
newp=None
try:
    kill_port(8091)
    newp=subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V511,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    deadline=time.time()+45;health=None
    while time.time()<deadline:
        try:
            health=get_json("http://127.0.0.1:8091/api/health")
            if health.get("version")=="5.11":break
        except Exception:pass
        time.sleep(.4)
    if not health or health.get("version")!="5.11":raise RuntimeError("health v5.11 failed")
    c=get_json("http://127.0.0.1:8091/api/config")
    farm=get_json("http://127.0.0.1:8091/api/worker-farm/status")
    html=get_text("http://127.0.0.1:8091/")
    for marker in ("Dyżury v5.11","Przejrzyj wariant / zwiń szczegóły","Umożliw pracę zdalnym workerom","OSTATNIA MOŻLIWOŚĆ: oczekiwanie"):
        if marker not in html:raise RuntimeError("UI marker missing: "+marker)
    if farm.get("enabled") or farm.get("broker_running"):raise RuntimeError("remote broker should default OFF")
    if port_pid(8093):raise RuntimeError("8093 unexpectedly listening")
    if port_pid(8092):raise RuntimeError("staging 8092 unexpectedly listening")
    STARTUP.write_text('@echo off\r\nstart "" /min C:\\Users\\Admin\\Production\\dyzury-v5.11-ortools\\start_service.cmd\r\n',encoding="ascii")
    result={
        "version":"5.11","pid":newp.pid,"old_pid":old_pid,"host":"127.0.0.1","port":8091,
        "localhost_only":True,"engine":health.get("engine"),
        "school_assignments":len(c["state"].get("school_assignments",[])),
        "rows13":len(c["state"].get("last_13_assignments",[])),
        "farm":{"enabled":farm.get("enabled"),"broker_running":farm.get("broker_running"),"port":farm.get("port"),"local_workers":farm.get("local_workers")},
        "worker_broker_exposed":False,"rollback":str(V510),
        "deployed_at":datetime.now().astimezone().isoformat(timespec="seconds")
    }
    (V511/"DEPLOYMENT-REPORT-v5.11.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
except Exception:
    if newp and newp.poll() is None:subprocess.run(["taskkill","/PID",str(newp.pid),"/F"],capture_output=True)
    if STARTUP_BAK.exists():STARTUP.write_text(STARTUP_BAK.read_text(encoding="utf-8"),encoding="utf-8")
    subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V510,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    time.sleep(2)
    raise
