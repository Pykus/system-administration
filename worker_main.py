from __future__ import annotations
import json, os, socket, sys, time, uuid, urllib.request, threading
from pathlib import Path
from solver_ortools import solve_positions_ortools
TOKEN=os.environ.get('DUTY_SOLVER_WORKER_TOKEN','')
VERSION="5.16"
WORKER_VERSION="1.12"
CAPABILITIES=["duty_solver"]
SEED_SHA='0c2829a108fa45a1f770632e2d08c2c11ea1e4c9e0fc6599fcd94699f67f9871'
BROKER_URLS=["http://192.0.2.10:8093","http://DEMO-AI-NODE00:8093"]

BASES=[]
if os.environ.get("ZSO_DUTY_BROKER"): BASES.append(os.environ["ZSO_DUTY_BROKER"].rstrip("/"))
BASES += [x.rstrip("/") for x in BROKER_URLS]
PROGRAM=Path(os.environ.get("PROGRAMDATA",r"C:\\ProgramData"))/"DEMO"/"DutySolverWorkerData"
PROGRAM.mkdir(parents=True,exist_ok=True)
IDFILE=PROGRAM/"worker-id.txt"
LOG=PROGRAM/"worker.log"
if IDFILE.exists(): WORKER_ID=IDFILE.read_text(encoding="utf-8").strip()
else:
    WORKER_ID=socket.gethostname()+"-"+uuid.uuid4().hex[:8]
    IDFILE.write_text(WORKER_ID,encoding="utf-8")
HOST=socket.gethostname()
CPU=os.cpu_count() or 1
BUNDLE=Path(getattr(sys,"_MEIPASS",Path(__file__).parent))
try:
    SEED=json.loads((BUNDLE/"data"/"seed.json").read_text(encoding="utf-8"))
except Exception:
    SEED={}
GROUP={t["name"]:t.get("group","school") for t in SEED.get("teachers",[]) if t.get("name")}

def log(msg):
    line=time.strftime("%Y-%m-%d %H:%M:%S")+" "+str(msg)
    print(line,flush=True)
    try:
        with LOG.open("a",encoding="utf-8") as f:f.write(line+"\n")
    except Exception: pass

def req(base,path,obj=None,timeout=15):
    data=None if obj is None else json.dumps(obj,ensure_ascii=False).encode("utf-8")
    r=urllib.request.Request(base+path,data=data,
        headers={"Content-Type":"application/json","X-Worker-Token":TOKEN},
        method="GET" if obj is None else "POST")
    with urllib.request.urlopen(r,timeout=timeout) as x:return json.load(x)

def report_deploy(step,ok=True,detail=""):
    payload={"hostname":HOST,"step":step,"ok":bool(ok),"detail":str(detail)[:500]}
    for base in BASES:
        try:
            req(base,"/worker/deploy-status",payload,3)
            return True
        except Exception:
            pass
    return False

def local_ips():
    out=[]
    try:
        for info in socket.getaddrinfo(HOST,None,socket.AF_INET):
            ip=info[4][0]
            if ip not in out: out.append(ip)
    except Exception: pass
    return out

def find_broker():
    errors=[]
    for base in BASES:
        try:
            h=req(base,"/health",None,3)
            if h.get("ok") and h.get("planner_version")==VERSION and h.get("seed_sha")==SEED_SHA:
                return base,errors
            errors.append(base+" -> odpowiedź niezgodna: "+json.dumps(h,ensure_ascii=False))
        except Exception as e:
            errors.append(base+" -> "+type(e).__name__+": "+str(e))
    return None,errors

def flat13(rows):
    return [{"day":a["day"],"abbr":a["abbr"],"slot":a["slot"],
             "location":"1–3 "+a.get("station",""),"teacher":a.get("teacher","")}
            for a in rows if a.get("teacher")]

def flat_school(rows):
    return [{"day":a["day"],"abbr":a["abbr"],"slot":a["slot"],
             "location":a.get("location",""),"teacher":a.get("teacher","")}
            for a in rows if a.get("teacher")]

def compute(payload):
    seed=payload.get("seed") or SEED
    if not seed: raise RuntimeError("Brak danych seed w zadaniu i lokalnym bundle.")
    group=payload.get("group") or {t["name"]:t.get("group","school") for t in seed.get("teachers",[]) if t.get("name")}
    state=payload["state"]
    # 3 to zalecana i domyślna liczba wątków CP-SAT; broker może ją nadpisać w zadaniu.
    state["solver_internal_workers"]=max(1,min(12,int(payload.get("solver_internal_workers",state.get("solver_internal_workers",3) or 3))))
    state["solver_coverage_seconds"]=max(4,int(state.get("solver_coverage_seconds",4) or 4))
    state["solver_coverage_retry_seconds"]=max(20,int(state.get("solver_coverage_retry_seconds",20) or 20))
    e13=set(payload["enabled13"])
    es=set(payload["enabledSchool"])
    def solve13(other):
        return solve_positions_ortools(state,"1–3",payload["positions13"],e13,other,None,seed,group,
            coverage_only=True,repair_mode=False)
    def solveschool(other):
        return solve_positions_ortools(state,"szkoła",payload["positionsSchool"],es,other,None,seed,group,
            coverage_only=True,repair_mode=False)
    def pack(a13,m13,meta13,school,ms,metas,order):
        inc=bool(meta13.get("diagnostics",{}).get("inconclusive") or metas.get("diagnostics",{}).get("inconclusive"))
        return {"missing":len(m13)+len(ms),"inconclusive":inc,"order":order,
                "coverage13":{"required":len(payload["positions13"]),"filled":len(payload["positions13"])-len(m13),"missing":len(m13)},
                "coverageSchool":{"required":len(payload["positionsSchool"]),"filled":len(payload["positionsSchool"])-len(ms),"missing":len(ms)}}
    a13,w13,m13,meta13=solve13([])
    school,ws,ms,metas=solveschool(flat13(a13))
    first=pack(a13,m13,meta13,school,ms,metas,"13-first")
    if not first["inconclusive"] and first["missing"]==0:return first
    school2,ws2,ms2,metas2=solveschool([])
    a132,w132,m132,meta132=solve13(flat_school(school2))
    second=pack(a132,m132,meta132,school2,ms2,metas2,"school-first")
    return min((first,second),key=lambda x:(x["inconclusive"],x["missing"]))

