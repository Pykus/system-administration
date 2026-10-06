# 07 — Hyper-V Live Migration: Kerberos, delegation, networks, and troubleshooting

Hyper-V Live Migration moves a running virtual machine from one Hyper-V host to another with little or no visible interruption to the guest workload. It is useful during host maintenance, hardware replacement, workload balancing, and planned infrastructure changes.

The difficult part is rarely the Move-VM command itself. Most real failures come from four areas:

1. authentication and delegation,
2. DNS, routing, and connectivity,
3. incompatible host or virtual-switch configuration,
4. incorrect storage or performance assumptions.

This chapter focuses on operational reasoning and troubleshooting rather than only on GUI steps.

## 1. When Live Migration is useful

Typical use cases include:

- patching or rebooting a Hyper-V host without a long VM outage,
- moving workloads away from failing or overloaded hardware,
- replacing an older Hyper-V host,
- redistributing CPU and memory load,
- performing planned maintenance,
- testing workload mobility procedures.

Live Migration is not a substitute for backup, Hyper-V Replica, failover clustering, application-level high availability, or disaster recovery.

A VM that can move between two hosts is still vulnerable if both hosts depend on the same failed storage, switch, rack, or power source.

## 2. What actually moves

A VM is more than a VHDX file. Hyper-V must coordinate:

- VM configuration,
- virtual CPU state,
- memory pages,
- virtual devices,
- network identity,
- storage state when storage migration is included.

Simplified flow:

~~~text
source host
   |
   | copy active memory pages
   v
destination host
   |
   | recopy pages changed during transfer
   v
short final synchronization
   |
   v
VM continues on destination
~~~

A VM that modifies memory rapidly may require several memory-copy passes before final cutover.

## 3. Three questions before troubleshooting

Separate the problem into three layers.

### Can the hosts communicate?

Check:

- DNS resolution,
- routing,
- firewall rules,
- WinRM where required,
- intended migration network.

### Can authentication be delegated?

This is where CredSSP, Kerberos, SPNs, and constrained delegation matter.

### Can the destination host run the VM?

Check:

- CPU compatibility,
- available memory,
- virtual switch names,
- storage availability,
- required VM features.

A perfect Kerberos configuration does not help if the destination host has no compatible virtual switch.

## 4. Enable and inspect Live Migration

Enable migration:

~~~powershell
Enable-VMMigration
~~~

Inspect host configuration:

~~~powershell
Get-VMHost | Select-Object VirtualMachineMigrationEnabled,VirtualMachineMigrationAuthenticationType,VirtualMachineMigrationPerformanceOption,MaximumVirtualMachineMigrations,UseAnyNetworkForMigration
~~~

Inspect another host:

~~~powershell
Get-VMHost -ComputerName HV02
~~~

Never assume that both hosts use the same migration settings.

## 5. CredSSP versus Kerberos

Hyper-V supports both authentication methods.

Kerberos:

~~~powershell
Set-VMHost -VirtualMachineMigrationAuthenticationType Kerberos
~~~

CredSSP:

~~~powershell
Set-VMHost -VirtualMachineMigrationAuthenticationType CredSSP
~~~

CredSSP is convenient when an administrator starts migration directly on the source host.

Remote administration introduces the classic second-hop problem:

~~~text
administrator workstation
        |
        v
      HV01
        |
        v
      HV02
~~~

If migration succeeds on HV01 but fails when initiated from a management workstation, delegation becomes a strong suspect.

## 6. Kerberos for remote administration

For domain-joined Hyper-V hosts and remote management, Kerberos is usually the better operational design.

Configure both hosts:

~~~powershell
Set-VMHost -ComputerName HV01 -VirtualMachineMigrationAuthenticationType Kerberos
Set-VMHost -ComputerName HV02 -VirtualMachineMigrationAuthenticationType Kerberos
~~~

Kerberos alone is not enough.

The source host computer account must be permitted to delegate authentication to the required services on the destination host.

