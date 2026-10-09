$ErrorActionPreference='Stop'
$old='C:\DutySolverDemo\dyzury-v5.19-ortools'
$new='C:\DutySolverDemo\dyzury-v5.21-ortools'
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$backup="C:\DutySolverDemo\rollback-v5.19-before-v5.21-$stamp"

function Stop-Port([int]$port) {
  $pids=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
  foreach($pid0 in $pids){ Stop-Process -Id $pid0 -Force -ErrorAction SilentlyContinue }
}
function Health([int]$port) {
  try { return Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 2 } catch { return $null }
}
Write-Host "Backup live v5.19 -> $backup"
Copy-Item "$old\data" $backup -Recurse -Force

# Stop test stage and current production/broker.
Stop-Port 8094
Stop-Port 8091
Stop-Port 8093
Start-Sleep -Milliseconds 500

# Copy only live data after processes are stopped. Old tree remains untouched for rollback.
if(Test-Path "$new\data"){ Remove-Item "$new\data" -Recurse -Force }
Copy-Item "$old\data" "$new\data" -Recurse -Force

# Persist one-time schema/default migrations in the new copy.
Push-Location $new
& 'C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe' -c "import app; s=app.load_state(); app.save_state(s); print('migration-ok')"
Pop-Location

Start-Process "$new\start_service.cmd"
$ok=$false
for($i=0;$i -lt 15;$i++){
  Start-Sleep -Seconds 1
  $h=Health 8091
  if($h -and $h.ok -and $h.version -eq '5.21'){ $ok=$true; break }
}
if(-not $ok){
  Write-Host 'v5.21 health failed - rollback to v5.19'
  Stop-Port 8091
  Stop-Port 8093
  Start-Process "$old\start_service.cmd"
  throw 'Deployment v5.21 failed; v5.19 restarted.'
}
$farm=Invoke-RestMethod 'http://127.0.0.1:8091/api/worker-farm/status' -TimeoutSec 5
if(-not $farm.broker_running){
  Write-Host 'Broker check failed - rollback to v5.19'
  Stop-Port 8091
  Stop-Port 8093
  Start-Process "$old\start_service.cmd"
  throw 'Deployment v5.21 broker failed; v5.19 restarted.'
}
Set-Content "$new\CURRENT_RELEASE.txt" 'v5.21' -Encoding ASCII
Write-Host ("DEPLOY_OK version="+$h.version+" broker="+$farm.broker_running+" backup="+$backup)
