from pathlib import Path
import json, re

ROOT=Path(r"C:\DutySolverDemo\dyzury-v4.6-final")
app=ROOT/"app.py"
ui=ROOT/"static"/"index.html"
statep=ROOT/"data"/"state.json"
readme=ROOT/"README.md"
start=ROOT/"start_service.cmd"

s=app.read_text(encoding="utf-8")
s=s.replace('app=FastAPI(title="DEMO Dyżury",version="4.5")','app=FastAPI(title="DEMO Dyżury",version="4.6")')

start_marker='def cdict(state):'
end_marker='class MCMF:'
a=s.index(start_marker)
b=s.index(end_marker)
helpers=r'''def cdict(state): return {c["key"]:c for c in state.get("global_constraints",[])}

def normalize_kind(value):
    return "hard" if str(value or "").lower() in ("hard","system_hard") else "soft"

def cenabled(cs,key):
    return bool(cs.get(key,{}).get("enabled",False))

def ckind(cs,key,default="soft"):
    c=cs.get(key,{})
    if not c.get("enabled",False):
        return "off"
    return normalize_kind(c.get("kind",default))

def cpriority(cs,key,default=1000):
    c=cs.get(key,{})
    try:
        return max(0,int(c.get("priority") if c.get("priority") is not None else default))
    except Exception:
        return max(0,int(default))

def cweight(cs,key,default=0):
    return cpriority(cs,key,default) if ckind(cs,key)=="soft" else 0

def cvalue(cs,key,default=None):
    c=cs.get(key,{})
    return c.get("value",default) if c.get("enabled",False) else default

def global_rule_effect(cs,key,multiplier=1,default_priority=1000):
    mode=ckind(cs,key)
    if mode=="off":
        return False,0
    if mode=="hard":
        return True,0
    return False,cpriority(cs,key,default_priority)*max(1,int(multiplier or 1))

def lesson_periods(name,abbr):
    return {int(p) for p in TBY[name]["lessons"].get(abbr,{})}

def blockset(state,name):
    return set(state.get("manual_blocks",{}).get(name,[]))

def active_individual(state,name,scope):
    out=[]
    for r in state.get("individual_constraints",[]):
        if not r.get("enabled",True) or r.get("teacher")!=name:
            continue
        sc=r.get("scope","oba")
        if sc not in ("oba",scope):
            continue
        out.append(r)
    return out

def individual_effect(state,name,scope,abbr,slot,location=None):
    hard_block=False
    max_day=None
    max_week=None
    cost=0
    for r in active_individual(state,name,scope):
        typ=r.get("rule")
        mode=normalize_kind(r.get("kind","hard"))
        try:
            pr=max(0,int(r.get("priority") or 0))
        except Exception:
            pr=0
        day=r.get("day")
        sl=r.get("slot")
        loc=r.get("location")
        match_day=(not day or day==abbr)
        match_slot=(not sl or sl==slot)
        match_loc=(not loc or loc==location)

        hit=False
        if typ=="unavailable":
            hit=match_day and match_slot and match_loc
        elif typ=="avoid_slot":
            hit=match_day and match_slot
        elif typ=="prefer_slot":
            hit=not (match_day and match_slot)
        elif typ=="avoid_day":
            hit=match_day
        elif typ=="prefer_day":
            hit=bool(day and day!=abbr)
        elif typ=="avoid_location":
            hit=match_loc
        elif typ=="prefer_location":
            hit=bool(loc and loc!=location)

        if hit:
            if mode=="hard":
                hard_block=True
            else:
                cost+=pr

        if typ=="max_day" and match_day:
            max_day={"value":max(0,int(r.get("value") or 0)),"kind":mode,"priority":pr}
        elif typ=="max_week":
            max_week={"value":max(0,int(r.get("value") or 0)),"kind":mode,"priority":pr}

    return hard_block,max_day,max_week,cost

def school_index(assignments):
    idx=defaultdict(list)
    for d in assignments:
        if d.get("teacher"):
            idx[(d["teacher"],d["abbr"],d["slot"])].append(d["location"])
    return idx

def duty_counts(assignments):
    day=Counter()
    week=Counter()
    for d in assignments:
        if d.get("teacher"):
            day[(d["teacher"],d["abbr"])]+=1
            week[d["teacher"]]+=1
    return day,week

def lesson_relation(name,br):
    ps=lesson_periods(name,br["abbr"])
    has_prev=br.get("prev") in ps
    has_next=br.get("next") in ps
    if has_prev and has_next:
        return "between"
    if has_next:
        return "before"
    if has_prev:
        return "after"
    if br.get("next") is None and br.get("prev") and br["prev"]-1 in ps:
        return "wait_after"
    return "none"

def wait_periods(name,br):
    ps=sorted(lesson_periods(name,br["abbr"]))
    if not ps:
        return 9
    prev=br.get("prev")
    nxt=br.get("next")
    if prev in ps or nxt in ps:
        return 0
    dist=[]
    if prev is not None:
        before=[p for p in ps if p<=prev]
        if before:
            dist.append(max(0,int(prev)-max(before)))
    if nxt is not None:
        after=[p for p in ps if p>=nxt]
        if after:
            dist.append(max(0,min(after)-int(nxt)))
    if not dist:
        if prev is not None and max(ps)<prev:
            return max(1,int(prev)-max(ps))
        if nxt is not None and min(ps)>nxt:
            return max(1,min(ps)-int(nxt))
        return 9
    return min(dist)

def duty_overlaps_lesson(name,br):
    p=br.get("period")
    if p is None:
        return False
    try:
        return int(p) in lesson_periods(name,br["abbr"])
    except Exception:
        return False

def directional_individual_effect(state,name,scope,relation):
    hard=False
    cost=0
    for r in active_individual(state,name,scope):
        typ=r.get("rule")
        mode=normalize_kind(r.get("kind","hard"))
        try:
            pr=max(0,int(r.get("priority") or 0))
        except Exception:
            pr=0
        hit=(typ=="no_before_lesson" and relation=="before") or (typ=="no_after_lesson" and relation in ("after","wait_after"))
        if hit:
            if mode=="hard":
                hard=True
            else:
                cost+=pr
    return hard,cost

def soft_required_penalty(state,scope,abbr,slot,location,candidate):
    cost=0
    for r in state.get("individual_constraints",[]):
        if not r.get("enabled",True) or r.get("rule")!="require_slot":
            continue
        if normalize_kind(r.get("kind","hard"))!="soft":
            continue
        if r.get("scope","oba") not in ("oba",scope):
            continue
        if r.get("day") and r.get("day")!=abbr:
            continue
        if r.get("slot") and r.get("slot")!=slot:
            continue
        if r.get("location") and r.get("location")!=location:
            continue
        if r.get("teacher")!=candidate:
            try:
                cost+=max(0,int(r.get("priority") or 0))
            except Exception:
                pass
    return cost

def global_limit_spec(cs,key):
    if not cenabled(cs,key):
        return None
    try:
        value=max(0,int(cs[key].get("value") or 0))
    except Exception:
        value=0
    return {"value":value,"kind":ckind(cs,key),"priority":cpriority(cs,key,1000)}

'''
s=s[:a]+helpers+s[b:]

