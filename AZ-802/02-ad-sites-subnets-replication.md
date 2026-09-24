# AZ-802 Drill — AD Sites, Subnets and Replication

## Core idea
AD Sites map physical/network topology to Active Directory. Correct subnet-to-site mapping helps clients find nearby domain controllers and lets AD schedule inter-site replication efficiently.

## Scenario
A branch-office client authenticates against `DC01` in the main site instead of nearby `DC02`. Replication between sites is also slower than expected.

## Diagnosis
First verify that the client's IP subnet exists in **Active Directory Sites and Services** and is linked to the correct site. Then inspect replication topology and failures.

## Commands
```powershell
Get-ADReplicationSite -Filter *
Get-ADReplicationSubnet -Filter *
Get-ADReplicationPartnerMetadata -Target DC02
repadmin /replsummary
repadmin /showrepl DC02
```

## Interpretation
If the client's subnet is missing or assigned to the wrong site, DC Locator may choose a less appropriate domain controller. Replication errors in `repadmin` point to DNS, RPC, connectivity, authentication or topology problems rather than merely a slow link.

## Repair / recommended action
Create or correct the subnet object and associate it with the proper site. Verify DNS and connectivity, then allow normal replication topology to converge. Avoid forcing replication repeatedly before fixing the underlying error.

## Exam trap
A **site** is not the same thing as an AD domain or an IP subnet. One site can contain multiple subnets, and a domain can span many sites.

## Interview question / model answer
**Q:** Why define subnets in AD Sites and Services?

**A:** So clients and services can map an IP address to an AD site, prefer appropriate domain controllers, and let AD apply site-aware replication behavior.

## C1 / CAE expression
**`to narrow down the root cause`** — to reduce several possible explanations until the real cause is identified.
