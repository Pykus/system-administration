import json,time,urllib.request,urllib.parse,sys
from pathlib import Path
sys.path.insert(0,r"C:\DutySolverDemo\dyzury-v5.77-ortools")
import app
base="http://127.0.0.1:8098"
def get(path,timeout=8):
    return json.load(urllib.request.urlopen(base+path,timeout=timeout))
def post(path,obj,timeout=8):
    data=json.dumps(obj).encode()
    req=urllib.request.Request(base+path,data=data,headers={"Content-Type":"application/json"},method="POST")
    return json.load(urllib.request.urlopen(req,timeout=timeout))

root=urllib.request.urlopen(base+"/",timeout=5)
ct=root.headers.get("Content-Type",""); html=root.read().decode("utf-8")
assert "text/html" in ct and "<html" in html.lower() and len(html)>10000,(ct,len(html))
before=get("/api/effective-plan?ts=before")
assert before["source"]["kind"]=="reference_verified",before["source"]
assert before["audit"]["ok"] and before["audit"]["filled13_real"]==before["audit"]["required13"] and before["audit"]["filledSchool_real"]==before["audit"]["requiredSchool"],before["audit"]
print("REFERENCE_OK",before["source"]["source_id"],before["audit"],flush=True)

job=post("/api/diagnostics/repair/search",{"force_restart":True,"fresh_start":True,"continuous_search":True})
jid=job["id"]
assert job.get("fresh_start") and not job.get("working_variants"),job
print("FRESH_JOB",jid,flush=True)

deadline=time.time()+720
last_print=0
live=None
cur=None
while time.time()<deadline:
    time.sleep(5)
    cur=get("/api/diagnostics/repair/search/current?ts="+str(time.time()))
    eff=get("/api/effective-plan?ts="+str(time.time()))
    now=time.time()
    if now-last_print>=15:
        j=cur["job"]
        print("PROGRESS",json.dumps({
            "status":j.get("status"),"stage":j.get("stage"),"checked":j.get("checked"),
            "best_missing":j.get("best_missing"),"lowest_live_stage":j.get("lowest_live_stage"),
            "wf_unlocked":j.get("wf_fallback_unlocked"),"after_unlocked":j.get("after_last_long_unlocked"),
            "wf_targeted_success":j.get("wf_targeted_success"),"suggestions":len(j.get("suggestions") or []),
            "source":eff.get("source",{}).get("kind")
        },ensure_ascii=True),flush=True)
        last_print=now
    if eff.get("source",{}).get("kind")=="live_verified":
        live=eff;break
    if cur.get("job",{}).get("status") in ("error","failed","cancelled"):
        raise AssertionError(cur["job"])

assert live is not None,"no live_verified result before timeout"
state=app.load_state()
audit=live["audit"]
assert audit["ok"],audit
r13=live["result_13"]; rs=live["result_school"]
wf=[a for a in r13+rs if a.get("teacher") and app.GROUP.get(a.get("teacher"))=="wf"]
locked=app._locked_wf_assignment_count_v577(state)
automatic_wf=max(0,len(wf)-locked)
bm=app.break_map()
after=[]
for a in r13+rs:
    t=a.get("teacher"); br=bm.get((a.get("abbr"),a.get("slot")))
    if t and br and int(br.get("minutes",0) or 0)>app.SHORT_BREAK_MAX_MINUTES and app.is_after_last_lesson(t,br):
        after.append(a)
waits=[a for a in r13+rs if int(a.get("wait",0) or 0)>0]
assert automatic_wf<=1,("too many automatic WF",automatic_wf,wf)
assert not after,("after_last_long used before needed",after)
assert not waits,("additional wait used before needed",waits)
j=cur["job"]
assert not j.get("after_last_long_unlocked"),j.get("after_last_long_unlock_reason")
assert int(j.get("lowest_live_stage",99) or 99)<=4
assert cur["effective_plan_source"]["source_id"]==live["source"]["source_id"]

# Every teacher portal must use exactly the same source and exact filtered assignments.
reg=json.loads(Path(r"C:\DutySolverDemo\dyzury-v5.77-ortools\data\teacher_registry.json").read_text(encoding="utf-8-sig"))
def expected(name):
    out=[]
    for a in r13:
        if a.get("teacher")==name: out.append(("1-3",a.get("abbr"),a.get("slot"),str(a.get("station") or "")))
    for a in rs:
        if a.get("teacher")==name: out.append(("school",a.get("abbr"),a.get("slot"),str(a.get("location") or "")))
    return sorted(out)
checked=0
for name,info in reg.items():
    tok=info.get("portal_token")
    if not tok or not info.get("active",True):continue
    po=get("/api/teacher-portal/"+urllib.parse.quote(tok,safe=""))
    assert po["duty_source"]["source_id"]==live["source"]["source_id"],(name,po["duty_source"],live["source"])
    got=sorted((x.get("scope"),x.get("abbr"),x.get("slot"),str(x.get("place") or "")) for x in po.get("duties",[]))
    assert got==expected(name),(name,got,expected(name))
    checked+=1

print("LIVE_GATE_OK",json.dumps({
    "source_id":live["source"]["source_id"],
    "audit":audit,
    "automatic_wf":automatic_wf,
    "wf_total":len(wf),
    "wf_teachers":sorted({a.get("teacher") for a in wf}),
    "after_last_long":len(after),
    "waits":len(waits),
    "lowest_live_stage":j.get("lowest_live_stage"),
    "after_unlocked":j.get("after_last_long_unlocked"),
    "teachers_checked":checked,
    "checked_trials":j.get("checked")
},ensure_ascii=True),flush=True)
