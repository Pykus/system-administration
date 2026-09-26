# HP 1910 / Comware — SNMP read-only and Zabbix monitoring

This short guide shows a minimal, read-only SNMP setup on an HP 1910-class switch and how to add it to Zabbix.

> Use a unique SNMP community in production. The example below uses `monitoring_ro` only as a placeholder.

## 1. Enable SNMP on the switch

From the switch CLI:

```text
system-view
snmp-agent
snmp-agent community read monitoring_ro
save
```

This creates an SNMP v2c read-only community.

## 2. Restrict SNMP to the monitoring server

Prefer limiting SNMP access to the Zabbix server instead of allowing every host to query the switch.

Example concept:

```text
acl number 2000
 rule permit source 10.10.20.15 0
 rule deny
quit
```

Then bind the ACL to the SNMP community if supported by the firmware:

```text
snmp-agent community read monitoring_ro acl 2000
save
```

Use the actual syntax supported by your HP 1910 firmware revision; older Web/Comware variants can differ slightly.

## 3. Verify SNMP from the Zabbix server

On Linux:

```bash
snmpwalk -v2c -c monitoring_ro 10.10.20.2 1.3.6.1.2.1.1
```

A healthy response should return standard system OIDs such as `sysDescr`, `sysName` and `sysUpTime`.

## 4. Add the switch to Zabbix

In Zabbix:

1. Go to **Data collection → Hosts**.
2. Create a new host.
3. Add an **SNMP interface** with the switch IP address.
4. Select SNMP version **SNMPv2**.
5. Set the community to `monitoring_ro`.
6. Link a suitable network switch template.

For HP/Comware devices, start with a generic SNMP network-device template if a model-specific template is unavailable.

## 5. What to monitor first

Useful initial items:

- system uptime,
- interface operational state,
- interface traffic counters,
- interface errors/discards,
- device availability by SNMP,
- CPU and memory if exposed by the device MIB.

## 6. Basic troubleshooting

If Zabbix reports SNMP timeout:

```bash
snmpwalk -v2c -c monitoring_ro 10.10.20.2 1.3.6.1.2.1.1.3.0
```

Then check:

- UDP/161 reachability,
- the SNMP community,
- ACL/source-IP restrictions,
- whether SNMP is enabled,
- the correct management IP/interface,
- firewall rules between Zabbix and the switch.

Keep SNMP read-only unless there is a specific reason to enable write access. For new deployments, SNMPv3 is preferable when the device and operational environment support it.
