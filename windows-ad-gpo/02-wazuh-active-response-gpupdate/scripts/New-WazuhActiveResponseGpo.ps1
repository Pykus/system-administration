#requires -Version 5.1
<#
.SYNOPSIS
Creates or updates a Computer Startup GPO that deploys Wazuh Active Response
scripts for GPUpdate and GPUpdate + reboot.

.EXAMPLE
.\New-WazuhActiveResponseGpo.ps1 `
  -DomainDns "example.local" `
  -TargetOuDn "OU=Computers,DC=example,DC=local"
#>

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)]
    [string]$DomainDns,

    [Parameter(Mandatory = $true)]
    [string]$TargetOuDn,

    [string]$GpoName = 'Wazuh - Active Response',

    [string]$LogRoot = 'C:\ProgramData\WazuhAR\Logs'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    throw "[FAILED] $Message"
}

function Step {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-AdsiObject {
    param([Parameter(Mandatory = $true)][string]$Dn)
    $obj = [ADSI]("LDAP://" + $Dn)
    $null = $obj.NativeObject
    $obj
}

Step 'Preflight'

if (-not (Get-Module -ListAvailable -Name GroupPolicy)) {
    Fail 'The GroupPolicy module is not installed. Run this on a DC or a workstation with GPMC/RSAT.'
}

Import-Module GroupPolicy -ErrorAction Stop

$rootDse = [ADSI]'LDAP://RootDSE'
$domainDn = [string]$rootDse.defaultNamingContext
if (-not $domainDn) {
    Fail 'Unable to determine the Active Directory naming context.'
}

$expectedDomainDn = ($DomainDns.Split('.') | ForEach-Object { "DC=$_" }) -join ','
if ($domainDn -ne $expectedDomainDn) {
    Fail "Connected domain '$domainDn' does not match -DomainDns '$DomainDns' ($expectedDomainDn)."
}

$null = Get-AdsiObject -Dn $TargetOuDn
Write-Host "Domain:    $DomainDns"
Write-Host "Target OU: $TargetOuDn"

Step 'Create or read GPO'

$gpo = Get-GPO -Name $GpoName -Domain $DomainDns -ErrorAction SilentlyContinue
if (-not $gpo) {
    if (-not $PSCmdlet.ShouldProcess($DomainDns, "Create GPO '$GpoName'")) {
        return
    }
    $gpo = New-GPO -Name $GpoName -Domain $DomainDns -Comment 'Deploy Wazuh Active Response scripts for GPUpdate and controlled reboot.'
} else {
    Write-Host "GPO already exists: $GpoName"
}

$gpoGuid = '{' + $gpo.Id.ToString().ToUpperInvariant() + '}'
$gpoRoot = "\\$DomainDns\SYSVOL\$DomainDns\Policies\$gpoGuid"
$machineScriptsDir = Join-Path $gpoRoot 'Machine\Scripts'
$startupDir = Join-Path $machineScriptsDir 'Startup'
$payloadDir = Join-Path $startupDir 'Payload'
$scriptsIni = Join-Path $machineScriptsDir 'scripts.ini'
$deployPs1Path = Join-Path $startupDir 'Deploy-WazuhActiveResponse.ps1'
$deployCmdPath = Join-Path $startupDir 'Deploy-WazuhActiveResponse.cmd'

if (-not (Test-Path -LiteralPath $gpoRoot -PathType Container)) {
    Fail "GPO SYSVOL path does not exist: $gpoRoot"
}

New-Item -ItemType Directory -Path $startupDir -Force | Out-Null
New-Item -ItemType Directory -Path $payloadDir -Force | Out-Null

Step 'Generate Active Response payload'

$gpupdateCmd = @"
@echo off
setlocal EnableExtensions
set "LOGDIR=$LogRoot"
set "LOGFILE=%LOGDIR%\gpupdate-computer.log"

if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1

echo [%DATE% %TIME%] START gpupdate-computer >> "%LOGFILE%"
"%SystemRoot%\System32\gpupdate.exe" /target:computer /force /wait:120 >> "%LOGFILE%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%DATE% %TIME%] END gpupdate-computer RC=%RC% >> "%LOGFILE%"

exit /b %RC%
"@

$gpupdateRebootCmd = @"
@echo off
setlocal EnableExtensions
set "LOGDIR=$LogRoot"
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
"@

Set-Content -LiteralPath (Join-Path $payloadDir 'gpupdate-computer.cmd') -Value $gpupdateCmd -Encoding ASCII
Set-Content -LiteralPath (Join-Path $payloadDir 'gpupdate-computer-reboot.cmd') -Value $gpupdateRebootCmd -Encoding ASCII

Step 'Generate startup deployer'

$deployPs1 = @"
Set-StrictMode -Version Latest
`$ErrorActionPreference = 'Stop'

`$Source = Join-Path `$PSScriptRoot 'Payload'
`$CandidateTargets = @(
    'C:\Program Files (x86)\ossec-agent\active-response\bin',
    'C:\Program Files\ossec-agent\active-response\bin'
)
`$Target = `$CandidateTargets |
    Where-Object { Test-Path -LiteralPath `$_ -PathType Container } |
    Select-Object -First 1

`$LogDir = '$LogRoot'
`$LogFile = Join-Path `$LogDir 'ActiveResponseDeploy.log'
New-Item -ItemType Directory -Path `$LogDir -Force | Out-Null

function Log {
    param([Parameter(Mandatory = `$true)][string]`$Text)
    Add-Content -LiteralPath `$LogFile -Encoding UTF8 -Value (
        '{0} | {1} | {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), `$env:COMPUTERNAME, `$Text
    )
}

