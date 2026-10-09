from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import app
s=app.load_state()
app.save_state(s)
profiles=app._load_settings_profiles()
needle="day_span_penalty"
state_text=app.STATE_PATH.read_text(encoding="utf-8")
prof_text=app.SETTINGS_PROFILES_PATH.read_text(encoding="utf-8") if app.SETTINGS_PROFILES_PATH.exists() else ""
print("STATE_HAS_REMOVED",needle in state_text)
print("PROFILES_HAVE_REMOVED",needle in prof_text)
print("GLOBAL_CONSTRAINTS",len(app.load_state().get("global_constraints",[])))
print("PROFILES",len(profiles.get("profiles",[])))
