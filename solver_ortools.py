from collections import Counter, defaultdict
from ortools.sat.python import cp_model

PRIORITY_BASE={1:100,2:10_000,3:1_000_000,4:100_000_000,5:10_000_000_000}
SHORT_BREAK_MAX_MINUTES=10
LONG_BREAK_MINUTES=11


def _safe_seed(value):
    try: return int(value or 20260918)
    except Exception: return 20260918

def normalize_priority(value):
    try: v=int(value)
    except Exception: return 3
    if 1 <= v <= 5: return v
    if v >= 50_000: return 5
    if v >= 5_000: return 4
    if v >= 500: return 3
    if v >= 50: return 2
    return 1

def _kind(row):
    return "hard" if str(row.get("kind","soft")).lower() in ("hard","system_hard") else "soft"

def _cmap(state):
    return {c["key"]:c for c in state.get("global_constraints",[])}

def _enabled(cs,key):
    return bool(cs.get(key,{}).get("enabled",False))

def _mode(cs,key):
    c=cs.get(key,{})
    return _kind(c) if c.get("enabled",False) else "off"

def _teacher_mode(cs,state,teacher,key):
    mode=_mode(cs,key)
    if mode=="hard" and key in set((state.get("teacher_relaxed_rules",{}) or {}).get(teacher,[]) or []):
        return "soft"
    return mode

def _value(cs,key,default=None):
    c=cs.get(key,{})
    return c.get("value",default) if c.get("enabled",False) else default

def _weight(state,key,default_level=3):
    try:
        ov=state.get("solver_weight_overrides",{})
        if key in ov:return max(0,int(ov[key]))
    except Exception:pass
    rows=state.get("global_constraints",[])
    for idx,c in enumerate(rows):
        if c.get("key")==key:
            level=normalize_priority(c.get("priority",default_level))
            return PRIORITY_BASE[level] + max(0,len(rows)-idx)
    return PRIORITY_BASE[default_level]

def _lesson_periods(tby,name,abbr):
    return {int(p) for p in tby[name].get("lessons",{}).get(abbr,{})}

def _is_opening_break(br):
    try:
        return (str(br.get("label") or "").strip()=="0/1"
                and int(br.get("prev"))==0 and int(br.get("next"))==1
                and int(br.get("minutes",0) or 0)<=5)
    except Exception:
        return False

def _opening_teacher_allowed(tby,name,br):
    if not _is_opening_break(br): return True
    try: return int(br.get("next")) in _lesson_periods(tby,name,br["abbr"])
    except Exception: return False

def _is_before_first_lesson(tby,name,br):
    if _is_opening_break(br): return False
    ps=_lesson_periods(tby,name,br["abbr"])
    nxt=br.get("next")
    return bool(ps and nxt in ps and int(nxt)==min(ps))

def _is_after_last_lesson(tby,name,br):
    ps=_lesson_periods(tby,name,br["abbr"])
    prev=br.get("prev")
    return bool(ps and prev in ps and int(prev)==max(ps))

def _lesson_count(tby,name):
    return sum(len(periods or {}) for periods in tby.get(name,{}).get("lessons",{}).values())

def _relation(tby,name,br):
    ps=_lesson_periods(tby,name,br["abbr"])
    hp=br.get("prev") in ps
    hn=br.get("next") in ps
    if hp and hn: return "between"
    if hn: return "before"
    if hp: return "after"
    if br.get("next") is None and br.get("prev") and br["prev"]-1 in ps: return "wait_after"
    return "none"

def _wait(tby,name,br):
    ps=sorted(_lesson_periods(tby,name,br["abbr"]))
    # Internal penalty sentinel for assigning a duty on a day with no lessons.
    # UI treats this separately as "przyjazd tylko na dyżur", not 9 lessons waiting.
    if not ps: return 9
    prev,nxt=br.get("prev"),br.get("next")
    if prev in ps or nxt in ps: return 0
    dist=[]
    if prev is not None:
        a=[p for p in ps if p<=prev]
        if a: dist.append(max(0,int(prev)-max(a)))
    if nxt is not None:
        a=[p for p in ps if p>=nxt]
        if a: dist.append(max(0,min(a)-int(nxt)))
    if dist: return min(dist)
    if prev is not None and max(ps)<prev: return max(1,int(prev)-max(ps))
    if nxt is not None and min(ps)>nxt: return max(1,min(ps)-int(nxt))
    return 9

def _wait_kind(tby,name,br):
    ps=sorted(_lesson_periods(tby,name,br["abbr"]))
    if not ps: return "offday"
    return "gap" if _wait(tby,name,br)>0 else ""

def _overlap(tby,name,br):
    p=br.get("period")
    if p is None: return False
    try: return int(p) in _lesson_periods(tby,name,br["abbr"])
    except Exception: return False

def _preference_effect(state,name,abbr,slot):
    prefs=state.get("preference_grid",{}).get(name,{})
    value=str(prefs.get(f"{abbr}|{slot}","neutral")).lower()
    if value=="avoid": return False,4
    if value=="prefer": return False,0
    return False,(1 if "prefer" in prefs.values() else 0)

def _room_zone(tby,name,abbr,period):
    if period is None: return None
    vals=tby[name].get("lessons",{}).get(abbr,{}).get(str(period),[])
    for v in vals:
        room=str(v.get("room",""))
        for ch in room:
            if ch.isdigit(): return ch
    return None