solve_start=s.index('def solve_positions(')
solve_end=s.index('\ndef required_slot_rules',solve_start)
solver=r'''def solve_positions(state,scope,positions,enabled,other_assignments,preserve_map=None):
    cs=cdict(state)
    base_day,base_week=duty_counts(other_assignments)
    other_idx=school_index(other_assignments)
    m=MCMF()
    S=("S",)
    T=("T",)
    wait_meta={}
    teacher_day_policy={}
    teacher_week_policy={}
    ts_incoming=Counter()

    bal_day_mode=ckind(cs,"balance_day")
    bal_day_pr=cpriority(cs,"balance_day",55)
    bal_week_mode=ckind(cs,"balance_week")
    bal_week_pr=cpriority(cs,"balance_week",10)

    global_day_key="max_day_13" if scope=="1–3" else "max_day_school"
    global_day_spec=global_limit_spec(cs,global_day_key)
    global_week_spec=global_limit_spec(cs,"max_week")

    for pi,p in enumerate(positions):
        pn=("P",pi)
        m.add(S,pn,1,0)
        br=p["break"]
        location=p.get("location")
        for t in SEED["teachers"]:
            n=t["name"]
            required_name=p.get("required_teacher")
            if required_name and n!=required_name:
                continue
            if n not in enabled and not required_name:
                continue

            cost=0
            if br["abbr"]+"|"+br["label"] in blockset(state,n):
                hard,pen=global_rule_effect(cs,"manual_blocks",1,100000)
                if hard:
                    continue
                cost+=pen

            if other_idx.get((n,br["abbr"],br["label"])):
                hard,pen=global_rule_effect(cs,"cross_scope_conflict",1,100000)
                if hard:
                    continue
                cost+=pen

            if duty_overlaps_lesson(n,br):
                hard,pen=global_rule_effect(cs,"no_lesson_overlap",1,100000)
                if hard:
                    continue
                cost+=pen

            hard,idmaxd,idmaxw,icost=individual_effect(state,n,scope,br["abbr"],br["label"],location)
            if hard:
                continue
            cost+=icost

            rel=lesson_relation(n,br)
            dhard,dcost=directional_individual_effect(state,n,scope,rel)
            if dhard:
                continue
            cost+=dcost

            if rel=="before":
                hard,pen=global_rule_effect(cs,"no_before_lesson",1,2500)
                if hard:
                    continue
                cost+=pen
            if rel in ("after","wait_after"):
                hard,pen=global_rule_effect(cs,"no_after_lesson",1,2500)
                if hard:
                    continue
                cost+=pen

            wait=wait_periods(n,br)
            if wait>0:
                hard,pen=global_rule_effect(cs,"adjacent_lesson",1,5000)
                if hard:
                    continue
                cost+=pen

                hard,pen=global_rule_effect(cs,"avoid_wait",wait,10000)
                if hard:
                    continue
                cost+=pen

            home=(GROUP.get(n)=="1-3") if scope=="1–3" else (GROUP.get(n)=="school")
            if not home:
                hard,pen=global_rule_effect(cs,"prefer_home_group",1,250)
                if hard:
                    continue
                cost+=pen

            if preserve_map is not None:
                old=preserve_map.get((br["abbr"],br["label"],location))
                if old and old!=n:
                    hard,pen=global_rule_effect(cs,"preserve_school_current",1,180)
                    if hard:
                        continue
                    cost+=pen

            if cenabled(cs,"long_break_penalty"):
                try:
                    long_min=max(0,int(cvalue(cs,"long_break_penalty",15) or 15))
                except Exception:
                    long_min=15
                if int(br.get("minutes",0) or 0)>=long_min:
                    hard,pen=global_rule_effect(cs,"long_break_penalty",1,20)
                    if hard:
                        continue
                    cost+=pen

            cost+=soft_required_penalty(state,scope,br["abbr"],br["label"],location,n)

            day_spec=idmaxd if idmaxd is not None else global_day_spec
            week_spec=idmaxw if idmaxw is not None else global_week_spec

            if day_spec and day_spec["kind"]=="hard" and base_day[(n,br["abbr"])]>=day_spec["value"]:
                continue
            if week_spec and week_spec["kind"]=="hard" and base_week[n]>=week_spec["value"]:
                continue
            if bal_day_mode=="hard" and base_day[(n,br["abbr"])]>=1:
                continue
            if bal_week_mode=="hard" and base_week[n]>=1:
                continue

            teacher_day_policy[(n,br["abbr"])]=day_spec
            teacher_week_policy[n]=week_spec

            ts=("TS",n,br["abbr"],br["label"])
            tag=(pi,n,wait)
            m.add(pn,ts,1,int(cost),tag=tag)
            ts_incoming[ts]+=1
            wait_meta[(pi,n)]=wait

    one_mode=ckind(cs,"one_place_per_slot")
    one_pr=cpriority(cs,"one_place_per_slot",100000)
    for ts,cnt in ts_incoming.items():
        _,n,ab,sl=ts
        td=("TD",n,ab)
        cap=1 if one_mode=="hard" else cnt
        for k in range(max(0,int(cap))):
            extra=(one_pr*k) if one_mode=="soft" else 0
            m.add(ts,td,1,int(extra))

    for (n,ab),spec in teacher_day_policy.items():
        td=("TD",n,ab)
        tw=("TW",n)
        base=base_day[(n,ab)]
        cap=len(positions)
        if spec and spec["kind"]=="hard":
            cap=min(cap,max(0,spec["value"]-base))
        if bal_day_mode=="hard":
            cap=min(cap,max(0,1-base))
        for k in range(max(0,int(cap))):
            after=base+k+1
            arc_cost=0
            if spec and spec["kind"]=="soft" and after>spec["value"]:
                arc_cost+=spec["priority"]*(after-spec["value"])
            if bal_day_mode=="soft":
                arc_cost+=(after-1)*bal_day_pr
            m.add(td,tw,1,int(arc_cost))

    for n,spec in teacher_week_policy.items():
        tw=("TW",n)
        base=base_week[n]
        cap=len(positions)
        if spec and spec["kind"]=="hard":
            cap=min(cap,max(0,spec["value"]-base))
        if bal_week_mode=="hard":
            cap=min(cap,max(0,1-base))
        for k in range(max(0,int(cap))):
            after=base+k+1
            arc_cost=0
            if spec and spec["kind"]=="soft" and after>spec["value"]:
                arc_cost+=spec["priority"]*(after-spec["value"])
            if bal_week_mode=="soft":
                arc_cost+=(after-1)*bal_week_pr
            m.add(tw,T,1,int(arc_cost))

    flow,cost=m.flow(S,T,len(positions))
    assignments=[]
    assigned_pos=set()
    waits=[]
    for pi,p in enumerate(positions):
        pn=("P",pi)
        chosen=None
        for e in m.g[pn]:
            v,rev,cap,c,tag=e
            if tag and cap==0:
                _,n,w=tag
                chosen=n
                break
        rec={k:v for k,v in p.items() if k!="break"}
        rec["teacher"]=chosen
        if chosen:
            assigned_pos.add(pi)
            w=wait_meta.get((pi,chosen),0)
            rec["wait"]=w
            if w:
                waits.append({**rec,"time":p["break"].get("time","")})
        else:
            rec["wait"]=0
        assignments.append(rec)
    missing=[assignments[i] for i in range(len(assignments)) if i not in assigned_pos]
    return assignments,waits,missing,{"flow":flow,"cost":cost}

'''
s=s[:solve_start]+solver+s[solve_end+1:]

