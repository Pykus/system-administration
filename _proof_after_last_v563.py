import json,sys
sys.path.insert(0,r"C:\DutySolverDemo\dyzury-v5.63-ortools")
import app
s=app.load_state()
e13=list(s.get("enabled_teachers_13",[]))
es=app._school_pool(s.get("enabled_teachers_school",[]))
p=app._edge_rule_exception_proof_v555(s,e13,es,"after_last_long")
print(json.dumps(p,ensure_ascii=False,indent=2))