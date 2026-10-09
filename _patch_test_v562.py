from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v5.63-ortools\tests\test_v562_home_group_architecture.py")
s=p.read_text(encoding="utf-8")
old='self.assertEqual(app.PLANNER_VERSION,"5.62")'
new='self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,62))'
assert old in s, old
p.write_text(s.replace(old,new),encoding="utf-8")
print("patched")