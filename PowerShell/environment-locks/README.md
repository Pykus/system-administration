# Environment lock exporter (PowerShell)

A small but practical PowerShell tool for answering a very common administration question:

> **“What exactly was installed in this working environment, and how can I check or rebuild it later?”**

The script creates a **privacy-conscious snapshot of selected tooling**, not a full image of the computer. It records:

- Python packages from a chosen interpreter or virtual environment,
- only the WinGet packages you explicitly allow,
- a machine-neutral manifest describing what was captured,
- optionally, a drift report against an older snapshot,
- optionally, a restore helper that is safe by default because it starts in **DRY-RUN** mode.

This makes the project useful for development PCs, lab machines, classroom workstations, automation hosts, small server-support environments, or simply for documenting a known-good toolset before making changes.

---

## What problem does it solve?

Imagine any of these situations:

1. You have a working Python / PowerShell workstation and are about to reinstall Windows.
2. You want several computers to have the same basic developer tools.
3. You are updating Python packages and want to know exactly what changed.
4. A script works on one PC but not on another, and you suspect package-version drift.
5. You are documenting a small automation environment for another administrator.
6. You want a reproducible record before experimenting with new packages.
7. You want to keep a public example on GitHub without exposing a complete workstation inventory.

This tool gives you a compact answer without trying to capture the entire operating system.

---

## What files are created?

A typical run can produce:

```text
environment-locks/
├── requirements.lock.txt
├── winget-packages.lock.json
├── manifest.json
├── drift-report.txt          # only when -BaselineDirectory is used
└── Restore-Environment.ps1   # only when -GenerateRestoreScript is used
```

### `requirements.lock.txt`

Created from:

```powershell
python -m pip freeze
```

Example:

```text
httpx==0.28.1
pandas==2.3.2
requests==2.32.5
```

Use it later with:

```powershell
python -m pip install -r .\requirements.lock.txt
```

### `winget-packages.lock.json`

WinGet can export a large list of installed software. This tool **does not keep the whole list**.

Instead, it filters the export to an explicit allow-list such as:

```powershell
@(
    "Git.Git",
    "Python.Python.3.12",
    "Microsoft.VisualStudioCode"
)
```

That prevents unrelated software from accidentally becoming part of a public snapshot.

### `manifest.json`

A small summary of the snapshot, for example:

```json
{
  "tool": "Export-EnvironmentLocks.ps1",
  "toolVersion": "2.0",
  "purpose": "Reproducible, privacy-conscious tooling snapshot",
  "python": {
    "succeeded": true,
    "version": "Python 3.12.x",
    "packageCount": 24,
    "output": "requirements.lock.txt"
  },
  "winget": {
    "succeeded": true,
    "capturedPackageCount": 3,
    "output": "winget-packages.lock.json"
  }
}
```

The manifest intentionally does **not** contain a computer name, user name, network configuration, credentials, environment variables, or full software inventory.

### `drift-report.txt`

Generated when you compare the new snapshot with an older one.

Example:

```text
PYTHON PACKAGES
---------------
- BASELINE: requests==2.31.0
+ CURRENT:  requests==2.32.5
+ CURRENT:  rich==14.1.0

WINGET PACKAGES
---------------
~ CHANGED: Git.Git  2.49.0 -> 2.50.1
```

That is useful when you want to answer:

> “What changed since the machine was known to be working?”

### `Restore-Environment.ps1`

Generated only when requested.

It is intentionally conservative:

```powershell
.\Restore-Environment.ps1
```

prints the actions it would perform but does **not** install anything.

Only this command performs installation:

```powershell
.\Restore-Environment.ps1 -Execute
```

---

## Requirements

- Windows 10 or Windows 11,
- PowerShell 5.1+ or PowerShell 7,
- Python + pip if you want the Python snapshot,
- WinGet if you want the WinGet snapshot.

Python and WinGet are independent stages. If one fails, the script still tries to complete the other stage and write the remaining useful output.

---

# Practical examples

## 1. Quick snapshot before reinstalling Windows

```powershell
.\Export-EnvironmentLocks.ps1 `
    -OutputDirectory .\before-reinstall `
    -GenerateRestoreScript
```

After reviewing the resulting files, store the directory somewhere safe or commit it to a private repository.

Later, after reinstalling Windows:

```powershell
cd .\before-reinstall
.\Restore-Environment.ps1
```

Review the dry-run output and only then run:

```powershell
.\Restore-Environment.ps1 -Execute
```

---

## 2. Capture one Python project virtual environment

If the project uses `.venv`:

```powershell
.\Export-EnvironmentLocks.ps1 `
    -OutputDirectory .\project-snapshot `
    -PythonExecutable .\.venv\Scripts\python.exe `
    -SkipWinget
```

This is a convenient way to document the exact installed Python state even when the project did not originally have a pinned requirements file.

---

## 3. Track only tools relevant to automation work

```powershell
.\Export-EnvironmentLocks.ps1 `
    -OutputDirectory .\automation-tools `
    -WingetPackageIds @(
        "Git.Git",
        "Python.Python.3.12",
        "Microsoft.PowerShell",
        "Microsoft.VisualStudioCode"
    )
