# AI-SysAdmin — event normalization foundation

This is the first practical AI-SysAdmin building block for WAZABIG.

It converts events from several administrative sources into one small operational model before any AI-assisted diagnosis or remediation is attempted.

Supported input shapes in this first increment:

- Zabbix
- Wazuh
- Windows Event Log exports
- syslog

## Safety model

- Unknown events are **not guessed**.
- Unknown events fall back to `privileged_manual`.
- Normalization does not execute remediation.
- Public examples use synthetic hosts and data only.
- Source systems remain authoritative.

## Normalized fields

`source`, `entity`, `message`, `severity`, `problem_kind`, `summary`, `remediation_mode`.

## Smoke test

PowerShell:

```powershell
$env:PYTHONPATH="$PWD\src"
python smoke_test.py
```

Expected result:

```text
AI_SYSADMIN_SMOKE_OK
```

The same smoke test was executed successfully in the integration environment before this code was published.

## Next practical increments

1. Read-only adapters for live Zabbix and Wazuh events.
2. Stable correlation/deduplication keys across sources.
3. Evidence attached to every diagnosis.
4. Local AI-assisted explanation only after deterministic normalization.
5. Approval-gated remediation with validation and audit logging.
