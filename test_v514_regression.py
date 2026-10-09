
from pathlib import Path
import sys,time,json
root=Path(r"C:\DutySolverDemo\dyzury-v5.14-ortools")
sys.path.insert(0,str(root))
import app
s=app.load_state()
e13=list(s.get("enabled_teachers_13",[]))
es=app._school_pool(s.get("enabled_teachers_school",[]))
tok="gsoft:avoid_wait"
t=time.perf_counter()
ev=app._eval_combo_deep(s,e13,es,[tok])
deep_s=time.perf_counter()-t
assert not ev["inconclusive"],ev
assert ev["missing"]==0,ev
assert ev["coverage13"]=={"required":95,"filled":95,"missing":0},ev["coverage13"]
assert ev["coverageSchool"]=={"required":354,"filled":354,"missing":0},ev["coverageSchool"]
assert len(ev["result13"])==95
assert len(ev["resultSchool"])==354
c=app._repair_candidate_v2(tok,"Unikaj dodatkowego oczekiwania: MUSI BYĆ → ZALECANE",6000,"komfort nauczyciela",True)
c["wait_relax"]=True;c["search_stage"]=3
st,p13,ps=app._apply_repair_tokens_v2(s,e13,es,[tok])
t=time.perf_counter()
v=app._repair_variant_v2(s,st,p13,ps,[tok],[c],ev)
variant_s=time.perf_counter()-t
assert v["coverage13"]["missing"]==0 and v["coverageSchool"]["missing"]==0,v
assert v["coverage13"]["required"]==95 and v["coverageSchool"]["required"]==354,v
assert v["coverage_reduction"]==0,v
assert variant_s<3.0,variant_s
html=(root/"static"/"index.html").read_text(encoding="utf-8")
for marker in ("Dyżury v5.14","showMissingSchool","Braki w planie całej szkoły","Najlepsze wyniki częściowe","best_partials"):
    assert marker in html,marker
assert app._firewall_rule_exists()
print(json.dumps({"deep_seconds":round(deep_s,2),"variant_reuse_seconds":round(variant_s,3),
 "coverage13":ev["coverage13"],"coverageSchool":ev["coverageSchool"],
 "result13":len(ev["result13"]),"resultSchool":len(ev["resultSchool"]),
 "coverage_reduction":v["coverage_reduction"],"firewall_ok":True},ensure_ascii=True,indent=2))
