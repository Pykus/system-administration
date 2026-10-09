
from pathlib import Path
import subprocess,time,json,urllib.request,os,shutil
PY=Path(r"C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe")
V14=Path(r"C:\DutySolverDemo\dyzury-v5.14-ortools")
V15=Path(r"C:\DutySolverDemo\dyzury-v5.15-ortools")
STARTUP=Path(r"C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd")
BACKUP=Path(r"C:\DutySolverDemo\DEMO-Dyzury.startup.pre-v5.15.cmd")
if STARTUP.exists(): BACKUP.write_bytes(STARTUP.read_bytes())

(V15/"start_service.cmd").write_text(
    '@echo off\r\ncd /d C:\\Users\\Admin\\Production\\dyzury-v5.15-ortools\r\n'
    '"C:\\Users\\Admin\\AppData\\Local\\Programs\\Python\\Python312\\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8091\r\n',
    encoding="ascii")

def port_pid(port):
    p=subprocess.run(["powershell.exe","-NoProfile","-Command",
        f"$x=Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue|Select-Object -First 1;if($x){{$x.OwningProcess}}else{{0}}"],
        capture_output=True,text=True)
    try:return int((p.stdout or "0").strip().splitlines()[-1])
    except:return 0

def kill_port(port):
    pid=port_pid(port)
    if pid:
        subprocess.run(["taskkill","/PID",str(pid),"/T","/F"],capture_output=True)
    return pid

def get_json(path,timeout=5):
    with urllib.request.urlopen("http://127.0.0.1:8091"+path,timeout=timeout) as r:return json.load(r)

def get_text(path="/",timeout=5):
    with urllib.request.urlopen("http://127.0.0.1:8091"+path,timeout=timeout) as r:return r.read().decode("utf-8","replace")

old_app=port_pid(8091)
old_stage=kill_port(8092)
old_broker=port_pid(8093)
newp=None
try:
    kill_port(8093)
    kill_port(8091)
    time.sleep(.8)
    newp=subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    deadline=time.time()+45; health=None
    while time.time()<deadline:
        try:
            health=get_json("/api/health")
            if health.get("version")=="5.15": break
        except Exception: pass
        time.sleep(.4)
    if not health or health.get("version")!="5.15":
        raise RuntimeError("health v5.15 failed")

    html=get_text("/")
    required_markers=[
        "Dyżury v5.15",
        "Wykluczeni ze wszystkich dyżurów",
        "Zamroź skład tej puli",
        "+ 1–3 awaryjnie",
        "Plan nauczyciela:",
        "przyjazdem tylko na dyżur",
    ]
    missing=[x for x in required_markers if x not in html]
    if missing: raise RuntimeError("UI markers missing: "+repr(missing))

    val=get_json("/api/config")
    if val.get("state",{}).get("version")!="5.15":
        raise RuntimeError("state version mismatch")
    vr=urllib.request.Request("http://127.0.0.1:8091/api/validation",
        data=b"{}",headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(vr,timeout=8) as rr: validation=json.load(rr)
    if validation.get("errors",0):
        raise RuntimeError("validation errors: "+json.dumps(validation,ensure_ascii=False))

    # Status call restarts broker from v5.15 when enabled.
    farm=get_json("/api/worker-farm/status")
    deadline=time.time()+12
    while time.time()<deadline and not (farm.get("broker_running") and port_pid(8093)):
        time.sleep(.4)
        farm=get_json("/api/worker-farm/status")
    if farm.get("enabled") and not farm.get("broker_running"):
        raise RuntimeError("worker broker failed to start")

    STARTUP.write_text('@echo off\r\nstart "" /min C:\\Users\\Admin\\Production\\dyzury-v5.15-ortools\\start_service.cmd\r\n',encoding="ascii")
    report={
        "ok":True,"version":"5.15","pid8091":port_pid(8091),"pid8093":port_pid(8093),
        "old_pid8091":old_app,"old_pid8093":old_broker,"old_stage_pid":old_stage,
        "validation_errors":validation.get("errors"),"validation_warnings":validation.get("warnings"),
        "broker_enabled":farm.get("enabled"),"broker_running":farm.get("broker_running"),
        "local_workers":farm.get("local_workers"),"workers_online":farm.get("workers_online"),
        "worker_protocol":farm.get("worker_protocol_version"),
        "rollback":str(V14)
    }
    (V15/"DEPLOYMENT-REPORT-v5.15.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
except Exception:
    if newp and newp.poll() is None:
        subprocess.run(["taskkill","/PID",str(newp.pid),"/T","/F"],capture_output=True)
    kill_port(8091); kill_port(8093)
    if BACKUP.exists(): STARTUP.write_bytes(BACKUP.read_bytes())
    subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V14,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    time.sleep(2)
    try:get_json("/api/worker-farm/status")
    except Exception:pass
    raise
