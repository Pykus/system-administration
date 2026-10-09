import copy, json, tempfile, unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
from v578_test_fixture import full_snapshot,grouped_13

class TestServerSideInvalidation545(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        td=Path(self.tmp.name)
        self.orig_state=app.STATE_PATH
        self.orig_registry_path=app.TEACHER_REGISTRY_PATH
        self.orig_jobs=app.REPAIR_JOBS
        self.orig_last_good_path=app.LAST_GOOD_PLAN_PATH
        self.last_good_bytes=self.orig_last_good_path.read_bytes() if self.orig_last_good_path.exists() else None
        self.seed_bytes=(ROOT/"data"/"seed.json").read_bytes()
        self.registry_bytes=self.orig_registry_path.read_bytes()
        self.seed_copy=copy.deepcopy(app.SEED)
        self.registry_copy=copy.deepcopy(app.TEACHER_REGISTRY)
        app.STATE_PATH=td/"state.json"
        app.STATE_PATH.write_text(self.orig_state.read_text(encoding="utf-8"),encoding="utf-8")
        app.TEACHER_REGISTRY_PATH=td/"teacher_registry.json"
        app.TEACHER_REGISTRY_PATH.write_bytes(self.registry_bytes)
        app.REPAIR_JOBS={}
        app.LAST_GOOD_PLAN_PATH=td/"last_good_plan.json"
        if self.last_good_bytes is not None:
            app.LAST_GOOD_PLAN_PATH.write_bytes(self.last_good_bytes)

    def tearDown(self):
        app.STATE_PATH=self.orig_state
        app.TEACHER_REGISTRY_PATH=self.orig_registry_path
        app.REPAIR_JOBS=self.orig_jobs
        app.LAST_GOOD_PLAN_PATH=self.orig_last_good_path
        app.SEED.clear(); app.SEED.update(copy.deepcopy(self.seed_copy))
        app.TEACHER_REGISTRY.clear(); app.TEACHER_REGISTRY.update(copy.deepcopy(self.registry_copy))
        (ROOT/"data"/"seed.json").write_bytes(self.seed_bytes)
        self.orig_registry_path.write_bytes(self.registry_bytes)
        app.refresh_teacher_indexes()
        self.tmp.cleanup()

    def active_job(self):
        j={"id":"v545-job","status":"running","_cancel":False,"auto_paused":False}
        app.REPAIR_JOBS[j["id"]]=j
        return j

    def assert_invalidated(self, mutate):
        j=self.active_job()
        mutate()
        self.assertTrue(j.get("stale_due_to_manual_edit"))
        self.assertEqual(j.get("status"),"paused")

    def test_remove_station_invalidates(self):
        def mutate():
            s=app.load_state(); order=app._stations_13(s)
            self.assertGreater(len(order),1)
            app.remove_station_13(order[-1])
        self.assert_invalidated(mutate)

    def test_rename_school_location_invalidates(self):
        def mutate():
            s=app.load_state(); old=s["school_locations"][0]
            app.rename_school_location({"old":old,"new":old+" TDD"})
        self.assert_invalidated(mutate)

    def test_commit_solver_invalidates(self):
        def mutate():
            r13,school,_=full_snapshot(app,app.load_state())
            out=app.commit_solver_plan({"assignments_13":grouped_13(r13),"school_assignments":school})
            self.assertTrue(out["audit"]["ok"])
        self.assert_invalidated(mutate)


    def test_import_plan_invalidates(self):
        def mutate():
            s=app.load_state(); school=copy.deepcopy(s.get("school_assignments",[]))
            self.assertTrue(school)
            school[0]["teacher"]=""
            app.import_source({"school_assignments":school})
        self.assert_invalidated(mutate)

    def test_add_teacher_invalidates(self):
        self.assert_invalidated(lambda: app.add_teacher({"name":"TDD Audit Teacher 545","group":"school"}))

    def test_update_teacher_invalidates(self):
        def mutate():
            name=next(n for n,r in app.TEACHER_REGISTRY.items() if r.get("active",True))
            app.update_teacher({"name":name,"active":False})
        self.assert_invalidated(mutate)

    def test_portal_preferences_invalidates(self):
        def mutate():
            st=app.load_state()
            for name,reg in app.TEACHER_REGISTRY.items():
                token=reg.get("portal_token")
                if not token or not reg.get("active",True): continue
                locked={f"{r.get('abbr')}|{r.get('slot')}" for r in st.get("locked_assignments",[]) if r.get("teacher")==name}
                for br in app.SEED.get("breaks",[]):
                    key=f"{br.get('abbr')}|{br.get('label')}"
                    if key not in locked and st.get("preference_grid",{}).get(name,{}).get(key)!="avoid":
                        order=[x["key"] for x in reversed(app.TEACHER_RELAX_CATALOG)]
                        app.teacher_portal_preferences(token,{"preferences":{key:"avoid"},"relax_order":order})
                        return
            self.fail("no teacher/slot fixture")
        self.assert_invalidated(mutate)

    def test_import_teacher_lessons_invalidates(self):
        def mutate():
            name=next(n for n,r in app.TEACHER_REGISTRY.items() if r.get("active",True))
            payload={"source_name":"TDD 5.45","teachers":[{"name":name,"lessons":{"Pn":{"1":[{"class":"TDD","subject":"TDD","room":"TDD"}]}}}]}
            app.import_teacher_lessons(payload)
        self.assert_invalidated(mutate)

    def test_noop_teacher_update_does_not_invalidate(self):
        name=next(n for n,r in app.TEACHER_REGISTRY.items() if r.get("active",True))
        reg=app.TEACHER_REGISTRY[name]
        j=self.active_job()
        app.update_teacher({"name":name,"active":bool(reg.get("active",True)),"group":reg.get("group","school")})
        self.assertFalse(j.get("stale_due_to_manual_edit"))
        self.assertEqual(j.get("status"),"running")
