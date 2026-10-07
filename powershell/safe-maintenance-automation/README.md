# Safe PowerShell maintenance automation with preflight, idempotency, and evidence

Administrative PowerShell becomes risky when a script is written as a sequence of commands that assumes the machine is already in the expected state. A production maintenance script should instead behave like a small transaction: inspect the target, decide whether a change is necessary, make the smallest change, verify the result, and leave evidence that another administrator can understand later.

This chapter shows a reusable pattern for Windows Server and workstation administration. The examples use services and files because they are easy to reproduce, but the same structure applies to registry settings, scheduled tasks, firewall rules, deployment agents, and configuration repair.

## When to use this pattern

Use it for repeatable maintenance that may run more than once: scheduled remediation, fleet repair, post-deployment validation, agent configuration, or controlled changes executed remotely. Idempotency matters because automation systems retry after timeouts and operators sometimes rerun a job when the first result is unclear.

Do not use unattended remediation when the change has destructive consequences, when rollback is unknown, or when the desired state cannot be determined safely. Domain controller promotion, storage reconfiguration, schema changes, and irreversible data migration deserve a separate change procedure rather than a generic repair loop.

## 1. Preflight before mutation

A useful preflight checks privileges, required paths, dependencies, current state, and whether the requested target is plausible.

```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Administrative privileges are required.'
    }
}

function Get-ServiceSnapshot {
    param([Parameter(Mandatory)][string]$Name)
    $svc = Get-CimInstance Win32_Service -Filter "Name='$Name'"
    if (-not $svc) { throw "Service '$Name' does not exist." }
    [pscustomobject]@{
        Name      = $svc.Name
        State     = $svc.State
        StartMode = $svc.StartMode
        PathName  = $svc.PathName
    }
}

Assert-Administrator
$before = Get-ServiceSnapshot -Name 'w32time'
$before | Format-List
```

The snapshot is evidence as well as input to the decision. Avoid testing only whether a command exits successfully: a successful command does not prove the resulting state is correct.

## 2. Express desired state explicitly

Separate *detect* from *change*. The function below changes startup type only when necessary and starts the service only when it is stopped.

```powershell
function Ensure-ServiceState {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)][string]$Name,
        [ValidateSet('Automatic','Manual','Disabled')]
        [string]$StartupType = 'Automatic',
        [ValidateSet('Running','Stopped')]
        [string]$State = 'Running'
    )

    $svc = Get-Service -Name $Name -ErrorAction Stop
    $cim = Get-CimInstance Win32_Service -Filter "Name='$Name'"

    $desiredMode = switch ($StartupType) {
        'Automatic' { 'Auto' }
        'Manual'    { 'Manual' }
        'Disabled'  { 'Disabled' }
    }

    if ($cim.StartMode -ne $desiredMode) {
        if ($PSCmdlet.ShouldProcess($Name, "Set startup type to $StartupType")) {
            Set-Service -Name $Name -StartupType $StartupType
        }
    }

    if ($State -eq 'Running' -and $svc.Status -ne 'Running') {
        if ($PSCmdlet.ShouldProcess($Name, 'Start service')) {
            Start-Service -Name $Name
        }
    }
    elseif ($State -eq 'Stopped' -and $svc.Status -ne 'Stopped') {
        if ($PSCmdlet.ShouldProcess($Name, 'Stop service')) {
            Stop-Service -Name $Name
        }
    }
}
```

Run `Ensure-ServiceState -Name w32time -WhatIf` first. `SupportsShouldProcess` gives operators a dry-run path and makes intent visible.

## 3. Make file changes atomically

Editing a configuration file in place can leave a truncated file after interruption. Write a temporary file, validate it, preserve the old version, and then replace the target.

```powershell
function Set-JsonConfigSafely {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][hashtable]$Configuration
    )

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $temp = "$Path.new"
    $backup = "$Path.bak"

    $Configuration | ConvertTo-Json -Depth 10 | Set-Content -Path $temp -Encoding UTF8

    # Parse the candidate before it can replace production configuration.
    $null = Get-Content $temp -Raw | ConvertFrom-Json

    if (Test-Path $Path) {
        Copy-Item $Path $backup -Force
    }
    Move-Item $temp $Path -Force
}
```

