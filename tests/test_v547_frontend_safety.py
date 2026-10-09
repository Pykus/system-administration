import re, unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")

def method_body(name):
    m=re.search(r"(?:async\s+)?"+re.escape(name)+r"\([^)]*\)\{",HTML)
    if not m: return ""
    start=m.start()
    nxt=re.search(r"\n(?:async\s+)?[A-Za-z_$][\w$]*\([^)]*\)\{",HTML[m.end():])
    end=m.end()+nxt.start() if nxt else min(len(HTML),m.end()+6000)
    return HTML[start:end]

class TestFrontendSafety547(unittest.TestCase):
    def test_station_label_rename_does_not_cancel_solver_job(self):
        b=method_body("renameStation13")
        self.assertTrue(b)
        self.assertNotIn("prepareParameterSave",b)
        self.assertNotIn("finishSolverMutation",b)
        self.assertIn("applyStation13Response",b)

    def test_save_variant_checks_http_before_using_response(self):
        b=method_body("saveVariant")
        self.assertIn("if(!r.ok)",b)
        self.assertLess(b.index("if(!r.ok)"),b.index("await r.json()"))

    def test_dismiss_teacher_request_checks_http(self):
        b=method_body("dismissTeacherRequest")
        self.assertIn("if(!r.ok)",b)
        self.assertIn("alert(",b)

    def test_full_recalc_request_dismisses_before_local_mutation_and_checks_http(self):
        b=method_body("fullRecalcFromRequest")
        self.assertIn("if(!dr.ok)",b)
        self.assertLess(b.index("fetch('/api/teacher-recalc-requests/"),b.index("this.manualBlocks"))

    def test_teacher_registry_checks_http(self):
        b=method_body("loadTeacherRegistry")
        self.assertIn("if(!r.ok)",b)

    def test_health_checks_http(self):
        b=method_body("refreshHealth")
        self.assertIn("if(!r.ok)",b)

    def test_reload_checks_config_http(self):
        b=method_body("reload")
        self.assertIn("if(!r.ok)",b)
        self.assertLess(b.index("if(!r.ok)"),b.index("await r.json()"))

    def test_all_fetch_literal_families_match_fastapi_routes(self):
        routes=[getattr(r,"path","") for r in app.app.routes]
        args=re.findall(r"fetch\(([^\n;]+?)(?:,\{|\))",HTML)
        unmatched=[]
        families=0
        for expr in args:
            if "/api/" not in expr: continue
            lits=[x.split("?")[0] for x in re.findall(r"['\"]([^'\"]*)['\"]",expr) if x]
            if not lits: continue
            families+=1
            if not any(all((lambda seq: seq[0])( [route.find(lit, (0 if i==0 else 0))] )>=0 for i,lit in enumerate(lits)) for route in routes):
                # Ordered literal check, preserving dynamic gaps.
                ok=False
                for route in routes:
                    pos=0
                    for lit in lits:
                        j=route.find(lit,pos)
                        if j<0: break
                        pos=j+len(lit)
                    else:
                        ok=True;break
                if not ok: unmatched.append((expr,lits))
        self.assertGreaterEqual(families,45)
        self.assertEqual(unmatched,[])
