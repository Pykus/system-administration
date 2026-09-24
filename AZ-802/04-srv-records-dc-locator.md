# SRV records and DC Locator — AZ-802 drill

## Core idea
Active Directory clients do not normally locate domain controllers by querying only a host name. They use DNS SRV records published under the AD DNS namespace, then DC Locator evaluates the returned candidates for the required service and site.

## Scenario
A domain-joined client in site `Branch` authenticates slowly and sometimes contacts `DC01` in site `HQ` even though `DC02` should service the local subnet.

## Diagnosis
First verify that the client uses the correct AD DNS servers. Then confirm that the expected SRV records exist and that the client's IP subnet is mapped to the correct AD site.

## Commands
```powershell
Resolve-DnsName _ldap._tcp.dc._msdcs.contoso.local -Type SRV
Resolve-DnsName _kerberos._tcp.contoso.local -Type SRV
nltest /dsgetdc:contoso.local
nltest /dsgetsite
repadmin /replsummary
```

## Interpretation
If the general domain-controller SRV records are present but the client reports the wrong site, investigate AD Sites and Services subnet mapping. If the relevant SRV records are missing, check DNS registration on the domain controller and the health of the Netlogon service.

A healthy result should provide domain controllers that advertise the required service. Site-aware location then helps the client prefer an appropriate controller rather than simply choosing any DNS-resolved server.

## Repair / recommended action
Fix the underlying site/subnet or DNS-registration problem. Avoid hard-coding clients to a particular domain controller because that bypasses the normal discovery and failover mechanism.

Useful checks include restarting Netlogon only when justified, verifying the domain controller's DNS configuration, and confirming that AD replication is healthy before treating missing SRV records as an isolated DNS problem.

## Exam trap
An A or AAAA record for a domain controller is not enough for normal AD service discovery. Clients rely on SRV records such as `_ldap._tcp...` and `_kerberos._tcp...` to locate services.

## Interview question
**What does DC Locator use to find a suitable domain controller?**

It combines DNS SRV queries with information such as the requested service and AD site topology, then selects a suitable domain controller from the available candidates.

## C1 / CAE phrase
**narrow down** — reduce the number of possible causes during troubleshooting.
