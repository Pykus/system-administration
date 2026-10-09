import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
APP=(ROOT/"app.py").read_text(encoding="utf-8")

class TestBreakThresholdLabels556(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,56))

    def test_edge_rule_is_named_as_over_ten_minutes(self):
        self.assertIn("po ostatniej lekcji, przerwa &gt;10 min",HTML)
        self.assertIn("przed pierwszą lekcją, przerwa &gt;10 min",HTML)
        self.assertIn("10-minutowa pozostaje krótką przerwą",HTML)

    def test_true_long_break_threshold_is_over_ten_minutes(self):
        self.assertEqual(app.LONG_BREAK_MINUTES,11)
        self.assertIn("długa przerwa zaczyna się powyżej 10 minut",HTML)

    def test_working_tighten_labels_use_same_semantics(self):
        self.assertIn('("after_last_long","przerwa >10 min po ostatniej lekcji")',APP)
        self.assertIn('("before_first_long","przerwa >10 min przed pierwszą lekcją")',APP)

    def test_ui_keeps_actual_draft_separate_from_proven_minimum(self):
        self.assertIn("Stan TEGO szkicu, nie minimum",HTML)
        self.assertIn("Udowodnione minimum przez preflight",HTML)
        self.assertIn("Poniższa lista nie jest listą kandydatów",HTML)

if __name__=="__main__":
    unittest.main()
