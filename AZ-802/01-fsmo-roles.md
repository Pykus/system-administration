# Drill 01 — FSMO roles

## Core idea

Active Directory is multi-master for most changes, but five operations use single-master roles called **FSMO roles**.

- Forest-wide: **Schema Master**, **Domain Naming Master**
- Domain-wide: **RID Master**, **PDC Emulator**, **Infrastructure Master**

## Scenario

`DC01` is offline. Users can still sign in and most AD changes work, but administrators need to determine whether any critical FSMO-dependent operation is affected.

## Diagnose

```powershell
netdom query fsmo
Get-ADDomain | Select-Object PDCEmulator,RIDMaster,InfrastructureMaster
Get-ADForest | Select-Object SchemaMaster,DomainNamingMaster
```

## Interpretation

- PDC Emulator: time source, password-change priority, account lockout coordination and several legacy compatibility functions.
- RID Master: allocates RID pools to domain controllers so new security principals can receive unique SIDs.
- Infrastructure Master: maintains cross-domain object references.
- Schema Master: controls schema changes.
- Domain Naming Master: controls adding/removing domains and application partitions.

## Repair

If the original role holder will return, **transfer** the role.

If it is permanently lost and cannot be recovered, **seize** the role to a healthy DC.

Example transfer:

```powershell
Move-ADDirectoryServerOperationMasterRole -Identity DC02 -OperationMasterRole PDCEmulator
```

Do not seize a role merely because a DC is temporarily unavailable.

## Exam trap

A failed FSMO holder does **not** mean the entire domain immediately stops working. Many AD operations continue because AD DS is multi-master.

## Interview question

**Q:** What is the difference between transferring and seizing an FSMO role?

**A:** A transfer is a planned handoff from a healthy current owner. A seizure is an emergency reassignment used when the former owner is permanently unavailable. After seizure, the old DC should not simply be returned to service as if nothing happened.

## CAE / C1 phrase

**single point of coordination** — a component that coordinates an operation that cannot safely be performed independently by every node.
