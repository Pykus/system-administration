import app,time,json,traceback
out={}
try:
    s=app.load_state()
    e13=list(s.get("enabled_teachers_13") or app.ALL)
    es=app._school_pool(s.get("enabled_teachers_school") or app.ALL)
    t=time.time()
    q=app._quick_draft_v527(s,e13,es,hardened_keys=[],seed_offset=565,optimize_seconds=8)
    el=app._live_eligibility_v565(q,{"accepted_compromises":[]})
    out={
      "ok": True,
      "elapsed": round(time.time()-t,2),
      "full": bool(q.get("full")),
      "missing": q.get("missing"),
      "coverage13": q.get("coverage13"),
      "coverageSchool": q.get("coverageSchool"),
      "after_last_long": q.get("after_last_long"),
      "after_scope_counts": q.get("after_last_long_scope_counts"),
      "after_proven": q.get("after_last_long_lex_proven"),
      "after_statuses": q.get("after_last_long_lex_statuses"),
      "before_first_long": q.get("before_first_long"),
      "before_scope_counts": q.get("before_first_long_scope_counts"),
      "before_proven": q.get("before_first_long_lex_proven"),
      "before_statuses": q.get("before_first_long_lex_statuses"),
      "human_guardrail_ok": q.get("human_guardrail_ok"),
      "fairness_grossly_unbalanced": q.get("fairness_grossly_unbalanced"),
      "wf13": q.get("home_group_foreign_13_wf"),
      "live_eligibility": el,
    }
except Exception as e:
    out={"ok":False,"error":repr(e),"trace":traceback.format_exc()}
print(json.dumps(out,ensure_ascii=True))