rs=s.index('def required_slot_rules(')
re_=s.index('\ndef break_map',rs)
req=r'''def required_slot_rules(state,scope,kind="hard"):
    out=[]
    for i,r in enumerate(state.get("individual_constraints",[])):
        if not r.get("enabled",True) or r.get("rule")!="require_slot":
            continue
        if r.get("scope","oba") not in ("oba",scope):
            continue
        if normalize_kind(r.get("kind","hard"))!=kind:
            continue
        if not r.get("teacher") or not r.get("day") or not r.get("slot"):
            continue
        out.append({
            "id":r.get("id") or f"req_{i}",
            "teacher":r["teacher"],
            "day":r["day"],
            "slot":r["slot"],
            "location":r.get("location") or "",
            "kind":kind,
            "priority":max(0,int(r.get("priority") or 0))
        })
    return out

'''
s=s[:rs]+req+s[re_+1:]
app.write_text(s,encoding="utf-8")

h=ui.read_text(encoding="utf-8")
h=h.replace('„Twarde” muszą być spełnione. „Miękkie” są składnikami funkcji kosztu — większy priorytet = solver silniej unika naruszenia. Reguły systemowe chronią fizyczną poprawność planu i nie można ich zmiękczyć.',
'''Każdy constraint ma tryb HARD albo SOFT. HARD nie może zostać naruszony — jeśli brakuje legalnej obsady, solver pozostawi pozycję nierozwiązaną. SOFT może zostać naruszony za koszt równy priorytetowi. Ustawienie fizycznych reguł na SOFT jest możliwe, ale może świadomie dopuścić kolizje.''')
old='''<tbody><tr v-for="c in globalConstraints" :class="c.kind==='system_hard'?'constraint-system':(c.kind==='soft'?'constraint-soft':'constraint-hard')">
<td><input type="checkbox" v-model="c.enabled" :disabled="c.kind==='system_hard'"></td>
<td><b>{{c.label}}</b></td><td>{{c.scope}}</td>
<td><span class="pill" :class="{soft:c.kind==='soft',hard:c.kind!=='soft'}">{{c.kind==='system_hard'?'SYSTEM HARD':c.kind.toUpperCase()}}</span></td>
<td><input class="priority" type="number" min="0" max="100000" v-model.number="c.priority" :disabled="c.kind!=='soft'"></td>'''
new='''<tbody><tr v-for="c in globalConstraints" :class="c.kind==='soft'?'constraint-soft':'constraint-hard'">
<td><input type="checkbox" v-model="c.enabled"></td>
<td><b>{{c.label}}</b></td><td>{{c.scope}}</td>
<td><select v-model="c.kind"><option value="hard">HARD</option><option value="soft">SOFT</option></select></td>
<td><input class="priority" type="number" min="0" max="100000" v-model.number="c.priority" :disabled="c.kind!=='soft'"></td>'''
if old not in h:
    raise RuntimeError("global UI block not found")
