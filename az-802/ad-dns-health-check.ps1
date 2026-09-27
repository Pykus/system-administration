# AZ-802 lab: read-only AD/DNS health checks for a domain controller.
$ErrorActionPreference = "Continue"
Write-Host "=== Domain controllers ==="
Get-ADDomainController -Filter * | Select-Object HostName,Site,IPv4Address,IsGlobalCatalog
Write-Host "
=== AD replication ==="
repadmin /replsummary
Write-Host "
=== DC diagnostics: DNS ==="
dcdiag /test:dns /e /v
Write-Host "
=== DNS server forwarders ==="
Get-DnsServerForwarder | Select-Object IPAddress,UseRootHint
