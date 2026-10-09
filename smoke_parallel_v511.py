import json,time,urllib.request
BASE="http://127.0.0.1:8092"
def get(path):
    with urllib.request.urlopen(BASE+path,timeout=15) as r:return json.load(r)
def post(path,obj=None):
    data=json.dumps(obj or {}).encode("utf-8")
    req=urllib.request.Request(BASE+path,data=data,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)

health=get("/api/health"); farm=get("/api/worker-farm/status"); cfg=get("/api/config"); s=cfg["state"]
body={"global":s.get("global_constraints",[]),"individual":s.get("individual_constraints",[]),
"min_people_13":s.get("min_people_13",{}),"min_people_school":s.get("min_people_school",{}),
"school_locations":s.get("school_locations",[]),"manual_blocks":s.get("manual_blocks",{}),
"preference_grid":s.get("preference_grid",{}),"locked_assignments":s.get("locked_assignments",[]),
"last_13_assignments":s.get("last_13_assignments",[]),"school_assignments":s.get("school_assignments",[]),
"enabled_teachers_13":s.get("enabled_teachers_13",[]),"enabled_teachers_school":s.get("enabled_teachers_school",[])}
job=post("/api/diagnostics/repair/search",body); jid=job["id"]; samples=[]
for _ in range(30):
    time.sleep(1)
    x=get("/api/diagnostics/repair/search/"+jid)
    samples.append({k:x.get(k) for k in ("status","stage","checked","estimated_total","local_workers_configured","local_active","local_completed","remote_completed","progress","search_policy")})
    if (x.get("local_workers_configured") or 0)==4 and (x.get("local_active") or 0)>0: break
    if x.get("status") in ("completed","error"): break
p=post("/api/diagnostics/repair/search/"+jid+"/pause"); time.sleep(1); p2=get("/api/diagnostics/repair/search/"+jid)
if p2.get("status")=="paused":
    post("/api/diagnostics/repair/search/"+jid+"/resume"); time.sleep(2)
a=get("/api/diagnostics/repair/search/"+jid)
c=post("/api/diagnostics/repair/search/"+jid+"/cancel")
out={"health":health,"farm":{"enabled":farm["enabled"],"local_workers":farm["local_workers"],"broker_running":farm["broker_running"]},
     "samples":samples[-8:],"paused":p2.get("status"),"after_resume":a.get("status"),"cancelled":c.get("status")}
print(json.dumps(out,ensure_ascii=False,indent=2))
assert health.get("version")=="5.11"
assert farm.get("enabled") is False and farm.get("local_workers")==4
assert any((z.get("local_workers_configured") or 0)==4 for z in samples), samples
assert all("OSTATNIA" not in str(z.get("stage")) for z in samples if (z.get("checked") or 0)<2)
assert c.get("status") in ("cancelled","completed")
