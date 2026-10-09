import json,sys,time,copy
sys.path.insert(0,r"C:\DutySolverDemo\dyzury-v5.63-ortools")
import app
orig=app._draft_metrics_v527
records=[]
def rec(ev,rels):
    m=orig(ev,rels)
    records.append({"order":ev.get("order"),"missing":ev.get("missing"),"after":m.get("after_last_long"),"before":m.get("before_first_long"),"wait":m.get("wait_lessons_total"),"foreign13":m.get("home_group_foreign_13"),"wf13":m.get("home_group_foreign_13_wf")})
    return m
app._draft_metrics_v527=rec
s=app.load_state(); e13=list(s.get("enabled_teachers_13",[])); es=app._school_pool(s.get("enabled_teachers_school",[]))
q=app._quick_draft_v527(s,e13,es,[],seed_offset=101,optimize_seconds=6)
print(json.dumps({"chosen":{"strategy":q.get("strategy"),"order":q.get("order"),"after":q.get("after_last_long"),"before":q.get("before_first_long"),"wait":q.get("wait_lessons_total"),"foreign13":q.get("home_group_foreign_13"),"wf13":q.get("home_group_foreign_13_wf"),"missing":q.get("missing")},"metric_calls":records},ensure_ascii=False,indent=2))
