from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
s=s.replace('version="5.4"','version="5.5"')
s=s.replace('"version":"5.4"','"version":"5.5"')

old='''    state.setdefault("solver_seed",20260918)
    state.setdefault("deterministic_mode",False)
    return state
'''
new='''    try:
        state["solver_seed"]=int(state.get("solver_seed") or 20260918)
    except Exception:
        state["solver_seed"]=20260918
    state.setdefault("deterministic_mode",False)
    return state
'''
assert old in s
s=s.replace(old,new,1)

start=s.index("def _coverage(state,scope,enabled):")
end=s.index('@app.post("/api/diagnostics/repair")',start)
block=r'''def _coverage(state,scope,enabled,other_override=None,preserve_override="DEFAULT",optimize=False):
    if scope=="1–3": positions,other,preserve=_diag_positions_13(state)
    else: positions,other,preserve=_diag_positions_school(state)
    if other_override is not None: other=other_override
    if preserve_override!="DEFAULT": preserve=preserve_override
    a,w,missing,meta=solve_positions(
        state,scope,positions,set(enabled),other,preserve_map=preserve,
        coverage_only=not optimize
    )
    return {"required":len(positions),"filled":len(positions)-len(missing),"missing":len(missing),
            "diagnostics":meta.get("diagnostics",{}),"assignments":a,"waits":w}

def _relax(state,tokens):
    import copy
    out=copy.deepcopy(state)
    for token in tokens:
        if token.startswith("g:"):
            key=token[2:]
            for c in out.get("global_constraints",[]):
                if c.get("key")==key: c["enabled"]=True; c["kind"]="soft"; break
        elif token.startswith("i:"):
            rid=token[2:]
            for c in out.get("individual_constraints",[]):
                if str(c.get("id"))==rid: c["kind"]="soft"; break
    return out

RELAX_COST={
    "max_day_13":260,"max_day_school":260,"max_week":320,
    "max_long_week":420,"max_long_day":520,
    "after_last_short":650,"after_last_long":720,
    "adjacent_lesson":800,"no_before_lesson":850,
    "avoid_wait":1200
}

def _repair_candidates(state):
    out=[]
    for c in state.get("global_constraints",[]):
        if c.get("enabled") and normalize_kind(c.get("kind"))=="hard" and c.get("key") not in FIXED_HARD_KEYS:
            key=c["key"]; pr=normalize_priority(c.get("priority",3))
            out.append({"token":"g:"+key,"label":c.get("label",key),"priority":pr,"type":"global",
                        "human_cost":RELAX_COST.get(key,700)+pr*20})
    for c in state.get("individual_constraints",[]):
        if c.get("enabled",True) and normalize_kind(c.get("kind"))=="hard":
            rid=str(c.get("id") or "")
            if rid:
                pr=normalize_priority(c.get("priority",3))
                out.append({"token":"i:"+rid,"label":f"{c.get('teacher','?')}: {c.get('rule','reguła indywidualna')}",
                            "priority":pr,"type":"individual","human_cost":1000+pr*30})
    return sorted(out,key=lambda x:(x["human_cost"],x["label"]))

def _lesson_items(t):
    for ps in t.get("lessons",{}).values():
        for ls in ps.values():
            for x in ls: yield x

def _teacher13_affinity():
    core=[t for t in SEED["teachers"] if GROUP.get(t["name"])=="1-3"]
    core_classes={str(x.get("class","")).strip() for t in core for x in _lesson_items(t) if str(x.get("class","")).strip()}
    corridor_rooms={str(r) for r in SEED.get("rooms",[])}
    for t in core:
        for x in _lesson_items(t):
            room=str(x.get("room","")).strip()
            if room.isdigit() and 120<=int(room)<=139: corridor_rooms.add(room)
    out={}
    for t in SEED["teachers"]:
        if GROUP.get(t["name"])!="school": continue
        classes=sorted({str(x.get("class","")).strip() for x in _lesson_items(t) if str(x.get("class","")).strip() in core_classes})
        rooms=sorted({str(x.get("room","")).strip() for x in _lesson_items(t) if str(x.get("room","")).strip() in corridor_rooms})
        score=len(classes)*20+len(rooms)*8
        reasons=[]
        if classes: reasons.append("uczy klas 1–3: "+", ".join(classes))
        if rooms: reasons.append("ma zajęcia w salach korytarza 1–3: "+", ".join(rooms))
        out[t["name"]]={"score":score,"reason":"; ".join(reasons)}
    return out

def _flat13_other(assignments):
    return [{"day":a["day"],"abbr":a["abbr"],"slot":a["slot"],"location":"1–3 "+a["station"],"teacher":a["teacher"]}
            for a in assignments if a.get("teacher")]

def _map13_from_state(state):
    m={}
    for r in state.get("last_13_assignments",[]):
        for a in r.get("assignments",[]):
            m["13|"+r["abbr"]+"|"+r["label"]+"|"+a["station"]]=a.get("teacher") or ""
    return m

def _map_school_from_state(state):
    return {"S|"+d["abbr"]+"|"+d["slot"]+"|"+d["location"]:d.get("teacher") or "" for d in state.get("school_assignments",[])}

def _map13_flat(arr):
    return {"13|"+a["abbr"]+"|"+a["slot"]+"|"+a["station"]:a.get("teacher") or "" for a in arr}

def _map_school_flat(arr):
    return {"S|"+a["abbr"]+"|"+a["slot"]+"|"+a["location"]:a.get("teacher") or "" for a in arr}

def _teacher_changes(old_map,new_map):
    from collections import defaultdict
    ch=defaultdict(lambda:{"added":0,"removed":0})
    changed=0
    for k in set(old_map)|set(new_map):
        old=old_map.get(k,""); new=new_map.get(k,"")
        if old==new: continue
        changed+=1
        if old: ch[old]["removed"]+=1
        if new: ch[new]["added"]+=1
    rows=[]
    for name,v in ch.items():
        if v["added"] or v["removed"]:
            rows.append({"teacher":name,**v})
    rows.sort(key=lambda x:x["teacher"])
    return {"positions_changed":changed,"teachers_changed":len(rows),"teachers":rows}

def _joint_rebalance(state,e13,es):
    affinity=_teacher13_affinity()
    core=[n for n in e13 if GROUP.get(n)=="1-3"]
    preferred=[n for n in es if GROUP.get(n)=="school" and affinity.get(n,{}).get("score",0)>0]
    all_general=[n for n in es if GROUP.get(n)=="school"]
    trials=[]
    for label,extras in [("powiązani z klasami/salami 1–3",preferred),("pozostali nauczyciele ogólni",all_general)]:
        pool=list(dict.fromkeys(core+extras))
        if not pool or any(set(pool)==set(x[1]) for x in trials): continue
        trials.append((label,pool))
    for label,pool in trials:
        c13=_coverage(state,"1–3",pool,other_override=[],preserve_override=None,optimize=True)
        if c13["missing"]: continue
        other13=_flat13_other(c13["assignments"])
        school=_coverage(state,"szkoła",es,other_override=other13,optimize=True)
        if school["missing"]: continue
        used_general=sorted({a.get("teacher") for a in c13["assignments"] if a.get("teacher") and GROUP.get(a.get("teacher"))=="school"})
        old={**_map13_from_state(state),**_map_school_from_state(state)}
        new={**_map13_flat(c13["assignments"]),**_map_school_flat(school["assignments"])}
        return {
            "action":"rebalance","coverage":{k:c13[k] for k in ("required","filled","missing")},
            "school_coverage":{k:school[k] for k in ("required","filled","missing")},
            "changes":[],"human_cost":100,
            "title":"Przesuń nauczycieli między planami bez luzowania reguł",
            "explanation":"Najpierw użyto nauczycieli powiązanych z klasami lub salami 1–3; plan całej szkoły został ponownie ułożony wokół tych zmian.",
            "general_teachers":[{"teacher":n,**affinity.get(n,{"score":0,"reason":""})} for n in used_general],
            "teacher_changes":_teacher_changes(old,new),
            "result_13":c13["assignments"],"result_school":school["assignments"]
        }
    return None

def _repair_for_scope(state,scope,enabled,counterpart_enabled=None):
    import itertools
    base=_coverage(state,scope,enabled)
    if base["missing"]==0:
        return {"baseline":{k:base[k] for k in ("required","filled","missing")},"suggestions":[],
                "message":"Pełna obsada jest już możliwa przy obecnych regułach."}
    full=[]
    if scope=="1–3" and counterpart_enabled:
        rb=_joint_rebalance(state,enabled,counterpart_enabled)
        if rb: full.append(rb)
    candidates=_repair_candidates(state)
    tested=[]
    for c in candidates:
        cov=_coverage(_relax(state,[c["token"]]),scope,enabled,optimize=True)
        row={"action":"relax","tokens":[c["token"]],"changes":[c],
             "coverage":{k:cov[k] for k in ("required","filled","missing")},"human_cost":c["human_cost"]}
        if cov["missing"]==0:
            old=_map13_from_state(state) if scope=="1–3" else _map_school_from_state(state)
            new=_map13_flat(cov["assignments"]) if scope=="1–3" else _map_school_flat(cov["assignments"])
            row["teacher_changes"]=_teacher_changes(old,new)
            row["title"]="Zmień jedną regułę"
            row["explanation"]="Pełna obsada po zmianie wskazanej reguły z „Musi być” na „Zalecane”."
            full.append(row)
        tested.append((c,cov))
    if not full:
        best=sorted(tested,key=lambda x:(x[1]["missing"],x[0]["human_cost"]))[:7]
        pool=[x[0] for x in best]
        for a,b in itertools.combinations(pool,2):
            cov=_coverage(_relax(state,[a["token"],b["token"]]),scope,enabled,optimize=True)
            if cov["missing"]: continue
            old=_map13_from_state(state) if scope=="1–3" else _map_school_from_state(state)
            new=_map13_flat(cov["assignments"]) if scope=="1–3" else _map_school_flat(cov["assignments"])
            full.append({"action":"relax","tokens":[a["token"],b["token"]],"changes":[a,b],
                         "coverage":{k:cov[k] for k in ("required","filled","missing")},
                         "human_cost":a["human_cost"]+b["human_cost"],
                         "teacher_changes":_teacher_changes(old,new),
                         "title":"Zmień dwie reguły",
                         "explanation":"Pełna obsada wymaga jednoczesnego złagodzenia dwóch reguł."})
    full.sort(key=lambda x:(0 if x["action"]=="rebalance" else 1,x.get("human_cost",99999),len(x.get("changes",[]))))
    msg=("Pokazuję wyłącznie warianty, które dają pełną obsadę." if full
         else "Nie znalazłem wariantu dającego pełną obsadę. Nie proponuję zmian częściowych.")
    return {"baseline":{k:base[k] for k in ("required","filled","missing")},"suggestions":full[:3],"message":msg}

'''
s=s[:start]+block+s[end:]

