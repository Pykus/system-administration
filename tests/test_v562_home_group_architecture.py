import copy, unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
from constraint_architecture import CONSTRAINT_ARCHITECTURE, VALID_LAYERS, audit_constraint_architecture


class TestHomeGroup562(unittest.TestCase):
    def setUp(self):
        self.state=app.load_state()

    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,62))

    def test_home_group_migrates_to_priority_five_once(self):
        s=copy.deepcopy(self.state)
        s.pop("home_group_v562_migrated",None)
        r=next(x for x in s["global_constraints"] if x.get("key")=="prefer_home_group")
        r.update({"enabled":True,"kind":"soft","priority":3})
        out=app.ensure_state_schema(s)
        rr=app._global_row(out,"prefer_home_group")
        self.assertEqual(rr["priority"],5)
        self.assertTrue(out["home_group_v562_migrated"])
        rr["priority"]=2
        out2=app.ensure_state_schema(out)
        self.assertEqual(app._global_row(out2,"prefer_home_group")["priority"],2)

    def _position_with_home_and_foreign(self):
        s=copy.deepcopy(self.state)
        r=app._global_row(s,"prefer_home_group")
        r.update({"enabled":True,"kind":"soft","priority":5})
        pool=[n for n in app.ALL if n not in set(s.get("excluded_teachers",[]))]
        for pos in app._diag_positions_13(s)[0]:
            legal=app._preflight_teacher_allowed_v524(s,"1-3",pos,pool)
            home=[n for n in legal if app.GROUP.get(n)=="1-3"]
            foreign=[n for n in legal if app.GROUP.get(n)!="1-3"]
            if home and foreign:
                return s,pos,home[0],foreign[0]
        self.fail("No real-state 1-3 position with both home and fallback candidate")

    def test_cp_sat_lexicographic_prefers_home_teacher(self):
        s,pos,home,foreign=self._position_with_home_and_foreign()
        s=app.ensure_state_schema(s)
        key='1-3|'+str(pos.get('station'))
        s['teacher_place_preferences'][home][key]=1.0
        s['teacher_place_preferences'][foreign][key]=0.25
        for r in s['global_constraints']:
            if r.get('kind')=='soft': r['enabled']=False
        s['solver_working_optimize']=False
        a,w,missing,meta=app.solve_positions(s,'1\u20133',[pos],{home,foreign},[],None,coverage_only=True)
        self.assertFalse(missing)
        self.assertEqual(a[0]['teacher'],home)
        d=meta['diagnostics']
        self.assertTrue(d['place_preference_lexicographic'])
        self.assertEqual(d['minimum_place_preference_deficit'],0)
        self.assertFalse(d['home_group_lexicographic'])

    def test_foreign_teacher_remains_valid_fallback(self):
        s,pos,home,foreign=self._position_with_home_and_foreign()
        s=app.ensure_state_schema(s)
        key='1-3|'+str(pos.get('station'))
        s['teacher_place_preferences'][foreign][key]=0.0
        s['solver_working_optimize']=False
        a,w,missing,meta=app.solve_positions(s,'1\u20133',[pos],{foreign},[],None,coverage_only=True)
        self.assertFalse(missing)
        self.assertEqual(a[0]['teacher'],foreign)
        self.assertTrue(meta['diagnostics']['place_preference_lexicographic'])
        self.assertEqual(meta['diagnostics']['minimum_place_preference_deficit'],4)

    def _position_with_home_general_and_wf(self):
        s=copy.deepcopy(self.state)
        r=app._global_row(s,"prefer_home_group")
        r.update({"enabled":True,"kind":"soft","priority":5})
        pool=[n for n in app.ALL if n not in set(s.get("excluded_teachers",[]))]
        for pos in app._diag_positions_13(s)[0]:
            legal=app._preflight_teacher_allowed_v524(s,"1-3",pos,pool)
            home=[n for n in legal if app.GROUP.get(n)=="1-3"]
            general=[n for n in legal if app.GROUP.get(n)=="school"]
            wf=[n for n in legal if app.GROUP.get(n)=="wf"]
            if home and general and wf:
                return s,pos,home[0],general[0],wf[0]
        self.fail("No 1-3 position with all three candidate groups")

    def test_fallback_order_general_before_wf(self):
        s,pos,home,general,wf=self._position_with_home_general_and_wf()
        s=app.ensure_state_schema(s)
        key='1-3|'+str(pos.get('station'))
        s['teacher_place_preferences'][general][key]=0.25
        s['teacher_place_preferences'][wf][key]=0.0
        for r in s['global_constraints']:
            if r.get('kind')=='soft': r['enabled']=False
        s['solver_working_optimize']=False
        a,w,missing,meta=app.solve_positions(s,'1\u20133',[pos],{general,wf},[],None,coverage_only=True)
        self.assertFalse(missing)
        self.assertEqual(a[0]['teacher'],general)
        d=meta['diagnostics']
        self.assertTrue(d['wf_fallback_lexicographic'])
        self.assertEqual(d['minimum_wf_fallback_assignments'],0)

    def test_wf_is_still_valid_last_resort(self):
        s,pos,home,general,wf=self._position_with_home_general_and_wf()
        s=app.ensure_state_schema(s)
        key='1-3|'+str(pos.get('station'))
        s['teacher_place_preferences'][wf][key]=0.0
        s['solver_working_optimize']=False
        a,w,missing,meta=app.solve_positions(s,'1\u20133',[pos],{wf},[],None,coverage_only=True)
        self.assertFalse(missing)
        self.assertEqual(a[0]['teacher'],wf)
        self.assertEqual(meta['diagnostics']['minimum_wf_fallback_assignments'],1)

    def test_quick_draft_never_relaxes_home_group_priority(self):
        import inspect
        src=inspect.getsource(app._quick_draft_v527)
        self.assertNotIn('hardened.add("prefer_home_group")',src)
        self.assertIn('matrix model - 13 first',src)
        self.assertIn('matrix model - school first',src)

    def test_draft_metrics_count_foreign_group(self):
        home=next(n for n in app.ALL if app.GROUP.get(n)=="1-3")
        general=next(n for n in app.ALL if app.GROUP.get(n)=="school")
        wf=next(n for n in app.ALL if app.GROUP.get(n)=="wf")
        ev={"school13":{"assignments":[{"teacher":home,"abbr":"Pn","slot":"1/2"},{"teacher":general,"abbr":"Pn","slot":"2/3"},{"teacher":wf,"abbr":"Pn","slot":"3/4"}],"waits":[]},
            "school":{"assignments":[],"waits":[]}}
        m=app._draft_metrics_v527(ev,[])
        self.assertEqual(m["home_group_foreign_13"],2)
        self.assertEqual(m["home_group_foreign_13_general"],1)
        self.assertEqual(m["home_group_foreign_13_wf"],1)
        self.assertAlmostEqual(m["home_group_foreign_13_share"],2/3,places=4)

    def test_working_ranking_prefers_fewer_13_outsiders_before_fairness(self):
        job={}
        a={"wait_lessons_total":0,"home_group_foreign_13":1,"home_group_foreign_13_wf":0,"home_group_foreign_school":0,
           "fairness_enabled":True,"fairness_normalized_deviation":0.5,"fairness_max_ratio":2,
           "after_last_long":9,"before_first_long":9,"consecutive_pairs":0,"temporary_relaxations_count":4}
        b={**a,"home_group_foreign_13":5,"fairness_normalized_deviation":0.1}
        self.assertLess(app._working_quality_key_v559(a,job),app._working_quality_key_v559(b,job))

    def test_working_ranking_prefers_general_before_wf_when_outsider_count_equal(self):
        job={}
        general={"wait_lessons_total":0,"home_group_foreign_13":2,"home_group_foreign_13_wf":0,"home_group_foreign_school":0,
                 "fairness_enabled":True,"fairness_normalized_deviation":0.5,"fairness_max_ratio":2,
                 "after_last_long":9,"before_first_long":9,"consecutive_pairs":0,"temporary_relaxations_count":4}
        wf={**general,"home_group_foreign_13_wf":2,"fairness_normalized_deviation":0.1}
        self.assertLess(app._working_quality_key_v559(general,job),app._working_quality_key_v559(wf,job))


