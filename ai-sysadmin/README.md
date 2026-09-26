# AI-SysAdmin — event normalization foundation

## What is WAZABIG?

**WAZABIG** is a lightweight infrastructure control plane that sits above tools such as **Zabbix, Wazuh and GLPI**. Its job is to combine monitoring, security and asset/service-management signals into one operational view: normalize events, correlate them with the same host or asset, group repeated symptoms into issues, support diagnosis, and provide tightly controlled remediation workflows.

WAZABIG does **not** replace those source systems. Zabbix remains the monitoring source, Wazuh the security source, and GLPI the asset/ticket source. WAZABIG acts as the layer that connects them and gives an administrator one place to reason about what is happening.

**AI-SysAdmin** is the local AI/automation layer being built inside that architecture. It first receives deterministic, normalized operational data from WAZABIG; only then can AI-assisted diagnosis, explanation or remediation be added.

## Current practical status

The project now has two working layers:

1. a deterministic event normalizer for Zabbix, Wazuh, Windows Event Log and syslog-shaped events,
2. a **read-only Zabbix adapter** that retrieves active problems through `problem.get`, resolves their hosts through `trigger.get`, attaches source evidence and generates a stable SHA-256 correlation key.

The Zabbix adapter was tested against synthetic API responses and then smoke-tested against a live Zabbix API in the integration environment before publication. No production data, hostnames, addresses, tokens or raw events are included in this repository.

## Safety model

- Unknown events are **not guessed**.
- Unknown events fall back to `privileged_manual`.
- The Zabbix adapter is read-only.
- Normalization and correlation do not execute remediation.
- Public examples use synthetic hosts and data only.
- Source systems remain authoritative.

## Normalized fields

`source`, `entity`, `message`, `severity`, `problem_kind`, `summary`, `remediation_mode`.

The Zabbix adapter adds:

`source_event_id`, `source_object_id`, `observed_at`, `correlation_key`.

## Why correlation comes before AI

Repeated source alerts should not be handed independently to an AI model. WAZABIG first creates a stable operational identity for the problem. AI-assisted diagnosis can then work on a grouped issue together with evidence instead of reacting to every raw alert.

## Next practical increments

1. Persist correlation keys and deduplicate repeated Zabbix events into issues.
2. Add the same read-only adapter contract for Wazuh.
3. Correlate Zabbix and Wazuh signals to a canonical host.
4. Attach source evidence to every diagnosis.
5. Add local AI-assisted explanations only after deterministic correlation.
6. Add approval-gated remediation with validation and audit logging.
