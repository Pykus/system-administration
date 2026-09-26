import unittest

from wazabig.zabbix_adapter import ZabbixAdapter


class FakeResponse:
    def __init__(self, result):
        self._result = result

    def raise_for_status(self):
        return None

    def json(self):
        return {"jsonrpc": "2.0", "result": self._result, "id": 1}


class FakeSession:
    def post(self, url, headers, json, timeout):
        if json["method"] == "problem.get":
            return FakeResponse([
                {
                    "eventid": "9001",
                    "objectid": "501",
                    "name": "Zabbix agent is not available",
                    "severity": "4",
                    "clock": "1700000000",
                }
            ])
        if json["method"] == "trigger.get":
            return FakeResponse([
                {
                    "triggerid": "501",
                    "description": "Agent unavailable",
                    "priority": "4",
                    "hosts": [{"hostid": "7", "host": "APP01", "name": "App 01"}],
                }
            ])
        raise AssertionError(json["method"])


class ZabbixAdapterTests(unittest.TestCase):
    def test_active_problem_becomes_normalized_event(self):
        adapter = ZabbixAdapter(
            "https://monitor.example/api_jsonrpc.php",
            "test-token",
            session=FakeSession(),
        )
        event = adapter.active_events(limit=10)[0]
        self.assertEqual(event.normalized.entity, "APP01")
        self.assertEqual(event.normalized.severity, "high")
        self.assertEqual(event.normalized.problem_kind, "zabbix_agent_unavailable")
        self.assertEqual(event.evidence.source_event_id, "9001")
        self.assertEqual(event.evidence.source_object_id, "501")
        self.assertEqual(len(event.correlation_key), 64)


if __name__ == "__main__":
    unittest.main()
