import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).parent
PORT=8092
BASE=f"http://127.0.0.1:{PORT}"

def get(path):
    with urllib.request.urlopen(BASE+path,timeout=10) as r:
        return json.load(r)

def post(path,obj):
    data=json.dumps(obj,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(BASE+path,data=data,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.load(r)

proc=subprocess.Popen(
    [sys.executable,"-m","uvicorn","app:app","--host","127.0.0.1","--port",str(PORT)],
    cwd=str(ROOT),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
result={"version":None,"constraints":0,"solve13":None,"solveSchool":None,"alicja_wait_violations":[]}
try:
    for _ in range(50):
        try:
            info=get("/openapi.json")["info"]
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("Lokalna aplikacja nie wystartowała")

    result["version"]=info["version"]
    if info["version"]!="5.7":
        raise AssertionError(info)

    cfg=get("/api/config")
    state=cfg["state"]
    cons=state["global_constraints"]
    result["constraints"]=len(cons)
    assert cons and all(c.get("kind") in ("hard","soft") for c in cons)
    assert all(c.get("priority") in (1,2,3,4,5) for c in cons)
    by={c["key"]:c for c in cons}
    assert by["max_long_day"]["value"]==1 and 0<=by["max_long_day"]["value"]<=2
    assert 0<=by["max_long_week"]["value"]<=10
    aw=next(c for c in cons if c["key"]=="avoid_wait")
    assert aw["enabled"] and aw["kind"]=="hard"

    # Regression: pusty seed z UI nie może powodować HTTP 500.
    post("/api/state",{"solver_seed":""})
    safe_state=get("/api/config")["state"]
    assert safe_state["solver_seed"]==20260918
    state=safe_state

    s13=post("/api/solve/13",{
        "enabled_teachers":state["enabled_teachers_13"],
        "manual_blocks":state.get("manual_blocks",{})
    })
    result["solve13"]=s13["summary"]
    assert s13["diagnostics"]["engine"]=="OR-Tools CP-SAT"
    assert s13["summary"]["wait_assignments"]==0
    assert not s13.get("waits")

    for row in s13["rows"]:
        for a in row.get("assignments",[]):
            if a.get("teacher")=="Alicja Kowalska" and int(a.get("wait") or 0)>0:
                result["alicja_wait_violations"].append({"abbr":row["abbr"],"slot":row["label"],"wait":a["wait"]})
    assert not result["alicja_wait_violations"]

    school=post("/api/solve/school",{
        "enabled_teachers":state["enabled_teachers_school"],
        "manual_blocks":state.get("manual_blocks",{})
    })
    result["solveSchool"]=school["summary"]
    assert school["diagnostics"]["engine"]=="OR-Tools CP-SAT"
    assert school["summary"]["wait_assignments"]==0
    assert not school.get("waits")

    print(json.dumps({"ok":True,**result},ensure_ascii=False,indent=2))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
