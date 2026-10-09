
import unittest,copy
from pathlib import Path
import app,repair_farm
ROOT=Path(__file__).parent

class TestV512(unittest.TestCase):
    def test_version(self):
        self.assertEqual(app.app.version,"5.12")
        self.assertEqual(app.health()["version"],"5.12")

    def test_school_pool_never_contains_13(self):
        pool=app._school_pool(app.ALL)
        self.assertTrue(pool)
        self.assertFalse(any(app.GROUP.get(n)=="1-3" for n in pool))
        core=next(n for n in app.ALL if app.GROUP.get(n)=="1-3")
        st=app.load_state()
        _,_,ps=app._apply_repair_tokens_v2(st,st.get("enabled_teachers_13",[]),pool,["addschool:"+core])
        self.assertNotIn(core,ps)

    def test_wait_is_absolute_last_stage(self):
        st=app.load_state()
        e13=list(st.get("enabled_teachers_13",[])); es=app._school_pool(st.get("enabled_teachers_school",[]))
        base=app._joint_coverage_v2({**st,"solver_coverage_seconds":2,"solver_coverage_retry_seconds":8},e13,es,False)
        cs=app._repair_candidates_v2(st,e13,es,base)
        waits=[c for c in cs if c.get("token")=="gsoft:avoid_wait"]
        self.assertTrue(waits)
        self.assertEqual(waits[0]["search_stage"],3)
        self.assertTrue(waits[0]["wait_relax"])
        self.assertFalse(any(c["token"].startswith("addschool:") and app.GROUP.get(c["token"][10:])=="1-3" for c in cs))

    def test_9po_one_person_means_one_position(self):
        st=copy.deepcopy(app.load_state())
        b=next(b for b in app.SEED["breaks"] if b["label"]=="9/po")
        key=f"{b['abbr']}|{b['label']}"
        st.setdefault("min_people_13",{})[key]=1
        positions,_,_=app._diag_positions_13(st)
        got=[p for p in positions if p["abbr"]==b["abbr"] and p["slot"]=="9/po"]
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]["station"],"A")

    def test_farm_defaults(self):
        cfg=app._farm_config()
        self.assertEqual(cfg["port"],8093)
        self.assertGreaterEqual(cfg["local_workers"],1)
        self.assertLessEqual(cfg["local_workers"],8)
        self.assertIn("workers",repair_farm.status())

    def test_ui_contract(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for phrase in ("Dyżury v5.12","Umożliw pracę zdalnym workerom","nierozstrzygnięte",
                       "To nie jest dowód braku rozwiązania","grupa 1–3 jest zawsze wykluczona",
                       "OSTATNIA MOŻLIWOŚĆ: oczekiwanie"):
            self.assertIn(phrase,h)
        self.assertNotIn("+ 1–3 awaryjnie",h)

if __name__=="__main__": unittest.main(verbosity=2)
