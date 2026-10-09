import copy
import json
import unittest
from pathlib import Path

import app

ROOT=Path(__file__).parent

def mk_teacher(name="A",group="1-3",lessons=None):
    return {"name":name,"group":group,"lessons":lessons or {"Pn":{},"Wt":{},"Śr":{},"Czw":{},"Pi":{}}}

def mk_break(abbr="Pn",label="1/2",prev=1,next_=2,minutes=10,period=None):
    day={"Pn":"Poniedziałek","Wt":"Wtorek","Śr":"Środa","Czw":"Czwartek","Pi":"Piątek"}[abbr]
    b={"day":day,"abbr":abbr,"label":label,"prev":prev,"next":next_,"time":"","minutes":minutes}
    if period is not None:
        b["period"]=period
    return b

def pos(br,location="X",station=None):
    x={"day":br["day"],"abbr":br["abbr"],"slot":br["label"],"location":location,"break":br}
    if station is not None:
        x["station"]=station
    return x

GLOBAL_KEYS=[
    "no_lesson_overlap","one_place_per_slot","cross_scope_conflict","manual_blocks",
    "adjacent_lesson","max_day_13","max_day_school","max_week","avoid_wait",
    "prefer_home_group","preserve_school_current","balance_day","balance_week",
    "long_break_penalty","no_before_lesson","after_last_short","after_last_long","max_long_day","max_long_week"
]

def state_with(key=None,kind="hard",value=None,priority=100):
    cs=[]
    for k in GLOBAL_KEYS:
        c={"key":k,"label":k,"scope":"oba","enabled":k==key,"kind":"hard","priority":100,"value":None}
        if k==key:
            c["kind"]=kind
            c["priority"]=priority
            c["value"]=value
        cs.append(c)
    return {
        "global_constraints":cs,
        "individual_constraints":[],
        "manual_blocks":{}
    }

class SyntheticBase(unittest.TestCase):
    def setUp(self):
        self.orig=(app.SEED,app.CORE,app.WF,app.SCHOOL,app.GROUP,app.ALL,app.TBY)

    def tearDown(self):
        app.SEED,app.CORE,app.WF,app.SCHOOL,app.GROUP,app.ALL,app.TBY=self.orig

    def use_teachers(self,teachers):
        app.SEED={"teachers":teachers,"breaks":[]}
        app.CORE={t["name"] for t in teachers if t.get("group")=="1-3"}
        app.WF={t["name"] for t in teachers if t.get("group")=="wf"}
        app.SCHOOL={t["name"] for t in teachers if t.get("group")=="school"}
        app.GROUP={t["name"]:t.get("group","school") for t in teachers}
        app.ALL={t["name"] for t in teachers}
        app.TBY={t["name"]:t for t in teachers}

    def solve(self,state,positions,enabled=None,scope="1–3",other=None,preserve=None):
        enabled=set(enabled or [t["name"] for t in app.SEED["teachers"]])
        return app.solve_positions(state,scope,positions,enabled,other or [],preserve_map=preserve)

    def assert_hard_soft(self,key,positions,teachers,state_value=None,scope="1–3",other=None,preserve=None,
                         hard_filled=0,soft_filled=None,configure=None):
        self.use_teachers(teachers)
        hs=state_with(key,"hard",state_value,100)
        ss=state_with(key,"soft",state_value,100)
        if configure:
            configure(hs); configure(ss)
        ha,hw,hm,hmeta=self.solve(hs,positions,scope=scope,other=other,preserve=preserve)
        sa,sw,sm,smeta=self.solve(ss,positions,scope=scope,other=other,preserve=preserve)
        hf=sum(1 for x in ha if x.get("teacher"))
        sf=sum(1 for x in sa if x.get("teacher"))
        self.assertEqual(hf,hard_filled,(key,"hard",ha,hm,hmeta))
        if soft_filled is None: soft_filled=len(positions)
        self.assertEqual(sf,soft_filled,(key,"soft",sa,sm,smeta))
        self.assertGreaterEqual(smeta["cost"],0)

