# File Integrity Toolkit

One PowerShell script. One README. No extra files.

The tool does two useful things:

1. **Inventory** — creates a SHA-256 list of all files in a directory.
2. **Compare** — compares two directory trees and tells you exactly what changed.

## When this is useful

Use it when you want to answer questions like:

- Did the deployed application contain the same files as the release package?
- Did somebody change a configuration file?
- Is a file missing after a copy or restore?
- Did an unexpected file appear?
- Which files differ between two copies of the same folder?

## 1. Inventory mode

Command:

```powershell
.\File-IntegrityToolkit.ps1 -Mode Inventory -Root "C:\ExampleApp"
```

Example result:

```text
RelativePath        SizeBytes Sha256
------------        --------- ------
config\app.json            40 250d03796d94821d02e583894e29a02df5ccd230656d44307a3bf6f310b43f03
scripts\start.ps1          18 d1c2...
bin\helper.dll         113664 9a7b...
```

This gives you a compact fingerprint of the whole directory, not just one file.

You can save it:

```powershell
.\File-IntegrityToolkit.ps1 -Mode Inventory -Root "C:\ExampleApp" |
    Export-Csv ".\inventory.csv" -NoTypeInformation
```

## 2. Compare mode

Suppose you have:

### Reference directory

```text
reference\
├── config\app.json        -> {"port":8080}
└── scripts\start.ps1      -> Write-Output start
```

### Candidate directory

```text
candidate\
├── config\app.json        -> {"port":9090}
└── temp\debug.log         -> debug
```

Run:

```powershell
.\File-IntegrityToolkit.ps1 -Mode Compare `
    -Reference ".\reference" `
    -Candidate ".\candidate"
```

Result:

```text
Status   Path
------   ----
CHANGED  config\app.json
MISSING  scripts\start.ps1
EXTRA    temp\debug.log
```

Meaning:

- **CHANGED** — file exists in both places, but its SHA-256 differs.
- **MISSING** — file exists in the reference, but not in the candidate.
- **EXTRA** — file exists only in the candidate.
- **UNCHANGED** — shown only when you add `-ShowUnchanged`.

## Real example: deployment verification

You have a release package in:

```text
C:\Release\ExampleApp
```

and the installed copy in:

```text
C:\Program Files\ExampleApp
```

Run:

```powershell
.\File-IntegrityToolkit.ps1 -Mode Compare `
    -Reference "C:\Release\ExampleApp" `
    -Candidate "C:\Program Files\ExampleApp"
```

If the command prints nothing, no differences were found.

## Real example: configuration drift

Only compare configuration files:

```powershell
.\File-IntegrityToolkit.ps1 -Mode Compare `
    -Reference ".\KnownGoodConfig" `
    -Candidate ".\CurrentConfig" `
    -Include '*.json','*.xml','*.ini'
```

This is useful after upgrades, maintenance, or incident response.

## Built-in demo

You do not need to create any example folders manually.

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\File-IntegrityToolkit.ps1 -Demo
```

The script creates temporary sample data, compares it, prints the result, and removes the temporary files.

Expected output:

```text
Status   Path
------   ----
CHANGED  config\app.json
MISSING  scripts\start.ps1
EXTRA    temp\debug.log
```

## Safety

The Inventory and Compare modes are read-only. They calculate hashes and compare paths. They do not modify the directories being checked.
