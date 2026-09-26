# HP 1910 / Comware — SNMP read-only and Zabbix monitoring

This short guide shows a minimal, read-only SNMP setup on an HP 1910-class switch and how to add it to Zabbix.

> All IP addresses, community names and ACL numbers below are examples. Replace them with values from your own environment.

## Example lab values used in this guide

- Zabbix server: `10.10.20.15`
- HP 1910 management IP: `10.10.20.2`
- SNMP community: `monitoring_ro`
- ACL number: `2000`

The Zabbix IP above is deliberately a documentation/example address. Do **not** copy a production monitoring-server address into public documentation.

## About ACL number 2000 vs 2001

On Comware 5, basic IPv4 ACLs use the range `2000–2999`. Therefore `2000` is not inherently better than `2001`; either is valid **if it is unused**.

Before creating a new ACL, inspect existing ACLs and choose a free number. If ACL `2000` already has another purpose, use `2001`, `2002`, or another unused number in the basic-ACL range. Never overwrite or repurpose an existing ACL just to match an example.

CLI check:

```text
display acl all
```

## Method A — Web GUI on HP 1910

Exact wording can differ slightly between firmware revisions, but HP 1910-family Web interfaces expose SNMP and ACL configuration from the navigation tree.

### 1. Configure the SNMP community

Typical path:

```text
Switching → SNMP → Community
```

Create or edit a community with these values:

- **Community Name:** `monitoring_ro`
- **Access:** read-only / read view
- **Manager / IP Address:** `10.10.20.15` when the firmware offers source-IP restriction directly on the community

Click **Apply**.

Then use **Save Configuration** so the change survives a reboot.

### 2. Create a source-IP ACL if needed

If your firmware does not provide the source IP directly in the SNMP Community screen, create a basic ACL that permits only the Zabbix server.

Depending on firmware, look under a path similar to:

```text
QoS / ACL → ACL
```

Create a **Basic IPv4 ACL**, choose an unused number in `2000–2999`, and add:

- action: **Permit**
- source IP: `10.10.20.15`
- wildcard: `0.0.0.0` / host-only

Do not add a broad permit rule after it unless you intentionally want other hosts to query SNMP.

### 3. Bind the ACL to SNMP

If the Web UI exposes an ACL field in the SNMP Community configuration, assign the ACL there. If it does not, use the CLI method below for that final binding.

## Method B — CLI

### 1. Enable SNMP and create the read-only community

```text
system-view
snmp-agent
snmp-agent community read monitoring_ro
```

### 2. Create an ACL restricted to the Zabbix server

First confirm that the chosen ACL number is unused:

```text
display acl all
```

Example using ACL `2000`:

```text
system-view
acl number 2000
 rule permit source 10.10.20.15 0
quit
```

### 3. Bind the ACL to the SNMP community

```text
snmp-agent community read monitoring_ro acl 2000
save
```

If your device already uses ACL `2000`, substitute another unused basic ACL number, for example `2001`, in **both** the ACL definition and the SNMP community command.

## Verify SNMP from the Zabbix server

On Linux:

```bash
snmpwalk -v2c -c monitoring_ro 10.10.20.2 1.3.6.1.2.1.1
```

A healthy response should return standard system OIDs such as `sysDescr`, `sysName` and `sysUpTime`.

## Add the switch in Zabbix GUI

Path:

```text
Data collection → Hosts → Create host
```

Then:

1. Enter a neutral host name, for example `SW-ACCESS-01`.
2. Add an **SNMP interface**.
3. Set the interface IP to the switch management IP, here `10.10.20.2`.
4. Select **SNMPv2**.
5. Configure the community as `monitoring_ro` (or use the template macro if the selected template expects one).
6. Link a suitable SNMP/network-switch template.
7. Save the host.

For HP/Comware devices, start with a generic SNMP network-device template if a model-specific template is unavailable.

## What to monitor first

- system uptime,
- interface operational state,
- interface traffic counters,
- interface errors/discards,
- device availability by SNMP,
- CPU and memory if exposed by the device MIB.

## Basic troubleshooting

If Zabbix reports an SNMP timeout, first test from the Zabbix server:

```bash
snmpwalk -v2c -c monitoring_ro 10.10.20.2 1.3.6.1.2.1.1.3.0
```

Then check:

- UDP/161 reachability,
- SNMP community value,
- whether the ACL permits the **Zabbix server source IP**,
- whether the ACL number bound to SNMP is the same ACL you configured,
- whether SNMP is enabled,
- the correct switch management IP/interface,
- firewall rules between Zabbix and the switch.

Keep SNMP read-only unless there is a specific reason to enable write access. For new deployments, SNMPv3 is preferable when the device and operational environment support it.
