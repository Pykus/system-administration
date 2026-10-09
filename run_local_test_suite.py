import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).parent

def run(name):
    p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    return {"script":name,"exit_code":p.returncode,"stdout":p.stdout,"stderr":p.stderr}

names=["test_constraints_local.py","test_v51.py","test_v52.py","test_v53.py","test_v54.py","test_v55.py","test_v56.py","deployment_test_local.py"]
tests=[run(name) for name in names]
ok=all(t["exit_code"]==0 for t in tests)
report={"ok":ok,"version":"5.6","engine":"OR-Tools CP-SAT","python":sys.version,"tests":tests}
(ROOT/"TEST_REPORT_v5.6.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"ok":ok,"tests":[{"script":t["script"],"exit_code":t["exit_code"]} for t in tests]},ensure_ascii=False))
raise SystemExit(0 if ok else 1)
