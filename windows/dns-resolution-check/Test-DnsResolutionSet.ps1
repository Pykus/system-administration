#requires -Version 5.1
<#
.SYNOPSIS
Read-only DNS resolution checker for a set of host names.

.DESCRIPTION
Resolves each requested name and returns a compact PASS/FAIL table. An optional
-DnsServer parameter lets administrators test a specific resolver. -Demo uses
synthetic results and therefore needs no network access.

.EXAMPLE
.\Test-DnsResolutionSet.ps1 -Name app.example.org,db.example.org
.\Test-DnsResolutionSet.ps1 -Name app.example.org -DnsServer 192.0.2.53
.\Test-DnsResolutionSet.ps1 -Demo

Expected demo result: one PASS, one FAIL, then SUMMARY total=2 passed=1 failed=1.
The script changes no DNS settings and requires Windows PowerShell 5.1+.
#>
[CmdletBinding()]
param([string[]]$Name,[string]$DnsServer,[switch]$Demo)
$ErrorActionPreference='Stop'

function New-Result([string]$HostName,[bool]$Ok,[string]$Answer,[string]$ErrorText){
    [pscustomobject]@{Name=$HostName;Status=($(if($Ok){'PASS'}else{'FAIL'}));Answer=$Answer;Error=$ErrorText}
}
if($Demo){
    $results=@(
        (New-Result 'app.example.org' $true '192.0.2.10' ''),
        (New-Result 'missing.example.org' $false '' 'Synthetic NXDOMAIN')
    )
} else {
    if(-not $Name){throw 'Provide -Name or use -Demo.'}
    $results=foreach($n in $Name){
        try{
            $args=@{Name=$n;Type='A';ErrorAction='Stop'}
            if($DnsServer){$args.Server=$DnsServer}
            $answers=Resolve-DnsName @args | Where-Object IPAddress | Select-Object -ExpandProperty IPAddress -Unique
            New-Result $n ($answers.Count -gt 0) ($answers -join ',') ''
        }catch{
            New-Result $n $false '' $_.Exception.Message
        }
    }
}
$results | Format-Table -AutoSize
$passed=@($results|Where-Object Status -eq 'PASS').Count
$failed=@($results|Where-Object Status -eq 'FAIL').Count
Write-Output ("SUMMARY total={0} passed={1} failed={2}" -f $results.Count,$passed,$failed)
if($Demo -and ($passed -ne 1 -or $failed -ne 1)){throw 'Demo self-check failed'}