# OPNsense 02 - troubleshooting routed Veyon over OpenVPN

This chapter presents a production-safe method for diagnosing a remote Veyon Master that reaches classroom or lab clients through OPNsense, OpenVPN, and a downstream routed subnet.

The central rule is simple: **prove each layer before changing the next one**. A Veyon GUI symptom is not enough evidence to justify routing, firewall, DNS, or directory changes.

## Example topology

All values below are documentation-only examples:

- VPN client pool: `10.8.0.0/24`
- OPNsense LAN: `10.20.30.1/24`
- downstream lab router: `10.20.30.254`
- routed lab subnet: `192.0.2.0/24`
- example Veyon client: `192.0.2.25`
- internal DNS server: `10.20.30.53`
- private DNS zone: `lab.example.org`
- example client FQDN: `pc25.lab.example.org`

The remote Master connects to OpenVPN, receives a VPN address, and must then reach the routed lab subnet through OPNsense.

## Evidence-first diagnostic order

Use this order and stop changing lower layers once they have been proven:

1. VPN client route to the lab subnet.
2. OPNsense static route to the downstream router.
3. TCP reachability of Veyon on port 11100.
4. Veyon BuiltinDirectory/network object addressing.
5. Veyon public/private authentication keys.
6. Internal DNS resolution for any FQDN stored in Veyon.
7. OpenVPN DNS push, followed by reconnect and retest.

A later failure does not invalidate an earlier successful test. For example, if TCP/11100 works by IP, routing and service reachability are already proven for that path.

## 1. Verify the VPN client route

On the remote Windows Veyon Master, first confirm that the routed lab prefix is installed on the VPN interface.

```powershell
Get-NetRoute -AddressFamily IPv4 |
  Where-Object DestinationPrefix -eq '192.0.2.0/24' |
  Format-Table DestinationPrefix,NextHop,InterfaceAlias,RouteMetric
```

Expected evidence:

- the destination prefix is the lab subnet,
- the selected interface is the OpenVPN interface,
- the route is more specific than the default route.

If the route is absent, fix OpenVPN route distribution before investigating Veyon itself.

## 2. Verify the OPNsense static route

The VPN endpoint also needs a route from OPNsense toward the downstream router that owns the lab subnet.

For the example topology, the logical relationship is:

```text
192.0.2.0/24 -> 10.20.30.254
```
Confirm this in OPNsense routing configuration and, if needed, with read-only routing table inspection.

Do not add another default gateway on the remote Master. A routed lab subnet needs a specific route, not a second default route.

## 3. Test Veyon TCP reachability by IP

This is the decisive transport-layer test.

```powershell
Test-NetConnection 192.0.2.25 -Port 11100
```

If the result contains:

```text
TcpTestSucceeded : True
```

then the remote Master can reach the Veyon service on that host by IP.

That successful test proves that, for this destination:

- the VPN route is usable,
- OPNsense can forward the traffic,
- the downstream route works,
- intervening firewall policy permits the flow,
- the client is listening or otherwise accepting TCP/11100.

At this point, do **not** keep modifying routes or adding speculative per-host firewall rules merely because the Veyon GUI still shows the host as unavailable.

## 4. Inspect Veyon BuiltinDirectory addressing

Next determine what address Veyon is actually trying to use.

```powershell
$veyon = 'C:\Program Files\Veyon\veyon-cli.exe'
& $veyon networkobjects list
```
Find the target host and inspect its configured address.

Two common cases exist:

- the network object stores an IP address such as `192.0.2.25`,
- the network object stores an FQDN such as `pc25.lab.example.org`.

If TCP/11100 succeeds by IP but Veyon stores an FQDN, DNS becomes the next diagnostic layer.

Do not replace every FQDN with a static IP as the first workaround. That hides the name-resolution problem and creates long-term address-management debt.

## 5. Verify Veyon authentication keys

Routing and DNS do not replace Veyon authentication. Confirm the expected keys on the Master.

```powershell
& $veyon authkeys list
```

In a public/private key deployment, the usual pattern is:

- the Veyon Master has the private key for the configured authentication identity,
- managed clients have the corresponding public key,
- normal clients do not need the Master's private key.

A missing or incorrect key is an authentication-layer failure. It should not be diagnosed by changing routes.

## 6. Test the exact FQDN stored in Veyon

If `networkobjects list` shows an FQDN, test that exact name first using the client's normal resolver configuration.

```powershell
Resolve-DnsName pc25.lab.example.org
```

Then test the same name explicitly against the intended internal DNS server.

```powershell
Resolve-DnsName pc25.lab.example.org -Server 10.20.30.53
```
This comparison is extremely useful.

If the default lookup fails but the explicit lookup against the internal DNS server succeeds, the private DNS data exists and the remaining problem is DNS delivery or resolver selection on the VPN client.

## 7. Repair OpenVPN DNS delivery and reconnect

A common failure pattern is:

1. the VPN route to the lab exists,
2. TCP/11100 succeeds by client IP,
3. the Veyon network object stores an internal FQDN,
4. the remote Master cannot resolve that FQDN with its current DNS configuration,
5. Veyon therefore reports the host as unavailable.

In this situation, the correct repair is to provide VPN clients with the **actual internal DNS service that resolves the private zone**.

Do not assume that the firewall's LAN address is automatically a usable DNS server for VPN clients. The authoritative or forwarding DNS service may live elsewhere, and the firewall resolver may not listen on or permit queries from the VPN interface.

Configure OpenVPN to push the intended internal DNS server, for example:

