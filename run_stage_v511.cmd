@echo off
cd /d C:\DutySolverDemo\dyzury-v5.11-ortools
"C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8092
