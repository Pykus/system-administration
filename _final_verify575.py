import json,urllib.request,time
from pathlib import Path
base="http://127.0.0.1:8091"
t=time.perf_counter()
eff=json.load(urllib.request.urlopen(base+"/api/effective-plan?ts=final575",timeout=4))
lat=round((time.perf_counter()-t)*1000)
cfg=json.load(urllib.request.urlopen(base+"/api/config",timeout=4))
diag=json.load(urllib.request.urlopen(base+"/api/diagnostics/repair/search/current?ts=final575",timeout=4))
sid=eff["source"]["source_id"]
assert eff["source"]["kind"]=="live",eff["source"]
assert cfg["effective_plan_source"]["source_id"]==sid
assert diag["effective_plan_source"]["source_id"]==sid
assert len(eff["result_13"])==80 and len(eff["result_school"])==385
chosen=next(v for v in diag["job"].get("working_variants",[]) if v.get("live_eligible") is True and v.get("result_13") and v.get("result_school"))
assert chosen["id"]==eff["source"]["variant_id"]

def exp(name):
 out=[]
 for a in eff["result_13"]:
  if a.get("teacher")==name:out.append(("1-3",a.get("abbr"),a.get("slot"),str(a.get("station") or ""),int(a.get("wait",0) or 0)))
 for a in eff["result_school"]:
  if a.get("teacher")==name:out.append(("school",a.get("abbr"),a.get("slot"),str(a.get("location") or ""),int(a.get("wait",0) or 0)))
 return sorted(out)

reg=json.loads(Path("data/teacher_registry.json").read_text(encoding="utf-8-sig"))
checked=0
for name,info in reg.items():
 tok=info.get("portal_token")
 if not tok or not info.get("active",True):continue
 po=json.load(urllib.request.urlopen(base+"/api/teacher-portal/"+tok,timeout=4))
 assert po["duty_source"]["source_id"]==sid,(name,po["duty_source"],eff["source"])
 got=sorted((d.get("scope"),d.get("abbr"),d.get("slot"),str(d.get("place") or ""),int(d.get("wait",0) or 0)) for d in po.get("duties",[]))
 assert got==exp(name),(name,got,exp(name))
 checked+=1

dom=exp("Karolina Malinowska")
assert ("school","Pi","7/8","228",0) in dom,dom
root=urllib.request.urlopen(base+"/",timeout=4).read().decode("utf-8")
assert "/api/effective-plan?ts=" in root
assert '<input type="checkbox" checked disabled>' in root
assert "effectivePlan?.source?.source_id" in root
print(json.dumps({"version":"5.75","source_id":sid,"effective_ms":lat,"job_status":diag["job"].get("status"),"teachers_checked":checked,"dominika":dom},ensure_ascii=True))
