$ErrorActionPreference='Stop'
$v57='C:\DutySolverDemo\dyzury-v5.7-ortools'
$v58='C:\DutySolverDemo\dyzury-v5.8-ortools'
$python='C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe'
$startup='C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd'
$startupBak='C:\DemoUser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\DEMO-Dyzury.cmd.pre-v5.8.bak'
$report=Join-Path $v58 'DEPLOYMENT-REPORT-v5.8.json'

# Synchronize only authoritative live data from production v5.7.
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$pre=Join-Path $v58 ('data\predeploy-v58-'+$stamp)
New-Item -ItemType Directory -Path $pre -Force | Out-Null
foreach($name in @('state.json','seed.json','teacher_registry.json')){
    $cur=Join-Path $v58 ('data\'+$name)
    if(Test-Path $cur){Copy-Item $cur (Join-Path $pre $name) -Force}
    $src=Join-Path $v57 ('data\'+$name)
    if(Test-Path $src){Copy-Item $src $cur -Force}
}
if(Test-Path $startup){Copy-Item $startup $startupBak -Force}

Push-Location $v58
& $python (Join-Path $v58 'migrate_state_v58.py')
if($LASTEXITCODE -ne 0){throw 'v5.8 schema migration failed'}
& $python -m compileall -q app.py solver_ortools.py validation.py test_v58.py
if($LASTEXITCODE -ne 0){throw 'v5.8 compile failed'}
& $python -m unittest -q test_v58.py
if($LASTEXITCODE -ne 0){throw 'v5.8 tests failed after live-data sync'}
Pop-Location

# Stop staging 8092, if still running.
Get-NetTCPConnection -State Listen -LocalPort 8092 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 500

# Localhost-only launcher by explicit user decision.
@"
@echo off
cd /d C:\DutySolverDemo\dyzury-v5.8-ortools
"$python" -m uvicorn app:app --host 127.0.0.1 --port 8091
"@ | Set-Content -LiteralPath (Join-Path $v58 'start_service.cmd') -Encoding ASCII

$old=Get-NetTCPConnection -State Listen -LocalPort 8091 -ErrorAction SilentlyContinue | Select-Object -First 1
$oldPid=if($old){[int]$old.OwningProcess}else{$null}
$newProc=$null
try {
    if($oldPid){Stop-Process -Id $oldPid -Force -ErrorAction Stop}
    Start-Sleep -Milliseconds 700
    $newProc=Start-Process $python -ArgumentList @('-m','uvicorn','app:app','--host','127.0.0.1','--port','8091') -WorkingDirectory $v58 -WindowStyle Hidden -PassThru

    $deadline=(Get-Date).AddSeconds(45)
    $health=$null
    do {
        Start-Sleep -Milliseconds 500
        try {$health=Invoke-RestMethod -UseBasicParsing 'http://127.0.0.1:8091/api/health' -TimeoutSec 3} catch {$health=$null}
        if($health -and $health.version -eq '5.8'){break}
    } while((Get-Date) -lt $deadline)
    if(-not $health -or $health.version -ne '5.8'){throw 'v5.8 health check failed'}

    $cfg=Invoke-RestMethod -UseBasicParsing 'http://127.0.0.1:8091/api/config' -TimeoutSec 8
    $cm=@{}
    foreach($row in $cfg.state.global_constraints){$cm[$row.key]=$row}
    foreach($key in @('before_first_long','after_last_long')){
        if(-not $cm.ContainsKey($key) -or -not $cm[$key].enabled -or $cm[$key].kind -ne 'hard'){
            throw "required hard policy missing: $key"
        }
    }
    if(-not $cm.ContainsKey('lesson_load_fairness')){throw 'lesson_load_fairness missing'}
    $main=(Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8091/' -TimeoutSec 8).Content
    if($main -notmatch 'teacherPageSize:15' -or $main -notmatch 'Efektywny wsp'){throw 'v5.8 main UI marker missing'}
    $teacher=(Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8091/teacher' -TimeoutSec 8).Content
    if($teacher -notmatch 'Plan tygodnia' -or $teacher -notmatch 'class="schedule"'){throw 'v5.8 teacher UI marker missing'}

    @"
@echo off
start "" /min C:\DutySolverDemo\dyzury-v5.8-ortools\start_service.cmd
"@ | Set-Content -LiteralPath $startup -Encoding ASCII

    $listener=Get-NetTCPConnection -State Listen -LocalPort 8091 | Select-Object -First 1
    $result=[ordered]@{
        deployed_at=(Get-Date).ToString('o')
        version='5.8'
        pid=$newProc.Id
        host=$listener.LocalAddress
        port=$listener.LocalPort
        localhost_only=($listener.LocalAddress -eq '127.0.0.1')
        engine=$health.engine
        teachers=$health.teachers
        before_first_long=$cm['before_first_long']
        after_last_long=$cm['after_last_long']
        before_first_short=$cm['before_first_short']
        after_last_short=$cm['after_last_short']
        lesson_load_fairness=$cm['lesson_load_fairness']
        manual_workload_fairness=$cm['workload_fairness']
        current_plan_preserved=$true
        startup_backup=$startupBak
        rollback='v5.7 retained'
    }
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $report -Encoding UTF8
    $result | ConvertTo-Json -Depth 12
}
catch {
    $err=$_.Exception.Message
    if($newProc -and -not $newProc.HasExited){Stop-Process -Id $newProc.Id -Force -ErrorAction SilentlyContinue}
    if(Test-Path $startupBak){Copy-Item $startupBak $startup -Force}
    Start-Process $python -ArgumentList @('-m','uvicorn','app:app','--host','127.0.0.1','--port','8091') -WorkingDirectory $v57 -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
    throw "DEPLOY_ROLLBACK: $err"
}