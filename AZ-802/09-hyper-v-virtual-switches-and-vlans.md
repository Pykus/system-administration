# 09 — Hyper-V Virtual Switches and VLANs

> **Exam:** AZ-802 — Administering Windows Server  
> **Measured skill:** Manage VMs (10–15%): configure a Hyper-V Virtual Switch and Hyper-V network adapters.  
> **Environment:** Windows Server with Hyper-V and the Hyper-V PowerShell module. Run commands in an elevated PowerShell session.  
> **Safety:** All host names, VM names, addresses, and VLAN IDs below are **synthetic lab examples**. Do not apply switch or VLAN changes to a production host without a maintenance window, console access, and a rollback plan.

## 1. Core idea

A **Hyper-V virtual switch (vSwitch)** is a software Layer 2 switch. It connects VM virtual network adapters to each other, the host, or a physical network. A vSwitch by itself is **not** a router, a DHCP server, or an Internet gateway.

| Switch type | VMs on the same host | Hyper-V host OS | Physical network |
| --- | --- | --- | --- |
| **External** | Yes | Optional: when management OS shares the NIC | Yes, through the bound physical NIC |
| **Internal** | Yes | Yes | No direct physical uplink |
| **Private** | Yes | No | No |

The difference between **Internal** and **Private** is a favorite exam distinction: Internal permits host-to-VM communication; Private does not. Neither automatically provides Internet access. External connectivity still depends on NICs, IP configuration, switching, routing, and firewall policy.

A **VLAN** is a Layer 2 broadcast domain identified by an IEEE 802.1Q VLAN ID. Several VLANs can use the same external vSwitch and physical uplink while remaining logically separate. To communicate between VLANs, traffic needs routing and suitable security rules.

- **Access mode:** a VM virtual adapter belongs to one VLAN. The guest typically sends/receives untagged Ethernet frames; Hyper-V handles VLAN tagging where required.
- **Trunk mode:** a VM virtual adapter can carry several VLANs. The guest must understand tagged traffic for the tagged VLANs. An optional native VLAN handles untagged frames.
- **Untagged mode:** no Hyper-V VLAN association is applied to that adapter.

**Key distinction:** You normally configure a VM's VLAN on its **virtual network adapter**, not by assuming that every VM connected to the same virtual switch inherits one VLAN.

## 2. Scenario

An isolated training host named `HV01` contains two disposable Windows Server VMs:

| Device | Purpose | Example addressing |
| --- | --- | --- |
| `HV01` | Hyper-V host | Managed separately |
| `LAB-APP01` | Application VM | `10.10.120.11/24` |
| `LAB-DB01` | Database VM | `10.10.120.12/24` |
| `LAB-RTR01` | Optional VLAN-aware router/firewall VM | Tagged VLANs 120 and 130 |

You want to:

1. Connect two VMs to the **same internal test switch**.
2. Place their vNICs in **VLAN 120**.
3. Verify how changing one VM to **VLAN 130** affects connectivity.
4. Understand how the design would change for a physical network or a VLAN-aware virtual appliance.

The VLAN IDs above are examples only; they do not describe a real infrastructure.

## 3. Diagnosis: read-only preflight

Run these on `HV01` before changing anything:

```powershell
Import-Module Hyper-V

Get-NetAdapter |
    Select-Object Name, Status, LinkSpeed

Get-VMSwitch |
    Select-Object Name, SwitchType, NetAdapterInterfaceDescription, AllowManagementOS

Get-VMNetworkAdapter -VMName 'LAB-APP01' |
    Select-Object VMName, Name, SwitchName, Status

Get-VMNetworkAdapterVlan -VMName 'LAB-APP01' |
    Format-List *

Get-VMNetworkAdapter -ManagementOS |
    Select-Object Name, SwitchName

Get-VMNetworkAdapterVlan -ManagementOS |
    Format-List *
```

**Interpretation:** `Get-VMSwitch` shows the type and bound physical adapter where applicable; `Get-VMNetworkAdapter` identifies the VM's switch connection; `Get-VMNetworkAdapterVlan` shows its VLAN mode. The management OS has a **separate** set of virtual network adapters and VLAN settings from the guest VMs.

