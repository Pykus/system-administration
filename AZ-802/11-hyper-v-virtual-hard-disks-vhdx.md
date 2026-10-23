# 11 — Hyper-V Virtual Hard Disks (VHDX): Create, Resize, and Troubleshoot

> **Exam:** AZ-802 — Administering Windows Server  
> **Official objective:** Manage VMs (10–15%) → Manage Hyper-V and guest VMs → **Manage Hyper-V virtual hard disks**.  
> **Lab:** Hyper-V host `HV01`; disposable Windows Server guest `LAB-APP01`.  
> **Public safety:** All names, paths, and values are fictional. Do not run storage operations on an unverified or production disk. Outputs described as examples are illustrative, not captured from a real host.

## 1. Core idea

A virtual hard disk is a file on a Hyper-V host that appears as a block-storage device in a VM. The host manages the **virtual disk file and its capacity**, but Windows inside the guest manages **disks, partitions, and volumes**.

| Format | Maximum virtual capacity | Typical use |
| --- | ---: | --- |
| `.vhd` | 2 TB | Older Hyper-V compatibility |
| **`.vhdx`** | **64 TB** | Modern Hyper-V, resilience improvements, larger disks, supported online resizing |

VHDX metadata logging improves resilience, but it is **not a backup**.

### Fixed, dynamic, and differencing

| Type | Allocation | Advantage | Risk / consideration |
| --- | --- | --- | --- |
| **Fixed** | Capacity allocated on the host when created | Predictable reservation and low allocation overhead | Immediately consumes host storage |
| **Dynamic** | Host file grows on demand up to virtual capacity | Efficient lab and variable-demand storage | Host file can exhaust physical free space |
| **Differencing** | Child stores changes; parent supplies unchanged blocks | Reusable lab templates | Parent dependency; chain complexity |

**Exam trap:** `VHDX` is a **format**, whereas `Fixed`, `Dynamic`, and `Differencing` describe disk allocation or relationship types.

## 2. Scenario

You have an existing, disposable VM `LAB-APP01` running Windows Server on Hyper-V host `HV01`. It has a separate OS disk. Your job is to:

1. Identify its existing disk paths and controller types.
2. Create an **8 GiB dynamically expanding VHDX** on the host.
3. Attach it as a **new data disk through virtual SCSI** while the VM is Off.
4. Initialize and format only the verified new disk in the guest.
5. Expand its virtual capacity from **8 GiB to 12 GiB** without shutting down the VM.
6. Expand its NTFS partition inside the guest.
7. Diagnose capacity, differencing disk, checkpoint, and compaction problems.

Note that PowerShell `8GB` means 8 GiB, or 8,589,934,592 bytes.

## 3. Diagnosis — read-only preflight on HV01

Run as an administrator **on the Hyper-V host**, not inside the guest:

```powershell
Import-Module Hyper-V

Get-VM -Name 'LAB-APP01' |
    Select-Object Name, State, Generation, Status

Get-VMHardDiskDrive -VMName 'LAB-APP01' |
    Select-Object VMName, ControllerType, ControllerNumber, ControllerLocation, Path

Get-VMHardDiskDrive -VMName 'LAB-APP01' |
    Where-Object { $_.Path } |
    ForEach-Object {
        Get-VHD -Path $_.Path |
            Select-Object Path, VhdFormat, VhdType, Size, FileSize, ParentPath
    }

Get-VMCheckpoint -VMName 'LAB-APP01' |
    Select-Object Name, CreationTime, CheckpointType

Get-Volume -DriveLetter C |
    Select-Object DriveLetter, FileSystem, Size, SizeRemaining
```

**Interpretation:**

