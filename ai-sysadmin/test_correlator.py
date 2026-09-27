import unittest
from correlator import correlate

class CorrelatorTests(unittest.TestCase):
    def test_merges_same_host_and_problem_across_sources(self):
        events = [
            {"source":"zabbix","entity":"LAB-DC1","problem_kind":"service","severity":2,"message":"service unavailable","source_event_id":"z1"},
            {"source":"wazuh","entity":"lab-dc1","problem_kind":"service","severity":3,"message":"service failure logged","source_event_id":"w1"},
        ]
        issues = correlate(events)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["sources"], ["wazuh", "zabbix"])
        self.assertEqual(issues[0]["severity"], 3)
        self.assertEqual(issues[0]["event_count"], 2)
        self.assertEqual(len(issues[0]["evidence"]), 2)

    def test_keeps_different_problem_kinds_separate(self):
        events = [
            {"source":"zabbix","entity":"LAB-PC1","problem_kind":"disk","severity":2},
            {"source":"wazuh","entity":"LAB-PC1","problem_kind":"auth","severity":4},
        ]
        self.assertEqual(len(correlate(events)), 2)

if __name__ == "__main__":
    unittest.main()
