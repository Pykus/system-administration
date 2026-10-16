# 10 — Hyper-V Dynamic Memory and Smart Paging

> **Exam:** AZ-802 — Administering Windows Server  
> **Syllabus mapping:** Manage VMs (10–15%) → Manage Hyper-V and guest VM → **Configure VM memory settings**.  
> **Lab environment:** Windows Server Hyper-V host `HV01`, disposable Windows Server VM `LAB-APP01`.  
> **Safety:** Host, VM, and numeric settings are fictional training examples. Never modify or restart a production VM without change approval, capacity assessment, maintenance planning, and a rollback procedure. All outputs below are illustrative, not captures from a live Hyper-V host.

## 1. Core idea

**Hyper-V Dynamic Memory** automatically adjusts the physical memory assigned to a VM according to guest demand, available host RAM, and administrator-defined boundaries. This can increase VM consolidation on a shared Hyper-V host, but it cannot create RAM and must respect application requirements.

| Setting | Our lab value | What it really controls |
| --- | ---: | --- |
| **Minimum RAM** | 2 GB | Lower bound on the VM's memory **after startup** |
| **Startup RAM** | 4 GB | Amount that must be available **when the VM boots** |
| **Maximum RAM** | 8 GB | Upper bound for runtime allocation |

Mental model:

```text
VM starts                  Needs 4 GB Startup RAM
↓
Guest boots                Hyper-V can reclaim RAM toward 2 GB
↓
Applications become busy   Hyper-V can grow allocation toward 8 GB
```

A configured `Maximum` of 8 GB does **not** immediately give the guest 8 GB. Nor does `Minimum` mean that a guest with a 4 GB startup requirement can cold-boot with only 2 GB available.

**Static Memory** assigns a fixed amount of RAM (Startup RAM). **Dynamic Memory** allows adjustment within the specified range, when the guest operating system and its integration components support it. Memory-sensitive software should be assessed against vendor requirements; don't enable Dynamic Memory indiscriminately.

## 2. Scenario

Hyper-V host `HV01` runs several lab VMs. `LAB-APP01` needs 4 GB for startup but uses less at idle. You have been asked to:

1. Inspect host capacity and current VM memory configuration.
2. Configure a **disposable Off VM** with 2 GB minimum, 4 GB startup, 8 GB maximum.
3. Understand what `Buffer 20` and `Priority 80` mean.
4. Verify the difference between configured values and actual memory assigned at runtime.
5. Explain why a restart and a cold start behave differently under severe host memory pressure.

The VM is assumed to **exist already**; no VM creation or forced shutdown is performed by this lesson.

## 3. Diagnosis: read-only preflight

Run on `HV01` in an **elevated PowerShell session**:

```powershell
Import-Module Hyper-V

# VM state and memory currently assigned/demanded.
Get-VM -Name 'LAB-APP01' |
    Select-Object Name, State, MemoryAssigned, MemoryDemand, MemoryStatus

# Configured dynamic memory limits and policies.
Get-VMMemory -VMName 'LAB-APP01' |
    Format-List *

# Host RAM inventory: the values here are in KB.
Get-CimInstance -ClassName Win32_OperatingSystem |
    Select-Object TotalVisibleMemorySize, FreePhysicalMemory

# Other VMs competing for host resources.
Get-VM |
    Select-Object Name, State, MemoryAssigned, MemoryDemand
```

**Interpretation:** `Get-VMMemory` is a configuration view; `Get-VM` contains runtime observations. `MemoryAssigned` need not equal either `Startup` or `Maximum` once Dynamic Memory is operating. An Off VM does not have meaningful live memory demand.

Record the current configuration before you make a change:

```powershell
$before = Get-VMMemory -VMName 'LAB-APP01' -ErrorAction Stop

$before |
    Select-Object VMName, DynamicMemoryEnabled, Minimum, Startup, Maximum, Buffer, Priority |
    Export-Csv -Path "$env:TEMP\LAB-APP01-memory-before.csv" -NoTypeInformation

$before | Format-List *
```

**Important:** This CSV is a record, not an automated restore script. Move it to approved storage if it must survive cleanup of the host's temporary directory.

