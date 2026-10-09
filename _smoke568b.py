import json,urllib.request
from collections import Counter
cfg=json.load(urllib.request.urlopen("http://127.0.0.1:8098/api/config",timeout=5))
j=json.load(urllib.request.urlopen("http://127.0.0.1:8098/api/diagnostics/repair/search/current?ts=smoke568b",timeout=5))
job=j.get("job") or {}
live=next((x for x in job.get("working_variants",[]) if x.get("live_eligible")),None)
assert live
rows=live.get("result_school",[])
mins=(cfg.get("state") or {}).get("min_people_school") or {}
cnt=Counter((x.get("abbr"),x.get("slot"),x.get("location")) for x in rows if x.get("teacher"))
missing=[]
for k,v in mins.items():
    req=int(v or 0)
    if req<=0: continue
    ab,slot,loc=k.split("|",2)
    have=cnt[(ab,slot,loc)]
    if have<req: missing.append((k,req,have))
entrance="wej\u015bcie"
e01=[x for x in rows if x.get("slot")=="0/1" and x.get("location")==entrance and x.get("teacher")]
assert not missing,missing[:10]
assert {x.get("abbr") for x in e01}=={"Pn","Wt","\u015ar","Czw","Pi"}
def suspicious(x):
    if isinstance(x,str):
        return any(c in x for c in ("\u00c2","\u00c3","\u00c4","\u00c5")) or any(0x80<=ord(c)<=0x9f for c in x)
    if isinstance(x,list): return any(suspicious(z) for z in x)
    if isinstance(x,dict): return any(suspicious(z) for z in x.values())
    return False
assert not suspicious(job)
print(json.dumps({"coverage13":live.get("coverage13"),"coverageSchool":live.get("coverageSchool"),"missing_recomputed":len(missing),"opening_entrance":len(e01),"opening_days":sorted(x.get("abbr") for x in e01),"after_last_long":live.get("after_last_long")},ensure_ascii=True))
