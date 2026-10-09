import json,urllib.request
job=json.load(urllib.request.urlopen("http://127.0.0.1:8091/api/diagnostics/repair/search/current?ts=verify572",timeout=5))["job"]
cfg=json.load(urllib.request.urlopen("http://127.0.0.1:8091/api/config",timeout=5))
w=next(x for x in job.get("working_variants",[]) if x.get("live_eligible"))
assert len(w["result_13"])==80 and len(w["result_school"])==385 and int(w.get("missing",0))==0
rows=cfg["state"]["global_constraints"]
def bad(s): return any(ord(c) in {0x00C3,0x00C5,0x00C4,0x00C2} or 0x80<=ord(c)<=0x9f for c in s)
for r in rows:
    for k in ("label","scope","description"):
        if isinstance(r.get(k),str): assert not bad(r[k]),(r["key"],k,r[k])
d={r["key"]:r for r in rows}
assert d["max_day_13"]["label"]=="Maks. dy\u017cur\u00f3w dziennie \u2013 1\u20133"
assert d["max_day_school"]["label"]=="Maks. dy\u017cur\u00f3w dziennie \u2013 ca\u0142a szko\u0142a"
assert d["balance_day"]["label"]=="Wyr\u00f3wnuj liczb\u0119 dy\u017cur\u00f3w w dniu"
assert d["balance_week"]["label"]=="Wyr\u00f3wnuj liczb\u0119 dy\u017cur\u00f3w w tygodniu"
print("PROD_OK",w["coverage13"],w["coverageSchool"],d["max_day_13"]["label"].encode("unicode_escape").decode())
