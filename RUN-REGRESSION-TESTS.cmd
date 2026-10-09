@echo off
setlocal
cd /d "%~dp0"
echo === Python compile ===
python -X utf8 -m py_compile app.py repair_farm.py worker_broker.py solver_ortools.py
if errorlevel 1 exit /b 10

echo === Vue/JS syntax ===
python -X utf8 -c "from pathlib import Path;import re;s=Path(r'static\index.html').read_text(encoding='utf-8');m=re.search(r'<script>(.*)</script>',s,re.S);Path(r'data\_ui_check.js').write_text(m.group(1),encoding='utf-8')"
if errorlevel 1 exit /b 11
node --check data\_ui_check.js
if errorlevel 1 exit /b 12

echo === Regression tests ===
python -X utf8 -m unittest discover -s tests -v
if errorlevel 1 exit /b 13

echo ALL_REGRESSION_TESTS_OK
exit /b 0
