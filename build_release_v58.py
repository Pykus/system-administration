from pathlib import Path
import hashlib,json,zipfile
root=Path(r"C:\DutySolverDemo\dyzury-v5.8-ortools")
out=Path(r"C:\DutySolverDemo\releases")
out.mkdir(exist_ok=True)
zip_path=out/"DEMO-Dyzury-v5.8-2026-09-19.zip"
skip_names={"MAIN-DOM-v58.html","TEACHER-DOM-v58.html","patch_v58.py","smoke_v58.py","run_smoke_v58.cmd","run_stage_v58.cmd","check_ui_v58.py","_ui_check_v58.js","migrate_state_v58.py","deploy_v58.ps1","deploy_v58.py","deploy_v58.cmd","run_v58_only.cmd","run_tests_v58.cmd"}
with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in root.rglob("*"):
        if not p.is_file(): continue
        rel=p.relative_to(root)
        s=rel.as_posix()
        if "__pycache__" in rel.parts or "logs" in rel.parts or s.startswith("data/predeploy-") or s.startswith("data/predeploy-v58-") or p.name in skip_names:
            continue
        z.write(p,(Path("dyzury-v5.8-ortools")/rel).as_posix())
with zipfile.ZipFile(zip_path) as z:
    bad=z.testzip()
if bad: raise SystemExit("ZIP_BAD "+bad)
h=hashlib.sha256(zip_path.read_bytes()).hexdigest()
result={"version":"5.8","zip":str(zip_path),"bytes":zip_path.stat().st_size,"sha256":h,"integrity":"PASS"}
(out/"DEMO-Dyzury-v5.8-2026-09-19.BUILD.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False))
