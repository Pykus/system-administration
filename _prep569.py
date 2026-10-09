import json, urllib.request, shutil, pathlib, os, time
root=pathlib.Path(r"C:\DutySolverDemo")
old=root/"dyzury-v5.68-ortools"
new=root/"dyzury-v5.69-ortools"
health=json.load(urllib.request.urlopen("http://127.0.0.1:8091/api/health",timeout=5))
assert health["version"]=="5.68",health
cur=json.load(urllib.request.urlopen("http://127.0.0.1:8091/api/diagnostics/repair/search/current?ts=prep569",timeout=8))
job=cur["job"]
live=[x for x in job.get("working_variants",[]) if x.get("live_eligible")]
assert live and len(live[0].get("result_13") or [])==80 and len(live[0].get("result_school") or [])==385
job_id=str(job["id"])
stamp=time.strftime("%Y%m%d-%H%M%S")
bak=root/"release-backups"/("v5.68-pre-v5.69-"+stamp)
(bak/"data").mkdir(parents=True,exist_ok=True)
shutil.copy2(root/"CURRENT_RELEASE.txt",bak/"CURRENT_RELEASE.txt")
critical=["state.json","repair_learning.json","seed.json","teacher_registry.json","settings.json","settings_profiles.json","repair_farm_config.json","worker_deploy_status.json"]
for fn in critical:
    src=old/"data"/fn
    if src.exists():
        shutil.copy2(src,bak/"data"/fn)
        shutil.copy2(src,new/"data"/fn)
src_jobs=old/"data"/"repair_jobs"
dst_jobs=new/"data"/"repair_jobs"
dst_jobs.mkdir(parents=True,exist_ok=True)
if src_jobs.exists():
    for f in src_jobs.glob("*.json"):
        shutil.copy2(f,dst_jobs/f.name)
state=json.loads((new/"data"/"state.json").read_text(encoding="utf-8-sig"))
job["plan_revision"]=int(state.get("plan_revision",0) or 0)
cp=dst_jobs/(job_id+".json")
cp.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding="utf-8")
os.utime(cp,None)
print("PREP_OK",job_id,live[0]["coverage13"],live[0]["coverageSchool"],live[0].get("after_last_long"),bak)
