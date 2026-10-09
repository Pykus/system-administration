from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v5.63-ortools\solver_ortools.py")
s=p.read_text(encoding="utf-8")
old='home_mismatch_vars=[]; wf_fallback_13_vars=[]'
new='home_mismatch_vars=[]; wf_fallback_13_vars=[]; after_last_long_vars=[]; before_first_long_vars=[]; wait_soft_terms=[]'
assert old in s
s=s.replace(old,new,1)
old='reasons=[]; cost=0'
new='reasons=[]; cost=0; before_long_soft=False; after_long_soft=False; wait_soft_mult=0'
assert old in s
s=s.replace(old,new,1)
old='''                if _teacher_mode(cs,state,n,key)=="hard": reasons.append(label)
                elif _teacher_mode(cs,state,n,key)=="soft": cost+=_weight(state,key,1 if edge_is_short else 5)
            if after_last:
'''
new='''                if _teacher_mode(cs,state,n,key)=="hard": reasons.append(label)
                elif _teacher_mode(cs,state,n,key)=="soft":
                    cost+=_weight(state,key,1 if edge_is_short else 5)
                    if key=="before_first_long": before_long_soft=True
            if after_last:
'''
assert old in s
s=s.replace(old,new,1)
old='''                if _teacher_mode(cs,state,n,key)=="hard": reasons.append(label)
                elif _teacher_mode(cs,state,n,key)=="soft": cost+=_weight(state,key,1 if edge_is_short else 5)
            wait=_wait(tby,n,br)
'''
new='''                if _teacher_mode(cs,state,n,key)=="hard": reasons.append(label)
                elif _teacher_mode(cs,state,n,key)=="soft":
                    cost+=_weight(state,key,1 if edge_is_short else 5)
                    if key=="after_last_long": after_long_soft=True
            wait=_wait(tby,n,br)
'''
assert old in s
s=s.replace(old,new,1)
old='''                if _teacher_mode(cs,state,n,"avoid_wait")=="hard": reasons.append("wymaga dodatkowego oczekiwania")
                elif _teacher_mode(cs,state,n,"avoid_wait")=="soft": cost+=_weight(state,"avoid_wait",5)*wait
'''
new='''                if _teacher_mode(cs,state,n,"avoid_wait")=="hard": reasons.append("wymaga dodatkowego oczekiwania")
                elif _teacher_mode(cs,state,n,"avoid_wait")=="soft":
                    cost+=_weight(state,"avoid_wait",5)*wait
                    wait_soft_mult=wait
'''
assert old in s
s=s.replace(old,new,1)
old='''            var=model.NewBoolVar(f"x_{pi}_{ti}"); x[(pi,n)]=var; candidate_cost[(pi,n)]=cost; wait_meta[(pi,n)]=wait
            if home_mismatch:
'''
new='''            var=model.NewBoolVar(f"x_{pi}_{ti}"); x[(pi,n)]=var; candidate_cost[(pi,n)]=cost; wait_meta[(pi,n)]=wait
            if after_long_soft: after_last_long_vars.append(var)
            if before_long_soft: before_first_long_vars.append(var)
            if wait_soft_mult: wait_soft_terms.append(wait_soft_mult*var)
            if home_mismatch:
'''
assert old in s
s=s.replace(old,new,1)
marker='''    home_group_optimized=False; best_home_mismatches=None; home_group_status=None; home_group_wall_time_s=None
    wf_fallback_optimized=False; best_wf_fallback_13=None; wf_fallback_status=None; wf_fallback_wall_time_s=None
'''
insert='''    home_group_optimized=False; best_home_mismatches=None; home_group_status=None; home_group_wall_time_s=None
    wf_fallback_optimized=False; best_wf_fallback_13=None; wf_fallback_status=None; wf_fallback_wall_time_s=None
    wait_lex_optimized=False; best_wait_soft=None; wait_lex_status=None; wait_lex_wall_time_s=None
    after_lex_optimized=False; best_after_last_long=None; after_lex_status=None; after_lex_wall_time_s=None
    before_lex_optimized=False; best_before_first_long=None; before_lex_status=None; before_lex_wall_time_s=None

    def _priority5_or_teacher_relaxed(key):
        row=cs.get(key,{})
        global_soft=(_mode(cs,key)=="soft" and normalize_priority(row.get("priority",3))>=5)
        teacher_soft=any(key in set(v or []) for v in (state.get("teacher_relaxed_rules",{}) or {}).values())
        return global_soft or teacher_soft

    if phase1_ok and best_missing==0 and not repair_mode:
        model.Add(sum(unfilled)==0)
        lex_seconds=5 if coverage_only else 8
        if wait_soft_terms and _priority5_or_teacher_relaxed("avoid_wait"):
            model.Minimize(sum(wait_soft_terms))
            ls=configured_solver(lex_seconds); st=ls.Solve(model)
            wait_lex_status=ls.StatusName(st); wait_lex_wall_time_s=round(ls.WallTime(),3)
            if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                best_wait_soft=sum(ls.Value(v) for v in wait_soft_terms)
                model.Add(sum(wait_soft_terms)==best_wait_soft)
                solver=ls; status=st; wait_lex_optimized=True
        if after_last_long_vars and _priority5_or_teacher_relaxed("after_last_long"):
            model.Minimize(sum(after_last_long_vars))
            ls=configured_solver(lex_seconds); st=ls.Solve(model)
            after_lex_status=ls.StatusName(st); after_lex_wall_time_s=round(ls.WallTime(),3)
            if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                best_after_last_long=sum(ls.Value(v) for v in after_last_long_vars)
                model.Add(sum(after_last_long_vars)==best_after_last_long)
                solver=ls; status=st; after_lex_optimized=True
        if before_first_long_vars and _priority5_or_teacher_relaxed("before_first_long"):
            model.Minimize(sum(before_first_long_vars))
            ls=configured_solver(lex_seconds); st=ls.Solve(model)
            before_lex_status=ls.StatusName(st); before_lex_wall_time_s=round(ls.WallTime(),3)
            if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                best_before_first_long=sum(ls.Value(v) for v in before_first_long_vars)
                model.Add(sum(before_first_long_vars)==best_before_first_long)
                solver=ls; status=st; before_lex_optimized=True
'''
assert marker in s
s=s.replace(marker,insert,1)
diag='''                 "wf_fallback_13_status":wf_fallback_status,"wf_fallback_13_wall_time_s":wf_fallback_wall_time_s,
                 "soft_optimized":soft_optimized,"mpp_optimized":mpp_optimized,"minimum_changes_found":best_changes,
'''
diagnew='''                 "wf_fallback_13_status":wf_fallback_status,"wf_fallback_13_wall_time_s":wf_fallback_wall_time_s,
                 "wait_lexicographic":wait_lex_optimized,"minimum_wait_soft_periods":best_wait_soft,
                 "wait_lex_status":wait_lex_status,"wait_lex_wall_time_s":wait_lex_wall_time_s,
                 "after_last_long_lexicographic":after_lex_optimized,"minimum_after_last_long":best_after_last_long,
                 "after_last_long_lex_status":after_lex_status,"after_last_long_lex_wall_time_s":after_lex_wall_time_s,
                 "before_first_long_lexicographic":before_lex_optimized,"minimum_before_first_long":best_before_first_long,
                 "before_first_long_lex_status":before_lex_status,"before_first_long_lex_wall_time_s":before_lex_wall_time_s,
                 "soft_optimized":soft_optimized,"mpp_optimized":mpp_optimized,"minimum_changes_found":best_changes,
'''
assert diag in s
s=s.replace(diag,diagnew,1)
p.write_text(s,encoding="utf-8")
print("edge lex patched")