- `Get-VMHardDiskDrive` reports a VM disk's **file path and IDE/SCSI controller**.
- `Get-VHD.Size` is the virtual capacity, in bytes.
- `Get-VHD.FileSize` is the current host-file allocation, in bytes.
- `Get-VHD.VhdType` identifies Fixed, Dynamic, or Differencing.
- `Get-VHD.ParentPath` identifies the parent in a differencing chain.
- `Get-VMCheckpoint` shows Hyper-V-managed checkpoints. The guest might write to an active `.avhdx` child, not to the base `.vhdx`.

**Never edit, delete, or resize a parent disk in an active differencing/checkpoint chain.** Confirm actual VM attachments before changing any file.

## 4. Commands — create a dynamic data VHDX

Run on **HV01**. The VM must **already be Off**; no force shutdown is included.

```powershell
$vmName  = 'LAB-APP01'
$labDir  = 'C:\HyperV-Lab\Disks'
$vhdPath = Join-Path $labDir 'lab-data.vhdx'

$vm = Get-VM -Name $vmName -ErrorAction Stop
if ($vm.State -ne 'Off') {
    throw "$vmName must be Off before this lab."
}

New-Item -ItemType Directory -Path $labDir -Force | Out-Null

if (Test-Path -LiteralPath $vhdPath) {
    throw "The lab disk already exists: $vhdPath"
}

New-VHD -Path $vhdPath -SizeBytes 8GB -Dynamic |
    Select-Object Path, VhdFormat, VhdType, Size, FileSize
```

**Illustrative result, not live host output:**

```text
Path      : C:\HyperV-Lab\Disks\lab-data.vhdx
VhdFormat : VHDX
VhdType   : Dynamic
Size      : 8589934592
FileSize  : [depends on metadata and actual allocated blocks]
```

A newly created dynamic disk normally occupies far less host space than the 8 GiB capacity presented to the guest. `New-VHD` does not create a guest NTFS partition.

### Compare with a fixed disk

Optional lab-only example, requiring about 2 GiB of host space:

```powershell
$fixedPath = Join-Path $labDir 'fixed-example.vhdx'
if (Test-Path -LiteralPath $fixedPath) {
    throw "Already exists: $fixedPath"
}

New-VHD -Path $fixedPath -SizeBytes 2GB -Fixed |
    Select-Object Path, VhdType, Size, FileSize
```

## 5. Attach the disk using SCSI

On **HV01**, with the disposable VM Off:

```powershell
$vm = Get-VM -Name 'LAB-APP01' -ErrorAction Stop
if ($vm.State -ne 'Off') {
    throw 'Stop: VM is not Off.'
}

$attached = @(
    Get-VMHardDiskDrive -VMName 'LAB-APP01' |
        Where-Object { $_.Path -eq $vhdPath }
)
if ($attached.Count -gt 0) {
    throw 'This exact disk is already attached.'
}

Add-VMHardDiskDrive -VMName 'LAB-APP01' `
    -ControllerType SCSI `
    -Path $vhdPath

Get-VMHardDiskDrive -VMName 'LAB-APP01' |
    Where-Object { $_.Path -eq $vhdPath } |
    Select-Object VMName, ControllerType, ControllerNumber, ControllerLocation, Path
```

**Expected:** one new **SCSI** attachment to `lab-data.vhdx`. `Add-VMHardDiskDrive` normally produces no stdout; the next command confirms success.

After owner approval, start the **disposable lab guest**:

```powershell
Start-VM -Name 'LAB-APP01'

Get-VM -Name 'LAB-APP01' |
    Select-Object Name, State, Status
```

SCSI matters for **online resize**. On Generation 1 VMs, an OS disk may be connected via IDE; the VHDX extension alone is not sufficient for online resizing.

## 6. Guest PowerShell — identify and format the correct new disk

**Now run commands inside LAB-APP01, not on HV01.** Use elevated PowerShell. Formatting is destructive, so verify the target carefully.

```powershell
Get-Disk |
    Select-Object Number, FriendlyName, Size, PartitionStyle, IsBoot, IsSystem

Get-Partition |
    Select-Object DiskNumber, PartitionNumber, DriveLetter, Size
```