h=h.replace(old,new,1)
h=h.replace(':disabled="newConstraint.rule===\'max_day\'||newConstraint.rule===\'max_week\'||newConstraint.rule===\'require_slot\'"','')
h=h.replace(':disabled="r.rule===\'require_slot\'||r.rule===\'max_day\'||r.rule===\'max_week\'"','')
old_method="addIndividualConstraint(){if(!this.newConstraint.teacher){alert('Wybierz nauczyciela.');return}if(this.newConstraint.rule==='require_slot'&&(!this.newConstraint.day||!this.newConstraint.slot)){alert('Dla twardego przypisania wybierz dzień i slot.');return}let r=JSON.parse(JSON.stringify(this.newConstraint));if(r.rule==='max_day'||r.rule==='max_week'||r.rule==='require_slot')r.kind='hard';r.id='ic_'+Date.now()+'_'+Math.random().toString(36).slice(2,7);if(r.kind==='hard')r.priority=0;this.individualConstraints.push(r)},"
new_method="addIndividualConstraint(){if(!this.newConstraint.teacher){alert('Wybierz nauczyciela.');return}if(this.newConstraint.rule==='require_slot'&&(!this.newConstraint.day||!this.newConstraint.slot)){alert('Dla przypisania wybierz dzień i slot.');return}let r=JSON.parse(JSON.stringify(this.newConstraint));r.id='ic_'+Date.now()+'_'+Math.random().toString(36).slice(2,7);this.individualConstraints.push(r)},"
if old_method not in h:
    raise RuntimeError("addIndividualConstraint block not found")
