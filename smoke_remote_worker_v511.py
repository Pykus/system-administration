import json,time,urllib.request
BASE="http://127.0.0.1:8092"
def get(p):
    with urllib.request.urlopen(BASE+p,timeout=15) as r:return json.load(r)
def post(p,obj=None):
    data=json.dumps(obj or {}).encode()
    req=urllib.request.Request(BASE+p,data=data,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
s=get("/api/config")["state"]
body={k:s.get(k) for k in ("global_constraints","individual_constraints","min_people_13","min_people_school","school_locations","manual_blocks","preference_grid","locked_assignments","last_13_assignments","school_assignments")}
body["global"]=body.pop("global_constraints");body["individual"]=body.pop("individual_constraints")
body["enabled_teachers_13"]=s.get("enabled_teachers_13",[]);body["enabled_teachers_school"]=s.get("enabled_teachers_school",[])
j=post("/api/diagnostics/repair/search",body);jid=j["id"]
hist=[]
deadline=time.time()+50
while time.time()<deadline:
    time.sleep(1)
    x=get("/api/diagnostics/repair/search/"+jid)
    f=get("/api/worker-farm/status")
    hist.append({"stage":x.get("stage"),"checked":x.get("checked"),"local_active":x.get("local_active"),
                 "local_completed":x.get("local_completed"),"remote_completed":x.get("remote_completed"),
                 "workers_online":f.get("workers_online"),"tasks":f.get("tasks")})
    if (x.get("remote_completed") or 0)>=1 or x.get("status") in ("completed","error"): break
post("/api/diagnostics/repair/search/"+jid+"/cancel")
print(json.dumps({"job":jid,"last":hist[-1] if hist else None,"tail":hist[-8:]},ensure_ascii=False,indent=2))
if not hist or (hist[-1].get("remote_completed") or 0)<1:
    raise SystemExit(2)