Never guess a disk number (for example, never assume the new disk is `Disk 1`). Select a unique 8 GiB RAW data disk, inspect it, and require explicit confirmation:

```powershell
$candidates = @(
    Get-Disk | Where-Object {
        $_.PartitionStyle -eq 'RAW' -and
        $_.Size -eq 8GB -and
        -not $_.IsBoot -and
        -not $_.IsSystem
    }
)

if ($candidates.Count -ne 1) {
    throw 'Expected one new 8 GiB RAW lab disk. Inspect Get-Disk.'
}

$disk = $candidates[0]
$disk | Format-List Number, FriendlyName, Size, PartitionStyle, UniqueId

# Verify manually that this is the NEW EMPTY VHDX in LAB-APP01.
$expected = "FORMAT-LAB-$($disk.Number)"
$answer = Read-Host "Enter $expected to initialize the verified LAB disk"
if ($answer -cne $expected) {
    throw 'No disk changes performed.'
}

$diskNumber = $disk.Number

Initialize-Disk -Number $diskNumber -PartitionStyle GPT -PassThru |
    New-Partition -UseMaximumSize -AssignDriveLetter |
    Format-Volume -FileSystem NTFS -NewFileSystemLabel 'LABDATA' -Confirm
```

**Warning:** The last pipeline initializes and formats the selected disk. Run it only for a truly new, empty, disposable disk. The guard and interactive confirmation are part of the exercise.

Read-only guest verification:

```powershell
Get-Partition -DiskNumber $diskNumber |
    Where-Object { $_.DriveLetter } |
    Get-Volume |
    Select-Object DriveLetter, FileSystemLabel, FileSystem, Size
```

**Expected:** one new NTFS data volume labeled `LABDATA`.

## 7. Online resize: extend VHDX capacity on HV01

**Switch back to HV01** and check controller, type, size, and checkpoint state before resizing. Leave the disposable VM running.

```powershell
$vhdPath = 'C:\HyperV-Lab\Disks\lab-data.vhdx'

$matches = @(
    Get-VMHardDiskDrive -VMName 'LAB-APP01' |
        Where-Object { $_.Path -eq $vhdPath }
)
if ($matches.Count -ne 1 -or $matches[0].ControllerType -ne 'SCSI') {
    throw 'The exact VHDX must be attached once through SCSI.'
}

if (@(Get-VMCheckpoint -VMName 'LAB-APP01').Count -gt 0) {
    throw 'Investigate checkpoint chains before resizing.'
}

$vhd = Get-VHD -Path $vhdPath
if ($vhd.VhdFormat -ne 'VHDX' -or
    $vhd.VhdType -ne 'Dynamic' -or
    $vhd.Size -ne 8GB) {
    throw 'Unexpected lab disk format, type, or size.'
}

Resize-VHD -Path $vhdPath -SizeBytes 12GB -WhatIf

# Execute on this disposable lab VHDX only.
Resize-VHD -Path $vhdPath -SizeBytes 12GB

Get-VHD -Path $vhdPath |
    Select-Object Path, Size, FileSize, VhdType
```

**Expected:** the host-side virtual `Size` is **12,884,901,888 bytes** (12 GiB). Since the disk is dynamic, `FileSize` does **not** have to grow by 4 GiB immediately.

| Controller/format | Live resize? | Notes |
| --- | --- | --- |
| VHDX on SCSI | **Yes**, supported | Online capacity expansion on a supported Hyper-V configuration |
| Disk connected via IDE | **No** | Requires VM offline |
| Legacy VHD | Expand supported, shrinking not supported | `Resize-VHD` cannot shrink VHD |
| VHDX shrink | Requires care | The disk minimum size and guest partition boundaries must be considered |

This lesson does **not** execute a shrink operation; shrinking an improperly prepared virtual disk can destroy guest data.

## 8. Guest PowerShell — extend the NTFS partition

**Switch back inside LAB-APP01** using the same PowerShell session with `$diskNumber` defined in section 6.