## 7. Constrained delegation

The important service for Live Migration is:

~~~text
Microsoft Virtual System Migration Service
~~~

For storage migration, CIFS may also be required:

~~~text
cifs
~~~

Typical Active Directory procedure:

1. Open Active Directory Users and Computers.
2. Open the computer account of the source Hyper-V host.
3. Open Properties.
4. Open Delegation.
5. Select delegation to specified services only.
6. Add the destination Hyper-V host.
7. Add Microsoft Virtual System Migration Service.
8. Add cifs if storage migration requires it.
9. Repeat in the reverse direction if migration must work both ways.

Delegation is directional.

Example:

~~~text
HV01 may delegate to:
  Microsoft Virtual System Migration Service / HV02
  cifs / HV02

HV02 may delegate to:
  Microsoft Virtual System Migration Service / HV01
  cifs / HV01
~~~

Avoid unconstrained delegation when constrained delegation is sufficient.

## 8. Service Principal Names

Inspect SPNs:

~~~powershell
setspn -L HV01
setspn -L HV02
~~~

Query before creating anything:

~~~powershell
setspn -Q "Microsoft Virtual System Migration Service/HV02.contoso.test"
~~~

If troubleshooting confirms a missing registration:

~~~powershell
setspn -S "Microsoft Virtual System Migration Service/HV02.contoso.test" HV02
~~~

Do not add SPNs blindly. Duplicate SPNs can break Kerberos.

## 9. Stale Kerberos tickets

After changing delegation or SPNs, cached tickets can preserve the old state.

Current user session:

~~~powershell
klist purge
~~~

Local System session:

~~~powershell
klist purge -li 0x3e7
~~~

Ticket purging is a troubleshooting step, not a permanent fix.

## 10. Windows Server 2025 and Credential Guard

Microsoft documents that Credential Guard can affect CredSSP-based Hyper-V Live Migration on Windows Server 2025.

Verify the operating system:

~~~powershell
Get-ComputerInfo | Select-Object WindowsProductName,WindowsVersion,OsBuildNumber
~~~

Inspect Device Guard state:

~~~powershell
Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard
~~~

Do not troubleshoot a Windows Server 2025 host exactly like an older Windows Server 2019 or 2022 host.

## 11. Migration network design

Live Migration can consume significant bandwidth and compete with:

- guest traffic,
- storage traffic,
- backup traffic,
- management traffic.

A production design may separate traffic logically:

~~~text
Management network     -> administration
VM network             -> guest traffic
Storage network        -> storage
Live Migration network -> memory/state transfer
~~~

Inspect adapters:

~~~powershell
Get-NetAdapter | Sort-Object Name | Format-Table Name,Status,LinkSpeed,MacAddress
~~~

Inspect routing:

~~~powershell
Get-NetRoute -AddressFamily IPv4 | Sort-Object RouteMetric
~~~

## 12. Migration network selection

Inspect:

~~~powershell
Get-VMHost | Select-Object UseAnyNetworkForMigration
~~~

Hyper-V exposes:

~~~powershell
Set-VMHost -UseAnyNetworkForMigration $true
~~~

In production, convenience should not replace deliberate traffic design.

## 13. Migration performance options

Hyper-V supports TCP/IP, Compression, and SMB migration modes.

Example:

~~~powershell
Set-VMHost -VirtualMachineMigrationPerformanceOption Compression
~~~

Verify:

~~~powershell
Get-VMHost | Select-Object VirtualMachineMigrationPerformanceOption
~~~

### Compression

Useful when CPU capacity is available but bandwidth is limited.

Trade-off:

- lower network usage,
- higher CPU usage.

### SMB

Useful in high-throughput SMB environments and can benefit from SMB Multichannel, RDMA, and SMB Direct.

Do not choose SMB only because it sounds faster. The network must support the design.

### TCP/IP

A straightforward baseline where advanced SMB/RDMA infrastructure is not present.

