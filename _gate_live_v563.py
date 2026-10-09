import json,sys
sys.path.insert(0,r"C:\DutySolverDemo\dyzury-v5.63-ortools")
import app
s=app.load_state()
e13=list(s.get("enabled_teachers_13",[]))
es=app._school_pool(s.get("enabled_teachers_school",[]))
q=app._quick_draft_v527(s,e13,es,[],seed_offset=0,optimize_seconds=4)
out={k:q.get(k) for k in ("status","full","missing","coverage13","coverageSchool","wait_lessons_total","after_last_long","before_first_long","consecutive_pairs","home_group_foreign_13","home_group_foreign_13_wf","elapsed_s","hardened_keys")}
print(json.dumps(out,ensure_ascii=False,indent=2))
assert q.get("full"), out
assert q["coverage13"]["missing"]==0 and q["coverageSchool"]["missing"]==0, out
assert int(q.get("wait_lessons_total",0) or 0)==0, out
assert int(q.get("after_last_long",0) or 0)==0, out
assert int(q.get("before_first_long",0) or 0)==0, out
print("LIVE_GATE_V563=OK")