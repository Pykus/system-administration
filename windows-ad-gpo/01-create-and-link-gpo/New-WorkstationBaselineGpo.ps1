param(
    [string]$GpoName = "Contoso - Workstation Baseline",
    [string]$OuName = "Workstations",
    [switch]$WhatIfMode,
    [switch]$NoLink
)

$ErrorActionPreference = "Stop"

Import-Module ActiveDirectory
Import-Module GroupPolicy

$domain = Get-ADDomain
$domainDn = $domain.DistinguishedName

$ous = @(
    Get-ADOrganizationalUnit `
        -LDAPFilter ("(ou={0})" -f $OuName) `
        -SearchBase $domainDn `
        -SearchScope Subtree
)

if ($ous.Count -ne 1) {
    throw "Expected exactly one OU named '$OuName'; found $($ous.Count). Nothing changed."
}

$ou = $ous[0]

$preview = [ordered]@{
    Domain      = $domain.DNSRoot
    TargetOU    = $ou.DistinguishedName
    GpoName     = $GpoName
    LinkEnabled = -not $NoLink
}

if ($WhatIfMode) {
    $preview | ConvertTo-Json -Depth 3
    exit 0
}

$gpo = Get-GPO -Name $GpoName -ErrorAction SilentlyContinue

if (-not $gpo) {
    $gpo = New-GPO `
        -Name $GpoName `
        -Comment "Example workstation baseline created by PowerShell."
}

if (-not $NoLink) {
    $inheritance = Get-GPInheritance -Target $ou.DistinguishedName
    $existingLink = @(
        $inheritance.GpoLinks |
            Where-Object { $_.DisplayName -eq $GpoName }
    )

    if (-not $existingLink) {
        New-GPLink `
            -Name $GpoName `
            -Target $ou.DistinguishedName `
            -LinkEnabled Yes |
            Out-Null
    }
}

[pscustomobject]@{
    Ok       = $true
    GpoName  = $gpo.DisplayName
    GpoId    = $gpo.Id
    TargetOU = $ou.DistinguishedName
    Linked   = -not $NoLink
}
