[CmdletBinding()]
param(
    [string[]]$Name = @("W32Time", "Dnscache"),
    [string[]]$ExpectedRunning = @(),
    [switch]$AsJson,
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ExecutablePath {
    param([string]$PathName)

    if ([string]::IsNullOrWhiteSpace($PathName)) {
        return $null
    }

    if ($PathName.StartsWith('"')) {
        $closingQuote = $PathName.IndexOf('"', 1)
        if ($closingQuote -gt 1) {
            return $PathName.Substring(1, $closingQuote - 1)
        }
    }

    return ($PathName -split '\s+', 2)[0]
}

$expected = @{}
foreach ($item in $ExpectedRunning) {
    $expected[$item.ToLowerInvariant()] = $true
}

$rows = foreach ($serviceName in $Name | Sort-Object -Unique) {
    $escaped = $serviceName.Replace("'", "''")
    $svc = Get-CimInstance Win32_Service -Filter "Name='$escaped'" -ErrorAction SilentlyContinue

    if (-not $svc) {
        [pscustomobject]@{
            Name             = $serviceName
            Present          = $false
            State            = "MISSING"
            StartMode        = $null
            ProcessId        = $null
            StartName        = $null
            PathName         = $null
            ExecutablePath   = $null
            ExecutableExists = $null
            ExpectedRunning  = $expected.ContainsKey($serviceName.ToLowerInvariant())
            ExpectationMet   = $false
        }
        continue
    }

    $executable = Get-ExecutablePath -PathName $svc.PathName
    $shouldRun = $expected.ContainsKey($svc.Name.ToLowerInvariant())

    [pscustomobject]@{
        Name             = $svc.Name
        Present          = $true
        State            = $svc.State
        StartMode        = $svc.StartMode
        ProcessId        = $svc.ProcessId
        StartName        = $svc.StartName
        PathName         = $svc.PathName
        ExecutablePath   = $executable
        ExecutableExists = if ($executable) { Test-Path -LiteralPath $executable } else { $null }
        ExpectedRunning  = $shouldRun
        ExpectationMet   = if ($shouldRun) { $svc.State -eq "Running" } else { $true }
    }
}

if ($OutputPath) {
    $rows |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $OutputPath -Encoding UTF8
}

if ($AsJson) {
    $rows | ConvertTo-Json -Depth 4
}
else {
    $rows |
        Select-Object Name, Present, State, StartMode, StartName, ExecutableExists, ExpectedRunning, ExpectationMet |
        Format-Table -AutoSize
}
