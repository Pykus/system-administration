from __future__ import annotations
import importlib.util, json, os, re, shutil, subprocess, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

V59=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools")
V510=Path(r"C:\DutySolverDemo\dyzury-v5.10-ortools")
PY=Path(r"C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe")
STARTUP=Path(r"C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd")
STARTUP_BACKUP=V510/"STARTUP-pre-v5.10.bak.cmd"

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
        for _ in range(30):
            if not port_pid(port):break
            time.sleep(.2)
    return pid

def get_json(url):
    with urllib.request.urlopen(url,timeout=8) as r:return json.load(r)

def get_text(url):
    with urllib.request.urlopen(url,timeout=8) as r:return r.read().decode("utf-8",errors="replace")

stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
bak=V510/"data"/("predeploy-v510-"+stamp)
bak.mkdir(parents=True,exist_ok=True)
for name in ("state.json","seed.json","teacher_registry.json"):
    cur=V510/"data"/name
    if cur.exists():shutil.copy2(cur,bak/name)
    src=V59/"data"/name
    if src.exists():shutil.copy2(src,cur)
if STARTUP.exists():
    STARTUP_BACKUP.write_text(STARTUP.read_text(encoding="utf-8",errors="replace"),encoding="utf-8")

# Persist schema migration using v5.10 code.
sys.path.insert(0,str(V510))
import app as app510
st=app510.load_state()
st["version"]="5.10"
app510.save_state(st)
cm={x["key"]:x for x in app510.load_state()["global_constraints"]}
assert cm["max_consecutive_duties"]["enabled"] is True
assert int(cm["max_consecutive_duties"]["value"])==1

# Validate after live-data sync.
subprocess.run([str(PY),"-m","compileall","-q","app.py","solver_ortools.py","validation.py","test_v510.py"],cwd=V510,check=True)
subprocess.run([str(PY),"-m","unittest","-q","test_v510.py"],cwd=V510,check=True)
subprocess.run(["node.exe","--check","_ui_check_v510.js"],cwd=V510,check=True)

# Staging no longer needed.
kill_port(8092)

launcher=V510/"start_service.cmd"
launcher.write_text('@echo off\r\ncd /d C:\\Users\\Admin\\Production\\dyzury-v5.10-ortools\r\n"'+str(PY)+'" -m uvicorn app:app --host 127.0.0.1 --port 8091\r\n',encoding="ascii")

old_pid=port_pid(8091)
newp=None
try:
    kill_port(8091)
    newp=subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V510,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    deadline=time.time()+45; h=None
    while time.time()<deadline:
        try:
            h=get_json("http://127.0.0.1:8091/api/health")
            if h.get("version")=="5.10":break
        except Exception:pass
        time.sleep(.5)
    if not h or h.get("version")!="5.10":raise RuntimeError("health v5.10 failed")
    cfg=get_json("http://127.0.0.1:8091/api/config")
    cm={x["key"]:x for x in cfg["state"]["global_constraints"]}
    if int(cm["max_consecutive_duties"]["value"])!=1:raise RuntimeError("consecutive default not migrated")
    html=get_text("http://127.0.0.1:8091/")
    for marker in ("Dyżury v5.10","Generator wariantów naprawczych","Pauza","Wznów","max_consecutive_duties"):
        if marker not in html:raise RuntimeError("UI marker missing: "+marker)
    STARTUP.write_text('@echo off\r\nstart "" /min C:\\Users\\Admin\\Production\\dyzury-v5.10-ortools\\start_service.cmd\r\n',encoding="ascii")
    result={
      "version":"5.10","pid":newp.pid,"host":"127.0.0.1","port":8091,"localhost_only":True,
      "engine":h.get("engine"),"school_assignments":len(cfg["state"].get("school_assignments",[])),
      "rows13":len(cfg["state"].get("last_13_assignments",[])),
      "max_consecutive_duties":cm["max_consecutive_duties"],
      "startup":str(STARTUP),"rollback":str(V59),
      "deployed_at":datetime.now().astimezone().isoformat(timespec="seconds")
    }
    (V510/"DEPLOYMENT-REPORT-v5.10.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
except Exception:
    if newp and newp.poll() is None:
        subprocess.run(["taskkill","/PID",str(newp.pid),"/F"],capture_output=True)
    if STARTUP_BACKUP.exists():
        STARTUP.write_text(STARTUP_BACKUP.read_text(encoding="utf-8"),encoding="utf-8")
    subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V59,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    time.sleep(2)
    raise
