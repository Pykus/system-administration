import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

BAD_CODEPOINTS={0x00C3,0x00C5,0x00C4,0x00C2}
def bad_text(s):
    return any(ord(c) in BAD_CODEPOINTS or 0x80<=ord(c)<=0x9f for c in s)
def walk_bad(v,path=""):
    out=[]
    if isinstance(v,str):
        if bad_text(v): out.append((path,v))
    elif isinstance(v,list):
        for i,x in enumerate(v): out+=walk_bad(x,f"{path}/{i}")
    elif isinstance(v,dict):
        for k,x in v.items(): out+=walk_bad(x,f"{path}/{k}")
    return out

class TestEncodingMigration572(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,72))

    def test_real_state_constraints_are_clean_after_schema(self):
        raw=json.loads((ROOT/"data"/"state.json").read_text(encoding="utf-8-sig"))
        s=app.ensure_state_schema(raw)
        self.assertEqual(walk_bad(s.get("global_constraints",[])),[])

    def test_key_constraint_labels_are_exact_polish(self):
        s=app.ensure_state_schema(json.loads((ROOT/"data"/"state.json").read_text(encoding="utf-8-sig")))
        d={x["key"]:x for x in s["global_constraints"]}
        self.assertEqual(d["max_day_13"]["label"],"Maks. dy\u017cur\u00f3w dziennie \u2013 1\u20133")
        self.assertEqual(d["max_day_school"]["label"],"Maks. dy\u017cur\u00f3w dziennie \u2013 ca\u0142a szko\u0142a")
        self.assertEqual(d["max_week"]["label"],"Maks. dy\u017cur\u00f3w tygodniowo")
        self.assertEqual(d["balance_day"]["label"],"Wyr\u00f3wnuj liczb\u0119 dy\u017cur\u00f3w w dniu")
        self.assertEqual(d["balance_week"]["label"],"Wyr\u00f3wnuj liczb\u0119 dy\u017cur\u00f3w w tygodniu")
        self.assertEqual(d["max_day_13"]["scope"],"1\u20133")
        self.assertEqual(d["max_day_school"]["scope"],"szko\u0142a")

    def test_runtime_sources_have_no_classic_mojibake(self):
        for rel in ("app.py","static/index.html","static/teacher.html"):
            text=(ROOT/rel).read_text(encoding="utf-8")
            self.assertFalse(any(ord(c) in BAD_CODEPOINTS for c in text),rel)
            self.assertFalse(any(0x80<=ord(c)<=0x9f for c in text),rel)

    def test_repair_is_idempotent_and_repairs_known_case(self):
        good="Maks. dy\u017cur\u00f3w dziennie \u2013 ca\u0142a szko\u0142a"
        self.assertEqual(app._repair_text_encoding_v572(good),good)
        broken="Maks. dy\u00c5\u00bcur\u00c3\u00b3w"
        self.assertEqual(app._repair_text_encoding_v572(broken),"Maks. dy\u017cur\u00f3w")

if __name__=="__main__":
    unittest.main(verbosity=2)
