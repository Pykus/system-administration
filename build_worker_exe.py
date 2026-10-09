from pathlib import Path
import shutil, PyInstaller.__main__
root=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
for p in (root/"dist_worker",root/"build_worker"):
    if p.exists(): shutil.rmtree(p,ignore_errors=True)
PyInstaller.__main__.run([
    str(root/"worker_main.py"),
    "--noconfirm","--clean","--onefile","--console",
    "--name=DEMO-DutySolver-Worker-v1.0",
    "--distpath="+str(root/"dist_worker"),
    "--workpath="+str(root/"build_worker"),
    "--specpath="+str(root/"build_worker"),
    "--paths="+str(root),
    "--hidden-import=worker_embedded_config",
    "--hidden-import=solver_ortools",
    "--collect-all=ortools",
    "--add-data="+str(root/"data"/"seed.json")+":data",
])
