
from pathlib import Path
import sys,json
root=Path(r"C:\DutySolverDemo\dyzury-v5.12-ortools")
sys.path.insert(0,str(root))
import app
s=app.load_state()
e13=list(s.get("enabled_teachers_13") or list(app.ALL))
es=app._school_pool(s.get("enabled_teachers_school") or list(app.ALL))
base=app._joint_coverage_v2({**s,"solver_coverage_seconds":4,"solver_coverage_retry_seconds":12},e13,es,optimize=False)
wait=app._eval_combo_local(s,e13,es,["gsoft:avoid_wait"])
bad_school_pool=[n for n in es if app.GROUP.get(n)=="1-3"]
st,p13,ps=app._apply_repair_tokens_v2(s,e13,es,["addschool:"+next((n for n in app.ALL if app.GROUP.get(n)=="1-3"),"")])
bad_after=[n for n in ps if app.GROUP.get(n)=="1-3"]
out={
 "version":app.PLANNER_VERSION,
 "school_pool_count":len(es),
 "bad_school_pool":bad_school_pool,
 "bad_after_addschool_13":bad_after,
 "baseline":{"missing":base["missing"],"inconclusive":base["inconclusive"],"order":base["order"],
             "13":{k:base["school13"][k] for k in ("required","filled","missing")},
             "school":{k:base["school"][k] for k in ("required","filled","missing")},
             "status13":base["school13"]["diagnostics"].get("status"),
             "statusSchool":base["school"]["diagnostics"].get("status")},
 "avoid_wait":wait
}
assert app.PLANNER_VERSION=="5.12"
assert not bad_school_pool
assert not bad_after
assert not wait.get("inconclusive"), wait
assert wait["coverage13"]["missing"]==0, wait
assert wait["coverageSchool"]["missing"]==0, wait
print(json.dumps(out,ensure_ascii=True,indent=2))
