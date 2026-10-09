import json,urllib.request
from pathlib import Path
base="http://127.0.0.1:8098"
eff=json.load(urllib.request.urlopen(base+"/api/effective-plan",timeout=4))
reg=json.loads(Path("data/teacher_registry.json").read_text(encoding="utf-8-sig"))
tok=reg["Karolina Malinowska"]["portal_token"]
po=json.load(urllib.request.urlopen(base+"/api/teacher-portal/"+tok,timeout=4))
assert po["duty_source"]["source_id"]==eff["source"]["source_id"]
got=sorted((d["scope"],d["abbr"],d["slot"],str(d["place"])) for d in po["duties"])
assert ("school","Pi","7/8","228") in got,got
print(json.dumps({"source_id":eff["source"]["source_id"],"dominika":got},ensure_ascii=True))
