# GPO 01 — create and safely link a GPO with PowerShell

This example is adapted from a real administration pattern and fully anonymized for public use.

The goal is intentionally small: create a GPO only when it does not already exist, resolve exactly one target OU, and avoid adding the same link twice.

## Requirements

- Windows Server or an administrative workstation with RSAT
- PowerShell
- `ActiveDirectory` module
- `GroupPolicy` module
- permissions to create and link GPOs

## Preview first

Run the script in preview mode:

```powershell
.\New-WorkstationBaselineGpo.ps1 -WhatIfMode
```

Example output:

```json
{
  "Domain": "contoso.local",
  "TargetOU": "OU=Workstations,DC=contoso,DC=local",
  "GpoName": "Contoso - Workstation Baseline",
  "LinkEnabled": true
}
```

No GPO or link is created in preview mode.

## Create and link

```powershell
.\New-WorkstationBaselineGpo.ps1
```

To create the GPO without linking it yet:

```powershell
.\New-WorkstationBaselineGpo.ps1 -NoLink
```

## Why these checks matter

The script refuses to continue unless the OU name resolves to exactly one object. This avoids accidentally linking a policy to the wrong OU when the same OU name exists in multiple branches.

It also checks whether the GPO and link already exist, so rerunning the script does not create duplicates.

## Next small step

A follow-up example can add one concrete policy setting with `Set-GPRegistryValue`, keeping the same preview, validation and idempotency pattern.
