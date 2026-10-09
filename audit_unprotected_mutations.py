import re
from pathlib import Path
src=Path(r"C:\DutySolverDemo\dyzury-v5.45-ortools\app.py").read_text(encoding="utf-8")
pat=re.compile(r'@app\.(post|put|patch|delete)\("([^"]+)"\)\s*\ndef\s+([A-Za-z_][A-Za-z0-9_]*)\([^)]*\):([\s\S]*?)(?=\n@app\.|\Z)')
for method,path,fn,body in pat.findall(src):
    if "save_state(" in body and not any(x in body for x in ["_save_solver_input_change","_invalidate_active_repair_jobs","REPAIR_JOB_LOCK"]):
        print(f"{method.upper()} {path} :: {fn}")
