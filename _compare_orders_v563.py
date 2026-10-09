import copy,json,sys,time
sys.path.insert(0,r"C:\DutySolverDemo\dyzury-v5.63-ortools")
import app
s=app.load_state(); base=app.ensure_state_schema(copy.deepcopy(s))
excluded=set(base.get("excluded_teachers",[]))|set(base.get("absent_teachers",[]))
hardened=set(app.HUMAN_REALISM_HARDENED_V560)|{"prefer_home_group","avoid_wait"}
relax_rows=[]; toks=[]
for c in app._repair_candidates(base):
    tok=str(c.get("token") or "")
    if not tok or tok=="g:offday_duty": continue
    if any(app._token_relaxes_rule_v537(tok,k) for k in hardened): continue
    toks.append(tok); relax_rows.append({"token":tok,"label":str(c.get("label") or tok)})
trial=app._relax(base,toks)
trial["solver_seed"]=int(base.get("solver_seed",20260918))+101*101
trial["solver_internal_workers"]=8; trial["solver_coverage_seconds"]=4; trial["solver_coverage_retry_seconds"]=12
trial["solver_working_optimize"]=True; trial["solver_working_optimize_seconds"]=6
trial["solver_weight_overrides"]={"avoid_wait":100_000_000_000_000,"after_last_long":1_000_000_000_000,"before_first_long":10_000_000_000,"max_consecutive_duties":100_000_000,"max_long_day":10_000_000,"max_long_week":1_000_000,"max_week":100_000,"max_day_13":10_000,"max_day_school":10_000}
e13=[n for n in dict.fromkeys(s.get("enabled_teachers_13",[])) if n in app.ALL and n not in excluded]
q13=[n for n in app.ALL if n not in excluded] if not trial.get("freeze_pool_13",False) else e13
es=app._school_pool(s.get("enabled_teachers_school",[]))
qschool=[n for n in app.ALL if n not in excluded and (app.GROUP.get(n)!="1-3" or n in es)] if not trial.get("freeze_pool_school",False) else es
for order in ("13-first","school-first"):
    t=time.time(); ev=app._joint_order_v2(trial,q13,qschool,order,False); m=app._draft_metrics_v527(ev,relax_rows)
    print(json.dumps({"order":order,"seconds":round(time.time()-t,2),"missing":ev["missing"],"after":m["after_last_long"],"before":m["before_first_long"],"wait":m["wait_lessons_total"],"consec":m["consecutive_pairs"],"foreign13":m["home_group_foreign_13"],"wf13":m["home_group_foreign_13_wf"],"d13_min_after":ev["school13"]["diagnostics"].get("minimum_after_last_long"),"school_min_after":ev["school"]["diagnostics"].get("minimum_after_last_long"),"d13_after_status":ev["school13"]["diagnostics"].get("after_last_long_lex_status"),"school_after_status":ev["school"]["diagnostics"].get("after_last_long_lex_status")},ensure_ascii=False))