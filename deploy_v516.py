
from pathlib import Path
import subprocess,time,json,urllib.request,shutil,sqlite3
PY=Path(r"C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe")
V15=Path(r"C:\DutySolverDemo\dyzury-v5.15-ortools")
V16=Path(r"C:\DutySolverDemo\dyzury-v5.16-ortools")
STARTUP=Path(r"C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd")
BACKUP=Path(r"C:\DutySolverDemo\DEMO-Dyzury.startup.pre-v5.16.cmd")
if STARTUP.exists(): BACKUP.write_bytes(STARTUP.read_bytes())

def port_pid(port):
    p=subprocess.run(["powershell.exe","-NoProfile","-Command",
        f"$x=Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue|Select-Object -First 1;if($x){{$x.OwningProcess}}else{{0}}"],
        capture_output=True,text=True)
    try:return int((p.stdout or "0").strip().splitlines()[-1])
    except:return 0
def kill_port(port):
    pid=port_pid(port)
    if pid: subprocess.run(["taskkill","/PID",str(pid),"/T","/F"],capture_output=True)
    return pid
def get_json(path,port=8091):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}",timeout=5) as r:return json.load(r)
def get_text(path="/",port=8091):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}",timeout=5) as r:return r.read().decode("utf-8","replace")

old_app=port_pid(8091); old_broker=port_pid(8093)
newp=None
try:
    # Stop old services first so volatile files can be synchronized consistently.
    kill_port(8093); kill_port(8091); kill_port(8092)

    for name in ("state.json","teacher_registry.json","settings.json"):
        src=V15/"data"/name
        if src.exists(): shutil.copy2(src,V16/"data"/name)
    sp=V16/"data"/"state.json"
    st=json.loads(sp.read_text(encoding="utf-8")); st["version"]="5.16"
    sp.write_text(json.dumps(st,ensure_ascii=False,indent=2),encoding="utf-8")

    cfg=json.loads((V15/"data"/"repair_farm_config.json").read_text(encoding="utf-8"))
    cfg["broker_pid"]=0
    (V16/"data"/"repair_farm_config.json").write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")

    srcdb=V15/"data"/"repair_farm.sqlite"; dstdb=V16/"data"/"repair_farm.sqlite"
    for x in (dstdb,Path(str(dstdb)+"-wal"),Path(str(dstdb)+"-shm")):
        try:x.unlink()
        except FileNotFoundError:pass
    a=sqlite3.connect(srcdb); b=sqlite3.connect(dstdb); a.backup(b); b.close(); a.close()

    newp=subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V16,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    deadline=time.time()+45; health=None
    while time.time()<deadline:
        try:
            health=get_json("/api/health")
            if health.get("version")=="5.16": break
        except Exception: pass
        time.sleep(.4)
    if not health or health.get("version")!="5.16": raise RuntimeError("health v5.16 failed")

    html=get_text("/")
    for marker in ("Dyżury v5.16","Zamroź skład tej puli","Wykluczeni ze wszystkich dyżurów"):
        if marker not in html: raise RuntimeError("UI marker missing: "+marker)

    farm=get_json("/api/worker-farm/status")
    deadline=time.time()+12
    while time.time()<deadline and not farm.get("broker_running"):
        time.sleep(.4); farm=get_json("/api/worker-farm/status")
    if not farm.get("broker_running"): raise RuntimeError("broker not running")
    if farm.get("worker_protocol_version")!="5.15": raise RuntimeError("worker protocol mismatch")
    if int(farm.get("local_workers") or 0)!=8: raise RuntimeError("local_workers != 8")

    STARTUP.write_text('@echo off\r\nstart "" /min C:\\Users\\Admin\\Production\\dyzury-v5.16-ortools\\start_service.cmd\r\n',encoding="ascii")
    out={"version":"5.16","pid":port_pid(8091),"old_pid":old_app,"broker_pid":port_pid(8093),
         "old_broker_pid":old_broker,"worker_protocol":farm.get("worker_protocol_version"),
         "local_workers":farm.get("local_workers"),"workers_online":farm.get("workers_online"),
         "rollback":str(V15)}
    (V16/"DEPLOYMENT-REPORT-v5.16.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=True))
except Exception:
    if newp and newp.poll() is None: subprocess.run(["taskkill","/PID",str(newp.pid),"/T","/F"],capture_output=True)
    kill_port(8091); kill_port(8093)
    if BACKUP.exists(): STARTUP.write_bytes(BACKUP.read_bytes())
    subprocess.Popen([str(PY),"-m","uvicorn","app:app","--host","127.0.0.1","--port","8091"],
        cwd=V15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    time.sleep(2)
    try:get_json("/api/worker-farm/status")
    except Exception:pass
    raise