class TestGlobalConstraints(SyntheticBase):
    def test_no_lesson_overlap_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","during-1",None,None,10,period=1)
        self.assert_hard_soft("no_lesson_overlap",[pos(b)],[t])

    def test_one_place_per_slot_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","1/2",1,2)
        self.assert_hard_soft("one_place_per_slot",[pos(b,"X"),pos(b,"Y")],[t],hard_filled=1,soft_filled=2)

    def test_cross_scope_conflict_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","1/2",1,2)
        other=[{"day":"Poniedziałek","abbr":"Pn","slot":"1/2","location":"Y","teacher":"A"}]
        self.assert_hard_soft("cross_scope_conflict",[pos(b)],[t],other=other)

    def test_manual_blocks_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","1/2",1,2)
        def cfg(s): s["manual_blocks"]={"A":["Pn|1/2"]}
        self.assert_hard_soft("manual_blocks",[pos(b)],[t],configure=cfg)

    def test_adjacent_lesson_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","3/4",3,4)
        self.assert_hard_soft("adjacent_lesson",[pos(b)],[t])

    def test_max_day_13_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}],"3":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        p=[pos(mk_break("Pn","1/2",1,2),"X"),pos(mk_break("Pn","2/3",2,3),"Y")]
        self.assert_hard_soft("max_day_13",p,[t],state_value=1,hard_filled=1,soft_filled=2)

    def test_max_day_school_hard_soft(self):
        t=mk_teacher("A","school",{"Pn":{"1":[{}],"2":[{}],"3":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        p=[pos(mk_break("Pn","1/2",1,2),"X"),pos(mk_break("Pn","2/3",2,3),"Y")]
        self.assert_hard_soft("max_day_school",p,[t],state_value=1,scope="szkoła",hard_filled=1,soft_filled=2)

    def test_max_week_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}]},"Wt":{"1":[{}],"2":[{}]},"Śr":{},"Czw":{},"Pi":{}})
        p=[pos(mk_break("Pn","1/2",1,2),"X"),pos(mk_break("Wt","1/2",1,2),"Y")]
        self.assert_hard_soft("max_week",p,[t],state_value=1,hard_filled=1,soft_filled=2)

    def test_avoid_wait_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","4/5",4,5)
        self.assert_hard_soft("avoid_wait",[pos(b)],[t])

    def test_prefer_home_group_hard_soft(self):
        t=mk_teacher("A","school",{"Pn":{"1":[{}],"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","1/2",1,2)
        self.assert_hard_soft("prefer_home_group",[pos(b)],[t])

    def test_preserve_school_current_hard_soft(self):
        ta=mk_teacher("A","school",{"Pn":{"1":[{}],"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        tb=mk_teacher("B","school",{"Pn":{"1":[{}],"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","1/2",1,2)
        preserve={("Pn","1/2","X"):"B"}
        self.use_teachers([ta,tb])
        hs=state_with("preserve_school_current","hard",None,100)
        ss=state_with("preserve_school_current","soft",None,100)
        ha,_,_,_=self.solve(hs,[pos(b)],enabled={"A"},scope="szkoła",preserve=preserve)
        sa,_,_,sm=self.solve(ss,[pos(b)],enabled={"A"},scope="szkoła",preserve=preserve)
        self.assertIsNone(ha[0]["teacher"])
        self.assertEqual(sa[0]["teacher"],"A")
        self.assertGreaterEqual(sm["cost"],100)

    def test_balance_day_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}],"3":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        p=[pos(mk_break("Pn","1/2",1,2),"X"),pos(mk_break("Pn","2/3",2,3),"Y")]
        self.assert_hard_soft("balance_day",p,[t],hard_filled=1,soft_filled=2)

    def test_balance_week_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}]},"Wt":{"1":[{}],"2":[{}]},"Śr":{},"Czw":{},"Pi":{}})
        p=[pos(mk_break("Pn","1/2",1,2),"X"),pos(mk_break("Wt","1/2",1,2),"Y")]
        self.assert_hard_soft("balance_week",p,[t],hard_filled=1,soft_filled=2)

    def test_long_break_penalty_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","1/2",1,2,minutes=20)
        self.assert_hard_soft("long_break_penalty",[pos(b)],[t],state_value=15)

    def test_no_before_lesson_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","1/2",1,2)
        self.assert_hard_soft("no_before_lesson",[pos(b)],[t])

    def test_after_last_short_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","1/2",1,2,minutes=10)
        self.assert_hard_soft("after_last_short",[pos(b)],[t])

    def test_after_last_long_hard_soft(self):
        t=mk_teacher("A","1-3",{"Pn":{"1":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})
        b=mk_break("Pn","1/2",1,2,minutes=20)
        self.assert_hard_soft("after_last_long",[pos(b)],[t])

class TestIndividualConstraints(SyntheticBase):
    def setUp(self):
        super().setUp()
        self.use_teachers([mk_teacher("A","1-3",{"Pn":{"1":[{}],"2":[{}]},"Wt":{},"Śr":{},"Czw":{},"Pi":{}})])

    def rule(self,typ,kind="hard",**kw):
        r={"id":"x","teacher":"A","scope":"1–3","rule":typ,"kind":kind,"priority":77,"day":"","slot":"","location":"","value":0,"enabled":True}
        r.update(kw)
        return r

    def state(self,r):
        s=state_with()
        s["individual_constraints"]=[r]
        return s

    def assert_effect_rule(self,typ,violation_kwargs):
        rh=self.rule(typ,"hard",**violation_kwargs)
        rs=self.rule(typ,"soft",**violation_kwargs)
        hh,_,_,hc=app.individual_effect(self.state(rh),"A","1–3","Pn","1/2","X")
        sh,_,_,sc=app.individual_effect(self.state(rs),"A","1–3","Pn","1/2","X")
        self.assertTrue(hh,typ)
        self.assertFalse(sh,typ)
        self.assertGreaterEqual(sc,77,typ)

    def test_unavailable_hard_soft(self): self.assert_effect_rule("unavailable",{"day":"Pn","slot":"1/2","location":"X"})
    def test_avoid_slot_hard_soft(self): self.assert_effect_rule("avoid_slot",{"day":"Pn","slot":"1/2"})
    def test_prefer_slot_hard_soft(self): self.assert_effect_rule("prefer_slot",{"day":"Wt","slot":"2/3"})
    def test_avoid_day_hard_soft(self): self.assert_effect_rule("avoid_day",{"day":"Pn"})
    def test_prefer_day_hard_soft(self): self.assert_effect_rule("prefer_day",{"day":"Wt"})
    def test_avoid_location_hard_soft(self): self.assert_effect_rule("avoid_location",{"location":"X"})
    def test_prefer_location_hard_soft(self): self.assert_effect_rule("prefer_location",{"location":"Y"})

    def test_no_before_hard_soft(self):
        h,c=app.directional_individual_effect(self.state(self.rule("no_before_lesson","hard")),"A","1–3","before")
        self.assertTrue(h)
        h,c=app.directional_individual_effect(self.state(self.rule("no_before_lesson","soft")),"A","1–3","before")
        self.assertFalse(h); self.assertEqual(c,77)

    def test_no_after_hard_soft(self):
        h,c=app.directional_individual_effect(self.state(self.rule("no_after_lesson","hard")),"A","1–3","after")
        self.assertTrue(h)
        h,c=app.directional_individual_effect(self.state(self.rule("no_after_lesson","soft")),"A","1–3","after")
        self.assertFalse(h); self.assertEqual(c,77)

    def test_max_day_hard_soft(self):
        h,d,w,c=app.individual_effect(self.state(self.rule("max_day","hard",value=1)),"A","1–3","Pn","1/2","X")
        self.assertEqual(d["kind"],"hard"); self.assertEqual(d["value"],1)
        h,d,w,c=app.individual_effect(self.state(self.rule("max_day","soft",value=1)),"A","1–3","Pn","1/2","X")
        self.assertEqual(d["kind"],"soft"); self.assertEqual(d["priority"],77)

    def test_max_week_hard_soft(self):
        h,d,w,c=app.individual_effect(self.state(self.rule("max_week","hard",value=2)),"A","1–3","Pn","1/2","X")
        self.assertEqual(w["kind"],"hard"); self.assertEqual(w["value"],2)
        h,d,w,c=app.individual_effect(self.state(self.rule("max_week","soft",value=2)),"A","1–3","Pn","1/2","X")
        self.assertEqual(w["kind"],"soft"); self.assertEqual(w["priority"],77)

    def test_require_slot_hard_soft(self):
        sh=self.state(self.rule("require_slot","hard",day="Pn",slot="1/2"))
        ss=self.state(self.rule("require_slot","soft",day="Pn",slot="1/2"))
        self.assertEqual(len(app.required_slot_rules(sh,"1–3","hard")),1)
        self.assertEqual(len(app.required_slot_rules(sh,"1–3","soft")),0)
        self.assertEqual(len(app.required_slot_rules(ss,"1–3","soft")),1)
        self.assertEqual(app.soft_required_penalty(ss,"1–3","Pn","1/2","X","A"),0)
        self.assertEqual(app.soft_required_penalty(ss,"1–3","Pn","1/2","X","B"),77)

class TestRealRegression(unittest.TestCase):
    def test_alicja_kowalska_no_wait(self):
        br=next(b for b in app.SEED["breaks"] if b["abbr"]=="Czw" and b["label"]=="7/8")
        self.assertGreater(app.wait_periods("Alicja Kowalska",br),0)
        st=copy.deepcopy(app.load_state())
        for c in st["global_constraints"]:
            c["enabled"]=False
        avoid=next(c for c in st["global_constraints"] if c["key"]=="avoid_wait")
        avoid["enabled"]=True; avoid["kind"]="hard"
        p=pos(br,"A")
        arr,waits,missing,meta=app.solve_positions(st,"1–3",[p],{"Alicja Kowalska"},[])
        self.assertIsNone(arr[0]["teacher"])
        self.assertEqual(len(missing),1)

class TestSchema(unittest.TestCase):
    def test_every_global_constraint_has_hard_soft_kind(self):
        s=app.load_state()
        self.assertTrue(set(GLOBAL_KEYS).issubset({c["key"] for c in s["global_constraints"]}))
        for c in s["global_constraints"]:
            self.assertIn(c.get("kind"),("hard","soft"),c)
            self.assertIsInstance(c.get("priority"),int,c)

    def test_ui_has_global_kind_selector(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        self.assertIn('<select v-model="c.kind">',h)
        self.assertNotIn("system_hard",h)

if __name__=="__main__":
    unittest.main(verbosity=2)
