
from pathlib import Path
import shutil,json,sqlite3,sys,datetime
v14=Path(r"C:\DutySolverDemo\dyzury-v5.14-ortools")
v15=Path(r"C:\DutySolverDemo\dyzury-v5.15-ortools")
archive=Path(r"C:\DutySolverDemo\archives")/("repair_jobs-v5.14-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
archive.parent.mkdir(parents=True,exist_ok=True)

# Preserve production repair history outside active v5.15 checkpoints.
src_jobs=v14/"data"/"repair_jobs"
if src_jobs.exists():
    shutil.copytree(src_jobs,archive,dirs_exist_ok=True)

# Copy latest dynamic data.
for name in ("state.json","seed.json","teacher_registry.json","settings.json"):
    src=v14/"data"/name
    if src.exists(): shutil.copy2(src,v15/"data"/name)

# Fresh active checkpoint directory so old v5.14 suggestions do not appear as current.
dst_jobs=v15/"data"/"repair_jobs"
if dst_jobs.exists(): shutil.rmtree(dst_jobs,ignore_errors=True)
dst_jobs.mkdir(parents=True,exist_ok=True)

# Preserve worker farm configuration, but broker PID is re-created on deploy.
cfgp=v14/"data"/"repair_farm_config.json"
cfg=json.loads(cfgp.read_text(encoding="utf-8")) if cfgp.exists() else {"enabled":True,"port":8093,"local_workers":8}
cfg["broker_pid"]=0
(v15/"data"/"repair_farm_config.json").write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")

# Consistent SQLite backup while v5.14 may still be using WAL.
srcdb=v14/"data"/"repair_farm.sqlite"; dstdb=v15/"data"/"repair_farm.sqlite"
for x in (dstdb,Path(str(dstdb)+"-wal"),Path(str(dstdb)+"-shm")):
    try:x.unlink()
    except FileNotFoundError:pass
if srcdb.exists():
    a=sqlite3.connect(srcdb); b=sqlite3.connect(dstdb)
    a.backup(b); b.close(); a.close()

# Let v5.15 migrate schema and add new hard rule(s) without touching production.
sys.path.insert(0,str(v15))
import app
st=app.load_state()
st["version"]="5.15"
app.save_state(st)
st=app.load_state()
keys={x.get("key"):x for x in st.get("global_constraints",[])}
assert "offday_duty" in keys and keys["offday_duty"].get("kind")=="hard" and keys["offday_duty"].get("enabled")
assert isinstance(st.get("excluded_teachers"),list)
assert "freeze_pool_13" in st and "freeze_pool_school" in st

(v15/"CURRENT_RELEASE.txt").write_text("5.15\n",encoding="ascii")
(v15/"start_service.cmd").write_text(
    '@echo off\r\ncd /d C:\\Users\\Admin\\Production\\dyzury-v5.15-ortools\r\n'
    '"C:\\Users\\Admin\\AppData\\Local\\Programs\\Python\\Python312\\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8091\r\n',
    encoding="ascii")
print(json.dumps({
  "state_version":st.get("version"),
  "offday_rule":keys["offday_duty"],
  "excluded":len(st.get("excluded_teachers",[])),
  "freeze13":st.get("freeze_pool_13"),
  "freezeSchool":st.get("freeze_pool_school"),
  "farm":cfg,
  "archived_repair_jobs":str(archive)
},ensure_ascii=True,indent=2))
