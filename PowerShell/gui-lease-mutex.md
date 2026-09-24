# PowerShell GUI lease: a simple cross-process mutex

When several automation workers share one interactive desktop, they must not click or type at the same time. A small filesystem lease is often enough to serialize GUI access.

The pattern below is intentionally generic. It stores the current owner and an expiry time in a directory that can be created atomically.

## Acquire

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$Owner,

    [string]$Resource = "desktop",

    [int]$LeaseSeconds = 300
)

$ErrorActionPreference = "Stop"
$LockRoot = "C:\Automation\locks"
$LeaseDir = Join-Path $LockRoot "$Resource.lease"
$Metadata = Join-Path $LeaseDir "lease.json"

New-Item -ItemType Directory -Force $LockRoot | Out-Null

function Try-AcquireLease {
    try {
        New-Item -ItemType Directory -Path $LeaseDir -ErrorAction Stop | Out-Null

        $now = [DateTimeOffset]::UtcNow
        [pscustomobject]@{
            owner        = $Owner
            acquired_utc = $now.ToString("o")
            expires_utc  = $now.AddSeconds($LeaseSeconds).ToString("o")
            host         = $env:COMPUTERNAME
            pid          = $PID
        } | ConvertTo-Json | Set-Content -Encoding UTF8 $Metadata

        Write-Output "ACQUIRED owner=$Owner"
        return $true
    }
    catch {
        return $false
    }
}

if (Try-AcquireLease) { exit 0 }

$stale = $false
try {
    $meta = Get-Content $Metadata -Raw | ConvertFrom-Json
    $expires = [DateTimeOffset]::Parse($meta.expires_utc)
    if ($expires -lt [DateTimeOffset]::UtcNow) {
        $stale = $true
    }
}
catch {
    $stale = $true
}

if ($stale) {
    Remove-Item $LeaseDir -Recurse -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 200

    if (Try-AcquireLease) { exit 0 }
}

try {
    $meta = Get-Content $Metadata -Raw | ConvertFrom-Json
    Write-Output ("BUSY owner={0} expires={1}" -f $meta.owner, $meta.expires_utc)
}
catch {
    Write-Output "BUSY owner=unknown"
}

exit 2
```

## Release

Only the owner that acquired the lease should be able to release it.

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$Owner,

    [string]$Resource = "desktop"
)

$LeaseDir = "C:\Automation\locks\$Resource.lease"
$Metadata = Join-Path $LeaseDir "lease.json"

if (-not (Test-Path $LeaseDir)) {
    Write-Output "NO_LOCK"
    exit 0
}

try {
    $meta = Get-Content $Metadata -Raw | ConvertFrom-Json

    if ($meta.owner -ne $Owner) {
        Write-Output ("NOT_OWNER current={0}" -f $meta.owner)
        exit 3
    }
}
catch {
    Write-Output "INVALID_METADATA"
    exit 4
}

Remove-Item $LeaseDir -Recurse -Force
Write-Output "RELEASED owner=$Owner"
```

## Usage

```powershell
.\Acquire-GuiLease.ps1 -Owner "worker-a" -LeaseSeconds 300
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

try {
    # Perform one short, atomic GUI step here.
}
finally {
    .\Release-GuiLease.ps1 -Owner "worker-a"
}
```

## Guardrails

- Never release a lease without checking the owner.
- Keep GUI steps short and atomic.
- Always release in `finally`.
- Give leases an expiry so a crashed worker cannot block the desktop forever.
- A stale lease may be reclaimed, but a live lease must not be bypassed.
- File/API/terminal work that does not touch the shared GUI should not take the GUI lease.