def _zone_distance(state,tby,name,scope,br,location):
    zones=state.get("location_zones",{})
    duty=zones.get(f"{scope}|{location}") or zones.get(str(location))
    if not duty:
        raw=str(location or "")
        duty=next((ch for ch in raw if ch.isdigit()),None)
    if not duty: return 0
    lesson_zones=[]
    for p in (br.get("prev"),br.get("next")):
        z=_room_zone(tby,name,br["abbr"],p)
        if z: lesson_zones.append(z)
    if not lesson_zones: return 0
    distances=[]
    for z in lesson_zones:
        try: distances.append(abs(int(duty)-int(z)))
        except Exception: distances.append(0 if str(duty)==str(z) else 1)
    return max(distances or [0])

def _active_individual(state,name,scope):
    for r in state.get("individual_constraints",[]):
        if not r.get("enabled",True) or r.get("teacher")!=name: continue
        if r.get("scope","oba") not in ("oba",scope): continue
        yield r

def _individual_effect(state,name,scope,abbr,slot,location):
    hard=[]; cost=0
    for r in _active_individual(state,name,scope):
        typ=r.get("rule"); mode=_kind(r)
        level=normalize_priority(r.get("priority",3))
        w=PRIORITY_BASE[level]
        day,sl,loc=r.get("day"),r.get("slot"),r.get("location")
        md=(not day or day==abbr); ms=(not sl or sl==slot); ml=(not loc or loc==location)
        hit=False
        if typ=="unavailable": hit=md and ms and ml
        elif typ=="avoid_slot": hit=md and ms
        elif typ=="prefer_slot": hit=not (md and ms)
        elif typ=="avoid_day": hit=md
        elif typ=="prefer_day": hit=bool(day and day!=abbr)
        elif typ=="avoid_location": hit=ml
        elif typ=="prefer_location": hit=bool(loc and loc!=location)
        if hit:
            if mode=="hard": hard.append("reguła indywidualna: "+typ)
            else: cost+=w
    return hard,cost

def _individual_direction(state,name,scope,before_first,after_last):
    hard=[]; cost=0
    for r in _active_individual(state,name,scope):
        typ=r.get("rule")
        hit=(typ in ("no_before_first_lesson","no_before_lesson") and before_first) or (typ in ("no_after_last_lesson","no_after_lesson") and after_last)
        if not hit: continue
        if _kind(r)=="hard": hard.append("reguła indywidualna: "+typ)
        else: cost+=PRIORITY_BASE[normalize_priority(r.get("priority",3))]
    return hard,cost

def _limit_for(state,name,scope,typ,day=None):
    found=None
    for r in _active_individual(state,name,scope):
        if r.get("rule")!=typ: continue
        if typ=="max_day" and r.get("day") and r.get("day")!=day: continue
        try: value=max(0,int(r.get("value") or 0))
        except Exception: value=0
        found={"value":value,"kind":_kind(r),"weight":PRIORITY_BASE[normalize_priority(r.get("priority",3))]}
    return found

def _soft_required_cost(state,scope,abbr,slot,location,candidate):
    cost=0
    for r in state.get("individual_constraints",[]):
        if not r.get("enabled",True) or r.get("rule")!="require_slot" or _kind(r)!="soft": continue
        if r.get("scope","oba") not in ("oba",scope): continue
        if r.get("day") and r.get("day")!=abbr: continue
        if r.get("slot") and r.get("slot")!=slot: continue
        if r.get("location") and r.get("location")!=location: continue
        if r.get("teacher")!=candidate:
            cost+=PRIORITY_BASE[normalize_priority(r.get("priority",3))]
    return cost

def _base_counts(assignments,breaks):
    day=Counter(); week=Counter(); lday=Counter(); lweek=Counter()
    bmap={(b["abbr"],b["label"]):b for b in breaks}
    for d in assignments:
        n=d.get("teacher")
        if not n: continue
        ab=d["abbr"]; day[(n,ab)]+=1; week[n]+=1
        br=bmap.get((ab,d["slot"]))
        if br and int(br.get("minutes",0) or 0)>=LONG_BREAK_MINUTES:
            lday[(n,ab)]+=1; lweek[n]+=1
    return day,week,lday,lweek

def _add_overflow(model,total,limit,ub,name):
    ov=model.NewIntVar(0,max(0,ub),name)
    model.Add(ov>=total-limit)
    return ov

