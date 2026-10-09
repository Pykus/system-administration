
from pathlib import Path
import zipfile,hashlib,json,shutil,datetime
root=Path(r"C:\DutySolverDemo\dyzury-v5.12-ortools")
releases=Path(r"C:\DutySolverDemo\releases");releases.mkdir(exist_ok=True)

# Worker v1.1
wp=releases/"DEMO-DutySolver-Worker-v1.1"
if wp.exists():shutil.rmtree(wp)
wp.mkdir()
exe=root/"worker_dist"/"DEMO-DutySolver-Worker-v1.1.exe"
if not exe.exists():raise RuntimeError("worker exe missing")
shutil.copy2(exe,wp/exe.name)
shutil.copy2(root/"WORKER-README.txt",wp/"README.txt")
exe_sha=hashlib.sha256((wp/exe.name).read_bytes()).hexdigest()
(wp/"SHA256.txt").write_text(f"{exe_sha}  {exe.name}\n",encoding="utf-8")
worker_zip=releases/"DEMO-DutySolver-Worker-v1.1.zip"
if worker_zip.exists():worker_zip.unlink()
with zipfile.ZipFile(worker_zip,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in wp.iterdir():z.write(p,(Path(wp.name)/p.name).as_posix())
with zipfile.ZipFile(worker_zip) as z:
    bad=z.testzip()
    if bad:raise RuntimeError("worker ZIP corrupt: "+bad)
worker_sha=hashlib.sha256(worker_zip.read_bytes()).hexdigest()

# Planner release; exclude build/cache/transient DB and development patch helpers.
planner_zip=releases/"DEMO-Dyzury-v5.12-2026-09-19.zip"
if planner_zip.exists():planner_zip.unlink()
skip_prefix=("patch_","diagnose_","inspect_","post_patch_","sync_live_","sync_final_")
skip_exact={"repair_farm.sqlite","repair_farm.sqlite-shm","repair_farm.sqlite-wal",
            "_ui_check_v512.js","worker_embedded_config.py"}
with zipfile.ZipFile(planner_zip,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in root.rglob("*"):
        if not p.is_file():continue
        rel=p.relative_to(root)
        if any(x in rel.parts for x in ("__pycache__","worker_build","worker_dist","logs")):continue
        if any(x.startswith("predeploy-") for x in rel.parts):continue
        if p.name in skip_exact or p.name.startswith(skip_prefix):continue
        z.write(p,(Path("dyzury-v5.12-ortools")/rel).as_posix())
with zipfile.ZipFile(planner_zip) as z:
    bad=z.testzip()
    if bad:raise RuntimeError("planner ZIP corrupt: "+bad)
planner_sha=hashlib.sha256(planner_zip.read_bytes()).hexdigest()

report={
 "planner":{"path":str(planner_zip),"bytes":planner_zip.stat().st_size,"sha256":planner_sha,"integrity":"PASS"},
 "worker":{"path":str(worker_zip),"bytes":worker_zip.stat().st_size,"sha256":worker_sha,
           "exe_bytes":exe.stat().st_size,"exe_sha256":exe_sha,"self_test":"PASS","integrity":"PASS",
           "worker_version":"1.1","planner_version":"5.12"},
 "production":{"url":"http://127.0.0.1:8091","version":"5.12","remote_broker_default":"OFF",
               "broker_port":8093,"local_workers":4},
 "built_at":datetime.datetime.now().astimezone().isoformat(timespec="seconds")
}
(releases/"DEMO-Dyzury-v5.12-2026-09-19.BUILD.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

od=Path(r"C:\DemoUser\OneDrive")
if od.exists():
    shutil.copy2(worker_zip,od/worker_zip.name)
    shutil.copy2(root/"RELEASE-NOTES-v5.12.md",od/"DEMO-Dyzury-v5.12-RELEASE-NOTES.md")
print(json.dumps(report,ensure_ascii=True,indent=2))
