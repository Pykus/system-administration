# OPNsense 01 — migrating a legacy installation to a modern release

This guide is for very old OPNsense installations where a direct jump to the newest release should not be assumed to be safe.

As of September 2026, the current Community Edition release line is 26.7. OPNsense uses two major releases per year, and major upgrades are intended to move between supported release lines rather than skip many years in one step.

## Core rule

Do not treat a legacy 16.x appliance as if it were a normal one-step in-place upgrade.

For an installation that old, the safer approach is:

1. inventory the existing configuration,
2. export and securely store a configuration backup,
3. document interfaces, gateways, routes, NAT and firewall behavior,
4. reproduce the configuration in a lab or spare appliance,
5. install a current supported OPNsense image,
6. restore or carefully recreate configuration in controlled stages,
7. validate routing and firewall behavior before cutover.

## 1. Capture the current state

Before changing anything, record at least:

- WAN/LAN/optional interface assignments,
- VLAN IDs and parent interfaces,
- static IPv4/IPv6 addresses,
- gateways and gateway groups,
- static routes,
- outbound NAT mode and rules,
- port forwards and one-to-one NAT,
- firewall aliases,
- interface and floating firewall rules,
- DHCP ranges and reservations,
- DNS resolver/forwarder settings,
- VPN configuration,
- certificates and certificate authorities,
- installed plugins,
- high-availability settings if used.

Do not publish or share the real values from this inventory. In documentation, replace them with examples such as `10.10.0.0/16`, `WAN`, `LAN`, `VLAN20`, and `vpn.example.com`.

## 2. Export a configuration backup

Use the OPNsense configuration backup function and keep more than one copy.

Before relying on the backup, verify that:

- the file is readable,
- the export is from the appliance you intend to migrate,
- sensitive configuration is stored securely,
- you know how to access the console if the web GUI becomes unavailable.

Do not commit real configuration XML files to a public repository.

## 3. Prefer staged migration over a blind direct upgrade

Current OPNsense documentation recommends console access for major upgrades because the upgrade runs offline and the web/SSH services are not available during the process.

For a release gap spanning many years, use a test environment first. A practical sequence is:

```text
legacy appliance
      |
      +--> export configuration
      |
      +--> document network behaviour
      |
      v
lab / spare appliance
      |
      +--> clean install of supported release
      |
      +--> controlled restore/recreation
      |
      +--> routing + firewall validation
      v
production cutover
```

## 4. Validate configuration in layers

Do not restore everything and immediately connect the appliance to production.

Validate in this order:

### Interfaces

- correct NIC-to-interface mapping,
- expected addresses and VLANs,
- no accidental interface swaps.

### Routing

- default gateway,
- static routes,
- gateway monitoring,
- gateway groups and failover behavior.

### NAT

- outbound NAT mode,
- port forwards,
- one-to-one NAT if present.

Newer OPNsense versions have changed parts of the NAT and firewall management interface, so old screenshots or menu paths should not be treated as authoritative.

### Firewall

- LAN-to-WAN connectivity,
- inter-VLAN rules,
- blocked traffic remains blocked,
- management access works only from intended networks.

### Services

- DHCP,
- DNS,
- VPN,
- monitoring,
- NTP and other local services.

## 5. Use a small acceptance test

Example neutral checklist:

```text
[ ] client receives expected DHCP address
[ ] client resolves DNS
[ ] client reaches permitted external destination
[ ] blocked test flow remains blocked
[ ] static route reaches test subnet
[ ] port forward reaches test service
[ ] VPN tunnel establishes
[ ] management GUI reachable only from admin network
```

## 6. Keep rollback simple

Before cutover, make rollback a physical and procedural option:

- keep the old appliance unchanged,
- label cables/interfaces,
- record which port maps to which network,
- keep a copy of the old configuration,
- define the exact point at which you revert.

If the new appliance fails routing, NAT, firewall or VPN acceptance tests, restore the previous appliance rather than debugging indefinitely during the production window.

## Notes for current releases

OPNsense 26.7 introduced significant changes around firewall rule management, interface/gateway APIs and Source NAT migration. When moving from a very old installation, validate these areas explicitly instead of assuming old GUI workflows map one-to-one to the current release.

## Next topics

Follow-up notes in this series can cover:

- interface and VLAN migration,
- gateways and static routes,
- firewall aliases and rules,
- outbound/source NAT,
- DHCP and DNS,
- VPN migration,
- monitoring and API-based administration.