The inventory output depends on the environment. An absent `LAB-Internal` switch during preflight is expected when starting from a clean lab. Do not invent or assume a production host's adapter name.

## 4. Controlled lab A: create an internal switch

**Prerequisites:** `LAB-APP01` and `LAB-DB01` already exist, have a virtual network adapter, and are disposable lab machines. The examples use the default adapter name, `Network Adapter`; obtain the actual name from `Get-VMNetworkAdapter` first.

Create the switch:

```powershell
New-VMSwitch -Name 'LAB-Internal' -SwitchType Internal

Get-VMSwitch -Name 'LAB-Internal' |
    Select-Object Name, SwitchType
```

**Illustrative output, not a live execution transcript:**

```text
Name         SwitchType
----         ----------
LAB-Internal Internal
```

An Internal switch also exposes a host-side `vEthernet (LAB-Internal)` interface, but neither that adapter nor the guest VMs automatically receive suitable IP addresses from Hyper-V. There is no built-in Internet access just because the switch exists.

Connect both guest adapters:

```powershell
Connect-VMNetworkAdapter -VMName 'LAB-APP01' -Name 'Network Adapter' -SwitchName 'LAB-Internal'
Connect-VMNetworkAdapter -VMName 'LAB-DB01'  -Name 'Network Adapter' -SwitchName 'LAB-Internal'

Get-VMNetworkAdapter -VMName 'LAB-APP01','LAB-DB01' |
    Select-Object VMName, Name, SwitchName
```

Configure both adapters in access mode on VLAN 120:

```powershell
Set-VMNetworkAdapterVlan -VMName 'LAB-APP01' -VMNetworkAdapterName 'Network Adapter' -Access -VlanId 120
Set-VMNetworkAdapterVlan -VMName 'LAB-DB01'  -VMNetworkAdapterName 'Network Adapter' -Access -VlanId 120

Get-VMNetworkAdapterVlan -VMName 'LAB-APP01'
Get-VMNetworkAdapterVlan -VMName 'LAB-DB01'
```

**Expected state:** both vNICs use **Access** mode with VLAN ID **120**, and both are attached to `LAB-Internal`. `Connect-VMNetworkAdapter` and `Set-VMNetworkAdapterVlan` normally return no output; the subsequent `Get-*` queries are the verification.

## 5. Controlled lab B: configure guest IP addresses and test

On `LAB-APP01`, in an elevated PowerShell session **inside that VM**, inspect the guest NIC name:

```powershell
Get-NetAdapter
Get-NetIPConfiguration
```

If this is a fresh lab guest NIC without an existing IP configuration, give it an address:

```powershell
New-NetIPAddress -InterfaceAlias 'Ethernet' -IPAddress '10.10.120.11' -PrefixLength 24
```

On `LAB-DB01`, using its own guest PowerShell session:

```powershell
New-NetIPAddress -InterfaceAlias 'Ethernet' -IPAddress '10.10.120.12' -PrefixLength 24
```

Replace `Ethernet` if the guest reports a different adapter alias. Do not add a default gateway merely to test same-subnet VM-to-VM connectivity.

Back on `LAB-APP01`:

```powershell
Test-Connection -ComputerName '10.10.120.12' -Count 2
```

**Expected:** the VMs can communicate at Layer 2 on the same switch and VLAN. ICMP success also depends on the guest firewall allowing echo requests. A failed ping alone is **not** proof of VLAN isolation.

To demonstrate separation, change only `LAB-DB01` to VLAN 130 **on the Hyper-V host**:

```powershell
Set-VMNetworkAdapterVlan -VMName 'LAB-DB01' -VMNetworkAdapterName 'Network Adapter' -Access -VlanId 130
Get-VMNetworkAdapterVlan -VMName 'LAB-DB01'
```

With the two VMs now on different access VLANs, they no longer share a Layer 2 broadcast domain through this switch. Even with correct guest firewalls, direct same-subnet communication should not work. Properly configured routing would be required for cross-VLAN communication.

