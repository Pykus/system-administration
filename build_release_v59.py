from pathlib import Path
import zipfile,hashlib,json,datetime
root=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools")
out=Path(r"C:\DutySolverDemo\releases"); out.mkdir(exist_ok=True)
zp=out/"DEMO-Dyzury-v5.9-2026-09-19.zip"
skip={"patch_v58.py","patch_v59.py","post_patch_v59.py","sync_live_v59.py","workload_audit_v59.py","edge_audit_v59.py","check_v59.py","_ui_check_v59.js","MAIN-DOM-v58.html","TEACHER-DOM-v58.html"}
with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in root.rglob("*"):
        if not p.is_file(): continue
        rel=p.relative_to(root)
        if "__pycache__" in rel.parts or "logs" in rel.parts or any(x.startswith("predeploy-") for x in rel.parts) or p.name in skip:
            continue
        z.write(p,(Path("dyzury-v5.9-ortools")/rel).as_posix())
bad=None
with zipfile.ZipFile(zp) as z: bad=z.testzip()
sha=hashlib.sha256(zp.read_bytes()).hexdigest()
report={
 "version":"5.9","deployed_at":datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
 "production":"http://127.0.0.1:8091","localhost_only":True,
 "tests":"7/7 PASS + compileall PASS + node --check PASS",
 "state_preserved":{"school_assignments":354,"rows13":50},
 "migration":"workload_fairness hard -> soft (one-time current-state correction)",
 "zip":str(zp),"bytes":zp.stat().st_size,"sha256":sha,"integrity":"PASS" if bad is None else "FAIL:"+str(bad),
 "rollback":r"C:\DutySolverDemo\dyzury-v5.8-ortools"
}
(root/"DEPLOYMENT-REPORT-v5.9.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
(out/"DEMO-Dyzury-v5.9-2026-09-19.BUILD.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
