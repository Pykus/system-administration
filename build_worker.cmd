@echo off
cd /d C:\DutySolverDemo\dyzury-v5.12-ortools
if exist worker_dist rmdir /s /q worker_dist
if exist worker_build rmdir /s /q worker_build
python.exe -m PyInstaller --noconfirm --clean --onefile --console --name DEMO-DutySolver-Worker-v1.1 --distpath C:\DutySolverDemo\dyzury-v5.12-ortools\worker_dist --workpath C:\DutySolverDemo\dyzury-v5.12-ortools\worker_build --specpath C:\DutySolverDemo\dyzury-v5.12-ortools\worker_build --add-data "C:\DutySolverDemo\dyzury-v5.12-ortools\data\seed.json;data" --collect-all ortools C:\DutySolverDemo\dyzury-v5.12-ortools\worker_main.py
exit /b %errorlevel%