Restore the original lab configuration when finished:

```powershell
Set-VMNetworkAdapterVlan -VMName 'LAB-DB01' -VMNetworkAdapterName 'Network Adapter' -Access -VlanId 120
Get-VMNetworkAdapterVlan -VMName 'LAB-DB01'
```

**Subtle trap:** Access VLAN 120 on the VMs does **not** automatically place the Hyper-V management OS's own virtual NIC into VLAN 120. To test host-to-VM connectivity through an Internal switch, the host-side virtual NIC must also have compatible VLAN and IP settings.

## 6. External virtual switch: production-design example

An External switch binds to a physical network adapter. The following command is a **design example, not an instruction to run on a remotely managed production host**:

```powershell
# Confirm which physical adapter would be affected.
Get-NetAdapter -Name 'Ethernet' |
    Select-Object Name, Status, InterfaceDescription

# LAB ONLY: can interrupt host network/RDP/PowerShell remoting.
New-VMSwitch -Name 'LAB-External' -NetAdapterName 'Ethernet' -AllowManagementOS $true
```

`-AllowManagementOS $true` enables host sharing of the physical adapter through a management OS virtual adapter. It does **not** guarantee uninterrupted remote access or automatically select a correct management VLAN. Plan any host IP/VLAN migration before creating an External switch.

To connect a test VM to the External switch and associate it with VLAN 120:

```powershell
Connect-VMNetworkAdapter -VMName 'LAB-APP01' -Name 'Network Adapter' -SwitchName 'LAB-External'

Set-VMNetworkAdapterVlan -VMName 'LAB-APP01' -VMNetworkAdapterName 'Network Adapter' -Access -VlanId 120

Get-VMNetworkAdapter -VMName 'LAB-APP01' |
    Select-Object VMName, Name, SwitchName

Get-VMNetworkAdapterVlan -VMName 'LAB-APP01'
```

For traffic to reach VLAN 120 beyond the Hyper-V host, the **physical switch uplink must also be configured to carry VLAN 120**. Hyper-V cannot override the upstream switch configuration. The VM still needs an appropriate IP address, default gateway (for off-subnet access), DNS, and permitted firewall paths.

When troubleshooting the **host's** VLAN, inspect `Get-VMNetworkAdapterVlan -ManagementOS` separately. Do not change a host management VLAN based solely on a guest connectivity symptom.

## 7. Trunk mode: a VLAN-aware virtual appliance

Suppose `LAB-RTR01` is an existing disposable router/firewall VM that must receive VLANs 120 and 130 through one virtual NIC. Configure its vNIC as a trunk:

```powershell
Set-VMNetworkAdapterVlan -VMName 'LAB-RTR01' -VMNetworkAdapterName 'Network Adapter' -Trunk -AllowedVlanIdList '120,130' -NativeVlanId 120

Get-VMNetworkAdapterVlan -VMName 'LAB-RTR01' |
    Format-List *
```

**Interpretation:** VLANs 120 and 130 are permitted on this virtual adapter; untagged frames are associated with native VLAN 120. The guest must configure VLAN interfaces for the **tagged** VLANs (for example, 130). A standard guest that expects only untagged traffic typically needs **Access**, not **Trunk**.

`-Access`, `-Trunk`, and `-Untagged` represent mutually exclusive modes for a single virtual NIC. These settings do not perform inter-VLAN routing. The guest router/firewall and the rest of the physical/virtual network still need correct interfaces, routes, and policies.

## 8. Interpretation and repair

| Symptom | Investigate first | Recommended action |
| --- | --- | --- |
| VM cannot connect to the intended network | `Get-VMNetworkAdapter` and `Get-VMSwitch` | Attach it to the correct vSwitch |
| VMs on one switch cannot communicate | `Get-VMNetworkAdapterVlan`, guest IPs, firewall | Align VLAN membership/IP settings or configure routing |
| External VM can reach local VLAN but not outside | Guest gateway, DNS, physical uplink, upstream rules | Correct the failed layer rather than recreating VMs |
| VLAN 120 guest cannot reach physical VLAN 120 | Physical trunk allowed VLAN list and Hyper-V access VLAN | Ensure upstream switching permits VLAN 120 |
| VM-to-VM works but host-to-VM does not | Private vs Internal; host vNIC's VLAN/IP | Choose Internal if host communication is required |
| Host loses remote network during switch creation | Management OS sharing, host-side vNIC, management VLAN | Use console access and restore planned host networking |
| Trunked guest cannot use VLAN 130 | Guest 802.1Q configuration and allowed VLAN list | Create the correct tagged guest interface |