def solve_positions_ortools(state,scope,positions,enabled,other_assignments,preserve_map,seed,group,coverage_only=False,repair_mode=False):
    teachers=seed["teachers"]; tby={t["name"]:t for t in teachers}; cs=_cmap(state)
    base_day,base_week,base_lday,base_lweek=_base_counts(other_assignments,seed.get("breaks",[]))
    other_idx=defaultdict(list); base_slot=Counter(); base_opening=Counter()
    break_by_key={(b.get("abbr"),b.get("label")):b for b in seed.get("breaks",[])}
    for d in other_assignments:
        if d.get("teacher"):
            other_idx[(d["teacher"],d["abbr"],d["slot"])].append(d.get("location",""))
            base_slot[(d["teacher"],d["abbr"],d["slot"])]+=1
            b0=break_by_key.get((d.get("abbr"),d.get("slot")))
            if b0 and _is_opening_break(b0): base_opening[d["teacher"]]+=1
    model=cp_model.CpModel(); objective=[]; x={}; candidate_cost={}; wait_meta={}; rejected=defaultdict(Counter)
    home_mismatch_vars=[]; wf_fallback_vars=[]; place_preference_terms=[]; after_last_long_vars=[]; before_first_long_vars=[]; wait_soft_terms=[]
    contract_only=bool(state.get("solver_contract_only",False))
    matrix_rule=cs.get("prefer_home_group",{}) or {}
    matrix_enabled=bool(matrix_rule.get("enabled",False))
    matrix_priority=normalize_priority(matrix_rule.get("priority",5))
    matrix_lexicographic=(not contract_only) and matrix_enabled and _kind(matrix_rule)=="soft" and matrix_priority>=5
    by_teacher_day=defaultdict(list); by_teacher_week=defaultdict(list); by_teacher_slot=defaultdict(list)
    by_long_day=defaultdict(list); by_long_week=defaultdict(list); by_opening_week=defaultdict(list)
    unfilled=[]; change_vars=[]; change_refs=[]
    long_threshold=LONG_BREAK_MINUTES

    def reject(pi,reason): rejected[pi][reason]+=1

    for pi,p in enumerate(positions):
        br=p["break"]; ab=br["abbr"]; sl=br["label"]; loc=p.get("location") or p.get("station")
        required=p.get("required_teacher")
        place_scope="1-3" if scope in ("1-3","1\u20133") else "school"
        place_key=f"{place_scope}|{loc}"
        place_meta=next((z for z in (state.get("duty_places",[]) or []) if z.get("key")==place_key),{})
        group_defaults=state.get("group_place_defaults",{}) or {}
        allowed_groups={g for g in ("1-3","school","wf") if place_key in set(group_defaults.get(g,[]) or [])}
        excluded=set(state.get("excluded_teachers",[]))
        for ti,t in enumerate(teachers):
            n=t["name"]
            if required and n!=required: continue
            if n in excluded:
                reject(pi,"wykluczony ze wszystkich dyżurów")
                continue
            if n not in enabled:
                reject(pi,"poza wybraną pulą nauczycieli")
                continue
            reasons=[]; cost=0; before_long_soft=False; after_long_soft=False; wait_soft_mult=0
            if n in set(state.get("active_absences",[])): reasons.append("nieobecność")
            blocked_key=ab+"|"+sl
            if blocked_key in set(state.get("manual_blocks",{}).get(n,[])):
                if _mode(cs,"manual_blocks")=="hard": reasons.append("ręczna blokada")
                elif _mode(cs,"manual_blocks")=="soft": cost+=_weight(state,"manual_blocks",5)
            if other_idx.get((n,ab,sl)):
                if _mode(cs,"cross_scope_conflict")=="hard": reasons.append("kolizja 1–3 / szkoła")
                elif _mode(cs,"cross_scope_conflict")=="soft": cost+=_weight(state,"cross_scope_conflict",5)
            if _overlap(tby,n,br):
                if _mode(cs,"no_lesson_overlap")=="hard": reasons.append("kolizja z lekcją")
                elif _mode(cs,"no_lesson_overlap")=="soft": cost+=_weight(state,"no_lesson_overlap",5)
            ih,ic=_individual_effect(state,n,scope,ab,sl,loc); reasons.extend(ih); cost+=ic
            rel=_relation(tby,n,br)
            minutes=int(br.get("minutes",0) or 0)
            is_long=minutes>=long_threshold
            edge_is_short=minutes<=SHORT_BREAK_MAX_MINUTES
            opening=_is_opening_break(br)
            if opening and not _opening_teacher_allowed(tby,n,br):
                reasons.append("slot 0/1 — nauczyciel nie ma lekcji na 1. godzinie")
            before_first=_is_before_first_lesson(tby,n,br)
            after_last=_is_after_last_lesson(tby,n,br)
            dh,dc=_individual_direction(state,n,scope,before_first,after_last); reasons.extend(dh); cost+=dc
            if before_first:
                key="before_first_short" if edge_is_short else "before_first_long"
                label="krótka przerwa 5-10 min przed pierwszą lekcją" if edge_is_short else "przerwa >10 min przed pierwszą lekcją"
                if _teacher_mode(cs,state,n,key)=="hard": reasons.append(label)
                elif _teacher_mode(cs,state,n,key)=="soft":
                    cost+=_weight(state,key,1 if edge_is_short else 5)
                    if key=="before_first_long": before_long_soft=True
            if after_last:
                key="after_last_short" if edge_is_short else "after_last_long"
                label="krótka przerwa 5-10 min po ostatniej lekcji" if edge_is_short else "przerwa >10 min po ostatniej lekcji"
                if _teacher_mode(cs,state,n,key)=="hard": reasons.append(label)
                elif _teacher_mode(cs,state,n,key)=="soft":
                    cost+=_weight(state,key,1 if edge_is_short else 5)
                    if key=="after_last_long": after_long_soft=True
            wait=_wait(tby,n,br)
            wait_kind=_wait_kind(tby,n,br)
            if wait_kind=="offday":
                if _mode(cs,"offday_duty")=="hard": reasons.append("dzień bez lekcji — przyjazd tylko na dyżur")
                elif _mode(cs,"offday_duty")=="soft": cost+=_weight(state,"offday_duty",50)*50
            elif wait>0:
                # Niezależnie od ustawienia avoid_wait, oczekiwanie >=2 okresy
                # jest niedopuszczalne i kandydat nie może wejść do modelu.
                if wait>=2: reasons.append("wymaga oczekiwania co najmniej 2 godzin")
                if _teacher_mode(cs,state,n,"avoid_wait")=="hard": reasons.append("wymaga dodatkowego oczekiwania")
                elif _teacher_mode(cs,state,n,"avoid_wait")=="soft":
                    cost+=_weight(state,"avoid_wait",5)*wait
                    wait_soft_mult=wait
            home_mismatch=False
            if state.get("place_preference_model")!="teacher_x_place_v1":
                scope_norm=str(scope).replace("\u2013","-")
                home=(group.get(n)=="1-3") if scope_norm=="1-3" else (group.get(n)=="school")
                if not home:
                    if _teacher_mode(cs,state,n,"prefer_home_group")=="hard": reasons.append("niew\u0142a\u015bciwa grupa nauczycieli")
                    elif _teacher_mode(cs,state,n,"prefer_home_group")=="soft":
                        cost+=_weight(state,"prefer_home_group",2)
                        home_mismatch=True
            if preserve_map is not None:
                old=preserve_map.get((ab,sl,loc))
                if old and old!=n:
                    if _mode(cs,"preserve_school_current")=="hard": reasons.append("zmiana istniejącego planu")
                    elif _mode(cs,"preserve_school_current")=="soft": cost+=_weight(state,"preserve_school_current",2)
            if _enabled(cs,"preference_grid"):
                _unused,mult=_preference_effect(state,n,ab,sl)
                if mult: cost+=_weight(state,"preference_grid",3)*mult
            if _enabled(cs,"zone_transition_penalty"):
                zd=_zone_distance(state,tby,n,scope,br,loc)
                if zd:
                    if _mode(cs,"zone_transition_penalty")=="hard": reasons.append("zbyt odległa strefa")
                    else: cost+=_weight(state,"zone_transition_penalty",2)*zd
            cost+=_soft_required_cost(state,scope,ab,sl,loc,n)
            if reasons:
                for rr in set(reasons): reject(pi,rr)
                continue
            var=model.NewBoolVar(f"x_{pi}_{ti}"); x[(pi,n)]=var; candidate_cost[(pi,n)]=cost; wait_meta[(pi,n)]=wait
            try:
                place_pref=max(0.0,min(1.0,float((state.get("teacher_place_preferences",{}).get(n,{}) or {}).get(place_key,0.0))))
            except Exception:
                place_pref=0.0
            place_deficit=int(round((1.0-place_pref)*4))
            if place_deficit and not required and matrix_enabled:
                if matrix_lexicographic:
                    place_preference_terms.append(place_deficit*var)
                else:
                    cost+=PRIORITY_BASE[matrix_priority]*place_deficit
            if after_long_soft: after_last_long_vars.append(var)
            if before_long_soft: before_first_long_vars.append(var)
            if wait_soft_mult: wait_soft_terms.append(wait_soft_mult*var)
            if home_mismatch:
                home_mismatch_vars.append(var)
            # WF is a late fallback only where the WF category is not explicitly enabled
            # for this place in the configurable category-place checklist.
            if group.get(n)=="wf" and not required and "wf" not in allowed_groups:
                wf_fallback_vars.append(var)
            by_teacher_day[(n,ab)].append(var); by_teacher_week[n].append(var); by_teacher_slot[(n,ab,sl)].append(var)
            if is_long: by_long_day[(n,ab)].append(var); by_long_week[n].append(var)
            if opening: by_opening_week[n].append(var)
            if cost: objective.append(cost*var)
        u=model.NewBoolVar(f"unfilled_{pi}"); unfilled.append(u)
        vars_here=[v for (ppi,_),v in x.items() if ppi==pi]
        model.Add(sum(vars_here)+u==1)
        if repair_mode and preserve_map is not None:
            old=preserve_map.get((ab,sl,loc))
            if old: change_refs.append((pi,x.get((pi,old))))

    one_mode=_mode(cs,"one_place_per_slot")
    for key,vars_ in by_teacher_slot.items():
        if one_mode=="hard": model.Add(sum(vars_)<=1)
        elif one_mode=="soft" and len(vars_)>1:
            ov=_add_overflow(model,sum(vars_),1,len(vars_),f"one_{abs(hash(key))%10**8}")
            objective.append(_weight(state,"one_place_per_slot",5)*ov)

    # v5.48: slot 0/1 is system-special. Coverage is already limited to teachers
    # with lesson 1; among them softly minimize concentration of opening duties.
    opening_counts=[]
    opening_ub=len(positions)+max(base_opening.values(),default=0)
    for n in sorted(set(by_opening_week)|set(base_opening)):
        vars_=by_opening_week.get(n,[])
        base=int(base_opening.get(n,0))
        cnt=model.NewIntVar(base,base+len(vars_),f"opening_count_{abs(hash(n))%10**8}")
        model.Add(cnt==sum(vars_)+base)
        opening_counts.append(cnt)
        rep=model.NewIntVar(0,max(0,base+len(vars_)-1),f"opening_repeat_{abs(hash(n))%10**8}")
        model.Add(rep>=cnt-1)
        objective.append(PRIORITY_BASE[1]*rep)
    if opening_counts:
        mx=model.NewIntVar(0,max(1,opening_ub),"opening_repeat_max")
        model.AddMaxEquality(mx,opening_counts)
        objective.append(PRIORITY_BASE[2]*mx)

    # v5.10: maximum number of consecutive duty breaks for one teacher.
    if _enabled(cs,"max_consecutive_duties"):
        try: consec=max(1,int(_value(cs,"max_consecutive_duties",1) or 1))
        except Exception: consec=1
        break_order=defaultdict(list)
        for br in seed.get("breaks",[]):
            break_order[br["abbr"]].append(br["label"])
        mode=_mode(cs,"max_consecutive_duties")
        for n in {t["name"] for t in teachers if t["name"] in enabled or any(k[0]==t["name"] for k in base_slot)}:
            for ab,slots in break_order.items():
                if len(slots)<=consec: continue
                for wi in range(0,len(slots)-consec):
                    win=slots[wi:wi+consec+1]
                    vars_=[]
                    fixed=0
                    for sl in win:
                        vars_ += by_teacher_slot.get((n,ab,sl),[])
                        fixed += min(1,base_slot.get((n,ab,sl),0))
                    if not vars_ and fixed<=consec: continue
                    total=sum(vars_)+fixed
                    if mode=="hard":
                        model.Add(total<=consec)
                    elif mode=="soft":
                        ov=_add_overflow(model,total,consec,len(vars_)+fixed,
                                         f"consec_{abs(hash((n,ab,wi)))%10**8}")
                        objective.append(_weight(state,"max_consecutive_duties",4)*ov)

    gday_key="max_day_13" if scope=="1–3" else "max_day_school"
    gday=cs.get(gday_key,{}) if _enabled(cs,gday_key) else None
    gweek=cs.get("max_week",{}) if _enabled(cs,"max_week") else None
    for (n,ab),vars_ in by_teacher_day.items():
        spec=_limit_for(state,n,scope,"max_day",ab)
        if spec is None and gday:
            spec={"value":max(0,int(gday.get("value") or 0)),"kind":_kind(gday),"weight":_weight(state,gday_key,4)}
        total=sum(vars_)+base_day[(n,ab)]
        if spec:
            if spec["kind"]=="hard":
                if base_day[(n,ab)]>=spec["value"]: model.Add(sum(vars_)==0)
                else: model.Add(total<=spec["value"])
            else:
                ov=_add_overflow(model,total,spec["value"],len(vars_)+base_day[(n,ab)],f"day_{abs(hash((n,ab)))%10**8}")
                objective.append(spec["weight"]*ov)
        if _mode(cs,"balance_day")=="hard":
            if base_day[(n,ab)]>=1: model.Add(sum(vars_)==0)
            else: model.Add(total<=1)
        elif _mode(cs,"balance_day")=="soft":
            ov=_add_overflow(model,total,1,len(vars_)+base_day[(n,ab)],f"balday_{abs(hash((n,ab)))%10**8}")
            objective.append(_weight(state,"balance_day",2)*ov)
    for n,vars_ in by_teacher_week.items():
        spec=_limit_for(state,n,scope,"max_week")
        if spec is None and gweek:
            spec={"value":max(0,int(gweek.get("value") or 0)),"kind":_kind(gweek),"weight":_weight(state,"max_week",3)}
        total=sum(vars_)+base_week[n]
        if spec:
            if spec["kind"]=="hard":
                if base_week[n]>=spec["value"]: model.Add(sum(vars_)==0)
                else: model.Add(total<=spec["value"])
            else:
                ov=_add_overflow(model,total,spec["value"],len(vars_)+base_week[n],f"week_{abs(hash(n))%10**8}")
                objective.append(spec["weight"]*ov)
        if _mode(cs,"balance_week")=="hard":
            if base_week[n]>=1: model.Add(sum(vars_)==0)
            else: model.Add(total<=1)
        elif _mode(cs,"balance_week")=="soft":
            ov=_add_overflow(model,total,1,len(vars_)+base_week[n],f"balweek_{abs(hash(n))%10**8}")
            objective.append(_weight(state,"balance_week",1)*ov)

    # v5.50: one fairness mechanism. Manual teacher weight is always a correction
    # multiplier of lesson-load fairness; it has no separate switch or priority.
    lesson_fair=_enabled(cs,"lesson_load_fairness")
    if lesson_fair and by_teacher_week:
        names=list(by_teacher_week); factors={}
        for n in names:
            try: manual=max(0.1,float(state.get("teacher_workload",{}).get(n,1.0)))
            except Exception: manual=1.0
            lessons=max(0,_lesson_count(tby,n))
            raw=float(lessons)*manual
            factors[n]=max(0,int(round(raw*100)))
        sum_factor=sum(factors.values())
        if sum_factor<=0:
            factors={n:100 for n in names}; sum_factor=100*len(names)
        combined_required=len(positions)+sum(base_week[n] for n in names)
        mode=_mode(cs,"lesson_load_fairness")
        weight=_weight(state,"lesson_load_fairness",2)
        for n in names:
            vars_=by_teacher_week[n]; total=sum(vars_)+base_week[n]
            target=int(round(combined_required*factors[n]/sum_factor))
            if mode=="hard":
                model.Add(total>=max(0,target-1)); model.Add(total<=target+1)
            else:
                dev=model.NewIntVar(0,len(positions)+base_week[n],f"workload_dev_{abs(hash(n))%10**8}")
                model.AddAbsEquality(dev,total-target)
                objective.append(weight*dev)

    for key,rule_key,base_counts,groups in [
        ("max_long_day","max_long_day",base_lday,by_long_day),
        ("max_long_week","max_long_week",base_lweek,by_long_week)
    ]:
        if not _enabled(cs,rule_key): continue
        row=cs[rule_key]; limit=max(0,int(row.get("value") or 0)); mode=_kind(row); weight=_weight(state,rule_key,4)
        for k,vars_ in groups.items():
            base=base_counts[k]; total=sum(vars_)+base
            if mode=="hard":
                if base>=limit: model.Add(sum(vars_)==0)
                else: model.Add(total<=limit)
            elif vars_:
                ov=_add_overflow(model,total,limit,len(vars_)+base,f"{rule_key}_{abs(hash(k))%10**8}")
                objective.append(weight*ov)

    def configured_solver(seconds):
        s=cp_model.CpSolver(); s.parameters.max_time_in_seconds=seconds
        try: s.parameters.random_seed=_safe_seed(state.get("solver_seed",20260918))
        except Exception: s.parameters.random_seed=20260918
        if state.get("deterministic_mode",False):
            s.parameters.num_search_workers=1
        else:
            try: s.parameters.num_search_workers=max(1,min(8,int(state.get("solver_internal_workers",3) or 3)))
            except Exception: s.parameters.num_search_workers=3
        return s

    # Etap 1: bezwzględnie minimalizuj liczbę braków.
    model.Minimize(sum(unfilled))
    model_validation=model.Validate()
    phase1_seconds=12
    if coverage_only:
        try: phase1_seconds=max(1,min(12,float(state.get("solver_coverage_seconds",4) or 4)))
        except Exception: phase1_seconds=4
    phase1=configured_solver(phase1_seconds)
    phase1_status=phase1.Solve(model)
    phase1_attempts=[{"seconds":phase1_seconds,"status":phase1.StatusName(phase1_status),"wall_time_s":round(phase1.WallTime(),3)}]
    if coverage_only and phase1_status==cp_model.UNKNOWN:
        try: retry_seconds=max(8,min(30,float(state.get("solver_coverage_retry_seconds",12) or 12)))
        except Exception: retry_seconds=12
        retry=configured_solver(retry_seconds)
        retry_status=retry.Solve(model)
        phase1_attempts.append({"seconds":retry_seconds,"status":retry.StatusName(retry_status),"wall_time_s":round(retry.WallTime(),3)})
        phase1=retry; phase1_status=retry_status
    phase1_ok=phase1_status in (cp_model.OPTIMAL,cp_model.FEASIBLE)
    best_missing=sum(phase1.Value(u) for u in unfilled) if phase1_ok else len(unfilled)

    # v5.62: "właściwa grupa najpierw" is a structural soft preference.
    # At priority 5, once full coverage is known, minimize the number of foreign-group
    # assignments lexicographically before fairness and the remaining comfort costs.
    solver=phase1; status=phase1_status; soft_optimized=False
    home_group_optimized=False; best_home_mismatches=None; home_group_status=None; home_group_wall_time_s=None
    wf_fallback_optimized=False; best_wf_fallback=None; wf_fallback_status=None; wf_fallback_wall_time_s=None
    place_pref_optimized=False; best_place_pref_deficit=None; place_pref_status=None; place_pref_wall_time_s=None
    wait_lex_optimized=False; best_wait_soft=None; wait_lex_status=None; wait_lex_wall_time_s=None
    after_lex_optimized=False; best_after_last_long=None; after_lex_status=None; after_lex_wall_time_s=None
    before_lex_optimized=False; best_before_first_long=None; before_lex_status=None; before_lex_wall_time_s=None

    def _priority5_or_teacher_relaxed(key):
        row=cs.get(key,{})
        global_soft=(_mode(cs,key)=="soft" and normalize_priority(row.get("priority",3))>=5)
        teacher_soft=any(key in set(v or []) for v in (state.get("teacher_relaxed_rules",{}) or {}).values())
        return global_soft or teacher_soft

    if phase1_ok and best_missing==0:
        model.Add(sum(unfilled)==0)
        try: lex_seconds=max(3,min(15,float(state.get("solver_edge_lex_seconds",8 if coverage_only else 12) or (8 if coverage_only else 12))))
        except Exception: lex_seconds=8 if coverage_only else 12
        try: lex_retry_seconds=max(lex_seconds,min(30,float(state.get("solver_edge_lex_retry_seconds",20 if coverage_only else 30) or (20 if coverage_only else 30))))
        except Exception: lex_retry_seconds=20 if coverage_only else 30
        def _solve_edge_lex(expr):
            ls=configured_solver(lex_seconds); st=ls.Solve(model); total=ls.WallTime()
            # v5.65: FEASIBLE is only an incumbent, never a proven lexicographic minimum.
            # Retry every non-OPTIMAL edge result when the coverage lane has more budget.
            if st!=cp_model.OPTIMAL and coverage_only and lex_retry_seconds>lex_seconds:
                ls=configured_solver(lex_retry_seconds); st=ls.Solve(model); total+=ls.WallTime()
            return ls,st,round(total,3)

        def _pin_lex(expr,best,st):
            if st==cp_model.OPTIMAL:
                model.Add(expr==best)
                return True
            if st==cp_model.FEASIBLE:
                # Preserve the best incumbent as an upper bound, but allow later phases
                # to improve it. Never freeze a merely feasible value as "the minimum".
                model.Add(expr<=best)
            return False
        if (not contract_only) and wait_soft_terms and _priority5_or_teacher_relaxed("avoid_wait"):
            model.Minimize(sum(wait_soft_terms))
            ls,st,wall=_solve_edge_lex(sum(wait_soft_terms))
            wait_lex_status=ls.StatusName(st); wait_lex_wall_time_s=wall
            if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                best_wait_soft=sum(ls.Value(v) for v in wait_soft_terms)
                wait_lex_optimized=_pin_lex(sum(wait_soft_terms),best_wait_soft,st)
                solver=ls; status=st
        if (not contract_only) and after_last_long_vars and _priority5_or_teacher_relaxed("after_last_long"):
            model.Minimize(sum(after_last_long_vars))
            ls,st,wall=_solve_edge_lex(sum(after_last_long_vars))
            after_lex_status=ls.StatusName(st); after_lex_wall_time_s=wall
            if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                best_after_last_long=sum(ls.Value(v) for v in after_last_long_vars)
                after_lex_optimized=_pin_lex(sum(after_last_long_vars),best_after_last_long,st)
                solver=ls; status=st
        if wf_fallback_vars:
            model.Minimize(sum(wf_fallback_vars))
            try:
                wf_seconds=max(2,min(15,float(state.get("solver_wf_fallback_seconds",5 if coverage_only else 8) or (5 if coverage_only else 8))))
            except Exception:
                wf_seconds=5 if coverage_only else 8
            wf_solver=configured_solver(wf_seconds); wf_status=wf_solver.Solve(model)
            wf_fallback_status=wf_solver.StatusName(wf_status); wf_fallback_wall_time_s=round(wf_solver.WallTime(),3)
            if wf_status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                best_wf_fallback=sum(wf_solver.Value(v) for v in wf_fallback_vars)
                wf_fallback_optimized=_pin_lex(sum(wf_fallback_vars),best_wf_fallback,wf_status)
                solver=wf_solver; status=wf_status
        if matrix_lexicographic and place_preference_terms:
            model.Minimize(sum(place_preference_terms))
            ls,st,wall=_solve_edge_lex(sum(place_preference_terms))
            place_pref_status=ls.StatusName(st); place_pref_wall_time_s=wall
            if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                best_place_pref_deficit=sum(ls.Value(v) if hasattr(v,"Index") else v for v in [])
                # Terms can be weighted linear expressions; evaluate via ObjectiveValue.
                best_place_pref_deficit=int(round(ls.ObjectiveValue()))
                place_pref_optimized=_pin_lex(sum(place_preference_terms),best_place_pref_deficit,st)
                solver=ls; status=st
        if (not contract_only) and before_first_long_vars and _priority5_or_teacher_relaxed("before_first_long"):
            model.Minimize(sum(before_first_long_vars))
            ls,st,wall=_solve_edge_lex(sum(before_first_long_vars))
            before_lex_status=ls.StatusName(st); before_lex_wall_time_s=wall
            if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                best_before_first_long=sum(ls.Value(v) for v in before_first_long_vars)
                before_lex_optimized=_pin_lex(sum(before_first_long_vars),best_before_first_long,st)
                solver=ls; status=st
    _home_row=cs.get("prefer_home_group",{})
    _home_lex=(_mode(cs,"prefer_home_group")=="soft" and normalize_priority(_home_row.get("priority",3))>=5
               and state.get("place_preference_model")!="teacher_x_place_v1")
    if (not contract_only) and phase1_ok and best_missing==0 and home_mismatch_vars and _home_lex:
        model.Add(sum(unfilled)==0)
        model.Minimize(sum(home_mismatch_vars))
        try:
            home_seconds=max(1,min(12,float(state.get("solver_home_group_seconds",5 if coverage_only else 8) or (5 if coverage_only else 8))))
        except Exception:
            home_seconds=5 if coverage_only else 8
        home_solver=configured_solver(home_seconds); home_status=home_solver.Solve(model)
        home_group_status=home_solver.StatusName(home_status); home_group_wall_time_s=round(home_solver.WallTime(),3)
        if home_status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            best_home_mismatches=sum(home_solver.Value(v) for v in home_mismatch_vars)
            if home_status==cp_model.OPTIMAL:
                model.Add(sum(home_mismatch_vars)==best_home_mismatches)
                home_group_optimized=True
            else:
                model.Add(sum(home_mismatch_vars)<=best_home_mismatches)
                home_group_optimized=False
            solver=home_solver; status=home_status



    # Tryb naprawczy stosuje Minimal Perturbation: po liczbie braków minimalizuje
    # liczbę zmian względem planu odniesienia, a dopiero potem preferencje.
    best_changes=None; mpp_optimized=False
    if phase1_ok and coverage_only and best_missing==0 and state.get("solver_working_optimize",False):
        # Working drafts must remain full solutions. Once full coverage exists,
        # spend only a short bounded pass improving the soft hierarchy.
        model.Add(sum(unfilled)==0)
        model.Minimize(sum(objective) if objective else 0)
        try: quick_seconds=max(1,min(20,float(state.get("solver_working_optimize_seconds",4) or 4)))
        except Exception: quick_seconds=4
        quick=configured_solver(quick_seconds); quick_status=quick.Solve(model)
        if quick_status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            solver=quick;status=quick_status;soft_optimized=True
    elif phase1_ok and not coverage_only:
        model.Add(sum(unfilled)==best_missing)
        if repair_mode and change_refs:
            for pi,oldvar in change_refs:
                ch=model.NewBoolVar(f"changed_{pi}")
                if oldvar is None: model.Add(ch==1)
                else: model.Add(ch+oldvar==1)
                change_vars.append(ch)
        if repair_mode and change_vars:
            model.Minimize(sum(change_vars))
            phase2=configured_solver(15); phase2_status=phase2.Solve(model)
            if phase2_status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                solver=phase2; status=phase2_status
                best_changes=sum(phase2.Value(v) for v in change_vars); mpp_optimized=True
                model.Add(sum(change_vars)==best_changes)
                model.Minimize(sum(objective) if objective else 0)
                phase3=configured_solver(20); phase3_status=phase3.Solve(model)
                if phase3_status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                    solver=phase3; status=phase3_status; soft_optimized=True
        else:
            model.Minimize(sum(objective) if objective else 0)
            phase2=configured_solver(20); phase2_status=phase2.Solve(model)
            if phase2_status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                solver=phase2; status=phase2_status; soft_optimized=True
    assignments=[]; waits=[]; missing=[]; unresolved=[]
    ok=status in (cp_model.OPTIMAL,cp_model.FEASIBLE)
    for pi,p in enumerate(positions):
        chosen=None
        if ok:
            for (ppi,n),var in x.items():
                if ppi==pi and solver.Value(var):
                    chosen=n; break
        rec={k:v for k,v in p.items() if k!="break"}; rec["teacher"]=chosen; rec["wait"]=0
        if chosen:
            rec["wait"]=wait_meta.get((pi,chosen),0)
            rec["wait_kind"]=_wait_kind(tby,chosen,p["break"]) if rec["wait"] else ""
            if rec["wait"]: waits.append({**rec,"time":p["break"].get("time","")})
        else:
            missing.append(rec)
            legal=sum(1 for (ppi,_n) in x if ppi==pi)
            reasons=[{"reason":r,"count":c} for r,c in rejected[pi].most_common()]
            if legal and not reasons: reasons=[{"reason":"limity zbiorcze lub konkurencja o dostępnych nauczycieli","count":legal}]
            unresolved.append({"position":rec,"legal_candidates":legal,"blocked_reasons":reasons})
        assignments.append(rec)
    totals=Counter()
    for c in rejected.values(): totals.update(c)
    stability={"reference":0,"preserved":0,"changed":0,"percent":100.0}
    if preserve_map is not None:
        for pi,p in enumerate(positions):
            br=p["break"]; loc=p.get("location") or p.get("station")
            old=preserve_map.get((br["abbr"],br["label"],loc))
            if not old: continue
            stability["reference"]+=1
            if assignments[pi].get("teacher")==old: stability["preserved"]+=1
            else: stability["changed"]+=1
        if stability["reference"]:
            stability["percent"]=round(100*stability["preserved"]/stability["reference"],1)
    diagnostics={"engine":"OR-Tools CP-SAT","status":solver.StatusName(status),"wall_time_s":round(solver.WallTime(),3),
                 "model_validation":model_validation,"solution_info":solver.SolutionInfo(),
                 "phase1_status":phase1.StatusName(phase1_status),"phase1_attempts":phase1_attempts,
                 "inconclusive":phase1_status==cp_model.UNKNOWN,"proven_infeasible":phase1_status==cp_model.INFEASIBLE,
                 "minimum_missing_found":best_missing if phase1_ok else None,
                 "home_group_lexicographic":bool(_home_lex),"home_group_optimized":home_group_optimized,
                 "minimum_foreign_group_assignments":best_home_mismatches,
                 "home_group_status":home_group_status,"home_group_wall_time_s":home_group_wall_time_s,
                 "wf_fallback_13_lexicographic":bool(scope=="1–3" and wf_fallback_vars),
                 "wf_fallback_13_optimized":bool(scope=="1–3" and wf_fallback_optimized),
                 "minimum_wf_fallback_13_assignments":best_wf_fallback if scope=="1–3" else None,
                 "wf_fallback_13_status":wf_fallback_status if scope=="1–3" else None,
                 "wf_fallback_13_wall_time_s":wf_fallback_wall_time_s if scope=="1–3" else None,
                 "wf_fallback_lexicographic":bool(wf_fallback_vars),
                 "wf_fallback_optimized":wf_fallback_optimized,
                 "minimum_wf_fallback_assignments":best_wf_fallback,
                 "wf_fallback_status":wf_fallback_status,"wf_fallback_wall_time_s":wf_fallback_wall_time_s,
                 "wf_fallback_scope":scope,
                 "place_preference_lexicographic":bool(place_preference_terms),
                 "place_preference_optimized":place_pref_optimized,
                 "minimum_place_preference_deficit":best_place_pref_deficit,
                 "place_preference_status":place_pref_status,"place_preference_wall_time_s":place_pref_wall_time_s,
                 "wait_lexicographic":wait_lex_optimized,"minimum_wait_soft_periods":best_wait_soft,
                 "wait_lex_status":wait_lex_status,"wait_lex_wall_time_s":wait_lex_wall_time_s,
                 "after_last_long_lexicographic":after_lex_optimized,"minimum_after_last_long":best_after_last_long,
                 "after_last_long_lex_status":after_lex_status,"after_last_long_lex_wall_time_s":after_lex_wall_time_s,
                 "before_first_long_lexicographic":before_lex_optimized,"minimum_before_first_long":best_before_first_long,
                 "before_first_long_lex_status":before_lex_status,"before_first_long_lex_wall_time_s":before_lex_wall_time_s,
                 "soft_optimized":soft_optimized,"mpp_optimized":mpp_optimized,"minimum_changes_found":best_changes,
                 "solver_seed":_safe_seed(state.get("solver_seed",20260918)),"deterministic_mode":bool(state.get("deterministic_mode",False)),
                 "stability":stability,
                 "unresolved":unresolved,"hard_rejections":[{"reason":r,"count":c} for r,c in totals.most_common()]}
    objective_value=int(round(solver.ObjectiveValue())) if ok and soft_optimized else None
    return assignments,waits,missing,{"flow":len(positions)-len(missing),"cost":objective_value,"diagnostics":diagnostics}

