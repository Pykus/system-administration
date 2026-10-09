import json,time,urllib.request
BASE="http://127.0.0.1:8092"
def get(path):
    with urllib.request.urlopen(BASE+path,timeout=20) as r:return json.load(r)
def post(path,obj=None):
    data=json.dumps(obj or {}).encode()
    req=urllib.request.Request(BASE+path,data=data,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
cfg=get("/api/config"); s=cfg["state"]
body={
 "global":s.get("global_constraints",[]),"individual":s.get("individual_constraints",[]),
 "min_people_13":s.get("min_people_13",{}),"min_people_school":s.get("min_people_school",{}),
 "school_locations":s.get("school_locations",[]),"manual_blocks":s.get("manual_blocks",{}),
 "preference_grid":s.get("preference_grid",{}),"locked_assignments":s.get("locked_assignments",[]),
 "last_13_assignments":s.get("last_13_assignments",[]),"school_assignments":s.get("school_assignments",[]),
 "enabled_teachers_13":s.get("enabled_teachers_13",[]),"enabled_teachers_school":s.get("enabled_teachers_school",[])
}
j=post("/api/diagnostics/repair/search",body); jid=j["id"]
time.sleep(2)
a=get("/api/diagnostics/repair/search/"+jid)
p=post("/api/diagnostics/repair/search/"+jid+"/pause")
time.sleep(1)
p2=get("/api/diagnostics/repair/search/"+jid)
r=post("/api/diagnostics/repair/search/"+jid+"/resume")
time.sleep(3)
b=get("/api/diagnostics/repair/search/"+jid)
c=post("/api/diagnostics/repair/search/"+jid+"/cancel")
out={"start":j,"after2":a,"paused":p2,"after_resume":b,"cancelled":c}
print(json.dumps(out,ensure_ascii=False,indent=2))
assert a["checked"]>=0 and a["estimated_total"]>=1
assert p2["status"]=="paused"
assert b["status"] in ("running","completed")
assert c["status"]=="cancelled"
