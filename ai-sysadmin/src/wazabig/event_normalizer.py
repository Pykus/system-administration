from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .problem_catalog import classify_problem


@dataclass(frozen=True)
class NormalizedEvent:
    source: str
    entity: str
    message: str
    severity: str
    problem_kind: str | None
    summary: str
    remediation_mode: str


def _severity(value: Any) -> str:
    if isinstance(value, int):
        if value >= 12:
            return "critical"
        if value >= 8:
            return "high"
        if value >= 4:
            return "warning"
        return "info"
    text = str(value or "").strip().lower()
    if text in {"disaster", "critical", "crit", "fatal", "emerg"}:
        return "critical"
    if text in {"high", "error", "err", "alert"}:
        return "high"
    if text in {"warning", "warn", "average"}:
        return "warning"
    if text in {"information", "informational", "info", "notice"}:
        return "info"
    return "unknown"


def _extract(source: str, payload: Mapping[str, Any]) -> tuple[str, str, Any]:
    if source == "zabbix":
        return (
            str(payload.get("host") or payload.get("name") or "unknown"),
            str(payload.get("message") or payload.get("problem") or ""),
            payload.get("severity"),
        )
    if source == "wazuh":
        agent = payload.get("agent") or {}
        rule = payload.get("rule") or {}
        return (
            str(agent.get("name") or "unknown"),
            str(rule.get("description") or payload.get("message") or ""),
            rule.get("level"),
        )
    if source == "windows_event":
        return (
            str(payload.get("Computer") or payload.get("computer") or "unknown"),
            str(payload.get("Message") or payload.get("message") or ""),
            payload.get("LevelDisplayName") or payload.get("level"),
        )
    if source == "syslog":
        return (
            str(payload.get("hostname") or "unknown"),
            str(payload.get("message") or ""),
            payload.get("severity"),
        )
    raise ValueError(f"Unsupported event source: {source}")


def normalize_event(source: str, payload: Mapping[str, Any]) -> NormalizedEvent:
    source = source.strip().lower()
    entity, message, raw_severity = _extract(source, payload)
    rule = classify_problem(message)

    if rule is None:
        return NormalizedEvent(
            source=source,
            entity=entity,
            message=message,
            severity=_severity(raw_severity),
            problem_kind=None,
            summary="Unclassified operational event",
            remediation_mode="privileged_manual",
        )

    remediation_mode = {
        "Monitoring": "source_tuning",
        "Capacity": "restricted_endpoint",
        "Performance": "read_only",
        "Service": "restricted_endpoint",
        "Network": "physical_check",
    }.get(rule.category, "read_only")

    return NormalizedEvent(
        source=source,
        entity=entity,
        message=message,
        severity=_severity(raw_severity),
        problem_kind=rule.kind,
        summary=rule.summary,
        remediation_mode=remediation_mode,
    )
