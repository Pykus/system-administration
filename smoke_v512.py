
import json,time,urllib.request
BASE="http://127.0.0.1:8092"
def get(path,timeout=30):
    with urllib.request.urlopen(BASE+path,timeout=timeout) as r:return json.load(r)
def text(path,timeout=30):
    with urllib.request.urlopen(BASE+path,timeout=timeout) as r:return r.read().decode("utf-8","replace")
def post(path,obj=None,timeout=60):
    data=json.dumps(obj or {},ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(BASE+path,data=data,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)

h=get("/api/health"); cfg=get("/api/config"); farm=get("/api/worker-farm/status"); html=text("/")
assert h["version"]=="5.12",h
for marker in ("Dyżury v5.12","grupa 1–3 jest zawsze wykluczona","nierozstrzygnięte","To nie jest dowód braku rozwiązania"):
    assert marker in html,marker
assert "+ 1–3 awaryjnie" not in html
assert farm["enabled"] is False and not farm["broker_running"],farm

teachers=cfg["teachers"]; groups={t["name"]:t.get("group") for t in teachers}; all_names=list(groups)
post("/api/state",{"enabled_teachers_school":all_names})
cfg2=get("/api/config")
school_pool=cfg2["state"]["enabled_teachers_school"]
assert not [n for n in school_pool if groups.get(n)=="1-3"],"1-3 leaked into saved school pool"

solve=post("/api/solve/school",{"enabled_teachers":all_names},timeout=90)
bad_assign=[a for a in solve.get("assignments",[]) if a.get("teacher") and groups.get(a["teacher"])=="1-3"]
assert not bad_assign,bad_assign[:5]
assert solve.get("diagnostics",{}).get("status") not in ("MODEL_INVALID","ERROR"),solve.get("diagnostics")

s=cfg2["state"]
body={"global":s.get("global_constraints",[]),"individual":s.get("individual_constraints",[]),
"min_people_13":s.get("min_people_13",{}),"min_people_school":s.get("min_people_school",{}),
"school_locations":s.get("school_locations",[]),"manual_blocks":s.get("manual_blocks",{}),
"preference_grid":s.get("preference_grid",{}),"locked_assignments":s.get("locked_assignments",[]),
"last_13_assignments":s.get("last_13_assignments",[]),"school_assignments":s.get("school_assignments",[]),
"enabled_teachers_13":s.get("enabled_teachers_13",[]),"enabled_teachers_school":school_pool}
job=post("/api/diagnostics/repair/search",body); jid=job["id"]; samples=[]
for _ in range(50):
    time.sleep(1)
    x=get("/api/diagnostics/repair/search/"+jid)
    samples.append({k:x.get(k) for k in ("status","stage","checked","estimated_total","local_workers_configured","local_active","local_completed","inconclusive_trials","progress","best_missing")})
    if x.get("status") in ("error","completed"):break
    if (x.get("local_workers_configured") or 0)>=1 and (x.get("local_active") or 0)>0:break
last=get("/api/diagnostics/repair/search/"+jid)
if last.get("status") not in ("completed","error","cancelled"):
    last=post("/api/diagnostics/repair/search/"+jid+"/cancel")
assert last.get("status")!="error",last
assert any((z.get("local_workers_configured") or 0)==4 for z in samples) or last.get("status")=="completed",samples[-5:]
out={"health":h,"farm":{"enabled":farm["enabled"],"broker_running":farm["broker_running"],"local_workers":farm["local_workers"]},
     "school_pool":len(school_pool),"school_solve":{"filled":solve["summary"]["filled_positions"],"required":solve["summary"]["required_positions"],
     "status":solve["diagnostics"].get("status"),"inconclusive":solve["diagnostics"].get("inconclusive")},
     "repair_samples":samples[-6:],"repair_final":last.get("status")}
print(json.dumps(out,ensure_ascii=True,indent=2))