h=h.replace(old_method,new_method,1)
ui.write_text(h,encoding="utf-8")

st=json.loads(statep.read_text(encoding="utf-8"))
st["version"]="4.6"
defaults={
"no_lesson_overlap":100000,
"one_place_per_slot":100000,
"cross_scope_conflict":100000,
"manual_blocks":100000,
"adjacent_lesson":5000,
"max_day_13":5000,
"max_day_school":5000,
"max_week":3000,
"avoid_wait":10000,
"prefer_home_group":250,
"preserve_school_current":180,
"balance_day":55,
"balance_week":10,
"long_break_penalty":20,
"no_before_lesson":2500,
"no_after_lesson":2500,
}
for c in st.get("global_constraints",[]):
    c["kind"]="hard" if str(c.get("kind","hard")).lower() in ("hard","system_hard") else "soft"
    if c.get("priority") is None:
        c["priority"]=defaults.get(c.get("key"),1000)
    if c.get("key")=="avoid_wait":
        c["enabled"]=True
        c["kind"]="hard"
        c["description"]="Nauczyciel nie może czekać specjalnie na dyżur ani przychodzić wcześniej tylko na dyżur. SOFT = kara rośnie z liczbą pustych lekcji między dyżurem a najbliższą lekcją."
    if c.get("key")=="adjacent_lesson":
        c["description"]="HARD: dyżur musi bezpośrednio stykać się z własną lekcją. SOFT: nieprzylegający dyżur jest dopuszczony za karę."
    if c.get("key")=="balance_day":
        c["description"]="SOFT: każdy kolejny dyżur w dniu kosztuje więcej. HARD: maksymalnie 1 dyżur dziennie."
    if c.get("key")=="balance_week":
        c["description"]="SOFT: każdy kolejny dyżur w tygodniu kosztuje więcej. HARD: maksymalnie 1 dyżur tygodniowo."
    if c.get("key")=="long_break_penalty":
        c["description"]="SOFT: kara za przydział na przerwie co najmniej o podanej długości. HARD: takie pozycje są niedozwolone i mogą pozostać nieobsadzone."
for rr in st.get("individual_constraints",[]):
    rr["kind"]="hard" if str(rr.get("kind","hard")).lower() in ("hard","system_hard") else "soft"
    if rr.get("priority") is None:
        rr["priority"]=1000
statep.write_text(json.dumps(st,ensure_ascii=False,indent=2),encoding="utf-8")

rd=readme.read_text(encoding="utf-8")
rd=re.sub(r'^# DEMO Dyżury v.*$', '# DEMO Dyżury v4.6 FINAL', rd, count=1, flags=re.M)
rd += '''\n## v4.6 – HARD/SOFT + testy lokalne
- Każdy constraint globalny i indywidualny ma jawny tryb HARD/SOFT.
- HARD usuwa niedozwolone kandydatury / narzuca limit; SOFT dodaje koszt według priorytetu.
- avoid_wait jest domyślnie HARD: nauczyciel nie czeka specjalnie na dyżur i nie przychodzi wcześniej tylko na dyżur.
- Regresja Alicji Kowalskiej jest objęta osobnym testem lokalnym.
- Testy constraintów uruchamiają się wyłącznie lokalnym Pythonem i nie korzystają z AI, MCP, konektorów ani usług zewnętrznych.
- Test wdrożeniowy uruchamia lokalny solver bez serwera HTTP, sprawdza schemat constraintów, oba solvery i brak naruszeń HARD avoid_wait.
'''
readme.write_text(rd,encoding="utf-8")
sc=start.read_text(encoding="utf-8").replace("dyzury-v4.5-final","dyzury-v4.6-final")
start.write_text(sc,encoding="utf-8")

print("PATCH_OK")
