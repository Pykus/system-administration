# 07 — Hyper-V Live Migration

Hyper-V Live Migration moves a running VM between Hyper-V hosts with little or no visible interruption. For AZ-802, the key skill is knowing which layer to check when migration fails.

## 1. What must be true

A successful migration needs four things:

1. the hosts can communicate,
2. authentication can be delegated,
3. the destination can run the VM,
4. networking and storage are compatible.

Useful troubleshooting model:

```text
connectivity
   ↓
authentication / delegation
   ↓
VM compatibility
   ↓
network / storage
```

## 2. Enable and inspect Live Migration

```powershell
Enable-VMMigration
Get-VMHost | Select-Object VirtualMachineMigrationEnabled,VirtualMachineMigrationAuthenticationType,VirtualMachineMigrationPerformanceOption
Get-VMHost -ComputerName HV02
```

Do not assume both hosts have identical settings.

## 3. CredSSP vs Kerberos

Hyper-V supports CredSSP and Kerberos.

```powershell
Set-VMHost -VirtualMachineMigrationAuthenticationType Kerberos
```

CredSSP is convenient when migration is started directly on the source host. Kerberos is usually the better choice for remote administration.

```text
ADM01 → HV01 → HV02
```

If migration works when started on HV01 but fails when started remotely from ADM01, suspect delegation.

## 4. Constrained delegation

For Kerberos-based remote migration, the source host computer account must be allowed to delegate to services on the destination host.

Important service:

```text
Microsoft Virtual System Migration Service
```

For storage migration, CIFS may also be needed:

```text
cifs
```

Typical AD configuration:

1. open the source Hyper-V computer account,
2. open **Delegation**,
3. allow delegation to specified services only,
4. add the destination host,
5. add **Microsoft Virtual System Migration Service**,
6. add **cifs** if storage is also moved.

Delegation is directional. Configure the reverse direction if VMs must move both ways. Avoid unconstrained delegation.

## 5. SPNs

Inspect SPNs:

```powershell
setspn -L HV01
setspn -L HV02
setspn -Q "Microsoft Virtual System Migration Service/HV02.contoso.test"
```

Do not create SPNs blindly. Duplicate SPNs can break Kerberos.

After delegation or SPN changes, stale tickets may need clearing:

```powershell
klist purge
```

## 6. Connectivity

Check DNS first:

```powershell
Resolve-DnsName HV01
Resolve-DnsName HV02
Test-NetConnection HV02
Test-WSMan HV02
```

If DNS or routing is broken, changing Kerberos settings will not fix the migration.

## 7. Migration network and performance

Live Migration can consume significant bandwidth. Production environments often separate migration traffic from guest, storage, and management traffic.

```powershell
Get-NetAdapter | Format-Table Name,Status,LinkSpeed
Get-VMHost | Select-Object VirtualMachineMigrationPerformanceOption
```

Typical modes:

- **TCP/IP** — simple baseline,
- **Compression** — saves bandwidth but uses more CPU,
- **SMB** — useful with suitable SMB Multichannel/RDMA infrastructure.

Choose the mode for the actual network design.

## 8. Destination compatibility

### Virtual switches

```powershell
Get-VMSwitch -ComputerName HV01 | Select-Object Name,SwitchType
Get-VMSwitch -ComputerName HV02 | Select-Object Name,SwitchType
Get-VMNetworkAdapter -ComputerName HV01 -VMName APP01 | Select-Object Name,SwitchName
```

A VM connected to `Production` on HV01 will not automatically match a differently named switch on HV02.

### CPU

```powershell
Get-VMProcessor -ComputerName HV01 -VMName APP01 | Select-Object CompatibilityForMigrationEnabled
Set-VMProcessor -VMName APP01 -CompatibilityForMigrationEnabled $true
```

Enable compatibility only when needed.

### Memory

```powershell
Get-VM -ComputerName HV01 -Name APP01 | Select-Object Name,State,MemoryAssigned
Get-Counter -ComputerName HV02 '\Memory\Available MBytes'
```

