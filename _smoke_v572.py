import json,urllib.request
j=json.load(urllib.request.urlopen("http://127.0.0.1:8098/api/config",timeout=5))
rows=j["state"]["global_constraints"]
def bad(s): return any(ord(c) in {0x00C3,0x00C5,0x00C4,0x00C2} or 0x80<=ord(c)<=0x9f for c in s)
for r in rows:
 for k in ("label","scope","description"):
  if isinstance(r.get(k),str): assert not bad(r[k]),(r["key"],k,r[k])
d={r["key"]:r for r in rows}
expected={
 "max_day_13":"Maks. dy\u017cur\u00f3w dziennie \u2013 1\u20133",
 "max_day_school":"Maks. dy\u017cur\u00f3w dziennie \u2013 ca\u0142a szko\u0142a",
 "max_week":"Maks. dy\u017cur\u00f3w tygodniowo",
 "balance_day":"Wyr\u00f3wnuj liczb\u0119 dy\u017cur\u00f3w w dniu",
 "balance_week":"Wyr\u00f3wnuj liczb\u0119 dy\u017cur\u00f3w w tygodniu",
}
for k,v in expected.items(): assert d[k]["label"]==v,(k,d[k]["label"])
assert d["max_day_13"]["scope"]=="1\u20133"
assert d["max_day_school"]["scope"]=="szko\u0142a"
print(json.dumps({k:d[k]["label"] for k in expected},ensure_ascii=True))