class TestConstraintArchitecture562(unittest.TestCase):
    def test_registry_exactly_covers_current_global_constraints(self):
        keys={r["key"] for r in app.load_state()["global_constraints"]}
        audit=audit_constraint_architecture(keys)
        self.assertTrue(audit["ok"],audit)
        self.assertEqual(audit["count_actual"],23)

    def test_all_layers_are_known(self):
        for key,row in CONSTRAINT_ARCHITECTURE.items():
            self.assertIn(row["primary_layer"],VALID_LAYERS,key)
            self.assertTrue(set(row.get("supporting_layers",[])).issubset(VALID_LAYERS),key)

    def test_important_constraints_live_in_correct_layer(self):
        self.assertEqual(CONSTRAINT_ARCHITECTURE["no_lesson_overlap"]["primary_layer"],"candidate_filter")
        self.assertEqual(CONSTRAINT_ARCHITECTURE["prefer_home_group"]["primary_layer"],"cp_sat_lexicographic")
        self.assertEqual(CONSTRAINT_ARCHITECTURE["lesson_load_fairness"]["primary_layer"],"cp_sat_soft")
        self.assertEqual(CONSTRAINT_ARCHITECTURE["max_consecutive_duties"]["primary_layer"],"cp_sat_hard")
        self.assertIn("preflight",CONSTRAINT_ARCHITECTURE["after_last_long"]["supporting_layers"])

if __name__=="__main__":
    unittest.main()
