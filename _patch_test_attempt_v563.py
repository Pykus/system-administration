from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v5.63-ortools\tests\test_v563_break_priority.py")
s=p.read_text(encoding="utf-8")
needle='''        self.assertIn('hardened.add("avoid_wait")',APP)
'''
insert='''        self.assertIn('hardened.add("avoid_wait")',APP)
    def test_final_fallback_compares_both_orders_by_human_quality(self):
        self.assertIn('def attempt_quality(z):',APP)
        self.assertIn('"ostatni fallback - szkoła potem 1–3"',APP)
        self.assertIn('int(m.get("wait_lessons_total",10**6) or 0)',APP)
        self.assertIn('int(m.get("after_last_long",10**6) or 0)',APP)
        self.assertIn('int(m.get("before_first_long",10**6) or 0)',APP)
'''
assert needle in s
p.write_text(s.replace(needle,insert,1),encoding="utf-8")
print("patched")