old='''    e13=x.get("enabled_teachers_13") or s.get("enabled_teachers_13") or list(ALL)
    es=x.get("enabled_teachers_school") or s.get("enabled_teachers_school") or list(ALL)
    return {"school13":_repair_for_scope(s,"1–3",e13),"school":_repair_for_scope(s,"szkoła",es)}
'''
new='''    e13=x.get("enabled_teachers_13") or s.get("enabled_teachers_13") or list(ALL)
    es=x.get("enabled_teachers_school") or s.get("enabled_teachers_school") or list(ALL)
    return {"school13":_repair_for_scope(s,"1–3",e13,es),"school":_repair_for_scope(s,"szkoła",es,e13)}
'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding="utf-8")

q=Path("solver_ortools.py")
ss=q.read_text(encoding="utf-8")
insert='''\ndef _safe_seed(value):\n    try: return int(value or 20260918)\n    except Exception: return 20260918\n\n'''
needle='''def normalize_priority(value):\n'''
assert needle in ss
ss=ss.replace(needle,insert+needle,1)
ss=ss.replace('s.parameters.random_seed=int(state.get("solver_seed",20260918))','s.parameters.random_seed=_safe_seed(state.get("solver_seed",20260918))')
ss=ss.replace('"solver_seed":int(state.get("solver_seed",20260918))','"solver_seed":_safe_seed(state.get("solver_seed",20260918))')
q.write_text(ss,encoding="utf-8")
print("backend patched")