## 9. Run the migration

Basic migration:

```powershell
Move-VM -Name APP01 -DestinationHost HV02
```

Remote initiation:

```powershell
Move-VM -ComputerName HV01 -Name APP01 -DestinationHost HV02
```

Move storage too:

```powershell
Move-VM -Name APP01 -DestinationHost HV02 -IncludeStorage -DestinationStoragePath "D:\VMs\APP01"
```

Storage migration adds path, free-space, permission, throughput, and sometimes CIFS delegation requirements.

## 10. Troubleshooting workflow

Use a fixed order:

1. confirm the VM is healthy on the source,
2. verify DNS for both hosts,
3. compare Live Migration settings,
4. determine whether migration is local or remotely initiated,
5. check Kerberos delegation and SPNs,
6. compare virtual switches,
7. check CPU compatibility,
8. check destination memory,
9. check storage paths and free space,
10. inspect Hyper-V event logs.

```powershell
Get-WinEvent -LogName "Microsoft-Windows-Hyper-V-VMMS-Admin" -MaxEvents 30 | Select-Object TimeCreated,Id,LevelDisplayName,Message
```

Common clues:

- **works locally, fails remotely** → Kerberos/delegation,
- **network configuration error** → virtual switch mismatch,
- **CPU incompatibility** → processor compatibility,
- **storage migration failure** → path, permissions, CIFS or free space,
- **very slow migration** → migration network, transport mode, CPU load or memory write rate.

## Concrete expected output: synthetic lab

The following is a **sample transcript**, not a claim that these commands were executed against a real Hyper-V environment. Assume the lab has two hosts (`HV01`, `HV02`), a running VM (`APP01`), a virtual switch named `Production`, and Kerberos configured for Live Migration. Actual IP addresses, RAM, disk paths, adapter status, and table spacing depend on the host.

Command:

```powershell
Get-VMHost -ComputerName HV01 | Select-Object VirtualMachineMigrationEnabled,VirtualMachineMigrationAuthenticationType
```

Expected sample output:

```text
VirtualMachineMigrationEnabled VirtualMachineMigrationAuthenticationType
------------------------------ -----------------------------------------
                          True                                  Kerberos
```

Command:

```powershell
Get-VMSwitch -ComputerName HV02 | Select-Object Name,SwitchType
```

Expected sample output:

```text
Name       SwitchType
----       ----------
Production   External
```

After a successful migration, command:

```powershell
Get-VM -ComputerName HV02 -Name APP01 | Select-Object Name,State,Status
```

Expected sample output:

```text
Name  State   Status
----  -----   ------
APP01 Running Operating normally
```

The important assertions are that migration is enabled with the intended authentication mode, the destination has the required virtual switch, and the VM is running on the destination. The sample output is illustrative; **the exact output of a real run must be captured and checked**, not inferred from this example. Commands that only change configuration or complete successfully without printing anything should be documented as having **no normal stdout**, followed by a separate verification command.

## 11. Verify after migration

```powershell
Get-VM -ComputerName HV02 -Name APP01 | Select-Object Name,State,Status
Get-VMNetworkAdapter -ComputerName HV02 -VMName APP01 | Select-Object SwitchName,Status
Get-VMHardDiskDrive -ComputerName HV02 -VMName APP01 | Select-Object Path
```

Finally verify the application itself. A successful Hyper-V migration does not automatically prove that the guest service is healthy.

## AZ-802 checklist

Before migration:

- DNS and host connectivity work,
- Live Migration is enabled,
- authentication mode is intentional,
- Kerberos delegation/SPNs are correct when used,
- destination switches match,
- destination has enough memory,
- CPU compatibility is considered,
- storage paths and permissions are valid.

After migration:

- VM is running on the destination,
- networking works,
- disks are in the expected location,
- the application responds,
- VMMS logs show no unresolved migration errors.

The exam-level principle is simple: troubleshoot Live Migration layer by layer instead of treating every failure as a generic Hyper-V problem.
