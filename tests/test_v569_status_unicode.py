import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
APP=(ROOT/"app.py").read_text(encoding="utf-8")
class TestStatusUnicode569(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,69))
    def test_current_startup_status_is_real_unicode(self):
        self.assertIn("Start: baseline i szerokie testy",APP)
        self.assertIn("od razu licz\u0119 baseline",APP)
        self.assertIn("fazy 1\u20133",APP)
        self.assertIn("najlepszy cz\u0119\u015bciowy trop",APP)
        self.assertNotIn("licz?",APP)
        self.assertNotIn("cz??ciowy",APP)


if __name__=="__main__":
    unittest.main(verbosity=2)
