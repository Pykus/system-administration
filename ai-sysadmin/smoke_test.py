from wazabig.event_normalizer import normalize_event

a = normalize_event(
    "zabbix",
    {"host": "APP01", "message": "Zabbix agent is not available", "severity": "high"},
)
assert a.problem_kind == "zabbix_agent_unavailable"

b = normalize_event(
    "wazuh",
    {
        "agent": {"name": "WS01"},
        "rule": {"description": "High CPU utilization detected", "level": 9},
    },
)
assert b.severity == "high"
assert b.problem_kind == "cpu_high"

c = normalize_event(
    "windows_event",
    {
        "Computer": "CLIENT01",
        "Message": "Synthetic application-specific failure",
        "LevelDisplayName": "Error",
    },
)
assert c.problem_kind is None
assert c.remediation_mode == "privileged_manual"

s = normalize_event(
    "syslog",
    {"hostname": "SW01", "message": "Interface is down", "severity": "warning"},
)
assert s.remediation_mode == "physical_check"

print("AI_SYSADMIN_SMOKE_OK")
