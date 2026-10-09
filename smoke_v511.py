import json,time,urllib.request
BASE="http://127.0.0.1:8092"
def get(path):
    with urllib.request.urlopen(BASE+path,timeout=15) as r:return json.load(r)
def post(path,obj=None):
    data=json.dumps(obj or {}).encode("utf-8")
    req=urllib.request.Request(BASE+path,data=data,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)

health=get("/api/health")
farm=get("/api/worker-farm/status")
cfg=get("/api/config");s=cfg["state"]
body={"global":s.get("global_constraints",[]),"individual":s.get("individual_constraints",[]),
      "min_people_13":s.get("min_people_13",{}),"min_people_school":s.get("min_people_school",{}),
      "school_locations":s.get("school_locations",[]),"manual_blocks":s.get("manual_blocks",{}),
      "preference_grid":s.get("preference_grid",{}),"locked_assignments":s.get("locked_assignments",[]),
      "last_13_assignments":s.get("last_13_assignments",[]),"school_assignments":s.get("school_assignments",[]),
      "enabled_teachers_13":s.get("enabled_teachers_13",[]),"enabled_teachers_school":s.get("enabled_teachers_school",[])}
job=post("/api/diagnostics/repair/search",body);jid=job["id"]
samples=[]
for _ in range(10):
    time.sleep(1)
    x=get("/api/diagnostics/repair/search/"+jid)
    samples.append({"status":x.get("status"),"stage":x.get("stage"),"checked":x.get("checked"),
                    "local_workers_configured":x.get("local_workers_configured"),
                    "local_active":x.get("local_active"),"local_completed":x.get("local_completed"),
                    "remote_completed":x.get("remote_completed"),"suggestions":len(x.get("suggestions",[])),
                    "search_policy":x.get("search_policy")})
    if x.get("status") in ("completed","error"):break
paused=post("/api/diagnostics/repair/search/"+jid+"/pause")
time.sleep(1)
paused2=get("/api/diagnostics/repair/search/"+jid)
resumed=post("/api/diagnostics/repair/search/"+jid+"/resume")
time.sleep(2)
after=get("/api/diagnostics/repair/search/"+jid)
cancelled=post("/api/diagnostics/repair/search/"+jid+"/cancel")
out={"health":health,"farm":farm,"samples":samples,"paused":paused2.get("status"),
     "resumed":after.get("status"),"cancelled":cancelled.get("status")}
print(json.dumps(out,ensure_ascii=False,indent=2))
assert health.get("version")=="5.11"
assert farm.get("local_workers")==4
assert farm.get("enabled") is False
assert any((x.get("local_workers_configured") or 0)==4 for x in samples)
assert all("OSTATNIA" not in str(x.get("stage")) for x in samples[:2])
assert paused2.get("status") in ("paused","completed")
assert cancelled.get("status") in ("cancelled","completed")
