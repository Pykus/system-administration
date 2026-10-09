import copy, unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

class TestStaffingActivity550(unittest.TestCase):
    def fresh(self):
        s=copy.deepcopy(app.load_state())
        s["staffing_zero_overrides"]={"school13":[],"school":[]}
        return s

    def test_final_break_after_lesson_is_active_in_13(self):
        br=next(b for b in app.SEED["breaks"] if b["abbr"]=="Wt" and b["label"]=="7/8")
        self.assertTrue(app._zone_ended_lesson_before_break("1-3","Wt","7/8"))
        self.assertTrue(app._position_zone_active_13("Wt","7/8"))

    def test_apply_staffing_keeps_at_least_one_after_final_lesson_all_days_13(self):
        s=self.fresh()
        for b in app.SEED["breaks"]:
            for sid in app._stations_13(s):
                s["min_people_13_stations"][f"{b['abbr']}|{b['label']}|{sid}"]=0
        app._apply_timetable_staffing(s)
        for b in app.SEED["breaks"]:
            if app._zone_ended_lesson_before_break("1-3",b["abbr"],b["label"]):
                total=sum(int(s["min_people_13_stations"].get(f"{b['abbr']}|{b['label']}|{sid}",0) or 0)
                          for sid in app._stations_13(s))
                self.assertGreaterEqual(total,1,(b["abbr"],b["label"]))

    def test_apply_staffing_keeps_at_least_one_after_final_lesson_all_school_zones(self):
        s=self.fresh()
        for b in app.SEED["breaks"]:
            for loc in s.get("school_locations",[]):
                s["min_people_school"][f"{b['abbr']}|{b['label']}|{loc}"]=0
        app._apply_timetable_staffing(s)
        for b in app.SEED["breaks"]:
            for zone in ("ground","floor1","floor2"):
                if not app._zone_ended_lesson_before_break(zone,b["abbr"],b["label"]):
                    continue
                locs=[loc for loc in s.get("school_locations",[]) if app._duty_location_zone(s,loc)==zone]
                if not locs: continue
                total=sum(int(s["min_people_school"].get(f"{b['abbr']}|{b['label']}|{loc}",0) or 0) for loc in locs)
                self.assertGreaterEqual(total,1,(zone,b["abbr"],b["label"],locs))

    def test_entrance_is_required_while_school_day_is_active(self):
        s=self.fresh()
        entrance=next(loc for loc in s.get("school_locations",[]) if str(loc).strip().casefold()=="wejście".casefold())
        for b in app.SEED["breaks"]:
            s["min_people_school"][f"{b['abbr']}|{b['label']}|{entrance}"]=0
        app._apply_timetable_staffing(s)
        for b in app.SEED["breaks"]:
            got=int(s["min_people_school"].get(f"{b['abbr']}|{b['label']}|{entrance}",0) or 0)
            if app._school_activity_at_break(b["abbr"],b["label"]):
                self.assertEqual(got,1,(b["abbr"],b["label"]))
            else:
                self.assertEqual(got,0,(b["abbr"],b["label"]))

    def test_confirmed_zero_override_is_respected(self):
        s=self.fresh()
        keys=[f"Wt|7/8|{sid}" for sid in app._stations_13(s)]
        for k in keys: s["min_people_13_stations"][k]=0
        s["staffing_zero_overrides"]["school13"]=list(keys)
        app._apply_timetable_staffing(s)
        self.assertEqual(sum(int(s["min_people_13_stations"][k]) for k in keys),0)

    def test_zero_warning_requires_explicit_confirmation(self):
        s=self.fresh()
        sid=app._stations_13(s)[0]; key=f"Wt|7/8|{sid}"
        s["min_people_13_stations"][key]=1
        proposal=copy.deepcopy(s["min_people_13_stations"]); proposal[key]=0
        warnings=app._staffing_zero_warnings(s,"school13",proposal)
        self.assertTrue(any(w.get("key")==key for w in warnings),warnings)
        entrance=next(loc for loc in s.get("school_locations",[]) if str(loc).strip().casefold()=="wejście".casefold())
        b=next(x for x in app.SEED["breaks"] if x["abbr"]=="Wt" and app._school_activity_at_break(x["abbr"],x["label"]))
        ek=f"{b['abbr']}|{b['label']}|{entrance}"
        s["min_people_school"][ek]=1
        proposal2=copy.deepcopy(s["min_people_school"]); proposal2[ek]=0
        warnings2=app._staffing_zero_warnings(s,"school",proposal2)
        self.assertTrue(any(w.get("key")==ek for w in warnings2),warnings2)

if __name__=="__main__": unittest.main()
