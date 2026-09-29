#requires -Version 5.1
<#
.SYNOPSIS
Read-only audit of Windows Scheduled Tasks with deterministic demo mode.

.DESCRIPTION
Finds enabled tasks that have never run, recently failed, or have not run within
a configurable age. It never modifies tasks. Use -Demo for a synthetic smoke
check on any Windows host without touching the local Task Scheduler.

.EXAMPLE
.\Invoke-ScheduledTaskAudit.ps1 -MaxAgeDays 14
.\Invoke-ScheduledTaskAudit.ps1 -Demo

Expected demo output contains one FAILED and one STALE task followed by
SUMMARY total=3 findings=2. Requires Windows PowerShell 5.1+.
#>
[CmdletBinding()]
param([int]$MaxAgeDays=30,[switch]$Demo)
$ErrorActionPreference='Stop'

function Test-TaskRecord {
    param($Task,[datetime]$Now,[int]$AgeDays)
    $findings=@()
    if($Task.Enabled -and $Task.LastTaskResult -ne 0){
        $findings += [pscustomobject]@{Name=$Task.Name;Issue='FAILED';Detail="LastTaskResult=$($Task.LastTaskResult)"}
    }
    if($Task.Enabled -and $Task.LastRunTime -eq [datetime]::MinValue){
        $findings += [pscustomobject]@{Name=$Task.Name;Issue='NEVER_RAN';Detail='No recorded run'}
    } elseif($Task.Enabled -and $Task.LastRunTime -lt $Now.AddDays(-$AgeDays)){
        $findings += [pscustomobject]@{Name=$Task.Name;Issue='STALE';Detail="LastRunTime=$($Task.LastRunTime.ToString('s'))"}
    }
    $findings
}

$now=Get-Date
if($Demo){
    $records=@(
        [pscustomobject]@{Name='Synthetic-Healthy';Enabled=$true;LastTaskResult=0;LastRunTime=$now.AddHours(-2)},
        [pscustomobject]@{Name='Synthetic-Failed';Enabled=$true;LastTaskResult=1;LastRunTime=$now.AddHours(-1)},
        [pscustomobject]@{Name='Synthetic-Stale';Enabled=$true;LastTaskResult=0;LastRunTime=$now.AddDays(-60)}
    )
} else {
    $records=Get-ScheduledTask | ForEach-Object {
        $info=Get-ScheduledTaskInfo -TaskName $_.TaskName -TaskPath $_.TaskPath
        [pscustomobject]@{Name=($_.TaskPath+$_.TaskName);Enabled=($_.State -ne 'Disabled');LastTaskResult=$info.LastTaskResult;LastRunTime=$info.LastRunTime}
    }
}
$findings=@($records | ForEach-Object { Test-TaskRecord $_ $now $MaxAgeDays })
$findings | Sort-Object Name,Issue | Format-Table -AutoSize
Write-Output ("SUMMARY total={0} findings={1}" -f $records.Count,$findings.Count)
if($Demo -and (($findings.Issue -notcontains 'FAILED') -or ($findings.Issue -notcontains 'STALE'))){throw 'Demo self-check failed'}