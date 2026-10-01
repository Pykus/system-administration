#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$LogRoot = 'C:\ProgramData\WazuhAR\Logs'
)

$ErrorActionPreference = 'Stop'

$targets = @(
    'C:\Program Files (x86)\ossec-agent\active-response\bin',
    'C:\Program Files\ossec-agent\active-response\bin'
)

$target = $targets | Where-Object { Test-Path -LiteralPath $_ -PathType Container } | Select-Object -First 1
if (-not $target) {
    throw 'Wazuh active-response\bin directory was not found.'
}

$required = @(
    'gpupdate-computer.cmd',
    'gpupdate-computer-reboot.cmd'
)

$rows = foreach ($name in $required) {
    $path = Join-Path $target $name
    [pscustomobject]@{
        File   = $name
        Exists = Test-Path -LiteralPath $path -PathType Leaf
        Path   = $path
        SHA256 = if (Test-Path -LiteralPath $path -PathType Leaf) {
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        } else {
            $null
        }
    }
}

$service = Get-Service -Name WazuhSvc -ErrorAction SilentlyContinue

Write-Host "Active Response directory: $target"
$rows | Format-Table -AutoSize

if ($service) {
    Write-Host "WazuhSvc: $($service.Status)"
} else {
    Write-Warning 'WazuhSvc was not found.'
}

$deployLog = Join-Path $LogRoot 'ActiveResponseDeploy.log'
if (Test-Path -LiteralPath $deployLog) {
    Write-Host ''
    Write-Host 'Deployment log (last 30 lines):'
    Get-Content -LiteralPath $deployLog -Tail 30
} else {
    Write-Warning "Deployment log does not exist: $deployLog"
}

if ($rows.Exists -contains $false) {
    throw 'One or more Active Response payload files are missing.'
}

if (-not $service -or $service.Status -ne 'Running') {
    throw 'WazuhSvc is not running.'
}

Write-Host ''
Write-Host 'CLIENT DEPLOYMENT CHECK: PASS' -ForegroundColor Green
