import sys,json
from pathlib import Path
ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools")
sys.path.insert(0,str(ROOT))
import app
st=app.load_state()
r13=app._coverage(st,"1–3",st.get("enabled_teachers_13",[]),optimize=False)
rs=app._coverage(st,"szkoła",st.get("enabled_teachers_school",[]),other_override=app._flat13_other(r13["assignments"]),optimize=False)
def s(r):
 d=r["diagnostics"]
 return {"filled":r["filled"],"required":r["required"],"missing":r["missing"],"phase1_status":d.get("phase1_status"),"minimum_missing_found":d.get("minimum_missing_found"),"wall_time_s":d.get("wall_time_s"),"solution_info":d.get("solution_info")}
print(json.dumps({"13":s(r13),"school":s(rs)},ensure_ascii=False,indent=2))
