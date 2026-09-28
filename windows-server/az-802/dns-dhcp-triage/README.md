# AZ-802 DNS and DHCP triage

This example provides a read-only Windows troubleshooting script for separating three common failure classes:

1. the client did not receive usable IP configuration;
2. the client has IP connectivity but is using the wrong or unreachable DNS servers;
3. DNS servers respond, but the requested name is missing or inconsistent.

The goal is to collect evidence before changing leases, scopes, DNS records, adapters, or firewall rules.

## What the script collects

`Collect-DnsDhcpTriage.ps1` records:

- active IPv4 interfaces, addresses, gateways, and DHCP status;
- configured IPv4 DNS servers per interface;
- whether the client is using an APIPA `169.254.0.0/16` address;
- DNS resolution through the system resolver;
- DNS resolution queried directly against each configured DNS server;
- a timestamped JSON report that can be attached to an incident or compared between machines.

It does not renew leases, flush DNS caches, modify adapters, remove records, or restart services.

## Example

```powershell
.\Collect-DnsDhcpTriage.ps1 -NameToResolve "host-a.example.org" -OutputPath ".\triage.json"
```

For an Active Directory environment, use a real internal test name locally but replace it with a synthetic value before publishing logs or examples.

## How to interpret the result

- **APIPA address present**: investigate DHCP reachability, VLAN/switch path, relay configuration, or adapter connectivity before changing DNS.
- **Valid IP and gateway, but all direct DNS queries fail**: investigate reachability to the configured DNS servers.
- **One DNS server resolves and another does not**: compare zone replication, forwarding, and server health.
- **Direct DNS queries work but the default resolver fails**: inspect client DNS configuration and suffix/search behavior.
- **All DNS queries return a consistent NXDOMAIN**: verify that the expected record actually exists before treating the client as broken.

This is a triage collector, not an automatic repair tool.
