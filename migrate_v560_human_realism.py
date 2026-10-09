import json
import app

s=app.load_state()
before=next((dict(r) for r in s.get("global_constraints",[]) if r.get("key")=="max_consecutive_duties"),{})
app.save_state(s)
after=next((dict(r) for r in app.load_state().get("global_constraints",[]) if r.get("key")=="max_consecutive_duties"),{})
print(json.dumps({
    "human_realism_v560_migrated": bool(s.get("human_realism_v560_migrated")),
    "max_consecutive_before_normalized": before,
    "max_consecutive_persisted": after,
    "never_auto_relax": sorted(app.NEVER_AUTO_RELAX_KEYS),
},ensure_ascii=False,indent=2))