## 14. CPU compatibility

Inspect:

~~~powershell
Get-VMProcessor -VMName APP01 | Select-Object CompatibilityForMigrationEnabled
~~~

Enable compatibility only where justified:

~~~powershell
Set-VMProcessor -VMName APP01 -CompatibilityForMigrationEnabled $true
~~~

Compatibility mode can hide newer CPU features from the guest, so do not enable it automatically on every VM.

## 15. Virtual switch compatibility

Compare both hosts:

~~~powershell
Get-VMSwitch -ComputerName HV01 | Select-Object Name,SwitchType
Get-VMSwitch -ComputerName HV02 | Select-Object Name,SwitchType
~~~

Inspect the VM network adapter:

~~~powershell
Get-VMNetworkAdapter -VMName APP01 -ComputerName HV01 | Select-Object Name,SwitchName,MacAddress
~~~

A source switch named Production and a destination switch named Prod-Network are not automatically equivalent.

## 16. Destination memory capacity

Inspect the VM:

~~~powershell
Get-VM -ComputerName HV01 -Name APP01 | Select-Object Name,State,MemoryAssigned
~~~

Destination free memory:

~~~powershell
Get-Counter -ComputerName HV02 '\Memory\Available MBytes'
~~~

Other VM demand:

~~~powershell
Get-VM -ComputerName HV02 | Select-Object Name,State,MemoryAssigned,MemoryDemand
~~~

Installed RAM alone is not enough. Available capacity and current workload matter.

## 17. Basic migration

Local migration:

~~~powershell
Move-VM -Name APP01 -DestinationHost HV02
~~~

Remote initiation:

~~~powershell
Move-VM -ComputerName HV01 -Name APP01 -DestinationHost HV02
~~~

If the first works and the second fails, that difference is valuable diagnostic evidence.

## 18. Moving storage too

~~~powershell
Move-VM -Name APP01 -DestinationHost HV02 -IncludeStorage -DestinationStoragePath "D:\VMs\APP01"
~~~

Check destination capacity:

~~~powershell
Get-Volume -CimSession HV02 | Select-Object DriveLetter,FileSystemLabel,SizeRemaining,Size
~~~

Storage migration adds dependencies:

- permissions,
- CIFS,
- delegation,
- disk space,
- throughput,
- destination paths.

## 19. Read-only preflight

A small preflight can catch common errors before migration begins.

~~~powershell
param(
    [Parameter(Mandatory)]
    [string]$SourceHost,

    [Parameter(Mandatory)]
    [string]$DestinationHost,

    [Parameter(Mandatory)]
    [string]$VMName
)

Resolve-DnsName $SourceHost -ErrorAction Stop
Resolve-DnsName $DestinationHost -ErrorAction Stop

$source = Get-VMHost -ComputerName $SourceHost
$destination = Get-VMHost -ComputerName $DestinationHost

$source | Select-Object ComputerName,VirtualMachineMigrationEnabled,VirtualMachineMigrationAuthenticationType,VirtualMachineMigrationPerformanceOption
$destination | Select-Object ComputerName,VirtualMachineMigrationEnabled,VirtualMachineMigrationAuthenticationType,VirtualMachineMigrationPerformanceOption

$vm = Get-VM -ComputerName $SourceHost -Name $VMName -ErrorAction Stop
$vm | Select-Object Name,State,MemoryAssigned,ProcessorCount

$vmNics = Get-VMNetworkAdapter -ComputerName $SourceHost -VMName $VMName
$destinationSwitches = Get-VMSwitch -ComputerName $DestinationHost

$missingSwitches = foreach ($nic in $vmNics) {
    if ($nic.SwitchName -and $nic.SwitchName -notin $destinationSwitches.Name) {
        $nic.SwitchName
    }
}

if ($missingSwitches) {
    Write-Warning ("Missing destination switches: " + ($missingSwitches -join ", "))
}

