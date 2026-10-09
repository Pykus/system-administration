import json,sys
from pathlib import Path
ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools")
sys.path.insert(0,str(ROOT))
import app, solver_ortools as so
st=app.load_state()
b=[x for x in app.SEED["breaks"] if x["label"]=="9/po"]
rows=[]
for br in b:
    eligible=st.get("enabled_teachers_13",[])
    l9=[n for n in eligible if 9 in so._lesson_periods(app.TBY,n,br["abbr"])]
    wait0=[n for n in eligible if so._wait(app.TBY,n,br)==0]
    rows.append({"day":br["abbr"],"prev":br.get("prev"),"next":br.get("next"),"minutes":br.get("minutes"),"lesson9":l9,"wait0":wait0})
hard_ind=[x for x in st.get("individual_constraints",[]) if x.get("enabled",True) and str(x.get("kind")).lower()=="hard"]
forbid=[]
for n,prefs in st.get("preference_grid",{}).items():
    for k,v in (prefs or {}).items():
        if str(v).lower()=="forbid": forbid.append((n,k))
print(json.dumps({"9po":rows,"hard_individual_count":len(hard_ind),"hard_individual":hard_ind[:20],"forbidden_preferences_count":len(forbid),"forbidden_preferences":forbid[:30]},ensure_ascii=False,indent=2))
