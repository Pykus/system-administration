$ErrorActionPreference='Stop'
$root='C:\DutySolverDemo\dyzury-v5.7-ortools'
$python='C:\DemoUser\AppData\Local\Programs\Python\Python312\python.exe'
$launcher=Join-Path $root 'start_service.cmd'
$launcherBak=Join-Path $root 'start_service.cmd.pre-lan-fix.bak'
Copy-Item $launcher $launcherBak -Force

$old=Get-NetTCPConnection -State Listen -LocalPort 8091 -ErrorAction SilentlyContinue | Select-Object -First 1
$oldPid=if($old){[int]$old.OwningProcess}else{$null}

try {
    @"
@echo off
cd /d C:\DutySolverDemo\dyzury-v5.7-ortools
"$python" -m uvicorn app:app --host 0.0.0.0 --port 8090
"@ | Set-Content -LiteralPath $launcher -Encoding ASCII

    $rule=Get-NetFirewallRule -DisplayName 'DEMO Dyżury 8090 LAN' -ErrorAction SilentlyContinue
    if(-not $rule){
        New-NetFirewallRule -DisplayName 'DEMO Dyżury 8090 LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8090 -Profile Domain,Private -RemoteAddress LocalSubnet | Out-Null
    } else {
        Set-NetFirewallRule -DisplayName 'DEMO Dyżury 8090 LAN' -Enabled True -Action Allow -Profile Domain,Private | Out-Null
    }

    if($oldPid){Stop-Process -Id $oldPid -Force}
    Start-Sleep -Milliseconds 500

    $p=Start-Process $python -ArgumentList @('-m','uvicorn','app:app','--host','0.0.0.0','--port','8090') -WorkingDirectory $root -WindowStyle Hidden -PassThru
    $deadline=(Get-Date).AddSeconds(30)
    $okLocal=$false; $okLan=$false; $h1=$null; $h2=$null
    do {
        Start-Sleep -Milliseconds 500
        try {$h1=Invoke-RestMethod -UseBasicParsing 'http://127.0.0.1:8090/api/health' -TimeoutSec 2; $okLocal=$h1.version -eq '5.7'} catch {}
        try {$h2=Invoke-RestMethod -UseBasicParsing 'http://192.0.2.10:8090/api/health' -TimeoutSec 2; $okLan=$h2.version -eq '5.7'} catch {}
        if($okLocal -and $okLan){break}
    } while((Get-Date) -lt $deadline)

    if(-not ($okLocal -and $okLan)){throw "health failed local=$okLocal lan=$okLan"}

    $listen=Get-NetTCPConnection -State Listen -LocalPort 8090 | Select-Object -First 1
    [pscustomobject]@{
        ok=$true
        version=$h1.version
        pid=$p.Id
        listen_address=$listen.LocalAddress
        port=$listen.LocalPort
        local_health=$okLocal
        lan_health=$okLan
        url='http://192.0.2.10:8090'
        firewall_rule='DEMO Dyżury 8090 LAN'
    } | ConvertTo-Json -Compress
}
catch {
    Copy-Item $launcherBak $launcher -Force
    Get-NetTCPConnection -State Listen -LocalPort 8090 -ErrorAction SilentlyContinue | ForEach-Object {Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue}
    Start-Process $python -ArgumentList @('-m','uvicorn','app:app','--host','127.0.0.1','--port','8091') -WorkingDirectory $root -WindowStyle Hidden | Out-Null
    throw
}