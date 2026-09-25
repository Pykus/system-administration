# PowerShell: report stale Active Directory computers

Read-only example for finding computer accounts that have not logged on recently.

```powershell
$Cutoff = (Get-Date).AddDays(-90)

Get-ADComputer -Filter * -Properties LastLogonDate, Enabled |
    Where-Object {
        $_.Enabled -eq $true -and
        $_.LastLogonDate -and
        $_.LastLogonDate -lt $Cutoff
    } |
    Select-Object Name, LastLogonDate |
    Sort-Object LastLogonDate
```

## Safe workflow

1. Run read-only first.
2. Export the result and review it.
3. Confirm whether listed devices were retired, reimaged, or simply unused.
4. Do not disable or delete accounts automatically from this report alone.

## Optional CSV export

```powershell
... | Export-Csv .\stale-computers.csv -NoTypeInformation -Encoding UTF8
```

Use synthetic lab names such as `PC001`, `PC002`; never publish real hostnames or directory structure from production.