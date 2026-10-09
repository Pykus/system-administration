import json,urllib.request
from collections import Counter
cfg=json.load(urllib.request.urlopen("http://127.0.0.1:8098/api/config",timeout=5))
j=json.load(urllib.request.urlopen("http://127.0.0.1:8098/api/diagnostics/repair/search/current?ts=smoke568",timeout=5))
job=j.get("job") or {}
live=next((x for x in job.get("working_variants",[]) if x.get("live_eligible")),None)
assert live, "no live variant"
rows=live.get("result_school",[])
mins=(cfg.get("state") or {}).get("min_people_school") or {}
cnt=Counter((x.get("abbr"),x.get("slot"),x.get("location")) for x in rows if x.get("teacher"))
missing=[]
for k,v in mins.items():
    req=int(v or 0)
    if req<=0: continue
    ab,slot,loc=k.split("|",2)
    if cnt[(ab,slot,loc)]<req: missing.append((k,req,cnt[(ab,slot,loc)]))
entrance="wej\u015bcie"
e01=[x for x in rows if x.get("slot")=="0/1" and x.get("location")==entrance and x.get("teacher")]
assert not missing, missing[:10]
assert {x.get("abbr") for x in e01}=={"Pn","Wt","\u015ar","Czw","Pi"}, e01
blob=json.dumps(job,ensure_ascii=False)
for bad in ("\u00c5\u009b","\u00c5\u0082","\u00c3\u00b3","\u00c5\u009a","\u00c4\u0085"):
    assert bad not in blob, bad
locks=(cfg.get("state") or {}).get("locked_assignments") or []
assert all("comment" in x for x in locks if isinstance(x,dict))
print(json.dumps({"status":job.get("status"),"live_seq":live.get("seq"),"coverageSchool":live.get("coverageSchool"),"coverage13":live.get("coverage13"),"missing_recomputed":len(missing),"opening_entrance":len(e01),"opening_days":sorted(x.get("abbr") for x in e01),"sample_locations":sorted(set(x.get("location") for x in rows))[:8]},ensure_ascii=True))
