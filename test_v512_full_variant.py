
from pathlib import Path
import sys,json
root=Path(r"C:\DutySolverDemo\dyzury-v5.12-ortools");sys.path.insert(0,str(root))
import app
s=app.load_state();e13=list(s.get("enabled_teachers_13",[]));es=app._school_pool(s.get("enabled_teachers_school",[]))
base=app._joint_coverage_v2({**s,"solver_coverage_seconds":3,"solver_coverage_retry_seconds":12},e13,es,False)
cs=app._repair_candidates_v2(s,e13,es,base); c=next(x for x in cs if x["token"]=="gsoft:avoid_wait")
st,p13,ps=app._apply_repair_tokens_v2(s,e13,es,[c["token"]])
fast=app._eval_combo_local(s,e13,es,[c["token"]])
assert fast["missing"]==0 and not fast["inconclusive"],fast
v=app._repair_variant_v2(s,st,p13,ps,[c["token"]],[c],fast)
out={"coverage13":v["coverage13"],"coverageSchool":v["coverageSchool"],"wait_relax":v["wait_relax"],
     "wait_assignments":v["wait_assignments"],"positions_changed":v["teacher_changes"]["positions_changed"],
     "teachers_changed":v["teacher_changes"]["teachers_changed"],"score":v["score"]}
assert v["coverage13"]["missing"]==0 and v["coverageSchool"]["missing"]==0,out
print(json.dumps(out,ensure_ascii=True,indent=2))
