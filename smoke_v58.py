from pathlib import Path
import json, subprocess, sys, time, urllib.request

ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.8-ortools")
sys.path.insert(0,str(ROOT))
import app
import solver_ortools as so

def synthetic_fairness():
    seed={
        "teachers":[
            {"name":"T1","lessons":{"Pn":{"1":[{}],"2":[{}]}}},
            {"name":"T2","lessons":{"Pn":{"1":[{}]}}},
        ],
        "breaks":[
            {"day":"Poniedziałek","abbr":"Pn","label":"1/2","prev":1,"next":2,"minutes":5,"time":""},
            {"day":"Poniedziałek","abbr":"Pn","label":"2/3","prev":2,"next":3,"minutes":5,"time":""},
            {"day":"Poniedziałek","abbr":"Pn","label":"3/4","prev":3,"next":4,"minutes":5,"time":""},
        ],
    }
    positions=[{"day":"Poniedziałek","abbr":"Pn","slot":b["label"],"location":"L","break":b} for b in seed["breaks"]]
    state={
        "global_constraints":[
            {"key":"lesson_load_fairness","enabled":True,"kind":"soft","priority":5},
            {"key":"workload_fairness","enabled":False,"kind":"soft","priority":2},
        ],
        "individual_constraints":[],"manual_blocks":{},"teacher_workload":{"T1":1.0,"T2":1.0},
        "preference_grid":{},"location_zones":{},"solver_seed":123,"deterministic_mode":True,
    }
    arr,_,_,_=so.solve_positions_ortools(state,"szkoła",positions,{"T1","T2"},[],None,seed,{"T1":"school","T2":"school"})
    counts={"T1":0,"T2":0}
    for row in arr: counts[row["teacher"]]+=1
    return counts

def current_edge_violations():
    st=app.load_state()
    bmap={(b["abbr"],b["label"]):b for b in app.SEED.get("breaks",[])}
    tby={t["name"]:t for t in app.SEED.get("teachers",[])}
    rows=[]
    for r in st.get("last_13_assignments",[]):
        for a in r.get("assignments",[]):
            if a.get("teacher"):
                rows.append(("1-3",a["teacher"],r["abbr"],r["label"],a.get("station","")))
    for a in st.get("school_assignments",[]):
        if a.get("teacher"):
            rows.append(("szkoła",a["teacher"],a["abbr"],a["slot"],a.get("location","")))
    out=[]
    for scope,name,abbr,slot,loc in rows:
        br=bmap.get((abbr,slot))
        if not br or int(br.get("minutes",0) or 0)<=5 or name not in tby: continue
        bef=so._is_before_first_lesson(tby,name,br)
        aft=so._is_after_last_lesson(tby,name,br)
        if bef or aft:
            out.append({"scope":scope,"teacher":name,"abbr":abbr,"slot":slot,"minutes":br.get("minutes"),"place":loc,"edge":"before_first" if bef else "after_last"})
    return out

def get_json(url):
    with urllib.request.urlopen(url,timeout=10) as r:
        return json.load(r)

result={"fairness_2_to_1":synthetic_fairness(),"current_edge_violations":current_edge_violations()}
proc=subprocess.Popen([sys.executable,"-m","uvicorn","app:app","--host","127.0.0.1","--port","8092"],cwd=str(ROOT),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    deadline=time.time()+35
    health=None
    while time.time()<deadline:
        try:
            health=get_json("http://127.0.0.1:8092/api/health")
            if health.get("version")=="5.8": break
        except Exception:
            pass
        time.sleep(.5)
    if not health or health.get("version")!="5.8":
        raise RuntimeError("v5.8 health failed")
    cfg=get_json("http://127.0.0.1:8092/api/config")
    teachers=get_json("http://127.0.0.1:8092/api/teachers")
    active=next((x for x in teachers.get("teachers",[]) if x.get("active") and x.get("portal_token")),None)
    portal=None
    if active:
        portal=get_json("http://127.0.0.1:8092/api/teacher-portal/"+active["portal_token"])
    cm={x["key"]:x for x in cfg["state"]["global_constraints"]}
    result.update({
        "health":health,
        "policy":{
            "before_first_long":{k:cm["before_first_long"].get(k) for k in ("enabled","kind","priority")},
            "after_last_long":{k:cm["after_last_long"].get(k) for k in ("enabled","kind","priority")},
            "before_first_short":{k:cm["before_first_short"].get(k) for k in ("enabled","kind","priority")},
            "after_last_short":{k:cm["after_last_short"].get(k) for k in ("enabled","kind","priority")},
        },
        "lesson_fairness_present":"lesson_load_fairness" in cm,
        "manual_fairness_present":"workload_fairness" in cm,
        "portal_timeline":bool(portal and portal.get("timeline")),
        "portal_breaks":len(portal.get("breaks",[])) if portal else 0,
    })
finally:
    proc.terminate()
    try: proc.wait(5)
    except Exception: proc.kill()

(ROOT/"SMOKE-v5.8.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
if result["fairness_2_to_1"]!={"T1":2,"T2":1}: raise SystemExit(2)
if not result.get("portal_timeline"): raise SystemExit(3)
