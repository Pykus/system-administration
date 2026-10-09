import json, urllib.request
from collections import Counter
job_id="d9ca7e95b5104ee488e98d415ed3ed4b"
cur=json.load(urllib.request.urlopen("http://127.0.0.1:8091/api/diagnostics/repair/search/current?ts=pre569resume",timeout=8))
assert cur["job"]["id"]==job_id,cur["job"].get("id")
req=urllib.request.Request("http://127.0.0.1:8091/api/diagnostics/repair/search",
    data=json.dumps({"continuous_search":True}).encode("utf-8"),
    headers={"Content-Type":"application/json"},method="POST")
res=json.load(urllib.request.urlopen(req,timeout=10))
assert res["id"]==job_id,res.get("id")
cur=json.load(urllib.request.urlopen("http://127.0.0.1:8091/api/diagnostics/repair/search/current?ts=verify569",timeout=8))
job=cur["job"]
live=[x for x in job.get("working_variants",[]) if x.get("live_eligible")]
assert live
w=live[0]
assert w["coverage13"]=={"required":80,"filled":80,"missing":0},w["coverage13"]
assert w["coverageSchool"]=={"required":385,"filled":385,"missing":0},w["coverageSchool"]
rows=w["result_school"]
cfg=json.load(urllib.request.urlopen("http://127.0.0.1:8091/api/config",timeout=8))["state"]
cnt=Counter((x.get("abbr"),x.get("slot"),x.get("location")) for x in rows if x.get("teacher"))
missing=[]
for k,v in (cfg.get("min_people_school") or {}).items():
    req=int(v or 0)
    if req<=0: continue
    key=tuple(k.split("|",2))
    if cnt[key]<req: missing.append((k,req,cnt[key]))
assert not missing,missing[:10]
entrance="wej\u015bcie"
e01=[x for x in rows if x.get("slot")=="0/1" and x.get("location")==entrance and x.get("teacher")]
assert {x.get("abbr") for x in e01}=={"Pn","Wt","\u015ar","Czw","Pi"},e01
blob=json.dumps(job,ensure_ascii=False)
for bad in ("\u00c2","\u00c3","\u00c4","\u00c5"):
    assert bad not in blob,bad
assert str(job.get("stage"))=="Wznowienie z pe\u0142nej kotwicy",repr(job.get("stage"))
page=urllib.request.urlopen("http://127.0.0.1:8091/",timeout=8).read().decode("utf-8")
assert "liveDisplaySnapshot" in page
assert "lockDraft13.comment" in page and "lockDraftSchool.comment" in page
print("VERIFY_OK",job["id"],job["status"],job["stage"],w["coverage13"],w["coverageSchool"],"MISSING",len(missing),"ENTRANCE01",len(e01),"AFTER",w.get("after_last_long"))
