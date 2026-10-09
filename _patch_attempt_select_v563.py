from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v5.63-ortools\app.py")
s=p.read_text(encoding="utf-8")
old='''    first=run_attempt("rozszerzona pula 1–3",q13,qschool,"13-first")
    if (first.get("inconclusive") or int(first.get("missing",10**6))>0) and not trial.get("freeze_pool_school",False):
        school_extra=[n for n in ALL if n not in excluded and (GROUP.get(n)!="1-3" or n in base_school)]
        if set(school_extra)!=set(qschool):
            run_attempt("rozszerzona pula 1–3 i szkoły",q13,school_extra,"13-first")
    ev,label,p13,ps,solve_s=min(attempts,key=lambda z:(bool(z[0].get("inconclusive")),int(z[0].get("missing",10**6)),z[4]))
'''
new='''    first=run_attempt("rozszerzona pula 1–3",q13,qschool,"13-first")
    school_extra=qschool
    if not trial.get("freeze_pool_school",False):
        school_extra=[n for n in ALL if n not in excluded and (GROUP.get(n)!="1-3" or n in base_school)]
        if (first.get("inconclusive") or int(first.get("missing",10**6))>0) and set(school_extra)!=set(qschool):
            run_attempt("rozszerzona pula 1–3 i szkoły",q13,school_extra,"13-first")
    # v5.63: the final edge-of-day fallback is expensive and human-sensitive.
    # Compare both decomposition orders with the widest legal school pool instead of
    # accepting whichever full draft happened to finish first.
    if "after_last_long" not in hardened:
        if set(school_extra)!=set(qschool):
            run_attempt("ostatni fallback - 1–3 potem szkoła",q13,school_extra,"13-first")
        run_attempt("ostatni fallback - szkoła potem 1–3",q13,school_extra,"school-first")
    def attempt_quality(z):
        ev0=z[0]
        m=_draft_metrics_v527(ev0,relax_rows)
        return (bool(ev0.get("inconclusive")),int(ev0.get("missing",10**6)),
                int(m.get("wait_lessons_total",10**6) or 0),
                int(m.get("after_last_long",10**6) or 0),
                int(m.get("before_first_long",10**6) or 0),
                int(m.get("consecutive_pairs",10**6) or 0),
                int(m.get("home_group_foreign_13",10**6) or 0),
                int(m.get("home_group_foreign_13_wf",10**6) or 0),
                z[4])
    ev,label,p13,ps,solve_s=min(attempts,key=attempt_quality)
'''
if old not in s:
    raise SystemExit("target block not found")
p.write_text(s.replace(old,new,1),encoding="utf-8")
print("attempt selection patched")