## 4. Commands: a guarded offline lab

**Prerequisites:** `LAB-APP01` is disposable, the guest has no important unsaved data, the host has sufficient RAM, and the VM is already **Off**. Never force-stop an active server just to run a lab command.

Use a safety guard:

```powershell
$vm = Get-VM -Name 'LAB-APP01' -ErrorAction Stop

if ($vm.State -ne 'Off') {
    throw "LAB-APP01 must be Off. Current state: $($vm.State)"
}
```

Apply the planned settings using PowerShell **splatting**:

```powershell
$memorySettings = @{
    VMName               = 'LAB-APP01'
    DynamicMemoryEnabled = $true
    MinimumBytes         = 2GB
    StartupBytes         = 4GB
    MaximumBytes         = 8GB
    Buffer               = 20
    Priority             = 80
}

# Safe preview: no configuration changes.
Set-VMMemory @memorySettings -WhatIf

# Execute only in the approved, isolated lab.
Set-VMMemory @memorySettings
```

Equivalent expanded command (for command recognition in the exam):

```powershell
Set-VMMemory -VMName 'LAB-APP01' `
    -DynamicMemoryEnabled $true `
    -MinimumBytes 2GB `
    -StartupBytes 4GB `
    -MaximumBytes 8GB `
    -Buffer 20 `
    -Priority 80
```

The continuation symbol at the end of each line is PowerShell's **backtick**. Do not leave trailing spaces after it.

`Set-VMMemory` normally returns no text when successful. Always verify with a **read-only** query:

```powershell
$m = Get-VMMemory -VMName 'LAB-APP01'

[pscustomobject]@{
    VMName        = 'LAB-APP01'
    Dynamic       = $m.DynamicMemoryEnabled
    MinimumGiB    = $m.Minimum / 1GB
    StartupGiB    = $m.Startup / 1GB
    MaximumGiB    = $m.Maximum / 1GB
    BufferPercent = $m.Buffer
    Priority      = $m.Priority
}
```

Illustrative output (not actual host evidence):

```text
VMName        : LAB-APP01
Dynamic       : True
MinimumGiB    : 2
StartupGiB    : 4
MaximumGiB    : 8
BufferPercent : 20
Priority      : 80
```

## 5. Interpretation: Buffer and Priority

### Memory Buffer

`-Buffer 20` requests approximately **20% headroom above guest memory demand**, when possible. It does not reserve 20% of the whole host.

For example:

```text
Memory currently required by the guest: 3.0 GB
20% buffer:                             0.6 GB
Desired allocation:                     3.6 GB
```

Hyper-V may not maintain that buffer if the host lacks free memory or the VM has reached its maximum. The amount varies with workload demand.

### Memory Priority

`-Priority 80` is a **relative preference under memory contention**, on a 0–100 scale. A VM with priority 80 generally has greater allocation preference than a VM with priority 20 if there isn't enough physical memory to satisfy competing demands. Priority is **not** a reserved share of 80% and cannot override the configured memory limit.

### Examine the running VM

Only after the lab VM has been approved to start:

```powershell
Start-VM -Name 'LAB-APP01'

Get-VM -Name 'LAB-APP01' |
    Select-Object Name, State, MemoryAssigned, MemoryDemand, MemoryStatus
```

Show memory in GiB, instead of the raw byte values:

```powershell
$vm = Get-VM -Name 'LAB-APP01'

[pscustomobject]@{
    Name         = $vm.Name
    State        = $vm.State
    AssignedGiB  = [math]::Round($vm.MemoryAssigned / 1GB, 2)
    DemandGiB    = [math]::Round($vm.MemoryDemand / 1GB, 2)
    MemoryStatus = $vm.MemoryStatus
}
```

**What matters:** Compare `AssignedGiB` with `DemandGiB` and check guest-level performance. Hyper-V's allocation can change while the guest runs. The VM reporting `Running` is not sufficient proof that its application is healthy.

## 6. Which changes can be made at runtime?

Microsoft documents these two important changes to **Dynamic Memory for a running VM**:

- **Increase** the configured Maximum RAM.
- **Decrease** the configured Minimum RAM.

