# AI-SysAdmin — event normalization foundation

## What is WAZABIG?

**WAZABIG** is a lightweight infrastructure control plane that sits above tools such as **Zabbix, Wazuh and GLPI**. Its job is to combine monitoring, security and asset/service-management signals into one operational view: normalize events, correlate them with the same host or asset, group repeated symptoms into issues, support diagnosis, and provide tightly controlled remediation workflows.

WAZABIG does **not** replace those source systems. Zabbix remains the monitoring source, Wazuh the security source, and GLPI the asset/ticket source. WAZABIG acts as the layer that connects them and gives an administrator one place to reason about what is happening.

**AI-SysAdmin** is the local AI/automation layer being built inside that architecture. It first receives deterministic, normalized operational data from WAZABIG; only then can AI-assisted diagnosis, explanation or remediation be added. This separation is intentional: raw alerts are not handed directly to an AI model and unknown conditions are not automatically “fixed”.

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
