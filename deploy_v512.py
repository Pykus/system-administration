
from __future__ import annotations
import json,re,subprocess,sys,time,urllib.request,shutil
from pathlib import Path
from datetime import datetime

V11=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
V12=Path(r"C:\DutySolverDemo\dyzury-v5.12-ortools")
PY=Path(r"C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe")
STARTUP=Path(r"C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd")
BACKUP=V12/"STARTUP-pre-v5.12.bak.cmd"

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
        for _ in range(50):
            if not port_pid(port):break
            time.sleep(.15)
    return pid

def get_json(path,timeout=10):
    with urllib.request.urlopen("http://127.0.0.1:8091"+path,timeout=timeout) as r:return json.load(r)
def get_text(path="/",timeout=10):
    with urllib.request.urlopen("http://127.0.0.1:8091"+path,timeout=timeout) as r:return r.read().decode("utf-8","replace")

# Last-second sync of user state from live v5.11.
for name in ("state.json","teacher_registry.json","settings.json"):
    src=V11/"data"/name
    if src.exists():shutil.copy2(src,V12/"data"/name)

sys.path.insert(0,str(V12))
import app as app12
st=app12.load_state()
st["version"]="5.12"
st["enabled_teachers_school"]=app12._school_pool(st.get("enabled_teachers_school",[]))
app12.save_state(st)
farmcfg=app12._farm_config()
farmcfg["enabled"]=False;farmcfg["broker_pid"]=0;farmcfg["local_workers"]=4
app12._save_farm_config(farmcfg)

(V12/"start_service.cmd").write_text(
    '@echo off\r\ncd /d C:\\Users\\Admin\\Production\\dyzury-v5.12-ortools\r\n'
    '"C:\\Users\\Admin\\AppData\\Local\\Programs\\Python\\Python312\\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8091\r\n',
    encoding="ascii")
if STARTUP.exists():BACKUP.write_text(STARTUP.read_text(encoding="utf-8",errors="replace"),encoding="utf-8")

old_pid=port_pid(8091)
newp=None
try:
    kill_port(8092)
    kill_port(8093)
    kill_port(8091)
    newp=subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V12,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    deadline=time.time()+50;health=None
    while time.time()<deadline:
        try:
            health=get_json("/api/health")
            if health.get("version")=="5.12":break
        except Exception:pass
        time.sleep(.4)
    if not health or health.get("version")!="5.12":raise RuntimeError("health v5.12 failed")
    html=get_text("/")
    for marker in ("Dyżury v5.12","grupa 1–3 jest zawsze wykluczona","nierozstrzygnięte","To nie jest dowód braku rozwiązania"):
        if marker not in html:raise RuntimeError("UI marker missing: "+marker)
    if "+ 1–3 awaryjnie" in html:raise RuntimeError("stale school 1-3 emergency button")
    cfg=get_json("/api/config")
    groups={t["name"]:t.get("group") for t in cfg["teachers"]}
    leaks=[n for n in cfg["state"].get("enabled_teachers_school",[]) if groups.get(n)=="1-3"]
    if leaks:raise RuntimeError("1-3 leaked into school pool: "+repr(leaks))
    farm=get_json("/api/worker-farm/status")
    if farm.get("enabled") or farm.get("broker_running"):raise RuntimeError("remote broker must default OFF")
    if int(farm.get("local_workers") or 0)!=4:raise RuntimeError("local_workers != 4")
    if port_pid(8093):raise RuntimeError("8093 unexpectedly listening")
    if port_pid(8092):raise RuntimeError("staging 8092 unexpectedly listening")
    STARTUP.write_text('@echo off\r\nstart "" /min C:\\Users\\Admin\\Production\\dyzury-v5.12-ortools\\start_service.cmd\r\n',encoding="ascii")
    result={
      "version":"5.12","pid":port_pid(8091),"old_pid":old_pid,"host":"127.0.0.1","port":8091,
      "engine":health.get("engine"),"teachers":health.get("teachers"),
      "school_pool":len(cfg["state"].get("enabled_teachers_school",[])),"school_13_leaks":leaks,
      "farm":{"enabled":farm.get("enabled"),"broker_running":farm.get("broker_running"),
              "port":farm.get("port"),"local_workers":farm.get("local_workers")},
      "staging_8092":False,"worker_broker_8093":False,"rollback":str(V11),
      "deployed_at":datetime.now().astimezone().isoformat(timespec="seconds")
    }
    (V12/"DEPLOYMENT-REPORT-v5.12.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=True,indent=2))
except Exception:
    if newp and newp.poll() is None:
        subprocess.run(["taskkill","/PID",str(newp.pid),"/F"],capture_output=True)
    kill_port(8091)
    if BACKUP.exists():STARTUP.write_text(BACKUP.read_text(encoding="utf-8",errors="replace"),encoding="utf-8")
    subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V11,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    time.sleep(2)
    raise
