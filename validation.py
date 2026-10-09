from collections import Counter, defaultdict

RULE_TYPES={"unavailable","avoid_slot","prefer_slot","require_slot","avoid_day","prefer_day","avoid_location","prefer_location","no_before_lesson","no_after_lesson","max_day","max_week"}
SCOPES={"oba","1–3","szkoła"}

def _kind(r):
    return "hard" if str(r.get("kind","soft")).lower() in ("hard","system_hard") else "soft"

def _lesson_periods(tby,name,abbr):
    return {int(p) for p in tby[name].get("lessons",{}).get(abbr,{})}

def _relation(tby,name,br):
    ps=_lesson_periods(tby,name,br["abbr"])
    hp=br.get("prev") in ps; hn=br.get("next") in ps
    if hp and hn: return "between"
    if hn: return "before"
    if hp: return "after"
    return "none"

def _is_after_last_lesson(tby,name,br):
    ps=_lesson_periods(tby,name,br["abbr"])
    prev=br.get("prev")
    return bool(ps and prev in ps and int(prev)==max(ps))

def validate_state(state,seed):
    problems=[]
    teachers={t["name"] for t in seed.get("teachers",[])}
    tby={t["name"]:t for t in seed.get("teachers",[])}
    breaks=seed.get("breaks",[])
    bmap={(b["abbr"],b["label"]):b for b in breaks}
    rows=state.get("global_constraints",[])
    keys=[r.get("key") for r in rows]
    for key,count in Counter(keys).items():
        if key and count>1:
            problems.append({"severity":"error","code":"duplicate_global","message":f"Reguła globalna „{key}” występuje {count} razy."})
    for r in rows:
        key=r.get("key")
        if r.get("priority") not in (1,2,3,4,5):
            problems.append({"severity":"error","code":"priority_range","message":f"Reguła „{r.get('label',key)}” ma nieprawidłowy priorytet."})
        if key=="max_long_day":
            try: v=int(r.get("value"))
            except Exception: v=-1
            if not 0<=v<=2:
                problems.append({"severity":"error","code":"long_day_range","message":"Limit długich przerw dziennie musi być w zakresie 0–2."})
        if key=="max_long_week":
            try: v=int(r.get("value"))
            except Exception: v=-1
            if not 0<=v<=10:
                problems.append({"severity":"error","code":"long_week_range","message":"Limit długich przerw tygodniowo musi być w zakresie 0–10."})

    ind=[r for r in state.get("individual_constraints",[]) if r.get("enabled",True)]
    for r in ind:
        if r.get("teacher") not in teachers:
            problems.append({"severity":"error","code":"unknown_teacher","message":f"Nieznany nauczyciel w regule: {r.get('teacher') or '—'}."})
        if r.get("scope","oba") not in SCOPES:
            problems.append({"severity":"error","code":"bad_scope","message":f"Nieprawidłowy zakres reguły dla {r.get('teacher','—')}."})
        if r.get("rule") not in RULE_TYPES:
            problems.append({"severity":"error","code":"bad_rule","message":f"Nieznany typ reguły „{r.get('rule')}” dla {r.get('teacher','—')}."})
        if r.get("priority") not in (1,2,3,4,5):
            problems.append({"severity":"error","code":"priority_range","message":f"Reguła indywidualna {r.get('teacher','—')} ma nieprawidłowy priorytet."})
        if r.get("rule")=="require_slot" and (not r.get("day") or not r.get("slot")):
            problems.append({"severity":"error","code":"require_incomplete","message":f"Wymagany dyżur dla {r.get('teacher','—')} nie ma dnia lub slotu."})

    hard_req=[r for r in ind if r.get("rule")=="require_slot" and _kind(r)=="hard"]
    for req in hard_req:
        n=req.get("teacher"); ab=req.get("day"); sl=req.get("slot"); loc=req.get("location") or ""
        if n not in tby: continue
        br=bmap.get((ab,sl))
        if not br:
            problems.append({"severity":"error","code":"require_unknown_slot","message":f"Wymagany dyżur {n}: {ab} {sl} nie istnieje w planie przerw."})
            continue
        if br.get("period") is not None and int(br["period"]) in _lesson_periods(tby,n,ab):
            problems.append({"severity":"error","code":"require_lesson_collision","message":f"{n}: wymagany dyżur {ab} {sl} koliduje z lekcją."})
        for r in ind:
            if r is req or r.get("teacher")!=n or _kind(r)!="hard": continue
            if r.get("scope","oba") not in ("oba",req.get("scope","oba")) and req.get("scope","oba")!="oba": continue
            typ=r.get("rule"); day=r.get("day"); slot=r.get("slot"); rloc=r.get("location")
            md=(not day or day==ab); ms=(not slot or slot==sl); ml=(not rloc or not loc or rloc==loc)
            conflict=(typ=="unavailable" and md and ms and ml) or (typ=="avoid_slot" and md and ms) or (typ=="avoid_day" and md)
            if conflict:
                problems.append({"severity":"error","code":"require_conflict","message":f"{n}: „musi być” na {ab} {sl} koliduje z twardą regułą „{typ}”."})
        cs={r.get("key"):r for r in rows if r.get("enabled",False)}
        rel=_relation(tby,n,br)
        if rel=="before" and _kind(cs.get("no_before_lesson",{}))=="hard":
            problems.append({"severity":"error","code":"require_before_conflict","message":f"{n}: wymagany dyżur {ab} {sl} jest tylko przed lekcją, a obowiązuje twardy zakaz."})
        if _is_after_last_lesson(tby,n,br):
            try: long_threshold=max(1,int(({r.get("key"):r for r in rows}.get("long_break_penalty",{}).get("value") or 15)))
            except Exception: long_threshold=15
            key="after_last_long" if int(br.get("minutes",0) or 0)>=long_threshold else "after_last_short"
            if _kind(cs.get(key,{}))=="hard":
                kind="długiej" if key=="after_last_long" else "krótkiej"
                problems.append({"severity":"error","code":"require_after_last_conflict","message":f"{n}: wymagany dyżur {ab} {sl} wypada po ostatniej lekcji na {kind} przerwie, a obowiązuje twardy zakaz."})

    # v5.7: walidacja macierzy miejsc/obsady całej szkoły.
    school_locations=[str(x).strip() for x in state.get("school_locations",[]) if str(x).strip()]
    if len(school_locations)!=len(set(school_locations)):
        problems.append({"severity":"error","code":"school_location_duplicate","message":"Lista miejsc dyżuru szkoły zawiera duplikaty."})
    if not school_locations:
        problems.append({"severity":"error","code":"school_locations_empty","message":"Lista miejsc dyżuru szkoły jest pusta."})
    mins_school=state.get("min_people_school",{})
    for key,value in (mins_school or {}).items():
        try: iv=int(value)
        except Exception: iv=-1
        if iv not in (0,1):
            problems.append({"severity":"error","code":"school_staffing_range","message":f"Obsada szkoły {key} musi wynosić 0 albo 1."})

    # Integrity of the currently saved plan. A teacher may occupy only one duty
    # position in a given break, regardless of scope (1–3 / whole school).
    teacher_slots=defaultdict(list)
    school_pos=Counter(); pos13=Counter()
    for a in state.get("school_assignments",[]) or []:
        n=a.get("teacher"); ab=a.get("abbr"); sl=a.get("slot"); loc=str(a.get("location") or "")
        if not n: continue
        if n not in teachers:
            problems.append({"severity":"error","code":"assignment_unknown_teacher","message":f"Plan szkoły wskazuje nieznanego nauczyciela: {n}."})
        if (ab,sl) not in bmap:
            problems.append({"severity":"error","code":"assignment_unknown_slot","message":f"Plan szkoły zawiera nieistniejący slot {ab} {sl}."})
        if loc and loc not in school_locations:
            problems.append({"severity":"error","code":"assignment_unknown_location","message":f"Plan szkoły zawiera nieaktywne miejsce „{loc}” ({ab} {sl})."})
        school_pos[(ab,sl,loc)]+=1
        teacher_slots[(n,ab,sl)].append(("szkoła",loc))
    for r in state.get("last_13_assignments",[]) or []:
        ab=r.get("abbr"); sl=r.get("label")
        for a in r.get("assignments",[]) or []:
            n=a.get("teacher"); station=str(a.get("station") or "")
            if not n: continue
            if n not in teachers:
                problems.append({"severity":"error","code":"assignment_unknown_teacher","message":f"Plan 1–3 wskazuje nieznanego nauczyciela: {n}."})
            if (ab,sl) not in bmap:
                problems.append({"severity":"error","code":"assignment_unknown_slot","message":f"Plan 1–3 zawiera nieistniejący slot {ab} {sl}."})
            pos13[(ab,sl,station)]+=1
            teacher_slots[(n,ab,sl)].append(("1–3",station))
    for (ab,sl,loc),count in school_pos.items():
        if loc and count>1:
            problems.append({"severity":"error","code":"duplicate_school_position","message":f"{ab} {sl} • {loc}: zapisano {count} przydziały tego samego stanowiska."})
    for (ab,sl,station),count in pos13.items():
        if station and count>1:
            problems.append({"severity":"error","code":"duplicate_13_position","message":f"{ab} {sl} • {station}: zapisano {count} przydziały tego samego stanowiska 1–3."})
    for (n,ab,sl),places in teacher_slots.items():
        if n and len(places)>1:
            where=", ".join(f"{scope} • {loc}" for scope,loc in places)
            problems.append({"severity":"error","code":"assignment_double_booked","message":f"{n}: więcej niż jeden dyżur w {ab} {sl}: {where}."})

    for req in hard_req:
        if req.get("scope") not in ("oba","szkoła"): continue
        loc=str(req.get("location") or "")
        if loc and loc not in school_locations:
            problems.append({"severity":"error","code":"require_school_unknown_location","message":f"{req.get('teacher')}: wymagany dyżur wskazuje nieaktywne miejsce „{loc}”."})
        if loc:
            key=f"{req.get('day')}|{req.get('slot')}|{loc}"
            if int((mins_school or {}).get(key,0) or 0)!=1:
                problems.append({"severity":"error","code":"require_school_disabled_position","message":f"{req.get('teacher')}: wymagany dyżur {req.get('day')} {req.get('slot')} • {loc} ma wyłączoną obsadę."})

    req_by=defaultdict(list)
    for r in hard_req:
        if r.get("scope") in ("oba","1–3"):
            req_by[(r.get("day"),r.get("slot"))].append(r)
    min_people=state.get("min_people_13",{})
    for key,rr in req_by.items():
        ab,sl=key
        try: capacity=int(min_people.get(f"{ab}|{sl}",2))
        except Exception: capacity=2
        if len(rr)>capacity:
            problems.append({"severity":"error","code":"too_many_required","message":f"{ab} {sl}: wymaganych jest {len(rr)} nauczycieli, a obsada wynosi {capacity}."})

    by_teacher_day=defaultdict(int)
    by_teacher_week=Counter()
    for r in hard_req:
        n=r.get("teacher"); ab=r.get("day")
        by_teacher_day[(n,ab)]+=1; by_teacher_week[n]+=1
    for r in ind:
        if _kind(r)!="hard": continue
        if r.get("rule")=="max_day":
            try: lim=int(r.get("value") or 0)
            except Exception: continue
            days=[r.get("day")] if r.get("day") else ["Pn","Wt","Śr","Czw","Pi"]
            for ab in days:
                if by_teacher_day[(r.get("teacher"),ab)]>lim:
                    problems.append({"severity":"error","code":"required_over_day_limit","message":f"{r.get('teacher')}: wymagane dyżury przekraczają twardy limit dzienny ({lim})."})
        if r.get("rule")=="max_week":
            try: lim=int(r.get("value") or 0)
            except Exception: continue
            if by_teacher_week[r.get("teacher")]>lim:
                problems.append({"severity":"error","code":"required_over_week_limit","message":f"{r.get('teacher')}: wymagane dyżury przekraczają twardy limit tygodniowy ({lim})."})

    # Funkcje zaawansowane v5.3.
    for n,v in state.get("teacher_workload",{}).items():
        if n not in teachers:
            problems.append({"severity":"error","code":"workload_unknown_teacher","message":f"Nieznany nauczyciel w pensum: {n}."})
        try: ok=float(v)>0
        except Exception: ok=False
        if not ok:
            problems.append({"severity":"error","code":"workload_value","message":f"{n}: współczynnik pensum/obciążenia musi być większy od zera."})
    allowed_pref={"prefer","neutral","avoid","forbid"}
    for n,cells in state.get("preference_grid",{}).items():
        if n not in teachers:
            problems.append({"severity":"error","code":"pref_unknown_teacher","message":f"Nieznany nauczyciel w siatce preferencji: {n}."})
        for cell,val in (cells or {}).items():
            if val not in allowed_pref:
                problems.append({"severity":"error","code":"pref_value","message":f"{n}: nieprawidłowa preferencja {cell} = {val}."})
    lock_keys=Counter()
    for lock in state.get("locked_assignments",[]):
        n=lock.get("teacher"); scope=lock.get("scope"); ab=lock.get("abbr"); sl=lock.get("slot"); loc=str(lock.get("location",""))
        lk=(scope,ab,sl,loc); lock_keys[lk]+=1
        if n not in teachers:
            problems.append({"severity":"error","code":"lock_unknown_teacher","message":f"Blokada wskazuje nieznanego nauczyciela: {n or '—'}."})
        if scope not in {"1–3","szkoła"}:
            problems.append({"severity":"error","code":"lock_scope","message":f"Blokada {n or '—'} ma nieprawidłowy zakres."})
        br=bmap.get((ab,sl))
        if not br:
            problems.append({"severity":"error","code":"lock_slot","message":f"Blokada {n or '—'} wskazuje nieistniejący slot {ab} {sl}."})
        elif n in tby and br.get("period") is not None and int(br["period"]) in _lesson_periods(tby,n,ab):
            problems.append({"severity":"error","code":"lock_lesson_collision","message":f"{n}: zamrożony dyżur {ab} {sl} koliduje z lekcją."})
        for req in hard_req:
            if req.get("teacher")!=n and req.get("day")==ab and req.get("slot")==sl and req.get("scope","oba") in ("oba",scope):
                rloc=str(req.get("location") or "")
                if not rloc or not loc or rloc==loc:
                    problems.append({"severity":"error","code":"lock_required_conflict","message":f"{ab} {sl}: blokada {n} koliduje z wymaganym nauczycielem {req.get('teacher')}."})
    for lk,count in lock_keys.items():
        if count>1:
            problems.append({"severity":"error","code":"duplicate_lock","message":f"To samo stanowisko jest zamrożone {count} razy: {lk[1]} {lk[2]} {lk[3]}."})

    excluded=set(state.get("excluded_teachers",[]))
    for n in excluded:
        if n not in teachers:
            problems.append({"severity":"error","code":"excluded_unknown_teacher","message":f"Nieznany nauczyciel na liście wykluczonych: {n}."})
    for r in hard_req:
        if r.get("teacher") in excluded:
            problems.append({"severity":"error","code":"excluded_required","message":f"{r.get('teacher')}: wykluczony ze wszystkich dyżurów, ale ma regułę wymaganego dyżuru."})
    for lock in state.get("locked_assignments",[]):
        if lock.get("teacher") in excluded:
            problems.append({"severity":"error","code":"excluded_locked","message":f"{lock.get('teacher')}: wykluczony ze wszystkich dyżurów, ale ma zamrożony przydział {lock.get('abbr')} {lock.get('slot')}."})

    warnings=[]
    absent=set(state.get("absent_teachers",[]))
    for lock in state.get("locked_assignments",[]):
        if lock.get("teacher") in absent:
            warnings.append({"severity":"warning","code":"absent_locked","message":f"{lock.get('teacher')}: nieobecność koliduje z zamrożonym dyżurem {lock.get('abbr')} {lock.get('slot')}."})
    if not any(r.get("key")=="avoid_wait" and r.get("enabled") and _kind(r)=="hard" for r in rows):
        warnings.append({"severity":"warning","code":"wait_not_hard","message":"Zakaz dodatkowego oczekiwania nie jest ustawiony jako „musi być”."})
    if not any(r.get("key")=="no_lesson_overlap" and r.get("enabled") and _kind(r)=="hard" for r in rows):
        warnings.append({"severity":"warning","code":"lesson_overlap_not_hard","message":"Kolizja dyżuru z lekcją nie jest ustawiona jako „musi być”."})
    problems.extend(warnings)
    return {"ok":not any(p["severity"]=="error" for p in problems),
            "errors":sum(1 for p in problems if p["severity"]=="error"),
            "warnings":sum(1 for p in problems if p["severity"]=="warning"),
            "problems":problems}