Get-VMProcessor -ComputerName $SourceHost -VMName $VMName | Select-Object CompatibilityForMigrationEnabled
~~~

This does not guarantee success, but it catches several common mismatches early.

## 20. Troubleshooting by error class

### Access denied or Kerberos errors

Typical symptoms:

- 0x80070005,
- Kerberos failures,
- works locally but not remotely.

Check:

~~~powershell
Get-VMHost -ComputerName HV01 | Select-Object VirtualMachineMigrationAuthenticationType
~~~

Then inspect:

- constrained delegation,
- SPNs,
- ticket cache,
- DNS identity.

### Destination cannot be contacted

~~~powershell
Resolve-DnsName HV02
Test-NetConnection HV02
Test-WSMan HV02
~~~

Do not change Kerberos if DNS is broken.

### VM network configuration failure

~~~powershell
Get-VMNetworkAdapter -ComputerName HV01 -VMName APP01
Get-VMSwitch -ComputerName HV02
~~~

### CPU compatibility failure

~~~powershell
Get-VMProcessor -ComputerName HV01 -VMName APP01
~~~

### Storage failure

~~~powershell
Get-VMHardDiskDrive -ComputerName HV01 -VMName APP01
~~~

Then verify path, free space, permissions, and CIFS delegation where applicable.

## 21. Hyper-V event logs

List Hyper-V logs:

~~~powershell
Get-WinEvent -ListLog "*Hyper-V*" | Select-Object LogName,RecordCount
~~~

Recent VMMS events:

~~~powershell
Get-WinEvent -LogName "Microsoft-Windows-Hyper-V-VMMS-Admin" -MaxEvents 50 | Select-Object TimeCreated,Id,LevelDisplayName,Message
~~~

Time-bounded query:

~~~powershell
$since = (Get-Date).AddMinutes(-15)

Get-WinEvent -FilterHashtable @{
    LogName = "Microsoft-Windows-Hyper-V-VMMS-Admin"
    StartTime = $since
} | Select-Object TimeCreated,Id,Message
~~~

Use the migration time to reduce noise.

## 22. Deterministic troubleshooting workflow

Use this order:

1. verify source VM state,
2. verify DNS for both hosts,
3. compare Live Migration settings,
4. determine whether migration is local or remotely initiated,
5. check delegation and SPNs,
6. compare virtual switch names,
7. check CPU compatibility,
8. check destination memory,
9. check storage,
10. read VMMS logs,
11. change one variable,
12. retest.

Do not change authentication, firewall, switches, storage, and CPU settings simultaneously.

## 23. Scenario: local migration works, remote migration fails

Topology:

~~~text
ADM01 -> HV01 -> HV02
~~~

Move-VM succeeds directly on HV01 but fails from ADM01.

Strong hypothesis:

- host connectivity likely works,
- VM compatibility likely works,
- credential delegation is the leading suspect.

Investigate Kerberos, constrained delegation, SPNs, and cached tickets before opening random firewall ports.

## 24. Scenario: authentication succeeds but preparation fails

Compare switch names:

~~~powershell
Get-VMNetworkAdapter -ComputerName HV01 -VMName APP01 | Select-Object SwitchName
Get-VMSwitch -ComputerName HV02 | Select-Object Name
~~~

If the source VM expects LAN-Production and the destination only has Production-LAN, fix the configuration intentionally.

## 25. Scenario: migration is very slow

Inspect transport mode:

~~~powershell
Get-VMHost | Select-Object VirtualMachineMigrationPerformanceOption
~~~

Then inspect:

- migration NIC speed,
- backup traffic,
- CPU usage with Compression,
- SMB/RDMA capabilities with SMB,
- VM memory write rate.

A VM that constantly changes memory can be harder to migrate than an idle VM with the same RAM size.

## 26. Security mistakes to avoid

Do not:

- enable unconstrained delegation unnecessarily,
- create SPNs without checking for duplicates,
- disable modern security features only to preserve an outdated design,
- send migration traffic over an untrusted network,
- publish real production host names or network details.

