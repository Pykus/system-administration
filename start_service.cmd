@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

"C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe" tests\test_utf8_integrity.py
if errorlevel 1 exit /b 1

"C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8091
exit
