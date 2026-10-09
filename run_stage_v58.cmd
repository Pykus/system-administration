@echo off
cd /d C:\DutySolverDemo\dyzury-v5.8-ortools
python.exe -m uvicorn app:app --host 127.0.0.1 --port 8092