Use least privilege and synthetic examples.

## 27. AZ-802 reasoning model

Use this mental model:

~~~text
Can the hosts communicate?
        |
        v
Can authentication delegate correctly?
        |
        v
Can the destination run the VM?
        |
        v
Can storage and network state move?
        |
        v
Is the selected transport appropriate?
~~~

Typical clues:

- works locally, fails remotely -> Kerberos/delegation,
- destination network unavailable -> virtual switch configuration,
- different CPU generations -> processor compatibility,
- VM files must move too -> storage/CIFS/delegation,
- transfer is slow -> transport and bandwidth.

## 28. Verification after migration

Verify VM location and state:

~~~powershell
Get-VM -ComputerName HV02 -Name APP01 | Select-Object Name,State,Status
~~~

Verify networking:

~~~powershell
Get-VMNetworkAdapter -ComputerName HV02 -VMName APP01 | Select-Object SwitchName,MacAddress,Status
~~~

Verify disks:

~~~powershell
Get-VMHardDiskDrive -ComputerName HV02 -VMName APP01 | Select-Object Path
~~~

Verify application health where possible:

~~~powershell
Test-NetConnection app01.contoso.test -Port 443
~~~

Infrastructure migration success and application health are not the same thing.

## 29. Rollback thinking

Before maintenance, record:

~~~text
source host
destination host
VM name
original storage paths
original switch names
authentication mode
processor compatibility state
application health check
rollback destination
~~~

A reverse Move-VM may be simple, but storage relocation and configuration changes can make rollback more complex.

## 30. Practical lab

Use synthetic hosts:

~~~text
HV01.contoso.test
HV02.contoso.test
LAB-VM01
~~~

Tasks:

1. enable Live Migration on both hosts,
2. compare authentication settings,
3. configure Kerberos,
4. configure constrained delegation in both directions,
5. verify migration-service SPNs,
6. compare virtual switches,
7. run the preflight,
8. migrate LAB-VM01 from HV01 to HV02,
9. verify guest connectivity,
10. migrate it back,
11. intentionally break a harmless test condition such as a test switch name,
12. observe the error,
13. restore the setting,
14. verify migration again.

Controlled failure and repair teaches more than a single successful migration.

## 31. Final checklist

Before migration:

- [ ] DNS works for both hosts,
- [ ] both hosts are reachable,
- [ ] Live Migration is enabled,
- [ ] authentication mode is intentional,
- [ ] constrained delegation is correct,
- [ ] SPNs are valid,
- [ ] migration network is suitable,
- [ ] destination switch configuration matches,
- [ ] destination has enough memory,
- [ ] CPU compatibility is considered,
- [ ] storage paths and permissions are valid.

After migration:

- [ ] VM runs on destination,
- [ ] guest networking works,
- [ ] disks are in expected locations,
- [ ] application health check passes,
- [ ] event logs contain no unresolved migration errors.

## 32. Microsoft documentation

Hyper-V Live Migration troubleshooting:

https://learn.microsoft.com/en-us/troubleshoot/windows-server/virtualization/hyper-v-virtual-machine-live-migration

Constrained delegation and migration troubleshooting:

https://learn.microsoft.com/en-us/troubleshoot/windows-server/virtualization/troubleshoot-live-migration-issues

Set-VMHost reference:

https://learn.microsoft.com/powershell/module/hyper-v/set-vmhost

Credential Guard considerations:

https://learn.microsoft.com/windows/security/identity-protection/credential-guard/considerations-known-issues

## Summary

Reliable Live Migration is the intersection of:

~~~text
Hyper-V configuration
+ DNS
+ Kerberos
+ constrained delegation
+ SPNs
+ networking
+ virtual switches
+ CPU compatibility
+ memory
+ storage
+ verification
~~~

The key administrative skill is to diagnose those layers separately instead of treating every migration failure as one generic Hyper-V problem.