For example, if the VM is running and the host has enough headroom, increase its **ceiling**:

```powershell
Set-VMMemory -VMName 'LAB-APP01' -MaximumBytes 10GB

(Get-VMMemory -VMName 'LAB-APP01').Maximum / 1GB
```

Expected numerical result after a successful change: `10`.

This **does not** immediately assign 10 GB to the VM. Avoid assuming that Startup RAM, enabling/disabling Dynamic Memory, or every other limit can be changed on an active VM. For this course, do those changes with the VM Off unless the operation is explicitly documented as hot-changeable.

Reducing Minimum RAM may be technically supported while running but is not automatically safe for a particular workload.

## 7. Smart Paging: restart-specific behavior

Consider the following situation:

```text
Startup RAM needed:                 4 GB
Currently assigned to running VM:  2 GB
Additional RAM needed to restart:  2 GB
Host physical RAM available:       Insufficient
RAM reclaimable from other VMs:    None
```

**Smart Paging** can temporarily use storage to bridge that **restart-time** memory shortage. It is slower than RAM and must not be mistaken for a permanent capacity solution.

Microsoft lists **all three** prerequisites:

1. The virtual machine is **restarting**.
2. Sufficient free physical host memory is **not available**.
3. Memory **cannot be reclaimed** from other VMs.

**Smart Paging is not used** for a VM starting from the **Off** state, for normal extra demand in a running guest, or during a VM failover in a Hyper-V cluster. It is temporary and released when it is no longer required.

Read-only inspection:

```powershell
Get-VM -Name 'LAB-APP01' |
    Select-Object Name, SmartPagingFilePath
```

Do **not** deliberately exhaust host RAM or trigger unplanned VM restarts to test Smart Paging.

**Exam-level distinction:** "VM could not cold-start because host RAM is insufficient" calls for investigating capacity and Startup RAM, **not** assuming Smart Paging will help.

## 8. Failure diagnosis and recommended repair

| Problem | Inspect first | Reasonable next action |
| --- | --- | --- |
| An **Off** VM cannot start because of insufficient RAM | `Get-VM`, Startup RAM, host free RAM, other VMs | Release/add host memory; validate startup memory against guest requirements |
| A VM restart occurs under host memory pressure | Startup vs assigned memory, capacity, other VM allocations | Evaluate Smart Paging's prerequisites, then fix the root capacity problem |
| VM is slow after its memory allocation shrinks | Assigned vs demand, guest performance, memory limits | Re-evaluate minimum, maximum, application requirements and host capacity |
| VM needs to grow but hits Maximum | `Get-VMMemory` | Raise the ceiling only after assessing available host capacity |
| Guest installation/upgrade needs more memory | Startup RAM and guest install requirements | Adjust Startup RAM before approved maintenance |
| Guest doesn't respond to Dynamic Memory as expected | Supported guest OS and integration components | Inspect compatibility/drivers; don't randomly enable unrelated guest services |
| A high-priority VM still cannot obtain enough memory | Physical capacity and per-VM ceilings | Priority helps with contention; it does not create RAM |

Host diagnostics:

```powershell
Get-VM |
    Sort-Object MemoryAssigned -Descending |
    Select-Object Name, State, MemoryAssigned, MemoryDemand

Get-CimInstance Win32_OperatingSystem |
    Select-Object TotalVisibleMemorySize, FreePhysicalMemory

# Performance counter names can be localized.
Get-Counter -ListSet 'Hyper-V Dynamic Memory Balancer'
```

The Hyper-V Dynamic Memory Balancer's **Available Memory** counter is relevant when checking how much host memory is available for VMs.

For a Windows guest, run these **inside the guest**, not on the host:

```powershell
Get-CimInstance Win32_OperatingSystem |
    Select-Object TotalVisibleMemorySize, FreePhysicalMemory

Get-Service -Name 'vmic*' |
    Select-Object Name, Status
```

Hyper-V integration components and drivers matter; however, enabling the optional **Guest Service Interface** is not equivalent to enabling Dynamic Memory ballooning.

## 9. Rollback: restore known settings

