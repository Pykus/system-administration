$ErrorActionPreference='Stop'
$v56='C:\DutySolverDemo\dyzury-v5.6-ortools'
$v57='C:\DutySolverDemo\dyzury-v5.7-ortools'
$python='C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe'
$startup='C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd'
$startupBackup='C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd.pre-v5.7.bak'
$report=Join-Path $v57 'DEPLOYMENT-REPORT.json'
$oldStartup=if(Test-Path $startup){Get-Content $startup -Raw}else{''}
if(Test-Path $startup){Copy-Item $startup $startupBackup -Force}

# Snapshot and resync authoritative live data from v5.6.
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir=Join-Path $v57 ('data\predeploy-'+$stamp)
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
foreach($name in 'state.json','seed.json','teacher_registry.json'){
    $dst=Join-Path $v57 ('data\'+$name)
    if(Test-Path $dst){Copy-Item $dst (Join-Path $backupDir $name) -Force}
    $src=Join-Path $v56 ('data\'+$name)
    if(Test-Path $src){Copy-Item $src $dst -Force}
}

# Persist v5.7 schema migration into the copied state.
Push-Location $v57
& $python -c "import app; s=app.load_state(); app.save_state(s); print('MIGRATION_OK locations=%d school_matrix=%d' % (len(s.get('school_locations',[])),len(s.get('min_people_school',{}))))"
if($LASTEXITCODE -ne 0){throw 'v5.7 state migration failed'}
& $python -m unittest -q test_v57.py
if($LASTEXITCODE -ne 0){throw 'v5.7 unit tests failed after production-data sync'}
Pop-Location

# Correct permanent launcher (production is localhost:8091).
@"
@echo off
cd /d C:\DutySolverDemo\dyzury-v5.7-ortools
"$python" -m uvicorn app:app --host 127.0.0.1 --port 8091
"@ | Set-Content -LiteralPath (Join-Path $v57 'start_service.cmd') -Encoding ASCII

$oldPid=$null
$listener=Get-NetTCPConnection -State Listen -LocalPort 8091 -ErrorAction SilentlyContinue | Select-Object -First 1
if($listener){$oldPid=[int]$listener.OwningProcess}
$newProc=$null
$ok=$false
$health=$null
try {
    if($oldPid){Stop-Process -Id $oldPid -Force -ErrorAction Stop}
    for($i=0;$i -lt 30;$i++){
        if(-not (Get-NetTCPConnection -State Listen -LocalPort 8091 -ErrorAction SilentlyContinue)){break}
        Start-Sleep -Milliseconds 200
    }

    $newProc=Start-Process $python -ArgumentList @('-m','uvicorn','app:app','--host','127.0.0.1','--port','8091') -WorkingDirectory $v57 -WindowStyle Hidden -PassThru
    $deadline=(Get-Date).AddSeconds(45)
    do {
        Start-Sleep -Milliseconds 500
        try {$health=Invoke-RestMethod -UseBasicParsing 'http://127.0.0.1:8091/api/health' -TimeoutSec 3} catch {$health=$null}
        if($health -and $health.version -eq '5.7'){break}
    } while((Get-Date) -lt $deadline)
    if(-not $health -or $health.version -ne '5.7'){throw 'v5.7 health check failed'}

    $cfg=Invoke-RestMethod -UseBasicParsing 'http://127.0.0.1:8091/api/config' -TimeoutSec 8
    $page=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8091/' -TimeoutSec 8
    if($page.Content -notmatch '/api/min-people-school'){throw 'UI v5.7 staffing marker missing'}
    if(-not $cfg.state.school_locations -or -not $cfg.state.min_people_school){throw 'v5.7 staffing migration missing'}

    # Only after successful health/UI checks change autostart.
    @"
@echo off
start "" /min C:\DutySolverDemo\dyzury-v5.7-ortools\start_service.cmd
"@ | Set-Content -LiteralPath $startup -Encoding ASCII
    $ok=$true

    $activeCount=($cfg.state.min_people_school.psobject.Properties | Where-Object {$_.Value -eq 1}).Count
    $obj=[ordered]@{
        deployed_at=(Get-Date).ToString('o')
        version='5.7'
        port=8091
        pid=$newProc.Id
        health_ok=$health.ok
        engine=$health.engine
        teachers=$health.teachers
        school_locations=@($cfg.state.school_locations)
        school_locations_count=@($cfg.state.school_locations).Count
        school_staffing_matrix_count=$cfg.state.min_people_school.psobject.Properties.Count
        school_active_positions=$activeCount
        startup_file=$startup
        startup_backup=$startupBackup
        rollback='v5.6 source retained; startup backup retained'
    }
    $obj | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $report -Encoding UTF8
    $obj | ConvertTo-Json -Depth 8
}
catch {
    $err=$_.Exception.Message
    if($newProc -and -not $newProc.HasExited){Stop-Process -Id $newProc.Id -Force -ErrorAction SilentlyContinue}
    if($oldStartup){Set-Content -LiteralPath $startup -Value $oldStartup -Encoding ASCII}
    Start-Process $python -ArgumentList @('-m','uvicorn','app:app','--host','127.0.0.1','--port','8091') -WorkingDirectory $v56 -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
    throw "DEPLOY_ROLLBACK: $err"
}
