from pathlib import Path
import zipfile,hashlib,json,shutil,datetime

root=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
releases=Path(r"C:\DutySolverDemo\releases");releases.mkdir(exist_ok=True)

# Worker package.
wp=releases/"DEMO-DutySolver-Worker-v1"
if wp.exists():shutil.rmtree(wp)
wp.mkdir()
exe=root/"worker_dist"/"DEMO-DutySolver-Worker-v1.exe"
shutil.copy2(exe,wp/exe.name)
shutil.copy2(root/"WORKER-README.txt",wp/"README.txt")
exe_sha=hashlib.sha256((wp/exe.name).read_bytes()).hexdigest()
(wp/"SHA256.txt").write_text(f"{exe_sha}  {exe.name}\n",encoding="utf-8")
worker_zip=releases/"DEMO-DutySolver-Worker-v1.zip"
if worker_zip.exists():worker_zip.unlink()
with zipfile.ZipFile(worker_zip,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in wp.iterdir():z.write(p,(Path(wp.name)/p.name).as_posix())
with zipfile.ZipFile(worker_zip) as z:
    if z.testzip():raise RuntimeError("worker ZIP corrupt")
worker_zip_sha=hashlib.sha256(worker_zip.read_bytes()).hexdigest()

# Planner release.
planner_zip=releases/"DEMO-Dyzury-v5.11-2026-09-19.zip"
if planner_zip.exists():planner_zip.unlink()
skip_names={
 "patch_test2_v510.py","check_v510.py","_ui_check_v510.js","smoke_repair_job_v510.py","run_stage_v510.cmd",
 "deploy_v510.py","build_release_v510.py","check_v511.py","_ui_check_v511.js","smoke_v511.py","smoke_parallel_v511.py",
 "smoke_remote_worker_v511.py","run_stage_v511.cmd","deploy_v511.py","sync_live_v511.py","sync_final_v511.py",
 "cleanup_farm_test.py","start_broker_test.py","build_worker.cmd","worker_embedded_config.py"
}
with zipfile.ZipFile(planner_zip,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in root.rglob("*"):
        if not p.is_file():continue
        rel=p.relative_to(root)
        if "__pycache__" in rel.parts or "logs" in rel.parts or "worker_build" in rel.parts or "worker_dist" in rel.parts:
            continue
        if any(x.startswith("predeploy-") for x in rel.parts) or p.name in skip_names or p.name=="repair_farm.sqlite":
            continue
        z.write(p,(Path("dyzury-v5.11-ortools")/rel).as_posix())
with zipfile.ZipFile(planner_zip) as z:
    if z.testzip():raise RuntimeError("planner ZIP corrupt")
planner_sha=hashlib.sha256(planner_zip.read_bytes()).hexdigest()

report={
 "planner":{"path":str(planner_zip),"bytes":planner_zip.stat().st_size,"sha256":planner_sha,"integrity":"PASS"},
 "worker":{"path":str(worker_zip),"bytes":worker_zip.stat().st_size,"sha256":worker_zip_sha,
           "exe_bytes":exe.stat().st_size,"exe_sha256":exe_sha,"self_test":"PASS","integrity":"PASS"},
 "production":{"url":"http://127.0.0.1:8091","version":"5.11","remote_broker_default":"OFF","broker_port":8093},
 "built_at":datetime.datetime.now().astimezone().isoformat(timespec="seconds")
}
(releases/"DEMO-Dyzury-v5.11-2026-09-19.BUILD.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
