@echo off
setlocal EnableExtensions
set "LOGDIR=C:\ProgramData\WazuhAR\Logs"
set "LOGFILE=%LOGDIR%\gpupdate-computer.log"

if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1

echo [%DATE% %TIME%] START gpupdate-computer >> "%LOGFILE%"
"%SystemRoot%\System32\gpupdate.exe" /target:computer /force /wait:120 >> "%LOGFILE%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%DATE% %TIME%] END gpupdate-computer RC=%RC% >> "%LOGFILE%"

exit /b %RC%
