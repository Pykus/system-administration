# Read-only GPO troubleshooting helper.
# Run in PowerShell as the affected user; elevation is only needed for some computer details.
$ErrorActionPreference = "Stop"
Write-Host "=== Identity ==="
whoami
Write-Host "
=== Computer ==="
Get-CimInstance Win32_ComputerSystem | Select-Object Name,Domain,PartOfDomain
Write-Host "
=== Applied policy summary ==="
gpresult /r
Write-Host "
=== Recent GroupPolicy operational events ==="
Get-WinEvent -LogName "Microsoft-Windows-GroupPolicy/Operational" -MaxEvents 20 -ErrorAction SilentlyContinue |
    Select-Object TimeCreated,Id,LevelDisplayName,Message
