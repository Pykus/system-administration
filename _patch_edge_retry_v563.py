from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v5.63-ortools\solver_ortools.py")
s=p.read_text(encoding="utf-8")
old='''        model.Add(sum(unfilled)==0)
        lex_seconds=5 if coverage_only else 8
        if wait_soft_terms and _priority5_or_teacher_relaxed("avoid_wait"):
'''
new='''        model.Add(sum(unfilled)==0)
        try: lex_seconds=max(3,min(15,float(state.get("solver_edge_lex_seconds",8 if coverage_only else 12) or (8 if coverage_only else 12))))
        except Exception: lex_seconds=8 if coverage_only else 12
        try: lex_retry_seconds=max(lex_seconds,min(30,float(state.get("solver_edge_lex_retry_seconds",20 if coverage_only else 30) or (20 if coverage_only else 30))))
        except Exception: lex_retry_seconds=20 if coverage_only else 30
        def _solve_edge_lex(expr):
            ls=configured_solver(lex_seconds); st=ls.Solve(model); total=ls.WallTime()
            if st==cp_model.UNKNOWN and coverage_only and lex_retry_seconds>lex_seconds:
                ls=configured_solver(lex_retry_seconds); st=ls.Solve(model); total+=ls.WallTime()
            return ls,st,round(total,3)
        if wait_soft_terms and _priority5_or_teacher_relaxed("avoid_wait"):
'''
assert old in s
s=s.replace(old,new,1)
s=s.replace('''            ls=configured_solver(lex_seconds); st=ls.Solve(model)
            wait_lex_status=ls.StatusName(st); wait_lex_wall_time_s=round(ls.WallTime(),3)
''','''            ls,st,wall=_solve_edge_lex(sum(wait_soft_terms))
            wait_lex_status=ls.StatusName(st); wait_lex_wall_time_s=wall
''',1)
s=s.replace('''            ls=configured_solver(lex_seconds); st=ls.Solve(model)
            after_lex_status=ls.StatusName(st); after_lex_wall_time_s=round(ls.WallTime(),3)
''','''            ls,st,wall=_solve_edge_lex(sum(after_last_long_vars))
            after_lex_status=ls.StatusName(st); after_lex_wall_time_s=wall
''',1)
s=s.replace('''            ls=configured_solver(lex_seconds); st=ls.Solve(model)
            before_lex_status=ls.StatusName(st); before_lex_wall_time_s=round(ls.WallTime(),3)
''','''            ls,st,wall=_solve_edge_lex(sum(before_first_long_vars))
            before_lex_status=ls.StatusName(st); before_lex_wall_time_s=wall
''',1)
p.write_text(s,encoding="utf-8")
print("edge retry patched")