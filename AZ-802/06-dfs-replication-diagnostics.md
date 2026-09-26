# DFS Replication diagnostics — AZ-802 drill

## Core idea
DFS Namespaces provide a logical path; DFS Replication (DFSR) replicates folder contents between members. Troubleshoot namespace referral and replication health as separate layers.

## Scenario
Users can open `\\contoso.local\Public`, but files created on `FS01` do not appear promptly on `FS02`.

## Read-only checks
```powershell
Get-DfsnFolderTarget -Path '\\contoso.local\Public\Data'
Get-DfsReplicatedFolder
Get-DfsrMember
Get-DfsrConnection
Get-DfsrState
```

For a backlog check:
```powershell
Get-DfsrBacklog -GroupName 'PublicData' -FolderName 'Data' -SourceComputerName FS01 -DestinationComputerName FS02
```

## Interpretation
A working namespace referral does not prove that DFSR is healthy. A growing backlog points to replication delay or failure; an absent/disabled connection is a configuration problem rather than a client referral problem.

## Safe workflow
1. Confirm both members and the replicated folder.
2. Confirm the connection is enabled.
3. Measure backlog in both directions where appropriate.
4. Review DFS Replication event logs.
5. Check free disk space and connectivity before changing configuration.
6. Re-run the same checks after remediation.

## Exam trap
Do not treat DFS Namespace and DFS Replication as the same service. A namespace can remain reachable while replicated data is stale.

## Quick drill
**Q:** Which cmdlet estimates pending replicated files between two DFSR members?  
**A:** `Get-DfsrBacklog`.

**Q:** Does successful access to a DFS namespace prove replication is current?  
**A:** No.

## C1 phrase
**pinpoint the cause** — identify the exact source of a problem.
