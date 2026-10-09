from __future__ import annotations
import argparse, os, time, json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse
import uvicorn
import repair_farm

ap=argparse.ArgumentParser()
ap.add_argument("--port",type=int,default=8093)
ap.add_argument("--token",required=True)
ap.add_argument("--version",default="5.12")
ap.add_argument("--seed-sha",required=True)
args=ap.parse_args()
TOKEN=args.token
app=FastAPI(title="DEMO Duty Solver Worker Broker",version="1.1")
SHARED_FARM_ROOT=Path(r"C:\DutySolverDemo\DEMO-WorkerFarm")
ACCESS_LOG=SHARED_FARM_ROOT/"worker_broker_access.log"
PACKAGE_ZIP=Path(r"C:\DutySolverDemo\DEMO-DutySolver-Worker-PY-v1.6-Veyon.zip")
DEPLOY_CMD=Path(r"C:\DutySolverDemo\DEMO-DEPLOY-WORKER-v1.6.cmd")
DEPLOY_STATUS_PATH=SHARED_FARM_ROOT/"worker_deploy_status.json"
PACKAGE_ZIP_17=Path(r"C:\DutySolverDemo\DEMO-DutySolver-Worker-FULL-v1.7.zip")
DEPLOY_CMD_17=Path(r"C:\DutySolverDemo\DEMO-DEPLOY-WORKER-v1.7.cmd")
PACKAGE_ZIP_18=Path(r"C:\DutySolverDemo\DEMO-DutySolver-Worker-FULL-v1.8.zip")
DEPLOY_CMD_18=Path(r"C:\DutySolverDemo\DEMO-DEPLOY-WORKER-v1.8.cmd")
PACKAGE_ZIP_19=Path(r"C:\DutySolverDemo\DEMO-DutySolver-Worker-FULL-v1.9.zip")
DEPLOY_CMD_19=Path(r"C:\DutySolverDemo\DEMO-DEPLOY-WORKER-v1.9.cmd")
PACKAGE_ZIP_110=Path(r"C:\DutySolverDemo\DEMO-DutySolver-Worker-FULL-v1.10.zip")
DEPLOY_CMD_110=Path(r"C:\DutySolverDemo\DEMO-DEPLOY-WORKER-v1.10.cmd")
PACKAGE_ZIP_111=Path(r"C:\DutySolverDemo\DEMO-DutySolver-Worker-FULL-v1.11.zip")
DEPLOY_CMD_111=Path(r"C:\DutySolverDemo\DEMO-DEPLOY-WORKER-v1.11.cmd")
PACKAGE_ZIP_112=Path(r"C:\DutySolverDemo\DEMO-DutySolver-Worker-FULL-v1.12.zip")
DEPLOY_CMD_112=Path(r"C:\DutySolverDemo\DEMO-DEPLOY-WORKER-v1.12.cmd")
PACKAGE_ZIP_113=Path(r"C:\DutySolverDemo\DEMO-DutySolver-Worker-FULL-v1.13.zip")
DEPLOY_CMD_113=Path(r"C:\DutySolverDemo\DEMO-DEPLOY-WORKER-v1.13.cmd")