For guest troubleshooting, execute these **inside the affected Windows guest**:

```powershell
Get-NetAdapter
Get-NetIPConfiguration
Get-NetRoute -AddressFamily IPv4
Get-DnsClientServerAddress
```

When a specific server and open service are known, test the **service port**, not only ICMP:

```powershell
# Example only: use when a lab SMB server actually exists at this address.
Test-NetConnection -ComputerName '10.10.120.20' -Port 445
```

Distinguish a Layer 2 VLAN problem from Layer 3 IP/routing issues and Layer 4 service/firewall issues. A successful `Get-VMSwitch` call proves only that the switch object exists, not end-to-end guest connectivity.

## 9. Exam traps

**Trap 1: "A Private switch allows host-to-VM communication."** False. That is an **Internal** switch.

**Trap 2: "An Internal switch automatically provides Internet access."** False. External access requires explicit routing/NAT and appropriate configuration.

**Trap 3: "All VMs on the same vSwitch are automatically in the same VLAN."** False. VLAN settings are associated with individual virtual adapters.

**Trap 4: "Setting the guest VM to VLAN 120 guarantees it reaches a physical VLAN 120."** False. The external uplink must allow that VLAN, and IP/network policies must work.

**Trap 5: "Trunk mode is required for every VM using a VLAN."** False. Ordinary single-VLAN guests usually use **Access** mode.

**Trap 6: "AllowManagementOS automatically sets the host's desired VLAN."** False. The host management vNIC has independent VLAN and IP configuration.

## 10. AZ-802-style practice questions (original, not official exam items)

Try to answer before checking the key.

**Q1.** Two test VMs on HV01 must communicate with each other. The Hyper-V host and physical network must have no access to them. Which switch type is appropriate?

A. External  
B. Internal  
C. Private  
D. External with management OS sharing

**Q2.** Two VMs must communicate with each other and with their Hyper-V host, but there must be no direct physical LAN uplink. Which switch type is the simplest choice?

A. Private  
B. Internal  
C. External  
D. Trunk

**Q3.** A VM attached to an External switch is configured in Access mode on VLAN 120. It cannot reach physical machines on VLAN 120, although its guest IP configuration is valid. Which infrastructure setting should you verify?

A. That Production Checkpoints are enabled  
B. That the physical switch uplink allows VLAN 120  
C. That Hyper-V Replica is enabled  
D. That the VM uses a differencing VHDX

**Q4.** A virtual firewall appliance must carry VLANs 120 and 130 on one virtual adapter and process 802.1Q-tagged frames. Which action best fits?

A. Configure Access mode, VLAN 120  
B. Configure Private switch mode  
C. Configure Trunk mode with both VLAN IDs allowed  
D. Disable the network adapter

**Q5.** After an External switch is bound to a physical NIC, the administrator loses the remote management connection to HV01. Which concern should have been addressed before the change?

A. Guest checkpoint frequency  
B. Whether the host management OS retains appropriate network and VLAN connectivity  
C. Whether all guests have dynamic memory  
D. Whether VHDX files are fixed-size

**Q6.** Both VMs are attached to `LAB-Internal`. One uses Access VLAN 120 and the other Access VLAN 130. No router exists. What should you expect?

A. They communicate because the switch name matches  
B. They communicate because IP packets ignore VLANs  
C. They are separated at Layer 2  
D. Hyper-V silently changes both adapters to VLAN 120

**Q7.** An administrator creates `New-VMSwitch -SwitchType Internal`. Why do guest VMs not automatically obtain IPv4 addresses?