Expanding the VHDX on HV01 only changes the guest-visible **disk size**, not the existing NTFS partition size.

```powershell
Update-HostStorageCache

Get-Disk -Number $diskNumber |
    Select-Object Number, Size, PartitionStyle

Get-Partition -DiskNumber $diskNumber |
    Select-Object PartitionNumber, DriveLetter, Size
```

Verify the correct 12 GiB data disk and NTFS volume before extending it:

```powershell
$disk = Get-Disk -Number $diskNumber -ErrorAction Stop
if ($disk.Size -ne 12GB -or $disk.IsSystem -or $disk.IsBoot) {
    throw 'This is not the expected 12 GiB LAB data disk.'
}

$parts = @(
    Get-Partition -DiskNumber $diskNumber |
        Where-Object { $_.DriveLetter }
)

if ($parts.Count -ne 1) {
    throw 'Expected exactly one drive-letter LAB data partition.'
}

$part = $parts[0]
$volume = $part | Get-Volume
if ($volume.FileSystemLabel -ne 'LABDATA' -or $volume.FileSystem -ne 'NTFS') {
    throw 'The volume identity does not match LABDATA NTFS.'
}

$range = Get-PartitionSupportedSize `
    -DiskNumber $diskNumber `
    -PartitionNumber $part.PartitionNumber

$range | Select-Object SizeMin, SizeMax

Resize-Partition `
    -DiskNumber $diskNumber `
    -PartitionNumber $part.PartitionNumber `
    -Size $range.SizeMax
```

Verify guest capacity:

```powershell
Get-Partition -DiskNumber $diskNumber |
    Where-Object { $_.DriveLetter } |
    Get-Volume |
    Select-Object DriveLetter, FileSystemLabel, Size, SizeRemaining
```

**The crucial exam distinction:**

- `Resize-VHD` on the **host** changes virtual disk capacity.
- `Resize-Partition` inside the **guest** changes how much of that disk the NTFS volume uses.

## 9. Differencing disks: parent-child relationships

Differencing disks let each student VM use a different child image while sharing an unchanged parent.

```text
base-template.vhdx (unchanged parent)
   |
   +--- student01.vhdx (student01 writes)
   |
   +--- student02.vhdx (student02 writes)
```

Optional independent lab on **HV01**:

```powershell
$parent = 'C:\HyperV-Lab\Disks\base-template.vhdx'
$child  = 'C:\HyperV-Lab\Disks\student01.vhdx'

if ((Test-Path -LiteralPath $parent) -or (Test-Path -LiteralPath $child)) {
    throw 'Do not overwrite an existing base or child.'
}

New-VHD -Path $parent -SizeBytes 2GB -Dynamic
New-VHD -Path $child -ParentPath $parent -Differencing

Get-VHD -Path $child |
    Select-Object Path, VhdType, ParentPath, Size
```

The parent and child here contain no OS; this example only demonstrates disk linkage.

**Critical:** Child disks depend on the correct parent *contents*, not merely the filename. Do not rewrite, resize, rename, or arbitrarily replace the parent after children are created. Avoid `Set-VHD -IgnoreIdMismatch` unless carrying out a validated expert recovery operation.

Checkpoints can also involve `.avhdx` differencing chains. Never manually delete AVHDX files to remove checkpoints. Use supported Hyper-V checkpoint operations and let Hyper-V merge the chain.

## 10. Expand, compact, and migrate: three different operations

| Operation | Cmdlet | Result |
| --- | --- | --- |
| Increase virtual capacity | `Resize-VHD` | Raises the virtual disk `Size` |
| Reclaim eligible unused host blocks | `Optimize-VHD` | Can reduce physical `FileSize` without reducing virtual `Size` |
| Relocate VM data | `Move-VMStorage` | Changes VM storage locations without necessarily moving its execution host |

### Compact: not the same as shrink

`Optimize-VHD` is designed to optimize allocation for eligible dynamic/differencing disks, subject to its attachment and mode requirements. Microsoft documents the requirement for an **unattached or read-only-attached** virtual hard disk. A compaction might reclaim no blocks.

This is a **read-only diagnostic**, not a request to compact the attached disk:

```powershell
Get-VHD -Path 'C:\HyperV-Lab\Disks\lab-data.vhdx' |
    Select-Object Path, VhdType, Size, FileSize, Attached