def _alog(line):
    try:
        ACCESS_LOG.parent.mkdir(parents=True,exist_ok=True)
        with ACCESS_LOG.open("a",encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S")+" "+line+"\n")
    except Exception:
        pass

@app.middleware("http")
async def access_log(request:Request,call_next):
    ip=request.client.host if request.client else "?"
    try:
        response=await call_next(request)
        _alog(f"{ip} {request.method} {request.url.path} {response.status_code}")
        return response
    except Exception as exc:
        _alog(f"{ip} {request.method} {request.url.path} EXC {type(exc).__name__}")
        raise

def auth(x_worker_token):
    if x_worker_token!=TOKEN: raise HTTPException(403,"invalid worker token")

@app.get("/")
@app.get("/health")
def health():
    # Health is intentionally DB-free: it is used to verify broker build identity
    # during planner upgrades and must answer immediately even with a large task history.
    return {"ok":True,"service":"duty-worker-broker",
            "planner_version":args.version,
            "protocol_version":args.version,
            "seed_sha":args.seed_sha,
            "runtime_root":str(Path(__file__).parent.resolve())}

@app.get("/worker/package/v1.6")
def package_v16():
    # Deployment package only; port 8093 is already restricted by firewall to school networks.
    if not PACKAGE_ZIP.exists(): raise HTTPException(404,"package missing")
    return FileResponse(PACKAGE_ZIP,filename=PACKAGE_ZIP.name,media_type="application/zip")

@app.post("/worker/deploy-status")
def deploy_status(x:dict):
    host=str(x.get("hostname") or "unknown")
    row={"hostname":host,"step":str(x.get("step") or ""),"ok":bool(x.get("ok",False)),
         "detail":str(x.get("detail") or "")[:500],"at":time.time()}
    try:
        cur=json.loads(DEPLOY_STATUS_PATH.read_text(encoding="utf-8")) if DEPLOY_STATUS_PATH.exists() else {}
        old=cur.get(host,{}) if isinstance(cur.get(host,{}),dict) else {}
        hist=list(old.get("history",[]) or [])
        hist.append(row.copy())
        row["history"]=hist[-30:]
        cur[host]=row
        DEPLOY_STATUS_PATH.write_text(json.dumps(cur,ensure_ascii=False,indent=2),encoding="utf-8")
    except Exception: pass
    return {"ok":True}

@app.get("/worker/deploy-status")
def deploy_status_all():
    try:return json.loads(DEPLOY_STATUS_PATH.read_text(encoding="utf-8")) if DEPLOY_STATUS_PATH.exists() else {}
    except Exception:return {}

@app.get("/worker/package/v1.13")
def package_v113():
    if not PACKAGE_ZIP_113.exists(): raise HTTPException(404,"package missing")
    return FileResponse(PACKAGE_ZIP_113,filename=PACKAGE_ZIP_113.name,media_type="application/zip")

@app.get("/worker/deploy/v1.13")
def deploy_v113():
    if not DEPLOY_CMD_113.exists(): raise HTTPException(404,"deploy script missing")
    return FileResponse(DEPLOY_CMD_113,filename=DEPLOY_CMD_113.name,media_type="text/plain")

@app.get("/worker/package/v1.12")
def package_v112():
    if not PACKAGE_ZIP_112.exists(): raise HTTPException(404,"package missing")
    return FileResponse(PACKAGE_ZIP_112,filename=PACKAGE_ZIP_112.name,media_type="application/zip")

@app.get("/worker/deploy/v1.12")
def deploy_v112():
    if not DEPLOY_CMD_112.exists(): raise HTTPException(404,"deploy script missing")
    return FileResponse(DEPLOY_CMD_112,filename=DEPLOY_CMD_112.name,media_type="text/plain")

@app.get("/worker/package/v1.11")
def package_v111():
    if not PACKAGE_ZIP_111.exists(): raise HTTPException(404,"package missing")
    return FileResponse(PACKAGE_ZIP_111,filename=PACKAGE_ZIP_111.name,media_type="application/zip")

@app.get("/worker/deploy/v1.11")
def deploy_v111():
    if not DEPLOY_CMD_111.exists(): raise HTTPException(404,"deploy script missing")
    return FileResponse(DEPLOY_CMD_111,filename=DEPLOY_CMD_111.name,media_type="text/plain")

@app.get("/worker/package/v1.10")
def package_v110():
    if not PACKAGE_ZIP_110.exists(): raise HTTPException(404,"package missing")
    return FileResponse(PACKAGE_ZIP_110,filename=PACKAGE_ZIP_110.name,media_type="application/zip")

@app.get("/worker/deploy/v1.10")
def deploy_v110():
    if not DEPLOY_CMD_110.exists(): raise HTTPException(404,"deploy script missing")
    return FileResponse(DEPLOY_CMD_110,filename=DEPLOY_CMD_110.name,media_type="text/plain")

@app.get("/worker/package/v1.9")
def package_v19():
    if not PACKAGE_ZIP_19.exists(): raise HTTPException(404,"package missing")
    return FileResponse(PACKAGE_ZIP_19,filename=PACKAGE_ZIP_19.name,media_type="application/zip")

@app.get("/worker/deploy/v1.9")
def deploy_v19():
    if not DEPLOY_CMD_19.exists(): raise HTTPException(404,"deploy script missing")
    return FileResponse(DEPLOY_CMD_19,filename=DEPLOY_CMD_19.name,media_type="text/plain")

@app.get("/worker/package/v1.8")
def package_v18():
    if not PACKAGE_ZIP_18.exists(): raise HTTPException(404,"package missing")
    return FileResponse(PACKAGE_ZIP_18,filename=PACKAGE_ZIP_18.name,media_type="application/zip")

@app.get("/worker/deploy/v1.8")
def deploy_v18():
    if not DEPLOY_CMD_18.exists(): raise HTTPException(404,"deploy script missing")
    return FileResponse(DEPLOY_CMD_18,filename=DEPLOY_CMD_18.name,media_type="text/plain")

@app.get("/worker/package/v1.7")
def package_v17():
    if not PACKAGE_ZIP_17.exists(): raise HTTPException(404,"package missing")
    return FileResponse(PACKAGE_ZIP_17,filename=PACKAGE_ZIP_17.name,media_type="application/zip")

@app.get("/worker/deploy/v1.7")
def deploy_v17():
    if not DEPLOY_CMD_17.exists(): raise HTTPException(404,"deploy script missing")
    return FileResponse(DEPLOY_CMD_17,filename=DEPLOY_CMD_17.name,media_type="text/plain")

@app.get("/worker/deploy/v1.6")
def deploy_v16():
    if not DEPLOY_CMD.exists(): raise HTTPException(404,"deploy script missing")
    return FileResponse(DEPLOY_CMD,filename=DEPLOY_CMD.name,media_type="text/plain")

@app.post("/worker/register")
def register(x:dict,x_worker_token:str|None=Header(default=None)):
    auth(x_worker_token)
    if x.get("version")!=args.version or x.get("seed_sha")!=args.seed_sha:
        raise HTTPException(409,"worker version/seed mismatch")
    wid=repair_farm.register(x["worker_id"],x.get("hostname","worker"),x["version"],x["seed_sha"],x.get("cpu_count",1))
    return {"ok":True,"worker_id":wid}

@app.post("/worker/heartbeat")
def heartbeat(x:dict,x_worker_token:str|None=Header(default=None)):
    auth(x_worker_token);repair_farm.heartbeat(x["worker_id"],x.get("status","idle"),x.get("current_task",""));return {"ok":True}

@app.post("/worker/task")
def task(x:dict,x_worker_token:str|None=Header(default=None)):
    auth(x_worker_token)
    t=repair_farm.lease(x["worker_id"],x.get("version"),x.get("seed_sha"))
    if t and isinstance(t.get("payload"),dict):
        # Remote-only CPU boost. Current worker package clamps CP-SAT to max 8.
        # Target ~75% of logical CPUs, but never exceed the package limit.
        try:
            ws=repair_farm.active_workers(version=x.get("version"),seed_sha=x.get("seed_sha"),within=120)
            me=next((w for w in ws if w.get("worker_id")==x.get("worker_id")),None)
            cpu=max(1,int((me or {}).get("cpu_count") or 1))
            slots=max(1,min(3,round(cpu/5)))
            remote_threads=max(1,min(4,int((cpu*0.75)//slots)))
        except Exception:
            remote_threads=3
        t["payload"]["solver_internal_workers"]=remote_threads
    return {"task":t}

@app.post("/worker/result")
def result(x:dict,x_worker_token:str|None=Header(default=None)):
    auth(x_worker_token)
    repair_farm.submit(x["worker_id"],x["task_id"],x.get("result"),x.get("error"),x.get("elapsed_s",0))
    return {"ok":True}

if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=args.port,log_level="warning")
