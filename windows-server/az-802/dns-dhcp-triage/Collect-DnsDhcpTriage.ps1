[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$NameToResolve,

    [string]$OutputPath = ".\dns-dhcp-triage.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-DnsCheck {
    param(
        [Parameter(Mandatory)][string]$Name,
        [string]$Server
    )

    try {
        $params = @{
            Name        = $Name
            DnsOnly     = $true
            ErrorAction = "Stop"
        }
        if ($Server) {
            $params.Server = $Server
        }

        $answers = Resolve-DnsName @params |
            Where-Object { $_.IPAddress } |
            Select-Object -ExpandProperty IPAddress -Unique

        [pscustomobject]@{
            Server    = if ($Server) { $Server } else { "system-default" }
            Success   = $true
            Addresses = @($answers)
            Error     = $null
        }
    }
    catch {
        [pscustomobject]@{
            Server    = if ($Server) { $Server } else { "system-default" }
            Success   = $false
            Addresses = @()
            Error     = $_.Exception.Message
        }
    }
}

$configurations = Get-CimInstance Win32_NetworkAdapterConfiguration |
    Where-Object { $_.IPEnabled } |
    ForEach-Object {
        $ipv4 = @($_.IPAddress | Where-Object { $_ -match '^\d{1,3}(\.\d{1,3}){3}$' })
        [pscustomobject]@{
            Description = $_.Description
            DHCPEnabled = [bool]$_.DHCPEnabled
            DHCPServer  = $_.DHCPServer
            IPv4        = $ipv4
            HasAPIPA    = [bool]($ipv4 | Where-Object { $_ -like '169.254.*' })
            Gateways    = @($_.DefaultIPGateway)
            DNSServers  = @($_.DNSServerSearchOrder)
        }
    }

$dnsServers = @(
    $configurations |
        ForEach-Object { $_.DNSServers } |
        Where-Object { $_ } |
        Sort-Object -Unique
)

$dnsChecks = @()
$dnsChecks += Invoke-DnsCheck -Name $NameToResolve
foreach ($server in $dnsServers) {
    $dnsChecks += Invoke-DnsCheck -Name $NameToResolve -Server $server
}

$report = [ordered]@{
    CollectedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    ComputerName   = $env:COMPUTERNAME
    NameToResolve  = $NameToResolve
    Interfaces     = @($configurations)
    DnsChecks      = @($dnsChecks)
}

$report |
    ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $OutputPath -Encoding UTF8

$report | ConvertTo-Json -Depth 8
