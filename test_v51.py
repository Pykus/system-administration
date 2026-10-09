import copy
import unittest
from pathlib import Path

import app

ROOT=Path(__file__).parent

def teacher(name="A",group="1-3",lessons=None):
    return {"name":name,"group":group,"lessons":lessons or {"Pn":{},"Wt":{},"Śr":{},"Czw":{},"Pi":{}}}

def br(abbr,label,prev,next_,minutes=20):
    day={"Pn":"Poniedziałek","Wt":"Wtorek","Śr":"Środa","Czw":"Czwartek","Pi":"Piątek"}[abbr]
    return {"day":day,"abbr":abbr,"label":label,"prev":prev,"next":next_,"minutes":minutes,"time":""}

def position(b,loc):
    return {"day":b["day"],"abbr":b["abbr"],"slot":b["label"],"location":loc,"break":b}

class V51Base(unittest.TestCase):
    def setUp(self):
        self.orig=(app.SEED,app.CORE,app.WF,app.SCHOOL,app.GROUP,app.ALL,app.TBY)
    def tearDown(self):
        app.SEED,app.CORE,app.WF,app.SCHOOL,app.GROUP,app.ALL,app.TBY=self.orig
    def use(self,teachers,breaks):
        app.SEED={"teachers":teachers,"breaks":breaks}
        app.CORE={t["name"] for t in teachers if t.get("group")=="1-3"}
        app.WF={t["name"] for t in teachers if t.get("group")=="wf"}
        app.SCHOOL={t["name"] for t in teachers if t.get("group")=="school"}
        app.GROUP={t["name"]:t.get("group","school") for t in teachers}
        app.ALL={t["name"] for t in teachers}; app.TBY={t["name"]:t for t in teachers}
    def state(self,key,value,kind="hard"):
        s={"global_constraints":[],"individual_constraints":[],"manual_blocks":{}}
        keys=["no_lesson_overlap","one_place_per_slot","cross_scope_conflict","manual_blocks","adjacent_lesson",
              "max_day_13","max_day_school","max_week","avoid_wait","prefer_home_group","preserve_school_current",
              "balance_day","balance_week","long_break_penalty","no_before_lesson","after_last_short","after_last_long","max_long_day","max_long_week"]
        for k in keys:
            s["global_constraints"].append({"key":k,"label":k,"scope":"oba","enabled":k==key,"kind":kind,"priority":3,"value":value if k==key else None})
        return s

class TestLongBreakLimits(V51Base):
    def test_daily_long_break_limit_zero_to_two(self):
        t=teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}],"3":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        bs=[br("Pn","1/2",1,2),br("Pn","2/3",2,3)]
        self.use([t],bs)
        pos=[position(bs[0],"X"),position(bs[1],"Y")]
        s=self.state("max_long_day",1,"hard")
        a,_,m,_=app.solve_positions(s,"1–3",pos,{"A"},[])
        self.assertEqual(sum(1 for x in a if x["teacher"]),1)
        self.assertEqual(len(m),1)
        s=self.state("max_long_day",2,"hard")
        a,_,m,_=app.solve_positions(s,"1–3",pos,{"A"},[])
        self.assertEqual(sum(1 for x in a if x["teacher"]),2)
        self.assertFalse(m)

    def test_weekly_long_break_limit(self):
        t=teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}]},"Wt":{"1":[{}],"2":[{}]},"Śr":{"1":[{}],"2":[{}]},"Czw":{},"Pi":{}})
        bs=[br("Pn","1/2",1,2),br("Wt","1/2",1,2),br("Śr","1/2",1,2)]
        self.use([t],bs)
        pos=[position(b,chr(88+i)) for i,b in enumerate(bs)]
        s=self.state("max_long_week",2,"hard")
        a,_,m,_=app.solve_positions(s,"1–3",pos,{"A"},[])
        self.assertEqual(sum(1 for x in a if x["teacher"]),2)
        self.assertEqual(len(m),1)

class TestDirectionSemantics(V51Base):
    def test_between_two_lessons_is_allowed(self):
        t=teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=br("Pn","1/2",1,2,10); self.use([t],[b])
        s=self.state("no_before_lesson",None,"hard")
        a,_,m,_=app.solve_positions(s,"1–3",[position(b,"X")],{"A"},[])
        self.assertEqual(a[0]["teacher"],"A")
        self.assertFalse(m)

    def test_short_break_after_last_lesson_is_allowed_by_default(self):
        t=teacher("A","1-3",{"Pn":{"1":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=br("Pn","1/2",1,2,10); self.use([t],[b])
        s=self.state("after_last_long",None,"hard")
        a,_,m,_=app.solve_positions(s,"1–3",[position(b,"X")],{"A"},[])
        self.assertEqual(a[0]["teacher"],"A")
        self.assertFalse(m)

    def test_long_break_after_last_lesson_can_be_hard_blocked(self):
        t=teacher("A","1-3",{"Pn":{"1":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=br("Pn","1/2",1,2,20); self.use([t],[b])
        s=self.state("after_last_long",None,"hard")
        a,_,m,_=app.solve_positions(s,"1–3",[position(b,"X")],{"A"},[])
        self.assertIsNone(a[0]["teacher"])
        self.assertEqual(len(m),1)

class TestSchemaAndUI(unittest.TestCase):
    def test_ranges_and_defaults(self):
        s=app.load_state(); by={c["key"]:c for c in s["global_constraints"]}
        self.assertEqual(by["max_long_day"]["value"],1)
        # Bieżąca wartość jest ustawieniem użytkownika; poprawny zakres tygodniowy to 0–10.\n        self.assertTrue(0<=by["max_long_day"]["value"]<=2)
        self.assertTrue(0<=by["max_long_week"]["value"]<=10)
        self.assertTrue(all(c["priority"] in (1,2,3,4,5) for c in s["global_constraints"]))
        self.assertFalse(by["after_last_short"]["enabled"])
        self.assertTrue(by["after_last_long"]["enabled"])
        self.assertEqual(by["after_last_long"]["kind"],"soft")
        self.assertNotIn("no_after_lesson",by)
        for k in ["no_lesson_overlap","one_place_per_slot","cross_scope_conflict","manual_blocks"]:
            self.assertTrue(by[k]["enabled"])
            self.assertEqual(by[k]["kind"],"hard")
    def test_ui_new_tabs_and_no_old_checkboxes(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for x in ["Plany nauczycieli","Diagnostyka","Walidacja","Musi być","Zalecane","dragConstraintStart"]:
            self.assertIn(x,h)
        self.assertNotIn('v-model="f13.allow_wait_one_period"',h)
        self.assertNotIn('v-model="fschool.preserve_current"',h)
    def test_validation_endpoint_logic(self):
        out=app.validate_state(app.load_state(),app.SEED)
        self.assertIn("errors",out); self.assertIn("warnings",out); self.assertIn("problems",out)

if __name__=="__main__":
    unittest.main(verbosity=2)

