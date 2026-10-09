import copy, json, tempfile, unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

class TestServerSideInvalidation544(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        td=Path(self.tmp.name)
        self.orig_state=app.STATE_PATH
        self.orig_profiles=app.SETTINGS_PROFILES_PATH
        self.orig_jobs=app.REPAIR_JOBS
        app.STATE_PATH=td/"state.json"
        app.SETTINGS_PROFILES_PATH=td/"settings_profiles.json"
        app.STATE_PATH.write_text(self.orig_state.read_text(encoding="utf-8"),encoding="utf-8")
        app.REPAIR_JOBS={}

    def tearDown(self):
        app.STATE_PATH=self.orig_state
        app.SETTINGS_PROFILES_PATH=self.orig_profiles
        app.REPAIR_JOBS=self.orig_jobs
        self.tmp.cleanup()

    def active_job(self):
        j={"id":"v544-job","status":"running","_cancel":False,"auto_paused":False}
        app.REPAIR_JOBS[j["id"]]=j
        return j

    def assert_invalidated(self, mutate):
        j=self.active_job()
        mutate()
        self.assertTrue(j.get("stale_due_to_manual_edit"))
        self.assertEqual(j.get("status"),"paused")

    def test_update_state_invalidates(self):
        t=next(iter(sorted(app.ALL)))
        self.assert_invalidated(lambda: app.update_state({"manual_blocks":{t:["Pn|1/2"]}}))

    def test_constraints_invalidates(self):
        def mutate():
            s=app.load_state(); g=copy.deepcopy(s.get("global_constraints",[]))
            row=next(r for r in g if r.get("key")=="avoid_wait")
            row["enabled"]=not bool(row.get("enabled"))
            app.save_constraints({"global":g,"individual":copy.deepcopy(s.get("individual_constraints",[]))})
        self.assert_invalidated(mutate)

    def test_min_people_13_invalidates(self):
        def mutate():
            s=app.load_state(); x=copy.deepcopy(s.get("min_people_13",{})); k=next(iter(x))
            x[k]=0 if int(x[k] or 0) else 1
            app.save_min_people_13({"min_people_13":x})
        self.assert_invalidated(mutate)

    def test_min_people_13_stations_invalidates(self):
        def mutate():
            s=app.load_state(); x=copy.deepcopy(s.get("min_people_13_stations",{}))
            k=next(kk for kk in x if app._position_zone_active_13(*kk.split("|",2)[:2]))
            new=0 if int(x[k] or 0) else 1
            x[k]=new
            payload={"staffing":x}
            if new==0: payload["confirmed_zero_keys"]=[k]
            app.save_min_people_13_stations(payload)
        self.assert_invalidated(mutate)

    def test_min_people_school_invalidates(self):
        def mutate():
            s=app.load_state(); x=copy.deepcopy(s.get("min_people_school",{}))
            k=next((kk for kk,v in x.items() if not int(v or 0)),next(iter(x)))
            new=0 if int(x[k] or 0) else 1
            x[k]=new
            payload={"min_people_school":x}
            if new==0: payload["confirmed_zero_keys"]=[k]
            app.save_min_people_school(payload)
        self.assert_invalidated(mutate)

    def test_station_add_invalidates(self):
        self.assert_invalidated(lambda: app.add_station_13({"name":"TDD 5.44"}))

    def test_school_locations_invalidates(self):
        def mutate():
            s=app.load_state(); x=list(s.get("school_locations",[]))
            x.append("TDD 5.44")
            app.save_school_locations({"locations":x})
        self.assert_invalidated(mutate)

    def test_profile_load_invalidates(self):
        def mutate():
            s=app.load_state(); settings=app._settings_snapshot(s)
            row=next(r for r in settings["global_constraints"] if r.get("key")=="avoid_wait")
            row["enabled"]=not bool(row.get("enabled"))
            app.SETTINGS_PROFILES_PATH.write_text(json.dumps({
                "profiles":[{"id":"tdd-profile","name":"TDD","created_at":"2026-09-21T00:00:00","settings":settings}],
                "default_id":None
            },ensure_ascii=False),encoding="utf-8")
            app.load_settings_profile("tdd-profile")
        self.assert_invalidated(mutate)

    def test_school_current_invalidates(self):
        def mutate():
            s=app.load_state(); arr=copy.deepcopy(s.get("school_assignments",[]))
            if arr:
                arr[0]["teacher"]=""
            else:
                arr=[{"day":"Poniedziałek","abbr":"Pn","slot":"1/2","location":"TDD","teacher":next(iter(sorted(app.ALL)))}]
            app.save_school_current({"assignments":arr})
        self.assert_invalidated(mutate)

    def test_noop_update_state_does_not_invalidate(self):
        s=app.load_state(); j=self.active_job()
        app.update_state({"manual_blocks":copy.deepcopy(s.get("manual_blocks",{}))})
        self.assertFalse(j.get("stale_due_to_manual_edit"))
        self.assertEqual(j.get("status"),"running")