Save the original configuration before a change. For this **specific training scenario only**, assume the VM originally used **Static Memory = 4 GB**. After a normal, owner-approved shutdown of the disposable VM, restore that known baseline:

```powershell
$vm = Get-VM -Name 'LAB-APP01' -ErrorAction Stop

if ($vm.State -ne 'Off') {
    throw 'Shutdown the disposable lab VM cleanly before rollback.'
}

Set-VMMemory -VMName 'LAB-APP01' -DynamicMemoryEnabled $false -StartupBytes 4GB

Get-VMMemory -VMName 'LAB-APP01' |
    Format-List *
```

**Do not apply this example to VMs with a different original configuration.** Restore the actual recorded settings, and verify guest and application health. A memory setting rollback is not a replacement for tested backup and recovery practices.

## 10. Exam traps

- **Trap 1:** "Maximum = 8 GB means 8 GB is assigned at boot." **False:** Startup RAM controls boot allocation.
- **Trap 2:** "Minimum must equal Startup." **False:** Dynamic Memory can reclaim RAM after startup.
- **Trap 3:** "Buffer 20 reserves 20% of host RAM." **False:** It is a target percentage above guest demand.
- **Trap 4:** "Priority 80 guarantees 80% of physical host RAM." **False:** It is a relative allocation preference.
- **Trap 5:** "Smart Paging fixes every memory shortage." **False:** It is only for specific restart conditions.
- **Trap 6:** "Smart Paging always helps an Off VM cold-start." **False:** A cold start is excluded.
- **Trap 7:** "Increasing Maximum immediately adds RAM." **False:** It raises a limit, not necessarily actual allocation.
- **Trap 8:** "Maximum RAM solves insufficient Startup RAM during guest OS upgrade." **False:** Set Startup appropriately for upgrades.

## 11. Original AZ-802-style practice questions

These questions are authored for this course based on public Microsoft documentation. They are **not official exam items**.

### Q1 — Single choice

A VM has Minimum = 2 GB, Startup = 4 GB, Maximum = 8 GB. How much RAM does the VM normally require to start?

A. 2 GB  
B. 4 GB  
C. 8 GB  
D. 14 GB

### Q2 — Single choice

Which PowerShell cmdlet shows configured Dynamic Memory limits?

A. `Get-VMCheckpoint`  
B. `Get-VMMemory`  
C. `Get-VMSwitch`  
D. `Get-VMHardDiskDrive`

### Q3 — Calculation

A guest needs 3 GB and its memory buffer is 20%. Assuming spare host capacity and no Maximum constraint, what total allocation does Hyper-V attempt?

A. 3.0 GB  
B. 3.2 GB  
C. 3.6 GB  
D. 6.0 GB

### Q4 — Single choice

VM-A has Memory Priority 80 and VM-B has 20. The host is under memory pressure. What does Priority 80 mean?

A. VM-A owns 80% of host RAM  
B. VM-A has a greater relative preference for memory under contention  
C. VM-A can exceed its configured Maximum  
D. VM-A can never use guest paging

### Q5 — Select TWO

Which Dynamic Memory changes does Microsoft specifically document for a VM while it is **running**?

A. Increase Maximum RAM  
B. Increase Startup RAM  
C. Decrease Minimum RAM  
D. Switch from Static to Dynamic Memory without stopping it

### Q6 — Single choice

A VM previously in the **Off** state cannot start because there is insufficient free host RAM to meet its Startup value. What should you do first?

A. Assume Smart Paging will always handle cold-start shortages  
B. Inspect host memory and Startup requirements; release or add sufficient capacity  
C. Increase Priority to 100 to create guaranteed memory  
D. Raise Maximum RAM without changing available host resources

### Q7 — Single choice

An operating system upgrade requires at least 4 GB. A VM has Startup = 2 GB and Maximum = 8 GB. What setting should you address before the upgrade?

A. Startup RAM  
B. Virtual switch type  
C. Production checkpoint selection only  
D. Memory Priority only

### Q8 — Single choice

When is Hyper-V Smart Paging potentially relevant?

A. A network outage during Live Migration  
B. Any high-memory demand from a running VM  
C. A restart with insufficient host RAM and no reclaimable memory from other VMs  
D. All VM cold starts

