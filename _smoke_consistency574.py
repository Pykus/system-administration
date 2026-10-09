import json,urllib.request
from pathlib import Path
base="http://127.0.0.1:8098"
eff=json.load(urllib.request.urlopen(base+"/api/effective-plan",timeout=8))
cfg=json.load(urllib.request.urlopen(base+"/api/config",timeout=8))
diag=json.load(urllib.request.urlopen(base+"/api/diagnostics/repair/search/current?ts=consistency574",timeout=8))
src=eff["source"]; sid=src["source_id"]
assert cfg["effective_plan_source"]["source_id"]==sid,(cfg["effective_plan_source"],src)
assert diag["effective_plan_source"]["source_id"]==sid,(diag["effective_plan_source"],src)
if src["kind"]=="live":
    job=diag["job"]
    chosen=next(v for v in (job.get("working_variants") or []) if v.get("live_eligible") is True and v.get("result_13") and v.get("result_school"))
    assert chosen["id"]==src["variant_id"],(chosen["id"],src["variant_id"])

def expected_for(name):
    out=[]
    for a in eff.get("result_13",[]):
        if a.get("teacher")==name: out.append(("1-3",a.get("abbr"),a.get("slot"),str(a.get("station") or ""),int(a.get("wait",0) or 0)))
    for a in eff.get("result_school",[]):
        if a.get("teacher")==name: out.append(("school",a.get("abbr"),a.get("slot"),str(a.get("location") or ""),int(a.get("wait",0) or 0)))
    return sorted(out)

reg=json.loads(Path("data/teacher_registry.json").read_text(encoding="utf-8-sig"))
checked=0
for name,info in reg.items():
    tok=info.get("portal_token")
    if not tok or not info.get("active",True): continue
    portal=json.load(urllib.request.urlopen(base+"/api/teacher-portal/"+tok,timeout=8))
    assert portal["duty_source"]["source_id"]==sid,(name,portal["duty_source"],src)
    got=sorted((d.get("scope"),d.get("abbr"),d.get("slot"),str(d.get("place") or ""),int(d.get("wait",0) or 0)) for d in portal.get("duties",[]))
    exp=expected_for(name)
    assert got==exp,(name,got,exp)
    checked+=1

name="Karolina Malinowska"
dom=expected_for(name)
assert ("school","Pi","7/8","228",0) in dom,dom
info=reg[name]
portal=json.load(urllib.request.urlopen(base+"/api/teacher-portal/"+info["portal_token"],timeout=8))
assert ("school","Pi","7/8","228",0) in sorted((d.get("scope"),d.get("abbr"),d.get("slot"),str(d.get("place") or ""),int(d.get("wait",0) or 0)) for d in portal["duties"])
root=urllib.request.urlopen(base+"/",timeout=8).read().decode("utf-8")
teacher=urllib.request.urlopen(base+"/teacher?t="+info["portal_token"],timeout=8).read().decode("utf-8")
assert "/api/effective-plan?ts=" in root
assert '<input type="checkbox" checked disabled>' in root
assert "effectivePlan?.source?.source_id" in root
assert 'id="dutySource"' in teacher and "refreshDuties" in teacher
print(json.dumps({"version":"5.74","source":src,"teachers_checked":checked,"dominika":dom},ensure_ascii=True))
