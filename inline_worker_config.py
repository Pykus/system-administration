from pathlib import Path
root=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
ns={}
exec((root/"worker_embedded_config.py").read_text(encoding="utf-8"),ns)
p=root/"worker_main.py"
s=p.read_text(encoding="utf-8")
old="import worker_embedded_config as cfg"
replacement="class cfg:\n    WORKER_VERSION="+repr(ns["WORKER_VERSION"])+"\n    VERSION="+repr(ns["VERSION"])+"\n    SEED_SHA="+repr(ns["SEED_SHA"])+"\n    TOKEN="+repr(ns["TOKEN"])+"\n    BROKER_URLS="+repr(ns["BROKER_URLS"])
if old not in s: raise SystemExit("config import anchor missing")
s=s.replace(old,replacement,1)
p.write_text(s,encoding="utf-8")
b=root/"build_worker_exe.py"
t=b.read_text(encoding="utf-8").replace('    "--hidden-import=worker_embedded_config",\n',"")
b.write_text(t,encoding="utf-8")
print("INLINE_CONFIG_OK")
