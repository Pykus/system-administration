
from pathlib import Path
import subprocess,time,json,urllib.request,os
PY=Path(r"C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe")
V13=Path(r"C:\DutySolverDemo\dyzury-v5.13-ortools")
V12=Path(r"C:\DutySolverDemo\dyzury-v5.12-ortools")
STARTUP=Path(r"C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd")
BACKUP=Path(r"C:\DutySolverDemo\DEMO-Dyzury.startup.pre-v5.13.cmd")
if STARTUP.exists(): BACKUP.write_bytes(STARTUP.read_bytes())

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
def get_json(path,port=8091):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}",timeout=5) as r:return json.load(r)
def get_text(path="/",port=8091):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}",timeout=5) as r:return r.read().decode("utf-8","replace")

old_app=port_pid(8091); old_broker=port_pid(8093)
newp=None
try:
    kill_port(8093); kill_port(8091); kill_port(8092); kill_port(8094)
    newp=subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V13,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    deadline=time.time()+45; health=None
    while time.time()<deadline:
        try:
            health=get_json("/api/health")
            if health.get("version")=="5.13": break
        except Exception: pass
        time.sleep(.4)
    if not health or health.get("version")!="5.13": raise RuntimeError("health v5.13 failed")
    html=get_text("/")
    for marker in ("Dyżury v5.13","recoverRepair","Wyszukiwanie trwa","żaden zdalny worker"):
        if marker not in html: raise RuntimeError("UI marker missing: "+marker)
    cur=get_json("/api/diagnostics/repair/search/current")
    farm=get_json("/api/worker-farm/status")
    deadline=time.time()+10
    while time.time()<deadline and not port_pid(8093):
        time.sleep(.3)
        farm=get_json("/api/worker-farm/status")
    if not farm.get("enabled") or not farm.get("broker_running"): raise RuntimeError("broker not running")
    if int(farm.get("local_workers") or 0)!=8: raise RuntimeError("local_workers != 8")
    if farm.get("worker_protocol_version")!="5.12": raise RuntimeError("worker protocol mismatch")
    if port_pid(8092) or port_pid(8094): raise RuntimeError("staging/test ports still listening")
    STARTUP.write_text('@echo off\r\nstart "" /min C:\\Users\\Admin\\Production\\dyzury-v5.13-ortools\\start_service.cmd\r\n',encoding="ascii")
    out={"version":"5.13","pid":port_pid(8091),"old_pid":old_app,"broker_pid":port_pid(8093),
         "old_broker_pid":old_broker,"local_workers":farm.get("local_workers"),
         "workers_online":farm.get("workers_online"),"worker_protocol_version":farm.get("worker_protocol_version"),
         "current_job":cur.get("job"),"rollback":str(V12)}
    (V13/"DEPLOYMENT-REPORT-v5.13.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=True,indent=2))
except Exception:
    if newp and newp.poll() is None:
        subprocess.run(["taskkill","/PID",str(newp.pid),"/T","/F"],capture_output=True)
    kill_port(8091); kill_port(8093)
    if BACKUP.exists(): STARTUP.write_bytes(BACKUP.read_bytes())
    subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V12,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    time.sleep(2)
    try:get_json("/api/worker-farm/status")
    except Exception:pass
    raise
