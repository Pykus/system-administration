import unittest
from pathlib import Path
from collections import Counter

import app

ROOT=Path(__file__).parent


class TestBellSource(unittest.TestCase):
    def test_same_bell_schedule_every_day(self):
        by={}
        for b in app.SEED["breaks"]:
            by.setdefault(b["abbr"],[]).append((b["label"],b["time"],b["minutes"],b.get("prev"),b.get("next")))
        self.assertEqual(set(by),{"Pn","Wt","Śr","Czw","Pi"})
        ref=by["Pn"]
        for code in ["Wt","Śr","Czw","Pi"]:
            self.assertEqual(by[code],ref)

    def test_two_long_breaks_each_day(self):
        c=Counter(b["abbr"] for b in app.SEED["breaks"] if int(b.get("minutes",0) or 0)>=15)
        self.assertEqual(c,Counter({"Pn":2,"Wt":2,"Śr":2,"Czw":2,"Pi":2}))


class TestDiagnosticsUI(unittest.TestCase):
    def test_validation_is_inside_diagnostics(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        self.assertNotIn("mainTab==='validation'",h)
        self.assertIn("Walidacja konfiguracji",h)
        self.assertIn("Propozycje dojścia do pełnej obsady",h)
        self.assertIn("Uwagi techniczne i szczegółowa diagnostyka solvera",h)

    def test_full_recalc_has_visible_feedback(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for x in ["recalculateAll","recalculating","calcMessage","spinner","refreshEpoch"]:
            self.assertIn(x,h)

    def test_fixed_rules_are_not_repair_candidates(self):
        s=app.load_state()
        tokens={x["token"] for x in app._repair_candidates(s)}
        for k in app.FIXED_HARD_KEYS:
            self.assertNotIn("g:"+k,tokens)


if __name__=="__main__":
    unittest.main(verbosity=2)
