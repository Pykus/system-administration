@echo off
setlocal EnableExtensions
set "LOGDIR=C:\ProgramData\WazuhAR\Logs"
set "LOGFILE=%LOGDIR%\gpupdate-computer-reboot.log"

if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1

echo [%DATE% %TIME%] START gpupdate-computer-reboot >> "%LOGFILE%"
"%SystemRoot%\System32\gpupdate.exe" /target:computer /force /wait:120 >> "%LOGFILE%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%DATE% %TIME%] GPUPDATE RC=%RC% >> "%LOGFILE%"

if "%RC%"=="0" (
    echo [%DATE% %TIME%] Scheduling forced reboot in 15 seconds >> "%LOGFILE%"
    "%SystemRoot%\System32\shutdown.exe" /r /t 15 /f /d p:4:1 /c "Wazuh Active Response: computer policy updated" >> "%LOGFILE%" 2>&1
) else (
    echo [%DATE% %TIME%] Reboot skipped because GPUpdate failed >> "%LOGFILE%"
)

exit /b %RC%