A. An Internal vSwitch does not provide DHCP by itself  
B. Internal switches require Azure Arc  
C. Internal switches disable TCP/IP  
D. Every Internal switch requires a domain controller

**Q8.** Which PowerShell command is the most direct way to inspect the VLAN settings of `LAB-APP01`?

A. `Get-VMHardDiskDrive -VMName 'LAB-APP01'`  
B. `Get-VMNetworkAdapterVlan -VMName 'LAB-APP01'`  
C. `Get-VMCheckpoint -VMName 'LAB-APP01'`  
D. `Get-VMProcessor -VMName 'LAB-APP01'`

### Answer key and reasoning

| Question | Answer | Reason |
| --- | --- | --- |
| Q1 | **C** | Private switches provide VM-to-VM connectivity on a host without host or physical LAN access. |
| Q2 | **B** | Internal permits host-to-VM and VM-to-VM connectivity without binding a physical NIC. |
| Q3 | **B** | An External VLAN requires compatible physical switch/uplink configuration. |
| Q4 | **C** | Trunk mode carries permitted VLANs to a VLAN-aware guest appliance. |
| Q5 | **B** | External switch creation can disrupt host management networking; plan management OS sharing and VLAN/IP settings. |
| Q6 | **C** | Different access VLANs are separate Layer 2 domains without routing. |
| Q7 | **A** | The vSwitch performs Layer 2 forwarding; it is not a DHCP server. |
| Q8 | **B** | `Get-VMNetworkAdapterVlan` reports virtual adapter VLAN configuration. |

## 11. Interview question

**"A VM is connected to an External Hyper-V switch but cannot reach another machine in the same expected VLAN. How would you investigate?"**

A strong answer proceeds in layers:

1. Verify the VM is connected to the **correct vSwitch** (`Get-VMNetworkAdapter`).
2. Confirm that the switch is **External** and bound to the intended working physical NIC (`Get-VMSwitch`, `Get-NetAdapter`).
3. Inspect the VM vNIC's **Access/Trunk VLAN configuration** (`Get-VMNetworkAdapterVlan`).
4. Verify that the **physical switch uplink permits that VLAN**.
5. Inspect guest **IP address, subnet, routes, DNS** (where relevant) and **firewall/service state**.
6. Retest using a known peer or application port, then document which layer was actually responsible.

## 12. Verification checklist

- [ ] Identify the intended switch type from the connectivity requirement.
- [ ] Confirm the correct virtual network adapter and switch name.
- [ ] Distinguish a VM's VLAN configuration from the host management OS VLAN.
- [ ] Use Access mode for ordinary single-VLAN guests; Trunk for VLAN-aware guests.
- [ ] Verify allowed VLANs on the physical uplink for an External switch.
- [ ] Remember that a vSwitch is neither a DHCP server nor a router.
- [ ] Confirm guest IP connectivity and application connectivity separately.
- [ ] Keep a console-based recovery path before changing production External switches.

## 13. C1/CAE phrase

**"To isolate a fault"** — to narrow the cause of a technical failure to a particular component or layer.

Example: *"We isolated the fault to the physical switch uplink after confirming that the VM's VLAN settings were correct."*

## 14. Microsoft references

- [AZ-802 official study guide — Manage VMs](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/az-802)
- [Plan for Hyper-V networking](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/plan/plan-hyper-v-networking-in-windows-server)
- [Create and configure a virtual switch](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/get-started/create-a-virtual-switch-for-hyper-v-virtual-machines)
- [Set-VMNetworkAdapterVlan](https://learn.microsoft.com/en-us/powershell/module/hyper-v/set-vmnetworkadaptervlan)
- [Get-VMNetworkAdapterVlan](https://learn.microsoft.com/en-us/powershell/module/hyper-v/get-vmnetworkadaptervlan)
- [Connect-VMNetworkAdapter](https://learn.microsoft.com/en-us/powershell/module/hyper-v/connect-vmnetworkadapter)

All examples are anonymized training examples. Outputs are illustrative; no Hyper-V host execution is claimed.
