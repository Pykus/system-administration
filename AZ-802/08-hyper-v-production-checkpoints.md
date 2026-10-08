# 08 — Hyper-V Production Checkpoints: Safe Configuration and Recovery

## Purpose and decision

A Hyper-V checkpoint records a point-in-time VM state so an administrator can revert a lab or test change. It is **not a substitute for an independently restorable backup**. Checkpoints share the VM's storage failure domain and can grow as writes accumulate.

There are two important types:

| Type | What is captured | Best fit | Key risk |
| --- | --- | --- | --- |
| Standard | VM disk state and running memory state | Disposable labs and debugging | Reverting running distributed workloads can cause inconsistency |
| Production | Data-consistent disk state using Windows VSS or Linux file-system freeze; not RAM | Planned guest-aware changes | Requires guest integration/support; applications still need verification |

For server workloads, prefer `ProductionOnly` rather than silently falling back to a standard checkpoint. `Production` permits a standard fallback if a production checkpoint cannot be created; `ProductionOnly` fails instead. This distinction is especially important for domain controllers and transactional services.

## Read-only preflight

On a Hyper-V host with the Hyper-V PowerShell module:

```powershell
Get-VM -Name LAB-APP01 |
    Select-Object Name,State,CheckpointType,AutomaticCheckpointsEnabled
Get-VMIntegrationService -VMName LAB-APP01 |
    Where-Object Name -match 'Backup|Volume Shadow Copy' |
    Select-Object Name,Enabled,PrimaryStatusDescription
Get-VMCheckpoint -VMName LAB-APP01 |
    Select-Object Name,CheckpointType,CreationTime
Get-VMHardDiskDrive -VMName LAB-APP01 |
    Select-Object ControllerType,ControllerNumber,ControllerLocation,Path
```

**Expected behavior:** The commands identify the VM's checkpoint policy, guest backup integration, existing checkpoints and disk paths without changing anything.

**Concrete expected output — illustrative lab state**, not an actual host capture:

```text
Name      State   CheckpointType AutomaticCheckpointsEnabled
----      -----   -------------- ---------------------------
LAB-APP01 Running ProductionOnly                       False
```

The other commands are inventory queries; their rows depend on the VM. Do not interpret an empty checkpoint list as a failure. Confirm the guest's backup integration and application-specific requirements before creating a checkpoint.

## Controlled lab: create and verify

Run only on a disposable lab VM with a separate tested backup. First set a strict policy:

```powershell
Set-VM -Name LAB-APP01 -CheckpointType ProductionOnly
Get-VM -Name LAB-APP01 | Select-Object Name,CheckpointType
```

**Expected output — illustrative:**

```text
Name      CheckpointType
----      --------------
LAB-APP01 ProductionOnly
```

`Set-VM` itself normally prints no output. Next create a named checkpoint and verify it exists:

```powershell
Checkpoint-VM -Name LAB-APP01 -SnapshotName BeforeLabChange
Get-VMCheckpoint -VMName LAB-APP01 |
    Where-Object Name -eq 'BeforeLabChange' |
    Select-Object Name,CheckpointType
```

**Expected output — illustrative after a successful production checkpoint:**

```text
Name            CheckpointType
----            --------------
BeforeLabChange Production
```

`Checkpoint-VM` normally prints no output. A failed production checkpoint in `ProductionOnly` mode must be investigated, not bypassed by switching to `Standard`. The displayed checkpoint type is the **actual created type**, while `CheckpointType` on `Get-VM` is the **configured policy**.

## Revert and cleanup: deliberate operations only

**Restore is destructive to post-checkpoint guest changes.** Never automate a restore on a production VM based only on a failed test. On a disposable lab VM, after explicitly approving the rollback:

```powershell
Restore-VMCheckpoint -VMName LAB-APP01 -Name BeforeLabChange -Confirm:$false
```

The restore command normally has no stdout. Verify the VM state, boot behavior, service health and application data; production checkpoints do not restore running memory.

Once the checkpoint is no longer needed, remove it using Hyper-V tools:

```powershell
Remove-VMCheckpoint -VMName LAB-APP01 -Name BeforeLabChange
Get-VMCheckpoint -VMName LAB-APP01 |
    Where-Object Name -eq 'BeforeLabChange'
```

**Exact expected output of the final query after successful removal:** no rows (empty stdout). Do **not** manually delete `.avhdx` differencing disks; Hyper-V manages their merge. Allow time and free disk space for merging, and confirm the VM still operates correctly.

## Failure diagnosis

| Observation | Check first | Avoid |
| --- | --- | --- |
| Production checkpoint fails | Guest backup integration, VSS writers, Linux freeze support, host/guest logs | Quietly enabling standard fallback |
| Checkpoint exists but app is inconsistent | Application quiescence and backup-aware behavior | Assuming a checkpoint equals a tested backup |
| Checkpoint deletion takes time | AVHDX merge progress, free capacity and I/O | Deleting AVHDX manually |
| VM boots after restore but service fails | Guest service state, network, database recovery, application health | Declaring success from Hyper-V state alone |

For Windows guests, inspect VSS writer health inside the guest (`vssadmin list writers`) and relevant event logs; do not treat a single VSS status as proof of application recovery. For Linux guests, verify supported freeze/integration components. A storage-level point in time cannot replace an application-aware backup and restore test.

## Verification checklist

1. Confirm the VM, owner, maintenance window, backup and available capacity.
2. Record `CheckpointType` and guest integration status.
3. Prefer `ProductionOnly` for appropriate server workloads.
4. Verify the checkpoint was actually created with the expected type.
5. Test the application, not just the VM's `Running` state.
6. Remove temporary checkpoints through Hyper-V and confirm merge/health.
7. Record the result, evidence and rollback decision.

**AZ-802 takeaway:** Know the difference between Standard, Production and ProductionOnly; understand VSS/file-system freeze, AVHDX merge behavior, and why checkpoints are not backups.

## References

- [Microsoft Learn — Using Hyper-V checkpoints](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/checkpoints)
- [Microsoft Learn — Set-VM](https://learn.microsoft.com/en-us/powershell/module/hyper-v/set-vm)
- [Microsoft Learn — Checkpoint-VM](https://learn.microsoft.com/en-us/powershell/module/hyper-v/checkpoint-vm)

All host and VM names are synthetic. Expected outputs are illustrative; no live Hyper-V execution is claimed.
