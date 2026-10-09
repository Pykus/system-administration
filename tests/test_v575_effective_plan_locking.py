import inspect,threading,time,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

class TestEffectivePlanLocking575(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,75))

    def test_public_copy_happens_after_lock_scope(self):
        src=inspect.getsource(app._current_view_job_v573)
        self.assertIn("\n        public=_repair_copy_public(current) if current else None",src)
        self.assertNotIn("\n            public=_repair_copy_public(current) if current else None",src)

    def test_active_job_snapshot_does_not_deadlock(self):
        job={"id":"locktest","status":"running","created_at":"2099-01-01T00:00:00",
             "working_variants":[],"suggestions":[],"_private":{}}
        old=dict(app.REPAIR_JOBS)
        try:
            app.REPAIR_JOBS.clear();app.REPAIR_JOBS[job["id"]]=job
            box={}
            th=threading.Thread(target=lambda:box.setdefault("out",app._current_view_job_v573()),daemon=True)
            th.start();th.join(1.0)
            self.assertFalse(th.is_alive(),"current view job deadlocked on REPAIR_JOB_LOCK")
            self.assertEqual((box.get("out") or {}).get("id"),"locktest")
        finally:
            app.REPAIR_JOBS.clear();app.REPAIR_JOBS.update(old)

if __name__=="__main__":
    unittest.main(verbosity=2)