```text
DNS server: 10.20.30.53
private zone: lab.example.org
```

After changing VPN DNS delivery:

1. disconnect the VPN client,
2. reconnect it so the new DNS settings are applied,
3. inspect the VPN adapter DNS configuration,
4. rerun the exact FQDN lookup,
5. rerun the Veyon connection test.
Do not treat a successful reconnect as proof by itself. The evidence is the post-reconnect DNS result and the recovered Veyon session.

## Compact decision table

| Test | Result | Next diagnostic layer |
|---|---|---|
| `Get-NetRoute` for lab prefix | Missing or wrong interface | OpenVPN route push / client routing |
| VPN route present | Correct | OPNsense static route |
| OPNsense route to lab | Missing/wrong next hop | Fix static route to downstream router |
| `Test-NetConnection <client-ip> -Port 11100` | Fails | Routing, firewall, downstream router, or Veyon service |
| TCP/11100 by IP | Succeeds | Stop changing routing; inspect Veyon addressing |
| `veyon-cli networkobjects list` | Stores IP | Check keys and Veyon service/authentication |
| `veyon-cli networkobjects list` | Stores FQDN | Test that exact FQDN |
| Default `Resolve-DnsName` | Fails | Query intended internal DNS explicitly |
| Explicit internal-DNS lookup | Fails | Internal DNS zone/record/service problem |
| Explicit internal-DNS lookup | Succeeds | OpenVPN DNS push / client DNS selection |
| `veyon-cli authkeys list` | Expected private key missing on Master | Repair Veyon authentication material |
| DNS and keys both correct | Correct | Re-test Veyon GUI/session and inspect Veyon-specific logs/config |

## What not to change yet

Before the relevant read-only test fails, do not make speculative production changes.

In particular, do not:

- create one firewall rule per Veyon client when subnet-level connectivity is already proven,
- replace all Veyon FQDNs with static IP addresses merely to bypass DNS,
- add extra default gateways to the remote Master,
- redesign NAT when direct TCP/11100 by IP already succeeds,
- alter OPNsense routing after the route and TCP path have been proven,
- rotate Veyon keys before confirming that authentication is the failing layer,
- publish real configuration exports, hostnames, addresses, keys, or private-zone names.

Each change should answer a failed test, not a GUI symptom.

## Minimal repeatable PowerShell diagnostic set

Use synthetic values when documenting or sharing results.

```powershell
# 1. Route installed on the VPN client
Get-NetRoute -AddressFamily IPv4 |
  Where-Object DestinationPrefix -eq '192.0.2.0/24'

# 2. Veyon transport by IP
Test-NetConnection 192.0.2.25 -Port 11100

# 3. Veyon directory objects
$veyon = 'C:\Program Files\Veyon\veyon-cli.exe'
& $veyon networkobjects list

# 4. Veyon authentication material
& $veyon authkeys list

# 5. Name resolution using current client DNS
Resolve-DnsName pc25.lab.example.org

# 6. Name resolution using intended internal DNS
Resolve-DnsName pc25.lab.example.org -Server 10.20.30.53
```

## Why TCP/11100 by IP is the pivot test
A Veyon GUI status combines several dependencies into one visual result. It cannot tell you whether the failure is routing, DNS, object addressing, authentication, or the Veyon service.

By contrast, a successful `Test-NetConnection <client-ip> -Port 11100` is narrow and strong evidence. It proves that the specific IP path and service port are reachable at that moment.

That evidence prevents unnecessary production changes. Once TCP/11100 succeeds by IP, continue upward into Veyon's configured address, DNS, and authentication instead of repeatedly changing lower network layers.

## Production-safe troubleshooting sequence

A disciplined session can be summarized as:

```text
VPN route?
  |
  +-- no  -> repair route distribution
  |
  +-- yes -> OPNsense static route correct?
               |
               +-- no  -> repair route to downstream router
               |
               +-- yes -> TCP/11100 by IP?
                            |
                            +-- no  -> investigate transport/service path
                            |
                            +-- yes -> stop changing routing/firewall
                                         |
                                         v
                               Veyon object uses FQDN?
                                         |
                          +--------------+--------------+
                          |                             |
                         no                            yes
                          |                             |
                  check keys/service            resolve exact FQDN
                                                        |
                                     explicit internal DNS succeeds?
                                                        |
                                            +-----------+-----------+
                                            |                       |
                                           no                      yes
                                            |                       |
                                  repair DNS zone/service    push internal DNS
                                                            through OpenVPN
                                                                    |
                                                              reconnect/retest
```
## Acceptance criteria after a DNS repair

A DNS-related repair is complete only when all relevant evidence is true after a fresh VPN connection:

- the lab route is present on the VPN client,
- the target client still answers TCP/11100 by IP,
- the exact FQDN stored in Veyon resolves normally,
- the FQDN resolves to the intended private address,
- the Master still has the required private authentication key,
- Veyon can open the remote session.

This keeps the change scoped to the layer that actually failed and leaves previously proven routing untouched.

## Security and publication hygiene

When turning a private incident runbook into public documentation:

- use RFC 5737 documentation addresses such as `192.0.2.0/24`,
- use synthetic private ranges such as `10.8.0.0/24` and `10.20.30.0/24`,
- use `example.org` names,
- never publish real VPN pools, internal zones, hostnames, gateways, user names, authentication key names, or topology details,
- never commit exported firewall or VPN configurations containing secrets.

The troubleshooting method is reusable precisely because it depends on observable layers rather than organization-specific identifiers.