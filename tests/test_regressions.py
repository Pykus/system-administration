import json
import re
import inspect
import tempfile
import unittest
from pathlib import Path
import copy
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
APP_SOURCE=(ROOT/"app.py").read_text(encoding="utf-8")
FARM_SOURCE=(ROOT/"repair_farm.py").read_text(encoding="utf-8")

class TempStateMixin:
    def setUp(self):
        self.orig_state_path=app.STATE_PATH
        self.tmp=tempfile.TemporaryDirectory()
        self.state_path=Path(self.tmp.name)/"state.json"
        self.state_path.write_text(self.orig_state_path.read_text(encoding="utf-8"),encoding="utf-8")
        app.STATE_PATH=self.state_path
    def tearDown(self):
        app.STATE_PATH=self.orig_state_path
        self.tmp.cleanup()

class TestBackendState(TempStateMixin,unittest.TestCase):
    def test_manual_block_persists_after_reload(self):
        s=app.load_state()
        teacher=next(iter(sorted(app.ALL)))
        s["manual_blocks"]={teacher:["Pn|1/2"]}
        app.save_state(s)
        again=app.load_state()
        self.assertIn("Pn|1/2",app.blockset(again,teacher))

    def test_update_state_manual_block_persists(self):
        teacher=next(iter(sorted(app.ALL)))
        app.update_state({"manual_blocks":{teacher:["Wt|2/3"]}})
        again=app.load_state()
        self.assertEqual(again["manual_blocks"].get(teacher),["Wt|2/3"])

    def test_manual_block_changes_preflight_eligibility(self):
        s=app.load_state()
        found=None
        for br in app.SEED.get("breaks",[]):
            pos={"break":br,"location":"","slot":br["label"],"abbr":br["abbr"]}
            for teacher in sorted(app.ALL):
                allowed=app._preflight_teacher_allowed_v524(s,"1-3",pos,[teacher])
                if teacher in allowed:
                    found=(teacher,br,pos);break
            if found:break
        self.assertIsNotNone(found,"fixture must contain at least one baseline-eligible teacher")
        teacher,br,pos=found
        s.setdefault("manual_blocks",{}).setdefault(teacher,[]).append(br["abbr"]+"|"+br["label"])
        allowed2=app._preflight_teacher_allowed_v524(s,"1-3",pos,[teacher])
        self.assertNotIn(teacher,allowed2)

    def test_avoid_wait_is_normal_configurable_rule(self):
        s=app.load_state()
        row=next(r for r in s["global_constraints"] if r.get("key")=="avoid_wait")
        row["kind"]="soft";row["priority"]=2;row["enabled"]=False
        z=app.ensure_state_schema(copy.deepcopy(s))
        r=next(r for r in z["global_constraints"] if r.get("key")=="avoid_wait")
        self.assertEqual(r["kind"],"soft")
        self.assertEqual(int(r["priority"]),2)
        self.assertFalse(r["enabled"])
        self.assertNotIn("OSTATNIE USTĘPSTWO",str(r.get("label","")))

