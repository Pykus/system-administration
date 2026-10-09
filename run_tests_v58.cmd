@echo off
cd /d C:\DutySolverDemo\dyzury-v5.8-ortools
python.exe -m compileall -q app.py solver_ortools.py validation.py test_v56.py test_v57.py test_v58.py
if errorlevel 1 exit /b %errorlevel%
python.exe -m unittest -v test_v56.py test_v57.py test_v58.py
exit /b %errorlevel%