For sensitive configuration, do not write passwords or API tokens into logs or backups. Use the platform's secret store, protected credentials, or an ACL-restricted source appropriate to the environment.

## 4. Verification must test the outcome

After mutation, read the target again. For a service, verify both startup mode and runtime state. For network software, also test its listening port or health endpoint.

```powershell
Ensure-ServiceState -Name 'w32time' -StartupType Automatic -State Running

$after = Get-ServiceSnapshot -Name 'w32time'
if ($after.StartMode -ne 'Auto' -or $after.State -ne 'Running') {
    throw "Verification failed: $($after | ConvertTo-Json -Compress)"
}

$after | ConvertTo-Json -Depth 4
```

A stronger verification for an application service might combine `Get-Service`, `Test-NetConnection -ComputerName localhost -Port 8080`, and an HTTP health request. Choose evidence that proves the feature works, not merely that its process exists.

## 5. Structured evidence and exit codes

Human-readable console text is useful interactively but weak for orchestration. Emit a small JSON record and return a non-zero exit code on failure.

```powershell
$started = Get-Date
try {
    Assert-Administrator
    $before = Get-ServiceSnapshot 'w32time'
    Ensure-ServiceState -Name 'w32time' -StartupType Automatic -State Running
    $after = Get-ServiceSnapshot 'w32time'

    if ($after.State -ne 'Running' -or $after.StartMode -ne 'Auto') {
        throw 'Post-change verification did not reach desired state.'
    }

    [pscustomobject]@{
        timestamp = (Get-Date).ToString('o')
        target    = $env:COMPUTERNAME
        operation = 'ensure-service-state'
        changed   = ($before.State -ne $after.State -or $before.StartMode -ne $after.StartMode)
        verified  = $true
        before    = $before
        after     = $after
        duration_ms = [int]((Get-Date) - $started).TotalMilliseconds
    } | ConvertTo-Json -Depth 6
    exit 0
}
catch {
    [pscustomobject]@{
        timestamp = (Get-Date).ToString('o')
        target    = $env:COMPUTERNAME
        operation = 'ensure-service-state'
        verified  = $false
        error     = $_.Exception.Message
    } | ConvertTo-Json -Depth 4
    exit 1
}
```

This is suitable for a scheduler, remote execution service, or monitoring system because success has a precise meaning.

## Common failure modes

**Blind retries.** Retrying a non-idempotent command can duplicate tasks, rules, or records. Detect current state first.

**Restarting too early.** A restart can hide the actual configuration failure and can create an outage. Verify configuration before restarting anything, and restart only when the product requires it.

**Using process exit as verification.** `Set-Service` returning without an exception does not prove the application is healthy. Re-read state and test the service boundary.

**Catching and ignoring exceptions.** A broad `catch { Write-Warning ... }` followed by exit code zero converts failure into false success. Failed verification must propagate as failure.

**Logging secrets.** Transcript logging, `ConvertTo-Json`, command-line arguments, and exception text can expose credentials. Redact or omit sensitive fields.

**No rollback evidence.** Before replacing configuration, record the original state or keep a controlled backup. For registry changes, export the relevant key or store the exact previous value.

## Testing the automation

Test four paths, not just the happy path:

1. **Already compliant:** run twice. The second run should report `changed=false`.
2. **Repairable drift:** deliberately set a safe test service to the wrong state, run remediation, and verify the desired state.
3. **Dependency failure:** use a nonexistent service or inaccessible path and confirm a non-zero exit with useful evidence.
4. **Dry run:** use `-WhatIf` and confirm no state changes occur.

In a lab, also interrupt the script during a file update and confirm the original configuration remains usable. If the script is used remotely, test a timeout and a repeated invocation to prove that retry does not duplicate changes.

## Practical conclusion

Reliable PowerShell administration is less about compact one-liners and more about state transitions that can be proved. A production-quality automation should answer five questions: What was the state before? Was a change necessary? What exactly changed? Does the target now work? What evidence remains for the next operator? Building scripts around those questions makes retries safer, monitoring more trustworthy, and incident diagnosis substantially easier.
