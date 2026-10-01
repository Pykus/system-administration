#requires -Version 5.1
<#
.SYNOPSIS
Dispatches a GPUpdate Active Response script to one Wazuh agent.

.NOTES
A successful API response proves dispatch only. Verify endpoint logs and, for
the reboot action, observe the endpoint disconnecting and returning.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://')]
    [string]$ApiBase,

    [Parameter(Mandatory = $true)]
    [string]$Token,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{3,}$')]
    [string]$AgentId,

    [Parameter(Mandatory = $true)]
    [ValidateSet('GpUpdate', 'GpUpdateAndReboot')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'

$scriptName = switch ($Action) {
    'GpUpdate'          { 'gpupdate-computer.cmd' }
    'GpUpdateAndReboot' { 'gpupdate-computer-reboot.cmd' }
}

$uri = $ApiBase.TrimEnd('/') + '/active-response?agents_list=' +
       [uri]::EscapeDataString($AgentId) + '&wait_for_complete=true'

$headers = @{
    Authorization = "Bearer $Token"
    'Content-Type' = 'application/json'
}

$body = @{
    command   = '!' + $scriptName
    arguments = @()
} | ConvertTo-Json -Depth 4

$result = Invoke-RestMethod -Method Put -Uri $uri -Headers $headers -Body $body

$result | ConvertTo-Json -Depth 10

$data = $result.data
if (-not $data -or [int]$data.total_failed_items -gt 0 -or [int]$data.total_affected_items -lt 1) {
    throw 'Wazuh did not accept the Active Response request for the selected agent.'
}

Write-Warning 'DISPATCH ACCEPTED. This is not endpoint-execution confirmation.'
