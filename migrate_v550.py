from pathlib import Path
import copy, json, sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import app

before_raw=json.loads(app.STATE_PATH.read_text(encoding="utf-8"))
before_assign13=copy.deepcopy(before_raw.get("last_13_assignments",[]))
before_school=copy.deepcopy(before_raw.get("school_assignments",[]))
before_manual=copy.deepcopy(before_raw.get("manual_blocks",{}))
before_locked=copy.deepcopy(before_raw.get("locked_assignments",[]))

s=app.load_state()
changes=app._apply_timetable_staffing(s)
s["last_auto_staffing_changes"]=changes

# Refresh derived 1-3 row metadata without changing actual assignments.
for row in s.get("last_13_assignments",[]) or []:
    ab=str(row.get("abbr") or "")
    slot=str(row.get("label") or row.get("slot") or "")
    required=app._required_stations_13(s,ab,slot) if ab and slot else []
    need=len(required)
    assigned=row.get("assignments",[]) or []
    filled=sum(1 for a in assigned if a.get("teacher") and a.get("station") in required)
    row["required_people"]=need
    row["complete"]=bool(filled>=need)

if changes:
    app._plan_event(s,"migration_v550_staffing",
                    f"v5.50: zaktualizowano wymagania obsady z planu lekcji ({len(changes)} zmian).",
                    changes[:100])
app.save_state(s)
app._load_settings_profiles()
after=app.load_state()

print("VERSION",app.PLANNER_VERSION)
print("CONSTRAINTS",len(after.get("global_constraints",[])))
print("CHANGES",len(changes))
for x in changes:
    print("CHANGE",json.dumps(x,ensure_ascii=False))
print("ASSIGNMENTS_13_SAME",before_assign13==after.get("last_13_assignments",[]))
print("SCHOOL_ASSIGNMENTS_SAME",before_school==after.get("school_assignments",[]))
print("MANUAL_BLOCKS_SAME",before_manual==after.get("manual_blocks",{}))
print("LOCKED_ASSIGNMENTS_SAME",before_locked==after.get("locked_assignments",[]))
print("REMOVED_KEYS_PRESENT",sorted(set(app.REMOVED_CONSTRAINT_KEYS)&{r.get("key") for r in after.get("global_constraints",[])}))
print("FORBID_IN_STATE",'"forbid"' in app.STATE_PATH.read_text(encoding="utf-8"))
print("FORBID_IN_PROFILES",'"forbid"' in app.SETTINGS_PROFILES_PATH.read_text(encoding="utf-8") if app.SETTINGS_PROFILES_PATH.exists() else False)
for ab in ["Pn","Wt","Śr","Czw","Pi"]:
    print("13_7_8",ab,after.get("min_people_13",{}).get(f"{ab}|7/8"),
          [(sid,after.get("min_people_13_stations",{}).get(f"{ab}|7/8|{sid}")) for sid in app._stations_13(after)])
entr=next((loc for loc in after.get("school_locations",[]) if app._is_entrance_location(loc)),None)
print("ENTRANCE",entr)
if entr:
    for b in app.SEED.get("breaks",[]):
        if app._school_activity_at_break(b["abbr"],b["label"]):
            print("ENTRANCE_ACTIVE",b["abbr"],b["label"],after.get("min_people_school",{}).get(f"{b['abbr']}|{b['label']}|{entr}"))

# Verify system invariants across all real days/slots.
problems=[]
for b in app.SEED.get("breaks",[]):
    ab,slot=b["abbr"],b["label"]
    if app._zone_ended_lesson_before_break("1-3",ab,slot):
        total=sum(int(after.get("min_people_13_stations",{}).get(f"{ab}|{slot}|{sid}",0) or 0) for sid in app._stations_13(after))
        if total<1: problems.append(("1-3",ab,slot,total))
    for zone in ("ground","floor1","floor2"):
        if not app._zone_ended_lesson_before_break(zone,ab,slot): continue
        locs=[loc for loc in after.get("school_locations",[]) if app._duty_location_zone(after,loc)==zone]
        total=sum(int(after.get("min_people_school",{}).get(f"{ab}|{slot}|{loc}",0) or 0) for loc in locs)
        if locs and total<1: problems.append((zone,ab,slot,total))
    if entr and app._school_activity_at_break(ab,slot):
        if int(after.get("min_people_school",{}).get(f"{ab}|{slot}|{entr}",0) or 0)<1:
            problems.append(("entrance",ab,slot,0))
print("INVARIANT_PROBLEMS",json.dumps(problems,ensure_ascii=False))
row=next((r for r in after.get("last_13_assignments",[]) if r.get("abbr")=="Wt" and r.get("label")=="7/8"),{})
print("WT_7_8_ROW",json.dumps({k:row.get(k) for k in ("required_people","complete","assignments")},ensure_ascii=False))