try {
    Log 'START'

    if (-not (Test-Path -LiteralPath `$Source -PathType Container)) {
        throw "Payload directory is missing: `$Source"
    }

    if (-not `$Target) {
        throw 'Wazuh active-response\bin directory was not found.'
    }

    `$files = @(Get-ChildItem -LiteralPath `$Source -File)
    if (`$files.Count -eq 0) {
        throw 'Active Response payload is empty.'
    }

    `$changed = `$false

    foreach (`$src in `$files) {
        `$dst = Join-Path `$Target `$src.Name
        `$copyNeeded = `$true

        if (Test-Path -LiteralPath `$dst -PathType Leaf) {
            `$srcHash = (Get-FileHash -LiteralPath `$src.FullName -Algorithm SHA256).Hash
            `$dstHash = (Get-FileHash -LiteralPath `$dst -Algorithm SHA256).Hash
            if (`$srcHash -eq `$dstHash) {
                `$copyNeeded = `$false
                Log "UNCHANGED `$(`$src.Name) SHA256=`$srcHash"
            }
        }

        if (`$copyNeeded) {
            Copy-Item -LiteralPath `$src.FullName -Destination `$dst -Force
            `$srcHashAfter = (Get-FileHash -LiteralPath `$src.FullName -Algorithm SHA256).Hash
            `$dstHashAfter = (Get-FileHash -LiteralPath `$dst -Algorithm SHA256).Hash

            if (`$srcHashAfter -ne `$dstHashAfter) {
                throw "Hash mismatch after copying `$(`$src.Name)"
            }

            `$changed = `$true
            Log "DEPLOYED `$(`$src.Name) SHA256=`$dstHashAfter"
        }
    }

    if (`$changed) {
        `$svc = Get-Service -Name 'WazuhSvc' -ErrorAction Stop
        if (`$svc.Status -eq 'Running') {
            Restart-Service -Name 'WazuhSvc' -Force -ErrorAction Stop
        } else {
            Start-Service -Name 'WazuhSvc' -ErrorAction Stop
        }

        (Get-Service -Name 'WazuhSvc').WaitForStatus(
            [System.ServiceProcess.ServiceControllerStatus]::Running,
            (New-TimeSpan -Seconds 30)
        )
        Log 'WazuhSvc restarted/started'
    } else {
        Log 'No file changes - service restart not required'
    }

    Log "SUCCESS Target=`$Target Files=`$(`$files.Count)"
    exit 0
}
catch {
    Log ('ERROR ' + `$_.Exception.Message)
    exit 1
}
"@

$deployCmd = @'
@echo off
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0Deploy-WazuhActiveResponse.ps1"
exit /b %errorlevel%
'@

Set-Content -LiteralPath $deployPs1Path -Value $deployPs1 -Encoding UTF8
Set-Content -LiteralPath $deployCmdPath -Value $deployCmd -Encoding ASCII

Step 'Register startup script'

$scriptsIniContent = @"
[Startup]
0CmdLine=Deploy-WazuhActiveResponse.cmd
0Parameters=
"@
Set-Content -LiteralPath $scriptsIni -Value $scriptsIniContent -Encoding Unicode

$policyDn = "CN=$gpoGuid,CN=Policies,CN=System,$domainDn"
$policy = Get-AdsiObject -Dn $policyDn

$scriptCseGuid  = '{42B5FAAE-6536-11D2-AE5A-0000F87571E3}'
$scriptToolGuid = '{40B6664F-4972-11D1-A7CA-0000F87571E3}'
$scriptPair = "[$scriptCseGuid$scriptToolGuid]"

$currentExtensions = ''
if ($policy.Properties['gPCMachineExtensionNames'].Count -gt 0) {
    $currentExtensions = [string]$policy.Properties['gPCMachineExtensionNames'].Value
}
if ($currentExtensions -notlike "*$scriptCseGuid*") {
    $policy.Properties['gPCMachineExtensionNames'].Value = $currentExtensions + $scriptPair
}

$currentVersion = 0
if ($policy.Properties['versionNumber'].Count -gt 0) {
    $currentVersion = [int]$policy.Properties['versionNumber'].Value
}

$userVersion = ($currentVersion -shr 16) -band 0xFFFF
$computerVersion = $currentVersion -band 0xFFFF
$computerVersion = ($computerVersion + 1) -band 0xFFFF
$newVersion = ($userVersion -shl 16) -bor $computerVersion

$policy.Properties['versionNumber'].Value = $newVersion
$policy.CommitChanges()

Set-Content -LiteralPath (Join-Path $gpoRoot 'GPT.INI') -Encoding ASCII -Value @"
[General]
Version=$newVersion
"@

Step 'Link GPO'

$inheritance = Get-GPInheritance -Target $TargetOuDn -Domain $DomainDns
$links = @($inheritance.GpoLinks | Where-Object { $_.DisplayName -eq $GpoName })

if ($links.Count -eq 0) {
    New-GPLink -Name $GpoName -Target $TargetOuDn -Domain $DomainDns -LinkEnabled Yes | Out-Null
} elseif ($links.Count -eq 1) {
    Write-Host 'GPO link already exists.'
} else {
    Fail "More than one link to '$GpoName' was found on the target OU."
}

Step 'Verify'

$requiredFiles = @(
    $scriptsIni,
    $deployPs1Path,
    $deployCmdPath,
    (Join-Path $payloadDir 'gpupdate-computer.cmd'),
    (Join-Path $payloadDir 'gpupdate-computer-reboot.cmd')
)

foreach ($required in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        Fail "Required file missing after deployment: $required"
    }
}

Write-Host ''
Write-Host 'SUCCESS - WAZUH ACTIVE RESPONSE GPO READY' -ForegroundColor Green
Write-Host "GPO:    $GpoName"
Write-Host "GUID:   $gpoGuid"
Write-Host "OU:     $TargetOuDn"
Write-Host "SYSVOL: $gpoRoot"
Write-Host ''
Write-Host 'Existing clients need a normal reboot for the Computer Startup script to run.'