def run_task(task):
    task_type=str(task.get("type") or "duty_solver")
    if task_type=="duty_solver": return compute(task["payload"])
    raise RuntimeError("Unsupported task type: "+task_type)

if "--self-test" in sys.argv:
    print(json.dumps({"ok":True,"worker_version":WORKER_VERSION,"planner_version":VERSION,
                      "seed_sha":SEED_SHA,"hostname":HOST,"cpu":CPU,
                      "brokers":BROKER_URLS,"capabilities":CAPABILITIES,"teachers":len(SEED.get("teachers",[]))},ensure_ascii=False))
    raise SystemExit(0)

# Single instance per machine. Repeated Veyon launches must not create duplicate workers.
if os.name=="nt":
    import ctypes
    _k32=ctypes.WinDLL("kernel32",use_last_error=True)
    _k32.CreateMutexW.restype=ctypes.c_void_p
    _worker_mutex=_k32.CreateMutexW(None,False,"Global\\DEMO-DutySolver-Worker-v1.6")
    if ctypes.get_last_error()==183:
        print("DEMO Duty Solver Worker v1.6 juz dziala na tym komputerze.",flush=True)
        raise SystemExit(0)

log("DEMO Duty Solver Worker "+WORKER_VERSION+" | "+WORKER_ID+" | CPU="+str(CPU))
report_deploy("WORKER_STARTED",True,"worker "+WORKER_VERSION+" pid="+str(os.getpid()))
log("Lokalne IPv4: "+(", ".join(local_ips()) or "brak"))
log("Broker targets: "+", ".join(BASES))
if any(ip.startswith("198.51.100.29.") for ip in local_ips()):
    log("Sieć S13 198.51.100.29.0/24: wymagany routing/firewall do 192.0.2.10:8093.")
TASK_SLOTS=max(1,min(3,round(CPU/5)))
log("Równoległe sloty zadań: "+str(TASK_SLOTS))
base=None
while True:
    if not base:
        base,errors=find_broker()
        if not base:
            log("Broker niedostępny; "+(" | ".join(errors) if errors else "brak odpowiedzi")+"; ponawiam za 30 s.")
            time.sleep(30);continue
        try:
            req(base,"/worker/register",{"worker_id":WORKER_ID,"hostname":HOST,"version":VERSION,
                "worker_version":WORKER_VERSION,"seed_sha":SEED_SHA,"cpu_count":CPU,"capabilities":CAPABILITIES})
            report_deploy("BROKER_CONNECTED",True,base)
            log("Połączono: "+base)
        except Exception as e:
            log("Rejestracja nieudana: "+str(e));base=None;time.sleep(30);continue
    try:
        tasks=[]
        for _ in range(TASK_SLOTS):
            t=req(base,"/worker/task",{"worker_id":WORKER_ID,"version":VERSION,"seed_sha":SEED_SHA},10).get("task")
            if not t: break
            tasks.append(t)
        if not tasks:
            req(base,"/worker/heartbeat",{"worker_id":WORKER_ID,"status":"idle","current_task":""},5)
            time.sleep(30);continue

        tids=[t["task_id"] for t in tasks]
        log("Liczenie równoległe "+", ".join(tids))
        current=",".join(tids)
        req(base,"/worker/heartbeat",{"worker_id":WORKER_ID,"status":"busy","current_task":current},5)
        started={t["task_id"]:time.perf_counter() for t in tasks}
        boxes={t["task_id"]:{"result":None,"error":None} for t in tasks}

        def _run(one):
            tid=one["task_id"];box=boxes[tid]
            try: box["result"]=run_task(one)
            except Exception as e: box["error"]=repr(e)

        threads=[threading.Thread(target=_run,args=(t,),daemon=True) for t in tasks]
        for th in threads: th.start()
        while any(th.is_alive() for th in threads):
            time.sleep(4)
            try:req(base,"/worker/heartbeat",{"worker_id":WORKER_ID,"status":"busy","current_task":current},5)
            except Exception:pass

        for t in tasks:
            tid=t["task_id"];box=boxes[tid];elapsed=time.perf_counter()-started[tid]
            req(base,"/worker/result",{"worker_id":WORKER_ID,"task_id":tid,"result":box["result"],
                                      "error":box["error"],"elapsed_s":elapsed},15)
            log("Gotowe "+tid+" "+str(round(elapsed,2))+" s "+(("ERROR "+box["error"]) if box["error"] else str(box["result"])))
        req(base,"/worker/heartbeat",{"worker_id":WORKER_ID,"status":"idle","current_task":""},5)
    except KeyboardInterrupt:
        break
    except Exception as e:
        log("Połączenie przerwane: "+str(e));base=None;time.sleep(30)

