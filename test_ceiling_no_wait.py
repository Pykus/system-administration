import time,json,collections
import app
s=app.load_state()
e=list(s.get("enabled_teachers_13",[]))
q=app._school_pool(s.get("enabled_teachers_school",[]))
b=app._joint_coverage_v2(s,e,q,False)
c=app._repair_candidates_v2(s,e,q,b)
sel=[]; best={}
for x in c:
    t=x["token"]; st=x["search_stage"]
    if st<=3:
        if t.startswith("gval:") or t.startswith("indval:"):
            best[app._candidate_key_v520(x)]=x
        elif not t.startswith("add13:"):
            sel.append(x)
sel+=list(best.values())
tokens=[x["token"] for x in sel]
t=time.perf_counter()
r=app._eval_combo_deep(s,e,q,tokens)
print(json.dumps({"n_tokens":len(tokens),"missing":r["missing"],"inconclusive":r["inconclusive"],"seconds":round(time.perf_counter()-t,2),"wait_included":"gsoft:avoid_wait" in tokens,"stage_counts":dict(collections.Counter(x["search_stage"] for x in sel))},ensure_ascii=True))