### Q9 — Single choice

A running VM's Maximum is raised from 8 GB to 10 GB, but `Get-VM` reports only 5 GB assigned. Is that necessarily a configuration error?

A. Yes, assigned memory always equals Maximum  
B. No, Maximum is a ceiling rather than a guaranteed allocation  
C. Yes, runtime changes to Maximum are forbidden  
D. Yes, Dynamic Memory requires a static allocation

### Q10 — Single choice

Which properties should be compared to see whether a running VM's assigned RAM differs from the guest's reported demand?

A. `MemoryAssigned` and `MemoryDemand`  
B. `SwitchName` and `VlanId`  
C. `CheckpointType` and `CreationTime`  
D. `VhdType` and `FileSize`

### Answers with explanations

| Q | Answer | Explanation |
| --- | --- | --- |
| 1 | **B** | Startup RAM specifies boot-time requirement. |
| 2 | **B** | `Get-VMMemory` reads memory settings; `Set-VMMemory` changes them. |
| 3 | **C** | 3 GB + 20% × 3 GB = 3.6 GB target; actual allocation depends on capacity and limits. |
| 4 | **B** | Higher priority influences relative allocation under contention; it is not a physical reservation. |
| 5 | **A, C** | Increasing Maximum and decreasing Minimum are documented running-state changes. |
| 6 | **B** | Smart Paging does **not** apply to cold starts from Off. |
| 7 | **A** | Startup RAM is the relevant memory amount for guest OS installation/upgrade. |
| 8 | **C** | Smart Paging is a temporary recovery mechanism for a specific restart shortage. |
| 9 | **B** | An increased ceiling doesn't force immediate allocation. |
| 10 | **A** | Runtime assigned and demand values are reported through `Get-VM`. |

## 12. Interview question

**"Your Hyper-V host runs out of RAM at busy times. Some VMs are slow and a VM occasionally fails to start. How do you approach this?"**

A strong response distinguishes **cold start versus restart**, inventories host RAM, checks `Get-VMMemory` limits and `Get-VM` runtime demand/assignment, identifies workload-level memory requirements, and determines whether the issue is incorrect Startup RAM, a restrictive Maximum, guest performance, or host exhaustion. It explains precisely **when Smart Paging is and is not available**, recommends enough physical capacity instead of abusing paging, and verifies the guest applications after any approved change.

## 13. Verification checklist

- [ ] Explain Minimum, Startup, and Maximum in plain English.
- [ ] Distinguish Static Memory from Dynamic Memory.
- [ ] Use `Get-VMMemory` and `Get-VM` correctly.
- [ ] Explain why Buffer and Priority are not guaranteed memory reservations.
- [ ] Recognize supported runtime adjustments.
- [ ] State all three Smart Paging prerequisites.
- [ ] Know that Smart Paging excludes a cold start from Off.
- [ ] Size Startup RAM appropriately for OS installations and upgrades.
- [ ] Apply and verify the settings only on a disposable lab VM.
- [ ] Preserve original values and use a workload-safe rollback.

## 14. C1/CAE phrase

**"To alleviate resource contention"** — to reduce competition for scarce computing resources.

Example: *"We adjusted Dynamic Memory settings to alleviate resource contention on the Hyper-V host without compromising the application's minimum RAM requirements."*

## 15. Microsoft references

- [AZ-802 official study guide](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/az-802)
- [Hyper-V Dynamic Memory overview](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/dynamic-memory)
- [Set-VMMemory](https://learn.microsoft.com/en-us/powershell/module/hyper-v/set-vmmemory?view=windowsserver2025-ps)
- [Get-VMMemory](https://learn.microsoft.com/en-us/powershell/module/hyper-v/get-vmmemory?view=windowsserver2025-ps)
- [Hyper-V memory performance](https://learn.microsoft.com/en-us/windows-server/administration/performance-tuning/role/hyper-v-server/memory-performance)
- [Manage Hyper-V integration services](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/manage/manage-hyper-v-integration-services)

**Portfolio convention:** The training scenario and values are synthetic. Commands were not executed against a real Hyper-V host; sample results are illustrative.
