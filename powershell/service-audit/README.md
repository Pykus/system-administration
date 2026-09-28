# Read-only Windows service audit

This tool answers a practical question: **is a required Windows service present, configured to start as expected, and actually running under the expected executable/account?**

It is intended for agent and infrastructure troubleshooting before changing anything on the machine.

## What it checks

For each requested service, `Get-ServiceAudit.ps1` collects:

- service existence;
- current state;
- start mode;
- process ID;
- service account;
- executable command line/path;
- whether the executable path can be resolved to an existing file;
- optional expectation checks for services that should currently be running.

The script does **not** start, stop, restart, reconfigure, or repair services.

## Examples

Audit two built-in services:

```powershell
.\Get-ServiceAudit.ps1 -Name W32Time,Dnscache
```

Mark a service as expected to be running and emit JSON for automation:

```powershell
.\Get-ServiceAudit.ps1 -Name W32Time -ExpectedRunning W32Time -AsJson
```

Write the report to disk:

```powershell
.\Get-ServiceAudit.ps1 -Name W32Time,Dnscache -OutputPath .\service-audit.json
```

## How to use the result

- `MISSING`: the expected service is not installed or the name is wrong.
- `Stopped` with `ExpectedRunning=true`: investigate the service log and dependencies before restarting it.
- unexpected `StartMode`: the service may not survive a reboot even if it is running now.
- unexpected `StartName`: useful when diagnosing permission or credential changes.
- executable not found: the service registration may point to a removed or moved binary.

The default examples use generic Windows services only. Add product-specific service names locally when needed.
