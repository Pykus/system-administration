import copy, json, tempfile, unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

class TestLifecycle546(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        td=Path(self.tmp.name)
        self.orig_state=app.STATE_PATH
        self.orig_profiles=app.SETTINGS_PROFILES_PATH
        self.orig_jobs=app.REPAIR_JOBS
        app.STATE_PATH=td/"state.json"
        app.STATE_PATH.write_text(self.orig_state.read_text(encoding="utf-8"),encoding="utf-8")
        app.SETTINGS_PROFILES_PATH=td/"settings_profiles.json"
        if self.orig_profiles.exists():
            app.SETTINGS_PROFILES_PATH.write_bytes(self.orig_profiles.read_bytes())
        app.REPAIR_JOBS={}

    def tearDown(self):
        app.STATE_PATH=self.orig_state
        app.SETTINGS_PROFILES_PATH=self.orig_profiles
        app.REPAIR_JOBS=self.orig_jobs
        self.tmp.cleanup()

    def active_job(self,jid="j546"):
        j={"id":jid,"status":"running","_cancel":False,"auto_paused":False}
        app.REPAIR_JOBS[jid]=j
        return j

    def assert_stale(self,j):
        self.assertTrue(j.get("stale_due_to_manual_edit"))
        self.assertEqual(j.get("status"),"paused")

    def assert_live(self,j):
        self.assertFalse(j.get("stale_due_to_manual_edit"))
        self.assertEqual(j.get("status"),"running")

    def test_operational_absence_change_invalidates(self):
        s=app.load_state()
        teacher=next(iter(sorted(app.ALL)))
        self.assertNotIn(teacher,s.get("absent_teachers",[]))
        j=self.active_job()
        app.save_operational_plan({"absent_teachers":[teacher],"assignments_13":[],"school_assignments":[]})
        self.assert_stale(j)

    def test_operational_metadata_only_does_not_invalidate(self):
        s=app.load_state(); j=self.active_job()
        app.save_operational_plan({"absent_teachers":copy.deepcopy(s.get("absent_teachers",[])),
                                   "assignments_13":[],"school_assignments":[],"stability":{"note":"metadata"}})
        self.assert_live(j)

    def test_preflight_staffing_correction_invalidates(self):
        s=app.load_state()
        target=next(
            (b,loc)
            for b in app.SEED.get("breaks",[])
            for loc in s.get("school_locations",[])
            if not app._position_zone_active_school(s,b["abbr"],b["label"],loc)
        )
        b,loc=target
        key=f"{b['abbr']}|{b['label']}|{loc}"
        s.setdefault("min_people_school",{})[key]=1
        app.save_state(s)
        j=self.active_job()
        app.repair_preflight({
            "min_people_13":dict(s["min_people_13"]),
            "min_people_13_stations":dict(s["min_people_13_stations"]),
            "min_people_school":dict(s.get("min_people_school",{})),
            "enabled_teachers_13":list(s.get("enabled_teachers_13",[])),
            "enabled_teachers_school":list(s.get("enabled_teachers_school",[]))
        })
        self.assert_stale(j)

    def test_preflight_without_persisted_change_does_not_invalidate(self):
        s=app.load_state()
        app._apply_timetable_staffing(s); app.save_state(s)
        j=self.active_job()
        app.repair_preflight({
            "min_people_13":copy.deepcopy(s.get("min_people_13",{})),
            "min_people_13_stations":copy.deepcopy(s.get("min_people_13_stations",{})),
            "min_people_school":copy.deepcopy(s.get("min_people_school",{})),
            "enabled_teachers_13":list(s.get("enabled_teachers_13",[])),
            "enabled_teachers_school":list(s.get("enabled_teachers_school",[]))
        })
        self.assert_live(j)

    def test_apply_repair_suggestion_invalidates_running_jobs(self):
        current=app.load_state()
        changed=copy.deepcopy(current)
        teacher=next(iter(sorted(app.ALL)))
        changed.setdefault("manual_blocks",{}).setdefault(teacher,[]).append("Pn|1/2")
        sug={"id":"s546","_state":changed,
             "_enabled13":list(changed.get("enabled_teachers_13",[])),
             "_enabledSchool":list(changed.get("enabled_teachers_school",[]))}
        j=self.active_job("apply-job")
        j["_private"]={"s546":sug}
        other=self.active_job("other-job")
        app.repair_search_apply("apply-job","s546")
        self.assert_stale(j); self.assert_stale(other)
        self.assertIn("Pn|1/2",app.load_state().get("manual_blocks",{}).get(teacher,[]))

    def test_publish_does_not_invalidate(self):
        j=self.active_job(); app.publish_plan({})
        self.assert_live(j)

    def test_save_variant_does_not_invalidate(self):
        j=self.active_job(); app.save_variant({"name":"metadata-only"})
        self.assert_live(j)

    def test_station_rename_does_not_invalidate(self):
        s=app.load_state(); sid=app._stations_13(s)[0]
        old=s.get("station_names",{}).get(sid,sid)
        j=self.active_job()
        app.rename_station_13(sid,{"name":old+" TDD"})
        self.assert_live(j)

    def test_update_state_station_label_only_does_not_invalidate(self):
        s=app.load_state(); names=copy.deepcopy(s.get("station_names",{})); sid=app._stations_13(s)[0]
        names[sid]=names.get(sid,sid)+" TDD"
        j=self.active_job()
        app.update_state({"station_names":names})
        self.assert_live(j)

class TestSettingsProfiles546(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        td=Path(self.tmp.name)
        self.orig_state=app.STATE_PATH; self.orig_profiles=app.SETTINGS_PROFILES_PATH
        app.STATE_PATH=td/"state.json"; app.STATE_PATH.write_text(self.orig_state.read_text(encoding="utf-8"),encoding="utf-8")
        app.SETTINGS_PROFILES_PATH=td/"settings_profiles.json"

    def tearDown(self):
        app.STATE_PATH=self.orig_state; app.SETTINGS_PROFILES_PATH=self.orig_profiles; self.tmp.cleanup()

    def test_profile_roundtrip_save_export_import_default_delete_persists(self):
        made=app.save_settings_profile({"name":"TDD Profile"})
        pid=made["id"]
        raw=json.loads(app.SETTINGS_PROFILES_PATH.read_text(encoding="utf-8"))
        self.assertTrue(any(p["id"]==pid for p in raw["profiles"]))
        exported=app.export_settings_profile(pid)
        self.assertEqual(exported["schema"],"demo-duty-solver-profile-v1")
        imported=app.import_settings_profile(exported)
        iid=imported["id"]
        app.default_settings_profile(pid)
        reread=json.loads(app.SETTINGS_PROFILES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(reread["default_id"],pid)
        app.delete_settings_profile(iid)
        final=json.loads(app.SETTINGS_PROFILES_PATH.read_text(encoding="utf-8"))
        self.assertFalse(any(p["id"]==iid for p in final["profiles"]))
        self.assertTrue(any(p["id"]==pid for p in final["profiles"]))