class TestVariantAndJobLifecycle(TempStateMixin,unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.orig_jobs=app.REPAIR_JOBS
        app.REPAIR_JOBS={}

    def tearDown(self):
        app.REPAIR_JOBS=self.orig_jobs
        super().tearDown()

    def _active_job(self):
        job={"id":"tdd-job","status":"running","_cancel":False,"auto_paused":False}
        app.REPAIR_JOBS[job["id"]]=job
        return job

    def test_loading_variant_invalidates_active_job_and_increments_revision(self):
        s=app.load_state()
        before=int(s.get("plan_revision",0) or 0)
        vid="tdd-variant"
        s.setdefault("variants",[]).append({
            "id":vid,"name":"TDD","school_assignments":copy.deepcopy(s.get("school_assignments",[])),
            "assignments_13":copy.deepcopy(s.get("last_13_assignments",[])),
            "settings":{"min_people_13_stations":{"Pn|1/2|A":1}},
            "global_constraints":copy.deepcopy(s.get("global_constraints",[])),
            "individual_constraints":copy.deepcopy(s.get("individual_constraints",[]))
        })
        app.save_state(s)
        job=self._active_job()
        app.load_variant(vid)
        after=app.load_state()
        self.assertGreater(int(after.get("plan_revision",0) or 0),before)
        self.assertTrue(job.get("stale_due_to_manual_edit"))
        self.assertEqual(job.get("status"),"paused")

    def test_release_local_override_invalidates_active_job(self):
        s=app.load_state()
        teacher=next(iter(sorted(app.ALL)))
        rec={"id":"ov-tdd","active":True,"scope":"szkoła","abbr":"Pn","slot":"1/2",
             "location":"TDD","source_teacher":teacher,"replacement_teacher":teacher}
        s.setdefault("local_repair_overrides",[]).append(rec)
        s.setdefault("manual_blocks",{}).setdefault(teacher,[]).append("Pn|1/2")
        s.setdefault("locked_assignments",[]).append({"scope":"szkoła","abbr":"Pn","slot":"1/2",
             "location":"TDD","teacher":teacher,"override_id":"ov-tdd"})
        app.save_state(s)
        job=self._active_job()
        app.release_local_override("ov-tdd")
        self.assertTrue(job.get("stale_due_to_manual_edit"))
        self.assertEqual(job.get("status"),"paused")

class TestZoneStaffing(TempStateMixin,unittest.TestCase):
    def test_constraint_shortage_never_reduces_required_staffing(self):
        src=inspect.getsource(app._slot_feasibility_v524)
        self.assertNotIn('f"m13:',src)
        self.assertNotIn('f"ms:',src)
        self.assertIn("shortage never reduces required staffing",src)

    def test_late_13_positions_do_not_exist_after_zone_finishes(self):
        s=app.load_state()
        app._apply_timetable_staffing(s)
        for day in ["Pn","Wt","Śr","Czw","Pi"]:
            self.assertEqual(app._required_stations_13(s,day,"8/9"),[])
            self.assertEqual(app._required_stations_13(s,day,"9/po"),[])

    def test_inactive_13_zone_is_persisted_as_zero_staffing(self):
        s=app.load_state()
        app._apply_timetable_staffing(s)
        for b in app.SEED.get("breaks",[]):
            if app._position_zone_active_13(b["abbr"],b["label"]):
                continue
            base=f"{b['abbr']}|{b['label']}"
            self.assertEqual(int(s.get("min_people_13",{}).get(base,0) or 0),0,base)
            for sid in app._stations_13(s):
                key=f"{base}|{sid}"
                self.assertEqual(int(s.get("min_people_13_stations",{}).get(key,0) or 0),0,key)

    def test_auto_staffing_report_contains_explicit_zero_changes(self):
        s=app.load_state()
        s["staffing_zero_overrides"]={"school13":[],"school":[]}
        target=next(b for b in app.SEED.get("breaks",[])
                    if not app._position_zone_active_13(b["abbr"],b["label"]))
        sid=app._stations_13(s)[0]
        key=f"{target['abbr']}|{target['label']}|{sid}"
        s.setdefault("min_people_13_stations",{})[key]=1
        changes=app._apply_timetable_staffing(s)
        zero=[x for x in changes if x.get("after")==0 and x.get("abbr")==target["abbr"]
              and x.get("slot")==target["label"]]
        self.assertTrue(zero)
        self.assertTrue(all(x.get("scope") and x.get("abbr") and x.get("slot")
                            and x.get("location") and x.get("reason") for x in zero))

    def test_inactive_school_zones_are_persisted_as_zero_staffing(self):
        s=app.load_state()
        app._apply_timetable_staffing(s)
        for b in app.SEED.get("breaks",[]):
            for loc in s.get("school_locations",[]):
                zone=app._duty_location_zone(s,loc)
                if not zone or app._position_zone_active_school(s,b["abbr"],b["label"],loc):
                    continue
                key=f"{b['abbr']}|{b['label']}|{loc}"
                self.assertEqual(int(s.get("min_people_school",{}).get(key,0) or 0),0,key)

    def test_special_unmapped_locations_are_not_auto_zeroed(self):
        s=app.load_state()
        before=dict(s.get("min_people_school",{}))
        app._apply_timetable_staffing(s)
        # "wejście" is intentionally special since v5.50 and follows whole-school activity.
        # Other unmapped special places remain controlled manually.
        for loc in ["stołówka","czytelnia"]:
            for k,v in before.items():
                if k.endswith("|"+loc):
                    self.assertEqual(s["min_people_school"].get(k),v)

    def test_preflight_persists_timetable_zero_and_returns_corrected_staffing(self):
        s=app.load_state()
        target=next(b for b in app.SEED.get("breaks",[]) if not app._position_zone_active_13(b["abbr"],b["label"]))
        base=f"{target['abbr']}|{target['label']}"
        order=app._stations_13(s)
        self.assertTrue(order)
        for sid in order:
            s.setdefault("min_people_13_stations",{})[f"{base}|{sid}"]=1
        s.setdefault("min_people_13",{})[base]=len(order)
        app.save_state(s)
        payload={
            "min_people_13":dict(s["min_people_13"]),
            "min_people_13_stations":dict(s["min_people_13_stations"]),
            "min_people_school":dict(s.get("min_people_school",{})),
            "enabled_teachers_13":list(s.get("enabled_teachers_13",[])),
            "enabled_teachers_school":list(s.get("enabled_teachers_school",[])),
        }
        out=app.repair_preflight(payload)
        persisted=app.load_state()
        self.assertEqual(int(persisted["min_people_13"].get(base,0) or 0),0)
        self.assertIn("corrected_staffing",out)
        self.assertEqual(int(out["corrected_staffing"]["min_people_13"].get(base,0) or 0),0)
        self.assertTrue(out.get("auto_staffing_changes"))

class TestFrontendContracts(unittest.TestCase):
    def method_body(self,name):
        m=re.search(r"(?:async\s+)?"+re.escape(name)+r"\([^)]*\)\{",HTML)
        self.assertIsNotNone(m,f"missing frontend method {name}")
        start=m.start()
        nxt=re.search(r"\n(?:async\s+)?[A-Za-z_$][\w$]*\([^)]*\)\{",HTML[m.end():])
        end=m.end()+nxt.start() if nxt else min(len(HTML),m.end()+5000)
        return HTML[start:end]

    def test_save_manual_blocks_invalidates_active_solver(self):
        body=self.method_body("saveManualBlocks")
        self.assertIn("prepareParameterSave",body)
        self.assertIn("finishSolverMutation",body)
        helper=self.method_body("finishSolverMutation")
        self.assertIn("refreshValidation",helper)

    def test_solver_mutating_actions_have_stale_job_guard(self):
        names=[
            "saveManualBlocks","addScopeLock","removeAdminLockRecord",
            "clearTeacherPreference","saveDutyPlaceBasics",
            "addStation13","removeStation13",
            "addSchoolLocation","renameSchoolLocation","removeSchoolLocation",
            "saveSchoolCurrent"
        ]
        bad=[]
        for name in names:
            body=self.method_body(name)
            if "prepareParameterSave" not in body and "commitManualDutyEdit" not in body:
                bad.append(name)
        self.assertEqual(bad,[],f"solver-mutating UI actions without stale-search guard: {bad}")

    def test_critical_buttons_have_handlers(self):
        for handler in ["saveManualBlocks","recalculateAll","saveStation13Staffing","saveSchoolStaffing",
                        "addScopeLock","saveAdvanced","pauseRepair","resumeRepair","cancelRepair"]:
            self.assertRegex(HTML,r"(?:async\s+)?"+re.escape(handler)+r"\([^)]*\)\{")

    def test_critical_api_routes_exist(self):
        routes={getattr(r,"path",None) for r in app.app.routes}
        for path in ["/api/state","/api/min-people-13/stations","/api/min-people-school",
                     "/api/diagnostics/repair/search","/api/plan/manual-cell",
                     "/api/worker-farm/status"]:
            self.assertIn(path,routes)

    def test_no_fake_global_progress_bar(self):
        self.assertNotIn("Jak daleko solver poszedł w kompromisach",HTML)
        self.assertNotIn("ukończone poziomy",HTML)
        self.assertIn("Co wykazały szybkie testy czterech poziomów kompromisu",HTML)

    def test_missing_positions_column_is_last(self):
        head=re.search(r"<table class=\"sheet\"><thead><tr>(.*?)</tr></thead>",HTML,re.S)
        self.assertIsNotNone(head)
        h=head.group(1)
        self.assertIn("Nieobsadzone miejsca",h)
        self.assertGreater(h.find("Nieobsadzone miejsca"),h.find('v-for="t in teachers"'))

    def test_every_simple_click_handler_has_implementation(self):
        handlers=set(re.findall(r'@click(?:\.stop)?=\"([A-Za-z_$][\w$]*)\"',HTML))
        missing=[]
        for h in handlers:
            if not re.search(r"(?:async\s+)?"+re.escape(h)+r"\([^)]*\)\{",HTML):
                missing.append(h)
        self.assertEqual(sorted(missing),[],f"dead simple @click handlers: {missing}")

    def test_worker_online_threshold_matches_30s_polling(self):
        self.assertIn("within=90",APP_SOURCE)
        self.assertIn("def active_workers(version=None,seed_sha=None,within=90)",FARM_SOURCE)

    def test_manual_block_save_has_local_visible_feedback(self):
        self.assertIn("blockSaveMessage",HTML)
        self.assertIn("Niezapisane zmiany — kliknij „Zapisz blokady”",HTML)
        body=self.method_body("saveManualBlocks")
        self.assertIn("blockSaveMessage='✓ Zapisano '",body)

    def test_preflight_shows_timetable_staffing_changes(self):
        self.assertIn("Automatyczna korekta obsady z planu lekcji",HTML)
        self.assertIn("auto_staffing_changes",HTML)
        self.assertIn("wymaganie dyżuru w tej strefie jest ustawiane na 0",HTML)

    def test_frontend_uses_corrected_preflight_staffing_before_search(self):
        body=self.method_body("runRepairPreflight")
        self.assertIn("corrected_staffing",body)
        self.assertIn("minPeople13Stations",body)
        self.assertIn("minPeopleSchool",body)

    def test_avoid_wait_has_no_magic_red_legacy_label(self):
        teacher=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")
        for text in [HTML,teacher]:
            self.assertNotIn("OSTATNIE USTĘPSTWO",text)
            self.assertNotIn("zawsze ostatnie",text.lower())

    def test_break_cells_have_explicit_edit_button(self):
        self.assertIn('class="duty-cell-btn"',HTML)
        self.assertIn("Kliknij, aby zmienić dyżur lub preferencję",HTML)
        self.assertIn("✎",HTML)
        self.assertIn("+ ustaw",HTML)

    def test_variant_save_contains_station_staffing_and_load_uses_job_guard(self):
        body=self.method_body("saveVariant")
        self.assertIn("min_people_13_stations",body)
        load=self.method_body("loadVariant")
        self.assertIn("prepareParameterSave",load)
        self.assertIn("finishSolverMutation",load)

    def test_local_repair_mutations_invalidate_active_solver(self):
        for fn in ["teacher_duty_local_repair_apply","release_local_override"]:
            m=re.search(r"def "+fn+r"\([^)]*\):([\s\S]*?)(?=\n(?:@app\.|def )|\Z)",APP_SOURCE)
            self.assertIsNotNone(m,fn)
            self.assertIn("_invalidate_active_repair_jobs",m.group(1),fn)

    def test_worker_cards_use_current_job_counters_not_history(self):
        self.assertIn("w tym wyszukiwaniu: ukończone",HTML)
        self.assertIn("job_completed",HTML)
        self.assertNotIn("ukończone {{w.completed}}",HTML)

    def test_simple_change_handlers_have_implementation(self):
        handlers=set(re.findall(r'@change=\"([A-Za-z_$][\w$]*)\"',HTML))
        missing=[]
        for h in handlers:
            if not re.search(r"(?:async\s+)?"+re.escape(h)+r"\([^)]*\)\{",HTML):
                missing.append(h)
        self.assertEqual(sorted(missing),[],f"dead simple @change handlers: {missing}")

if __name__=="__main__":
    unittest.main(verbosity=2)
