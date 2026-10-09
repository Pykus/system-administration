import sys,json
from pathlib import Path
sys.path.insert(0,r"C:\DutySolverDemo\dyzury-v5.9-ortools")
import app
st=app.load_state()
r=app._coverage(st,"szkoła",st.get("enabled_teachers_school",[]),other_override=app._flat13_other([{"day":row["day"],"abbr":row["abbr"],"slot":row["label"],"station":a["station"],"teacher":a.get("teacher")} for row in st.get("last_13_assignments",[]) for a in row.get("assignments",[]) if a.get("teacher")]),optimize=False)
print(json.dumps({"filled":r["filled"],"required":r["required"],"missing":r["missing"],"unresolved":r["diagnostics"]["unresolved"]},ensure_ascii=False,indent=2))