```

The rest of the workstation software is deliberately ignored.

---

## 4. Compare a workstation before and after an upgrade

First create a baseline:

```powershell
.\Export-EnvironmentLocks.ps1 `
    -OutputDirectory .\baseline
```

Install updates, change packages, or experiment.

Then create a second snapshot:

```powershell
.\Export-EnvironmentLocks.ps1 `
    -OutputDirectory .\after-upgrade `
    -BaselineDirectory .\baseline
```

Open:

```text
after-upgrade\drift-report.txt
```

You now have a human-readable record of package drift.

---

## 5. Compare two similar lab computers

On computer A:

```powershell
.\Export-EnvironmentLocks.ps1 `
    -OutputDirectory C:\Temp\computer-a
```

Copy that folder to computer B, for example as:

```text
C:\Temp\computer-a-baseline
```

Then run on computer B:

```powershell
.\Export-EnvironmentLocks.ps1 `
    -OutputDirectory C:\Temp\computer-b `
    -BaselineDirectory C:\Temp\computer-a-baseline
```

The resulting drift report highlights differences in the tracked toolset without requiring a full inventory product.

---

## 6. Use only the Python part

```powershell
.\Export-EnvironmentLocks.ps1 `
    -SkipWinget `
    -OutputDirectory .\python-only
```

Useful on machines where WinGet is unavailable or irrelevant.

---

## 7. Use only the WinGet part

```powershell
.\Export-EnvironmentLocks.ps1 `
    -SkipPython `
    -WingetPackageIds @(
        "Git.Git",
        "Microsoft.PowerShell"
    ) `
    -OutputDirectory .\tools-only
```

Useful when Python is not part of the workstation role.

---

## 8. Generate a restore helper but inspect everything first

```powershell
.\Export-EnvironmentLocks.ps1 `
    -OutputDirectory .\known-good `
    -GenerateRestoreScript
```

Then:

```powershell
.\known-good\Restore-Environment.ps1
```

Example dry-run output:

```text
Mode: DRY-RUN
[Python]
  python -m pip install -r "...\requirements.lock.txt"

[WinGet]
  winget install --id Git.Git --exact ...
  winget install --id Microsoft.PowerShell --exact ...
```

If the commands look correct:

```powershell
.\known-good\Restore-Environment.ps1 -Execute
```

---

# Parameters

| Parameter | Purpose |
| --- | --- |
| `-OutputDirectory` | Where the snapshot files are written. |
| `-WingetPackageIds` | Explicit allow-list of WinGet packages to retain. |
| `-PythonExecutable` | Python command or path to a virtual-environment interpreter. |
| `-BaselineDirectory` | Older snapshot used to generate `drift-report.txt`. |
| `-GenerateRestoreScript` | Adds `Restore-Environment.ps1` to the output directory. |
| `-SkipPython` | Skip Python capture completely. |
| `-SkipWinget` | Skip WinGet capture completely. |

---

# What this tool deliberately does NOT do

It is **not** a system-imaging or full configuration-management product.

It does not capture:

- Windows accounts,
- passwords or credentials,
- API tokens,
- environment variables,
- host names,
- IP addresses or network topology,
- registry state,
- firewall rules,
- VPN configuration,
- browser data,
- Windows services,
- scheduled tasks,
- complete installed-software inventory,
- arbitrary files from the computer.

For full machine provisioning, tools such as Intune, DSC, Ansible, imaging, or dedicated configuration-management systems may be more appropriate.

This script intentionally solves a **smaller and safer problem**: keeping a readable, reproducible record of selected development / automation tooling.

---

# Why the WinGet allow-list matters

A normal package export can reveal far more about a workstation than you intended to publish.

For example, it might expose:

- specialist applications,
- corporate software,
- security products,
- remote-access tools,
- vendor-specific utilities.

This script first creates a temporary WinGet export and then keeps only package IDs explicitly supplied through `-WingetPackageIds`.

The temporary full export is removed after processing.

That makes the result much more suitable for examples, documentation, and public repositories.

---

# Error handling

Each major stage is isolated.

If Python export fails:

```text
WARNING: Python snapshot skipped: ...
```

WinGet is still attempted.

If WinGet fails:

```text
WARNING: WinGet snapshot skipped: ...
```

The manifest and any other possible stages still continue.

This is particularly useful on heterogeneous machines where not every workstation has exactly the same tooling installed.

---

# Suggested workflow for real use

A practical pattern is:

```text
1. Create known-good snapshot
2. Review snapshot files
3. Archive or version-control the snapshot
4. Make changes / upgrades
5. Create a new snapshot with -BaselineDirectory
6. Review drift-report.txt
7. Keep or roll back the changes
```

For a small lab or automation environment, this provides a lightweight change record without introducing a large configuration-management platform.

---

# Security note

Always review generated lock files before publishing them publicly.

`pip freeze` normally contains only package names and versions, but those names may still reveal project choices or technologies that you did not intend to disclose.

The script is designed to minimize accidental disclosure, not to replace human review.
