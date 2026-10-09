import json,urllib.request,urllib.error
from pathlib import Path
base="http://127.0.0.1:8098"
reg=json.loads(Path("data/teacher_registry.json").read_text(encoding="utf-8"))
name,info=next((n,r) for n,r in reg.items() if r.get("active",True) and r.get("portal_token"))
token=info["portal_token"]
portal=json.load(urllib.request.urlopen(f"{base}/api/teacher-portal/{token}",timeout=5))
assert "preference_comments" in portal
prefs=dict(portal.get("preferences") or {})
comments=dict(portal.get("preference_comments") or {})
order=list(portal.get("relax_order") or [])
locks={f"{r.get('abbr')}|{r.get('slot')}" for r in portal.get("admin_locks",[]) or []}
breaks=portal.get("breaks") or []
key=next(f"{b.get('abbr')}|{b.get('label')}" for b in breaks if b.get("abbr") and b.get("label") and f"{b.get('abbr')}|{b.get('label')}" not in locks)
orig=dict(comments)
comments[key]="SMOKE-v570"
payload=json.dumps({"preferences":prefs,"comments":comments,"relax_order":order},ensure_ascii=False).encode("utf-8")
req=urllib.request.Request(f"{base}/api/teacher-portal/{token}/preferences",data=payload,headers={"Content-Type":"application/json"},method="POST")
out=json.load(urllib.request.urlopen(req,timeout=5))
assert out.get("ok") is True
assert out.get("solver_input_changed") is False, out
again=json.load(urllib.request.urlopen(f"{base}/api/teacher-portal/{token}",timeout=5))
assert again.get("preference_comments",{}).get(key)=="SMOKE-v570"
# restore comments-only state
payload=json.dumps({"preferences":prefs,"comments":orig,"relax_order":order},ensure_ascii=False).encode("utf-8")
req=urllib.request.Request(f"{base}/api/teacher-portal/{token}/preferences",data=payload,headers={"Content-Type":"application/json"},method="POST")
restore=json.load(urllib.request.urlopen(req,timeout=5))
assert restore.get("solver_input_changed") is False
root=urllib.request.urlopen(base+"/",timeout=5).read().decode("utf-8")
teacher_html=urllib.request.urlopen(base+"/teacher?t="+token,timeout=5).read().decode("utf-8")
assert root.count("Blokady / sta&#322;e przydzia&#322;y dla nauczyciela")>=2
assert 'v-if="adminConstraintModal"' in root
assert "data-comment-k" in teacher_html and "comments:prefComments" in teacher_html
print(json.dumps({"health":"5.70","teacher_api":True,"comment_roundtrip":True,"comment_only_solver_change":False,"admin_unified_ui":True,"teacher_ui_comment":True},ensure_ascii=True))
