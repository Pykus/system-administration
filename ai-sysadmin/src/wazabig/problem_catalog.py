from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProblemRule:
    kind: str
    category: str
    summary: str
    needles: tuple[str, ...]


RULES: tuple[ProblemRule, ...] = (
    ProblemRule(
        "zabbix_agent_unavailable",
        "Monitoring",
        "Monitoring agent unavailable",
        ("zabbix agent is not available", "agent is unavailable"),
    ),
    ProblemRule(
        "zabbix_active_checks_unavailable",
        "Monitoring",
        "Active checks unavailable",
        ("active checks are not available",),
    ),
    ProblemRule(
        "zabbix_value_cache_low_memory",
        "Monitoring",
        "Value cache is in low-memory mode",
        ("value cache working in low-memory mode",),
    ),
    ProblemRule(
        "zabbix_missing_data",
        "Monitoring",
        "Monitoring data is missing",
        ("no data", "not supported"),
    ),
    ProblemRule(
        "disk_space_low",
        "Capacity",
        "Disk free space is low",
        ("disk space is low", "free disk space"),
    ),
    ProblemRule(
        "cpu_high",
        "Performance",
        "CPU utilization is high",
        ("high cpu", "cpu utilization"),
    ),
    ProblemRule(
        "memory_high",
        "Performance",
        "Memory utilization is high",
        ("high memory", "memory utilization"),
    ),
    ProblemRule(
        "windows_service_not_running",
        "Service",
        "A monitored Windows service is not running",
        ("service is not running",),
    ),
    ProblemRule(
        "network_link_down",
        "Network",
        "Network interface is down",
        ("link down", "interface is down"),
    ),
    ProblemRule(
        "network_speed_changed",
        "Network",
        "Network interface speed changed",
        ("speed changed",),
    ),
)


def classify_problem(text: str) -> ProblemRule | None:
    normalized = " ".join(text.lower().split())
    for rule in RULES:
        if any(needle in normalized for needle in rule.needles):
            return rule
    return None
