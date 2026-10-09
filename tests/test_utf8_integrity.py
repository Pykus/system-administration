import ast, json, re, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BAD_FRAGMENTS=("szko?a","wed?ug","aktywno?ci","pojemno??","uwzgl?dnieniem",
               "dy?ur","pi?tro","wy??cznie","Zmie?","Usu?","ju? istnieje")
MOJIBAKE=("\ufffd","Ã","Å","Ä","Ĺ","Â","â","â€","â€“","â€”")
WORD_Q=re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]\?[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]")

def walk_strings(x):
    if isinstance(x,str):
        yield x
    elif isinstance(x,dict):
        for k,v in x.items():
            yield from walk_strings(k); yield from walk_strings(v)
    elif isinstance(x,list):
        for v in x: yield from walk_strings(v)

class TestUtf8Integrity(unittest.TestCase):
    def test_active_files_are_strict_utf8(self):
        for rel in ("app.py","solver_ortools.py","static/index.html","static/map.html","static/teacher.html","data/state.json"):
            raw=(ROOT/rel).read_bytes()
            raw.decode("utf-8")
    def test_python_user_strings_have_no_corruption(self):
        for rel in ("app.py","solver_ortools.py"):
            src=(ROOT/rel).read_text(encoding="utf-8")
            tree=ast.parse(src)
            for n in ast.walk(tree):
                if isinstance(n,ast.Constant) and isinstance(n.value,str):
                    s=n.value
                    self.assertFalse(any(x in s for x in MOJIBAKE),(rel,s))
                    self.assertIsNone(WORD_Q.search(s),(rel,s))
                    for bad in BAD_FRAGMENTS:
                        self.assertNotIn(bad,s,(rel,s))

    def test_current_state_strings_have_no_corruption(self):
        data=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        for s in walk_strings(data):
            self.assertFalse(any(x in s for x in MOJIBAKE),s)
            self.assertIsNone(WORD_Q.search(s),s)
            for bad in BAD_FRAGMENTS:
                self.assertNotIn(bad,s)

    def test_html_has_utf8_declaration_and_no_known_corruption(self):
        for rel in ("static/index.html","static/map.html","static/teacher.html"):
            s=(ROOT/rel).read_text(encoding="utf-8")
            self.assertRegex(s.lower(),r'<meta[^>]+charset=["\']?utf-8')
            self.assertFalse(any(x in s for x in MOJIBAKE),(rel,"mojibake"))
            for bad in BAD_FRAGMENTS:
                self.assertNotIn(bad,s,(rel,bad))

if __name__=="__main__":
    unittest.main(verbosity=2)
