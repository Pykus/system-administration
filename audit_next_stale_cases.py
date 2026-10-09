import copy, json, tempfile
from pathlib import Path
import sys
ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.43-ortools")
sys.path.insert(0,str(ROOT))
import app

orig_state,orig_profiles,orig_jobs=app.STATE_PATH,app.SETTINGS_PROFILES_PATH,app.REPAIR_JOBS
base=json.loads(orig_state.read_text(encoding="utf-8"))

def run_case(name,fn):
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); app.STATE_PATH=td/"state.json"; app.SETTINGS_PROFILES_PATH=td/"profiles.json"
        app.STATE_PATH.write_text(json.dumps(base,ensure_ascii=False,indent=2),encoding="utf-8")
        app.REPAIR_JOBS={"audit":{"id":"audit","status":"running","_cancel":False,"auto_paused":False}}
        try:
            fn(td)
            j=app.REPAIR_JOBS["audit"]
            print(name,"STALE",bool(j.get("stale_due_to_manual_edit")),"STATUS",j.get("status"))
        except Exception as e:
            print(name,"ERROR",type(e).__name__,str(e)[:180])

def case_update(td):
    t=next(iter(sorted(app.ALL))); app.update_state({"manual_blocks":{t:["Pn|1/2"]}})

def case_constraints(td):
    s=app.load_state(); g=copy.deepcopy(s.get("global_constraints",[])); i=copy.deepcopy(s.get("individual_constraints",[]))
    if g: g[0]["enabled"]=not bool(g[0].get("enabled"))
    app.save_constraints({"global":g,"individual":i})

def case_staffing(td):
    s=app.load_state(); raw=copy.deepcopy(s.get("min_people_13_stations",{}))
    key=next(iter(raw),None)
    if key: raw[key]=0 if int(raw[key] or 0) else 1
    app.save_min_people_13_stations({"staffing":raw})

def case_profile(td):
    s=app.load_state(); snap=app._settings_snapshot(s)
    if snap.get("global_constraints"): snap["global_constraints"][0]["enabled"]=not bool(snap["global_constraints"][0].get("enabled"))
    app.SETTINGS_PROFILES_PATH.write_text(json.dumps({"profiles":[{"id":"p","name":"P","settings":snap}],"default_id":None},ensure_ascii=False),encoding="utf-8")
    app.load_settings_profile("p")

def case_school(td):
    s=app.load_state(); arr=copy.deepcopy(s.get("school_assignments",[]))
    if arr: arr[0]["teacher"]=""
    else: arr=[{"day":"Poniedziałek","abbr":"Pn","slot":"1/2","location":"AUDIT","teacher":next(iter(sorted(app.ALL)))}]
    app.save_school_current({"assignments":arr})

for name,fn in [("update_state",case_update),("constraints",case_constraints),("staffing13",case_staffing),("profile_load",case_profile),("school_current",case_school)]:
    run_case(name,fn)
app.STATE_PATH,app.SETTINGS_PROFILES_PATH,app.REPAIR_JOBS=orig_state,orig_profiles,orig_jobs
