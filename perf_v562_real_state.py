import json,time,statistics
from pathlib import Path
import app
from constraint_architecture import audit_constraint_architecture

ROOT=Path(__file__).resolve().parent
s=app.load_state()
e13=s.get("enabled_teachers_13",[])
es=s.get("enabled_teachers_school",[])
runs=[]
for seed in (0,17):
    t=time.perf_counter()
    q=app._quick_draft_v527(s,e13,es,[],seed_offset=seed,optimize_seconds=4)
    wall=time.perf_counter()-t
    required13=int((q.get("coverage13") or {}).get("required") or 0)
    foreign13=int(q.get("home_group_foreign_13") or 0)
    general13=int(q.get("home_group_foreign_13_general") or 0)
    wf13=int(q.get("home_group_foreign_13_wf") or 0)
    share=foreign13/max(1,required13)
    wf_share=wf13/max(1,required13)
    runs.append({
        "seed_offset":seed,"wall_s":round(wall,3),
        "full":bool(q.get("full")),"missing":int(q.get("missing") or 0),
        "coverage13":q.get("coverage13"),"coverageSchool":q.get("coverageSchool"),
        "human_guardrail_ok":bool(q.get("human_guardrail_ok")),
        "fairness_normalized_deviation":q.get("fairness_normalized_deviation"),
        "foreign13":foreign13,"foreign13_share":round(share,4),
        "foreign13_general":general13,"foreign13_wf":wf13,"wf13_share":round(wf_share,4),
        "foreign_school":int(q.get("home_group_foreign_school") or 0),
        "max_weekly":q.get("human_max_weekly_duties"),
        "max_daily":q.get("human_max_daily_duties"),
        "longest_consecutive":q.get("human_longest_consecutive_duties"),
    })

keys={r["key"] for r in s.get("global_constraints",[])}
arch=audit_constraint_architecture(keys)
checks={
    "all_full":all(r["full"] and r["missing"]==0 for r in runs),
    "all_human":all(r["human_guardrail_ok"] for r in runs),
    "foreign13_share_le_20pct":all(r["foreign13_share"]<=0.20 for r in runs),
    "wf13_share_le_5pct":all(r["wf13_share"]<=0.05 for r in runs),
    "each_run_le_60s":all(r["wall_s"]<=60 for r in runs),
    "architecture_registry_ok":bool(arch["ok"]),
}
report={
    "version":app.PLANNER_VERSION,"runs":runs,"checks":checks,
    "architecture":arch,
    "summary":{
        "median_wall_s":round(statistics.median(r["wall_s"] for r in runs),3),
        "max_foreign13_share":max(r["foreign13_share"] for r in runs),
        "max_foreign13":max(r["foreign13"] for r in runs),
        "max_wf13":max(r["foreign13_wf"] for r in runs),
        "max_wf13_share":max(r["wf13_share"] for r in runs),
    },
    "ok":all(checks.values()),
}
(ROOT/"PERF-REPORT-v5.62.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=True,indent=2))
raise SystemExit(0 if report["ok"] else 2)