```

Do not run `Optimize-VHD` against the writable, attached `lab-data.vhdx` of this lab.

### Storage Migration: a read-only preview

`Move-VMStorage` relocates VM storage, while Live Migration changes the host running the VM.

```powershell
Get-VM -Name 'LAB-APP01' |
    Select-Object Name, Path, ConfigurationLocation, SnapshotFileLocation

Get-VMHardDiskDrive -VMName 'LAB-APP01' |
    Select-Object Path, ControllerType

Move-VMStorage -Name 'LAB-APP01' `
    -DestinationStoragePath 'C:\HyperV-Lab\Moved\LAB-APP01' `
    -WhatIf
```

This is a preview only. A real storage move requires verifying destination storage, permissions, backup/recovery readiness, and active disk chains.

## 11. Failure diagnosis and recommended repair

| Symptom | Check | Repair direction |
| --- | --- | --- |
| Host VHDX is 12 GiB but guest disk still reports 8 GiB | Attachment path, guest storage discovery | Verify correct VHDX; refresh the guest storage view |
| Guest disk reports 12 GiB but NTFS only 8 GiB | `Get-Partition` and `Get-PartitionSupportedSize` | Extend the correct guest partition |
| Online resize fails | IDE vs SCSI, disk format, chain state | Use supported VHDX/SCSI or plan VM downtime |
| Dynamic disk exhausts host storage | Host `Get-Volume`; `Get-VHD.FileSize` | Add/free capacity and monitor growth |
| Differencing child cannot find parent | `Get-VHD.ParentPath`, metadata and file accessibility | Restore the correct validated chain |
| Unexplained AVHDX files | Checkpoints and backup activity | Investigate Hyper-V-managed merge/checkpoint state |
| Compaction saves no space | Eligibility, attachment mode, file blocks | Review prerequisites; do not mistake compaction for capacity resizing |
| Chain performance is poor | Differencing chain length and host disk I/O | Plan supported, backed-up consolidation |

## 12. Verification and rollback checklist

- [ ] Confirm the actual VM, owner, OS disk and **verified separate data disk**.
- [ ] Save inventory of disk paths, controller type, checkpoint chain and host capacity.
- [ ] Verify created disk `VhdFormat = VHDX` and `VhdType = Dynamic`.
- [ ] Verify the data disk was attached via **SCSI**, not IDE.
- [ ] Verify a new, empty RAW guest disk before any formatting.
- [ ] After `Resize-VHD`, verify `Size = 12 GiB` on HV01.
- [ ] After `Resize-Partition`, verify that the **LABDATA** guest volume grew.
- [ ] Test application data, not only the Hyper-V VM status.
- [ ] **Never simply shrink back to 8 GiB to undo the expansion**; that can destroy a now-larger guest partition. Restore from a verified backup or follow a tested data-preserving procedure.
- [ ] Never delete a disk file referenced by an active VM, differencing child, or checkpoint chain.

## 13. Exam traps

**Trap 1:** A dynamic disk cannot exhaust host storage. **False:** it can grow until physical storage is full.

**Trap 2:** `Get-VHD.Size` and `Get-VHD.FileSize` are always equal. **False:** they represent virtual capacity and physical backing-file allocation.

**Trap 3:** Host-side `Resize-VHD` automatically extends NTFS. **False:** use guest-side `Resize-Partition`.

**Trap 4:** A VHDX attached through IDE can be resized while the VM is running. **False:** IDE requires offline resizing.

**Trap 5:** `Optimize-VHD` and `Resize-VHD` are interchangeable. **False:** reclaiming host blocks differs from changing virtual capacity.

**Trap 6:** Parent VHDX content can be safely changed while children depend on it. **False:** the child chain can become invalid.

**Trap 7:** Delete AVHDX files in Explorer to remove checkpoints. **False:** use Hyper-V checkpoint removal.

**Trap 8:** `Move-VMStorage` means the VM's CPU and RAM execution move to another host. **False:** that is a separate migration operation.

## 14. Original AZ-802-style practice questions

These are independently authored questions based on public Microsoft materials, **not official Microsoft exam items**.

### Q1 — Single choice

Which virtual disk format supports capacity up to 64 TB?

A. VHD  
B. VHDX  
C. ISO  
D. AVHD

### Q2 — Single choice

A fixed 100 GiB VHDX and a dynamic 100 GiB VHDX have just been created. Which statement is correct?

A. Both always use 100 GiB on the host  
B. The dynamic VHDX can start much smaller; the fixed VHDX allocates its capacity  
C. Dynamic VHDX cannot grow beyond 10 GiB  
D. Fixed VHDX can never be expanded

### Q3 — Single choice

Which Hyper-V PowerShell cmdlet creates a virtual hard disk file?

A. `New-VHD`  
B. `New-Partition`  
C. `Set-VMSwitch`  
D. `Format-Volume`

### Q4 — Single choice

A running VM has a data VHDX on SCSI. You need to increase the VHDX virtual capacity. Which host-side cmdlet should you use?

A. `Optimize-VHD`  
B. `Resize-VHD`  
C. `Format-Volume`  
D. `Resize-Partition`

### Q5 — Single choice

After host-side expansion, the guest disk shows 12 GiB but the NTFS volume remains 8 GiB. What is the next action?

A. `Resize-Partition` inside the guest  
B. Delete and recreate the volume  
C. Enable Dynamic Memory  
D. Delete all VM checkpoints

### Q6 — Select TWO

Which statements are correct?

A. An IDE-attached VHDX can always be resized online  
B. A VHDX on virtual SCSI can be resized online in supported configurations  
C. Legacy VHD can be shrunk with `Resize-VHD`  
D. `Resize-VHD` expands VHD and VHDX, but only VHDX can shrink

### Q7 — Single choice

Two disposable student VMs must use the same read-only base image but save their writes separately. What disk model fits?

A. Both write directly to the same parent VHDX  
B. Separate differencing child disks from one unchanged parent  
C. An ISO file for each VM's writeable OS disk  
D. A single shared dynamic VHDX

### Q8 — Single choice

You want to reclaim eligible host-file blocks from a dynamic VHDX without decreasing guest-visible virtual capacity. Which cmdlet is relevant?

A. `Optimize-VHD`  
B. `Resize-VHD -SizeBytes 64TB`  
C. `Set-VMMemory`  
D. `Set-VMProcessor`

### Q9 — Single choice

You discover a VM's checkpoint chain uses AVHDX files. Which action is the correct principle?

A. Delete AVHDX files with File Explorer  
B. Use Hyper-V checkpoint tools and managed merge operations  
C. Rename AVHDX files while the VM is running  
D. Replace the parent with any same-size VHDX

### Q10 — Single choice

Which cmdlet relocates VM storage without being a command for compute live migration to another host?

A. `Move-VMStorage`  
B. `Move-VM`  
C. `Start-VM`  
D. `Checkpoint-VM`

### Q11 — Single choice

`Get-VHD` shows `Size = 12 GiB` and `FileSize = 2 GiB`. Which is the best explanation?

A. The disk is necessarily corrupt  
B. A dynamic disk has not allocated its full virtual capacity on the host  
C. It must be a fixed VHDX  
D. The guest cannot write more than 2 GiB

### Q12 — Single choice

Which cmdlet reports supported size boundaries for a guest Windows partition?

A. `Get-PartitionSupportedSize`  
B. `Get-VMNetworkAdapterVlan`  
C. `Get-VMSwitch`  
D. `Get-VMIntegrationService`

### Answer key with reasoning

| Question | Answer | Reason |
| --- | --- | --- |
| Q1 | **B** | VHDX supports 64 TB; legacy VHD supports 2 TB. |
| Q2 | **B** | Dynamic allocates on demand; fixed reserves capacity immediately. |
| Q3 | **A** | `New-VHD` creates VHD/VHDX files. |
| Q4 | **B** | `Resize-VHD` changes virtual disk capacity. |
| Q5 | **A** | Guest partition extension is separate from host disk expansion. |
| Q6 | **B, D** | VHDX/SCSI is online-resizable; VHD cannot shrink via `Resize-VHD`. |
| Q7 | **B** | Each child holds independent changes, parent must remain unchanged. |
| Q8 | **A** | Optimization can reclaim eligible host allocation without changing virtual `Size`. |
| Q9 | **B** | Hyper-V should manage checkpoint removal and disk merges. |
| Q10 | **A** | `Move-VMStorage` relocates storage, not necessarily the VM execution host. |
| Q11 | **B** | `FileSize` and virtual `Size` are different, particularly for dynamic disks. |
| Q12 | **A** | `Get-PartitionSupportedSize` returns allowable partition sizes. |

## 15. Interview question

**"The VHDX has a virtual size of 200 GiB, but the guest NTFS volume is only 100 GiB. Meanwhile, the Hyper-V host has less than 50 GiB of physical free space. What do you check?"**

A strong answer separates **host VHDX virtual capacity**, **host physical FileSize and free storage**, and **guest partition/volume capacity**. It inspects the correct disk path and checkpoint chain, checks `Get-Disk`, `Get-Partition`, and `Get-PartitionSupportedSize` inside the guest, and only then plans a guest partition extension if appropriate. It also addresses host capacity risk if the VHDX is dynamically expanding and avoids pointlessly expanding the host virtual disk again.

## 16. C1 / CAE phrase

**"To rule out a storage bottleneck"** — to investigate and exclude insufficient storage capacity or throughput as the cause of a problem.

Example: *"We compared guest partition size, VHDX allocation, and host free space to rule out a storage bottleneck before modifying the VM."*

## 17. Microsoft references

- [AZ-802 official study guide](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/az-802)
- [Hyper-V features and terminology](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/features-terminology)
- [Hyper-V storage I/O performance](https://learn.microsoft.com/en-us/windows-server/administration/performance-tuning/role/hyper-v-server/storage-io-performance)
- [New-VHD](https://learn.microsoft.com/en-us/powershell/module/hyper-v/new-vhd)
- [Get-VHD](https://learn.microsoft.com/en-us/powershell/module/hyper-v/get-vhd)
- [Add-VMHardDiskDrive](https://learn.microsoft.com/en-us/powershell/module/hyper-v/add-vmharddiskdrive)
- [Resize-VHD](https://learn.microsoft.com/en-us/powershell/module/hyper-v/resize-vhd)
- [Get-PartitionSupportedSize](https://learn.microsoft.com/en-us/powershell/module/storage/get-partitionsupportedsize)
- [Resize-Partition](https://learn.microsoft.com/en-us/powershell/module/storage/resize-partition)
- [Optimize-VHD](https://learn.microsoft.com/en-us/powershell/module/hyper-v/optimize-vhd)
- [Move-VMStorage](https://learn.microsoft.com/en-us/powershell/module/hyper-v/move-vmstorage)
- [Troubleshoot Hyper-V checkpoints and differencing disks](https://learn.microsoft.com/en-us/troubleshoot/windows-server/virtualization/hyper-v-snapshots-checkpoints-differencing-disks)

**Repository convention:** Synthetic examples only. All outcomes are illustrative; no live VM execution is claimed.
