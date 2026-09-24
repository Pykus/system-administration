# AD-integrated DNS — AZ-802 drill

## Core idea
An AD-integrated DNS zone stores zone data in Active Directory instead of a standalone zone file. Replication follows an AD replication scope and can use secure dynamic updates.

## Scenario
`DC01` and `DC02` host `contoso.local`. A client registers a record on `DC01`, but queries sent to `DC02` do not return it.

## Diagnosis
First separate DNS registration from AD replication. Confirm the zone type and replication scope, then compare records on both DNS servers.

## Commands
```powershell
Get-DnsServerZone -ComputerName DC01
Get-DnsServerZone -ComputerName DC02
Resolve-DnsName host01.contoso.local -Server DC01
Resolve-DnsName host01.contoso.local -Server DC02
repadmin /replsummary
```

## Interpretation
If the record exists on `DC01` but not `DC02` and the zone is AD-integrated on both, investigate AD replication and the zone replication scope. If replication is healthy, check dynamic-update permissions and client registration.

## Repair / recommended action
Fix the underlying AD replication or DNS registration issue rather than manually creating duplicate records. Keep secure dynamic updates where domain clients are expected to register automatically.

## Exam trap
AD-integrated DNS does not use DNS zone transfer as its normal replication mechanism between AD-integrated replicas; the zone data is replicated through Active Directory.

## Interview question
**Why choose an AD-integrated zone?**

It provides multi-master DNS updates, AD replication, configurable replication scope and secure dynamic updates without maintaining a separate primary zone file.

## C1 / CAE phrase
**rule out** — eliminate a possible cause during troubleshooting.