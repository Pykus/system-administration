from pathlib import Path
import json, uuid, heapq, math, secrets, re
from collections import Counter, defaultdict
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from solver_ortools import solve_positions_ortools, normalize_priority
from validation import validate_state

ROOT=Path(__file__).parent
SEED=json.loads((ROOT/"data"/"seed.json").read_text(encoding="utf-8"))
STATE_PATH=ROOT/"data"/"state.json"
LAST_GOOD_PLAN_PATH=ROOT/"data"/"last_good_plan.json"
TEACHER_REGISTRY_PATH=ROOT/"data"/"teacher_registry.json"
SETTINGS_PROFILES_PATH=ROOT/"data"/"settings_profiles.json"
PLANNER_VERSION="5.79"
WORKER_PROTOCOL_VERSION="5.16"
WORKER_PACKAGE_VERSION="1.13"
app=FastAPI(title="DEMO Dyżury",version=PLANNER_VERSION)

def _empty_lessons():
    return {d:{} for d in ["Pn","Wt","Śr","Czw","Pi"]}

def _load_teacher_registry():
    try:
        raw=json.loads(TEACHER_REGISTRY_PATH.read_text(encoding="utf-8")) if TEACHER_REGISTRY_PATH.exists() else {}
    except Exception:
        raw={}
    if isinstance(raw,list): raw={x.get("name"):x for x in raw if isinstance(x,dict) and x.get("name")}
    changed=False
    for t in SEED.get("teachers",[]):
        name=t.get("name")
        if not name: continue
        row=raw.setdefault(name,{})
        if "group" not in row: row["group"]=t.get("group","school"); changed=True
        if "active" not in row: row["active"]=True; changed=True
        if not row.get("portal_token"): row["portal_token"]=secrets.token_urlsafe(18); changed=True
    if changed or not TEACHER_REGISTRY_PATH.exists():
        TEACHER_REGISTRY_PATH.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")
    return raw

TEACHER_REGISTRY=_load_teacher_registry()
CORE=set(); WF=set(); SCHOOL=set(); GROUP={}; ALL=set(); TBY={}

def refresh_teacher_indexes():
    CORE.clear(); WF.clear(); SCHOOL.clear(); GROUP.clear(); ALL.clear(); TBY.clear()
    for t in SEED.get("teachers",[]):
        name=t.get("name")
        if not name: continue
        reg=TEACHER_REGISTRY.setdefault(name,{"group":t.get("group","school"),"active":True,"portal_token":secrets.token_urlsafe(18)})
        t["group"]=reg.get("group","school")
        t["active"]=bool(reg.get("active",True))
        t["core"]=t["group"]=="1-3"
        TBY[name]=t
        GROUP[name]=t["group"]
        if not t["active"]: continue
        ALL.add(name)
        if t["group"]=="1-3": CORE.add(name)
        elif t["group"]=="wf": WF.add(name)
        else: SCHOOL.add(name)

def _display_teacher(name):
    parts=str(name or "").strip().split()
    return (" ".join(parts[1:])+" "+parts[0]) if len(parts)>1 else (parts[0] if parts else "")

def _teacher_sort_key(name):
    parts=str(name or "").strip().split()
    return ((" ".join(parts[1:]) if len(parts)>1 else (parts[0] if parts else "")).casefold(),
            (parts[0] if parts else "").casefold())

def persist_teacher_data():
    (ROOT/"data"/"seed.json").write_text(json.dumps(SEED,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    TEACHER_REGISTRY_PATH.write_text(json.dumps(TEACHER_REGISTRY,ensure_ascii=False,indent=2),encoding="utf-8")

def _classify_new_teacher(lessons):
    core_classes={str(x.get("class","")).strip() for t in SEED.get("teachers",[]) if GROUP.get(t.get("name"))=="1-3" for ps in t.get("lessons",{}).values() for ls in ps.values() for x in ls if str(x.get("class","")).strip()}
    total=lower=wf=0
    for ps in (lessons or {}).values():
        if not isinstance(ps,dict): continue
        for vals in ps.values():
            if not isinstance(vals,list): vals=[vals]
            for x in vals:
                if not isinstance(x,dict): continue
                total+=1
                if str(x.get("class","")).strip() in core_classes: lower+=1
                subj=str(x.get("subject","")).lower().replace("."," ").strip()
                if subj=="wf" or "wychowanie fizyczne" in subj: wf+=1
    if total and wf*2>=total: return "wf"
    if total and lower*2>=total: return "1-3"
    return "school"

refresh_teacher_indexes()

def load_state():
    state=ensure_state_schema(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    state,_=_sanitize_inactive_13_state(state)
    return state

def save_state(x):
    state=ensure_state_schema(x)
    state,_=_sanitize_inactive_13_state(state)
    STATE_PATH.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
def cdict(state): return {c["key"]:c for c in state.get("global_constraints",[])}

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

def is_opening_break(br):
    """Systemowy slot 0/1 07:25-07:30: nie jest zwykłą przerwą przed pierwszą lekcją."""
    try:
        return (str(br.get("label") or "").strip()=="0/1"
                and int(br.get("prev"))==0 and int(br.get("next"))==1
                and int(br.get("minutes",0) or 0)<=5)
    except Exception:
        return False

def opening_break_teacher_allowed(name,br):
    if not is_opening_break(br): return True
    try: return int(br.get("next")) in lesson_periods(name,br["abbr"])
    except Exception: return False

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
    if is_opening_break(br) and has_next:
        return "opening"
    if has_prev and has_next:
        return "between"
    if has_next:
        return "before"
    if has_prev:
        return "after"
    if br.get("next") is None and br.get("prev") and br["prev"]-1 in ps:
        return "wait_after"
    return "none"

def is_after_last_lesson(name,br):
    ps=lesson_periods(name,br["abbr"])
    prev=br.get("prev")
    return bool(ps and prev in ps and int(prev)==max(ps))

def is_before_first_lesson(name,br):
    ps=lesson_periods(name,br["abbr"])
    nxt=br.get("next")
    return bool(ps and nxt in ps and int(nxt)==min(ps))

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
        hit=(typ in ("no_before_first_lesson","no_before_lesson") and relation=="before") or (typ in ("no_after_last_lesson","no_after_lesson") and relation in ("after","wait_after"))
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

REMOVED_CONSTRAINT_KEYS={"day_span_penalty","adjacent_lesson","long_break_penalty","workload_fairness"}
SHORT_BREAK_MAX_MINUTES=10
LONG_BREAK_MINUTES=11

def _repair_text_encoding_v572(text):
    if not isinstance(text,str) or not text:
        return text
    def _fix_chunk(chunk):
        raw=chunk.encode("latin1")
        out=[]; i=0
        while i<len(raw):
            b0=raw[i]; widths=()
            if 0xC2<=b0<=0xDF: widths=(2,)
            elif 0xE0<=b0<=0xEF: widths=(3,)
            elif 0xF0<=b0<=0xF4: widths=(4,)
            done=False
            for width in widths:
                if i+width>len(raw): continue
                part=raw[i:i+width]
                try: decoded=part.decode("utf-8")
                except UnicodeDecodeError: continue
                out.append(decoded); i+=width; done=True; break
            if not done:
                out.append(chr(b0)); i+=1
        return "".join(out)
    out=text
    for _ in range(3):
        pieces=[]; buf=[]
        def flush():
            if buf:
                pieces.append(_fix_chunk("".join(buf))); buf.clear()
        for ch in out:
            if ord(ch)<=255: buf.append(ch)
            else: flush(); pieces.append(ch)
        flush()
        fixed="".join(pieces)
        if fixed==out: break
        out=fixed
    return out

def normalize_constraint_rows(rows):
    out=[]
    for raw in rows or []:
        if not isinstance(raw,dict) or raw.get("key") in REMOVED_CONSTRAINT_KEYS:
            continue
        r={k:(_repair_text_encoding_v572(v) if isinstance(v,str) else v) for k,v in dict(raw).items()}
        r["kind"]=normalize_kind(r.get("kind","hard"))
        r["priority"]=normalize_priority(r.get("priority",3))
        r["enabled"]=bool(r.get("enabled",True))
        key=r.get("key")
        if key in {"no_lesson_overlap","one_place_per_slot","cross_scope_conflict","manual_blocks"}:
            r["enabled"]=True
            r["kind"]="hard"
            r["priority"]=5
        if key=="max_long_day":
            try: r["value"]=min(2,max(0,int(r.get("value",1))))
            except Exception: r["value"]=1
        elif key=="max_long_week":
            try: r["value"]=min(10,max(0,int(r.get("value",3))))
            except Exception: r["value"]=3
        elif key=="max_consecutive_duties":
            try: r["value"]=min(6,max(1,int(r.get("value",1))))
            except Exception: r["value"]=1
        out.append(r)
    return out

def normalize_preference_grid(raw):
    out={}
    if not isinstance(raw,dict): return out
    for name,prefs in raw.items():
        clean={}
        if isinstance(prefs,dict):
            for key,value in prefs.items():
                vv=str(value or "").lower()
                if vv=="forbid": vv="avoid"
                if vv in ("prefer","avoid"): clean[str(key)]=vv
        out[str(name)]=clean
    return out

def ensure_state_schema(state):
    state=dict(state or {})
    _legacy_global=[dict(r) for r in (state.get("global_constraints",[]) or []) if isinstance(r,dict)]
    _legacy_lesson=next((r for r in _legacy_global if r.get("key")=="lesson_load_fairness"),None)
    _legacy_workload=next((r for r in _legacy_global if r.get("key")=="workload_fairness"),None)
    rows=[r for r in normalize_constraint_rows(_legacy_global) if r.get("key") not in {"no_after_lesson","no_before_lesson"}]
    keys={r.get("key") for r in rows}
    defaults=[
        {"key":"before_first_short","label":"Przed pierwszą lekcją – krótka przerwa 5-10 min (bez 0/1)","scope":"oba","enabled":False,"kind":"soft","priority":1,"value":None,
         "description":"Dotyczy krótkiej przerwy 5-10 min bezpośrednio przed PIERWSZĄ lekcją nauczyciela danego dnia, ale NIGDY slotu 0/1 (07:25–07:30). Slot 0/1 ma osobną regułę systemową: dyżur może dostać tylko nauczyciel mający lekcję na 1. godzinie."},
        {"key":"before_first_long","label":"Przed pierwszą lekcją – przerwa >10 min — ZAKAZ (bez 0/1)","scope":"oba","enabled":True,"kind":"hard","priority":5,"value":None,
         "description":"Bezwzględny zakaz dyżuru na przerwie dłuższej niż 10 minut przed PIERWSZĄ lekcją nauczyciela. Nie dotyczy systemowego slotu 0/1, który ma własną logikę kandydatów."},
        {"key":"after_last_short","label":"Po ostatniej lekcji – krótka przerwa 5-10 min","scope":"oba","enabled":False,"kind":"soft","priority":1,"value":None,
         "description":"Dotyczy wyłącznie krótkiej przerwy 5-10 min bezpośrednio po OSTATNIEJ lekcji nauczyciela danego dnia. Może być dopuszczona."},
        {"key":"after_last_long","label":"Po ostatniej lekcji – przerwa >10 min — ZAKAZ","scope":"oba","enabled":True,"kind":"hard","priority":5,"value":None,
         "description":"Bezwzględny zakaz dyżuru na przerwie dłuższej niż 10 minut po OSTATNIEJ lekcji nauczyciela, aby nie musiał zostawać dłużej w szkole."},
        {"key":"offday_duty","label":"Dyżur w dniu bez lekcji — ZAKAZ","scope":"oba","enabled":True,"kind":"hard","priority":5,"value":None,
         "description":"Bezwzględny zakaz przydzielania dyżuru nauczycielowi w dniu, w którym nie ma żadnej lekcji. Nie jest automatycznie luzowany przez Generator wariantów."},
        {"key":"max_long_day","label":"Maks. długich przerw dziennie","scope":"oba","enabled":True,"kind":"hard","priority":4,"value":1,
         "description":"Na jednego nauczyciela: maksymalnie wskazana liczba długich przerw w jednym dniu. W szkole są dwie długie przerwy dziennie."},
        {"key":"max_long_week","label":"Maks. długich przerw tygodniowo","scope":"oba","enabled":True,"kind":"hard","priority":4,"value":3,
         "description":"Na jednego nauczyciela: maksymalnie wskazana liczba długich przerw w tygodniu."},
        {"key":"max_consecutive_duties","label":"Maks. dyżurów następujących po sobie","scope":"oba","enabled":True,"kind":"hard","priority":4,"value":1,
         "description":"Maksymalna liczba kolejnych przerw, na których ten sam nauczyciel może mieć dyżur. Domyślnie 1: nie przydzielaj dyżurów na dwóch kolejnych przerwach. Wartość 2 pozwala na dwa kolejne dyżury."},
        {"key":"lesson_load_fairness","label":"Sprawiedliwy podział wg obciążenia dydaktycznego","scope":"oba","enabled":False,"kind":"soft","priority":2,"value":None,
         "description":"Jeden mechanizm sprawiedliwości: docelowy udział = liczba lekcji w tygodniu × ręczny współczynnik korekcyjny. Waga 1,00 jest neutralna; mniejsza zmniejsza, większa zwiększa docelowy udział."},
        {"key":"preference_grid","label":"Preferencje nauczycieli w siatce czasu","scope":"oba","enabled":False,"kind":"soft","priority":3,"value":None,
         "description":"Uwzględnia trzy stany: preferowana, neutralna i niepożądana. Twarde „nie mogę” ustawia administrator przez blokadę."},
        {"key":"prefer_home_group","label":"Najpierw właściwa grupa (siatka nauczyciel × miejsce)","scope":"oba","enabled":True,"kind":"soft","priority":5,"value":None,
         "description":"Steruje macierzą nauczyciel × miejsce dyżuru. Solver najpierw minimalizuje odstępstwa od zapisanych współczynników 0,00–1,00, ale niższa wartość nie jest zakazem i może zostać użyta jako fallback dla pełnej obsady. Bazowe współczynniki nie są automatycznie nadpisywane."},
        {"key":"zone_transition_penalty","label":"Preferuj dyżur blisko sali lekcyjnej","scope":"oba","enabled":False,"kind":"soft","priority":2,"value":None,
         "description":"Preferuje miejsce dyżuru blisko sali lekcyjnej przed lub po przerwie. Dla numerowanych sal/miejsc używa numeru piętra z pierwszej cyfry; ręczna konfiguracja stref nadal może nadpisać tę heurystykę."}
    ]
    for c in defaults:
        if c["key"] not in keys: rows.append(c)
    # v5.50: merge the two historical fairness switches into the canonical lesson-load rule.
    # Preserve the strongest active mode/priority so the migration does not silently weaken fairness.
    if _legacy_lesson or _legacy_workload:
        _fair=next((r for r in rows if r.get("key")=="lesson_load_fairness"),None)
        _sources=[r for r in (_legacy_lesson,_legacy_workload) if r and r.get("enabled")]
        if _fair and _sources:
            _fair["enabled"]=True
            _fair["kind"]="hard" if any(normalize_kind(r.get("kind"))=="hard" for r in _sources) else "soft"
            _fair["priority"]=max(normalize_priority(r.get("priority",2)) for r in _sources)
    # v5.48: opisy są metadanymi interfejsu; aktualizuj także istniejące wiersze.
    for r in rows:
        if r.get("key")=="before_first_short":
            r["label"]="Przed pierwszą lekcją – krótka przerwa 5-10 min (bez 0/1)"
            r["description"]="Dotyczy krótkiej przerwy 5-10 min bezpośrednio przed PIERWSZĄ lekcją nauczyciela danego dnia, ale NIGDY slotu 0/1 (07:25–07:30). Slot 0/1 ma osobną regułę systemową: dyżur może dostać tylko nauczyciel mający lekcję na 1. godzinie."
        elif r.get("key")=="before_first_long":
            r["label"]="Przed pierwszą lekcją – przerwa >10 min — ZAKAZ (bez 0/1)"
            r["description"]="Bezwzględny zakaz dyżuru na przerwie dłuższej niż 10 minut przed PIERWSZĄ lekcją nauczyciela. Nie dotyczy systemowego slotu 0/1, który ma własną logikę kandydatów."
        elif r.get("key")=="lesson_load_fairness":
            r["label"]="Sprawiedliwy podział wg obciążenia dydaktycznego"
            r["description"]="Jeden mechanizm sprawiedliwości: docelowy udział = liczba lekcji w tygodniu × ręczny współczynnik korekcyjny. Waga 1,00 jest neutralna."
        elif r.get("key")=="prefer_home_group":
            r["label"]="Najpierw właściwa grupa (siatka nauczyciel × miejsce)"
            r["description"]="Steruje macierzą nauczyciel × miejsce dyżuru. Solver minimalizuje odstępstwa od zapisanych współczynników 0,00–1,00; 0,00 nadal jest legalnym fallbackiem, a wartości bazowe nie są automatycznie nadpisywane podczas szukania rozwiązania."
        elif r.get("key")=="max_consecutive_duties":
            r["label"]="Maks. dyżurów następujących po sobie"
            r["description"]="Twardy limit odpoczynku między dyżurami. Wartość 1 oznacza: po każdym dyżurze kolejna przerwa musi być wolna. Szybkie szkice Generatora nie mogą automatycznie luzować tej reguły."
        elif r.get("key")=="zone_transition_penalty":
            r["label"]="Preferuj dyżur blisko sali lekcyjnej"
            r["description"]="Preferuje miejsce dyżuru blisko sali lekcyjnej. Dla numerowanych sal i miejsc używa numeru piętra z pierwszej cyfry."
        elif r.get("key")=="preference_grid":
            r["description"]="Preferencje mają trzy stany: preferowana, neutralna i niepożądana. Twarde blokady ustawia administrator."
    for r in rows:
        if r.get("key")=="preserve_school_current":
            r["label"]="Zachowuj istniejący plan"
            r["description"]="W zwykłym przeliczeniu preferuje obecne przydziały szkoły; tryb naprawczy dodatkowo używa ścisłej minimalizacji liczby zmian."
        desc=str(r.get("description") or "")
        desc=re.sub(r"\bHARD\b","Musi być",desc,flags=re.I)
        desc=re.sub(r"\bSOFT\b","Zalecane",desc,flags=re.I)
        r["description"]=desc
    # v5.21: jednorazowa migracja zalecanej wartości domyślnej. 9 daje obecnej puli 1–3
    # tylko 4 miejsca zapasu przy 95 wymaganych dyżurach; 10 daje rozsądny bufor bez luzowania komfortu.
    try: defaults_version=int(state.get("constraint_defaults_version",0) or 0)
    except Exception: defaults_version=0
    if defaults_version<521:
        for r in rows:
            if r.get("key")=="max_week" and r.get("enabled") and normalize_kind(r.get("kind"))=="hard":
                try:
                    if int(r.get("value") or 0)==9: r["value"]=10
                except Exception: pass
        state["constraint_defaults_version"]=521
    _aw=[r for r in rows if r.get("key")=="avoid_wait"]
    for r in _aw:
        r["label"]="Unikaj dodatkowego oczekiwania"
        r["description"]="Nauczyciel nie powinien czekać specjalnie na dyżur ani przychodzić wcześniej tylko na dyżur. W strategii Generatora ta reguła jest sprawdzana na końcu kolejności."
    rows=[r for r in rows if r.get("key")!="avoid_wait"]+_aw
    # v5.60 one-time human-realism migration. The old production value 2 allowed
    # a teacher to cover two adjacent breaks; for the current timetable we proved
    # full 70/70 + 385/385 coverage with value 1, so make a free break mandatory
    # between any two duties. This marker prevents later user edits being reset.
    if not bool(state.get("human_realism_v560_migrated",False)):
        for _r in rows:
            if _r.get("key")=="max_consecutive_duties" and _r.get("enabled") and normalize_kind(_r.get("kind"))=="hard":
                try:
                    if int(_r.get("value") or 1)>1: _r["value"]=1
                except Exception: _r["value"]=1
        state["human_realism_v560_migrated"]=True
    # Matrix preference meta-rule: v5.78 temporarily disabled the legacy home-group row.
    # Restore it once with new teacher×place semantics; later user edits are preserved.
    if not bool(state.get("matrix_place_rule_v578_migrated",False)):
        _mr=next((r for r in rows if r.get("key")=="prefer_home_group"),None)
        if _mr:
            _mr["enabled"]=True
            _mr["kind"]="soft"
            try:
                if int(_mr.get("priority") or 0)<5: _mr["priority"]=5
            except Exception: _mr["priority"]=5
        state["matrix_place_rule_v578_migrated"]=True

    # Learned fast-start migration. Historical NODE00 runs repeatedly reached
    # full plans only after raising these neutral capacity caps. Starting there
    # avoids rediscovering the same non-comfort compromise on every run.
    if not bool(state.get("solver_fast_start_v579_migrated",False)):
        _learned_caps={"max_day_13":5,"max_day_school":5,"max_week":10}
        for _r in rows:
            _k=_r.get("key")
            if _k in _learned_caps and _r.get("enabled") and normalize_kind(_r.get("kind"))=="hard":
                try:
                    _r["value"]=max(int(_r.get("value") or 0),_learned_caps[_k])
                except Exception:
                    _r["value"]=_learned_caps[_k]
        # Visible order mirrors the actual compromise strategy: neutral capacity
        # first, then soft preferences, then comfort, day edges, off-day ban,
        # and waiting absolutely last.
        _order=[
            "no_lesson_overlap","one_place_per_slot","cross_scope_conflict","manual_blocks",
            "preserve_school_current",
            "max_day_13","max_day_school","max_week",
            "prefer_home_group","preference_grid","balance_day","balance_week",
            "zone_transition_penalty","lesson_load_fairness",
            "before_first_short","after_last_short",
            "max_long_week","max_long_day","max_consecutive_duties",
            "before_first_long","after_last_long","offday_duty","avoid_wait"
        ]
        _rank={k:i for i,k in enumerate(_order)}
        rows=sorted(rows,key=lambda r:(_rank.get(str(r.get("key")),10**6),str(r.get("key",""))))
        state["solver_coverage_retry_seconds"]=30
        state["solver_fast_start_v579_migrated"]=True
    state["global_constraints"]=rows
    state["individual_constraints"]=normalize_constraint_rows(state.get("individual_constraints",[]))
    # v5.9: nazwy reguł indywidualnych mówią wprost o krawędzi dnia.
    for r in state["individual_constraints"]:
        if r.get("rule")=="no_before_lesson": r["rule"]="no_before_first_lesson"
        elif r.get("rule")=="no_after_lesson": r["rule"]="no_after_last_lesson"
    state.setdefault("teacher_workload",{})
    for name in ALL: state["teacher_workload"].setdefault(name,1.0)
    state["preference_grid"]=normalize_preference_grid(state.get("preference_grid",{}))
    def _normalize_comment_map(raw):
        out={}
        if not isinstance(raw,dict): return out
        for teacher,rows in raw.items():
            if not isinstance(rows,dict): continue
            clean={}
            for key,value in rows.items():
                text=str(value or "").strip()[:500]
                if text: clean[str(key)]=text
            if clean: out[str(teacher)]=clean
        return out
    state["preference_comments"]=_normalize_comment_map(state.get("preference_comments",{}))
    state["manual_block_comments"]=_normalize_comment_map(state.get("manual_block_comments",{}))
    state.setdefault("repair_guidance",{"accepted_compromises":[]})
    if not isinstance(state.get("repair_guidance"),dict): state["repair_guidance"]={"accepted_compromises":[]}
    state["repair_guidance"]["accepted_compromises"]=list(dict.fromkeys(
        str(x) for x in state["repair_guidance"].get("accepted_compromises",[])
        if str(x) and str(x) not in REMOVED_CONSTRAINT_KEYS))
    _teacher_relax_default=["before_first_short","after_last_short","before_first_long","after_last_long","avoid_wait"]
    state.setdefault("teacher_relax_order",{})
    for _n in ALL:
        _raw=[str(x) for x in (state["teacher_relax_order"].get(_n) or []) if str(x) in _teacher_relax_default]
        _ord=list(dict.fromkeys(_raw+[x for x in _teacher_relax_default if x not in _raw]))
        _ord=[x for x in _ord if x!="avoid_wait"]+["avoid_wait"]
        state["teacher_relax_order"][_n]=_ord
    state.setdefault("teacher_relaxed_rules",{})
    for _n,_vals in list(state["teacher_relaxed_rules"].items()):
        state["teacher_relaxed_rules"][_n]=[str(x) for x in (_vals or []) if str(x) not in REMOVED_CONSTRAINT_KEYS]
    state.setdefault("solver_weight_overrides",{})
    if isinstance(state["solver_weight_overrides"],dict):
        for _k in REMOVED_CONSTRAINT_KEYS: state["solver_weight_overrides"].pop(_k,None)
    state.setdefault("variants",[])
    if isinstance(state["variants"],list):
        for _v in state["variants"]:
            if not isinstance(_v,dict): continue
            if "global_constraints" in _v:
                _v["global_constraints"]=normalize_constraint_rows(_v.get("global_constraints",[]))
            _vs=_v.get("settings")
            if isinstance(_vs,dict):
                if "global_constraints" in _vs:
                    _vs["global_constraints"]=normalize_constraint_rows(_vs.get("global_constraints",[]))
                if "preference_grid" in _vs:
                    _vs["preference_grid"]=normalize_preference_grid(_vs.get("preference_grid",{}))
    state.setdefault("teacher_recalc_requests",[])
    if not isinstance(state["teacher_recalc_requests"],list): state["teacher_recalc_requests"]=[]
    state.setdefault("plan_revision",0)
    state.setdefault("plan_events",[])
    state.setdefault("local_repair_overrides",[])
    if not isinstance(state["plan_events"],list): state["plan_events"]=[]
    if not isinstance(state["local_repair_overrides"],list): state["local_repair_overrides"]=[]
    state.setdefault("location_zones",{})
    state.setdefault("duty_location_zones",{})
    state.setdefault("auto_staffing_by_timetable",{"school":{},"school13":{}})
    if not isinstance(state.get("auto_staffing_by_timetable"),dict): state["auto_staffing_by_timetable"]={"school":{},"school13":{}}
    state["auto_staffing_by_timetable"].setdefault("school",{})
    state["auto_staffing_by_timetable"].setdefault("school13",{})
    state.setdefault("staffing_zero_overrides",{"school13":[],"school":[]})
    if not isinstance(state["staffing_zero_overrides"],dict): state["staffing_zero_overrides"]={"school13":[],"school":[]}
    for _scope in ("school13","school"):
        _vals=state["staffing_zero_overrides"].get(_scope,[])
        state["staffing_zero_overrides"][_scope]=list(dict.fromkeys(str(x) for x in (_vals or []) if str(x)))
    state.setdefault("locked_assignments",[])
    if not isinstance(state.get("locked_assignments"),list):
        state["locked_assignments"]=[]
    for _lock in state["locked_assignments"]:
        if isinstance(_lock,dict):
            _lock["comment"]=str(_lock.get("comment") or "")
    state.setdefault("absent_teachers",[])
    state.setdefault("excluded_teachers",[])
    state["excluded_teachers"]=[n for n in dict.fromkeys(state.get("excluded_teachers") or []) if n in ALL]
    state["freeze_pool_13"]=bool(state.get("freeze_pool_13",False))
    state["freeze_pool_school"]=bool(state.get("freeze_pool_school",False))
    excluded=set(state["excluded_teachers"])
    if "enabled_teachers_13" in state:
        state["enabled_teachers_13"]=[n for n in dict.fromkeys(state.get("enabled_teachers_13") or []) if n in ALL and n not in excluded]
    if "enabled_teachers_school" in state:
        state["enabled_teachers_school"]=[n for n in dict.fromkeys(state.get("enabled_teachers_school") or []) if n in ALL and n not in excluded]
    state.setdefault("published_snapshot",None)
    state.setdefault("operational_plan",None)
    state.setdefault("substitution_history",[])
    try:
        state["solver_seed"]=int(state.get("solver_seed") or 20260918)
    except Exception:
        state["solver_seed"]=20260918
    state.setdefault("deterministic_mode",False)
    state["auto_tune_capacity"]=bool(state.get("auto_tune_capacity",True))
    try: state["solver_internal_workers"]=max(1,min(8,int(state.get("solver_internal_workers",3) or 3)))
    except Exception: state["solver_internal_workers"]=3
    try: state["solver_coverage_seconds"]=max(4,int(state.get("solver_coverage_seconds",8) or 8))
    except Exception: state["solver_coverage_seconds"]=8
    try: state["solver_coverage_retry_seconds"]=max(20,int(state.get("solver_coverage_retry_seconds",45) or 45))
    except Exception: state["solver_coverage_retry_seconds"]=45

    # Dynamiczne stanowiska korytarza 1–3. Identyfikator jest stabilny, nazwa może się zmieniać.
    _names=dict(state.get("station_names") or {})
    _raw_order=list(state.get("station_order_13") or [])
    if not _raw_order:
        _raw_order=[str(k) for k in _names.keys() if str(k).strip()]
    if not _raw_order:
        _raw_order=["A","B"]
    _order=[]
    for _sid in _raw_order:
        _sid=str(_sid or "").strip()
        if _sid and "|" not in _sid and _sid not in _order: _order.append(_sid)
    if not _order: _order=["A","B"]
    state["station_order_13"]=_order
    for _sid in _order:
        _names.setdefault(_sid,f"Punkt {_sid}")
    state["station_names"]={_sid:str(_names.get(_sid) or f"Punkt {_sid}") for _sid in _order}

    _legacy=state.get("min_people_13",{})
    if not isinstance(_legacy,dict): _legacy={}
    _raw_st=state.get("min_people_13_stations",{})
    if not isinstance(_raw_st,dict): _raw_st={}
    _st={}
    _counts={}
    for _b in SEED.get("breaks",[]):
        _base=f"{_b['abbr']}|{_b['label']}"
        _has_any=any(f"{_base}|{_sid}" in _raw_st for _sid in _order)
        if _has_any:
            for _sid in _order:
                try: _v=int(_raw_st.get(f"{_base}|{_sid}",0) or 0)
                except Exception: _v=0
                _st[f"{_base}|{_sid}"]=1 if _v else 0
        else:
            try: _n=int(_legacy.get(_base,min(2,len(_order))))
            except Exception: _n=min(2,len(_order))
            _n=max(0,min(len(_order),_n))
            for _i,_sid in enumerate(_order):
                _st[f"{_base}|{_sid}"]=1 if _i<_n else 0
        _counts[_base]=sum(_st[f"{_base}|{_sid}"] for _sid in _order)
    state["min_people_13_stations"]=_st
    state["min_people_13"]=_counts

    # v5.7: źródłem prawdy dla miejsc i wymaganej obsady szkoły jest stan roboczy.
    # Migracja zachowuje każde miejsce widoczne w planie źródłowym/bieżącym.
    locs=[]
    for source in (
        state.get("school_locations",[]),
        SEED.get("schoolDuty",{}).get("locations",[]),
        [d.get("location") for d in state.get("school_assignments",[])],
    ):
        for loc in source or []:
            loc=str(loc or "").strip()
            if loc and "|" not in loc and loc not in locs: locs.append(loc)
    # Sala gimnastyczna is a normal zone/category with any number of independent
    # duty points. One-time migration turns the old single point into A+B.
    # After migration, users may freely add/remove/rename gym-zone points.
    old_single="Sala gimnastyczna"
    gym_a="Sala gimnastyczna A"
    gym_b="Sala gimnastyczna B"
    gym_migration=not bool(state.get("gym_multi_place_v581_migrated",False))
    had_single=any(str(loc).strip().casefold()==old_single.casefold() for loc in locs)
    if gym_migration:
        locs=[gym_a if str(loc).strip().casefold()==old_single.casefold() else loc for loc in locs]
        locs=list(dict.fromkeys(locs))
        if had_single and gym_a not in locs: locs.append(gym_a)
        if gym_b not in locs: locs.append(gym_b)
        state["gym_multi_place_v581_migrated"]=True
    else:
        # The immutable seed may still contain the legacy single label; never
        # re-introduce it after the one-time migration has completed.
        locs=[loc for loc in locs if str(loc).strip().casefold()!=old_single.casefold()]
    state["school_locations"]=locs
    dz=dict(state.get("duty_location_zones",{}) or {})
    dz.pop(old_single,None)
    if gym_a in locs: dz.setdefault(gym_a,"gym")
    if gym_b in locs: dz.setdefault(gym_b,"gym")
    # Remove stale zone entries for deleted school locations.
    dz={k:v for k,v in dz.items() if k in set(locs)}
    state["duty_location_zones"]=dz

    # Preserve A/B as distinct positions. Old single-gym assignments become A.
    migrated_school=[]
    seen_school=set()
    for _d in state.get("school_assignments",[]) or []:
        _x=dict(_d)
        if str(_x.get("location") or "").strip().casefold()==old_single.casefold():
            _x["location"]=gym_a
        _k=(str(_x.get("abbr") or ""),str(_x.get("slot") or ""),str(_x.get("location") or ""))
        if _k not in seen_school:
            seen_school.add(_k); migrated_school.append(_x)
    state["school_assignments"]=migrated_school
    for _d in state.get("locked_assignments",[]) or []:
        if _d.get("scope")=="szkoła" and str(_d.get("location") or "").strip().casefold()==old_single.casefold():
            _d["location"]=gym_a
    for _d in state.get("individual_constraints",[]) or []:
        if str(_d.get("location") or "").strip().casefold()==old_single.casefold():
            _d["location"]=gym_a

    raw=state.get("min_people_school",{})
    if not isinstance(raw,dict): raw={}
    existing={(d.get("abbr"),d.get("slot"),str(d.get("location") or "")) for d in state.get("school_assignments",[])}
    clean={}
    for br in SEED.get("breaks",[]):
        for loc in locs:
            key=f"{br['abbr']}|{br['label']}|{loc}"
            try:
                if key in raw:
                    v=int(raw[key])
                elif loc==gym_a:
                    v=int(raw.get(f"{br['abbr']}|{br['label']}|{old_single}",0) or 0)
                elif loc==gym_b:
                    v=0
                else:
                    v=1 if (br["abbr"],br["label"],loc) in existing else 0
            except Exception: v=0
            clean[key]=1 if v else 0
    state["min_people_school"]=clean

    duty_places=[]
    for sid in _order:
        duty_places.append({"key":f"1-3|{sid}","label":state["station_names"].get(sid,f"Punkt {sid}"),
                            "legacy_scope":"1-3","location":sid,"zone":"1-3"})
    for loc in locs:
        zone=str(dz.get(loc) or "")
        duty_places.append({"key":f"school|{loc}","label":loc,"legacy_scope":"school","location":loc,
                            "zone":zone})
    state["duty_places"]=duty_places

    raw_group_defaults=state.get("group_place_defaults",{})
    if not isinstance(raw_group_defaults,dict): raw_group_defaults={}
    default_sets={"1-3":set(),"school":set(),"wf":set()}
    for place in duty_places:
        if place.get("zone")=="gym":
            default_sets["wf"].add(place["key"])
        elif place.get("legacy_scope")=="1-3":
            default_sets["1-3"].add(place["key"])
        else:
            default_sets["school"].add(place["key"])
    group_defaults={}
    valid_keys={p["key"] for p in duty_places}
    for g in ("1-3","school","wf"):
        raw=raw_group_defaults.get(g,list(default_sets[g]))
        if not isinstance(raw,list): raw=list(default_sets[g])
        else:
            raw=list(raw)
            if "school|Sala gimnastyczna" in raw:
                raw=[k for k in raw if k!="school|Sala gimnastyczna"]
                if g=="wf":
                    raw.extend(["school|Sala gimnastyczna A","school|Sala gimnastyczna B"])
                else:
                    raw.append("school|Sala gimnastyczna A")
        group_defaults[g]=list(dict.fromkeys(k for k in raw if k in valid_keys))
    state["group_place_defaults"]=group_defaults

    raw_pref=state.get("teacher_place_preferences",{})
    if not isinstance(raw_pref,dict): raw_pref={}
    levels=(0.0,0.25,0.5,0.75,1.0)
    def norm_pref(v,default):
        try: x=max(0.0,min(1.0,float(v)))
        except Exception: x=default
        return min(levels,key=lambda z:abs(z-x))
    pref={}
    for name in ALL:
        row=raw_pref.get(name,{})
        if not isinstance(row,dict): row={}
        else: row=dict(row)
        # Legacy single gym preference becomes A; A/B remain independent.
        _legacy_gym=row.pop("school|Sala gimnastyczna",None)
        if _legacy_gym is not None and "school|Sala gimnastyczna A" not in row:
            row["school|Sala gimnastyczna A"]=_legacy_gym
        g=GROUP.get(name,"school")
        out={}
        for place in duty_places:
            key=place["key"]; scope=place["legacy_scope"]
            default=1.0 if key in set(group_defaults.get(g,[])) else 0.0
            out[key]=norm_pref(row.get(key,default),default)
        pref[name]=out
    state["teacher_place_preferences"]=pref
    state["teacher_place_preference_levels"]=[0.0,0.25,0.5,0.75,1.0]
    state["place_preference_model"]="teacher_x_place_v1"
    # v5.78+: the legacy row is now the meta-rule controlling the exact teacher×place matrix.
    for rr in state.get("global_constraints",[]):
        if rr.get("key")=="prefer_home_group":
            rr["kind"]="soft"
    for n in list(state.get("teacher_relax_order",{})):
        state["teacher_relax_order"][n]=[x for x in state["teacher_relax_order"].get(n,[]) if x!="prefer_home_group"]
    for n in list(state.get("teacher_relaxed_rules",{})):
        state["teacher_relaxed_rules"][n]=[x for x in state["teacher_relaxed_rules"].get(n,[]) if x!="prefer_home_group"]
    return state


ZONE_LABELS={
    "1-3":"Korytarz 1-3",
    "floor2":"II piętro",
    "floor1":"I piętro poza strefą 1–3",
    "ground":"Parter",
    "gym":"Sala gimnastyczna",
}

def _core_13_classes():
    out=set()
    for t in SEED.get("teachers",[]):
        if GROUP.get(t.get("name"))!="1-3": continue
        for ps in (t.get("lessons") or {}).values():
            for vals in (ps or {}).values():
                if not isinstance(vals,list): vals=[vals]
                for x in vals:
                    c=str((x or {}).get("class","")).strip()
                    if c: out.add(c)
    return out

def _room_numeric(room):
    txt=str(room or "").strip()
    return int(txt) if txt.isdigit() else None

def _lesson_zone(x,core_classes=None):
    """Return the physical/organizational zone relevant for duty coverage."""
    raw_room=str((x or {}).get("room") or "").strip()
    room_cf=raw_room.casefold().replace("?","l")
    if room_cf.startswith("sg") or room_cf.startswith("sil"):
        return "gym"
    room=_room_numeric(raw_room)
    if room is None:return None
    cls=str((x or {}).get("class","")).strip()
    core_classes=core_classes if core_classes is not None else _core_13_classes()
    if 120<=room<=139:
        return "1-3" if cls in core_classes else None
    if 200<=room<=299:return "floor2"
    if 100<=room<=199:return "floor1"
    if 0<=room<100:return "ground"
    return None

def _duty_location_zone(state,loc):
    loc=str(loc or "").strip()
    explicit=str((state.get("duty_location_zones",{}) or {}).get(loc) or "").strip()
    if explicit in ZONE_LABELS:return explicit
    n=_room_numeric(loc)
    if n is None:return None
    if 200<=n<=299:return "floor2"
    if 100<=n<=199:
        # School duty points in 1xx are the general first-floor corridor.
        # The separate 1-3 corridor is represented by its own A/B stations.
        return "floor1"
    if 0<=n<100:return "ground"
    return None

def _zone_lesson_periods(zone,abbr):
    core=_core_13_classes(); out=set()
    for t in SEED.get("teachers",[]):
        slots=(t.get("lessons") or {}).get(abbr,{}) or {}
        for ps,vals in slots.items():
            try: p=int(ps)
            except Exception: continue
            if not isinstance(vals,list): vals=[vals]
            if any(_lesson_zone(x,core)==zone for x in vals): out.add(p)
    return out

def _zone_ended_lesson_before_break(zone,abbr,slot):
    br=break_map().get((abbr,slot))
    if not br or br.get("prev") is None:return False
    try:return int(br.get("prev")) in _zone_lesson_periods(zone,abbr)
    except Exception:return False

def _zone_has_lesson_after_break(zone,abbr,slot):
    """True if the zone still has lessons after this break."""
    br=break_map().get((abbr,slot))
    if not br or br.get("next") is None:return False
    try:start=int(br.get("next"))
    except Exception:return False
    return any(p>=start for p in _zone_lesson_periods(zone,abbr))

def _zone_active_at_break(zone,abbr,slot):
    # A zone stays active through internal gaps and also on the break immediately
    # after its final lesson.
    return _zone_ended_lesson_before_break(zone,abbr,slot) or _zone_has_lesson_after_break(zone,abbr,slot)

def _school_lesson_periods(abbr):
    out=set()
    for t in SEED.get("teachers",[]):
        for ps,vals in ((t.get("lessons") or {}).get(abbr,{}) or {}).items():
            try:
                if vals: out.add(int(ps))
            except Exception: pass
    return out

def _school_activity_at_break(abbr,slot):
    br=break_map().get((abbr,slot))
    if not br:return False
    ps=_school_lesson_periods(abbr)
    try:
        if br.get("prev") is not None and int(br.get("prev")) in ps:return True
    except Exception: pass
    try:
        if br.get("next") is not None and any(p>=int(br.get("next")) for p in ps):return True
    except Exception: pass
    return False

def _is_entrance_location(loc):
    return str(loc or "").strip().casefold()=="wejście".casefold()

def _is_gym_location(loc,state=None):
    name=str(loc or "").strip()
    if state is not None:
        try:
            if str((state.get("duty_location_zones",{}) or {}).get(name) or "")=="gym":
                return True
        except Exception:
            pass
    # Legacy/name fallback keeps old snapshots readable, but new logic is zone-driven.
    return name.casefold().startswith("sala gimnastyczna")

def _position_zone_active_13(abbr,slot):
    return _zone_active_at_break("1-3",abbr,slot)

def _sanitize_inactive_13_state(state):
    """Enforce timetable authority for corridor 1-3.

    Once the zone has no lesson after a break and the immediately-post-final-lesson
    break has passed, there is no 1-3 duty position to staff. Manual staffing,
    saved assignments and 1-3 require_slot rules cannot recreate that position.
    """
    state=dict(state or {})
    order=[str(x) for x in (state.get("station_order_13") or ["A","B"]) if str(x)]
    removed=[]
    rows=[]
    for r in state.get("individual_constraints",[]) or []:
        if (isinstance(r,dict) and r.get("rule")=="require_slot"
                and r.get("scope","oba")=="1–3"
                and r.get("day") and r.get("slot")
                and not _position_zone_active_13(r.get("day"),r.get("slot"))):
            removed.append({"type":"require_slot","teacher":r.get("teacher"),"day":r.get("day"),"slot":r.get("slot"),"id":r.get("id")})
            continue
        rows.append(r)
    state["individual_constraints"]=rows

    mins=state.setdefault("min_people_13_stations",{})
    counts=state.setdefault("min_people_13",{})
    for b in SEED.get("breaks",[]):
        if _position_zone_active_13(b["abbr"],b["label"]):
            continue
        base=f"{b['abbr']}|{b['label']}"
        for sid in order:
            key=f"{base}|{sid}"
            if int(mins.get(key,0) or 0):
                removed.append({"type":"staffing","day":b["abbr"],"slot":b["label"],"station":sid})
            mins[key]=0
        counts[base]=0

    for row in state.get("last_13_assignments",[]) or []:
        ab=str(row.get("abbr") or ""); slot=str(row.get("label") or row.get("slot") or "")
        if ab and slot and not _position_zone_active_13(ab,slot):
            if any(a.get("teacher") for a in (row.get("assignments") or [])):
                removed.append({"type":"saved_assignment","day":ab,"slot":slot})
            row["assignments"]=[]
            row["required_people"]=0
            row["complete"]=True
    return state,removed

def _gym_active_at_break(abbr,slot):
    br=break_map().get((abbr,slot))
    if not br:return False
    ps=_zone_lesson_periods("gym",abbr)
    try:
        if br.get("prev") is not None and int(br.get("prev")) in ps:return True
    except Exception: pass
    try:
        if br.get("next") is not None and int(br.get("next")) in ps:return True
    except Exception: pass
    return False

def _position_zone_active_school(state,abbr,slot,loc):
    if _is_entrance_location(loc): return _school_activity_at_break(abbr,slot)
    if _is_gym_location(loc,state): return _gym_active_at_break(abbr,slot)
    z=_duty_location_zone(state,loc)
    # Special unmapped locations remain manually controlled.
    if not z:return True
    return _zone_active_at_break(z,abbr,slot)

def _apply_timetable_staffing(state):
    """Synchronize staffing with timetable activity while preserving explicit manual zeros.

    Rules:
    - a zone is never auto-zeroed on the break immediately after a lesson in that zone;
    - if such a break would have aggregate staffing 0, create a minimum of 1 unless
      every available point was explicitly confirmed as a zero override;
    - "wejście" is active for the whole school day while any lesson is still running,
      starting, or has just ended before the current break.
    """
    normalized=ensure_state_schema(state)
    if normalized is not state:
        state.clear(); state.update(normalized)
    meta=state.setdefault("auto_staffing_by_timetable",{"school":{},"school13":{}})
    m13=meta.setdefault("school13",{}); ms=meta.setdefault("school",{})
    ov=state.setdefault("staffing_zero_overrides",{"school13":[],"school":[]})
    ov13=set(ov.get("school13",[]) or []); ovs=set(ov.get("school",[]) or [])
    changes=[]

    # Separate 1-3 corridor.
    order=_stations_13(state); vals=state.setdefault("min_people_13_stations",{})
    for b in SEED.get("breaks",[]):
        base=f"{b['abbr']}|{b['label']}"; active=_position_zone_active_13(b["abbr"],b["label"])
        for sid in order:
            key=f"{base}|{sid}"; cur=1 if int(vals.get(key,0) or 0) else 0; rec=m13.get(key)
            if not active:
                if cur:
                    m13[key]={"restore":cur,"auto_zero":True}; vals[key]=0
                    changes.append({"scope":"1-3","abbr":b["abbr"],"slot":b["label"],
                                    "location":state.get("station_names",{}).get(sid,sid),
                                    "before":cur,"after":0,"reason":"w strefie 1–3 nie ma już lekcji wymagających dalszego nadzoru"})
                elif rec and rec.get("auto_zero"): pass
            elif rec and rec.get("auto_zero"):
                restore=1 if int(rec.get("restore",1) or 0) else 0
                if cur==0 and restore and key not in ov13:
                    vals[key]=restore
                    changes.append({"scope":"1-3","abbr":b["abbr"],"slot":b["label"],
                                    "location":state.get("station_names",{}).get(sid,sid),
                                    "before":0,"after":restore,"reason":"przywrócono obsadę po ponownym pojawieniu się lekcji"})
                m13.pop(key,None)
        # System minimum after a lesson has just ended in 1-3.
        if _zone_ended_lesson_before_break("1-3",b["abbr"],b["label"]):
            keys=[f"{base}|{sid}" for sid in order]
            if sum(int(vals.get(k,0) or 0) for k in keys)==0:
                candidates=[k for k in keys if k not in ov13]
                if candidates:
                    k=candidates[0]; vals[k]=1; sid=k.rsplit("|",1)[1]
                    changes.append({"scope":"1-3","abbr":b["abbr"],"slot":b["label"],
                                    "location":state.get("station_names",{}).get(sid,sid),
                                    "before":0,"after":1,
                                    "reason":"bezpośrednio po lekcji w strefie 1–3 musi zostać co najmniej 1 osoba"})
    _sync_min13_counts_from_stations(state)

    # Whole-school points and floor zones.
    mins=state.setdefault("min_people_school",{})
    for b in SEED.get("breaks",[]):
        for loc in state.get("school_locations",[]):
            key=f"{b['abbr']}|{b['label']}|{loc}"; cur=1 if int(mins.get(key,0) or 0) else 0
            rec=ms.get(key); active=_position_zone_active_school(state,b["abbr"],b["label"],loc)
            if not active:
                if cur:
                    ms[key]={"restore":cur,"auto_zero":True}; mins[key]=0
                    changes.append({"scope":"szkoła","abbr":b["abbr"],"slot":b["label"],"location":loc,
                                    "before":cur,"after":0,"reason":"w tym punkcie/strefie nie ma już aktywności lekcyjnej"})
                elif rec and rec.get("auto_zero"): pass
            elif rec and rec.get("auto_zero"):
                restore=1 if int(rec.get("restore",1) or 0) else 0
                if cur==0 and restore and key not in ovs:
                    mins[key]=restore
                    changes.append({"scope":"szkoła","abbr":b["abbr"],"slot":b["label"],"location":loc,
                                    "before":0,"after":restore,"reason":"przywrócono obsadę po ponownym pojawieniu się lekcji"})
                ms.pop(key,None)

        # "wejście" has a school-wide minimum for the entire active school day.
        gyms=[loc for loc in state.get("school_locations",[]) if _is_gym_location(loc,state)]
        gym_active=_gym_active_at_break(b["abbr"],b["label"])
        for loc in gyms:
            key=f"{b['abbr']}|{b['label']}|{loc}"
            want=1 if gym_active else 0
            if int(mins.get(key,0) or 0)!=want:
                changes.append({"scope":"szkoła","abbr":b["abbr"],"slot":b["label"],"location":loc,
                                "before":int(mins.get(key,0) or 0),"after":want,
                                "reason":"sala gimnastyczna aktywna według planu WF" if want else "brak aktywności sali gimnastycznej"})
                mins[key]=want

        entrances=[loc for loc in state.get("school_locations",[]) if _is_entrance_location(loc)]
        if _school_activity_at_break(b["abbr"],b["label"]):
            for loc in entrances:
                key=f"{b['abbr']}|{b['label']}|{loc}"
                if int(mins.get(key,0) or 0)==0 and key not in ovs:
                    mins[key]=1
                    changes.append({"scope":"szkoła","abbr":b["abbr"],"slot":b["label"],"location":loc,
                                    "before":0,"after":1,
                                    "reason":"wejście musi mieć dyżur, dopóki w szkole trwa dzień lekcyjny"})

        # Each numbered floor zone gets at least one duty immediately after a lesson
        # in that zone, unless all its points were explicitly confirmed as zero.
        for zone in ("ground","floor1","floor2"):
            if not _zone_ended_lesson_before_break(zone,b["abbr"],b["label"]): continue
            locs=[loc for loc in state.get("school_locations",[]) if _duty_location_zone(state,loc)==zone]
            keys=[f"{b['abbr']}|{b['label']}|{loc}" for loc in locs]
            if keys and sum(int(mins.get(k,0) or 0) for k in keys)==0:
                candidates=[k for k in keys if k not in ovs]
                if candidates:
                    k=candidates[0]; mins[k]=1; loc=k.split("|",2)[2]
                    changes.append({"scope":"szkoła","abbr":b["abbr"],"slot":b["label"],"location":loc,
                                    "before":0,"after":1,
                                    "reason":"bezpośrednio po lekcji w tej strefie musi zostać co najmniej 1 osoba"})
    state["auto_staffing_by_timetable"]=meta
    return changes

def _staffing_zero_warnings(state,scope,proposed):
    """Warnings for an explicit 1 -> 0 staffing change while lessons still justify duty."""
    out=[]
    if scope=="school13":
        current=state.get("min_people_13_stations",{}) or {}
        for key,val in (proposed or {}).items():
            if int(current.get(key,0) or 0)!=1 or int(val or 0)!=0: continue
            parts=str(key).split("|",2)
            if len(parts)!=3: continue
            ab,slot,sid=parts
            if _position_zone_active_13(ab,slot):
                out.append({"key":key,"scope":"1-3","abbr":ab,"slot":slot,
                            "location":state.get("station_names",{}).get(sid,sid),
                            "message":f"{ab} {slot}: według planu strefa 1–3 nadal wymaga nadzoru. Czy na pewno ustawić 0 osób w tym punkcie?"})
    else:
        current=state.get("min_people_school",{}) or {}
        for key,val in (proposed or {}).items():
            if int(current.get(key,0) or 0)!=1 or int(val or 0)!=0: continue
            parts=str(key).split("|",2)
            if len(parts)!=3: continue
            ab,slot,loc=parts
            if _position_zone_active_school(state,ab,slot,loc):
                where="w szkole są jeszcze lekcje" if _is_entrance_location(loc) else "według planu ta strefa nadal wymaga nadzoru"
                out.append({"key":key,"scope":"szkoła","abbr":ab,"slot":slot,"location":loc,
                            "message":f"{ab} {slot} — {loc}: {where}. Czy na pewno ustawić 0 osób dyżuru w tym punkcie?"})
    return out

def _stations_13(state):
    order=[str(x) for x in (state.get("station_order_13") or ["A","B"]) if str(x)]
    return list(dict.fromkeys(order))

def _required_stations_13(state,abbr,slot):
    if not _position_zone_active_13(abbr,slot):
        return []
    order=_stations_13(state)
    vals=state.get("min_people_13_stations",{}) or {}
    base=f"{abbr}|{slot}"
    if any(f"{base}|{sid}" in vals for sid in order):
        return [sid for sid in order if int(vals.get(f"{base}|{sid}",0) or 0)==1]
    try: n=int((state.get("min_people_13",{}) or {}).get(base,min(2,len(order))))
    except Exception: n=min(2,len(order))
    return order[:max(0,min(len(order),n))]

def _sync_min13_counts_from_stations(state):
    order=_stations_13(state)
    vals=state.setdefault("min_people_13_stations",{})
    counts={}
    for b in SEED.get("breaks",[]):
        base=f"{b['abbr']}|{b['label']}"
        counts[base]=sum(1 for sid in order if int(vals.get(f"{base}|{sid}",0) or 0)==1)
    state["min_people_13"]=counts
    return counts

def _set_required_13_count(state,abbr,slot,count):
    order=_stations_13(state)
    if not _position_zone_active_13(abbr,slot):
        n=0
    else:
        try: n=max(0,min(len(order),int(count)))
        except Exception: n=min(2,len(order))
    vals=state.setdefault("min_people_13_stations",{})
    base=f"{abbr}|{slot}"
    for i,sid in enumerate(order):
        vals[f"{base}|{sid}"]=1 if i<n else 0
    _sync_min13_counts_from_stations(state)

def _hard_global_row(state,key):
    return next((r for r in state.get("global_constraints",[])
                 if r.get("key")==key and r.get("enabled") and normalize_kind(r.get("kind"))=="hard"),None)

def _required_13_counts(state):
    by_day=defaultdict(int); total=0
    for b in SEED.get("breaks",[]):
        need=len(_required_stations_13(state,b["abbr"],b["label"]))
        total+=need;by_day[b["abbr"]]+=need
    return total,dict(by_day)

def _required_school_counts(state):
    by_day=defaultdict(int); total=0
    vals=state.get("min_people_school",{})
    for b in SEED.get("breaks",[]):
        for loc in state.get("school_locations",[]):
            try: need=1 if int(vals.get(f"{b['abbr']}|{b['label']}|{loc}",0) or 0) else 0
            except Exception: need=0
            total+=need;by_day[b["abbr"]]+=need
    return total,dict(by_day)

def _auto_tune_capacity(state,scope):
    """Only raise mathematically insufficient hard capacity limits; never relax comfort rules."""
    if not state.get("auto_tune_capacity",True): return state,[]
    state=ensure_state_schema(state)
    changes=[]
    excluded=set(state.get("excluded_teachers",[]))
    if scope=="1–3":
        enabled=[n for n in state.get("enabled_teachers_13",[]) if n in ALL and n not in excluded]
        total,by_day=_required_13_counts(state)
        day_key="max_day_13"
    else:
        enabled=[n for n in _school_pool(state.get("enabled_teachers_school",[])) if n in ALL and n not in excluded]
        total,by_day=_required_school_counts(state)
        day_key="max_day_school"
    if not enabled or total<=0: return state,changes

    # Weekly lower bound. This is a capacity correction only; no waiting/day-edge rule is changed.
    wk=_hard_global_row(state,"max_week")
    if wk:
        cur=max(0,int(wk.get("value") or 0))
        required_min=max(1,math.ceil(total/len(enabled)))
        if cur<required_min:
            wk["value"]=required_min
            changes.append({"key":"max_week","before":cur,"after":required_min,
                            "reason":f"minimalna pojemność: {total} pozycji / {len(enabled)} nauczycieli"})

    # Daily aggregate lower bound for the selected scope.
    dr=_hard_global_row(state,day_key)
    if dr and by_day:
        cur=max(0,int(dr.get("value") or 0))
        required_min=max(1,max(math.ceil(v/len(enabled)) for v in by_day.values()))
        if cur<required_min:
            dr["value"]=required_min
            changes.append({"key":day_key,"before":cur,"after":required_min,
                            "reason":"minimalna pojemność dzienna wymaganej obsady"})
    return state,changes

_PROFILE_STATE_KEYS=("auto_tune_capacity","solver_internal_workers","solver_coverage_seconds",
                     "solver_coverage_retry_seconds","solver_seed","deterministic_mode")

def _load_settings_profiles():
    try:
        raw=json.loads(SETTINGS_PROFILES_PATH.read_text(encoding="utf-8")) if SETTINGS_PROFILES_PATH.exists() else {}
    except Exception:
        raw={}
    if not isinstance(raw,dict): raw={}
    raw.setdefault("profiles",[])
    raw.setdefault("default_id",None)
    before=json.dumps(raw,ensure_ascii=False,sort_keys=True,default=str)
    for p in raw.get("profiles",[]):
        if not isinstance(p,dict): continue
        settings=p.get("settings")
        if isinstance(settings,dict) and "global_constraints" in settings:
            settings["global_constraints"]=normalize_constraint_rows(settings.get("global_constraints",[]))
    after=json.dumps(raw,ensure_ascii=False,sort_keys=True,default=str)
    if before!=after:
        SETTINGS_PROFILES_PATH.parent.mkdir(parents=True,exist_ok=True)
        SETTINGS_PROFILES_PATH.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")
    return raw

def _save_settings_profiles(raw):
    SETTINGS_PROFILES_PATH.parent.mkdir(parents=True,exist_ok=True)
    SETTINGS_PROFILES_PATH.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")

def _settings_snapshot(state):
    return {
        "global_constraints":_copy.deepcopy(state.get("global_constraints",[])),
        "individual_constraints":_copy.deepcopy(state.get("individual_constraints",[])),
        **{k:_copy.deepcopy(state.get(k)) for k in _PROFILE_STATE_KEYS}
    }

def _ensure_comfort_profile():
    raw=_load_settings_profiles()
    if not raw["profiles"]:
        state=load_state()
        pid="comfort-default"
        raw["profiles"].append({"id":pid,"name":"Komfort nauczycieli","created_at":datetime.now().isoformat(timespec="seconds"),
                                "settings":_settings_snapshot(state)})
        raw["default_id"]=pid
        _save_settings_profiles(raw)
    return raw

class MCMF:
    def __init__(self):
        self.g=defaultdict(list)
    def add(self,u,v,cap,cost,tag=None):
        a=[v,len(self.g[v]),cap,cost,tag]
        b=[u,len(self.g[u]),0,-cost,None]
        self.g[u].append(a); self.g[v].append(b)
    def flow(self,s,t,want):
        flow=0; cost=0
        pot=defaultdict(int)
        while flow<want:
            dist=defaultdict(lambda:10**18); prev={}
            dist[s]=0; pq=[(0,s)]
            while pq:
                d,u=heapq.heappop(pq)
                if d!=dist[u]: continue
                for i,e in enumerate(self.g[u]):
                    v,rev,cap,c,tag=e
                    if cap<=0: continue
                    nd=d+c+pot[u]-pot[v]
                    if nd<dist[v]:
                        dist[v]=nd; prev[v]=(u,i); heapq.heappush(pq,(nd,v))
            if t not in prev: break
            for n,d in list(dist.items()):
                if d<10**18: pot[n]+=d
            add=1; v=t
            while v!=s:
                u,i=prev[v]; add=min(add,self.g[u][i][2]); v=u
            v=t
            while v!=s:
                u,i=prev[v]; e=self.g[u][i]
                e[2]-=add; self.g[v][e[1]][2]+=add; cost+=add*e[3]; v=u
            flow+=add
        return flow,cost

def solve_positions_legacy(state,scope,positions,enabled,other_assignments,preserve_map=None):
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
            if is_after_last_lesson(n,br):
                try:
                    long_min=LONG_BREAK_MINUTES
                except Exception:
                    long_min=15
                key="after_last_long" if int(br.get("minutes",0) or 0)>=long_min else "after_last_short"
                hard,pen=global_rule_effect(cs,key,1,2500 if key=="after_last_long" else 100)
                if hard:
                    continue
                cost+=pen

            wait=wait_periods(n,br)
            # Stały wymóg organizacyjny: nie rozważamy dyżuru wymagającego
            # oczekiwania dwóch lub więcej okresów lekcyjnych.
            if wait>=2:
                continue
            if wait>0:

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

def solve_positions(state,scope,positions,enabled,other_assignments,preserve_map=None,coverage_only=False,repair_mode=False):
    return solve_positions_ortools(
        state,scope,positions,enabled,other_assignments,preserve_map,
        SEED,GROUP,coverage_only=coverage_only,repair_mode=repair_mode
    )

def _solve_school_decomposed_v578(state,positions,enabled,other_assignments,preserve_map=None,coverage_only=False,repair_mode=False):
    """Solve exclusive gym positions first, then ordinary school positions."""
    gym=[p for p in (positions or []) if _is_gym_location(p.get("location"),state)]
    regular=[p for p in (positions or []) if not _is_gym_location(p.get("location"),state)]
    if not gym or not regular:
        return solve_positions(state,"szkoła",positions,enabled,other_assignments,
                               preserve_map=preserve_map,coverage_only=coverage_only,repair_mode=repair_mode)

    preserve_map=preserve_map or {}
    pg={k:v for k,v in preserve_map.items() if _is_gym_location(k[2] if isinstance(k,tuple) and len(k)>2 else "",state)}
    pr={k:v for k,v in preserve_map.items() if not _is_gym_location(k[2] if isinstance(k,tuple) and len(k)>2 else "",state)}

    ga,gw,gm,gmeta=solve_positions(state,"szkoła",gym,enabled,other_assignments,
                                   preserve_map=pg,coverage_only=coverage_only,repair_mode=repair_mode)
    fixed_gym=_flat_school_other(ga)
    ra,rw,rm,rmeta=solve_positions(state,"szkoła",regular,enabled,list(other_assignments or [])+fixed_gym,
                                   preserve_map=pr,coverage_only=coverage_only,repair_mode=repair_mode)

    gd=(gmeta.get("diagnostics",{}) or {}); rd=(rmeta.get("diagnostics",{}) or {})
    def merged_status(key):
        vals=[x for x in (gd.get(key),rd.get(key)) if x is not None]
        if not vals:return None
        return "OPTIMAL" if all(x=="OPTIMAL" for x in vals) else next((x for x in vals if x!="OPTIMAL"),vals[0])
    diag=dict(rd)
    diag["decomposed_school_v578"]=True
    diag["gym_required"]=len(gym); diag["gym_filled"]=len(gym)-len(gm); diag["gym_missing"]=len(gm)
    diag["gym_diagnostics"]=_copy.deepcopy(gd)
    diag["ordinary_required"]=len(regular);diag["ordinary_filled"]=len(regular)-len(rm);diag["ordinary_missing"]=len(rm)
    diag["inconclusive"]=bool(gd.get("inconclusive") or rd.get("inconclusive"))
    for key in ("after_last_long_lex_status","before_first_long_lex_status","wait_lex_status","place_preference_status"):
        diag[key]=merged_status(key)
    diag["wf_fallback_status"]=rd.get("wf_fallback_status")
    diag["wf_fallback_optimized"]=rd.get("wf_fallback_optimized")
    diag["minimum_wf_fallback_assignments"]=rd.get("minimum_wf_fallback_assignments")
    diag["wf_fallback_scope"]="szkoła"
    return ga+ra,gw+rw,gm+rm,{
        "cost":float(gmeta.get("cost",0) or 0)+float(rmeta.get("cost",0) or 0),
        "diagnostics":diag,
    }

def locked_teacher(state,scope,abbr,slot,location):
    for r in state.get("locked_assignments",[]):
        if r.get("scope")==scope and r.get("abbr")==abbr and r.get("slot")==slot and str(r.get("location",""))==str(location or ""):
            return r.get("teacher")
    return None

def preserve_13_map(rows):
    out={}
    for r in rows or []:
        for a in r.get("assignments",[]):
            if a.get("teacher"): out[(r.get("abbr"),r.get("label"),a.get("station"))]=a.get("teacher")
    return out

def required_slot_rules(state,scope,kind="hard"):
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
        if scope=="1–3" and not _position_zone_active_13(r.get("day"),r.get("slot")):
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

def break_map():
    return {(b["abbr"],b["label"]):b for b in SEED["breaks"]}


FIXED_HARD_KEYS={"no_lesson_overlap","one_place_per_slot","cross_scope_conflict","manual_blocks"}
# v5.60: „human realism” guardrails stay hard in every quick/live draft. They may still
# be diagnosed by the main generator, but a broad jump is never allowed to obtain a
# visually full plan by turning a teacher into a break-duty machine.
HUMAN_REALISM_HARDENED_V560={"max_consecutive_duties","max_day_13","max_day_school","max_week","max_long_day","max_long_week"}
NEVER_AUTO_RELAX_KEYS=FIXED_HARD_KEYS|{"offday_duty"}|HUMAN_REALISM_HARDENED_V560

# v5.53: preflight may only soften comfort/capacity rules that are PROVEN
# impossible for the current timetable/required staffing. It never weakens
# system rules, manual blocks or the no-duty-on-offday rule.
PREFLIGHT_EDGE_RELAX_COST_V553={
    "prefer_home_group":10,
    "before_first_short":20,
    "after_last_short":20,
    "before_first_long":60,
    "after_last_long":70,
    "avoid_wait":1000,
}
PREFLIGHT_NUMERIC_RELAX_KEYS_V553={
    "max_day_13","max_day_school","max_week","max_long_day","max_long_week"
}

def _preflight_soften_global_v553(state,key):
    row=_global_row(state,key)
    if not row or not row.get("enabled") or normalize_kind(row.get("kind"))!="hard":
        return False
    if key in NEVER_AUTO_RELAX_KEYS:
        return False
    row["kind"]="soft"
    row["priority"]=5
    return True

def _active_auto_relaxations_v554(state,previous,new_changes):
    """Keep provenance visible while an auto-softened rule is still active as soft priority 5."""
    merged={}
    for ch in list(previous or [])+list(new_changes or []):
        if not isinstance(ch,dict):
            continue
        if ch.get("constraint_type")=="individual":
            token=("individual",str(ch.get("id") or ""))
        else:
            token=("global",str(ch.get("key") or ""))
        if token[1]:
            merged[token]=_copy.deepcopy(ch)
    active=[]
    for (kind,ident),ch in merged.items():
        if kind=="individual":
            row=next((r for r in state.get("individual_constraints",[])
                      if str(r.get("id") or "")==ident),None)
        else:
            row=_global_row(state,ident)
        if not row or not row.get("enabled",True):
            continue
        if normalize_kind(row.get("kind"))!="soft":
            continue
        try:
            priority=int(row.get("priority") or 0)
        except Exception:
            priority=0
        if priority!=5:
            continue
        active.append(ch)
    return active

def _school_pool(names):
    """Lista jawnie dopuszczonych nauczycieli szkoły; grupa 1–3 może wejść tylko po ręcznym dodaniu."""
    return [n for n in dict.fromkeys(names or []) if n in ALL]


def _locked_wf_teachers_v577(state,scope):
    out=set()
    aliases={scope}
    if scope=="szko\u0142a": aliases.add("school")
    if scope=="school": aliases.add("szko\u0142a")
    for r in state.get("locked_assignments",[]) or []:
        if r.get("scope") in aliases and GROUP.get(r.get("teacher"))=="wf":
            out.add(r.get("teacher"))
    return out

def _primary_pool_without_wf_v577(state,names,scope):
    """Automatic phases exclude WF; explicit admin locks remain legal."""
    locked=_locked_wf_teachers_v577(state,scope)
    return [n for n in dict.fromkeys(names or []) if n in ALL and (GROUP.get(n)!="wf" or n in locked)]

def _wf_count_v577(assignments):
    return sum(1 for a in (assignments or []) if a.get("teacher") and GROUP.get(a.get("teacher"))=="wf")

def _locked_wf_assignment_count_v577(state):
    return sum(1 for r in (state.get("locked_assignments",[]) or [])
               if GROUP.get(r.get("teacher"))=="wf")

def _diag_positions_13(state):
    req_rules=required_slot_rules(state,"1–3")
    required_by=defaultdict(list)
    for r in req_rules:
        k=(r["day"],r["slot"])
        if r["teacher"] not in required_by[k]: required_by[k].append(r["teacher"])
    positions=[]
    for b in SEED["breaks"]:
        stations=_required_stations_13(state,b["abbr"],b["label"])
        names=required_by.get((b["abbr"],b["label"]),[])
        for i,st in enumerate(stations):
            x={"day":b["day"],"abbr":b["abbr"],"slot":b["label"],"station":st,"break":b}
            required=names[i] if i<len(names) else None
            locked=locked_teacher(state,"1–3",b["abbr"],b["label"],st)
            if locked:
                x["admin_lock"]=locked
            if required and locked and required!=locked:
                x["required_teacher"]="__CONFLICT__"
                x["admin_lock_conflict"]={"locked":locked,"required":required}
            elif locked or required:
                x["required_teacher"]=locked or required
            positions.append(x)
    return positions,state.get("school_assignments",[]),preserve_13_map(state.get("last_13_assignments",[]))

def _school_positions(state,current=None,include_locks=True):
    state=ensure_state_schema(state)
    current=list(current if current is not None else state.get("school_assignments",[]))
    current_map={(d.get("abbr"),d.get("slot"),str(d.get("location") or "")):d.get("teacher") for d in current}
    req_rules=required_slot_rules(state,"szkoła"); used=set(); positions=[]; preserve={}; conflicts=[]
    mins=state.get("min_people_school",{})
    for b in SEED.get("breaks",[]):
        for loc in state.get("school_locations",[]):
            key=f"{b['abbr']}|{b['label']}|{loc}"
            if int(mins.get(key,0) or 0)!=1: continue
            if not _position_zone_active_school(state,b["abbr"],b["label"],loc): continue
            p={"day":b["day"],"abbr":b["abbr"],"slot":b["label"],"location":loc,"break":b}
            exact=next((r for r in req_rules if r["id"] not in used and r["day"]==b["abbr"] and r["slot"]==b["label"] and r["location"]==loc),None)
            generic=next((r for r in req_rules if r["id"] not in used and r["day"]==b["abbr"] and r["slot"]==b["label"] and not r["location"]),None)
            rr=exact or generic
            locked=locked_teacher(state,"szkoła",b["abbr"],b["label"],loc) if include_locks else None
            if locked: p["admin_lock"]=locked
            if rr: used.add(rr["id"])
            if rr and locked and rr["teacher"]!=locked:
                p["required_teacher"]="__CONFLICT__"
                conflicts.append({"teacher":rr["teacher"],"day":b["abbr"],"slot":b["label"],"location":loc,"message":f"Blokada {locked} koliduje z wymaganym nauczycielem {rr['teacher']}."})
            elif locked or rr:
                chosen=locked or rr["teacher"]
                p["required_teacher"]=chosen
                if chosen in set(state.get("excluded_teachers",[])):
                    conflicts.append({"teacher":chosen,"day":b["abbr"],"slot":b["label"],"location":loc,
                                      "message":f"{chosen}: wykluczony ze wszystkich dyżurów, ale ma stały/wymagany przydział."})
            positions.append(p)
            preserve[(b["abbr"],b["label"],loc)]=current_map.get((b["abbr"],b["label"],loc))
    unused=[r for r in req_rules if r["id"] not in used]
    return positions,preserve,unused,conflicts

def _diag_positions_school(state):
    positions,preserve,unused,conflicts=_school_positions(state)
    other=[]
    for row in state.get("last_13_assignments",[]):
        for a in row.get("assignments",[]):
            if a.get("teacher"): other.append({"day":row["day"],"abbr":row["abbr"],"slot":row["label"],"location":"1–3 "+a["station"],"teacher":a["teacher"]})
    return positions,other,preserve

def _coverage(state,scope,enabled,other_override=None,preserve_override="DEFAULT",optimize=False):
    excluded=set(state.get("excluded_teachers",[]))
    enabled=[n for n in enabled if n not in excluded]
    if scope=="1–3": positions,other,preserve=_diag_positions_13(state)
    else: positions,other,preserve=_diag_positions_school(state)
    if other_override is not None: other=other_override
    if preserve_override!="DEFAULT": preserve=preserve_override
    if scope in ("szkoła","school"):
        a,w,missing,meta=_solve_school_decomposed_v578(
            state,positions,set(enabled),other,preserve_map=preserve,
            coverage_only=not optimize,repair_mode=optimize
        )
    else:
        a,w,missing,meta=solve_positions(
            state,scope,positions,set(enabled),other,preserve_map=preserve,
            coverage_only=not optimize,repair_mode=optimize
        )
    diag=meta.get("diagnostics",{})
    return {"required":len(positions),"filled":len(positions)-len(missing),"missing":len(missing),
            "inconclusive":bool(diag.get("inconclusive")),"diagnostics":diag,"assignments":a,"waits":w}

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
        elif token.startswith("p:"):
            parts=token[2:].split("|",2)
            if len(parts)==3:
                teacher,abbr,slot=parts
                prefs=out.setdefault("preference_grid",{}).setdefault(teacher,{})
                prefs.pop(f"{abbr}|{slot}",None)
    return out

RELAX_COST={
    "max_day_13":260,"max_day_school":260,"max_week":320,
    "max_long_week":420,"max_long_day":520,
    "before_first_short":650,"after_last_short":650,
    "avoid_wait":1200
}

def _token_relaxes_rule_v537(token,key):
    tok=str(token or "")
    return (tok==f"g:{key}" or tok==f"gsoft:{key}" or
            (tok.startswith("trelax:") and tok.endswith("|"+key)))

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

def _teacher13_wait_profile(state,name,baseline=None):
    """Comfort-first profile for extending the 1–3 pool.
    Zero-wait coverage is the primary signal; 1-period waits are only secondary.
    """
    wanted=None
    if baseline:
        wanted={(u.get("position",{}).get("abbr"),u.get("position",{}).get("slot"))
                for u in baseline.get("school13",{}).get("diagnostics",{}).get("unresolved",[])}
        wanted={x for x in wanted if x[0] and x[1]}
    seen=set(); zero=[]; one=[]; longwait=[]; offday=[]
    for br in SEED.get("breaks",[]):
        key=(br.get("abbr"),br.get("label"))
        if wanted is not None and key not in wanted: continue
        if key in seen: continue
        seen.add(key)
        w=wait_periods(name,br)
        if w==0: zero.append(key)
        elif w==1: one.append(key)
        elif w>=9: offday.append(key)
        else: longwait.append(key)
    return {"zero_wait":len(zero),"one_wait":len(one),"long_wait":len(longwait),"offday":len(offday),
            "zero_slots":zero,"one_slots":one}

def _flat13_other(assignments):
    return [{"day":a["day"],"abbr":a["abbr"],"slot":a["slot"],"location":"1–3 "+a["station"],"teacher":a["teacher"]}
            for a in assignments if a.get("teacher")]

def _teacher_sort_key(name):
    parts=str(name or "").strip().split()
    if len(parts)<2: return (parts[0].casefold() if parts else "","")
    return (" ".join(parts[1:]).casefold(),parts[0].casefold())

def _duty_rec(teacher,scope,abbr,slot,place,wait=0):
    return {"teacher":teacher or "","scope":scope,"abbr":abbr,"slot":slot,"place":place or "","wait":int(wait or 0)}

def _map13_from_state(state):
    m={}
    for r in state.get("last_13_assignments",[]):
        for a in r.get("assignments",[]):
            m["13|"+r["abbr"]+"|"+r["label"]+"|"+a["station"]]=_duty_rec(a.get("teacher"),"1–3",r["abbr"],r["label"],a["station"],a.get("wait",0))
    return m

def _map_school_from_state(state):
    return {"S|"+d["abbr"]+"|"+d["slot"]+"|"+d["location"]:_duty_rec(d.get("teacher"),"szkoła",d["abbr"],d["slot"],d["location"],d.get("wait",0)) for d in state.get("school_assignments",[])}

def _map13_flat(arr):
    return {"13|"+a["abbr"]+"|"+a["slot"]+"|"+a["station"]:_duty_rec(a.get("teacher"),"1–3",a["abbr"],a["slot"],a["station"],a.get("wait",0)) for a in arr}

def _map_school_flat(arr):
    return {"S|"+a["abbr"]+"|"+a["slot"]+"|"+a["location"]:_duty_rec(a.get("teacher"),"szkoła",a["abbr"],a["slot"],a["location"],a.get("wait",0)) for a in arr}

def _teacher_changes(old_map,new_map):
    from collections import defaultdict
    ch=defaultdict(lambda:{"added":0,"removed":0,"added_duties":[],"removed_duties":[]})
    changed=0
    for k in set(old_map)|set(new_map):
        old=old_map.get(k,{}) or {}; new=new_map.get(k,{}) or {}
        if isinstance(old,str): old={"teacher":old}
        if isinstance(new,str): new={"teacher":new}
        oldn=old.get("teacher",""); newn=new.get("teacher","")
        if oldn==newn: continue
        changed+=1
        if oldn:
            ch[oldn]["removed"]+=1
            ch[oldn]["removed_duties"].append({k:v for k,v in old.items() if k!="teacher"})
        if newn:
            ch[newn]["added"]+=1
            ch[newn]["added_duties"].append({k:v for k,v in new.items() if k!="teacher"})
    rows=[]
    for name,v in ch.items():
        if v["added"] or v["removed"]: rows.append({"teacher":name,**v})
    rows.sort(key=lambda x:_teacher_sort_key(x["teacher"]))
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
        trial13=_coverage(state,"1–3",pool,other_override=[],optimize=False)
        if trial13["missing"]: continue
        trial_school=_coverage(state,"szkoła",es,other_override=_flat13_other(trial13["assignments"]),optimize=False)
        if trial_school["missing"]: continue
        c13=_coverage(state,"1–3",pool,other_override=[],optimize=True)
        school=_coverage(state,"szkoła",es,other_override=_flat13_other(c13["assignments"]),optimize=True)
        if school["missing"]:
            c13,school=trial13,trial_school
        used_general=sorted({a.get("teacher") for a in c13["assignments"] if a.get("teacher") and GROUP.get(a.get("teacher"))=="school"},key=_teacher_sort_key)
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
        relaxed=_relax(state,[c["token"]])
        trial=_coverage(relaxed,scope,enabled,optimize=False)
        if trial["missing"]==0:
            cov=_coverage(relaxed,scope,enabled,optimize=True)
            row={"action":"relax","tokens":[c["token"]],"changes":[c],
                 "coverage":{k:cov[k] for k in ("required","filled","missing")},"human_cost":c["human_cost"]}
            old=_map13_from_state(state) if scope=="1–3" else _map_school_from_state(state)
            new=_map13_flat(cov["assignments"]) if scope=="1–3" else _map_school_flat(cov["assignments"])
            row["teacher_changes"]=_teacher_changes(old,new)
            row["title"]="Zmień jedną regułę"
            row["explanation"]="Pełna obsada po zmianie wskazanej reguły z „Musi być” na „Zalecane”."
            full.append(row)
        tested.append((c,trial))
    if not full:
        best=sorted(tested,key=lambda x:(x[1]["missing"],x[0]["human_cost"]))[:7]
        pool=[x[0] for x in best]
        for a,b in itertools.combinations(pool,2):
            relaxed=_relax(state,[a["token"],b["token"]])
            trial=_coverage(relaxed,scope,enabled,optimize=False)
            if trial["missing"]: continue
            cov=_coverage(relaxed,scope,enabled,optimize=True)
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

@app.post("/api/diagnostics/repair")
def diagnostics_repair(x:dict):
    s=load_state()
    if "global" in x: s["global_constraints"]=normalize_constraint_rows(x.get("global",[]))
    if "individual" in x: s["individual_constraints"]=normalize_constraint_rows(x.get("individual",[]))
    if "min_people_13" in x: s["min_people_13"]=dict(x.get("min_people_13") or {})
    if "min_people_school" in x: s["min_people_school"]=dict(x.get("min_people_school") or {})
    if "school_locations" in x: s["school_locations"]=list(x.get("school_locations") or [])
    if "manual_blocks" in x: s["manual_blocks"]=dict(x.get("manual_blocks") or {})
    if "excluded_teachers" in x: s["excluded_teachers"]=list(x.get("excluded_teachers") or [])
    if "freeze_pool_13" in x: s["freeze_pool_13"]=bool(x.get("freeze_pool_13"))
    if "freeze_pool_school" in x: s["freeze_pool_school"]=bool(x.get("freeze_pool_school"))
    if "last_13_assignments" in x: s["last_13_assignments"]=list(x.get("last_13_assignments") or [])
    if "school_assignments" in x: s["school_assignments"]=list(x.get("school_assignments") or [])
    s=ensure_state_schema(s)
    inactive=set(s.get("excluded_teachers",[]))|set(s.get("absent_teachers",[]))
    e13=[n for n in ALL if n not in inactive]
    es=list(e13)
    return {"school13":_repair_for_scope(s,"1–3",e13,es),"school":_repair_for_scope(s,"szkoła",es,e13)}


# ---------- v5.12 progressive / parallel repair search ----------
import copy as _copy
import math as _math
import threading as _threading
import time as _time
import uuid as _uuid
import hashlib as _hashlib
import os as _os
import socket as _socket
import subprocess as _subprocess
import sys as _sys
from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor, wait as _fwait, FIRST_COMPLETED as _FIRST_COMPLETED
import repair_farm as _repair_farm

SHARED_FARM_ROOT=Path(r"C:\DutySolverDemo\DEMO-WorkerFarm")
SHARED_FARM_ROOT.mkdir(parents=True,exist_ok=True)
FARM_CONFIG_PATH=SHARED_FARM_ROOT/"repair_farm_config.json"
ACTIVE_RUNTIME_PATH=SHARED_FARM_ROOT/"active_runtime.json"

def _seed_sha():
    return _hashlib.sha256((ROOT/"data"/"seed.json").read_bytes()).hexdigest()

def _default_farm_config():
    return {"enabled":False,"port":8093,"local_workers":4,"token":secrets.token_urlsafe(32),"broker_pid":0}

def _farm_config():
    if not FARM_CONFIG_PATH.exists():
        cfg=_default_farm_config(); FARM_CONFIG_PATH.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8"); return cfg
    try: cfg=json.loads(FARM_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except Exception: cfg=_default_farm_config()
    d=_default_farm_config()
    for k,v in d.items(): cfg.setdefault(k,v)
    cfg["local_workers"]=max(1,min(8,int(cfg.get("local_workers",4) or 4)))
    cfg["port"]=int(cfg.get("port",8093) or 8093)
    return cfg

def _save_farm_config(cfg):
    FARM_CONFIG_PATH.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")

def _node_lan_ip():
    try:
        for info in _socket.getaddrinfo(_socket.gethostname(),None,_socket.AF_INET):
            ip=info[4][0]
            if ip.startswith("192.0.2."): return ip
    except Exception: pass
    return "192.0.2.10"

def _pid_alive(pid):
    if not pid: return False
    try:
        _os.kill(int(pid),0); return True
    except Exception: return False

def _broker_listening(port=None):
    port=int(port or _farm_config().get("port",8093))
    try:
        with _socket.create_connection(("127.0.0.1",port),timeout=.35):
            return True
    except Exception:
        return False

def _broker_runtime_ok(port):
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/health",timeout=1.5) as r:
            x=json.loads(r.read().decode("utf-8"))
        return (str(x.get("protocol_version") or "")==WORKER_PROTOCOL_VERSION
                and Path(str(x.get("runtime_root") or "")).resolve()==ROOT.resolve()
                and str(x.get("seed_sha") or "")==_seed_sha())
    except Exception:
        return False

def _write_active_runtime(cfg=None):
    try:
        x={"planner_version":PLANNER_VERSION,"runtime_root":str(ROOT.resolve()),
           "worker_protocol_version":WORKER_PROTOCOL_VERSION,
           "worker_package_version":WORKER_PACKAGE_VERSION,
           "farm_db":str(_repair_farm.DB),
           "farm_config":str(FARM_CONFIG_PATH),
           "broker_pid":int((cfg or {}).get("broker_pid") or 0),
           "at":datetime.now().isoformat(timespec="seconds")}
        ACTIVE_RUNTIME_PATH.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
    except Exception:
        pass

def _start_worker_broker():
    cfg=_farm_config()
    pid=cfg.get("broker_pid")
    if _pid_alive(pid) and _broker_listening(cfg.get("port")) and _broker_runtime_ok(cfg.get("port")):
        _write_active_runtime(cfg); return cfg
    # A broker from another planner build must never survive an upgrade,
    # even if its PID was not copied into the current config.
    if _broker_listening(cfg.get("port")) and not _broker_runtime_ok(cfg.get("port")):
        try:
            ps=f"$p=(Get-NetTCPConnection -LocalPort {int(cfg.get('port',8093))} -State Listen -ErrorAction SilentlyContinue).OwningProcess;if($p){{Stop-Process -Id $p -Force}}"
            _subprocess.run(["powershell.exe","-NoProfile","-Command",ps],capture_output=True,timeout=8)
        except Exception:pass
        _time.sleep(.5)
    elif _pid_alive(pid):
        try:_subprocess.run(["taskkill","/PID",str(pid),"/T","/F"],capture_output=True,timeout=8)
        except Exception:pass
        _time.sleep(.4)
    cfg["broker_pid"]=0
    cmd=[_sys.executable,str(ROOT/"worker_broker.py"),"--port",str(cfg["port"]),"--token",cfg["token"],
         "--version",WORKER_PROTOCOL_VERSION,"--seed-sha",_seed_sha()]
    flags=getattr(_subprocess,"CREATE_NO_WINDOW",0)
    p=_subprocess.Popen(cmd,cwd=str(ROOT),stdout=_subprocess.DEVNULL,stderr=_subprocess.DEVNULL,creationflags=flags)
    cfg["broker_pid"]=p.pid; cfg["enabled"]=True; _save_farm_config(cfg); _write_active_runtime(cfg); return cfg

def _stop_worker_broker():
    cfg=_farm_config(); pid=cfg.get("broker_pid")
    if _pid_alive(pid):
        try: _subprocess.run(["taskkill","/PID",str(pid),"/T","/F"],capture_output=True,timeout=8)
        except Exception: pass
    cfg["broker_pid"]=0; cfg["enabled"]=False; _save_farm_config(cfg)
    return cfg

def _firewall_rule_exists():
    try:
        ps=(
          "$r=Get-NetFirewallRule -DisplayName 'DEMO Duty Solver Workers 8093' -ErrorAction SilentlyContinue;"
          "if(-not $r){exit 3};$a=$r|Get-NetFirewallAddressFilter;$ra=(@($a.RemoteAddress)-join ',');"
          "$ok=((([int]$r.Profile)-band 4)-ne 0)-and(([int]$r.Enabled)-eq 1)-and(([int]$r.Action)-eq 2)"
          "-and($ra -match '172\\.28\\.29\\.0')-and($ra -match '172\\.30\\.0\\.0');"
          "if($ok){exit 0}else{exit 3}"
        )
        p=_subprocess.run(["powershell.exe","-NoProfile","-Command",ps],capture_output=True,timeout=8)
        return p.returncode==0
    except Exception:return False

def _request_firewall_uac(port):
    # Idempotently create or repair the narrow broker rule for the school LAN
    # and the routed S13 subnet. The Planner port 8091 remains localhost-only.
    try:
        import ctypes
        cmd=(
          "$n='DEMO Duty Solver Workers 8093';"
          "$r=Get-NetFirewallRule -DisplayName $n -ErrorAction SilentlyContinue;"
          f"if($r){{Set-NetFirewallRule -DisplayName $n -Direction Inbound -Action Allow -Protocol TCP -LocalPort {int(port)} "
          "-Profile Domain,Private,Public -RemoteAddress 198.51.100.29.0/24,192.0.2.0.0/16 -Enabled True}}"
          f"else{{New-NetFirewallRule -DisplayName $n -Direction Inbound -Action Allow -Protocol TCP -LocalPort {int(port)} "
          "-Profile Domain,Private,Public -RemoteAddress 198.51.100.29.0/24,192.0.2.0.0/16}}"
        )
        args=f'-NoProfile -Command "{cmd}"'
        rc=ctypes.windll.shell32.ShellExecuteW(None,"runas","powershell.exe",args,None,1)
        return int(rc)>32
    except Exception:return False

def _farm_status_public():
    cfg=_farm_config()
    if cfg.get("enabled") and not (_pid_alive(cfg.get("broker_pid")) and _broker_listening(cfg.get("port"))):
        try: cfg=_start_worker_broker()
        except Exception: pass
    try:
        _jobs=list(globals().get("REPAIR_JOBS",{}).values())
        _active=[j for j in _jobs if j.get("status") in ("queued","running","paused") and not j.get("_cancel")]
        _cur=max(_active,key=lambda j:j.get("created_at","")) if _active else (max(_jobs,key=lambda j:j.get("created_at","")) if _jobs else None)
        _job_id=_cur.get("id") if _cur else None
    except Exception:
        _job_id=None
    st=_repair_farm.status(_job_id)
    local_host=_socket.gethostname().casefold()
    remote_workers=[dict(w) for w in st["workers"] if str(w.get("hostname") or "").casefold()!=local_host]
    seed=_seed_sha()
    for w in remote_workers:
        w["compatible"]=bool(str(w.get("version") or "")==WORKER_PROTOCOL_VERSION and str(w.get("seed_sha") or "")==seed)
        w["usable"]=bool(w.get("online") and w["compatible"])
    online=[w for w in remote_workers if w.get("online")]
    usable=[w for w in remote_workers if w.get("usable")]
    return {"enabled":bool(cfg.get("enabled")),"broker_running":bool(_pid_alive(cfg.get("broker_pid")) and _broker_listening(cfg.get("port"))),
            "port":cfg["port"],"node_ip":_node_lan_ip(),"endpoint":f"http://{_node_lan_ip()}:{cfg['port']}",
            "local_workers":cfg["local_workers"],"seed_sha":seed,"planner_version":PLANNER_VERSION,"worker_protocol_version":WORKER_PROTOCOL_VERSION,
            "worker_package_version":WORKER_PACKAGE_VERSION,"firewall_rule":_firewall_rule_exists(),"workers":remote_workers,
            "workers_online":len(usable),"workers_connected":len(online),"workers_incompatible":len([w for w in online if not w.get("compatible")]),"tasks":st["tasks"]}


REPAIR_JOBS={}
REPAIR_JOB_LOCK=_threading.Lock()

def _invalidate_active_repair_jobs(reason="Stan planera został zmieniony."):
    changed=[]
    with REPAIR_JOB_LOCK:
        for job in REPAIR_JOBS.values():
            if job.get("status") in ("queued","running","paused") and not job.get("_cancel"):
                job["status"]="paused"; job["auto_paused"]=False; job["stale_due_to_manual_edit"]=True
                job["stage"]="Wstrzymane po zmianie stanu"
                job["message"]=reason+" Zachowano wyniki do podglądu; uruchom nowe przeliczenie przed zastosowaniem wyniku."
                changed.append(job.get("id"))
    return changed

def _functional_locked_assignments(state):
    rows=[]
    for r in (state.get("locked_assignments",[]) or []):
        if not isinstance(r,dict): continue
        rows.append({k:r.get(k) for k in ("scope","abbr","slot","location","teacher")})
    rows.sort(key=lambda r:tuple(str(r.get(k) or "") for k in ("scope","abbr","slot","location","teacher")))
    return rows

def _functional_preference_grid(state):
    raw=normalize_preference_grid(state.get("preference_grid",{}))
    return {str(teacher):dict(rows) for teacher,rows in raw.items() if isinstance(rows,dict) and rows}

_SOLVER_INPUT_STATE_KEYS=(
    "global_constraints","individual_constraints","enabled_teachers_13","enabled_teachers_school",
    "manual_blocks","station_order_13","min_people_13","min_people_13_stations",
    "school_locations","min_people_school","school_assignments","last_13_assignments",
    "teacher_workload","teacher_place_preferences","group_place_defaults","preference_grid","teacher_relax_order","teacher_relaxed_rules",
    "location_zones","duty_location_zones","locked_assignments","staffing_zero_overrides","absent_teachers","excluded_teachers",
    "freeze_pool_13","freeze_pool_school",
    "solver_seed","deterministic_mode","auto_tune_capacity","solver_internal_workers",
    "solver_coverage_seconds","solver_coverage_retry_seconds","teacher_lessons"
)

def _teacher_solver_snapshot():
    rows=[]
    for t in SEED.get("teachers",[]) or []:
        name=str(t.get("name") or "")
        reg=TEACHER_REGISTRY.get(name,{})
        rows.append({"name":name,
                     "group":reg.get("group",t.get("group","school")),
                     "active":bool(reg.get("active",t.get("active",True))),
                     "lessons":_copy.deepcopy(t.get("lessons",{}))})
    rows.sort(key=lambda r:r["name"].casefold())
    return rows

def _solver_input_signature(state):
    state_payload={k:state.get(k) for k in _SOLVER_INPUT_STATE_KEYS}
    state_payload["locked_assignments"]=_functional_locked_assignments(state)
    state_payload["preference_grid"]=_functional_preference_grid(state)
    payload={"state":state_payload,
             "teachers":_teacher_solver_snapshot()}
    return json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)

def _save_solver_input_change(before,after,reason,before_signature=None):
    old=before_signature if before_signature is not None else _solver_input_signature(before)
    changed=old!=_solver_input_signature(after)
    if changed:
        after["solver_input_revision"]=int(before.get("solver_input_revision",0) or 0)+1
    else:
        after["solver_input_revision"]=int(before.get("solver_input_revision",0) or 0)
    save_state(after)
    if changed:_invalidate_active_repair_jobs(reason)
    return changed

def _repair_job_input_current_v581(job):
    expected=str((job or {}).get("_solver_input_signature") or "")
    if not expected:return True
    try:
        latest=load_state()
        return _solver_input_signature(latest)==expected
    except Exception:
        return False

def _repair_abort_if_stale_v581(job,where=""):
    if _repair_job_input_current_v581(job):return False
    with REPAIR_JOB_LOCK:
        job["_cancel"]=True
        job["status"]="cancelled"
        job["stage"]="Zatrzymane — zmieniły się dane wejściowe"
        job["message"]="Ten przebieg używał starszej konfiguracji i został bezpiecznie zatrzymany. Nie może nadpisać nowszych ustawień."
        job["stale_input_detected"]=True
        job["stale_input_where"]=where
        job["local_active"]=0;job["remote_active"]=0
    try:_repair_checkpoint(job)
    except Exception:pass
    return True

REPAIR_CHECKPOINT_DIR=ROOT/"data"/"repair_jobs"
REPAIR_CHECKPOINT_DIR.mkdir(parents=True,exist_ok=True)
REPAIR_LEARNING_PATH=ROOT/"data"/"repair_learning.json"
SOLVER_KNOWLEDGE_PATH=ROOT/"data"/"solver_knowledge.json"
REPAIR_LEARNING_LOCK=_threading.Lock()
REPAIR_LEARNING_POLICY="v5.78-teacher-place-matrix"
SOLVER_KNOWLEDGE_POLICY="v1-cross-plan-constraint-learning"
REPAIR_LEARNING_MAX_CONTEXTS=12
REPAIR_LEARNING_MAX_TRIALS=900
SOLVER_KNOWLEDGE_MAX_KEYS=2500

def _repair_learning_fingerprint(state,e13,es):
    payload={
        "policy":REPAIR_LEARNING_POLICY,"seed_sha":_seed_sha(),
        "global":state.get("global_constraints",[]),"individual":state.get("individual_constraints",[]),
        "teacher_relax_order":state.get("teacher_relax_order",{}),
        "min13":state.get("min_people_13",{}),"min13stations":state.get("min_people_13_stations",{}),
        "minschool":state.get("min_people_school",{}),"locations":state.get("school_locations",[]),
        "manual_blocks":state.get("manual_blocks",{}),"locked":_functional_locked_assignments(state),
        "preferences":_functional_preference_grid(state),"place_preferences":state.get("teacher_place_preferences",{}),"duty_location_zones":state.get("duty_location_zones",{}),"excluded":state.get("excluded_teachers",[]),
        "absent":state.get("absent_teachers",[]),"freeze13":state.get("freeze_pool_13",False),
        "freezeSchool":state.get("freeze_pool_school",False),"e13":sorted(e13 or []),"es":sorted(es or [])
    }
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
    return _hashlib.sha256(raw).hexdigest()

def _learning_sig(tokens):
    return _hashlib.sha1("\n".join(sorted(str(x) for x in (tokens or []))).encode("utf-8")).hexdigest()[:20]

def _knowledge_token_family(token):
    tok=str(token or "")
    if tok.startswith("trelax:") and "|" in tok:
        return "trelax:*|"+tok.rsplit("|",1)[1]
    if tok.startswith("indsoft:"):
        return "indsoft:*"
    if tok.startswith("indval:"):
        parts=tok.split(":")
        return "indval:*:"+parts[-1] if len(parts)>=3 else "indval:*"
    if tok.startswith(("add13:","addschool:","move13:","moveschool:")):
        return tok.split(":",1)[0]+":*"
    return tok

def _solver_knowledge_bootstrap_from_repair_learning():
    """Build cross-plan priors from accumulated contextual trial history.
    These are associations used only for ordering trials inside the same safety stage.
    """
    try:
        old=json.loads(REPAIR_LEARNING_PATH.read_text(encoding="utf-8")) if REPAIR_LEARNING_PATH.exists() else {}
    except Exception:
        old={}
    stats={}
    contexts=(old.get("contexts",{}) or {}) if isinstance(old,dict) else {}
    for ctx in contexts.values():
        for row in (ctx.get("trials",{}) or {}).values():
            if not isinstance(row,dict):continue
            attempts=max(0,int(row.get("attempts",0) or 0))
            conclusive=max(0,int(row.get("conclusive_count",0) or 0))
            inconclusive=max(0,int(row.get("inconclusive_count",0) or 0))
            full=max(0,int(row.get("full_count",0) or 0))
            best=int(row.get("best_missing",10**6) or 10**6)
            for tok in dict.fromkeys(str(t) for t in (row.get("tokens",[]) or []) if str(t)):
                for key in ("token:"+tok,"family:"+_knowledge_token_family(tok)):
                    cur=stats.setdefault(key,{"attempts":0,"conclusive":0,"inconclusive":0,"full":0,
                                              "best_missing":10**6,"elapsed_total":0.0,"elapsed_count":0})
                    cur["attempts"]+=attempts
                    cur["conclusive"]+=conclusive
                    cur["inconclusive"]+=inconclusive
                    cur["full"]+=full
                    cur["best_missing"]=min(int(cur.get("best_missing",10**6)),best)
                    cur["last_at"]=row.get("last_at") or cur.get("last_at")
    rows=sorted(stats.items(),key=lambda kv:(-int(kv[1].get("full",0)),
                                              int(kv[1].get("best_missing",10**6)),
                                              -int(kv[1].get("attempts",0))))[:SOLVER_KNOWLEDGE_MAX_KEYS]
    return {"version":1,"policy":SOLVER_KNOWLEDGE_POLICY,
            "bootstrapped_from":"repair_learning.json",
            "bootstrapped_at":datetime.now().isoformat(timespec="seconds"),
            "updated_at":datetime.now().isoformat(timespec="seconds"),
            "stats":dict(rows)}

def _solver_knowledge_load():
    try:
        raw=json.loads(SOLVER_KNOWLEDGE_PATH.read_text(encoding="utf-8")) if SOLVER_KNOWLEDGE_PATH.exists() else {}
    except Exception:
        raw={}
    if not isinstance(raw,dict): raw={}
    if not isinstance(raw.get("stats"),dict) or not raw.get("stats"):
        raw=_solver_knowledge_bootstrap_from_repair_learning()
        try:
            tmp=SOLVER_KNOWLEDGE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")
            tmp.replace(SOLVER_KNOWLEDGE_PATH)
        except Exception:
            pass
    raw.setdefault("version",1);raw.setdefault("policy",SOLVER_KNOWLEDGE_POLICY)
    raw.setdefault("stats",{})
    if not isinstance(raw["stats"],dict):raw["stats"]={}
    # Historical exact teacher keys from the old encoding bug are unsafe as
    # person-specific evidence. Family-level cross-plan knowledge remains valid.
    bad_markers=tuple(chr(cp) for cp in (0xfffd,0x00c3,0x00c5,0x00c2))
    raw["stats"]={k:v for k,v in raw["stats"].items()
                  if not (str(k).startswith("token:trelax:") and any(m in str(k) for m in bad_markers))}
    return raw

def _solver_knowledge_snapshot():
    with REPAIR_LEARNING_LOCK:
        return _copy.deepcopy(_solver_knowledge_load())

def _solver_knowledge_update_memory(job,row):
    kb=job.get("_solver_knowledge")
    if not isinstance(kb,dict):return
    stats=kb.setdefault("stats",{})
    inc=bool(row.get("inconclusive"));miss=int(row.get("missing",10**6))
    elapsed=float(row.get("elapsed_s",0) or 0)
    keys=[]
    for tok in row.get("tokens",[]) or []:
        tok=str(tok)
        keys.extend(("token:"+tok,"family:"+_knowledge_token_family(tok)))
    for key in dict.fromkeys(keys):
        cur=stats.setdefault(key,{})
        cur["attempts"]=int(cur.get("attempts",0))+1
        if inc:cur["inconclusive"]=int(cur.get("inconclusive",0))+1
        else:
            cur["conclusive"]=int(cur.get("conclusive",0))+1
            cur["best_missing"]=min(int(cur.get("best_missing",10**6)),miss)
            if miss==0:
                cur["full"]=int(cur.get("full",0))+1
                cur["full_elapsed_total"]=round(float(cur.get("full_elapsed_total",0) or 0)+elapsed,3)
                cur["full_elapsed_count"]=int(cur.get("full_elapsed_count",0))+1
        cur["elapsed_total"]=round(float(cur.get("elapsed_total",0) or 0)+elapsed,3)
        cur["elapsed_count"]=int(cur.get("elapsed_count",0))+1
        cur["last_at"]=row.get("at")
    job["_solver_knowledge_dirty"]=int(job.get("_solver_knowledge_dirty",0))+1

def _solver_knowledge_flush(job):
    kb=job.get("_solver_knowledge")
    if not isinstance(kb,dict) or not int(job.get("_solver_knowledge_dirty",0) or 0):return
    stats=kb.get("stats",{}) or {}
    rows=sorted(stats.items(),key=lambda kv:(-int(kv[1].get("full",0)),
                                              int(kv[1].get("best_missing",10**6)),
                                              -int(kv[1].get("attempts",0))))[:SOLVER_KNOWLEDGE_MAX_KEYS]
    payload={"version":1,"policy":SOLVER_KNOWLEDGE_POLICY,
             "updated_at":datetime.now().isoformat(timespec="seconds"),
             "stats":dict(rows)}
    with REPAIR_LEARNING_LOCK:
        tmp=SOLVER_KNOWLEDGE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(SOLVER_KNOWLEDGE_PATH)
    job["_solver_knowledge"]=payload
    job["_solver_knowledge_dirty"]=0

def _solver_knowledge_stat(job,token):
    kb=job.get("_solver_knowledge",{}) if isinstance(job,dict) else {}
    stats=kb.get("stats",{}) if isinstance(kb,dict) else {}
    exact=stats.get("token:"+str(token),{})
    fam=stats.get("family:"+_knowledge_token_family(token),{})
    # Exact history wins once it has enough samples; otherwise use the cross-plan family.
    if int(exact.get("attempts",0))>=8:return exact
    return fam if int(fam.get("attempts",0))>=4 else exact

def _solver_knowledge_cost_adjustment(job,token,base):
    r=_solver_knowledge_stat(job,token)
    attempts=int(r.get("attempts",0) or 0)
    if attempts<4:return 0
    conclusive=max(0,int(r.get("conclusive",0) or 0))
    full=max(0,int(r.get("full",0) or 0))
    inconclusive=max(0,int(r.get("inconclusive",0) or 0))
    full_rate=full/max(1,conclusive)
    timeout_rate=inconclusive/max(1,attempts)
    best=int(r.get("best_missing",10**6) or 10**6)
    confidence=min(1.0,attempts/40.0)
    quality=max(full_rate, 0.30 if best<=2 else (0.15 if best<=5 else 0.0))
    bonus=int(max(0,base)*0.45*confidence*quality)
    penalty=int(max(0,base)*0.30*confidence*timeout_rate)
    return penalty-bonus

def _solver_knowledge_public_summary(job=None):
    kb=(job or {}).get("_solver_knowledge") if isinstance(job,dict) else None
    if not isinstance(kb,dict):kb=_solver_knowledge_snapshot()
    stats=kb.get("stats",{}) or {}
    numeric_keys=("max_day_13","max_day_school","max_week","max_long_day","max_long_week","max_consecutive_duties")
    labels={"max_day_13":"Maks. dziennie 1–3","max_day_school":"Maks. dziennie szkoła",
            "max_week":"Maks. tygodniowo","max_long_day":"Maks. długich / dzień",
            "max_long_week":"Maks. długich / tydzień","max_consecutive_duties":"Maks. kolejnych dyżurów"}
    recommended_values={}; learned=[]
    for key in numeric_keys:
        candidates=[]
        prefix="token:gval:"+key+":"
        for sk,r in stats.items():
            if not sk.startswith(prefix) or not isinstance(r,dict):continue
            raw=sk[len(prefix):]
            try:value=int(raw)
            except Exception:continue
            attempts=int(r.get("attempts",0) or 0);conclusive=int(r.get("conclusive",0) or 0)
            full=int(r.get("full",0) or 0);inc=int(r.get("inconclusive",0) or 0)
            best=int(r.get("best_missing",10**6) or 10**6)
            rate=full/max(1,conclusive)
            confidence=min(1.0,attempts/200.0)
            # Prefer values repeatedly producing full plans; then closer partials and more evidence.
            score=(1 if full>0 else 0,round(rate*confidence,6),-best,min(attempts,5000),-value)
            candidates.append((score,value,attempts,conclusive,full,inc,best,rate))
        if not candidates:continue
        candidates.sort(reverse=True)
        _,value,attempts,conclusive,full,inc,best,rate=candidates[0]
        if attempts<4:continue
        recommended_values[key]=value
        rr=stats.get("token:gval:"+key+":"+str(value),{}) or {}
        elapsed_count=int(rr.get("elapsed_count",0) or 0)
        full_elapsed_count=int(rr.get("full_elapsed_count",0) or 0)
        learned.append({"key":key,"label":labels.get(key,key),"value":value,
                        "attempts":attempts,"full":full,"full_rate":round(rate,3),
                        "best_missing":None if best>=10**6 else best,
                        "inconclusive":inc,
                        "avg_seconds":round(float(rr.get("elapsed_total",0) or 0)/max(1,elapsed_count),2) if elapsed_count else None,
                        "avg_full_seconds":round(float(rr.get("full_elapsed_total",0) or 0)/max(1,full_elapsed_count),2) if full_elapsed_count else None,
                        "confidence":round(min(1.0,attempts/200.0),2)})
    return {"policy":SOLVER_KNOWLEDGE_POLICY,"entries":len(stats),"updated_at":kb.get("updated_at"),
            "recommended_values":recommended_values,"learned_starts":learned}

def _repair_learning_load_context(fp):
    try:
        raw=json.loads(REPAIR_LEARNING_PATH.read_text(encoding="utf-8")) if REPAIR_LEARNING_PATH.exists() else {}
        return _copy.deepcopy((raw.get("contexts",{}) or {}).get(fp,{}).get("trials",{}))
    except Exception:return {}

def _repair_learning_flush(job):
    fp=job.get("_learning_fp"); trials=job.get("_learning_trials")
    if not fp or not isinstance(trials,dict):return
    with REPAIR_LEARNING_LOCK:
        try:raw=json.loads(REPAIR_LEARNING_PATH.read_text(encoding="utf-8")) if REPAIR_LEARNING_PATH.exists() else {}
        except Exception:raw={}
        contexts=raw.setdefault("contexts",{})
        now=datetime.now().isoformat(timespec="seconds")
        # Keep the most useful bounded subset: known full, then closest partials, then recent inconclusive.
        rows=list(trials.items())
        rows.sort(key=lambda kv:(0 if int(kv[1].get("full_count",0))>0 else
                                 1 if int(kv[1].get("conclusive_count",0))>0 else 2,
                                 int(kv[1].get("best_missing",10**6)),
                                 str(kv[1].get("last_at",""))),reverse=False)
        kept=dict(rows[:REPAIR_LEARNING_MAX_TRIALS])
        contexts[fp]={"updated_at":now,"policy":REPAIR_LEARNING_POLICY,"trials":kept}
        # Drop oldest configuration contexts.
        if len(contexts)>REPAIR_LEARNING_MAX_CONTEXTS:
            old=sorted(contexts.items(),key=lambda kv:str(kv[1].get("updated_at","")))
            for k,_ in old[:len(contexts)-REPAIR_LEARNING_MAX_CONTEXTS]:contexts.pop(k,None)
        raw["version"]=1;raw["policy"]=REPAIR_LEARNING_POLICY
        tmp=REPAIR_LEARNING_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8");tmp.replace(REPAIR_LEARNING_PATH)
    job["_learning_dirty"]=0
    _solver_knowledge_flush(job)

def _repair_learning_record(job,row):
    trials=job.get("_learning_trials")
    if not isinstance(trials,dict):return
    sig=_learning_sig(row.get("tokens",[])); cur=trials.get(sig,{})
    inc=bool(row.get("inconclusive")); miss=int(row.get("missing",10**6))
    elapsed=float(row.get("elapsed_s",0) or 0)
    cur.update({"tokens":sorted(row.get("tokens",[])),"last_at":row.get("at"),
                "last_missing":miss,"last_inconclusive":inc,"last_elapsed_s":round(elapsed,3)})
    cur["attempts"]=int(cur.get("attempts",0))+1
    cur["elapsed_total"]=round(float(cur.get("elapsed_total",0) or 0)+elapsed,3)
    cur["elapsed_count"]=int(cur.get("elapsed_count",0))+1
    if inc:cur["inconclusive_count"]=int(cur.get("inconclusive_count",0))+1
    else:
        cur["conclusive_count"]=int(cur.get("conclusive_count",0))+1
        cur["best_missing"]=min(int(cur.get("best_missing",10**6)),miss)
        if miss==0:
            cur["full_count"]=int(cur.get("full_count",0))+1
            cur["full_elapsed_total"]=round(float(cur.get("full_elapsed_total",0) or 0)+elapsed,3)
            cur["full_elapsed_count"]=int(cur.get("full_elapsed_count",0))+1
    trials[sig]=cur
    _solver_knowledge_update_memory(job,row)
    job["_learning_dirty"]=int(job.get("_learning_dirty",0))+1
    if job["_learning_dirty"]>=5:_repair_learning_flush(job)

def _repair_learning_order(job,items):
    trials=job.get("_learning_trials",{}) if isinstance(job.get("_learning_trials"),dict) else {}
    known=0
    def key(item):
        nonlocal known
        toks=item.get("tokens",[]) or []
        r=trials.get(_learning_sig(toks))
        global_bias=sum(_solver_knowledge_cost_adjustment(job,t,1000) for t in toks)
        if not r:return (1,global_bias,0,0)
        known+=1
        if int(r.get("full_count",0))>0:return (0,global_bias,int(r.get("best_missing",0)),0)
        if int(r.get("conclusive_count",0))>0:return (2,global_bias,int(r.get("best_missing",10**6)),int(r.get("attempts",0)))
        return (3,global_bias,10**6,int(r.get("attempts",0)))
    out=sorted(list(items),key=key)
    with REPAIR_JOB_LOCK:job["learning_known_in_block"]=known
    return out


def _repair_mojibake_text_v567(text):
    if not isinstance(text,str) or not text:
        return text

    def fix_latin1_chunk(chunk):
        # Decode only valid UTF-8 byte sequences hidden inside a Latin-1-decoded
        # substring. Invalid single Latin-1 characters are preserved verbatim.
        raw=chunk.encode("latin1")
        out=[]; i=0
        while i < len(raw):
            b0=raw[i]
            widths=()
            if 0xC2 <= b0 <= 0xDF: widths=(2,)
            elif 0xE0 <= b0 <= 0xEF: widths=(3,)
            elif 0xF0 <= b0 <= 0xF4: widths=(4,)
            done=False
            for width in widths:
                if i+width > len(raw):
                    continue
                part=raw[i:i+width]
                try:
                    decoded=part.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                out.append(decoded); i+=width; done=True; break
            if not done:
                out.append(chr(b0)); i+=1
        return "".join(out)

    out=text
    for _ in range(2):
        pieces=[]; buf=[]
        def flush():
            if buf:
                pieces.append(fix_latin1_chunk("".join(buf)))
                buf.clear()
        for ch in out:
            if ord(ch) <= 255:
                buf.append(ch)
            else:
                flush(); pieces.append(ch)
        flush()
        fixed="".join(pieces)
        if fixed==out:
            break
        out=fixed
    return out

def _repair_mojibake_recursive_v567(value):
    if isinstance(value,str):
        return _repair_mojibake_text_v567(value)
    if isinstance(value,list):
        return [_repair_mojibake_recursive_v567(x) for x in value]
    if isinstance(value,tuple):
        return tuple(_repair_mojibake_recursive_v567(x) for x in value)
    if isinstance(value,dict):
        return {k:_repair_mojibake_recursive_v567(v) for k,v in value.items()}
    return value

def _repair_public_unlocked(job):
    public={k:_copy.deepcopy(v) for k,v in job.items() if not k.startswith("_")}
    return _repair_mojibake_recursive_v567(public)

def _repair_copy_public(job):
    with REPAIR_JOB_LOCK:
        return _repair_public_unlocked(job)

def _repair_checkpoint(job):
    with REPAIR_JOB_LOCK:
        snap=_repair_public_unlocked(job)
    path=REPAIR_CHECKPOINT_DIR/(str(job.get("id","unknown"))+".json")
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(path)

def _record_trial(job,item,ev,source,phase):
    sig=tuple(sorted(item.get("tokens",[])))
    row={
        "tokens":list(item.get("tokens",[])),
        "title":" + ".join(c.get("label",c.get("token","")) for c in item.get("changes",[])) or "Pełne przetasowanie bez zmiany reguł",
        "missing":int(ev.get("missing",10**6)),
        "inconclusive":bool(ev.get("inconclusive")),
        "order":ev.get("order"),
        "coverage13":_copy.deepcopy(ev.get("coverage13",{})),
        "coverageSchool":_copy.deepcopy(ev.get("coverageSchool",{})),
        "elapsed_s":round(float(ev.get("elapsed_s",0) or 0),2),
        "source":source,"phase":phase,
        "human_cost":sum(int(c.get("human_cost",0) or 0) for c in item.get("changes",[])),
        "wait_relax":any(_token_relaxes_rule_v537(t,"avoid_wait") for t in item.get("tokens",[])),
        "at":datetime.now().isoformat(timespec="seconds")
    }
    improved=False
    with REPAIR_JOB_LOCK:
        job.setdefault("_trial_records",[]).append({"item":_copy.deepcopy(item),"result":_copy.deepcopy(ev),"phase":phase})
        job["trial_count"]=int(job.get("trial_count",0))+1
        if row["inconclusive"]:
            xs=job.setdefault("inconclusive_samples",[])
            if not any(tuple(sorted(x.get("tokens",[])))==sig for x in xs):
                xs.append(row); xs.sort(key=lambda x:(x.get("human_cost",0),x.get("elapsed_s",0))); del xs[10:]
        elif row["missing"]>0:
            xs=job.setdefault("best_partials",[])
            before=xs[0]["missing"] if xs else 10**9
            xs=[x for x in xs if tuple(sorted(x.get("tokens",[])))!=sig]
            xs.append(row)
            xs.sort(key=lambda x:(x["missing"],x.get("wait_relax",False),x.get("human_cost",0),x.get("elapsed_s",0)))
            del xs[20:]
            job["best_partials"]=xs
            after=xs[0]["missing"] if xs else before
            improved=after<before
        if not row["inconclusive"]:
            job["best_missing"]=row["missing"] if job.get("best_missing") is None else min(int(job["best_missing"]),row["missing"])
        job["last_source"]=source; job["last_order"]=ev.get("order")
        job["last_probe_result"]=_copy.deepcopy(row)
    logp=REPAIR_CHECKPOINT_DIR/(str(job.get("id","unknown"))+".jsonl")
    with logp.open("a",encoding="utf-8") as f:
        f.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n")
    _repair_learning_record(job,row)
    if improved or int(job.get("trial_count",0))%5==0:
        _repair_checkpoint(job)
    return row

def _top_trial_items(job,phase,limit=8,require_token_count=None):
    with REPAIR_JOB_LOCK:
        recs=_copy.deepcopy(job.get("_trial_records",[]))
    rows=[]
    for rec in recs:
        if rec.get("phase")!=phase: continue
        item=rec.get("item",{});ev=rec.get("result",{})
        if require_token_count is not None and len(item.get("tokens",[]))!=require_token_count: continue
        cost=sum(int(c.get("human_cost",0) or 0) for c in item.get("changes",[]))
        key=(1 if ev.get("inconclusive") else 0,int(ev.get("missing",10**6)),cost,len(item.get("tokens",[])))
        rows.append((key,item))
    rows.sort(key=lambda x:x[0])
    out=[];seen=set()
    for _,item in rows:
        sig=tuple(sorted(item.get("tokens",[])))
        if sig in seen:continue
        seen.add(sig);out.append(item)
        if len(out)>=limit:break
    return out

def _deep_items_from_job(job,wait_only=False,limit=10):
    with REPAIR_JOB_LOCK:
        recs=_copy.deepcopy(job.get("_trial_records",[]))
    uniq={}
    for rec in recs:
        item=rec.get("item",{}); ev=rec.get("result",{})
        toks=item.get("tokens",[]); is_wait=any(_token_relaxes_rule_v537(t,"avoid_wait") for t in toks)
        if bool(wait_only)!=bool(is_wait): continue
        if not toks or (not ev.get("inconclusive") and int(ev.get("missing",10**6))==0): continue
        sig=tuple(sorted(toks))
        old=uniq.get(sig)
        key=(1 if ev.get("inconclusive") else 0,int(ev.get("missing",10**6)),
             sum(int(c.get("human_cost",0) or 0) for c in item.get("changes",[])),len(toks))
        if old is None or key<old[0]: uniq[sig]=(key,item)
    vals=list(uniq.values())
    if wait_only:
        vals.sort(key=lambda z:(0 if any(_token_relaxes_rule_v537(t,"avoid_wait") for t in z[1].get("tokens",[])) else 1,z[0]))
    else:
        vals.sort(key=lambda z:z[0])
    return [v[1] for v in vals[:limit]]

def _latest_repair_checkpoint():
    files=sorted(REPAIR_CHECKPOINT_DIR.glob("*.json"),key=lambda x:x.stat().st_mtime,reverse=True)
    if not files:return None
    try:
        x=_repair_mojibake_recursive_v567(json.loads(files[0].read_text(encoding="utf-8-sig")))
        if x.get("status") in ("queued","running","paused"):
            x["status"]="interrupted";x["stage"]="Przerwane restartem usługi — zapisane wyniki częściowe są zachowane."
        return x
    except Exception:return None

def _checkpoint_live_seed(state):
    """Reuse only complete live drafts from the same solver-input revision after a service restart."""
    prev=_latest_repair_checkpoint()
    if not prev:
        return []
    try:
        if int(prev.get("plan_revision",-1))!=int((state or {}).get("plan_revision",-2)):
            return []
    except Exception:
        return []
    out=[]
    for v in prev.get("working_variants",[]) or []:
        if not isinstance(v,dict):
            continue
        c13=v.get("coverage13") or {}; cs=v.get("coverageSchool") or {}
        if (v.get("live_eligible") is True
            and int(v.get("missing",1) or 0)==0
            and int(c13.get("filled",0) or 0)>=int(c13.get("required",0) or 0)
            and int(cs.get("filled",0) or 0)>=int(cs.get("required",0) or 0)
            and v.get("result_13") and v.get("result_school")):
            out.append(_copy.deepcopy(v))
    out.sort(key=lambda x:(_working_quality_key_v559(x,prev),int(x.get("seq",0) or 0)))
    return out[:10]

def _checkpoint_resume_id(state):
    prev=_latest_repair_checkpoint()
    if not prev or prev.get("status")!="interrupted":
        return None
    try:
        if int(prev.get("plan_revision",-1))!=int((state or {}).get("plan_revision",-2)):
            return None
    except Exception:
        return None
    jid=str(prev.get("id") or "").strip()
    return jid or None

def _repair_pausepoint(job):
    while True:
        with REPAIR_JOB_LOCK:
            if job.get("_cancel"): return False
            paused=job.get("status")=="paused"
        if not paused: return True
        _time.sleep(.25)

def _set_global_value(st,key,value=None,kind=None,enabled=None):
    for r in st.get("global_constraints",[]):
        if r.get("key")==key:
            if value is not None: r["value"]=value
            if kind is not None: r["kind"]=kind
            if enabled is not None: r["enabled"]=enabled
            return

def _apply_repair_tokens_v2(state,e13,es,tokens):
    st=_copy.deepcopy(state)
    excluded=set(st.get("excluded_teachers",[]))
    p13=[n for n in e13 if n not in excluded]
    ps=[n for n in _school_pool(es) if n not in excluded]
    freeze13=bool(st.get("freeze_pool_13",False))
    freezeSchool=bool(st.get("freeze_pool_school",False))
    for token in tokens:
        if token.startswith("gsoft:"):
            _set_global_value(st,token[6:],kind="soft",enabled=True)
        elif token.startswith("goff:"):
            _set_global_value(st,token[5:],enabled=False)
        elif token.startswith("gval:"):
            _,key,value=token.split(":",2); _set_global_value(st,key,value=int(value),enabled=True)
        elif token.startswith("m13:"):
            _,rest=token.split(":",1); ab,slot,val=rest.split("|",2)
            _set_required_13_count(st,ab,slot,int(val))
        elif token.startswith("ms:"):
            _,rest=token.split(":",1); ab,slot,loc,val=rest.rsplit("|",3)
            st.setdefault("min_people_school",{})[f"{ab}|{slot}|{loc}"]=int(val)
        elif token.startswith("add13:"):
            n=token[6:]
            if not freeze13 and n not in excluded and n not in p13: p13.append(n)
        elif token=="add13group:school":
            if not freeze13: p13=list(dict.fromkeys(p13+[n for n in sorted(SCHOOL,key=_teacher_sort_key) if n not in excluded]))
        elif token=="add13group:wf":
            if not freeze13: p13=list(dict.fromkeys(p13+[n for n in sorted(WF,key=_teacher_sort_key) if n not in excluded]))
        elif token.startswith("addschool:"):
            n=token[10:]
            if not freezeSchool and n not in excluded and n not in ps: ps.append(n)
        elif token.startswith("move13:"):
            n=token[7:]
            if not freeze13 and not freezeSchool and n not in excluded:
                if n not in p13: p13.append(n)
                ps=[x for x in ps if x!=n]
        elif token.startswith("moveschool:"):
            n=token[11:]
            if not freeze13 and not freezeSchool and n not in excluded:
                if n not in ps: ps.append(n)
                p13=[x for x in p13 if x!=n]
        elif token.startswith("trelax:"):
            _,rest=token.split(":",1); teacher,key=rest.split("|",1)
            vals=st.setdefault("teacher_relaxed_rules",{}).setdefault(teacher,[])
            if key not in vals: vals.append(key)
        elif token.startswith("prefclr:"):
            _,rest=token.split(":",1); teacher,abbr,slot=rest.split("|",2)
            st.setdefault("preference_grid",{}).setdefault(teacher,{}).pop(f"{abbr}|{slot}",None)
        elif token.startswith("indval:"):
            _,rid,value=token.split(":",2)
            for r in st.get("individual_constraints",[]):
                if str(r.get("id"))==rid:
                    r["value"]=int(value); r["enabled"]=True; break
        elif token.startswith("indsoft:"):
            rid=token[8:]
            for r in st.get("individual_constraints",[]):
                if str(r.get("id"))==rid: r["kind"]="soft"; break
        elif token.startswith("unlock:"):
            _,rest=token.split(":",1); scope,abbr,slot,loc=rest.split("|",3)
            st["locked_assignments"]=[r for r in st.get("locked_assignments",[])
                if not (r.get("scope")==scope and r.get("abbr")==abbr and r.get("slot")==slot and str(r.get("location",""))==loc)]
        elif token.startswith("unblock:"):
            _,rest=token.split(":",1); teacher,abbr,slot=rest.split("|",2)
            key=f"{abbr}|{slot}"
            vals=st.setdefault("manual_blocks",{}).get(teacher,[])
            st["manual_blocks"][teacher]=[x for x in vals if x!=key]
    return ensure_state_schema(st),p13,ps

def _flat_school_other(assignments):
    return [{"day":a["day"],"abbr":a["abbr"],"slot":a["slot"],"location":a.get("location",""),
             "teacher":a["teacher"]} for a in assignments if a.get("teacher")]

def _joint_order_v2(st,e13,es,order,optimize=False):
    es=_school_pool(es)
    if order=="school-first":
        b=_coverage(st,"szkoła",es,other_override=[],optimize=optimize)
        a=_coverage(st,"1–3",e13,other_override=_flat_school_other(b["assignments"]),optimize=optimize)
    else:
        a=_coverage(st,"1–3",e13,other_override=[],optimize=optimize)
        b=_coverage(st,"szkoła",es,other_override=_flat13_other(a["assignments"]),optimize=optimize)
    ind=bool(a.get("inconclusive") or b.get("inconclusive"))
    return {"school13":a,"school":b,"missing":a["missing"]+b["missing"],
            "inconclusive":ind,"order":order}

def _joint_coverage_v2(st,e13,es,optimize=False):
    # Decomposition in both directions prevents the first scope from unfairly
    # consuming teachers needed by the second one.
    es=_school_pool(es)
    if optimize:
        p1=_joint_order_v2(st,e13,es,"13-first",False)
        if not p1["inconclusive"] and p1["missing"]==0:
            opt=_joint_order_v2(st,e13,es,"13-first",True)
            return opt if not opt["inconclusive"] and opt["missing"]==0 else p1
        p2=_joint_order_v2(st,e13,es,"school-first",False)
        probe=min((p1,p2),key=lambda x:(x["inconclusive"],x["missing"],
             len(x["school13"].get("waits",[]))+len(x["school"].get("waits",[]))))
        opt=_joint_order_v2(st,e13,es,probe["order"],True)
        return opt if not opt["inconclusive"] and opt["missing"]<=probe["missing"] else probe
    r1=_joint_order_v2(st,e13,es,"13-first",False)
    if not r1["inconclusive"] and r1["missing"]==0:
        return r1
    r2=_joint_order_v2(st,e13,es,"school-first",False)
    return min((r1,r2),key=lambda x:(x["inconclusive"],x["missing"],
        len(x["school13"].get("waits",[]))+len(x["school"].get("waits",[]))))

def _repair_candidate_v2(token,label,cost,category="organizacyjne",comfort=False):
    return {"token":token,"label":label,"human_cost":int(cost),"category":category,"comfort_cost":bool(comfort)}


def _preflight_teacher_allowed_v524(st,scope,pos,enabled):
    """Necessary-condition eligibility only: never claims impossibility from a soft preference."""
    cs=cdict(st); br=pos["break"]; loc=pos.get("location")
    required=pos.get("required_teacher")
    excluded=set(st.get("excluded_teachers",[]))
    out=[]
    for t in SEED.get("teachers",[]):
        n=t.get("name")
        if not n or n in excluded: continue
        if required and n!=required: continue
        if not required and n not in enabled: continue

        if br["abbr"]+"|"+br["label"] in blockset(st,n):
            hard,_=global_rule_effect(cs,"manual_blocks",1,100000)
            if hard: continue
        if duty_overlaps_lesson(n,br):
            hard,_=global_rule_effect(cs,"no_lesson_overlap",1,100000)
            if hard: continue

        hard,_,_,_=individual_effect(st,n,scope,br["abbr"],br["label"],loc)
        if hard: continue
        opening=is_opening_break(br)
        if opening and not opening_break_teacher_allowed(n,br):
            continue
        rel=lesson_relation(n,br)
        dhard,_=directional_individual_effect(st,n,scope,rel)
        if dhard: continue

        relaxed=set((st.get("teacher_relaxed_rules",{}) or {}).get(n,[]) or [])
        try: long_min=LONG_BREAK_MINUTES
        except Exception: long_min=15
        ps=sorted(lesson_periods(n,br["abbr"]))
        nxt=br.get("next")
        before_first=bool((not opening) and ps and nxt in ps and int(nxt)==min(ps))
        edge_short=int(br.get("minutes",0) or 0)<=SHORT_BREAK_MAX_MINUTES
        if before_first:
            key="before_first_short" if edge_short else "before_first_long"
            hard,_=global_rule_effect(cs,key,1,2500 if key=="before_first_long" else 100)
            if hard and key not in relaxed: continue
        if is_after_last_lesson(n,br):
            key="after_last_short" if edge_short else "after_last_long"
            hard,_=global_rule_effect(cs,key,1,2500 if key=="after_last_long" else 100)
            if hard and key not in relaxed: continue

        wait=wait_periods(n,br)
        if wait>=2: continue
        if wait>0:
            hard,_=global_rule_effect(cs,"avoid_wait",wait,10000)
            if hard and "avoid_wait" not in relaxed: continue
        if st.get("place_preference_model")!="teacher_x_place_v1":
            home=(GROUP.get(n)=="1-3") if scope=="1-3" else (GROUP.get(n)=="school")
            if not home:
                hard,_=global_rule_effect(cs,"prefer_home_group",1,2500)
                if hard and "prefer_home_group" not in relaxed: continue
        out.append(n)
    return out

def _max_bipartite_match_v524(edges):
    match={}
    def dfs(i,seen):
        for n in edges[i]:
            if n in seen: continue
            seen.add(n)
            if n not in match or dfs(match[n],seen):
                match[n]=i
                return True
        return False
    return sum(1 for i in range(len(edges)) if dfs(i,set()))

def _slot_feasibility_v524(st,e13,es):
    """Cheap per-slot matching before CP-SAT; detects only hard, obvious shortages."""
    st=ensure_state_schema(_copy.deepcopy(st))
    excluded=set(st.get("excluded_teachers",[]))|set(st.get("absent_teachers",[]))
    active=[n for n in ALL if n not in excluded]
    p13=list(active)
    ps=list(active)
    pos13,_,_=_diag_positions_13(st)
    posS,_,_,_=_school_positions(st)
    problems=[]; candidates=[]

    def analyze(scope,positions,enabled,is13):
        groups=defaultdict(list)
        for pos in positions:
            groups[(pos.get("abbr"),pos.get("slot"))].append(pos)
        for (ab,slot),grp in groups.items():
            edges=[_preflight_teacher_allowed_v524(st,scope,pos,enabled) for pos in grp]
            possible=_max_bipartite_match_v524(edges)
            required=len(grp)
            if possible>=required: continue
            shortage=required-possible
            union=sorted(set(n for xs in edges for n in xs),key=_teacher_sort_key)
            # Check whether the shortage can be covered simply by adding teachers
            # who are outside the current pool but satisfy the same hard/no-wait rules.
            all_allowed=[n for n in ALL if n not in excluded]
            all_edges=[_preflight_teacher_allowed_v524(st,scope,pos,all_allowed) for pos in grp]
            all_possible=_max_bipartite_match_v524(all_edges)
            outside=sorted(
                set(n for xs in all_edges for n in xs if n not in enabled),
                key=_teacher_sort_key)

            admin_locks=[]
            for pos in grp:
                if pos.get("admin_lock"):
                    admin_locks.append({"teacher":pos.get("admin_lock"),"location":pos.get("location") or pos.get("station") or "",
                                        "abbr":ab,"slot":slot,"scope":"1-3" if is13 else "school"})
                if pos.get("admin_lock_conflict"):
                    z=pos["admin_lock_conflict"]
                    admin_locks.append({"teacher":z.get("locked"),"location":pos.get("location") or pos.get("station") or "",
                                        "abbr":ab,"slot":slot,"scope":"1-3" if is13 else "school",
                                        "conflict_with":z.get("required")})
            # Compare matching with admin locks removed. If feasibility increases,
            # the fixed assignment is a real blocker/contributor and must be released manually.
            unlock_possible=possible; unlock_all_possible=all_possible
            if admin_locks:
                ust=_copy.deepcopy(st);ust["locked_assignments"]=[]
                if is13:
                    upos=_diag_positions_13(ust)[0]
                else:
                    upos=_school_positions(ust,include_locks=False)[0]
                ugrp=[p for p in upos if p.get("abbr")==ab and p.get("slot")==slot]
                uedges=[_preflight_teacher_allowed_v524(ust,scope,pos,enabled) for pos in ugrp]
                uaedges=[_preflight_teacher_allowed_v524(ust,scope,pos,all_allowed) for pos in ugrp]
                unlock_possible=_max_bipartite_match_v524(uedges)
                unlock_all_possible=_max_bipartite_match_v524(uaedges)
            lock_blocker=bool(admin_locks and (unlock_possible>possible or unlock_all_possible>all_possible))
            problems.append({
                "scope":"1-3" if is13 else "school","abbr":ab,"slot":slot,
                "required":required,"possible_without_relax":possible,
                "possible_with_pool_expansion":all_possible,
                "shortage":shortage,"eligible_teachers":union,
                "eligible_outside_pool":outside,
                "admin_locks":admin_locks,"admin_lock_blocker":lock_blocker,
                "possible_without_admin_locks":unlock_possible,
                "possible_with_pool_and_without_admin_locks":unlock_all_possible,
                "message":f"{ab} {slot}: wymagane {required}, maksymalnie {possible} w obecnej puli bez łamania twardych reguł."
            })

            # v5.78: there is no candidate-pool expansion. All active teachers are
            # already visible to CP-SAT. Spatial participation is controlled by the
            # teacher x exact-duty-place matrix and hard place properties.

            # v5.53: shortage never reduces required staffing here. Staffing may
            # become zero only in _apply_timetable_staffing(), when the timetable
            # proves that the relevant corridor/floor/zone is no longer active.
            # Otherwise preflight relaxes a proven-impossible comfort constraint
            # or reports a genuine organizational blocker.
    analyze("1-3",pos13,p13,True)
    analyze("school",posS,ps,False)
    return {"problems":problems,"candidates":candidates}

def _preflight_effective_shortages_v553(st,e13,es):
    """Hard per-slot shortages after any allowed pool expansion, but before CP-SAT."""
    raw=_slot_feasibility_v524(st,e13,es)
    rows=[]; score=0
    for p in raw.get("problems",[]):
        if p.get("admin_lock_blocker"):
            continue
        freeze=bool(st.get("freeze_pool_13" if p.get("scope")=="1-3" else "freeze_pool_school",False))
        possible=int(p.get("possible_without_relax",0) if freeze else p.get("possible_with_pool_expansion",0))
        required=int(p.get("required",0) or 0)
        shortage=max(0,required-possible)
        if not shortage:
            continue
        row=dict(p);row["effective_possible"]=possible;row["effective_shortage"]=shortage
        rows.append(row);score+=shortage
    return score,rows,raw

def _auto_relax_edge_constraints_v553(st,e13,es):
    """Find the least-cost subset of relaxable HARD edge rules needed for slot feasibility."""
    import itertools
    base_score,base_rows,_=_preflight_effective_shortages_v553(st,e13,es)
    if base_score<=0:
        return []
    keys=[k for k in PREFLIGHT_EDGE_RELAX_COST_V553
          if (_global_row(st,k).get("enabled")
              and normalize_kind(_global_row(st,k).get("kind"))=="hard")]
    tested=[]
    for n in range(1,len(keys)+1):
        for combo in itertools.combinations(keys,n):
            trial=_copy.deepcopy(st)
            for key in combo:
                _preflight_soften_global_v553(trial,key)
            score,rows,_=_preflight_effective_shortages_v553(trial,e13,es)
            if score>=base_score:
                continue
            cost=sum(PREFLIGHT_EDGE_RELAX_COST_V553[k] for k in combo)
            tested.append({"combo":combo,"score":int(score),"cost":int(cost),"rows":rows,"state":trial})
    if not tested:
        return []
    complete=[x for x in tested if x["score"]==0]
    if complete:
        best=min(complete,key=lambda x:(x["cost"],len(x["combo"]),x["combo"]))
    else:
        best=min(tested,key=lambda x:(x["score"],x["cost"],len(x["combo"]),x["combo"]))
    selected=list(best["combo"])
    final_state=best["state"]
    final_score=best["score"]
    changes=[]
    for key in selected:
        without=_copy.deepcopy(st)
        for other in selected:
            if other!=key:
                _preflight_soften_global_v553(without,other)
        without_score,without_rows,_=_preflight_effective_shortages_v553(without,e13,es)
        final_rows=best["rows"]
        before_map={(x["scope"],x["abbr"],x["slot"]):x for x in without_rows}
        after_map={(x["scope"],x["abbr"],x["slot"]):x for x in final_rows}
        affected=[];cases=0;min_teachers=0
        for slot_id,b in before_map.items():
            a=after_map.get(slot_id)
            before=int(b.get("effective_shortage",0) or 0)
            after=int((a or {}).get("effective_shortage",0) or 0)
            freed=max(0,before-after)
            if not freed:
                continue
            cases+=freed;min_teachers=max(min_teachers,freed)
            affected.append({"scope":slot_id[0],"abbr":slot_id[1],"slot":slot_id[2],
                             "required":int(b.get("required",0) or 0),
                             "before_possible":int(b.get("effective_possible",0) or 0),
                             "after_possible":int((a or {}).get("effective_possible",b.get("required",0)) or 0),
                             "minimum_exceptions":freed})
        # Synergistic rules may have zero individual gain until the whole selected
        # subset is softened. In that case report the common baseline proof.
        if not affected and without_score>final_score:
            affected=[{"scope":x["scope"],"abbr":x["abbr"],"slot":x["slot"],
                       "required":int(x.get("required",0) or 0),
                       "before_possible":int(x.get("effective_possible",0) or 0),
                       "after_possible":int(x.get("required",0) or 0),
                       "minimum_exceptions":int(x.get("effective_shortage",0) or 0)}
                      for x in base_rows]
            cases=sum(int(x.get("minimum_exceptions",0) or 0) for x in affected)
            min_teachers=max([int(x.get("minimum_exceptions",0) or 0) for x in affected] or [1])
        label=_global_row(st,key).get("label",key)
        changes.append({
            "key":key,"label":label,"from":"MUSI BYĆ","to":"ZALECANE 5 — Najwyższa",
            "priority":5,"proof":"minimal_cost_slot_matching",
            "minimum_exception_cases":max(1,cases),
            "minimum_teachers":max(1,min_teachers),
            "affected_slots":affected,
            "selected_relaxation_set":selected,
            "reason":f"Preflight sprawdził wszystkie kombinacje zwykłych reguł brzegowych i znalazł najtańszy zestaw pozwalający zachować wymaganą obsadę. Ta reguła jest częścią koniecznego zestawu wyjątków."
        })
    for key in selected:
        _preflight_soften_global_v553(st,key)
    return changes

def _auto_relax_individual_directional_v553(st,e13,es):
    """Soften proven-impossible per-teacher edge-of-day HARD comfort rules."""
    relaxable={"no_before_first_lesson":60,"no_after_last_lesson":70,
               "no_before_lesson":60,"no_after_lesson":70}
    changes=[]
    score,rows,_=_preflight_effective_shortages_v553(st,e13,es)
    while score>0:
        candidates=[r for r in st.get("individual_constraints",[])
                    if r.get("enabled",True)
                    and normalize_kind(r.get("kind"))=="hard"
                    and str(r.get("rule") or "") in relaxable
                    and str(r.get("id") or "")]
        if not candidates:
            break
        options=[]
        # Usually one teacher-specific relaxation already increases matching.
        for r in candidates:
            trial=_copy.deepcopy(st)
            tr=next((x for x in trial.get("individual_constraints",[]) if str(x.get("id"))==str(r.get("id"))),None)
            if not tr: continue
            tr["kind"]="soft";tr["priority"]=5
            ns,nrows,_=_preflight_effective_shortages_v553(trial,e13,es)
            if ns<score:
                options.append((int(relaxable[str(r.get("rule"))]),1,int(ns),(str(r.get("id")),),trial,nrows))
        # Handle a rare synergy: two edge rules for the same teacher may both
        # block the only physically usable assignment, so neither helps alone.
        if not options and len(candidates)<=24:
            import itertools
            for a,b in itertools.combinations(candidates,2):
                if a.get("teacher")!=b.get("teacher"):
                    continue
                trial=_copy.deepcopy(st)
                ids={str(a.get("id")),str(b.get("id"))}
                for tr in trial.get("individual_constraints",[]):
                    if str(tr.get("id")) in ids:
                        tr["kind"]="soft";tr["priority"]=5
                ns,nrows,_=_preflight_effective_shortages_v553(trial,e13,es)
                if ns<score:
                    cost=sum(relaxable[str(x.get("rule"))] for x in (a,b))
                    options.append((cost,2,int(ns),tuple(sorted(ids)),trial,nrows))
        if not options:
            break
        cost,count,newscore,ids,trial,newrows=min(options,key=lambda x:(x[2],x[0],x[1],x[3]))
        before_map={(x["scope"],x["abbr"],x["slot"]):x for x in rows}
        after_map={(x["scope"],x["abbr"],x["slot"]):x for x in newrows}
        affected=[];cases=0;min_teachers=0
        for slot_id,b in before_map.items():
            a=after_map.get(slot_id)
            freed=max(0,int(b.get("effective_shortage",0) or 0)-int((a or {}).get("effective_shortage",0) or 0))
            if not freed: continue
            cases+=freed;min_teachers=max(min_teachers,freed)
            affected.append({"scope":slot_id[0],"abbr":slot_id[1],"slot":slot_id[2],
                             "required":int(b.get("required",0) or 0),
                             "before_possible":int(b.get("effective_possible",0) or 0),
                             "after_possible":int((a or {}).get("effective_possible",b.get("required",0)) or 0),
                             "minimum_exceptions":freed})
        for rid in ids:
            src=next((r for r in st.get("individual_constraints",[]) if str(r.get("id"))==rid),None)
            if not src: continue
            src["kind"]="soft";src["priority"]=5
            changes.append({
                "constraint_type":"individual","id":rid,
                "key":str(src.get("rule") or ""),"teacher":src.get("teacher"),
                "label":f"{_display_teacher(src.get('teacher','?'))}: {src.get('rule')}",
                "from":"MUSI BYĆ","to":"ZALECANE 5 — Najwyższa","priority":5,
                "proof":"teacher_specific_slot_matching",
                "minimum_exception_cases":max(1,cases),
                "minimum_teachers":max(1,min_teachers),
                "affected_slots":affected,
                "reason":"Ta indywidualna reguła brzegowa blokuje wymaganą obsadę w co najmniej jednym slocie. Została złagodzona wyłącznie dla wskazanego nauczyciela."
            })
        score,rows=int(newscore),newrows
    return changes

def _auto_relax_consecutive_v553(st,e13,es):
    row=_global_row(st,"max_consecutive_duties")
    if not row or not row.get("enabled") or normalize_kind(row.get("kind"))!="hard":
        return []
    try: limit=int(row.get("value") or 0)
    except Exception: return []
    if limit!=1:
        return []
    excluded=set(st.get("excluded_teachers",[]))
    all_allowed=[n for n in ALL if n not in excluded]
    p13=[n for n in dict.fromkeys(e13 or []) if n in ALL and n not in excluded]
    ps=[n for n in _school_pool(es or []) if n not in excluded]
    pos13=_diag_positions_13(st)[0]; posS=_school_positions(st)[0]
    by=defaultdict(list)
    for p in pos13: by[(p.get("abbr"),p.get("slot"))].append(("1-3",p))
    for p in posS: by[(p.get("abbr"),p.get("slot"))].append(("school",p))
    order=defaultdict(list)
    for b in SEED.get("breaks",[]): order[b.get("abbr")].append(b.get("label"))
    affected=[];max_need=0;cases=0
    for ab,slots in order.items():
        for s1,s2 in zip(slots,slots[1:]):
            pair=by.get((ab,s1),[])+by.get((ab,s2),[])
            if not pair: continue
            edges=[]
            indiv_ok=True
            for sl in (s1,s2):
                part=by.get((ab,sl),[])
                pedges=[]
                for scope,pos in part:
                    freeze=bool(st.get("freeze_pool_13" if scope=="1-3" else "freeze_pool_school",False))
                    pool=(p13 if scope=="1-3" else ps) if freeze else all_allowed
                    pedges.append(_preflight_teacher_allowed_v524(st,scope,pos,pool))
                if pedges and _max_bipartite_match_v524(pedges)<len(pedges):
                    indiv_ok=False;break
            if not indiv_ok: continue
            for scope,pos in pair:
                freeze=bool(st.get("freeze_pool_13" if scope=="1-3" else "freeze_pool_school",False))
                pool=(p13 if scope=="1-3" else ps) if freeze else all_allowed
                edges.append(_preflight_teacher_allowed_v524(st,scope,pos,pool))
            possible=_max_bipartite_match_v524(edges);required=len(edges)
            if possible<required:
                need=required-possible
                max_need=max(max_need,need);cases+=need
                affected.append({"abbr":ab,"slots":[s1,s2],"required_positions":required,
                                 "possible_without_consecutive":possible,"minimum_consecutive_exceptions":need})
    if not affected:
        return []
    # v5.60: this is a human-capacity guardrail, not a comfort rule. Never
    # silently soften it. If strict preflight pressure exists, the main search
    # must first relax ordinary comfort constraints or report no human-realistic plan.
    if not _preflight_soften_global_v553(st,"max_consecutive_duties"):
        return []
    return [{"key":"max_consecutive_duties","label":row.get("label","Maks. dyżurów następujących po sobie"),
             "from":"MUSI BYĆ","to":"ZALECANE 5 — Najwyższa","priority":5,"proof":"adjacent_slot_matching",
             "minimum_exception_cases":cases,"minimum_teachers":max_need,"affected_slots":affected,
             "reason":f"Co najmniej {max_need} nauczyciel(i) musi mieć kolejne dyżury w co najmniej jednej parze sąsiednich przerw; inaczej pełna obsada jest niemożliwa."}]

def _auto_relax_numeric_v553(st,recommendations):
    changes=[]
    for x in recommendations or []:
        key=str(x.get("key") or "")
        if key not in PREFLIGHT_NUMERIC_RELAX_KEYS_V553:
            continue
        row=_global_row(st,key)
        if not row or not row.get("enabled") or normalize_kind(row.get("kind"))!="hard":
            continue
        before=row.get("value")
        if not _preflight_soften_global_v553(st,key):
            continue
        changes.append({"key":key,"label":row.get("label",key),
                        "from":"MUSI BYĆ","to":"ZALECANE 5 — Najwyższa","priority":5,
                        "proof":"capacity_lower_bound","configured_value":before,
                        "minimum_required_value":x.get("after"),
                        "minimum_exception_cases":max(1,int(x.get("after",0) or 0)-int(before or 0)),
                        "minimum_teachers":1,
                        "affected_slots":[],
                        "reason":f"Z samej wymaganej obsady wynika dolna granica {x.get('after')}; ustawione {before} jest niewykonalne jako reguła bezwzględna."})
    return changes

def _repair_preflight_v520(st,e13,es,auto_staffing_changes=None):
    """Cheap necessary-condition checks before any repair search starts.
    Timetable-driven zone staffing is applied before this function."""
    st=ensure_state_schema(_copy.deepcopy(st))
    auto_staffing_changes=list(auto_staffing_changes or [])
    excluded=set(st.get("excluded_teachers",[]))|set(st.get("absent_teachers",[]))
    active=[n for n in ALL if n not in excluded]
    p13=list(active)
    ps=list(active)
    pos13,_,_=_diag_positions_13(st)
    posS,_,_,_=_school_positions(st)
    req13=len(pos13); reqS=len(posS)
    day13=defaultdict(int); dayS=defaultdict(int); long13=defaultdict(int); longS=defaultdict(int)
    try: long_threshold=LONG_BREAK_MINUTES
    except Exception: long_threshold=15
    for x in pos13:
        day13[x.get("abbr")]+=1
        if int((x.get("break") or {}).get("minutes",0) or 0)>=long_threshold: long13[x.get("abbr")]+=1
    for x in posS:
        dayS[x.get("abbr")]+=1
        if int((x.get("break") or {}).get("minutes",0) or 0)>=long_threshold: longS[x.get("abbr")]+=1

    rec=[]; alternatives=[]; checks=[]
    def hard_value(key):
        row=_global_row(st,key)
        if row.get("enabled") and normalize_kind(row.get("kind"))=="hard":
            try:return max(0,int(row.get("value") or 0))
            except Exception:return 0
        return None
    def add_rec(key,need,reason):
        cur=hard_value(key)
        if cur is None or need<=cur:return
        row=_global_row(st,key)
        rec.append({"key":key,"label":row.get("label",key),"before":cur,"after":int(need),
                    "reason":reason,"tier":"capacity","comfort_impact":"niski"})
    # v5.78 has no candidate pools. Capacity is checked globally and for
    # places whose configurable category checklist allows exactly one teacher group.

    wk=hard_value("max_week")
    if wk is not None and wk>0:
        needs=[]
        if active and req13+reqS:
            needs.append(("wszyscy aktywni",math.ceil((req13+reqS)/len(active))))
        group_defaults=st.get("group_place_defaults",{}) or {}
        exclusive_counts=Counter()
        for pos in posS:
            key="school|"+str(pos.get("location") or "")
            allowed=[g for g in ("1-3","school","wf") if key in set(group_defaults.get(g,[]) or [])]
            if len(allowed)==1: exclusive_counts[allowed[0]]+=1
        for g,count in sorted(exclusive_counts.items()):
            members=[n for n in active if GROUP.get(n)==g]
            if count and members:
                label="WF-only" if g=="wf" else ("grupa "+str(g))
                needs.append((label,math.ceil(count/len(members))))
        need=max([x[1] for x in needs] or [wk])
        add_rec("max_week",need,"minimalna pojemność tygodniowa: "+", ".join(f"{sc} = {v}" for sc,v in needs))

    d13=hard_value("max_day_13")
    if d13 is not None and p13 and day13:
        need=max(math.ceil(v/len(p13)) for v in day13.values())
        add_rec("max_day_13",need,"minimalna dzienna pojemność puli 1–3")
    ds=hard_value("max_day_school")
    if ds is not None and active and dayS:
        vals=[math.ceil(v/len(active)) for v in dayS.values()]
        group_defaults=st.get("group_place_defaults",{}) or {}
        ex_by_day=defaultdict(Counter)
        for pos in posS:
            key="school|"+str(pos.get("location") or "")
            allowed=[g for g in ("1-3","school","wf") if key in set(group_defaults.get(g,[]) or [])]
            if len(allowed)==1: ex_by_day[pos.get("abbr")][allowed[0]]+=1
        for ab,counts in ex_by_day.items():
            for g,count in counts.items():
                members=[n for n in active if GROUP.get(n)==g]
                if members: vals.append(math.ceil(count/len(members)))
        add_rec("max_day_school",max(vals or [ds]),"minimalna dzienna pojemność z uwzględnieniem miejsc ekskluzywnych")

    lweek=hard_value("max_long_week")
    if lweek is not None:
        vals=[]
        if p13 and long13: vals.append(("1–3",math.ceil(sum(long13.values())/len(p13))))
        if ps and longS: vals.append(("szkoła",math.ceil(sum(longS.values())/len(ps))))
        union=set(p13)|set(ps)
        if union: vals.append(("łącznie",math.ceil((sum(long13.values())+sum(longS.values()))/len(union))))
        if vals:add_rec("max_long_week",max(v for _,v in vals),"minimalna pojemność długich przerw: "+", ".join(f"{sc} ≥ {v}" for sc,v in vals))
    lday=hard_value("max_long_day")
    if lday is not None:
        vals=[]
        if p13 and long13: vals.append(max(math.ceil(v/len(p13)) for v in long13.values()))
        if ps and longS: vals.append(max(math.ceil(v/len(ps)) for v in longS.values()))
        if vals:add_rec("max_long_day",max(vals),"minimalna dzienna pojemność długich przerw")

    for key in ("max_week","max_day_13","max_day_school","max_long_day","max_long_week","max_consecutive_duties"):
        row=_global_row(st,key)
        checks.append({"key":key,"enabled":bool(row.get("enabled")),"kind":normalize_kind(row.get("kind")),
                       "value":row.get("value")})
    # Deduplicate a key, keeping the strongest lower bound.
    by={}
    for x in rec:
        old=by.get(x["key"])
        if old is None or int(x["after"])>int(old["after"]):by[x["key"]]=x
    rec=list(by.values())
    slotcheck=_slot_feasibility_v524(st,p13,ps)
    obvious=list(slotcheck.get("candidates",[]))
    for x in rec:
        obvious.append(_repair_candidate_v2(
            f"gval:{x['key']}:{int(x['after'])}",
            f"{x.get('label',x['key'])}: {x['before']} -> {x['after']} (precheck: {x.get('reason','minimalna pojemność')})",
            0,"oczywista wykonalność",False))
    return {"ok":True,
            "blocking":bool(rec or slotcheck.get("problems")),
            "recommendations":rec,"alternatives":alternatives,"checks":checks,
            "slot_problems":slotcheck.get("problems",[]),"obvious_candidates":obvious,
            "auto_staffing_changes":auto_staffing_changes,
            "required":{"school13":req13,"school":reqS},
            "pool_sizes":{"school13":len(p13),"school":len(ps)}}

def _repair_candidates_v2(st,e13,es,baseline,preflight=None):
    out=[]; seen=set()
    def add(c,stage=1,level=0):
        if c["token"] in seen:return
        seen.add(c["token"]);c["search_stage"]=stage;c["relax_level"]=int(level or 0)
        c["wait_relax"]=_token_relaxes_rule_v537(c.get("token"),"avoid_wait")
        out.append(c)

    # 0. Cheap proven repairs from preflight. Legacy pool tokens are deliberately
    # discarded in v5.78 because all active teachers are already part of the model.
    for raw in (preflight or {}).get("obvious_candidates",[]):
        c=dict(raw); tok=str(c.get("token",""))
        if tok.startswith(("add13:","addschool:","add13group:","move13:","moveschool:")):
            continue
        add(c,1)

    # 1. ALL feasible values of neutral capacity constraints, not only +1/+2.
    byday=defaultdict(int); longby=defaultdict(int)
    try: long_threshold=LONG_BREAK_MINUTES
    except Exception: long_threshold=15
    for b in SEED.get("breaks",[]):
        byday[b.get("abbr")]+=1
        if int(b.get("minutes",0) or 0)>=long_threshold:longby[b.get("abbr")]+=1
    max_day=max(byday.values() or [10]); max_long_day=max(longby.values() or [2])
    max_week=len(SEED.get("breaks",[])) or 50; max_long_week=sum(longby.values()) or 10
    # Etap 1: tylko pojemność/organizacja, bez pogarszania komfortu konkretnej osoby.
    neutral_caps={"max_day_13":max_day,"max_day_school":max_day,"max_week":max_week}
    basecost={"max_day_13":90,"max_day_school":90,"max_week":100}
    for key,cap in neutral_caps.items():
        r=_global_row(st,key)
        if not r or not r.get("enabled") or normalize_kind(r.get("kind"))!="hard":continue
        try:cur=max(0,int(r.get("value") or 0))
        except Exception:continue
        for nv in range(cur+1,int(cap)+1):
            add(_repair_candidate_v2(f"gval:{key}:{nv}",
                f"{r.get('label',key)}: {cur} → {nv}",
                basecost.get(key,150)+(nv-cur-1)*12,"limity organizacyjne",False),1)

    # Limity długich przerw i serii dyżurów są regułami komfortu, nie neutralną pojemnością.
    # Zwiększenie ich może pomóc wykonalności, ale wolno je sprawdzać dopiero po wyczerpaniu etapu 1.
    _gorder={str(r.get("key")):i+1 for i,r in enumerate(st.get("global_constraints",[]))}
    comfort_numeric={
        "max_long_day":(max_long_day,3,650),
        "max_long_week":(max_long_week,3,620),
        "max_consecutive_duties":(max_day,3,900),
    }
    for key,(cap,base_stage,base_cost) in comfort_numeric.items():
        r=_global_row(st,key)
        if not r or not r.get("enabled") or normalize_kind(r.get("kind"))!="hard":continue
        try:cur=max(0,int(r.get("value") or 0))
        except Exception:continue
        for nv in range(cur+1,int(cap)+1):
            stage=base_stage
            # Kolejne dyżury są kompromisem komfortowym, ale wcześniejszym niż oczekiwanie.
            # Stage 4 = WF fallback; stage 5 = after_last_long; stage 6 = avoid_wait.
            add(_repair_candidate_v2(f"gval:{key}:{nv}",
                f"{r.get('label',key)}: {cur} → {nv}",
                base_cost+(nv-cur-1)*80,"komfort nauczyciela",True),stage,_gorder.get(key,999))

    # v5.78: legacy pool expansion/move candidates are obsolete.
    # Every active teacher is already visible to CP-SAT. Exact teacher x place
    # preferences and lexicographic WF fallback decide participation.

    # Coverage requirements are NOT automatically reduced.
    # Policy: organization -> teacher-specific concession order -> global table order -> waiting last.
    costs={"avoid_wait":10000,"before_first_long":7000,"after_last_long":7000,
           "before_first_short":2200,"after_last_short":2200,
           "balance_day":500,"balance_week":500,
           "lesson_load_fairness":700,"prefer_home_group":800}
    teacher_keys={"before_first_short","after_last_short",
                  "before_first_long","after_last_long","avoid_wait"}

    # Every teacher's rank 1 is exhausted before any rank 2, etc.
    for teacher in sorted(ALL,key=_teacher_sort_key):
        order=list(st.get("teacher_relax_order",{}).get(teacher,[]) or [])
        for rank,key in enumerate(order,1):
            if key not in teacher_keys: continue
            row=_global_row(st,key)
            if not row.get("enabled") or normalize_kind(row.get("kind"))!="hard" or key in NEVER_AUTO_RELAX_KEYS: continue
            stage=6 if key=="avoid_wait" else (5 if key=="after_last_long" else (3 if key=="before_first_long" else 2))
            add(_repair_candidate_v2(
                f"trelax:{teacher}|{key}",
                f"{_display_teacher(teacher)}: indywidualne ustępstwo — {row.get('label',key)}",
                1300+rank*20,"indywidualna kolejność ustępstw",True),stage,rank)

    # Global relaxations follow the visible table order exactly.
    for pos,r in enumerate(st.get("global_constraints",[]),1):
        key=r.get("key")
        if key=="prefer_home_group" and r.get("enabled") and normalize_kind(r.get("kind"))=="soft":
            add(_repair_candidate_v2(
                "goff:prefer_home_group",
                "Siatka nauczyciel × miejsce: tymczasowo pomiń preferencje dla wariantu",
                costs.get(key,800),"globalna kolejność ustępstw",True),2,pos)
            continue
        if not r.get("enabled") or normalize_kind(r.get("kind"))!="hard" or key in NEVER_AUTO_RELAX_KEYS:continue
        stage=6 if key=="avoid_wait" else (5 if key=="after_last_long" else 3)
        add(_repair_candidate_v2("gsoft:"+key,f"{r.get('label',key)}: MUSI BYĆ → ZALECANE",
             costs.get(key,1400),"globalna kolejność ustępstw",True),stage,pos)

    # Administrator-created individual constraints follow their order per teacher,
    # after the teacher's standard concession list.
    _ind_rank=defaultdict(int)
    for r in st.get("individual_constraints",[]):
        if not r.get("enabled",True) or normalize_kind(r.get("kind"))!="hard":continue
        rid=str(r.get("id") or "")
        if not rid:continue
        teacher=str(r.get("teacher") or "")
        _ind_rank[teacher]+=1; rank=100+_ind_rank[teacher]
        rule=str(r.get("rule") or "")
        if rule in ("max_day","max_week"):
            try:cur=max(0,int(r.get("value") or 0))
            except Exception:cur=0
            cap=max_day if rule=="max_day" else max_week
            for nv in range(cur+1,int(cap)+1):
                add(_repair_candidate_v2(f"indval:{rid}:{nv}",
                    f"{_display_teacher(r.get('teacher','?'))}: {rule} {cur} → {nv}",
                    115+(nv-cur-1)*12,"limity indywidualne",False),2,rank)
        add(_repair_candidate_v2("indsoft:"+rid,
            f"{_display_teacher(r.get('teacher','?'))}: {rule} — MUSI BYĆ → ZALECANE",
            1800,"indywidualne reguły administratora",True),2,rank)
    # Administrator locks and manual blocks are SYSTEM-FIXED.
    # The generator may diagnose them, but never creates unlock/unblock candidates.
    return sorted(out,key=lambda c:(c.get("search_stage",9),c.get("relax_level",0),c.get("human_cost",0),c.get("label","")))

def _global_row(state,key):
    return next((r for r in state.get("global_constraints",[]) if r.get("key")==key),{})

def _repair_change_details(base_state,trial_state,changes):
    out=[]
    for c in changes:
        x=dict(c); tok=str(c.get("token","")); before=""; after=""
        if tok.startswith("gval:"):
            _,key,val=tok.split(":",2); b=_global_row(base_state,key); a=_global_row(trial_state,key)
            before=str(b.get("value","—")); after=str(a.get("value",val))
        elif tok.startswith("gsoft:"):
            key=tok[6:]; b=_global_row(base_state,key); a=_global_row(trial_state,key)
            before=("MUSI BYĆ" if b.get("kind")=="hard" else "ZALECANE"); after=("MUSI BYĆ" if a.get("kind")=="hard" else "ZALECANE")
        elif tok.startswith("trelax:"):
            _,rest=tok.split(":",1); teacher,key=rest.split("|",1)
            row=_global_row(base_state,key)
            before="MUSI BYĆ globalnie";after=f"ZALECANE tylko dla {_display_teacher(teacher)} — {row.get('label',key)}"
        elif tok.startswith("goff:"):
            before="włączona";after="wyłączona"
        elif tok.startswith("m13:"):
            _,rest=tok.split(":",1);ab,slot,val=rest.split("|",2)
            before=str(base_state.get("min_people_13",{}).get(f"{ab}|{slot}",2));after=str(val)
        elif tok.startswith("ms:"):
            _,rest=tok.split(":",1);ab,slot,loc,val=rest.rsplit("|",3)
            before=str(base_state.get("min_people_school",{}).get(f"{ab}|{slot}|{loc}",1));after=str(val)
        elif tok.startswith(("add13:","addschool:","add13group:")):
            before="poza pulą";after="dopuszczony do puli"
        elif tok.startswith("move13:"):
            before="pula całej szkoły";after="pula 1–3"
        elif tok.startswith("moveschool:"):
            before="pula 1–3";after="pula całej szkoły"
        elif tok.startswith("prefclr:"):
            before="ZABRONIONA";after="neutralna"
        elif tok.startswith("indval:"):
            _,rid,val=tok.split(":",2)
            br=next((r for r in base_state.get("individual_constraints",[]) if str(r.get("id"))==rid),{})
            ar=next((r for r in trial_state.get("individual_constraints",[]) if str(r.get("id"))==rid),{})
            before=str(br.get("value","—"));after=str(ar.get("value",val))
        elif tok.startswith("indsoft:"):
            before="MUSI BYĆ";after="ZALECANE"
        elif tok.startswith("unlock:"):
            before="stały przydział";after="odblokowany"
        elif tok.startswith("unblock:"):
            before="zablokowany";after="dostępny"
        x["before"]=before;x["after"]=after
        if before or after: x["exact_change"]=f"{before} → {after}"
        out.append(x)
    return out

def _impact_summary(tc,waits):
    by={}
    for w in waits:
        n=w.get("teacher")
        if not n: continue
        row=by.setdefault(n,{"teacher":n,"wait_duties":0,"wait_lessons_total":0,
                             "max_wait_lessons":0,"offday_duties":0,"duties":[]})
        ww=int(w.get("wait",0) or 0)
        kind=w.get("wait_kind") or ("offday" if ww==9 else "gap")
        row["wait_duties"]+=1
        if kind=="offday":
            row["offday_duties"]+=1
        else:
            row["wait_lessons_total"]+=ww
            row["max_wait_lessons"]=max(row["max_wait_lessons"],ww)
        duty={k:w.get(k) for k in ("scope","abbr","slot","location","station","time","wait","wait_kind") if w.get(k) not in (None,"")}
        duty["wait_kind"]=kind
        row["duties"].append(duty)
    wait_rows=sorted(by.values(),key=lambda x:(-x["offday_duties"],-x["wait_lessons_total"],-x["wait_duties"],_teacher_sort_key(x["teacher"])))
    wait_names={x["teacher"] for x in wait_rows}
    more=fewer=same=0
    for row in tc.get("teachers",[]):
        row["net_change"]=int(row.get("added",0))-int(row.get("removed",0))
        row["waiting"]=row["teacher"] in wait_names
        wr=by.get(row["teacher"],{})
        row["wait_duties"]=wr.get("wait_duties",0)
        row["wait_lessons_total"]=wr.get("wait_lessons_total",0)
        row["offday_duties"]=wr.get("offday_duties",0)
        if row["net_change"]>0:more+=1
        elif row["net_change"]<0:fewer+=1
        else:same+=1
    tc["teachers"].sort(key=lambda x:(0 if x.get("waiting") else 1,-x.get("offday_duties",0),-x.get("wait_lessons_total",0),-abs(x.get("net_change",0)),-(x.get("added",0)+x.get("removed",0)),x["teacher"]))
    return {"more_duties_teachers":more,"fewer_duties_teachers":fewer,"same_count_moved_teachers":same,
            "waiting_teachers_count":len(wait_rows),"waiting_duties":sum(x["wait_duties"] for x in wait_rows),
            "wait_lessons_total":sum(x["wait_lessons_total"] for x in wait_rows),
            "offday_duties":sum(x["offday_duties"] for x in wait_rows),
            "waiting_teachers":wait_rows}

def _eval_combo_local(state,e13,es,tokens,solver_workers=2):
    # Cheap screening only. The expensive both-direction check is reserved for
    # promising partial results in _eval_combo_deep.
    started=_time.perf_counter()
    st,p13,ps=_apply_repair_tokens_v2(state,e13,es,tokens)
    st["solver_internal_workers"]=max(1,int(solver_workers or 1))
    st["solver_coverage_seconds"]=4
    st["solver_coverage_retry_seconds"]=20
    ev=_joint_order_v2(st,p13,ps,"13-first",False)
    return {"missing":ev["missing"],"inconclusive":bool(ev.get("inconclusive")),"order":ev.get("order"),
            "coverage13":{k:ev["school13"][k] for k in ("required","filled","missing")},
            "coverageSchool":{k:ev["school"][k] for k in ("required","filled","missing")},
            "elapsed_s":_time.perf_counter()-started}

def _eval_combo_deep(state,e13,es,tokens):
    started=_time.perf_counter()
    st,p13,ps=_apply_repair_tokens_v2(state,e13,es,tokens)
    # Deep probe is a fast live-contract proof, not a second quality optimizer.
    # Quality optimization runs exactly once later, after the first full draft
    # has already been published to the GUI.
    st["solver_contract_only"]=True
    st["solver_internal_workers"]=4
    st["solver_coverage_seconds"]=6
    st["solver_coverage_retry_seconds"]=20
    st["solver_wf_fallback_seconds"]=5
    ev=_joint_coverage_v2(st,p13,ps,optimize=False)
    return {"missing":ev["missing"],"inconclusive":bool(ev.get("inconclusive")),"order":ev.get("order"),
            "coverage13":{k:ev["school13"][k] for k in ("required","filled","missing")},
            "coverageSchool":{k:ev["school"][k] for k in ("required","filled","missing")},
            "result13":ev["school13"].get("assignments",[]),
            "resultSchool":ev["school"].get("assignments",[]),
            "waits13":ev["school13"].get("waits",[]),
            "waitsSchool":ev["school"].get("waits",[]),
            "diagnostics13":_copy.deepcopy(ev["school13"].get("diagnostics",{})),
            "diagnosticsSchool":_copy.deepcopy(ev["school"].get("diagnostics",{})),
            "optimized_full":False,
            "elapsed_s":_time.perf_counter()-started}

def _near_full_candidate_items_v580(candidates,base,limit=16):
    """Minimal single-step repairs for a baseline with only 1-3 missing positions."""
    try: missing=int(base.get("missing",10**6))
    except Exception: return []
    if missing<1 or missing>3:return []
    # Keep only the smallest numeric step per constraint. Do not jump to late
    # comfort fallbacks here; normal stage ordering still controls those.
    numeric={}
    other=[]
    for c in candidates or []:
        stage=int(c.get("search_stage",9) or 9)
        if stage>3:continue
        tok=str(c.get("token") or "")
        if tok.startswith("gval:"):
            parts=tok.split(":",2)
            if len(parts)!=3:continue
            key=parts[1]
            try:v=int(parts[2])
            except Exception:continue
            old=numeric.get(key)
            if old is None or v<old[0]:numeric[key]=(v,c)
        elif tok.startswith(("indval:","indsoft:")):
            other.append(c)
        elif tok.startswith("gsoft:before_first_long"):
            other.append(c)
    items=[{"tokens":[c["token"]],"changes":[c],"near_full":True}
           for _v,c in numeric.values()]
    items += [{"tokens":[c["token"]],"changes":[c],"near_full":True} for c in other]
    items.sort(key=lambda x:(int(x["changes"][0].get("search_stage",9)),
                             int(x["changes"][0].get("relax_level",0)),
                             int(x["changes"][0].get("human_cost",0)),
                             str(x["changes"][0].get("token",""))))
    return items[:max(1,int(limit or 16))]

def _eval_combo_micro_v580(state,e13,es,tokens):
    started=_time.perf_counter()
    st,p13,ps=_apply_repair_tokens_v2(state,e13,es,tokens)
    st["solver_contract_only"]=True
    st["solver_internal_workers"]=2
    st["solver_coverage_seconds"]=3
    st["solver_coverage_retry_seconds"]=8
    st["solver_wf_fallback_seconds"]=3
    ev=_joint_coverage_v2(st,p13,ps,optimize=False)
    return {"missing":ev["missing"],"inconclusive":bool(ev.get("inconclusive")),"order":ev.get("order"),
            "coverage13":{k:ev["school13"][k] for k in ("required","filled","missing")},
            "coverageSchool":{k:ev["school"][k] for k in ("required","filled","missing")},
            "result13":ev["school13"].get("assignments",[]),
            "resultSchool":ev["school"].get("assignments",[]),
            "waits13":ev["school13"].get("waits",[]),
            "waitsSchool":ev["school"].get("waits",[]),
            "diagnostics13":_copy.deepcopy(ev["school13"].get("diagnostics",{})),
            "diagnosticsSchool":_copy.deepcopy(ev["school"].get("diagnostics",{})),
            "elapsed_s":_time.perf_counter()-started}

def _terminal_probe_row(item,phase,source="local"):
    changes=list(item.get("changes",[]) or []) if isinstance(item,dict) else []
    tokens=list(item.get("tokens",[]) or []) if isinstance(item,dict) else []
    title=" + ".join(str(c.get("label") or c.get("token") or "") for c in changes if c) or ("bez zmian parametrów" if not tokens else " + ".join(tokens))
    return {"id":_hashlib.sha1(("|".join(sorted(tokens))+"|"+str(phase)+"|"+str(source)).encode("utf-8")).hexdigest()[:12],
            "phase":str(phase),"source":str(source),"title":title,
            "tokens":tokens,"changes":[{"label":c.get("label"),"token":c.get("token")} for c in changes],
            "started_at":datetime.now().isoformat(timespec="seconds")}

def _evaluate_near_full_parallel_v580(job,state,e13,es,items):
    queue=_repair_learning_order(job,list(items or []))
    if not queue:return
    workers=max(1,min(4,int((_farm_config() or {}).get("local_workers",4) or 4)))
    ex=_ThreadPoolExecutor(max_workers=workers,thread_name_prefix="repair-near")
    pending={}
    total=len(queue);done_count=0
    try:
        with REPAIR_JOB_LOCK:
            job["block_label"]="Szybka naprawa 1–3 braków"
            job["block_total"]=total;job["block_done"]=0
        while queue or pending:
            if not _repair_pausepoint(job):break
            while queue and len(pending)<workers:
                item=queue.pop(0)
                probe=_terminal_probe_row(item,"near-full","local")
                with REPAIR_JOB_LOCK:
                    xs=[x for x in job.get("active_probes",[]) if x.get("id")!=probe["id"]]
                    xs.append(probe); job["active_probes"]=xs[-12:]
                    job["current_probe"]=probe
                pending[ex.submit(_eval_combo_micro_v580,state,e13,es,item.get("tokens",[]))]=item
            done,_=_fwait(list(pending),timeout=.15,return_when=_FIRST_COMPLETED)
            if not done:continue
            for fut in done:
                item=pending.pop(fut)
                probe=_terminal_probe_row(item,"near-full","local")
                try:ev=fut.result()
                except Exception as exc:ev={"missing":10**6,"inconclusive":True,"error":repr(exc),"elapsed_s":0}
                done_count+=1
                with REPAIR_JOB_LOCK:
                    job["active_probes"]=[x for x in job.get("active_probes",[]) if x.get("id")!=probe["id"]]
                    job["block_done"]=done_count
                    job["stage"]="Szybka naprawa 1–3 braków"
                yield item,ev,"near-full"
                if not ev.get("inconclusive") and int(ev.get("missing",10**6))==0:
                    for pf in pending:pf.cancel()
                    return
    finally:
        ex.shutdown(wait=False,cancel_futures=True)

def _evaluate_deep_parallel(job,state,e13,es,items,stage):
    ex=_ThreadPoolExecutor(max_workers=2,thread_name_prefix="repair-deep")
    pending={}
    queue=list(items)
    try:
        while pending or queue:
            if not _repair_pausepoint(job):break
            while len(pending)<2 and queue:
                item=queue.pop(0); pending[ex.submit(_eval_combo_deep,state,e13,es,item["tokens"])]=item
            with REPAIR_JOB_LOCK:
                job["stage"]=stage; job["deep_active"]=len(pending)
            done,_=_fwait(list(pending),timeout=.2,return_when=_FIRST_COMPLETED)
            for fut in done:
                item=pending.pop(fut)
                try:ev=fut.result()
                except Exception as exc:ev={"missing":10**6,"inconclusive":True,"error":repr(exc),"elapsed_s":0}
                yield item,ev,"deep-local"
    finally:
        with REPAIR_JOB_LOCK: job["deep_active"]=0
        ex.shutdown(wait=False,cancel_futures=True)

def _evaluate_items_parallel(job,state,e13,es,items,stage):
    cfg=_farm_config()
    local_n=max(1,min(8,int(cfg.get("local_workers",4))))
    # With many parallel jobs use one CP-SAT worker per local job so the API keeps CPU headroom.
    local_solver_workers=2 if local_n>=4 else 3
    seedsha=_seed_sha()
    local_items=_repair_learning_order(job,list(items))
    remote={}
    with REPAIR_JOB_LOCK:
        job["block_label"]=stage
        job["block_total"]=len(local_items)
        job["block_done"]=0
        job["local_workers_configured"]=local_n
        job["local_solver_threads_each"]=local_solver_workers
        job["remote_connected"]=0
        job["local_active"]=0
        job.setdefault("local_completed",0);job.setdefault("remote_completed",0)
    ex=_ThreadPoolExecutor(max_workers=local_n,thread_name_prefix="repair-local")
    pending={}
    try:
        while pending or remote or local_items:
            if not _repair_pausepoint(job): break

            # Remote workers are discovered continuously, not only once at stage start.
            remote_workers=_repair_farm.active_workers(WORKER_PROTOCOL_VERSION,seedsha,within=90) if _farm_config().get("enabled") else []
            local_host=_socket.gethostname().casefold()
            remote_workers=[w for w in remote_workers if str(w.get("hostname") or "").casefold()!=local_host]
            # Keep roughly two queued tasks per genuinely remote worker.
            remote_target=min(len(items),len(remote_workers)*2)
            while len(remote)<remote_target and local_items:
                item=local_items.pop(0)
                trial,p13,ps=_apply_repair_tokens_v2(state,e13,es,item["tokens"])
                trial["solver_coverage_seconds"]=4
                trial["solver_coverage_retry_seconds"]=20
                positions13,_,_=_diag_positions_13(trial)
                positionsSchool,_,_,_=_school_positions(trial)
                p13set=set(p13); psset=set(ps)
                for pos in positions13:
                    if pos.get("required_teacher") and pos.get("required_teacher") not in p13set:
                        pos["required_teacher"]="__OUTSIDE_POOL__"
                for pos in positionsSchool:
                    if pos.get("required_teacher") and pos.get("required_teacher") not in psset:
                        pos["required_teacher"]="__OUTSIDE_POOL__"
                payload={"state":trial,"enabled13":p13,"enabledSchool":ps,
                         "positions13":positions13,"positionsSchool":positionsSchool,
                         "seed":SEED,"group":GROUP}
                tid=_repair_farm.enqueue(job["id"],WORKER_PROTOCOL_VERSION,seedsha,payload)
                probe=_terminal_probe_row(item,stage,"remote")
                with REPAIR_JOB_LOCK:
                    xs=[x for x in job.get("active_probes",[]) if x.get("id")!=probe["id"]]
                    xs.append(probe);job["active_probes"]=xs[-12:];job["current_probe"]=probe
                remote[tid]={"item":item,"started":_time.time(),"probe_id":probe["id"]}

            # Fill local slots from whatever remains after feeding remote workers.
            while len(pending)<local_n and local_items:
                item=local_items.pop(0)
                probe=_terminal_probe_row(item,stage,"local")
                with REPAIR_JOB_LOCK:
                    xs=[x for x in job.get("active_probes",[]) if x.get("id")!=probe["id"]]
                    xs.append(probe);job["active_probes"]=xs[-12:];job["current_probe"]=probe
                fut=ex.submit(_eval_combo_local,state,e13,es,item["tokens"],local_solver_workers)
                pending[fut]=item

            with REPAIR_JOB_LOCK:
                job["stage"]=stage
                job["local_active"]=len(pending)
                job["remote_connected"]=len(remote_workers)
                job["remote_active"]=len(remote)

            if pending:
                done,_=_fwait(list(pending),timeout=.18,return_when=_FIRST_COMPLETED)
                for fut in done:
                    item=pending.pop(fut)
                    probe=_terminal_probe_row(item,stage,"local")
                    try: result=fut.result()
                    except Exception as exc: result={"missing":10**6,"error":repr(exc),"elapsed_s":0}
                    with REPAIR_JOB_LOCK:
                        job["active_probes"]=[x for x in job.get("active_probes",[]) if x.get("id")!=probe["id"]]
                        job["local_completed"]+=1
                        job["local_active"]=len(pending)
                        job["block_done"]=min(int(job.get("block_total",0)),int(job.get("block_done",0))+1)
                    yield item,result,"local"

            # Collect remote results. A worker that joins in the middle of a stage is used on the next loop.
            for tid,meta in list(remote.items()):
                row=_repair_farm.get_task(tid)
                if row and row.get("status") in ("done","failed"):
                    remote.pop(tid,None)
                    with REPAIR_JOB_LOCK:
                        job["active_probes"]=[x for x in job.get("active_probes",[]) if x.get("id")!=meta.get("probe_id")]
                    if row["status"]=="done" and isinstance(row.get("result"),dict):
                        result=row["result"];result["elapsed_s"]=float(result.get("elapsed_s",0) or 0)
                        with REPAIR_JOB_LOCK:
                            job["remote_completed"]+=1
                            job["block_done"]=min(int(job.get("block_total",0)),int(job.get("block_done",0))+1)
                        yield meta["item"],result,"remote"
                    else:
                        fut=ex.submit(_eval_combo_local,state,e13,es,meta["item"]["tokens"],local_solver_workers)
                        pending[fut]=meta["item"]
                elif _time.time()-meta["started"]>240:
                    _repair_farm.cancel_task(tid);remote.pop(tid,None)
                    with REPAIR_JOB_LOCK:
                        job["active_probes"]=[x for x in job.get("active_probes",[]) if x.get("id")!=meta.get("probe_id")]
                    probe=_terminal_probe_row(meta["item"],stage,"local")
                    with REPAIR_JOB_LOCK:
                        xs=[x for x in job.get("active_probes",[]) if x.get("id")!=probe["id"]]
                        xs.append(probe);job["active_probes"]=xs[-12:];job["current_probe"]=probe
                    fut=ex.submit(_eval_combo_local,state,e13,es,meta["item"]["tokens"],local_solver_workers)
                    pending[fut]=meta["item"]

            if not pending and not remote and not local_items: break
            if not pending:_time.sleep(.12)
    finally:
        ex.shutdown(wait=False,cancel_futures=True)
        with REPAIR_JOB_LOCK:
            job["local_active"]=0
            job["remote_active"]=0
            job["active_probes"]=[]


def _observed_full_limits(opt,state):
    rows=[]
    for scope,key in (("1–3","school13"),("szkoła","school")):
        for a in opt.get(key,{}).get("assignments",[]) or []:
            if a.get("teacher"):
                rows.append({"teacher":a.get("teacher"),"abbr":a.get("abbr"),"slot":a.get("slot"),"scope":scope})
    byweek=Counter(); byday=Counter(); bylongweek=Counter(); bylongday=Counter()
    slots=defaultdict(set)
    try: long_threshold=LONG_BREAK_MINUTES
    except Exception: long_threshold=15
    mins={(b.get("abbr"),b.get("label")):int(b.get("minutes",0) or 0) for b in SEED.get("breaks",[])}
    order=defaultdict(list)
    for b in SEED.get("breaks",[]): order[b.get("abbr")].append(b.get("label"))
    for a in rows:
        n=a["teacher"];ab=a["abbr"];sl=a["slot"]
        byweek[n]+=1;byday[(n,ab)]+=1;slots[(n,ab)].add(sl)
        if mins.get((ab,sl),0)>=long_threshold:
            bylongweek[n]+=1;bylongday[(n,ab)]+=1
    maxcon=0
    for (n,ab),have in slots.items():
        run=0
        for sl in order.get(ab,[]):
            if sl in have: run+=1;maxcon=max(maxcon,run)
            else: run=0
    return {
        "max_week":max(byweek.values() or [0]),
        "max_day_13":max(byday.values() or [0]),
        "max_day_school":max(byday.values() or [0]),
        "max_long_week":max(bylongweek.values() or [0]),
        "max_long_day":max(bylongday.values() or [0]),
        "max_consecutive_duties":maxcon,
        "teacher_week":dict(byweek),
        "teacher_day":{n:max([v for (t,_),v in byday.items() if t==n] or [0]) for n in byweek},
    }

def _tighten_numeric_repair_changes(base_state,trial_state,tokens,changes,opt):
    """After a full plan is found, tighten any raised numeric limit to the
    smallest value actually needed by that exact full assignment."""
    st=_copy.deepcopy(trial_state); toks=list(tokens); ch=[_copy.deepcopy(x) for x in changes]
    usage=_observed_full_limits(opt,st)
    replace={}; remove=set()
    for tok in list(toks):
        if tok.startswith("gval:"):
            _,key,val=tok.split(":",2)
            if key not in ("max_day_13","max_day_school","max_week","max_long_day","max_long_week","max_consecutive_duties"):continue
            try: trial=int(val); base=int(_global_row(base_state,key).get("value") or 0); need=int(usage.get(key,trial))
            except Exception:continue
            target=max(base,need)
            if target>=trial:continue
            _set_global_value(st,key,value=target,enabled=True)
            if target<=base: remove.add(tok)
            else: replace[tok]=f"gval:{key}:{target}"
        elif tok.startswith("indval:"):
            try: _,rid,val=tok.split(":",2); trial=int(val)
            except Exception:continue
            br=next((r for r in base_state.get("individual_constraints",[]) if str(r.get("id"))==rid),None)
            ar=next((r for r in st.get("individual_constraints",[]) if str(r.get("id"))==rid),None)
            if not br or not ar:continue
            rule=str(br.get("rule") or ""); n=br.get("teacher")
            try: base=int(br.get("value") or 0)
            except Exception:base=0
            need=int(usage.get("teacher_day",{}).get(n,0) if rule=="max_day" else usage.get("teacher_week",{}).get(n,0))
            target=max(base,need)
            if target>=trial:continue
            ar["value"]=target
            if target<=base: remove.add(tok)
            else: replace[tok]=f"indval:{rid}:{target}"
    if not remove and not replace:return st,toks,ch
    nt=[]
    for t in toks:
        if t in remove:continue
        nt.append(replace.get(t,t))
    nc=[]
    for c in ch:
        old=str(c.get("token",""))
        if old in remove:continue
        if old in replace:
            newtok=replace[old];c["token"]=newtok
            if newtok.startswith("gval:"):
                _,key,target=newtok.split(":",2)
                b=_global_row(base_state,key); c["label"]=f"{b.get('label',key)}: {b.get('value','—')} → {target}"
            elif newtok.startswith("indval:"):
                _,rid,target=newtok.split(":",2)
                br=next((r for r in base_state.get("individual_constraints",[]) if str(r.get("id"))==rid),{})
                c["label"]=f"{_display_teacher(br.get('teacher','?'))}: {br.get('rule','limit')} {br.get('value','—')} → {target}"
        nc.append(c)
    return ensure_state_schema(st),nt,nc

def _repair_variant_v2(base_state,trial_state,e13,es,tokens,changes,eval_fast):
    # Pełność jest tylko bramką. Każdy pełny kandydat przechodzi jeszcze fazę
    # optymalizacji komfortu; nie pokazujemy użytkownikowi surowego coverage-plan.
    fallback=None
    if (not eval_fast.get("inconclusive") and int(eval_fast.get("missing",1))==0
            and "result13" in eval_fast and "resultSchool" in eval_fast):
        fallback={
            "school13":{**eval_fast.get("coverage13",{}),"assignments":eval_fast.get("result13",[]),"waits":eval_fast.get("waits13",[])},
            "school":{**eval_fast.get("coverageSchool",{}),"assignments":eval_fast.get("resultSchool",[]),"waits":eval_fast.get("waitsSchool",[])},
            "missing":0,"inconclusive":False,"order":eval_fast.get("order")
        }
    run_state=_copy.deepcopy(trial_state)
    run_state["solver_internal_workers"]=3
    run_state["solver_coverage_seconds"]=12
    run_state["solver_coverage_retry_seconds"]=45
    optimized=_joint_coverage_v2(run_state,e13,es,optimize=True)
    opt=optimized if (not optimized.get("inconclusive") and int(optimized.get("missing",1))==0) else fallback
    if opt is None: opt=optimized
    trial_state,tokens,changes=_tighten_numeric_repair_changes(base_state,trial_state,tokens,changes,opt)
    old={**_map13_from_state(base_state),**_map_school_from_state(base_state)}
    new={**_map13_flat(opt["school13"]["assignments"]),**_map_school_flat(opt["school"]["assignments"])}
    tc=_teacher_changes(old,new)
    waits=[{**w,"scope":"1–3"} for w in opt["school13"].get("waits",[])]+[{**w,"scope":"szkoła"} for w in opt["school"].get("waits",[])]
    impact=_impact_summary(tc,waits)
    details=_repair_change_details(base_state,trial_state,changes)
    comfort=sum(1 for c in details if c.get("comfort_cost"))
    human=sum(int(c.get("human_cost",0)) for c in details)
    base_req13=len(_diag_positions_13(base_state)[0])
    base_req_school=len(_school_positions(base_state)[0])
    coverage_reduction=max(0,base_req13-int(opt["school13"].get("required",0)))+max(0,base_req_school-int(opt["school"].get("required",0)))
    score=(human+tc["positions_changed"]*4+tc["teachers_changed"]*2
           +impact["wait_lessons_total"]*3000+impact.get("offday_duties",0)*30000
           +comfort*5000+coverage_reduction*1000000)
    metrics=_draft_metrics_v527(opt,details,trial_state)
    all_assignments=list(opt["school13"].get("assignments",[]))+list(opt["school"].get("assignments",[]))
    metrics.update(_fairness_profile_v559(base_state,all_assignments,set(e13)|set(es)))
    metrics.update(_human_guardrail_profile_v560(base_state,all_assignments))
    d13=(opt["school13"].get("diagnostics",{}) or {})
    ds=(opt["school"].get("diagnostics",{}) or {})
    wf_scope=[int(metrics.get("wf_assignments_13",0) or 0),int(metrics.get("wf_assignments_school",0) or 0)]
    metrics["wf_fallback_scope_counts"]=wf_scope
    metrics["wf_fallback_lex_statuses"]=[d13.get("wf_fallback_status"),ds.get("wf_fallback_status")]
    metrics["wf_fallback_lex_proven"]=all(
        count==0 or metrics["wf_fallback_lex_statuses"][i]=="OPTIMAL"
        for i,count in enumerate(wf_scope)
    )
    after_scope=[
        sum(1 for a in opt["school13"].get("assignments",[]) if a.get("teacher") and is_after_last_lesson(a.get("teacher"),break_map().get((a.get("abbr"),a.get("slot")))) and int((break_map().get((a.get("abbr"),a.get("slot"))) or {}).get("minutes",0) or 0)>SHORT_BREAK_MAX_MINUTES),
        sum(1 for a in opt["school"].get("assignments",[]) if a.get("teacher") and is_after_last_lesson(a.get("teacher"),break_map().get((a.get("abbr"),a.get("slot")))) and int((break_map().get((a.get("abbr"),a.get("slot"))) or {}).get("minutes",0) or 0)>SHORT_BREAK_MAX_MINUTES)
    ]
    metrics["after_last_long_scope_counts"]=after_scope
    metrics["after_last_long_lex_statuses"]=[d13.get("after_last_long_lex_status"),ds.get("after_last_long_lex_status")]
    metrics["after_last_long_lex_proven"]=all(
        count==0 or metrics["after_last_long_lex_statuses"][i]=="OPTIMAL"
        for i,count in enumerate(after_scope)
    )
    before_scope=[
        sum(1 for a in opt["school13"].get("assignments",[]) if a.get("teacher") and is_before_first_lesson(a.get("teacher"),break_map().get((a.get("abbr"),a.get("slot")))) and int((break_map().get((a.get("abbr"),a.get("slot"))) or {}).get("minutes",0) or 0)>SHORT_BREAK_MAX_MINUTES),
        sum(1 for a in opt["school"].get("assignments",[]) if a.get("teacher") and is_before_first_lesson(a.get("teacher"),break_map().get((a.get("abbr"),a.get("slot")))) and int((break_map().get((a.get("abbr"),a.get("slot"))) or {}).get("minutes",0) or 0)>SHORT_BREAK_MAX_MINUTES)
    ]
    metrics["before_first_long_scope_counts"]=before_scope
    metrics["before_first_long_lex_statuses"]=[d13.get("before_first_long_lex_status"),ds.get("before_first_long_lex_status")]
    metrics["before_first_long_lex_proven"]=all(
        count==0 or metrics["before_first_long_lex_statuses"][i]=="OPTIMAL"
        for i,count in enumerate(before_scope)
    )
    return {
        "id":_uuid.uuid4().hex[:12],"action":"progressive","tokens":list(tokens),"changes":details,
        "full":bool(not opt.get("inconclusive") and int(opt.get("missing",0) or 0)==0),"missing":int(opt.get("missing",0) or 0),
        "title":" + ".join(c["label"]+((" "+c["exact_change"]) if c.get("exact_change") else "") for c in details) if details else "Przełóż nauczycieli bez zmiany reguł",
        "explanation":("Pełna obsada bez zmiany konfiguracji — tylko inne rozmieszczenie nauczycieli."
                       if not details else "Pełna obsada po wskazanych zmianach. Generator nadal szuka tańszych wariantów."),
        "coverage13":{k:opt["school13"][k] for k in ("required","filled","missing")},
        "coverageSchool":{k:opt["school"][k] for k in ("required","filled","missing")},
        "teacher_changes":tc,"impact":impact,"wait_assignments":impact["waiting_duties"],
        "human_cost":human,"score":score,"coverage_reduction":coverage_reduction,"comfort_change":bool(comfort),
        "wait_relax":any(_token_relaxes_rule_v537(c.get("token"),"avoid_wait") for c in details),
        "search_stage":max([int(c.get("search_stage",1)) for c in details] or [1]),
        "categories":sorted({c.get("category","") for c in details}),
        "result_13":opt["school13"]["assignments"],"result_school":opt["school"]["assignments"],
        **metrics,
        "_state":trial_state,"_enabled13":list(e13),"_enabledSchool":list(es)
    }

def _job_add_suggestion(job,sug):
    eligibility=_live_eligibility_v565(sug,job)
    sug["live_eligible"]=bool(eligibility["ok"])
    sug["live_rejection_reasons"]=list(eligibility["reasons"])
    with REPAIR_JOB_LOCK:
        seq=int(job.get("_suggestion_seq",0) or 0)+1
        job["_suggestion_seq"]=seq
        sug["seq"]=int(sug.get("seq") or seq)
    public={k:v for k,v in sug.items() if not k.startswith("_")}
    added=False
    with REPAIR_JOB_LOCK:
        private=job.setdefault("_private",{})
        private[sug["id"]]=sug
        arr=job.setdefault("suggestions",[])
        sig=tuple(sorted(sug.get("tokens",[])))
        if any(tuple(sorted(x.get("tokens",[])))==sig for x in arr):
            return False
        arr.append(public)
        arr.sort(key=lambda x:(_working_quality_key_v559(x,job),
                               x.get("teacher_changes",{}).get("positions_changed",9999),
                               x.get("score",10**12)))
        if len(arr)>12:
            dropped=arr[12:]
            del arr[12:]
            for x in dropped: private.pop(x.get("id"),None)
        added=True
    if added and public.get("live_eligible"):
        _persist_last_good_plan_v577(
            public.get("result_13") or [],public.get("result_school") or [],
            {"kind":"live_verified","source_id":"live:"+str(job.get("id") or "")+":"+str(public.get("id") or ""),
             "variant_id":public.get("id"),"seq":public.get("seq"),"job_id":job.get("id"),
             "found_at":datetime.now().isoformat(timespec="seconds")},
            load_state(),public)
    return added

def _accepted_compromises(job=None,state=None):
    if job is not None:
        vals=job.get("accepted_compromises",[])
        if vals:return set(str(x) for x in vals)
    if state is not None:
        return set(str(x) for x in ((state.get("repair_guidance",{}) or {}).get("accepted_compromises",[]) or []))
    return set()

def _candidate_guided_cost_v541(c,job):
    base=int(c.get("human_cost",0) or 0)
    accepted=_accepted_compromises(job)
    tok=str(c.get("token",""))
    for key in accepted:
        if _token_relaxes_rule_v537(tok,key):
            base=max(0,base//12)
            break
    # Cross-plan local learning only reorders candidates inside their search stage.
    # It can never move a late safety/comfort stage ahead of an earlier one.
    return max(0,base+_solver_knowledge_cost_adjustment(job,tok,base))

def _working_quality_key_v541(x,job):
    q=list(x.get("quality_key",[10**9]*5))
    while len(q)<5:q.append(10**9)
    a=_accepted_compromises(job)
    if "avoid_wait" in a:q[0]=0
    if "after_last_long" in a:q[1]=0
    if "before_first_long" in a:q[2]=0
    if "max_consecutive_duties" in a:q[3]=0
    return tuple(q)

def _working_quality_key_v559(x,job):
    a=_accepted_compromises(job)
    wait=0 if "avoid_wait" in a else int(x.get("wait_lessons_total",10**9) or 0)
    foreign13=int(x.get("home_group_foreign_13",10**9) or 0)
    wf_total=int(x.get("wf_assignments_total",x.get("home_group_foreign_13_wf",10**9)) or 0)
    foreign_school=int(x.get("home_group_foreign_school",10**9) or 0)
    fair_enabled=bool(x.get("fairness_enabled",False))
    fair_dev=int(round(float(x.get("fairness_normalized_deviation",0) or 0)*10000)) if fair_enabled else 0
    fair_ratio=int(round(float(x.get("fairness_max_ratio",0) or 0)*1000)) if fair_enabled else 0
    after=0 if "after_last_long" in a else int(x.get("after_last_long",10**9) or 0)
    before=0 if "before_first_long" in a else int(x.get("before_first_long",10**9) or 0)
    consec=0 if "max_consecutive_duties" in a else int(x.get("consecutive_pairs",10**9) or 0)
    relax=int(x.get("temporary_relaxations_count",10**9) or 0)
    return (wait,after,wf_total,before,consec,foreign13,foreign_school,fair_dev,fair_ratio,relax)

def _variant_quality_key_v540(sug):
    impact=sug.get("impact",{}) or {}
    tc=sug.get("teacher_changes",{}) or {}
    return (
        int(impact.get("offday_duties",10**6) or 0),
        int(impact.get("wait_lessons_total",10**6) or 0),
        int(impact.get("waiting_duties",10**6) or 0),
        1 if sug.get("comfort_change") else 0,
        int(sug.get("human_cost",10**9) or 0),
        int(tc.get("positions_changed",10**6) or 0),
        int(sug.get("score",10**12) or 0),
    )

def _lns_improve_suggestion_v540(base_state,sug,radius=1):
    """Large Neighborhood Search around one full solution.

    Freeze positions outside a small neighborhood as temporary admin locks,
    re-optimize only the problematic teachers and nearby break slots, then
    discard those temporary locks before returning the variant.
    """
    if not sug or not sug.get("result_13") or not sug.get("result_school"):
        return None
    trial=_copy.deepcopy(sug.get("_state") or base_state)
    original_locks=_copy.deepcopy(trial.get("locked_assignments",[]) or [])
    arr13=_copy.deepcopy(sug.get("result_13",[]))
    arrs=_copy.deepcopy(sug.get("result_school",[]))
    bad=set()
    for r in (sug.get("impact",{}) or {}).get("waiting_teachers",[]) or []:
        if r.get("teacher"):bad.add(r["teacher"])
    # If there is no waiting, improve the busiest/most changed teachers locally.
    if not bad:
        for r in (sug.get("teacher_changes",{}) or {}).get("teachers",[])[:8]:
            if r.get("teacher") and (r.get("added",0) or r.get("removed",0)):
                bad.add(r["teacher"])
    if not bad:
        cnt=Counter(a.get("teacher") for a in arr13+arrs if a.get("teacher"))
        bad={n for n,_ in cnt.most_common(6)}
    if not bad:return None

    byday=defaultdict(list)
    for br in SEED.get("breaks",[]):
        byday[str(br.get("abbr"))].append(str(br.get("label")))
    near=set()
    def add_near(scope,abbr,slot):
        seq=byday.get(str(abbr),[])
        try:i=seq.index(str(slot))
        except ValueError:
            near.add((scope,str(abbr),str(slot)));return
        for j in range(max(0,i-radius),min(len(seq),i+radius+1)):
            near.add((scope,str(abbr),seq[j]))
    for a in arr13:
        if a.get("teacher") in bad:add_near("1-3",a.get("abbr"),a.get("slot"))
    for a in arrs:
        if a.get("teacher") in bad:add_near("szkoła",a.get("abbr"),a.get("slot"))

    existing={(r.get("scope"),r.get("abbr"),r.get("slot"),str(r.get("location",""))) for r in original_locks}
    temp=[]
    for a in arr13:
        if not a.get("teacher"):continue
        if a.get("teacher") in bad or ("1-3",str(a.get("abbr")),str(a.get("slot"))) in near:continue
        row={"scope":"1-3","abbr":a.get("abbr"),"slot":a.get("slot"),
             "location":a.get("station",""),"teacher":a.get("teacher"),"_lns_temp":True}
        k=(row["scope"],row["abbr"],row["slot"],str(row["location"]))
        if k not in existing:temp.append(row);existing.add(k)
    for a in arrs:
        if not a.get("teacher"):continue
        if a.get("teacher") in bad or ("szkoła",str(a.get("abbr")),str(a.get("slot"))) in near:continue
        row={"scope":"szkoła","abbr":a.get("abbr"),"slot":a.get("slot"),
             "location":a.get("location",""),"teacher":a.get("teacher"),"_lns_temp":True}
        k=(row["scope"],row["abbr"],row["slot"],str(row["location"]))
        if k not in existing:temp.append(row);existing.add(k)
    trial["locked_assignments"]=original_locks+temp
    trial["solver_internal_workers"]=4
    trial["solver_coverage_seconds"]=10
    trial["solver_coverage_retry_seconds"]=30

    eval_fast={
        "missing":0,"inconclusive":False,"order":"lns",
        "coverage13":_copy.deepcopy(sug.get("coverage13",{})),
        "coverageSchool":_copy.deepcopy(sug.get("coverageSchool",{})),
        "result13":arr13,"resultSchool":arrs,
        "waits13":[],"waitsSchool":[]
    }
    # Existing wait rows are only a fallback; the real optimization below recomputes them.
    for w in (sug.get("impact",{}) or {}).get("waiting_teachers",[]) or []:
        for d in w.get("duties",[]) or []:
            rec={"teacher":w.get("teacher"),**d}
            (eval_fast["waits13"] if d.get("scope")=="1-3" else eval_fast["waitsSchool"]).append(rec)
    try:
        out=_repair_variant_v2(base_state,trial,
            list(sug.get("_enabled13",[])),list(sug.get("_enabledSchool",[])),
            list(sug.get("tokens",[])),list(sug.get("changes",[])),eval_fast)
    except Exception:
        return None
    # Temporary LNS locks are never user configuration.
    if isinstance(out.get("_state"),dict):
        out["_state"]["locked_assignments"]=original_locks
    out["lns"]=True;out["lns_radius"]=radius;out["lns_neighborhood_teachers"]=len(bad)
    out["title"]="LNS • "+str(out.get("title") or "lokalna poprawa pełnego planu")
    out["explanation"]="Lokalna poprawa pełnego planu: większość przydziałów pozostała zamrożona, a solver przebudował tylko problematyczne osoby i sąsiednie sloty."
    return out

def _candidate_key_v520(c):
    tok=str(c.get("token",""))
    if tok.startswith("gval:"):
        parts=tok.split(":",2); return "gval:"+parts[1]
    if tok.startswith("gsoft:"): return tok
    if tok.startswith("indval:"):
        parts=tok.split(":",2); return "indval:"+parts[1]
    if tok.startswith("add13group:"): return tok
    return tok

def _combo_compatible_v520(combo):
    keys=set()
    toks=[str(c.get("token","")) for c in combo]
    for c in combo:
        k=_candidate_key_v520(c)
        if k in keys:return False
        keys.add(k)
    # Group expansions supersede individual additions from that same group.
    if "add13group:school" in toks and any(t.startswith("add13:") for t in toks):
        return False
    if "add13group:wf" in toks and any(t.startswith("add13:") for t in toks):
        return False
    add13={t[6:] for t in toks if t.startswith("add13:")}
    addS={t[10:] for t in toks if t.startswith("addschool:")}
    move13={t[7:] for t in toks if t.startswith("move13:")}
    moveS={t[11:] for t in toks if t.startswith("moveschool:")}
    if add13 & move13:return False
    if addS & moveS:return False
    if move13 & moveS:return False
    return True

def _iter_stage_combos_v520(candidates,stage,max_size=3):
    """Systematic breadth-first combinations. No top-N beam.
    Stage N may use candidates from stages <=N, but must contain at least one from N."""
    pool=[c for c in candidates if int(c.get("search_stage",9))<=stage]
    current=[c for c in pool if int(c.get("search_stage",9))==stage]
    if not current:return
    current_tokens={c["token"] for c in current}
    import itertools
    for size in range(1,max_size+1):
        for combo in itertools.combinations(pool,size):
            if not any(c.get("token") in current_tokens for c in combo):continue
            if not _combo_compatible_v520(combo):continue
            yield {"tokens":[c["token"] for c in combo],"changes":list(combo)}

def _rough_stage_space_v520(candidates,stage,max_size=3):
    import math
    n=sum(1 for c in candidates if int(c.get("search_stage",9))<=stage)
    cur=sum(1 for c in candidates if int(c.get("search_stage",9))==stage)
    prev=n-cur
    # upper bound, before compatibility pruning
    total=0
    for k in range(1,max_size+1):
        if n>=k:
            total+=math.comb(n,k)-(math.comb(prev,k) if prev>=k else 0)
    return total

def _tier_ceiling_item_v520(candidates,stage):
    """Most permissive configuration reachable without entering a worse stage.
    If this still has missing positions, every subset of this stage is dominated
    and cannot produce full coverage."""
    pool=[c for c in candidates if int(c.get("search_stage",9))<=stage]
    best_numeric={}
    group_school=any(c.get("token")=="add13group:school" for c in pool)
    group_wf=any(c.get("token")=="add13group:wf" for c in pool)
    chosen=[]
    for c in pool:
        tok=str(c.get("token",""))
        if tok.startswith(("gval:","indval:")):
            key=_candidate_key_v520(c)
            try: val=int(tok.rsplit(":",1)[1])
            except Exception: val=0
            old=best_numeric.get(key)
            if old is None or val>old[0]:best_numeric[key]=(val,c)
            continue
        if tok.startswith("add13:"):
            n=tok[6:];g=GROUP.get(n)
            if (g=="school" and group_school) or (g=="wf" and group_wf):continue
        chosen.append(c)
    chosen += [v[1] for v in best_numeric.values()]
    # deterministic order makes diagnostics reproducible
    chosen.sort(key=lambda c:(int(c.get("search_stage",9)),int(c.get("human_cost",0)),c.get("token","")))
    seen=set();uniq=[]
    for c in chosen:
        if c.get("token") in seen:continue
        seen.add(c.get("token"));uniq.append(c)
    return {"tokens":[c["token"] for c in uniq],"changes":uniq}

def _broad_probe_item_v539(state,candidates,stage,include_global_wait=False):
    """Comfort-bounded monotonic probe used before fine combinatorics.

    It only enlarges the feasible set: pool additions, moderate numeric increases,
    teacher/global softening. It never lowers staffing, moves teachers between pools,
    unlocks admin decisions or touches waiting before stage 6.
    """
    pool=[c for c in candidates if int(c.get("search_stage",9))<=int(stage)]
    group_school=any(c.get("token")=="add13group:school" for c in pool)
    group_wf=any(c.get("token")=="add13group:wf" for c in pool)
    numeric={}
    chosen=[]
    inc={"max_day_13":1,"max_day_school":1,"max_week":2,
         "max_long_day":1,"max_long_week":2,"max_consecutive_duties":1}
    for c in pool:
        tok=str(c.get("token",""))
        if not tok:continue
        if tok.startswith(("m13:","ms:","move13:","moveschool:","unlock:","unblock:")):
            continue
        if _token_relaxes_rule_v537(tok,"avoid_wait"):
            if int(stage)<6:continue
            # Prefer precise teacher exceptions. Global waiting is a fallback only.
            if tok=="gsoft:avoid_wait" and not include_global_wait:continue
        if tok.startswith("add13:"):
            n=tok[6:];g=GROUP.get(n)
            if (g=="school" and group_school) or (g=="wf" and group_wf):continue
        if tok.startswith("gval:"):
            _,key,val=tok.split(":",2)
            try:val=int(val)
            except Exception:continue
            row=_global_row(state,key)
            try:cur=int(row.get("value") or 0)
            except Exception:cur=0
            cap=cur+inc.get(key,max(1,val-cur))
            if val>cap:continue
            old=numeric.get("g:"+key)
            if old is None or val>old[0]:numeric["g:"+key]=(val,c)
            continue
        if tok.startswith("indval:"):
            _,rid,val=tok.split(":",2)
            try:val=int(val)
            except Exception:continue
            row=next((r for r in state.get("individual_constraints",[]) if str(r.get("id"))==rid),{})
            try:cur=int(row.get("value") or 0)
            except Exception:cur=0
            step=1 if str(row.get("rule") or "")=="max_day" else 2
            if val>cur+step:continue
            old=numeric.get("i:"+rid)
            if old is None or val>old[0]:numeric["i:"+rid]=(val,c)
            continue
        chosen.append(c)
    chosen += [v[1] for v in numeric.values()]
    chosen.sort(key=lambda c:(int(c.get("search_stage",9)),int(c.get("relax_level",0)),
                              int(c.get("human_cost",0)),str(c.get("token",""))))
    seen=set();uniq=[]
    for c in chosen:
        tok=str(c.get("token",""))
        if tok in seen:continue
        seen.add(tok);uniq.append(c)
    return {"tokens":[c["token"] for c in uniq],"changes":uniq,
            "probe_stage":int(stage),"probe_kind":"comfort-bounded"}

def _middle_anchor_items_v527(candidates):
    """Large safe jumps into the middle of the search space, before fine search."""
    usable=[c for c in candidates if int(c.get("search_stage",9))<4]
    bykey=defaultdict(list)
    for c in usable:
        tok=str(c.get("token",""))
        if tok.startswith("gval:"):
            bykey[_candidate_key_v520(c)].append(c)
    def qpick(key,q):
        xs=sorted(bykey.get("gval:"+key,[]),key=lambda c:int(str(c["token"]).rsplit(":",1)[1]))
        if not xs:return None
        return xs[min(len(xs)-1,max(0,round((len(xs)-1)*q)))]
    def uniq(rows):
        out=[];seen=set()
        for c in rows:
            if not c or c.get("token") in seen:continue
            seen.add(c.get("token"));out.append(c)
        return out
    add13=[c for c in usable if str(c.get("token","")).startswith("add13:")][:8]
    addschool=[c for c in usable if str(c.get("token","")).startswith("addschool:")][:8]
    gschool=next((c for c in usable if c.get("token")=="add13group:school"),None)
    gwf=next((c for c in usable if c.get("token")=="add13group:wf"),None)
    trel=[c for c in usable if str(c.get("token","")).startswith("trelax:")][:8]
    gsoft=[c for c in usable if str(c.get("token","")).startswith("gsoft:") and c.get("token")!="gsoft:avoid_wait"][:4]
    caps_mid=[qpick(k,.55) for k in ("max_day_13","max_day_school","max_week")]
    caps_hi=[qpick(k,.82) for k in ("max_day_13","max_day_school","max_week")]
    comfort_mid=[qpick(k,.55) for k in ("max_long_day","max_long_week")]
    comfort_hi=[qpick(k,.82) for k in ("max_long_day","max_long_week")]
    specs=[
        ("środek: pojemność + wybrane pule",caps_mid+add13[:5]+addschool[:3]),
        ("duży skok: szerokie pule + wysokie limity",caps_hi+[gschool,gwf]+addschool[:6]),
        ("środek: pojemność + komfort indywidualny",caps_hi+comfort_mid+[gschool]+trel[:4]),
        ("duży skok: pojemność + część komfortu",caps_hi+comfort_hi+[gschool,gwf]+trel[:6]+gsoft[:2]),
    ]
    out=[]
    for label,rows in specs:
        rows=uniq(rows)
        # Do not reduce required staffing and do not touch waiting in middle anchors.
        rows=[c for c in rows if not str(c.get("token","")).startswith(("m13:","ms:")) and "avoid_wait" not in str(c.get("token",""))]
        if rows:out.append({"tokens":[c["token"] for c in rows],"changes":rows,"anchor_label":label})
    return out

def _anchor_neighbors_v527(item,candidates,limit=28,allow_existing_wait=False):
    """Binary-style refinement around a full anchor.

    For numeric relaxations test the midpoint toward the strict baseline first,
    then an upper midpoint and finally one-step-back as a safety net.
    Non-numeric relaxations are tested by removing them completely.
    """
    toks=list(item.get("tokens",[])); changes={c.get("token"):c for c in item.get("changes",[])}
    bykey=defaultdict(list)
    lookup={str(c.get("token","")):c for c in candidates}
    for c in candidates:
        tok=str(c.get("token",""))
        if tok.startswith("gval:"):bykey[_candidate_key_v520(c)].append(c)
    out=[];seen=set()
    def emit(nt):
        nt=list(dict.fromkeys(nt))
        if (not allow_existing_wait) and any(_token_relaxes_rule_v537(t,"avoid_wait") for t in nt):return
        sig=tuple(sorted(nt))
        if sig in seen:return
        seen.add(sig)
        rows=[changes.get(t) or lookup.get(t,{"token":t,"label":t,"human_cost":999}) for t in nt]
        out.append({"tokens":nt,"changes":rows})
    for i,t in enumerate(toks):
        if t.startswith("gval:"):
            key=_candidate_key_v520({"token":t})
            cur=int(t.rsplit(":",1)[1])
            vals=sorted({int(str(c["token"]).rsplit(":",1)[1]) for c in bykey.get(key,[])})
            lower=[v for v in vals if v<cur]
            if lower:
                strict=min(vals)-1
                mid=max(strict,(strict+cur)//2)
                upper=max(mid,(mid+cur)//2)
                targets=[]
                for v in (mid,upper,cur-1):
                    if v>strict and v<cur and v in vals and v not in targets:targets.append(v)
                for v in targets:
                    nt=toks[:];nt[i]=f"{key}:{v}";emit(nt)
            # Removing the token tests the strict baseline for this dimension.
            emit(toks[:i]+toks[i+1:])
        else:
            emit(toks[:i]+toks[i+1:])
    out.sort(key=lambda x:(sum(int(c.get("human_cost",0) or 0) for c in x["changes"]),len(x["tokens"])))
    return out[:limit]


WORKING_TIGHTEN_ORDER=[
    ("avoid_wait","dodatkowe oczekiwanie na dyżur"),
    ("after_last_long","przerwa >10 min po ostatniej lekcji"),
    ("before_first_long","przerwa >10 min przed pierwszą lekcją"),
    ("max_consecutive_duties","kolejne dyżury"),
    ("max_long_day","limit długich przerw dziennie"),
    ("max_long_week","limit długich przerw tygodniowo"),
    ("max_week","limit dyżurów tygodniowo"),
    ("max_day_13","limit dyżurów dziennie 1–3"),
    ("max_day_school","limit dyżurów dziennie całej szkoły"),
]

def _edge_rule_exception_proof_v555(state,e13,es,key):
    """Cheap proof/candidate summary for one edge-of-day rule.

    This is a necessary-condition calculation, not a full solver result:
    it reports only deficits that disappear when this one rule changes
    from HARD to SOFT while every other current hard rule is kept.
    """
    hard=ensure_state_schema(_copy.deepcopy(state))
    row=_global_row(hard,key)
    if not row or not row.get("enabled",True):
        return {"required":False,"minimum_teachers":0,"minimum_exception_assignments":0,
                "candidate_teachers":[],"affected_slots":[],"proof":"rule_inactive"}
    row["kind"]="hard"; row["priority"]=5
    soft=_copy.deepcopy(hard)
    srow=_global_row(soft,key)
    srow["kind"]="soft"; srow["priority"]=5

    excluded=set(hard.get("excluded_teachers",[]))
    all_allowed=[n for n in ALL if n not in excluded]
    p13=[n for n in dict.fromkeys(e13 or hard.get("enabled_teachers_13",[])) if n in ALL and n not in excluded]
    ps=[n for n in _school_pool(es if es is not None else hard.get("enabled_teachers_school",[])) if n not in excluded]
    pos13=_diag_positions_13(hard)[0]
    posS=_school_positions(hard)[0]
    affected=[]; candidate_counts=Counter(); total_cases=0; min_teachers=0

    def analyze(scope,positions,enabled,freeze):
        nonlocal total_cases,min_teachers
        groups=defaultdict(list)
        for pos in positions:
            groups[(pos.get("abbr"),pos.get("slot"))].append(pos)
        pool=enabled if freeze else all_allowed
        for (ab,slot),grp in groups.items():
            hard_edges=[_preflight_teacher_allowed_v524(hard,scope,pos,pool) for pos in grp]
            soft_edges=[_preflight_teacher_allowed_v524(soft,scope,pos,pool) for pos in grp]
            hp=_max_bipartite_match_v524(hard_edges)
            sp=_max_bipartite_match_v524(soft_edges)
            need=max(0,min(len(grp),sp)-hp)
            if not need:
                continue
            candidates=set()
            for he,se in zip(hard_edges,soft_edges):
                candidates.update(set(se)-set(he))
            total_cases+=need
            min_teachers=max(min_teachers,need)
            for n in candidates:
                candidate_counts[n]+=1
            br=next((p.get("break") for p in grp if p.get("break")),None) or {}
            affected.append({
                "scope":"1-3" if scope=="1-3" else "school",
                "abbr":ab,"slot":slot,"day":br.get("day",""),
                "required_positions":len(grp),
                "possible_with_rule_hard":hp,
                "possible_with_rule_soft":sp,
                "minimum_exceptions":need,
                "candidates":sorted(candidates,key=_teacher_sort_key),
            })

    analyze("1-3",pos13,p13,bool(hard.get("freeze_pool_13",False)))
    analyze("school",posS,ps,bool(hard.get("freeze_pool_school",False)))
    cand=[{"teacher":n,"affected_slots":int(v)}
          for n,v in sorted(candidate_counts.items(),key=lambda kv:(-kv[1],_teacher_sort_key(kv[0])))]
    return {
        "required":bool(affected),
        "minimum_teachers":int(min_teachers),
        "minimum_exception_assignments":int(total_cases),
        "candidate_teachers":cand,
        "affected_slots":affected,
        "proof":"per_slot_matching",
    }

def _fairness_profile_v559(state,assignments,eligible_names=None):
    row=_global_row(state,"lesson_load_fairness")
    enabled=bool(row and row.get("enabled",False))
    base={"fairness_enabled":enabled,"fairness_total_deviation":0.0,"fairness_normalized_deviation":0.0,
          "fairness_max_ratio":0.0,"fairness_max_excess":0.0,"fairness_top10_share":0.0,
          "fairness_zero_target_teachers":0,"fairness_grossly_unbalanced":False,"fairness_rejection_reasons":[]}
    if not enabled:return base
    excluded=set(state.get("excluded_teachers",[]) or [])|set(state.get("absent_teachers",[]) or [])
    eligible=set(eligible_names or ALL)-excluded
    counts=Counter(a.get("teacher") for a in (assignments or []) if a.get("teacher"))
    eligible.update(n for n in counts if n in ALL and n not in excluded)
    if not eligible:return base
    factors={}
    for n in eligible:
        t=TBY.get(n,{})
        lessons=sum(len(periods or {}) for periods in (t.get("lessons",{}) or {}).values())
        try:manual=max(0.1,float((state.get("teacher_workload",{}) or {}).get(n,1.0)))
        except Exception:manual=1.0
        factors[n]=float(lessons)*manual
    sf=sum(factors.values())
    if sf<=0:
        factors={n:1.0 for n in eligible};sf=float(len(eligible))
    total=sum(counts.values())
    if total<=0:return base
    targets={n:total*factors[n]/sf for n in eligible}
    dev=sum(abs(counts.get(n,0)-targets[n]) for n in eligible)
    max_ratio=0.0;max_excess=0.0
    for n in eligible:
        target=targets[n];actual=counts.get(n,0)
        excess=max(0.0,actual-target)
        ratio=(actual/max(2.0,target)) if actual else 0.0
        max_ratio=max(max_ratio,ratio);max_excess=max(max_excess,excess)
    zero_target=sum(1 for n in eligible if targets[n]>=3.0 and counts.get(n,0)==0)
    top10=sum(sorted(counts.values(),reverse=True)[:10])/max(1,total)
    norm=dev/max(1,total)
    reasons=[]
    if norm>0.75:reasons.append(f"łączna nierównowaga {norm:.2f} > 0.75")
    if max_ratio>3.0 and max_excess>=8.0:reasons.append(f"pojedyncze przeciążenie {max_ratio:.2f}× celu, +{max_excess:.1f} dyż.")
    if top10>0.55:reasons.append(f"10 najbardziej obciążonych osób ma {top10:.0%} wszystkich dyżurów")
    return {**base,"fairness_total_deviation":round(dev,2),"fairness_normalized_deviation":round(norm,4),
            "fairness_max_ratio":round(max_ratio,3),"fairness_max_excess":round(max_excess,2),
            "fairness_top10_share":round(top10,4),"fairness_zero_target_teachers":int(zero_target),
            "fairness_grossly_unbalanced":bool(reasons),"fairness_rejection_reasons":reasons}

def _human_guardrail_profile_v560(state,assignments):
    cs=cdict(state)
    bm=break_map()
    duty_slots=defaultdict(set)
    daily=Counter();weekly=Counter();long_day=Counter();long_week=Counter()
    for a in assignments or []:
        n=a.get("teacher");ab=a.get("abbr");sl=a.get("slot")
        if not n or not ab or not sl: continue
        key=(n,ab,sl)
        if sl in duty_slots[(n,ab)]: continue
        duty_slots[(n,ab)].add(sl)
        daily[(n,ab)]+=1; weekly[n]+=1
        br=bm.get((ab,sl),{})
        if int(br.get("minutes",0) or 0)>=LONG_BREAK_MINUTES:
            long_day[(n,ab)]+=1;long_week[n]+=1
    order=defaultdict(list)
    for br in SEED.get("breaks",[]):
        order[str(br.get("abbr"))].append(str(br.get("label")))
    longest=0;longest_teacher="";longest_day=""
    for (n,ab),have in duty_slots.items():
        run=best=0
        for sl in order.get(str(ab),[]):
            if sl in have: run+=1;best=max(best,run)
            else: run=0
        if best>longest: longest=best;longest_teacher=n;longest_day=ab
    violations=[]
    def hard_limit(key):
        r=cs.get(key,{})
        if not r.get("enabled") or normalize_kind(r.get("kind"))!="hard": return None
        try:return max(0,int(r.get("value") or 0))
        except Exception:return None
    consec=hard_limit("max_consecutive_duties")
    if consec is not None and longest>consec:
        violations.append(f"{_display_teacher(longest_teacher)}: {longest} kolejnych dyżurów w {longest_day} (limit {consec})")
    week_cap=hard_limit("max_week")
    if week_cap is not None:
        bad=[(v,n) for n,v in weekly.items() if v>week_cap]
        if bad:
            v,n=max(bad);violations.append(f"{_display_teacher(n)}: {v} dyżurów w tygodniu (limit {week_cap})")
    day_caps=[x for x in (hard_limit("max_day_13"),hard_limit("max_day_school")) if x is not None]
    day_cap=min(day_caps) if day_caps else None
    if day_cap is not None:
        bad=[(v,n,ab) for (n,ab),v in daily.items() if v>day_cap]
        if bad:
            v,n,ab=max(bad);violations.append(f"{_display_teacher(n)}: {v} dyżurów w {ab} (limit dzienny {day_cap})")
    long_day_cap=hard_limit("max_long_day")
    if long_day_cap is not None:
        bad=[(v,n,ab) for (n,ab),v in long_day.items() if v>long_day_cap]
        if bad:
            v,n,ab=max(bad);violations.append(f"{_display_teacher(n)}: {v} długich dyżurów w {ab} (limit {long_day_cap})")
    long_week_cap=hard_limit("max_long_week")
    if long_week_cap is not None:
        bad=[(v,n) for n,v in long_week.items() if v>long_week_cap]
        if bad:
            v,n=max(bad);violations.append(f"{_display_teacher(n)}: {v} długich dyżurów w tygodniu (limit {long_week_cap})")
    return {
        "human_guardrail_ok":not violations,
        "human_guardrail_violations":violations,
        "human_max_weekly_duties":max(weekly.values(),default=0),
        "human_max_daily_duties":max(daily.values(),default=0),
        "human_longest_consecutive_duties":longest,
        "human_max_long_week":max(long_week.values(),default=0),
        "human_max_long_day":max(long_day.values(),default=0),
    }

def _draft_metrics_v527(ev,relax_rows,state=None):
    waits=list(ev["school13"].get("waits",[]))+list(ev["school"].get("waits",[]))
    wait_lessons=sum(max(0,int(w.get("wait",0) or 0)) for w in waits)
    wait_counts=Counter();wait_periods=Counter()
    for w in waits:
        n=w.get("teacher")
        if n:
            wait_counts[n]+=1;wait_periods[n]+=max(0,int(w.get("wait",0) or 0))
    bm=break_map()
    assignments13=list(ev["school13"].get("assignments",[]))
    assignments_school=list(ev["school"].get("assignments",[]))
    assignments=assignments13+assignments_school
    foreign13=sum(1 for a in assignments13 if a.get("teacher") and GROUP.get(a.get("teacher"))!="1-3")
    foreign13_general=sum(1 for a in assignments13 if a.get("teacher") and GROUP.get(a.get("teacher"))=="school")
    foreign13_wf=sum(1 for a in assignments13 if a.get("teacher") and GROUP.get(a.get("teacher"))=="wf")
    wf_school_gym=sum(1 for a in assignments_school if a.get("teacher") and GROUP.get(a.get("teacher"))=="wf" and _is_gym_location(a.get("location"),state))
    wf_school=sum(1 for a in assignments_school if a.get("teacher") and GROUP.get(a.get("teacher"))=="wf" and not _is_gym_location(a.get("location"),state))
    wf_total=foreign13_wf+wf_school
    foreign_school=sum(1 for a in assignments_school if a.get("teacher") and GROUP.get(a.get("teacher"))!="school")
    after_long=before_long=0
    after_counts=Counter();before_counts=Counter();consecutive_counts=Counter()
    after_slots=defaultdict(lambda:{"cases":0,"teachers":set()})
    before_slots=defaultdict(lambda:{"cases":0,"teachers":set()})
    slots_by=defaultdict(set);order_by=defaultdict(list)
    for br in SEED.get("breaks",[]):
        order_by[br.get("abbr")].append(br.get("label"))
    for a in assignments:
        n=a.get("teacher");ab=a.get("abbr");sl=a.get("slot")
        if not n or not ab or not sl:continue
        slots_by[(n,ab)].add(sl)
        br=bm.get((ab,sl))
        if not br or int(br.get("minutes",0) or 0)<=SHORT_BREAK_MAX_MINUTES:continue
        ps=lesson_periods(n,ab)
        if not ps:continue
        prev=br.get("prev");nxt=br.get("next")
        if prev in ps and int(prev)==max(ps):
            after_long+=1;after_counts[n]+=1
            after_slots[(ab,sl)]["cases"]+=1;after_slots[(ab,sl)]["teachers"].add(n)
        if nxt in ps and int(nxt)==min(ps):
            before_long+=1;before_counts[n]+=1
            before_slots[(ab,sl)]["cases"]+=1;before_slots[(ab,sl)]["teachers"].add(n)
    consecutive_pairs=0
    for (n,ab),have in slots_by.items():
        seq=order_by.get(ab,[])
        pairs=sum(1 for x,y in zip(seq,seq[1:]) if x in have and y in have)
        consecutive_pairs+=pairs
        if pairs:consecutive_counts[n]+=pairs
    relax_count=len(relax_rows)
    quality_key=[wait_lessons,after_long,before_long,consecutive_pairs,relax_count]
    def rows(cnt):
        return [{"teacher":n,"cases":int(v)} for n,v in sorted(cnt.items(),key=lambda kv:(-kv[1],_teacher_sort_key(kv[0])))]
    def slot_rows(src):
        out=[]
        for (ab,sl),v in sorted(src.items(),key=lambda kv:(kv[0][0],kv[0][1])):
            br=bm.get((ab,sl),{})
            out.append({"abbr":ab,"slot":sl,"day":br.get("day",""),"cases":int(v["cases"]),
                        "teachers":sorted(v["teachers"],key=_teacher_sort_key)})
        return out
    return {
        "waiting_duties":len(waits),"wait_lessons_total":wait_lessons,
        "waiting_teachers_count":len(wait_counts),"waiting_teachers":rows(wait_counts),
        "waiting_max_cases_per_teacher":max(wait_counts.values(),default=0),
        "waiting_max_periods_per_teacher":max(wait_periods.values(),default=0),
        "after_last_long":after_long,"after_last_long_teachers_count":len(after_counts),
        "after_last_long_teachers":rows(after_counts),"after_last_long_max_per_teacher":max(after_counts.values(),default=0),
        "after_last_long_unique_breaks":len(after_slots),"after_last_long_slots":slot_rows(after_slots),
        "before_first_long":before_long,"before_first_long_teachers_count":len(before_counts),
        "before_first_long_teachers":rows(before_counts),"before_first_long_max_per_teacher":max(before_counts.values(),default=0),
        "before_first_long_unique_breaks":len(before_slots),"before_first_long_slots":slot_rows(before_slots),
        "consecutive_pairs":consecutive_pairs,"consecutive_teachers_count":len(consecutive_counts),
        "consecutive_teachers":rows(consecutive_counts),"consecutive_max_pairs_per_teacher":max(consecutive_counts.values(),default=0),
        "home_group_foreign_13":foreign13,"home_group_foreign_school":foreign_school,
        "home_group_foreign_13_general":foreign13_general,"home_group_foreign_13_wf":foreign13_wf,
        "wf_assignments_13":foreign13_wf,"wf_assignments_school":wf_school,"wf_assignments_school_gym":wf_school_gym,
        "wf_assignments_total":wf_total,
        "home_group_foreign_total":foreign13+foreign_school,
        "home_group_foreign_13_share":round(foreign13/max(1,len(assignments13)),4),
        "home_group_foreign_school_share":round(foreign_school/max(1,len(assignments_school)),4),
        "temporary_relaxations_count":relax_count,"quality_key":quality_key
    }

def _quick_draft_v527(state,e13,es,hardened_keys=None,seed_offset=0,optimize_seconds=4):
    """Reverse-search draft: full coverage first, then progressively restore comfort."""
    started=_time.perf_counter()
    base=ensure_state_schema(_copy.deepcopy(state))
    excluded=set(base.get("excluded_teachers",[]))|set(base.get("absent_teachers",[]))
    hardened=set(hardened_keys or [])
    # v5.60: quick/live drafts are not allowed to buy completeness by violating
    # basic human-capacity limits. Broad jumps may relax comfort, never these limits.
    hardened.update(HUMAN_REALISM_HARDENED_V560)
    # v5.62: home-group priority is structural and never relaxed in broad drafts.
    # Outsiders remain legal fallback because the rule stays soft; CP-SAT decides
    # the minimum number needed, then prefers general-school teachers before WF.
    # v5.37: dodatkowe oczekiwanie jest twarde także w szybkich szkicach.
    # Waiting may be relaxed only in stage 6 of the main generator.
    hardened.add("avoid_wait")
    relax_rows=[];relax_tokens=[]
    for c in _repair_candidates(base):
        tok=str(c.get("token") or "")
        if not tok or tok=="g:offday_duty": continue
        if any(_token_relaxes_rule_v537(tok,key) for key in hardened): continue
        relax_tokens.append(tok)
        relax_rows.append({"token":tok,"label":str(c.get("label") or tok)})
    trial=_relax(base,relax_tokens)
    try: base_seed=int(base.get("solver_seed",20260918) or 20260918)
    except Exception: base_seed=20260918
    trial["solver_seed"]=base_seed+int(seed_offset or 0)*101
    trial["solver_internal_workers"]=8
    # v5.63 live-draft budget: keep the lexicographic order, but do not give each
    # preview phase the production-sized retry window. Final/deep solves keep their
    # normal budgets because these overrides exist only in the temporary trial state.
    trial["solver_coverage_seconds"]=3
    trial["solver_coverage_retry_seconds"]=8
    trial["solver_edge_lex_seconds"]=4
    trial["solver_edge_lex_retry_seconds"]=15
    trial["solver_home_group_seconds"]=3
    trial["solver_wf_fallback_seconds"]=2
    trial["solver_working_optimize"]=True
    trial["solver_working_optimize_seconds"]=max(1,min(3,int(optimize_seconds or 3)))
    # Strict reverse-search hierarchy, only for working drafts.
    trial["solver_weight_overrides"]={
        "avoid_wait":100_000_000_000_000,
        "after_last_long":1_000_000_000_000,
        "before_first_long":10_000_000_000,
        "max_consecutive_duties":100_000_000,
        "max_long_day":10_000_000,
        "max_long_week":1_000_000,
        "max_week":100_000,
        "max_day_13":10_000,
        "max_day_school":10_000,
    }
    raw13=[n for n in dict.fromkeys(e13 or []) if n in ALL and n not in excluded]
    raw_school=[n for n in dict.fromkeys(es or []) if n in ALL and n not in excluded]
    all_legal=[n for n in ALL if n not in excluded]
    base13=raw13 or all_legal
    base_school=raw_school or all_legal
    q13=list(all_legal)
    qschool=list(all_legal)
    school_extra=list(all_legal)
    school_all=list(all_legal)
    attempts=[]
    def run_attempt(label,p13,ps,order="13-first"):
        t=_time.perf_counter();ev=_joint_order_v2(trial,p13,ps,order,False)
        attempts.append((ev,label,list(p13),list(ps),_time.perf_counter()-t))
        return ev
    # v5.78: quick drafts use the same canonical model as production search.
    # There are no candidate pools. Every active teacher is visible from the start;
    # exact-place preferences, WF-only places and lexicographic objectives decide use.
    run_attempt("matrix model - 13 first",q13,qschool,"13-first")
    run_attempt("matrix model - school first",q13,qschool,"school-first")
    def attempt_quality(z):
        ev0=z[0]
        m=_draft_metrics_v527(ev0,relax_rows,base)
        return (bool(ev0.get("inconclusive")),int(ev0.get("missing",10**6)),
                int(m.get("wait_lessons_total",10**6) or 0),
                int(m.get("after_last_long",10**6) or 0),
                int(m.get("wf_assignments_total",10**6) or 0),
                int(m.get("before_first_long",10**6) or 0),
                int(m.get("consecutive_pairs",10**6) or 0),
                int(m.get("home_group_foreign_13",10**6) or 0),
                int(m.get("home_group_foreign_school",10**6) or 0),
                z[4])
    ev,label,p13,ps,solve_s=min(attempts,key=attempt_quality)
    full=bool(not ev.get("inconclusive") and int(ev.get("missing",10**6))==0)
    metrics=_draft_metrics_v527(ev,relax_rows,base)
    _all_assignments=list(ev["school13"].get("assignments",[]))+list(ev["school"].get("assignments",[]))
    metrics.update(_fairness_profile_v559(base,_all_assignments,set(p13)|set(ps)))
    metrics.update(_human_guardrail_profile_v560(base,_all_assignments))
    # v5.55: distinguish what the current draft happens to do from what the
    # timetable/staffing proof says is genuinely unavoidable.
    metrics["after_last_long_proof"]=_edge_rule_exception_proof_v555(base,e13,es,"after_last_long")
    metrics["before_first_long_proof"]=_edge_rule_exception_proof_v555(base,e13,es,"before_first_long")
    # v5.65: exact live eligibility comes from the real CP-SAT lexicographic phases,
    # never from the cheap per-slot lower-bound helper above.
    d13=(ev.get("school13",{}).get("diagnostics",{}) or {})
    ds=(ev.get("school",{}).get("diagnostics",{}) or {})
    _bm=break_map()
    def _scope_edge_count(rows,which):
        total=0
        for a in rows or []:
            n=a.get("teacher"); ab=a.get("abbr"); sl=a.get("slot")
            if not n or not ab or not sl: continue
            br=_bm.get((ab,sl))
            if not br or int(br.get("minutes",0) or 0)<=SHORT_BREAK_MAX_MINUTES: continue
            ps=lesson_periods(n,ab)
            if not ps: continue
            if which=="after":
                prev=br.get("prev")
                if prev in ps and int(prev)==max(ps): total+=1
            else:
                nxt=br.get("next")
                if nxt in ps and int(nxt)==min(ps): total+=1
        return total
    _after_scope=[_scope_edge_count(ev["school13"].get("assignments",[]),"after"),
                  _scope_edge_count(ev["school"].get("assignments",[]),"after")]
    _before_scope=[_scope_edge_count(ev["school13"].get("assignments",[]),"before"),
                   _scope_edge_count(ev["school"].get("assignments",[]),"before")]
    def _edge_proven(scope_counts,key):
        status_key=key+"_lex_status"
        diags=(d13,ds)
        return all((count==0 or diags[i].get(status_key)=="OPTIMAL") for i,count in enumerate(scope_counts))
    metrics["after_last_long_scope_counts"]=_after_scope
    metrics["before_first_long_scope_counts"]=_before_scope
    metrics["after_last_long_lex_proven"]=_edge_proven(_after_scope,"after_last_long")
    metrics["before_first_long_lex_proven"]=_edge_proven(_before_scope,"before_first_long")
    metrics["after_last_long_lex_statuses"]=[d13.get("after_last_long_lex_status"),ds.get("after_last_long_lex_status")]
    metrics["before_first_long_lex_statuses"]=[d13.get("before_first_long_lex_status"),ds.get("before_first_long_lex_status")]
    _wf_scope=[int(metrics.get("wf_assignments_13",0) or 0),int(metrics.get("wf_assignments_school",0) or 0)]
    _wf_diags=(d13,ds)
    metrics["wf_fallback_scope_counts"]=_wf_scope
    metrics["wf_fallback_lex_statuses"]=[d13.get("wf_fallback_status"),ds.get("wf_fallback_status")]
    metrics["wf_fallback_lex_proven"]=all((count==0 or _wf_diags[i].get("wf_fallback_status")=="OPTIMAL")
                                            for i,count in enumerate(_wf_scope))
    hardened_labels=[lab for key,lab in WORKING_TIGHTEN_ORDER if key in hardened]
    return {
        "status":"full" if full else ("inconclusive" if ev.get("inconclusive") else "partial"),
        "full":full,"nonoptimal":True,
        "coverage13":{k:ev["school13"][k] for k in ("required","filled","missing")},
        "coverageSchool":{k:ev["school"][k] for k in ("required","filled","missing")},
        "missing":int(ev.get("missing",10**6)),"elapsed_s":round(_time.perf_counter()-started,2),
        "solve_s":round(solve_s,2),"order":ev.get("order"),"strategy":label,
        "temporary_relaxations":relax_rows,"hardened_keys":list(hardened),
        "hardened_labels":hardened_labels,
        "pool13_before":len(base13),"pool13_draft":len(p13),
        "pool_school_before":len(base_school),"pool_school_draft":len(ps),
        "human_guardrails_preserved":sorted(HUMAN_REALISM_HARDENED_V560),
        **metrics,
        "system_rules_preserved":["brak kolizji z lekcją","maksymalnie jedno miejsce dyżuru w tym samym slocie",
          "brak kolizji 1–3 / cała szkoła","ręczne blokady administratora","stałe przydziały administratora",
          "brak dyżuru w dniu bez lekcji","zakaz oczekiwania co najmniej 2 okresów"],
        "_result13":ev["school13"].get("assignments",[]),"_resultSchool":ev["school"].get("assignments",[]),
        "_enabled13":p13,"_enabledSchool":ps
    }

def _working_from_full_eval_v579(state,e13,es,ev,strategy="pełny baseline"):
    """Build a live-capable draft from an already solved full coverage result.
    No second CP-SAT solve is performed here: this is the fast publication path."""
    full=bool(ev and not ev.get("inconclusive") and int(ev.get("missing",10**6))==0)
    if not full:return {"full":False,"missing":int((ev or {}).get("missing",10**6))}
    relax_rows=[]
    metrics=_draft_metrics_v527(ev,relax_rows,state)
    a13=list(ev.get("school13",{}).get("assignments",[]) or [])
    ass=list(ev.get("school",{}).get("assignments",[]) or [])
    all_assignments=a13+ass
    metrics.update(_fairness_profile_v559(state,all_assignments,set(e13)|set(es)))
    metrics.update(_human_guardrail_profile_v560(state,all_assignments))
    metrics["after_last_long_proof"]=_edge_rule_exception_proof_v555(state,e13,es,"after_last_long")
    metrics["before_first_long_proof"]=_edge_rule_exception_proof_v555(state,e13,es,"before_first_long")
    d13=(ev.get("school13",{}).get("diagnostics",{}) or {})
    ds=(ev.get("school",{}).get("diagnostics",{}) or {})
    bm=break_map()
    def edge_count(rows,which):
        total=0
        for a in rows:
            n=a.get("teacher");ab=a.get("abbr");sl=a.get("slot")
            if not n or not ab or not sl:continue
            br=bm.get((ab,sl))
            if not br or int(br.get("minutes",0) or 0)<=SHORT_BREAK_MAX_MINUTES:continue
            ps=lesson_periods(n,ab)
            if not ps:continue
            if which=="after":
                prev=br.get("prev")
                if prev in ps and int(prev)==max(ps):total+=1
            else:
                nxt=br.get("next")
                if nxt in ps and int(nxt)==min(ps):total+=1
        return total
    after_scope=[edge_count(a13,"after"),edge_count(ass,"after")]
    before_scope=[edge_count(a13,"before"),edge_count(ass,"before")]
    metrics["after_last_long_scope_counts"]=after_scope
    metrics["before_first_long_scope_counts"]=before_scope
    metrics["after_last_long_lex_statuses"]=[d13.get("after_last_long_lex_status"),ds.get("after_last_long_lex_status")]
    metrics["before_first_long_lex_statuses"]=[d13.get("before_first_long_lex_status"),ds.get("before_first_long_lex_status")]
    metrics["after_last_long_lex_proven"]=all(c==0 or metrics["after_last_long_lex_statuses"][i]=="OPTIMAL" for i,c in enumerate(after_scope))
    metrics["before_first_long_lex_proven"]=all(c==0 or metrics["before_first_long_lex_statuses"][i]=="OPTIMAL" for i,c in enumerate(before_scope))
    wf_scope=[int(metrics.get("wf_assignments_13",0) or 0),int(metrics.get("wf_assignments_school",0) or 0)]
    metrics["wf_fallback_scope_counts"]=wf_scope
    metrics["wf_fallback_lex_statuses"]=[d13.get("wf_fallback_status"),ds.get("wf_fallback_status")]
    metrics["wf_fallback_lex_proven"]=all(c==0 or metrics["wf_fallback_lex_statuses"][i]=="OPTIMAL" for i,c in enumerate(wf_scope))
    return {
        "status":"full","full":True,"nonoptimal":True,
        "coverage13":{k:ev["school13"][k] for k in ("required","filled","missing")},
        "coverageSchool":{k:ev["school"][k] for k in ("required","filled","missing")},
        "missing":0,"elapsed_s":0,"solve_s":0,"order":ev.get("order"),"strategy":strategy,
        "temporary_relaxations":[],"hardened_keys":[],"hardened_labels":[],
        "pool13_before":len(e13),"pool13_draft":len(e13),
        "pool_school_before":len(es),"pool_school_draft":len(es),
        "human_guardrails_preserved":sorted(HUMAN_REALISM_HARDENED_V560),
        **metrics,
        "system_rules_preserved":["brak kolizji z lekcją","maksymalnie jedno miejsce dyżuru w tym samym slocie",
          "brak kolizji 1–3 / cała szkoła","ręczne blokady administratora","stałe przydziały administratora",
          "brak dyżuru w dniu bez lekcji","zakaz oczekiwania co najmniej 2 okresów"],
        "_result13":a13,"_resultSchool":ass,
        "_enabled13":list(e13),"_enabledSchool":list(es)
    }

def _working_from_fast_eval_v580(state,e13,es,ev,strategy="pełny szybki test"):
    if not ev or ev.get("inconclusive") or int(ev.get("missing",10**6))!=0:
        return {"full":False,"missing":int((ev or {}).get("missing",10**6))}
    joint={
        "school13":{**(ev.get("coverage13") or {}),
                    "assignments":list(ev.get("result13",[]) or []),
                    "waits":list(ev.get("waits13",[]) or []),
                    "diagnostics":_copy.deepcopy(ev.get("diagnostics13",{}) or {})},
        "school":{**(ev.get("coverageSchool") or {}),
                  "assignments":list(ev.get("resultSchool",[]) or []),
                  "waits":list(ev.get("waitsSchool",[]) or []),
                  "diagnostics":_copy.deepcopy(ev.get("diagnosticsSchool",{}) or {})},
        "missing":0,"inconclusive":False,"order":ev.get("order")
    }
    return _working_from_full_eval_v579(state,e13,es,joint,strategy)

def _working_signature_v527(q):
    m={**_map13_flat(q.get("_result13",[])),**_map_school_flat(q.get("_resultSchool",[]))}
    return tuple(sorted((k,(v or {}).get("teacher","")) for k,v in m.items()))

def _live_eligibility_v565(q,job=None):
    reasons=[]
    accepted=_accepted_compromises(job)
    if not q or not q.get("full") or int(q.get("missing",10**9) or 0)!=0:
        reasons.append("coverage_not_full")
    if q.get("human_guardrail_ok") is False:
        reasons.append("human_guardrail")
    wf_locked=int((job or {}).get("wf_locked_baseline",0) or 0)
    wf_extra=max(0,int(q.get("wf_assignments_total",0) or 0)-wf_locked)
    if wf_extra>0 and q.get("wf_fallback_lex_proven") is not True:
        reasons.append("wf_fallback_not_proven_minimum")
    # Severe edge-of-day exceptions may enter live only after CP-SAT has PROVEN
    # their lexicographic minimum (OPTIMAL), unless the administrator explicitly
    # accepted that compromise.
    if "after_last_long" not in accepted and int(q.get("after_last_long",0) or 0)>0:
        if not (job or {}).get("after_last_long_unlocked",False):
            reasons.append("after_last_long_phase_not_unlocked")
        elif q.get("after_last_long_lex_proven") is not True:
            reasons.append("after_last_long_not_proven_minimum")
    if "before_first_long" not in accepted and int(q.get("before_first_long",0) or 0)>0 and q.get("before_first_long_lex_proven") is not True:
        reasons.append("before_first_long_not_proven_minimum")
    return {"ok":not reasons,"reasons":reasons}

def _job_add_working_v527(job,q,reason,improved_rule=""):
    q=_repair_mojibake_recursive_v567(q)
    if not q.get("full"): return False
    eligibility=_live_eligibility_v565(q,job)
    q["live_eligible"]=bool(eligibility["ok"])
    q["live_rejection_reasons"]=list(eligibility["reasons"])
    sig=_working_signature_v527(q)
    with REPAIR_JOB_LOCK:
        priv=job.setdefault("_working_private",{})
        seen=job.setdefault("_working_signatures_seen",set())
        if sig in seen:return False
        seen.add(sig)
        job["full_drafts_seen_total"]=int(job.get("full_drafts_seen_total",0))+1
        if q.get("human_guardrail_ok") is False:
            job["working_rejected_human_total"]=int(job.get("working_rejected_human_total",0))+1
            job["last_human_rejection"]={
                "at":datetime.now().isoformat(timespec="seconds"),
                "reason":reason,
                "violations":_copy.deepcopy(q.get("human_guardrail_violations",[])),
                "max_weekly":q.get("human_max_weekly_duties"),
                "max_daily":q.get("human_max_daily_duties"),
                "longest_consecutive":q.get("human_longest_consecutive_duties"),
                "max_long_week":q.get("human_max_long_week"),
                "max_long_day":q.get("human_max_long_day"),
            }
            return False
        if q.get("fairness_grossly_unbalanced"):
            job["working_fairness_warning_total"]=int(job.get("working_fairness_warning_total",0))+1
            job["last_fairness_warning"]={
                "at":datetime.now().isoformat(timespec="seconds"),
                "reason":reason,
                "normalized_deviation":q.get("fairness_normalized_deviation"),
                "max_ratio":q.get("fairness_max_ratio"),
                "max_excess":q.get("fairness_max_excess"),
                "top10_share":q.get("fairness_top10_share"),
                "reasons":_copy.deepcopy(q.get("fairness_rejection_reasons",[])),
            }
        if not eligibility["ok"]:
            job["working_rejected_live_contract_total"]=int(job.get("working_rejected_live_contract_total",0))+1
            job["last_live_contract_rejection"]={"at":datetime.now().isoformat(timespec="seconds"),
                                                  "reason":reason,
                                                  "reasons":list(eligibility["reasons"]),
                                                  "after_last_long":int(q.get("after_last_long",0) or 0),
                                                  "before_first_long":int(q.get("before_first_long",0) or 0),
                                                  "after_statuses":_copy.deepcopy(q.get("after_last_long_lex_statuses",[])),
                                                  "before_statuses":_copy.deepcopy(q.get("before_first_long_lex_statuses",[]))}
            return False
        current=job.get("working_variants",[])
        # v5.59: only fair-enough full drafts may become live anchors. Grossly
        # concentrated solutions are discarded before LNS / deeper analysis.
        seq=int(job.get("_working_seq",0))+1;job["_working_seq"]=seq
        vid="wrk_"+uuid.uuid4().hex[:10]
        previous=max(priv.values(),key=lambda x:x.get("seq",0),default=None)
        delta={"positions_changed":0,"teachers_changed":0}
        if previous:
            old={**_map13_flat(previous.get("_result13",[])),**_map_school_flat(previous.get("_resultSchool",[]))}
            new={**_map13_flat(q.get("_result13",[])),**_map_school_flat(q.get("_resultSchool",[]))}
            tc=_teacher_changes(old,new);delta={"positions_changed":tc["positions_changed"],"teachers_changed":tc["teachers_changed"]}
        full={**_copy.deepcopy(q),"id":vid,"seq":seq,"reason":reason,"improved_rule":improved_rule,
              "found_at":datetime.now().isoformat(timespec="seconds"),"difference_from_previous":delta,"_signature":sig}
        priv[vid]=full
        public={k:v for k,v in full.items() if not k.startswith("_")}
        # UI preview: expose assignments of the draft, but keep them out of persisted plan state.
        public["result_13"]=_copy.deepcopy(full.get("_result13",[]))
        public["result_school"]=_copy.deepcopy(full.get("_resultSchool",[]))
        arr=job.setdefault("working_variants",[])
        arr=[x for x in arr if x.get("id")!=vid]+[public]
        # Best first; keep the ten best previews while counting every unique full draft.
        arr.sort(key=lambda x:(_working_quality_key_v559(x,job),x.get("seq",0)))
        if len(arr)>10:
            dropped=arr[10:];arr=arr[:10]
            for x in dropped:priv.pop(x.get("id"),None)
        job["working_variants"]=arr
        job["quick_draft"]=arr[0] if arr else public
        job["working_found_total"]=seq
        _persist_last_good_plan_v577(
            public.get("result_13") or [],public.get("result_school") or [],
            {"kind":"live_verified","source_id":"live:"+str(job.get("id") or "")+":"+str(vid),
             "variant_id":vid,"seq":seq,"job_id":job.get("id"),"found_at":public.get("found_at")},
            load_state(),public)
        batch=max(1,int(job.get("solution_batch_size",10) or 10))
        threshold=int(job.get("_next_solution_pause",batch) or batch)
        if not bool(job.get("continuous_search",True)) and seq>=threshold:
            job["status"]="paused";job["auto_paused"]=True
            job["stage"]=f"Znaleziono {seq} pełnych szkiców — pauza"
            job["message"]=(f"Znaleziono {seq} unikalnych pełnych szkiców roboczych. "
                            f"Wyszukiwanie wstrzymane po paczce {batch}. Kliknij „Szukaj następnych”, aby znaleźć kolejną paczkę.")
    return True

def _advance_working_v527(job,state,e13,es,reason):
    with REPAIR_JOB_LOCK:
        arr=_copy.deepcopy(job.get("working_variants",[]))
        hardened=list(job.get("_working_hardened",[]))
        attempt=int(job.get("_working_attempt",0))+1;job["_working_attempt"]=attempt
    if not arr:return False
    best=arr[0]

    accepted=_accepted_compromises(job,state)
    # If the best full assignment already has zero of a severe effect,
    # that rule can be promoted to hard without losing this assignment.
    # Human-accepted compromises are deliberately skipped.
    metric_for={"avoid_wait":"wait_lessons_total","after_last_long":"after_last_long","before_first_long":"before_first_long"}
    changed=True
    while changed:
        changed=False
        for key,_label in WORKING_TIGHTEN_ORDER:
            if key in hardened or key in accepted:continue
            metric=metric_for.get(key)
            if metric and int(best.get(metric,0) or 0)==0:
                hardened.append(key);changed=True
                continue
            break

    if len(hardened)>=len(WORKING_TIGHTEN_ORDER):
        with REPAIR_JOB_LOCK:job["_working_hardened"]=hardened
        return False

    remaining=[x for x in WORKING_TIGHTEN_ORDER if x[0] not in hardened and x[0] not in accepted]
    if not remaining:return False
    key,label=remaining[0]
    seconds=min(16,4+attempt*2)

    # First try to restore the next worst rule completely.
    q=_quick_draft_v527(state,e13,es,hardened+[key],seed_offset=attempt,optimize_seconds=seconds)
    if q.get("full"):
        with REPAIR_JOB_LOCK:
            job["_working_hardened"]=hardened+[key]
            job.pop("working_last_failed_rule",None)
        return _job_add_working_v527(job,q,reason,improved_rule=label)

    # If zeroing that effect would lose coverage, keep the current hard set and
    # search for a different full assignment that minimizes the effect as much as possible.
    q2=_quick_draft_v527(state,e13,es,hardened,seed_offset=100+attempt,optimize_seconds=seconds)
    added=False
    if q2.get("full"):
        added=_job_add_working_v527(job,q2,reason+" — redukcja najgorszego naruszenia",improved_rule="")
        with REPAIR_JOB_LOCK:job["_working_hardened"]=hardened
    with REPAIR_JOB_LOCK:
        job["working_last_failed_rule"]=label
        job["working_last_failed_at"]=datetime.now().isoformat(timespec="seconds")
    return added

def _working_checkpoint_v527(job,state,e13,es,reason):
    """Keep the reverse/full-coverage lane alive during long forward searches."""
    added=_advance_working_v527(job,state,e13,es,reason)
    if added:
        return True
    with REPAIR_JOB_LOCK:
        attempt=int(job.get("_working_attempt",0))+1
        hardened=list(job.get("_working_hardened",[]))
        job["_working_attempt"]=attempt
    draft_state=_copy.deepcopy(state)
    draft_state["_wf_fallback_unlocked"]=bool(job.get("wf_fallback_unlocked",False))
    q=_quick_draft_v527(draft_state,e13,es,hardened,seed_offset=500+attempt,optimize_seconds=6)
    if q.get("full"):
        return _job_add_working_v527(job,q,reason+" — alternatywny pełny szkic")
    return False


def _run_repair_job(job,state,e13,es):
    try:
        TARGET=5
        with REPAIR_JOB_LOCK:
            _preflight_probe={"id":"preflight","phase":"preflight","source":"NODE00",
                              "title":"Preflight: pojemność i realna dostępność nauczycieli",
                              "tokens":[],"changes":[],"started_at":datetime.now().isoformat(timespec="seconds")}
            job["status"]="running";job["stage"]="Preflight: szybki test wykonalności"
            job["message"]="Sprawdzam minimalną pojemność limitów, dostępność nauczycieli w slotach i oczywiste konflikty przed uruchomieniem CP-SAT."
            job["current_probe"]=_copy.deepcopy(_preflight_probe);job["active_probes"]=[_copy.deepcopy(_preflight_probe)]
            job["block_total"]=1;job["block_done"]=0
            job["search_policy"]="Pełna obsada -> ochrona końca dnia -> minimalne WF poza salą gimnastyczną -> preferencje nauczyciel × miejsce -> pozostały komfort/fairness; avoid_wait na końcu."
            job["best_partials"]=[];job["inconclusive_samples"]=[];job["trial_count"]=0
            job["deep_checked"]=0;job["deep_active"]=0;job["inconclusive_trials"]=0
            _seeded=_copy.deepcopy(job.get("_seed_working_variants",[]) or [])
            job["working_variants"]=_seeded;job["_working_private"]={};job["_working_signatures_seen"]=set()
            job["_working_seq"]=max([int(v.get("seq",0) or 0) for v in _seeded],default=0)
            job["working_found_total"]=job["_working_seq"];job["quick_draft"]=(_seeded[0] if _seeded else None);job["auto_paused"]=False
            job["_working_hardened"]=["avoid_wait"];job["_working_attempt"]=0
            job["_next_working_checkpoint"]=320
            job["_next_solution_pause"]=int(job.get("solution_batch_size",10) or 10)
            job["target_full"]=TARGET;job["progress_mode"]="full_variants";job["search_algorithm"]="Szerokie testy → binary dla limitów → dzielenie wyjątków na połowy → best-first/beam → LNS"
            job["accepted_compromises"]=list((state.get("repair_guidance",{}) or {}).get("accepted_compromises",[]) or [])
        lp=REPAIR_CHECKPOINT_DIR/(job["id"]+".jsonl")
        try:lp.unlink()
        except FileNotFoundError:pass
        _repair_checkpoint(job)

        # v5.42 fixed rule: staffing follows actual timetable activity in each zone.
        corrected=ensure_state_schema(_copy.deepcopy(state))
        auto_staffing_changes=_apply_timetable_staffing(corrected)
        if auto_staffing_changes:
            corrected["last_auto_staffing_changes"]=_copy.deepcopy(auto_staffing_changes)
            save_state(corrected)
        elif corrected.get("last_auto_staffing_changes"):
            auto_staffing_changes=_copy.deepcopy(corrected.get("last_auto_staffing_changes") or [])
        state=corrected
        base_state=_copy.deepcopy(corrected)
        inactive=set(base_state.get("excluded_teachers",[]))|set(base_state.get("absent_teachers",[]))
        e13=[n for n in ALL if n not in inactive]
        es=list(e13)
        with REPAIR_JOB_LOCK:
            job["wf_policy"]="lexicographic_fallback_outside_wf_only_places"
            job["wf_fallback_unlocked"]=True
            job["wf_locked_baseline"]=0
            job["wf_filtered_from_initial_13"]=0
            job["wf_filtered_from_initial_school"]=0
        fp=_repair_learning_fingerprint(base_state,e13,es)
        learned=_repair_learning_load_context(fp)
        global_knowledge=_solver_knowledge_snapshot()
        with REPAIR_JOB_LOCK:
            job["_learning_fp"]=fp;job["_learning_trials"]=learned;job["_learning_dirty"]=0
            job["_solver_knowledge"]=global_knowledge;job["_solver_knowledge_dirty"]=0
            job["learning_context"]=fp[:10];job["learning_known_trials"]=len(learned)
            job["solver_knowledge_entries"]=len((global_knowledge.get("stats") or {}))
            job["solver_knowledge_policy"]="Kontekst bieżącego planu + wiedza przekrojowa między planami; historia wpływa wyłącznie na kolejność prób w obrębie tego samego etapu."
            job["solver_knowledge_summary"]=_solver_knowledge_public_summary(job)
            job["learning_policy"]="Pełne znane najpierw → nowe → znane słabe → wcześniejsze timeouty; wiedza globalna porządkuje próby, ale niczego nie pomija."
        # Fast-first policy: baseline exists to publish the first safe full draft,
        # not to optimize every soft preference. Prove full coverage and the live
        # WF fallback contract quickly; full comfort/place optimization follows later.
        base_state["solver_contract_only"]=True
        base_state["solver_internal_workers"]=8
        base_state["solver_coverage_seconds"]=4
        base_state["solver_coverage_retry_seconds"]=12
        base_state["solver_wf_fallback_seconds"]=4

        preflight=_repair_preflight_v520(base_state,e13,es,auto_staffing_changes)
        preflight["auto_constraint_relaxations"]=_copy.deepcopy(base_state.get("last_preflight_constraint_relaxations",[]))
        preflight["constraint_relaxation_policy"]={
            "staffing_reduction_allowed_only_for_inactive_timetable_zone":True,
            "hard_impossible_becomes_soft_priority":5,
            "never_auto_relaxed":sorted(NEVER_AUTO_RELAX_KEYS),
        }
        irreducible=[]
        for p in preflight.get("slot_problems",[]):
            frozen=bool(base_state.get("freeze_pool_13" if p.get("scope")=="1-3" else "freeze_pool_school",False))
            possible=int(p.get("possible_without_relax",0) if frozen else p.get("possible_with_pool_expansion",0))
            if p.get("admin_lock_blocker") or possible<int(p.get("required",0) or 0):
                irreducible.append(p)
        with REPAIR_JOB_LOCK:
            job["preflight"]=preflight
            job["obvious_blockers"]=len(irreducible)+len(preflight.get("recommendations",[]))
            job["preflight_irreducible"]=irreducible
            job["stage"]="Szybki test wykonalności"
            if irreducible:
                job["status"]="completed";job["progress"]=100
                job["message"]=(f"Preflight udowodnił niewykonalność {len(irreducible)} slotu/slotów przy wymaganej obsadzie. "
                                "Nie uruchamiam CP-SAT dla zadania, o którym z góry wiadomo, że nie ma rozwiązania.")
            elif job["obvious_blockers"]:
                job["message"]=f"Precheck wykrył {job['obvious_blockers']} oczywistych ograniczeń przed pełnym CP-SAT."
            else:
                job["message"]="Precheck nie wykrył oczywistej niewykonalności; uruchamiam pełny solver."
        _repair_checkpoint(job)
        if irreducible:
            return

        # v5.77: do not burn minutes on redundant startup quick-drafts.
        # Baseline + broad probes already explore the same protected search space,
        # and stage 4 has a targeted single-WF repair path for the best partial.
        with REPAIR_JOB_LOCK:
            job["stage"]="Start: baseline i szerokie testy"
            job["message"]="Pomijam kosztowne, redundantne skoki startowe; od razu liczę baseline, fazy 1–3 i najlepszy częściowy trop."
            job["jump_total"]=0
            job["jump_checked"]=0
            job["startup_jump_policy"]="disabled_v577_redundant_with_broad_probes"
        _repair_checkpoint(job)

        baseline_probe={
            "id":"baseline","phase":"baseline","source":"NODE00",
            "title":"Baseline: pełna obsada bez ustępstw",
            "tokens":[],"changes":[],
            "started_at":datetime.now().isoformat(timespec="seconds"),
            "parameters":{
                "workers":base_state.get("solver_internal_workers"),
                "coverage_seconds":base_state.get("solver_coverage_seconds"),
                "retry_seconds":base_state.get("solver_coverage_retry_seconds"),
                "wf_fallback_seconds":base_state.get("solver_wf_fallback_seconds"),
            },
        }
        with REPAIR_JOB_LOCK:
            job["stage"]="Baseline: pełna obsada bez ustępstw"
            job["message"]="Sprawdzam pełną obsadę na aktualnych twardych regułach, bez dodatkowych ustępstw. Jeśli zostaną maksymalnie 3 braki, następny krok to lokalna naprawa tylko tych slotów."
            job["current_probe"]=_copy.deepcopy(baseline_probe)
            job["active_probes"]=[_copy.deepcopy(baseline_probe)]
            job["block_total"]=1
            job["block_done"]=0
        _repair_checkpoint(job)
        base_started=_time.perf_counter()
        base=_joint_coverage_v2(base_state,e13,es,optimize=False)
        base_elapsed=_time.perf_counter()-base_started
        with REPAIR_JOB_LOCK:
            job["baseline13"]={k:base["school13"][k] for k in ("required","filled","missing")}
            job["baselineSchool"]={k:base["school"][k] for k in ("required","filled","missing")}
            job["best_missing"]=None if base.get("inconclusive") else base["missing"]
            job["baseline_inconclusive"]=bool(base.get("inconclusive"))
            job["baseline_order"]=base.get("order")
            job["baseline_blockers13"]=base["school13"].get("diagnostics",{}).get("hard_rejections",[])[:12]
            job["baseline_blockersSchool"]=base["school"].get("diagnostics",{}).get("hard_rejections",[])[:12]
            job["baseline_unresolved13"]=_copy.deepcopy(base["school13"].get("diagnostics",{}).get("unresolved",[])[:12])
            job["baseline_unresolvedSchool"]=_copy.deepcopy(base["school"].get("diagnostics",{}).get("unresolved",[])[:12])
            job["active_probes"]=[]
            job["current_probe"]=None
            job["block_done"]=1
            job["last_probe_result"]={
                "title":"Baseline: pełna obsada bez ustępstw",
                "phase":"baseline",
                "source":"NODE00",
                "missing":None if base.get("inconclusive") else int(base.get("missing",10**6)),
                "inconclusive":bool(base.get("inconclusive")),
                "elapsed_s":round(base_elapsed,3),
                "coverage13":_copy.deepcopy(job["baseline13"]),
                "coverageSchool":_copy.deepcopy(job["baselineSchool"]),
            }
        _repair_checkpoint(job)

        if not base.get("inconclusive") and base["missing"]==0:
            # Publish the already solved full baseline immediately. Do not make the
            # GUI wait for a second, expensive comfort-optimization solve.
            quick=_working_from_full_eval_v579(base_state,e13,es,base,"pełny baseline — natychmiastowy podgląd")
            quick_added=_job_add_working_v527(job,quick,"pełny baseline — natychmiastowy podgląd")
            with REPAIR_JOB_LOCK:
                if quick_added:
                    job["stage"]="Pełny szkic znaleziony — optymalizuję jakość"
                    job["message"]="Pełna obsada jest już dostępna w GUI. W tle trwa dalsza optymalizacja jakości i komfortu."
            _repair_checkpoint(job)
            _job_add_suggestion(job,_repair_variant_v2(state,state,e13,es,[],[],base))
            with REPAIR_JOB_LOCK:
                job["status"]="completed";job["stage"]="Gotowe";job["progress"]=100
                job["message"]="Plan bazowy daje pełną obsadę bez zmiany parametrów; optymalizacja jakości zakończona."
            _repair_checkpoint(job);return

        candidates=_repair_candidates_v2(state,e13,es,base,preflight)
        with REPAIR_JOB_LOCK:
            job["candidate_count"]=len(candidates)
            job["candidate_groups"]={
                "organizacyjne":sum(1 for c in candidates if c.get("search_stage")==1),
                "indywidualne":sum(1 for c in candidates if c.get("search_stage")==2),
                "globalne":sum(1 for c in candidates if c.get("search_stage")==3),
                "wf_awaryjnie":sum(1 for c in candidates if c.get("search_stage")==4),
                "koniec_dnia_ostatni_fallback":sum(1 for c in candidates if c.get("search_stage")==5),
                "oczekiwanie_absolutnie_ostatnie":sum(1 for c in candidates if c.get("search_stage")==6)
            }
            job["search_space_upper_bound"]={str(st):_rough_stage_space_v520(candidates,st,3) for st in (1,2,3,4,5,6)}
            job["estimated_total"]=0

        def target_reached():
            # v5.30: five strict/final variants are a quality milestone, not a stop condition.
            # Full nonoptimal drafts are accepted as useful solutions and the search continues
            # until the user pauses/stops it or batch mode auto-pauses.
            return False

        def consume(item,ev,source,phase):
            run_working_checkpoint=False
            with REPAIR_JOB_LOCK:
                job["checked"]=int(job.get("checked",0))+1
                checked=int(job["checked"])
                if ev.get("inconclusive"):
                    job["inconclusive_trials"]=int(job.get("inconclusive_trials",0))+1
                job["progress"]=min(100,round(len(job.get("suggestions",[]))*100/TARGET,1))
                next_cp=int(job.get("_next_working_checkpoint",320) or 320)
                if checked>=next_cp:
                    job["_next_working_checkpoint"]=next_cp+320
                    run_working_checkpoint=True
            _record_trial(job,item,ev,source,phase)
            if not ev.get("inconclusive") and int(ev.get("missing",10**6))==0:
                st,p13,ps=_apply_repair_tokens_v2(state,e13,es,item.get("tokens",[]))
                # Publish the already solved full draft before expensive quality optimization.
                if ev.get("result13") is not None and ev.get("resultSchool") is not None:
                    quick=_working_from_fast_eval_v580(st,p13,ps,ev,phase+" — natychmiastowy podgląd")
                    quick_added=_job_add_working_v527(job,quick,phase+" — natychmiastowy podgląd")
                    if quick_added:
                        with REPAIR_JOB_LOCK:
                            job["stage"]="Pełny szkic znaleziony — optymalizuję jakość"
                            job["message"]="Pełna obsada jest już dostępna w GUI. W tle trwa dalsza optymalizacja jakości i komfortu."
                        _repair_checkpoint(job)
                sug=_repair_variant_v2(state,st,p13,ps,item.get("tokens",[]),item.get("changes",[]),ev)
                added=_job_add_suggestion(job,sug)
                if added and sug.get("live_eligible"):
                    live_stage=int(sug.get("search_stage",9) or 9)
                    with REPAIR_JOB_LOCK:
                        prev=int(job.get("lowest_live_stage",99) or 99)
                        job["lowest_live_stage"]=min(prev,live_stage)
                        job["lowest_live_source_id"]="live:"+str(job.get("id") or "")+":"+str(sug.get("id") or "")
            if run_working_checkpoint and not target_reached() and _repair_pausepoint(job):
                _working_checkpoint_v527(job,base_state,e13,es,f"punkt kontrolny po {checked} próbach")
                _repair_checkpoint(job)

        # Track the baseline already computed above; never solve the same
        # baseline a second time just to record it in learning history.
        if not _repair_pausepoint(job):return
        consume({"tokens":[],"changes":[]},
                {"missing":base["missing"],"inconclusive":bool(base.get("inconclusive")),"order":base.get("order"),
                 "coverage13":{k:base["school13"][k] for k in ("required","filled","missing")},
                 "coverageSchool":{k:base["school"][k] for k in ("required","filled","missing")},
                 "result13":base["school13"].get("assignments",[]),
                 "resultSchool":base["school"].get("assignments",[]),
                 "waits13":base["school13"].get("waits",[]),
                 "waitsSchool":base["school"].get("waits",[]),
                 "diagnostics13":_copy.deepcopy(base["school13"].get("diagnostics",{})),
                 "diagnosticsSchool":_copy.deepcopy(base["school"].get("diagnostics",{})),
                 "elapsed_s":base_elapsed},"local","baseline")

        # v5.80: when only 1-3 positions are missing, try the smallest relevant
        # single-step repairs first. Do not enter the huge broad search space yet.
        near_items=_near_full_candidate_items_v580(candidates,base,16)
        if near_items and _repair_pausepoint(job):
            with REPAIR_JOB_LOCK:
                job["near_full_enabled"]=True
                job["near_full_candidates"]=len(near_items)
                job["stage"]=f"Szybka naprawa {int(base.get('missing',0))} braków"
                job["message"]="Plan jest prawie pełny. Najpierw równolegle sprawdzam minimalne pojedyncze korekty zgodne z kolejnością reguł."
            near_full_found=False
            for it,ev,source in _evaluate_near_full_parallel_v580(job,state,e13,es,near_items):
                consume(it,ev,source,"near-full")
                if not ev.get("inconclusive") and int(ev.get("missing",10**6))==0:
                    near_full_found=True
                    with REPAIR_JOB_LOCK:
                        job["near_full_found"]=True
                        job["near_full_winning_tokens"]=list(it.get("tokens",[]))
                    break
            if not near_full_found:
                with REPAIR_JOB_LOCK:
                    job["near_full_found"]=False
                    job["message"]="Minimalne pojedyncze korekty nie domknęły planu; przechodzę do szerokich testów kolejnych poziomów."

        # v5.39: before fine combinatorics, probe four human-readable compromise levels
        # with wide but comfort-bounded, monotonic changes. This answers quickly whether
        # we should keep digging in an earlier level or jump to the next one.
        stage_names={
            1:"Bez pogarszania warunkow pracy",
            2:"Wyjatki indywidualne bez wydluzania dnia",
            3:"Limity, grupy i preferencje bez WF",
            4:"Awaryjny fallback WF",
            5:"OSTATNI fallback komfortu: dluga przerwa po ostatniej lekcji",
            6:"ABSOLUTNIE OSTATNI fallback: dodatkowe oczekiwanie"
        }
        first_full_stage=None
        broad_full_item=None
        broad_best_missing={}
        with REPAIR_JOB_LOCK:
            job["tier_probes"]={}
            job["stage_number"]=1
        for stage in (1,2,3):
            if not _repair_pausepoint(job):return
            item=_broad_probe_item_v539(state,candidates,stage)
            if not item.get("tokens"):continue
            with REPAIR_JOB_LOCK:
                job["stage"]=f"Szeroki test: {stage_names[stage]}"
                job["stage_number"]=stage
                job["message"]="Sprawdzam od razu szeroki, ale nadal rozsądny wariant. Dopiero potem zawężam parametry i wyjątki."
                job["current_probe"]=_terminal_probe_row(item,f"broad-probe-{stage}","deep-local")
                job["active_probes"]=[job["current_probe"]]
            ev=_eval_combo_deep(state,e13,es,item["tokens"])
            with REPAIR_JOB_LOCK:
                job["active_probes"]=[]
            consume(item,ev,"deep-local",f"broad-probe-{stage}")
            missing=int(ev.get("missing",10**6))
            broad_best_missing[stage]=missing
            full=bool(not ev.get("inconclusive") and missing==0)
            with REPAIR_JOB_LOCK:
                job["deep_checked"]=int(job.get("deep_checked",0))+1
                job["tier_probes"][str(stage)]={
                    "stage":stage,"label":stage_names[stage],"missing":missing,
                    "inconclusive":bool(ev.get("inconclusive")),"feasible":full,
                    "changes":len(item.get("tokens",[])),"broad":True
                }
            _repair_checkpoint(job)
            if full:
                first_full_stage=stage
                broad_full_item=item
                with REPAIR_JOB_LOCK:
                    job["first_full_stage"]=stage
                    job["message"]=f"Pełny plan znaleziony już w poziomie: {stage_names[stage]}. Teraz usuwam zbędne ustępstwa połówkowo."
                break

        # If waiting is the first level that yields a full plan, minimize the affected
        # teacher set by delta-debugging: remove half of the exceptions at a time.
        if broad_full_item and first_full_stage==6:
            wait_tokens=[t for t in broad_full_item.get("tokens",[]) if _token_relaxes_rule_v537(t,"avoid_wait")]
            fixed_tokens=[t for t in broad_full_item.get("tokens",[]) if t not in wait_tokens]
            lookup={str(c.get("token","")):c for c in candidates}
            current=list(wait_tokens); granularity=2; tests=0; max_tests=12
            while len(current)>1 and tests<max_tests and _repair_pausepoint(job):
                size=max(1,math.ceil(len(current)/granularity))
                chunks=[current[i:i+size] for i in range(0,len(current),size)]
                reduced=False
                for chunk in chunks:
                    if tests>=max_tests or not _repair_pausepoint(job):break
                    remove=set(chunk)
                    kept=[t for t in current if t not in remove]
                    if not kept:continue
                    toks=fixed_tokens+kept
                    rows=[lookup.get(t,{"token":t,"label":t,"human_cost":999}) for t in toks]
                    it={"tokens":toks,"changes":rows,"probe_stage":4,"probe_kind":"wait-halving"}
                    with REPAIR_JOB_LOCK:
                        job["stage"]="Zmniejszam liczbę nauczycieli, którzy muszą czekać"
                        job["stage_number"]=4
                        job["message"]=f"Połówkowe zawężanie: sprawdzam, czy można zejść z {len(current)} do {len(kept)} wyjątków oczekiwania."
                    ev=_eval_combo_deep(state,e13,es,toks);tests+=1
                    consume(it,ev,"deep-local","wait-halving")
                    if not ev.get("inconclusive") and int(ev.get("missing",10**6))==0:
                        current=kept;broad_full_item=it;reduced=True
                        granularity=max(2,granularity-1)
                        _repair_checkpoint(job)
                        break
                if not reduced:
                    if granularity>=len(current):break
                    granularity=min(len(current),granularity*2)
            with REPAIR_JOB_LOCK:
                job["wait_halving_tests"]=tests
                job["wait_exceptions_after_halving"]=len(current)

        # Use the first broad full plan as the refinement anchor. Only when no broad
        # full plan exists do we fall back to the older middle anchors.
        anchors=[] if broad_full_item else _middle_anchor_items_v527(candidates)
        anchor_full=[broad_full_item] if broad_full_item else []
        if anchors and not target_reached():
            with REPAIR_JOB_LOCK:
                job["stage"]="Szybkie skoki do środka przestrzeni"
                job["message"]="Najpierw próbuję kilku dużych zmian naraz, żeby szybko złapać pełny plan; potem cofam zbędne ustępstwa."
                job["middle_anchor_count"]=len(anchors)
            for it,ev,source in _evaluate_items_parallel(job,state,e13,es,anchors,job["stage"]):
                if not _repair_pausepoint(job):return
                consume(it,ev,source,"middle-anchor")
                if not ev.get("inconclusive") and int(ev.get("missing",10**6))==0:
                    anchor_full.append(it)
        frontier=anchor_full[:]
        for rnd in range(1,6):
            if not frontier or target_reached():break
            better=[];seen=set()
            for base_item in frontier[:3]:
                for n in _anchor_neighbors_v527(base_item,candidates,limit=24,allow_existing_wait=(first_full_stage==6)):
                    sig=tuple(sorted(n.get("tokens",[])))
                    if sig in seen:continue
                    seen.add(sig);better.append(n)
            better=better[:48]
            if not better:break
            with REPAIR_JOB_LOCK:
                job["stage"]=f"Doszukiwanie lepszych wariantów wokół pełnej kotwicy • runda {rnd}"
                job["message"]="Pełna kotwica już istnieje; teraz zawężam limity połówkowo między ustawieniem ścisłym a działającym, a pozostałe ustępstwa usuwam pojedynczo. Niezależny tor nadal szuka innych pełnych szkiców."
            next_frontier=[]
            for it,ev,source in _evaluate_items_parallel(job,state,e13,es,better,job["stage"]):
                if not _repair_pausepoint(job):return
                consume(it,ev,source,f"middle-refine-{rnd}")
                if not ev.get("inconclusive") and int(ev.get("missing",10**6))==0:
                    next_frontier.append(it)
            if not next_frontier:break
            next_frontier.sort(key=lambda x:(sum(int(c.get("human_cost",0) or 0) for c in x.get("changes",[])),len(x.get("tokens",[]))))
            frontier=next_frontier[:4]
        if not target_reached() and _repair_pausepoint(job):
            _working_checkpoint_v527(job,base_state,e13,es,"po szybkich skokach od środka")
            _repair_checkpoint(job)

        # v5.39: preflight is a short sanity sample only. Broad probes above decide
        # where the promising region is; do not burn hundreds of trials on tiny moves.
        preflight_done=set()
        obvious=[c for c in candidates if c.get("category")=="oczywista wykonalność"]
        if obvious and not target_reached():
            limit=12 if broad_full_item else 24
            sample=[{"tokens":[c.get("token","")],"changes":[c]} for c in obvious[:limit]]
            with REPAIR_JOB_LOCK:
                job["stage"]="Krótka kontrola najprostszych poprawek"
                job["message"]=f"Sprawdzam tylko {len(sample)} najprostszych pojedynczych korekt; nie mielę już setek małych kombinacji."
            for it,ev,source in _evaluate_items_parallel(job,state,e13,es,sample,"preflight-sample"):
                if not _repair_pausepoint(job):return
                preflight_done.add(frozenset(it.get("tokens",[])))
                consume(it,ev,source,"preflight-sample")

        if not target_reached() and _repair_pausepoint(job):
            with REPAIR_JOB_LOCK:
                job["stage"]="Równoległa poprawa wariantu roboczego"
                job["message"]="Od strony roboczej próbuję teraz usunąć najgorsze pozostałe ustępstwo, zaczynając od oczekiwania."
            _advance_working_v527(job,base_state,e13,es,"po pierwszych korektach organizacyjnych")
            _repair_checkpoint(job)

        # v5.39: broad probes above already describe all four compromise levels.
        # Keep those results visible instead of overwriting them with the old ceiling test.

        # v5.40: best-first / beam search. Keep only the most promising partial
        # configurations instead of enumerating hundreds of combinations at every depth.
        beam_width_default=18
        beam_expand_limit=72
        beam_depth={1:3,2:3,3:4,4:5,5:5,6:4}
        for stage in (1,2,3,4,5,6):
            if target_reached():break
            if not _repair_pausepoint(job):return
            with REPAIR_JOB_LOCK:
                lowest_live=int(job.get("lowest_live_stage",99) or 99)
            # Once a verified full plan exists without after_last_long, never unlock
            # a worse comfort phase just to collect more variants.
            if stage>=5 and lowest_live<=4:
                with REPAIR_JOB_LOCK:
                    job["protected_phase_stop"]=True
                    job["protected_phase_stop_reason"]="verified_full_plan_exists_before_after_last_long"
                    job["message"]="Mam pe\u0142ny zweryfikowany plan bez luzowania d\u0142ugiej przerwy po ostatniej lekcji; nie otwieram gorszych faz."
                _repair_checkpoint(job)
                break
            stage_candidates=[c for c in candidates if int(c.get("search_stage",9))<=stage]
            if stage==4:
                with REPAIR_JOB_LOCK:
                    job["stage"]="Preferencje miejsca i awaryjne WF ? optymalizacja CP-SAT"
                    job["wf_fallback_unlocked"]=True
                    job["wf_fallback_unlock_reason"]="native_cp_sat_matrix"
                _repair_checkpoint(job)
            if stage==5:
                with REPAIR_JOB_LOCK:
                    job["after_last_long_unlocked"]=True
                    job["after_last_long_unlock_reason"]="stages_1_4_exhausted"
                _repair_checkpoint(job)
            if stage<6:
                stage_candidates=[c for c in stage_candidates if not _token_relaxes_rule_v537(c.get("token"),"avoid_wait")]
            current_tokens={str(c.get("token","")) for c in candidates if int(c.get("search_stage",9))==stage}
            if not current_tokens:continue
            stage_candidates.sort(key=lambda c:(int(c.get("relax_level",0)),_candidate_guided_cost_v541(c,job),str(c.get("token",""))))
            # Earlier broad probes already showed whether an early stage is promising.
            width=10 if first_full_stage and stage<first_full_stage else beam_width_default
            depth_limit=2 if first_full_stage and stage<first_full_stage else beam_depth[stage]
            lookup_stage={str(c.get("token","")):c for c in stage_candidates}
            beam=[{"tokens":[],"changes":[]}]
            with REPAIR_JOB_LOCK:
                _partial_seeds=_copy.deepcopy(job.get("best_partials",[])[:10])
            for bp in _partial_seeds:
                toks=list(dict.fromkeys(bp.get("tokens",[]) or []))
                if not toks or any(t not in lookup_stage for t in toks):
                    continue
                rows=[lookup_stage[t] for t in toks]
                if not _combo_compatible_v520(rows):
                    continue
                if stage<6 and any(_token_relaxes_rule_v537(t,"avoid_wait") for t in toks):
                    continue
                beam.append({"tokens":toks,"changes":rows,"seed_missing":int(bp.get("missing",10**6))})
            # Best partials are already sorted by missing/human cost. Keep a bounded
            # cumulative frontier plus the empty baseline for escape.
            if len(beam)>max(2,width):
                beam=beam[:max(2,width)]
            seen={tuple(sorted(x.get("tokens",[]))) for x in beam if x.get("tokens")}
            with REPAIR_JOB_LOCK:
                job["stage_number"]=stage
                job["stage"]=f"Najlepsze tropy: {stage_names[stage]}"
                job["message"]=f"Beam search: rozwijam tylko {width} najlepszych tropów zamiast sprawdzać wszystkie kombinacje."
                job["beam_width"]=width;job["beam_depth_limit"]=depth_limit
            for depth in range(1,depth_limit+1):
                if not _repair_pausepoint(job):return
                proposals=[]
                for base_item in beam:
                    have=set(base_item.get("tokens",[]))
                    for c in stage_candidates[:120]:
                        tok=str(c.get("token",""))
                        if not tok or tok in have:continue
                        nt=list(base_item.get("tokens",[]))+[tok]
                        if not any(t in current_tokens for t in nt):continue
                        rows=list(base_item.get("changes",[]))+[c]
                        if not _combo_compatible_v520(rows):continue
                        sig=tuple(sorted(nt))
                        if sig in seen:continue
                        seen.add(sig)
                        proposals.append({"tokens":nt,"changes":rows})
                if not proposals:break
                # Learned outcomes prioritize known-good regions but never suppress retesting.
                proposals=_repair_learning_order(job,proposals)
                proposals.sort(key=lambda it:(sum(_candidate_guided_cost_v541(c,job) for c in it.get("changes",[])),len(it.get("tokens",[]))))
                proposals=proposals[:beam_expand_limit]
                scored=[]
                with REPAIR_JOB_LOCK:
                    job["stage"]=f"Najlepsze tropy: {stage_names[stage]} • głębokość {depth}/{depth_limit}"
                    job["message"]=f"Sprawdzam {len(proposals)} najbardziej obiecujące rozwinięcia i zachowuję tylko {width} najlepszych."
                for it,ev,source in _evaluate_items_parallel(job,state,e13,es,proposals,job["stage"]):
                    if not _repair_pausepoint(job):return
                    consume(it,ev,source,f"beam-{stage}-{depth}")
                    cost=sum(_candidate_guided_cost_v541(c,job) for c in it.get("changes",[]))
                    waits=sum(1 for t in it.get("tokens",[]) if _token_relaxes_rule_v537(t,"avoid_wait"))
                    rank=(1 if ev.get("inconclusive") else 0,int(ev.get("missing",10**6)),waits,cost,len(it.get("tokens",[])))
                    scored.append((rank,it))
                if not scored:break
                scored.sort(key=lambda z:z[0])
                beam=[it for _,it in scored[:width]]
                with REPAIR_JOB_LOCK:
                    job["beam_best_missing"]=scored[0][0][1]
                    job["beam_kept"]=len(beam)
                _repair_checkpoint(job)
            with REPAIR_JOB_LOCK:
                job.setdefault("completed_stages",[]).append(stage)
                job["message"]=f"Poziom {stage_names[stage]}: zakończono przeszukiwanie najlepszych tropów."
            _repair_checkpoint(job)

        # v5.40 LNS: after a full suggestion exists, improve it locally while freezing
        # most of the schedule. Two neighborhood sizes balance precision and escape.
        for radius in (1,2):
            if not _repair_pausepoint(job):return
            with REPAIR_JOB_LOCK:
                best_id=(job.get("suggestions") or [{}])[0].get("id") if job.get("suggestions") else None
                private=job.get("_private",{})
                best=_copy.deepcopy(private.get(best_id)) if best_id else None
            if not best:break
            with REPAIR_JOB_LOCK:
                job["stage"]="Lokalna poprawa pełnego planu"
                job["message"]=f"LNS: zamrażam zdrową część planu i przebudowuję problematyczne osoby oraz sąsiednie przerwy (promień {radius})."
                job["lns_radius"]=radius
            improved=_lns_improve_suggestion_v540(state,best,radius=radius)
            if improved and _variant_quality_key_v540(improved)<_variant_quality_key_v540(best):
                _job_add_suggestion(job,improved)
                with REPAIR_JOB_LOCK:
                    job["lns_improvements"]=int(job.get("lns_improvements",0))+1
            with REPAIR_JOB_LOCK:
                job["lns_runs"]=int(job.get("lns_runs",0))+1
            _repair_checkpoint(job)

        # v5.30: after the systematic pass, keep both goals alive indefinitely:
        # improve the best full draft and also generate different full drafts.
        continuous_round=0
        with REPAIR_JOB_LOCK:
            job["stage"]="Ciągłe szukanie kolejnych i lepszych szkiców"
            job["message"]="Przeszukiwanie systematyczne zakończyło pierwszy przebieg. Nadal szukam zarówno lepszych, jak i innych pełnych szkiców."
        _repair_checkpoint(job)
        while _repair_pausepoint(job):
            continuous_round+=1
            with REPAIR_JOB_LOCK:
                if job.get("_cancel"):return
                job["continuous_round"]=continuous_round
                job["stage"]="Ciągłe szukanie kolejnych i lepszych szkiców"
            _working_checkpoint_v527(job,base_state,e13,es,f"ciągłe wyszukiwanie • runda {continuous_round}")
            _repair_checkpoint(job)
    except Exception as exc:
        with REPAIR_JOB_LOCK:
            job["status"]="error";job["stage"]="Błąd";job["error"]=str(exc)
        try:_repair_checkpoint(job)
        except Exception:pass

@app.post("/api/diagnostics/repair/preflight")
def repair_preflight(x:dict):
    s=load_state()
    if "global" in x: s["global_constraints"]=normalize_constraint_rows(x.get("global",[]))
    if "individual" in x: s["individual_constraints"]=normalize_constraint_rows(x.get("individual",[]))
    for key in ("min_people_13","min_people_13_stations","min_people_school","manual_blocks","teacher_place_preferences","preference_grid","excluded_teachers","locked_assignments"):
        if key in x: s[key]=_copy.deepcopy(x[key])
    for key in ("freeze_pool_13","freeze_pool_school"):
        if key in x: s[key]=bool(x[key])
    if "school_locations" in x:s["school_locations"]=list(x.get("school_locations") or [])
    s=ensure_state_schema(s)

    # v5.53 policy:
    # 1) staffing may be auto-zeroed ONLY from timetable-driven zone inactivity;
    # 2) if a user HARD comfort/capacity rule is mathematically impossible with
    #    the required staffing, preflight downgrades that rule to SOFT priority 5;
    # 3) only then may the expensive CP-SAT search start.
    auto_changes=_apply_timetable_staffing(s)
    effective_changes=_copy.deepcopy(auto_changes or s.get("last_auto_staffing_changes") or [])
    e13=list(x["enabled_teachers_13"] if "enabled_teachers_13" in x else s.get("enabled_teachers_13",list(ALL)))
    es=_school_pool(x["enabled_teachers_school"] if "enabled_teachers_school" in x else s.get("enabled_teachers_school",list(ALL)))

    auto_relax=[]
    auto_relax.extend(_auto_relax_edge_constraints_v553(s,e13,es))
    auto_relax.extend(_auto_relax_individual_directional_v553(s,e13,es))
    auto_relax.extend(_auto_relax_consecutive_v553(s,e13,es))

    # Capacity lower bounds are already computed by the normal preflight. Use
    # those proofs to soften impossible numeric HARD caps instead of changing
    # their numeric value or reducing staffing.
    first=_repair_preflight_v520(s,e13,es,effective_changes)
    numeric=_auto_relax_numeric_v553(s,first.get("recommendations",[]))
    auto_relax.extend(numeric)
    out=_repair_preflight_v520(s,e13,es,effective_changes) if numeric else first

    persisted=load_state();before_persisted=_copy.deepcopy(persisted)
    for key in ("min_people_13","min_people_13_stations","min_people_school","auto_staffing_by_timetable"):
        persisted[key]=_copy.deepcopy(s.get(key,{}))
    persisted["last_auto_staffing_changes"]=effective_changes

    # Persist only the rules actually auto-softened; do not silently save other
    # unsaved UI edits that merely happened to be present in the preflight request.
    if auto_relax:
        pby={str(r.get("key")):r for r in persisted.get("global_constraints",[]) if isinstance(r,dict)}
        iby={str(r.get("id")):r for r in persisted.get("individual_constraints",[]) if isinstance(r,dict)}
        for ch in auto_relax:
            if ch.get("constraint_type")=="individual":
                rid=str(ch.get("id") or "")
                src=next((r for r in s.get("individual_constraints",[]) if str(r.get("id"))==rid),None)
                if src and rid in iby:
                    iby[rid].update(_copy.deepcopy(src))
                continue
            src=_global_row(s,ch.get("key"))
            if not src: continue
            if ch.get("key") in pby:
                pby[ch.get("key")].update(_copy.deepcopy(src))
            else:
                persisted.setdefault("global_constraints",[]).append(_copy.deepcopy(src))
    active_relax=_active_auto_relaxations_v554(
        s,before_persisted.get("last_preflight_constraint_relaxations",[]),auto_relax)
    persisted["last_preflight_constraint_relaxations"]=_copy.deepcopy(active_relax)
    reason="Preflight zaktualizował obsadę z planu lekcji"
    if auto_relax:
        reason+=f" i automatycznie złagodził {len(auto_relax)} niewykonalną/e regułę/y MUSI BYĆ do ZALECANE 5"
    _save_solver_input_change(before_persisted,persisted,reason+".")

    out["auto_constraint_relaxations"]=auto_relax
    out["active_constraint_relaxations"]=_copy.deepcopy(active_relax)
    out["corrected_global_constraints"]=_copy.deepcopy(s.get("global_constraints",[]))
    out["corrected_individual_constraints"]=_copy.deepcopy(s.get("individual_constraints",[]))
    out["constraint_relaxation_policy"]={
        "staffing_reduction_allowed_only_for_inactive_timetable_zone":True,
        "hard_impossible_becomes_soft_priority":5,
        "never_auto_relaxed":sorted(NEVER_AUTO_RELAX_KEYS),
    }
    out["corrected_staffing"]={
        "min_people_13":_copy.deepcopy(s.get("min_people_13",{})),
        "min_people_13_stations":_copy.deepcopy(s.get("min_people_13_stations",{})),
        "min_people_school":_copy.deepcopy(s.get("min_people_school",{})),
    }
    return out

@app.post("/api/diagnostics/repair/search")
def repair_search_start(x:dict):
    # Do not accidentally start a second expensive search while one is already alive.
    with REPAIR_JOB_LOCK:
        active=[j for j in REPAIR_JOBS.values() if j.get("status") in ("queued","running","paused") and not j.get("_cancel")]
        current=max(active,key=lambda j:j.get("created_at","")) if active else None
    if current and not bool(x.get("force_restart",False)):
        return _repair_copy_public(current)
    if current and bool(x.get("force_restart",False)):
        with REPAIR_JOB_LOCK:
            current["_cancel"]=True; current["status"]="cancelled"; current["stage"]="Zatrzymane po zmianie parametrów"; current["local_active"]=0; current["remote_active"]=0
        try: _repair_farm.cancel_job(current["id"])
        except Exception: pass
    s=load_state()
    if "global" in x: s["global_constraints"]=normalize_constraint_rows(x.get("global",[]))
    if "individual" in x: s["individual_constraints"]=normalize_constraint_rows(x.get("individual",[]))
    for key in ("min_people_13","min_people_13_stations","min_people_school","manual_blocks","preference_grid","excluded_teachers","locked_assignments"):
        if key in x: s[key]=_copy.deepcopy(x[key])
    for key in ("freeze_pool_13","freeze_pool_school"):
        if key in x: s[key]=bool(x[key])
    if "school_locations" in x: s["school_locations"]=list(x.get("school_locations") or [])
    if "locked_assignments" in x: s["locked_assignments"]=list(x.get("locked_assignments") or [])
    if "last_13_assignments" in x: s["last_13_assignments"]=list(x.get("last_13_assignments") or [])
    if "school_assignments" in x: s["school_assignments"]=list(x.get("school_assignments") or [])
    s=ensure_state_schema(s)
    e13=list(x["enabled_teachers_13"] if "enabled_teachers_13" in x else s.get("enabled_teachers_13",list(ALL)))
    es=_school_pool(x["enabled_teachers_school"] if "enabled_teachers_school" in x else s.get("enabled_teachers_school",list(ALL)))
    fresh_start=bool(x.get("fresh_start",False))
    jid=(_uuid.uuid4().hex if fresh_start else (_checkpoint_resume_id(s) or _uuid.uuid4().hex))
    seeded=[] if fresh_start else _checkpoint_live_seed(s)
    _created=datetime.now().isoformat()
    _initial_probe={"id":"queued","phase":"queued","source":"NODE00",
                    "title":"Przygotowanie szybkiego testu wykonalności",
                    "tokens":[],"changes":[],"started_at":_created}
    job={"id":jid,"status":"queued","stage":"Kolejka: szybki test wykonalności","checked":0,"estimated_total":1,"progress":0,
         "suggestions":[],"best_missing":None,"created_at":_created,
         "message":"Przygotowuję preflight i baseline dla aktualnej konfiguracji. GUI jest zsynchronizowane z tym jobem.",
         "current_probe":_copy.deepcopy(_initial_probe),"active_probes":[_copy.deepcopy(_initial_probe)],
         "block_total":1,"block_done":0,
         "continuous_search":bool(x.get("continuous_search",True)),"solution_batch_size":10,
         "fresh_start":fresh_start,"working_found_total":0,"auto_paused":False,"_next_solution_pause":10,
         "plan_revision":int(s.get("plan_revision",0) or 0),"_seed_working_variants":seeded}
    with REPAIR_JOB_LOCK: REPAIR_JOBS[jid]=job
    th=_threading.Thread(target=_run_repair_job,args=(job,_copy.deepcopy(s),e13,es),daemon=True,name="repair-"+jid[:8])
    job["_thread"]=th; job["_private"]={}; job["_cancel"]=False
    th.start()
    return _repair_copy_public(job)

@app.get("/api/diagnostics/repair/search/current")
def repair_search_current():
    with REPAIR_JOB_LOCK:
        jobs=list(REPAIR_JOBS.values())
        active=[j for j in jobs if j.get("status") in ("queued","running","paused") and not j.get("_cancel")]
        pool=active or jobs
        current=max(pool,key=lambda j:j.get("created_at","")) if pool else None
    eff=_effective_plan_v574(load_state())
    return {"job":_repair_copy_public(current) if current else _latest_repair_checkpoint(),
            "effective_plan_source":eff.get("source")}

@app.get("/api/diagnostics/repair/search/{job_id}")
def repair_search_status(job_id:str):
    job=REPAIR_JOBS.get(job_id)
    if not job: raise HTTPException(404,"Nie ma takiego wyszukiwania.")
    out=_repair_copy_public(job)
    out["effective_plan_source"]=_effective_plan_v574(load_state()).get("source")
    return out

@app.post("/api/diagnostics/repair/search/{job_id}/pause")
def repair_search_pause(job_id:str):
    job=REPAIR_JOBS.get(job_id)
    if not job: raise HTTPException(404,"Nie ma takiego wyszukiwania.")
    with REPAIR_JOB_LOCK:
        if job.get("status")=="running":
            job["status"]="paused";job["auto_paused"]=False;job["stage"]="Wstrzymane przez użytkownika"
    _repair_learning_flush(job)
    _repair_checkpoint(job)
    return _repair_copy_public(job)

@app.post("/api/diagnostics/repair/search/{job_id}/resume")
def repair_search_resume(job_id:str):
    job=REPAIR_JOBS.get(job_id)
    if not job: raise HTTPException(404,"Nie ma takiego wyszukiwania.")
    with REPAIR_JOB_LOCK:
        if job.get("status")=="paused":
            if job.get("stale_due_to_manual_edit"):
                raise HTTPException(409,"Plan został ręcznie zmieniony. Uruchom nowe przeliczenie zamiast wznawiać stary przebieg.")
            if job.get("auto_paused"):
                batch=max(1,int(job.get("solution_batch_size",10) or 10))
                job["_next_solution_pause"]=int(job.get("working_found_total",0) or 0)+batch
            job["auto_paused"]=False;job["status"]="running";job["stage"]="Szukam następnych pełnych szkiców"
    return _repair_copy_public(job)

@app.post("/api/diagnostics/repair/search/{job_id}/accept-compromise")
def repair_accept_compromise(job_id:str,x:dict):
    key=str(x.get("key") or "")
    allowed={"avoid_wait","after_last_long","before_first_long","max_consecutive_duties","max_long_day","max_long_week","max_week","max_day_13","max_day_school"}
    if key not in allowed:raise HTTPException(400,"Nieznany kompromis.")
    job=REPAIR_JOBS.get(job_id)
    if not job:raise HTTPException(404,"Nie ma takiego wyszukiwania.")
    s=ensure_state_schema(load_state())
    vals=list((s.get("repair_guidance",{}) or {}).get("accepted_compromises",[]) or [])
    if key not in vals:vals.append(key)
    s.setdefault("repair_guidance",{})["accepted_compromises"]=vals
    save_state(s)
    with REPAIR_JOB_LOCK:
        cur=list(job.get("accepted_compromises",[]) or [])
        if key not in cur:cur.append(key)
        job["accepted_compromises"]=cur
        job["message"]=f"Uwzględniam wskazówkę człowieka: kompromis „{key}” jest akceptowalny i będzie tańszy w dalszym wyszukiwaniu."
    _repair_checkpoint(job)
    return _repair_copy_public(job)

@app.post("/api/diagnostics/repair/guidance/clear")
def repair_guidance_clear():
    s=ensure_state_schema(load_state());s.setdefault("repair_guidance",{})["accepted_compromises"]=[];save_state(s)
    with REPAIR_JOB_LOCK:
        for j in REPAIR_JOBS.values(): j["accepted_compromises"]=[]
    return {"ok":True}

@app.post("/api/diagnostics/repair/search/{job_id}/continuous")
def repair_search_continuous(job_id:str,x:dict):
    job=REPAIR_JOBS.get(job_id)
    if not job: raise HTTPException(404,"Nie ma takiego wyszukiwania.")
    enabled=bool(x.get("enabled",True))
    with REPAIR_JOB_LOCK:
        job["continuous_search"]=enabled
        batch=max(1,int(job.get("solution_batch_size",10) or 10))
        total=int(job.get("working_found_total",0) or 0)
        if enabled:
            if job.get("status")=="paused" and job.get("auto_paused"):
                job["status"]="running";job["stage"]="Wznowiono wyszukiwanie bez końca"
            job["auto_paused"]=False
        else:
            job["_next_solution_pause"]=((total//batch)+1)*batch
            job["message"]=f"Tryb paczkowy: automatyczna pauza po {job['_next_solution_pause']} pełnych szkicach."
    return _repair_copy_public(job)

@app.post("/api/diagnostics/repair/search/{job_id}/cancel")
def repair_search_cancel(job_id:str):
    job=REPAIR_JOBS.get(job_id)
    if not job: raise HTTPException(404,"Nie ma takiego wyszukiwania.")
    with REPAIR_JOB_LOCK:
        job["_cancel"]=True; job["status"]="cancelled"; job["stage"]="Zatrzymane"; job["local_active"]=0; job["remote_active"]=0
    try: _repair_farm.cancel_job(job_id)
    except Exception: pass
    return _repair_copy_public(job)

@app.post("/api/diagnostics/repair/search/{job_id}/apply/{suggestion_id}")
def repair_search_apply(job_id:str,suggestion_id:str):
    job=REPAIR_JOBS.get(job_id)
    if not job: raise HTTPException(404,"Nie ma takiego wyszukiwania.")
    sug=job.get("_private",{}).get(suggestion_id)
    if not sug: raise HTTPException(404,"Nie ma takiego wariantu.")
    before=load_state()
    st=_copy.deepcopy(sug["_state"])
    st["enabled_teachers_13"]=list(sug["_enabled13"]); st["enabled_teachers_school"]=_school_pool(sug["_enabledSchool"])
    changed=_save_solver_input_change(before,st,"Zastosowano wariant znaleziony przez diagnostykę.")
    return {"ok":True,"suggestion_id":suggestion_id,"solver_input_changed":changed}

@app.get("/api/worker-farm/status")
def worker_farm_status():
    return _farm_status_public()

@app.post("/api/worker-farm/settings")
def worker_farm_settings(x:dict):
    cfg=_farm_config()
    if "local_workers" in x: cfg["local_workers"]=max(1,min(8,int(x["local_workers"])))
    _save_farm_config(cfg)
    return _farm_status_public()

@app.post("/api/worker-farm/enable")
def worker_farm_enable():
    cfg=_farm_config();uac=False
    if not _firewall_rule_exists(): uac=_request_firewall_uac(cfg["port"])
    _start_worker_broker()
    out=_farm_status_public();out["uac_requested"]=uac
    return out

@app.post("/api/worker-farm/disable")
def worker_farm_disable():
    _stop_worker_broker()
    return _farm_status_public()

@app.get("/api/config")
def config():
    s=load_state()
    school_duty=dict(SEED.get("schoolDuty",{}))
    school_duty["locations"]=list(s.get("school_locations",[]))
    school_duty["slots"]=list(dict.fromkeys(b["label"] for b in SEED.get("breaks",[])))
    view={**SEED,"schoolDuty":school_duty,"teachers":[t for t in SEED.get("teachers",[]) if t.get("name") in ALL]}
    eff=_effective_plan_v574(s)
    return {**view,"app_meta":{"version":PLANNER_VERSION,"engine":"OR-Tools CP-SAT","worker_protocol_version":WORKER_PROTOCOL_VERSION,"worker_package_version":WORKER_PACKAGE_VERSION},
            "state":s,"plan_state_source":{"kind":"saved","source_id":"saved:"+str(int(s.get("plan_revision",0) or 0))},
            "effective_plan_source":eff.get("source"),
            "solver_knowledge":_solver_knowledge_public_summary(),
            "variant_meta":[{"id":v["id"],"name":v["name"],"created_at":v["created_at"],"note":v.get("note","")} for v in s.get("variants",[])]}

@app.get("/api/validation")
def validation():
    return validate_state(load_state(),SEED)

@app.post("/api/validation")
def validation_preview(x:dict):
    s=load_state()
    if "global" in x:
        s["global_constraints"]=normalize_constraint_rows(x.get("global",[]))
    if "individual" in x:
        s["individual_constraints"]=normalize_constraint_rows(x.get("individual",[]))
    s,_=_sanitize_inactive_13_state(s)
    if "min_people_13" in x:
        s["min_people_13"]=dict(x.get("min_people_13") or {})
    if "min_people_13_stations" in x:
        s["min_people_13_stations"]=dict(x.get("min_people_13_stations") or {})
    if "min_people_school" in x:
        s["min_people_school"]=dict(x.get("min_people_school") or {})
    if "school_locations" in x:
        s["school_locations"]=list(x.get("school_locations") or [])
    for k in ["teacher_workload","teacher_place_preferences","preference_grid","location_zones","locked_assignments","absent_teachers","excluded_teachers","freeze_pool_13","freeze_pool_school"]:
        if k in x: s[k]=x[k]
    s=ensure_state_schema(s)
    s,_=_sanitize_inactive_13_state(s)
    return validate_state(s,SEED)

@app.get("/api/health")
def health():
    import ortools
    s=load_state()
    return {"ok":True,"version":PLANNER_VERSION,"engine":"OR-Tools CP-SAT","ortools_version":getattr(ortools,"__version__","?"),
            "teachers":len(ALL),"constraints":len(s.get("global_constraints",[])),
            "state_file":str(STATE_PATH),"state_file_exists":STATE_PATH.exists()}

@app.get("/api/settings-profiles")
def settings_profiles():
    raw=_ensure_comfort_profile()
    return {"profiles":[{"id":p.get("id"),"name":p.get("name"),"created_at":p.get("created_at"),
                         "is_default":p.get("id")==raw.get("default_id")} for p in raw.get("profiles",[])],
            "default_id":raw.get("default_id")}

@app.post("/api/settings-profiles")
def save_settings_profile(x:dict):
    name=str(x.get("name") or "").strip()
    if not name: raise HTTPException(400,"Podaj nazwę profilu.")
    raw=_ensure_comfort_profile();state=load_state()
    pid=str(x.get("id") or _uuid.uuid4().hex[:12])
    row=next((p for p in raw["profiles"] if p.get("id")==pid),None)
    payload={"id":pid,"name":name,"created_at":datetime.now().isoformat(timespec="seconds"),
             "settings":_settings_snapshot(state)}
    if row: row.update(payload)
    else: raw["profiles"].append(payload)
    if x.get("make_default"): raw["default_id"]=pid
    _save_settings_profiles(raw)
    return {"ok":True,"id":pid}

@app.post("/api/settings-profiles/{profile_id}/load")
def load_settings_profile(profile_id:str):
    raw=_ensure_comfort_profile()
    p=next((p for p in raw["profiles"] if p.get("id")==profile_id),None)
    if not p: raise HTTPException(404,"Nie ma takiego profilu.")
    s=load_state();before=_copy.deepcopy(s);settings=p.get("settings",{})
    if "global_constraints" in settings: s["global_constraints"]=normalize_constraint_rows(settings["global_constraints"])
    if "individual_constraints" in settings: s["individual_constraints"]=normalize_constraint_rows(settings["individual_constraints"])
    for k in _PROFILE_STATE_KEYS:
        if k in settings and settings[k] is not None: s[k]=_copy.deepcopy(settings[k])
    _save_solver_input_change(before,s,"Wczytano profil ustawień solvera.")
    return {"ok":True,"profile_id":profile_id,"name":p.get("name")}

@app.get("/api/settings-profiles/{profile_id}/export")
def export_settings_profile(profile_id:str):
    raw=_ensure_comfort_profile()
    p=next((p for p in raw["profiles"] if p.get("id")==profile_id),None)
    if not p: raise HTTPException(404,"Nie ma takiego profilu.")
    return {"schema":"demo-duty-solver-profile-v1","planner_version":PLANNER_VERSION,
            "profile":{"name":p.get("name"),"settings":_copy.deepcopy(p.get("settings",{}))}}

@app.post("/api/settings-profiles/import")
def import_settings_profile(x:dict):
    if x.get("schema")!="demo-duty-solver-profile-v1": raise HTTPException(400,"Nieobsługiwany format profilu.")
    p=x.get("profile") or {}; settings=p.get("settings") or {}
    if not isinstance(settings,dict): raise HTTPException(400,"Nieprawidłowe ustawienia profilu.")
    clean={}
    if "global_constraints" in settings: clean["global_constraints"]=normalize_constraint_rows(settings["global_constraints"])
    if "individual_constraints" in settings: clean["individual_constraints"]=normalize_constraint_rows(settings["individual_constraints"])
    for k in _PROFILE_STATE_KEYS:
        if k in settings: clean[k]=_copy.deepcopy(settings[k])
    name=str(p.get("name") or "Profil importowany").strip() or "Profil importowany"
    raw=_ensure_comfort_profile(); pid=_uuid.uuid4().hex[:12]
    raw["profiles"].append({"id":pid,"name":name,"created_at":datetime.now().isoformat(timespec="seconds"),"settings":clean})
    _save_settings_profiles(raw)
    return {"ok":True,"id":pid,"name":name}

@app.post("/api/settings-profiles/{profile_id}/default")
def default_settings_profile(profile_id:str):
    raw=_ensure_comfort_profile()
    if not any(p.get("id")==profile_id for p in raw["profiles"]): raise HTTPException(404,"Nie ma takiego profilu.")
    raw["default_id"]=profile_id;_save_settings_profiles(raw);return {"ok":True}

@app.delete("/api/settings-profiles/{profile_id}")
def delete_settings_profile(profile_id:str):
    raw=_ensure_comfort_profile()
    if profile_id==raw.get("default_id"): raise HTTPException(409,"Nie można usunąć profilu domyślnego.")
    raw["profiles"]=[p for p in raw["profiles"] if p.get("id")!=profile_id]
    _save_settings_profiles(raw);return {"ok":True}

@app.get("/api/constraints")
def constraints():
    s=load_state()
    return {"global":s.get("global_constraints",[]),"individual":s.get("individual_constraints",[])}

@app.post("/api/constraints")
def save_constraints(x:dict):
    s=load_state();before=_copy.deepcopy(s)
    if "global" in x:
        s["global_constraints"]=normalize_constraint_rows(x["global"])
    if "individual" in x:
        s["individual_constraints"]=normalize_constraint_rows(x["individual"])
    s=ensure_state_schema(s)
    s,_=_sanitize_inactive_13_state(s)
    _save_solver_input_change(before,s,"Zmieniono reguły solvera.")
    return {"ok":True,"global":s.get("global_constraints",[]),"individual":s.get("individual_constraints",[])}

@app.post("/api/min-people-13")
def save_min_people_13(x:dict):
    s=ensure_state_schema(load_state());before=_copy.deepcopy(s)
    vals=x.get("min_people_13",{})
    for b in SEED.get("breaks",[]):
        k=f"{b['abbr']}|{b['label']}"
        try: v=int(vals.get(k,len(_required_stations_13(s,b["abbr"],b["label"]))))
        except Exception: v=len(_required_stations_13(s,b["abbr"],b["label"]))
        _set_required_13_count(s,b["abbr"],b["label"],v)
        base=f"{b['abbr']}|{b['label']}"
        mm=s.setdefault("auto_staffing_by_timetable",{"school13":{},"school":{}}).setdefault("school13",{})
        for sid in _stations_13(s): mm.pop(f"{base}|{sid}",None)
    _save_solver_input_change(before,s,"Zmieniono minimalną obsadę 1–3.")
    return {"ok":True,"min_people_13":s.get("min_people_13",{}),"min_people_13_stations":s.get("min_people_13_stations",{})}

@app.post("/api/min-people-13/stations")
def save_min_people_13_stations(x:dict):
    s=ensure_state_schema(load_state());before=_copy.deepcopy(s)
    raw=x.get("staffing") or {}; confirmed=set(str(k) for k in (x.get("confirmed_zero_keys") or []))
    warnings=_staffing_zero_warnings(s,"school13",raw)
    pending=[w for w in warnings if w["key"] not in confirmed]
    if pending: raise HTTPException(409,detail={"requires_confirmation":True,"warnings":pending})
    order=_stations_13(s);clean={}
    overrides=set(s.setdefault("staffing_zero_overrides",{"school13":[],"school":[]}).get("school13",[]) or [])
    for b in SEED.get("breaks",[]):
        base=f"{b['abbr']}|{b['label']}"
        active=_position_zone_active_13(b["abbr"],b["label"])
        for sid in order:
            k=f"{base}|{sid}"
            if not active:
                clean[k]=0
                overrides.discard(k)
                continue
            try: v=int(raw.get(k,s.get("min_people_13_stations",{}).get(k,0)) or 0)
            except Exception: v=0
            clean[k]=1 if v else 0
            if clean[k]: overrides.discard(k)
            elif k in confirmed: overrides.add(k)
    s["staffing_zero_overrides"]["school13"]=sorted(overrides)
    s["min_people_13_stations"]=clean
    s.setdefault("auto_staffing_by_timetable",{"school13":{},"school":{}})["school13"]={}
    counts=_sync_min13_counts_from_stations(s)
    _save_solver_input_change(before,s,"Zmieniono obsadę stanowisk 1–3.")
    return {"ok":True,"min_people_13":counts,"min_people_13_stations":clean}

@app.post("/api/min-people-school")
def save_min_people_school(x:dict):
    s=ensure_state_schema(load_state());before=_copy.deepcopy(s)
    vals=x.get("min_people_school",{}); confirmed=set(str(k) for k in (x.get("confirmed_zero_keys") or []))
    warnings=_staffing_zero_warnings(s,"school",vals)
    pending=[w for w in warnings if w["key"] not in confirmed]
    if pending: raise HTTPException(409,detail={"requires_confirmation":True,"warnings":pending})
    clean={}; overrides=set(s.setdefault("staffing_zero_overrides",{"school13":[],"school":[]}).get("school",[]) or [])
    for b in SEED.get("breaks",[]):
        for loc in s.get("school_locations",[]):
            k=f"{b['abbr']}|{b['label']}|{loc}"
            try: v=int(vals.get(k,0))
            except Exception: v=0
            clean[k]=1 if v else 0
            if clean[k]: overrides.discard(k)
            elif k in confirmed: overrides.add(k)
    s["staffing_zero_overrides"]["school"]=sorted(overrides)
    s["min_people_school"]=clean
    s.setdefault("auto_staffing_by_timetable",{"school13":{},"school":{}})["school"]={}
    _save_solver_input_change(before,s,"Zmieniono minimalną obsadę szkoły.")
    return {"ok":True,"min_people_school":clean}

@app.post("/api/stations-13/add")
def add_station_13(x:dict):
    s=ensure_state_schema(load_state());before=_copy.deepcopy(s)
    name=str(x.get("name") or "").strip()
    if not name: raise HTTPException(400,"Podaj nazwę stanowiska.")
    order=_stations_13(s)
    used=set(order)
    sid=next((chr(c) for c in range(ord("A"),ord("Z")+1) if chr(c) not in used),None)
    if sid is None:
        i=1
        while f"S{i}" in used:i+=1
        sid=f"S{i}"
    order.append(sid);s["station_order_13"]=order;s.setdefault("station_names",{})[sid]=name
    vals=s.setdefault("min_people_13_stations",{})
    for b in SEED.get("breaks",[]): vals[f"{b['abbr']}|{b['label']}|{sid}"]=0
    _sync_min13_counts_from_stations(s)
    _save_solver_input_change(before,s,"Dodano stanowisko 1–3.")
    return {"ok":True,"station_order_13":order,"station_names":s["station_names"],"min_people_13_stations":vals,"min_people_13":s["min_people_13"]}

@app.post("/api/stations-13/{station_id}/rename")
def rename_station_13(station_id:str,x:dict):
    s=ensure_state_schema(load_state());sid=str(station_id)
    if sid not in _stations_13(s): raise HTTPException(404,"Nie ma takiego stanowiska.")
    name=str(x.get("name") or "").strip()
    if not name: raise HTTPException(400,"Podaj nazwę stanowiska.")
    s.setdefault("station_names",{})[sid]=name;save_state(s)
    return {"ok":True,"station_order_13":_stations_13(s),"station_names":s["station_names"]}

@app.post("/api/stations-13/{station_id}/remove")
def remove_station_13(station_id:str):
    s=ensure_state_schema(load_state());before=_copy.deepcopy(s);sid=str(station_id);order=_stations_13(s)
    if sid not in order: raise HTTPException(404,"Nie ma takiego stanowiska.")
    if len(order)<=1: raise HTTPException(409,"Musi pozostać co najmniej jedno stanowisko 1–3.")
    order=[x for x in order if x!=sid];s["station_order_13"]=order
    s.setdefault("station_names",{}).pop(sid,None)
    s["min_people_13_stations"]={k:v for k,v in s.get("min_people_13_stations",{}).items() if not k.endswith("|"+sid)}
    # Remove current assignments and hard locks referring to the deleted station.
    for row in s.get("last_13_assignments",[]) or []:
        row["assignments"]=[a for a in row.get("assignments",[]) if str(a.get("station"))!=sid]
    s["locked_assignments"]=[r for r in s.get("locked_assignments",[]) if not(r.get("scope")=="1–3" and str(r.get("location"))==sid)]
    zones=dict(s.get("location_zones",{}) or {})
    for prefix in ("1–3","1-3"):
        zones.pop(f"{prefix}|{sid}",None)
    s["location_zones"]=zones
    _sync_min13_counts_from_stations(s)
    _save_solver_input_change(before,s,"Usunięto stanowisko 1–3.")
    return {"ok":True,"station_order_13":order,"station_names":s["station_names"],"min_people_13_stations":s["min_people_13_stations"],"min_people_13":s["min_people_13"]}

@app.post("/api/teacher-place-preferences")
def save_teacher_place_preferences(x:dict):
    s=ensure_state_schema(load_state()); before=_copy.deepcopy(s)
    raw=x.get("teacher_place_preferences",{})
    if not isinstance(raw,dict): raise HTTPException(400,"teacher_place_preferences musi być obiektem.")
    s["teacher_place_preferences"]=_copy.deepcopy(raw)
    s=ensure_state_schema(s)
    _save_solver_input_change(before,s,"Zmieniono preferencje nauczyciel × miejsce dyżuru.")
    return {"ok":True,"teacher_place_preferences":s["teacher_place_preferences"],
            "levels":s.get("teacher_place_preference_levels",[0,0.25,0.5,0.75,1])}

@app.post("/api/group-place-defaults")
def save_group_place_defaults(x:dict):
    s=ensure_state_schema(load_state()); before=_copy.deepcopy(s)
    raw=x.get("group_place_defaults",{})
    if not isinstance(raw,dict): raise HTTPException(400,"group_place_defaults musi być obiektem.")
    valid={p["key"]:p for p in s.get("duty_places",[])}
    out={}
    for g in ("1-3","school","wf"):
        vals=raw.get(g,[])
        if not isinstance(vals,list): vals=[]
        clean=[]
        for key in vals:
            key=str(key)
            p=valid.get(key)
            if not p: continue
            if key not in clean: clean.append(key)
        out[g]=clean
    s["group_place_defaults"]=out
    if bool(x.get("apply_to_group",False)):
        prefs=_copy.deepcopy(s.get("teacher_place_preferences",{}))
        for name in ALL:
            g=GROUP.get(name,"school")
            row=dict(prefs.get(name,{}) or {})
            allowed=set(out.get(g,[]))
            for p in s.get("duty_places",[]):
                key=p["key"]
                row[key]=1.0 if key in allowed else 0.0
            prefs[name]=row
        s["teacher_place_preferences"]=prefs
    s=ensure_state_schema(s)
    _save_solver_input_change(before,s,"Zmieniono startowo dopuszczone miejsca dyżurów dla kategorii nauczycieli.")
    return {"ok":True,"group_place_defaults":s["group_place_defaults"],
            "teacher_place_preferences":s["teacher_place_preferences"]}

@app.post("/api/school-locations")
def save_school_locations(x:dict):
    s=load_state();before=_copy.deepcopy(s)
    raw=x.get("locations",[])
    if not isinstance(raw,list): raise HTTPException(400,"locations musi być listą")
    locs=[]
    for value in raw:
        loc=str(value or "").strip()
        if not loc: continue
        if "|" in loc: raise HTTPException(400,"Nazwa miejsca nie może zawierać znaku |")
        if loc not in locs: locs.append(loc)
    if not locs: raise HTTPException(400,"Musi pozostać co najmniej jedno miejsce dyżuru.")
    removed=set(s.get("school_locations",[]))-set(locs)
    refs=[]
    for r in s.get("individual_constraints",[]):
        if r.get("enabled",True) and r.get("location") in removed and r.get("scope","oba") in ("oba","szkoła"):
            refs.append(f"reguła {r.get('teacher','?')}: {r.get('location')}")
    for r in s.get("locked_assignments",[]):
        if r.get("scope")=="szkoła" and r.get("location") in removed:
            refs.append(f"zamrożony dyżur {r.get('abbr')} {r.get('slot')}: {r.get('location')}")
    if refs:
        raise HTTPException(409,"Miejsce jest używane przez reguły/blokady: "+"; ".join(refs[:8]))
    s["school_locations"]=locs
    s["school_assignments"]=[d for d in s.get("school_assignments",[]) if d.get("location") in locs]
    # ensure_state_schema zachowa istniejące wartości i dopisze 0 dla nowych miejsc.
    _save_solver_input_change(before,s,"Zmieniono listę miejsc dyżuru szkoły.")
    s=load_state()
    return {"ok":True,"locations":s["school_locations"],"min_people_school":s["min_people_school"]}

@app.post("/api/school-locations/rename")
def rename_school_location(x:dict):
    s=load_state();before=_copy.deepcopy(s)
    old=str(x.get("old") or "").strip(); new=str(x.get("new") or "").strip()
    if not old or not new: raise HTTPException(400,"Podaj starą i nową nazwę.")
    if "|" in new: raise HTTPException(400,"Nazwa miejsca nie może zawierać znaku |")
    locs=list(s.get("school_locations",[]))
    if old not in locs: raise HTTPException(404,"Nie znaleziono miejsca do zmiany.")
    if new in locs and new!=old: raise HTTPException(409,"Miejsce o tej nazwie już istnieje.")
    locs=[new if z==old else z for z in locs]
    s["school_locations"]=locs

    # Preserve staffing values.
    mp={}
    for k,v in (s.get("min_people_school",{}) or {}).items():
        try:
            ab,slot,loc=str(k).split("|",2)
            if loc==old: loc=new
            mp[f"{ab}|{slot}|{loc}"]=v
        except Exception:
            mp[k]=v
    s["min_people_school"]=mp

    # Preserve current assignments, admin locks and location-scoped individual rules.
    for d in s.get("school_assignments",[]) or []:
        if d.get("location")==old: d["location"]=new
    for d in s.get("locked_assignments",[]) or []:
        if d.get("scope")=="szkoła" and d.get("location")==old: d["location"]=new
    for d in s.get("individual_constraints",[]) or []:
        if d.get("location")==old and d.get("scope","oba") in ("oba","szkoła"): d["location"]=new

    duty_zones=dict(s.get("duty_location_zones",{}) or {})
    if old in duty_zones: duty_zones[new]=duty_zones.pop(old)
    s["duty_location_zones"]=duty_zones
    prefs=dict(s.get("teacher_place_preferences",{}) or {})
    for teacher,row in prefs.items():
        if isinstance(row,dict) and f"school|{old}" in row:
            row[f"school|{new}"]=row.pop(f"school|{old}")
    s["teacher_place_preferences"]=prefs

    zones=dict(s.get("location_zones",{}) or {})
    for prefix in ("szkoła","school"):
        ok=f"{prefix}|{old}"; nk=f"{prefix}|{new}"
        if ok in zones:
            zones[nk]=zones.pop(ok)
    s["location_zones"]=zones
    _save_solver_input_change(before,s,"Zmieniono nazwę miejsca dyżuru szkoły.")
    s=load_state()
    return {"ok":True,"locations":s.get("school_locations",[]),"min_people_school":s.get("min_people_school",{})}

@app.post("/api/state")
def update_state(x:dict):
    s=load_state();before=_copy.deepcopy(s)
    for k in ["enabled_teachers_13","enabled_teachers_school","manual_blocks","station_names","school_assignments","last_13_assignments",
              "school_locations","min_people_school","teacher_workload","teacher_place_preferences","preference_grid","preference_comments","manual_block_comments","location_zones","duty_location_zones","locked_assignments","absent_teachers","excluded_teachers","freeze_pool_13","freeze_pool_school","solver_seed","deterministic_mode","auto_tune_capacity","solver_internal_workers","solver_coverage_seconds","solver_coverage_retry_seconds"]:
        if k in x: s[k]=x[k]
    s["enabled_teachers_school"]=_school_pool(s.get("enabled_teachers_school",[]))
    changed=_save_solver_input_change(before,s,"Zmieniono stan wejściowy solvera.")
    return {"ok":True,"solver_input_changed":changed}

@app.post("/api/publish")
def publish_plan(x:dict=None):
    s=load_state()
    snap={"published_at":datetime.now().isoformat(timespec="seconds"),
          "school_assignments":s.get("school_assignments",[]),
          "assignments_13":s.get("last_13_assignments",[])}
    s["published_snapshot"]=snap; save_state(s)
    return {"ok":True,**snap}

@app.post("/api/operations/save")
def save_operational_plan(x:dict):
    s=load_state();before=_copy.deepcopy(s)
    rec={"created_at":datetime.now().isoformat(timespec="seconds"),
         "absent_teachers":list(x.get("absent_teachers",[])),
         "assignments_13":list(x.get("assignments_13",[])),
         "school_assignments":list(x.get("school_assignments",[])),
         "stability":x.get("stability",{})}
    s["operational_plan"]=rec
    s["absent_teachers"]=rec["absent_teachers"]
    s.setdefault("substitution_history",[]).append(rec)
    s["substitution_history"]=s["substitution_history"][-100:]
    changed=_save_solver_input_change(before,s,"Zmieniono listę nieobecnych nauczycieli w planie operacyjnym.")
    return {"ok":True,"created_at":rec["created_at"],"solver_input_changed":changed}


def _all_current_duties(state):
    out=[]
    for row in state.get("last_13_assignments",[]) or []:
        for a in row.get("assignments",[]) or []:
            if a.get("teacher"):
                out.append({"scope":"1–3","day":row.get("day"),"abbr":row.get("abbr"),"slot":row.get("label"),
                            "location":a.get("station"),"teacher":a.get("teacher")})
    for d in state.get("school_assignments",[]) or []:
        if d.get("teacher"):
            out.append({"scope":"szkoła","day":d.get("day"),"abbr":d.get("abbr"),"slot":d.get("slot"),
                        "location":d.get("location"),"teacher":d.get("teacher")})
    return out

def _same_duty(a,b):
    return (str(a.get("scope"))==str(b.get("scope")) and str(a.get("abbr"))==str(b.get("abbr"))
            and str(a.get("slot"))==str(b.get("slot")) and str(a.get("location") or "")==str(b.get("location") or ""))

def _plan_event(state,kind,summary,changes=None):
    rev=int(state.get("plan_revision",0) or 0)+1
    state["plan_revision"]=rev
    event={"revision":rev,"kind":kind,"at":datetime.now().isoformat(timespec="seconds"),"summary":summary}
    if changes is not None: event["changes"]=_copy.deepcopy(changes)
    state.setdefault("plan_events",[]).append(event)
    state["plan_events"]=state["plan_events"][-300:]
    return event

def _teacher_slot_duties(state,name,abbr):
    out=[]
    for d in _all_current_duties(state):
        if d.get("teacher")==name and d.get("abbr")==abbr:
            out.append(d)
    return out

def _consecutive_after_add(state,name,abbr,slot,remove_targets):
    slots=[b["label"] for b in SEED.get("breaks",[]) if b.get("abbr")==abbr]
    order={x:i for i,x in enumerate(dict.fromkeys(slots))}
    have=set()
    for d in _teacher_slot_duties(state,name,abbr):
        if any(_same_duty(d,t) for t in remove_targets): continue
        if d.get("slot") in order: have.add(order[d["slot"]])
    if slot in order: have.add(order[slot])
    best=cur=0;prev=None
    for i in sorted(have):
        cur=cur+1 if prev is not None and i==prev+1 else 1
        best=max(best,cur);prev=i
    return best

def _local_candidate(state,source_teacher,target,candidate,remove_targets):
    cs=cdict(state); reasons=[]; notes=[]; score=0
    scope=target["scope"]; ab=target["abbr"]; sl=target["slot"]; loc=target.get("location")
    br=break_map().get((ab,sl))
    if not br: return None,["brak definicji przerwy"]
    if candidate==source_teacher:return None,["ten sam nauczyciel"]
    if candidate in set(state.get("excluded_teachers",[])):return None,["wykluczony ze wszystkich dyżurów"]
    if candidate in set(state.get("absent_teachers",[])):return None,["nieobecny"]
    if f"{ab}|{sl}" in blockset(state,candidate):return None,["blokada administratora dla tego slotu"]

    # No teacher may be in two duties at the same time. Selected source duties are removed for this check.
    for d in _all_current_duties(state):
        if any(_same_duty(d,t) for t in remove_targets):continue
        if d.get("teacher")==candidate and d.get("abbr")==ab and d.get("slot")==sl:
            return None,["ma już dyżur w tym samym slocie"]

    if duty_overlaps_lesson(candidate,br):return None,["kolizja z lekcją"]

    ih,_md,_mw,ic=individual_effect(state,candidate,scope,ab,sl,loc)
    # max_day/max_week are intentionally ignored; direct individual block is not.
    if ih:return None,["indywidualna reguła wyklucza ten slot"]
    score+=max(0,int(ic or 0))

    opening=is_opening_break(br)
    if opening and not opening_break_teacher_allowed(candidate,br):
        return None,["slot 0/1 — nauczyciel nie ma lekcji na 1. godzinie"]
    rel=lesson_relation(candidate,br)
    dh,dc=directional_individual_effect(state,candidate,scope,rel)
    if dh:return None,["indywidualna reguła kierunkowa"]
    score+=max(0,int(dc or 0))

    ps=sorted(lesson_periods(candidate,ab))
    minutes=int(br.get("minutes",0) or 0)
    short=minutes<=SHORT_BREAK_MAX_MINUTES
    before_first=bool((not opening) and ps and br.get("next") in ps and int(br.get("next"))==min(ps))
    after_last=is_after_last_lesson(candidate,br)
    relaxed=set((state.get("teacher_relaxed_rules",{}) or {}).get(candidate,[]) or [])

    def rule_cost(key,label,cost):
        nonlocal score
        hard,pen=global_rule_effect(cs,key,1,cost)
        if hard and key not in relaxed:
            reasons.append(label);return False
        if key not in relaxed and pen:
            score+=max(cost,int(pen));notes.append(label)
        return True

    if before_first:
        key="before_first_short" if short else "before_first_long"
        rule_cost(key,"przed pierwszą lekcją",500 if short else 3000)
    if after_last:
        key="after_last_short" if short else "after_last_long"
        rule_cost(key,"po ostatniej lekcji",500 if short else 3500)

    wait=wait_periods(candidate,br)
    if not ps:
        hard,pen=global_rule_effect(cs,"offday_duty",1,8000)
        if hard:return None,["dzień bez lekcji"]
        score+=max(8000,int(pen or 0));notes.append("przyjazd tylko na dyżur")
    elif wait>=2:
        return None,["oczekiwanie co najmniej 2 okresy"]
    elif wait>0:
        if not rule_cost("avoid_wait","dodatkowe oczekiwanie",4500):pass

    if reasons:return None,reasons

    if opening:
        existing=0
        for d in _all_current_duties(state):
            if any(_same_duty(d,t) for t in remove_targets): continue
            if d.get("teacher")==candidate:
                b0=break_map().get((d.get("abbr"),d.get("slot")))
                if b0 and is_opening_break(b0): existing+=1
        if existing:
            score+=700*existing
            notes.append(f"ma już {existing} dyżur(y) w slocie 0/1")

    # Maximum consecutive duties remains a comfort/safety rule in local replacement.
    row=_global_row(state,"max_consecutive_duties")
    if row.get("enabled"):
        try:limit=max(1,int(row.get("value") or 1))
        except Exception:limit=1
        consec=_consecutive_after_add(state,candidate,ab,sl,remove_targets)
        if consec>limit:
            if normalize_kind(row.get("kind"))=="hard":return None,[f"{consec} dyżury z rzędu (limit {limit})"]
            score+=4000*(consec-limit);notes.append(f"{consec} dyżury z rzędu")
    else: consec=_consecutive_after_add(state,candidate,ab,sl,remove_targets)

    # Long-break volume constraints remain relevant; generic day/week load and fairness do not.
    is_long=minutes>=LONG_BREAK_MINUTES
    if is_long:
        for key,period in (("max_long_day","day"),("max_long_week","week")):
            row=_global_row(state,key)
            if not row.get("enabled"):continue
            try:limit=max(0,int(row.get("value") or 0))
            except Exception:continue
            count=0
            for d in _all_current_duties(state):
                if any(_same_duty(d,t) for t in remove_targets):continue
                if d.get("teacher")!=candidate:continue
                if period=="day" and d.get("abbr")!=ab:continue
                bb=break_map().get((d.get("abbr"),d.get("slot")))
                if bb and int(bb.get("minutes",0) or 0)>=LONG_BREAK_MINUTES:count+=1
            count+=1
            if count>limit:
                if normalize_kind(row.get("kind"))=="hard":return None,[f"przekracza {row.get('label',key)}"]
                score+=1800*(count-limit);notes.append(f"{row.get('label',key)}: {count}")

    # Teacher preference is comfort, not an administrator lock.
    pref=str((state.get("preference_grid",{}).get(candidate,{}) or {}).get(f"{ab}|{sl}","neutral")).lower()
    if pref=="avoid":
        score+=1800;notes.append("nauczyciel oznaczył slot jako niepożądany")
    elif pref=="prefer":
        score=max(0,score-300);notes.append("slot preferowany przez nauczyciela")

    home=(GROUP.get(candidate)=="1-3") if scope=="1–3" else (GROUP.get(candidate)=="school")
    if not home:
        row=_global_row(state,"prefer_home_group")
        if row.get("enabled") and normalize_kind(row.get("kind"))=="hard" and "prefer_home_group" not in relaxed:
            return None,["poza podstawową grupą dyżurów"]
        score+=700;notes.append("poza podstawową grupą dyżurów")

    pool=set(state.get("enabled_teachers_13",[]) if scope=="1–3" else _school_pool(state.get("enabled_teachers_school",[])))
    if candidate not in pool:
        score+=900;notes.append("poza bieżącą pulą — kandydat awaryjny")

    return {"teacher":candidate,"score":int(score),"wait":wait,"consecutive":consec,
            "notes":notes,"group":GROUP.get(candidate,"school"),"in_pool":candidate in pool},[]

def _local_teacher_repair_preview(state,teacher,selected,limit=5):
    state=ensure_state_schema(_copy.deepcopy(state))
    if teacher not in ALL:return {"ok":False,"reason":"Nieznany nauczyciel."}
    current=_all_current_duties(state);targets=[]
    for q in selected:
        scope="1–3" if str(q.get("scope")) in ("1–3","1-3","school13") else "szkoła"
        probe={"scope":scope,"abbr":q.get("abbr"),"slot":q.get("slot"),"location":q.get("location")}
        hit=next((d for d in current if d.get("teacher")==teacher and _same_duty(d,probe)),None)
        if hit and not any(_same_duty(hit,z) for z in targets):targets.append(hit)
    if not targets:return {"ok":False,"reason":"Nie zaznaczono aktualnego dyżuru tego nauczyciela."}
    for t in targets:
        locked=locked_teacher(state,t["scope"],t["abbr"],t["slot"],t.get("location"))
        if locked:return {"ok":False,"locked":True,"reason":"Ten dyżur jest stałym przydziałem administratora. Najpierw ręcznie zwolnij stały przydział.","duty":t}

    result=[]
    for t in targets:
        candidates=[];rejected=Counter()
        for n in ALL:
            cand,bad=_local_candidate(state,teacher,t,n,targets)
            if cand:candidates.append(cand)
            else:
                for why in bad or []:rejected[why]+=1
        candidates.sort(key=lambda x:(x["score"],0 if x["in_pool"] else 1,_teacher_sort_key(x["teacher"])))
        result.append({"duty":t,"candidates":candidates[:max(1,int(limit or 5))],
                       "legal_count":len(candidates),
                       "rejected":[{"reason":k,"count":v} for k,v in rejected.most_common(8)]})
    needs_full=any(not x["candidates"] for x in result)
    return {"ok":True,"teacher":teacher,"targets":result,"needs_full_recalc":needs_full,
            "policy":"Ignorowane: max_day, max_week, balance/fairness i ręczne wagi obciążenia. Zachowane: kolizje, blokady administratora, oczekiwanie >=2, krawędzie dnia i kolejne dyżury."}

@app.post("/api/teacher-duty/local-repair/preview")
def teacher_duty_local_repair_preview(x:dict):
    out=_local_teacher_repair_preview(load_state(),str(x.get("teacher") or ""),list(x.get("duties") or []),int(x.get("limit") or 5))
    if not out.get("ok"):raise HTTPException(409 if out.get("locked") else 400,detail=out)
    return out

@app.post("/api/teacher-duty/local-repair/apply")
def teacher_duty_local_repair_apply(x:dict):
    teacher=str(x.get("teacher") or "");choices=list(x.get("choices") or [])
    s=ensure_state_schema(load_state())
    if teacher not in ALL:raise HTTPException(400,"Nieznany nauczyciel.")
    selected=[c.get("duty") or {} for c in choices]
    preview=_local_teacher_repair_preview(s,teacher,selected,limit=max(20,len(ALL)))
    if not preview.get("ok"):raise HTTPException(409,detail=preview)
    bykey={}
    for row in preview.get("targets",[]):
        d=row["duty"];key=(d["scope"],d["abbr"],d["slot"],str(d.get("location") or ""))
        bykey[key]={c["teacher"]:c for c in row.get("candidates",[])}
    changes=[]
    for c in choices:
        d=c.get("duty") or {};new=str(c.get("teacher") or "")
        scope="1–3" if str(d.get("scope")) in ("1–3","1-3","school13") else "szkoła"
        key=(scope,d.get("abbr"),d.get("slot"),str(d.get("location") or ""))
        if new not in bykey.get(key,{}):raise HTTPException(409,f"{new}: kandydat nie jest już legalny dla {key}.")
        changes.append({"scope":scope,"abbr":d.get("abbr"),"slot":d.get("slot"),"location":d.get("location"),
                        "old_teacher":teacher,"new_teacher":new,"candidate":bykey[key][new]})
    # prevent one replacement teacher being in two places in same slot within this batch
    seen=set()
    for ch in changes:
        k=(ch["new_teacher"],ch["abbr"],ch["slot"])
        if k in seen:raise HTTPException(409,f'{ch["new_teacher"]}: dwie podmiany w tym samym slocie.')
        seen.add(k)

    for ch in changes:
        if ch["scope"]=="1–3":
            for row in s.get("last_13_assignments",[]) or []:
                if row.get("abbr")==ch["abbr"] and row.get("label")==ch["slot"]:
                    for a in row.get("assignments",[]) or []:
                        if str(a.get("station"))==str(ch.get("location")) and a.get("teacher")==teacher:
                            a["teacher"]=ch["new_teacher"];a["wait"]=ch["candidate"].get("wait",0)
        else:
            for d in s.get("school_assignments",[]) or []:
                if d.get("abbr")==ch["abbr"] and d.get("slot")==ch["slot"] and str(d.get("location"))==str(ch.get("location")) and d.get("teacher")==teacher:
                    d["teacher"]=ch["new_teacher"]

        # Persist outgoing hard block.
        key=f'{ch["abbr"]}|{ch["slot"]}'
        vals=s.setdefault("manual_blocks",{}).setdefault(teacher,[])
        if key not in vals:vals.append(key)

        # Persist accepted replacement as immutable administrator assignment.
        s["locked_assignments"]=[r for r in s.get("locked_assignments",[]) if not(
            r.get("scope")==ch["scope"] and r.get("abbr")==ch["abbr"] and r.get("slot")==ch["slot"]
            and str(r.get("location") or "")==str(ch.get("location") or ""))]
        override_id=_uuid.uuid4().hex[:12]
        s["locked_assignments"].append({"scope":ch["scope"],"abbr":ch["abbr"],"slot":ch["slot"],
            "location":ch.get("location") or "","teacher":ch["new_teacher"],"source":"local_repair","override_id":override_id})
        s.setdefault("local_repair_overrides",[]).append({
            "id":override_id,"active":True,"scope":ch["scope"],"abbr":ch["abbr"],"slot":ch["slot"],"location":ch.get("location") or "",
            "source_teacher":teacher,"replacement_teacher":ch["new_teacher"],"reason":"lokalna podmiana po odmowie / blokadzie slotu",
            "candidate_score":ch["candidate"].get("score"),"candidate_notes":ch["candidate"].get("notes",[]),
            "created_at":datetime.now().isoformat(timespec="seconds"),"base_revision":int(s.get("plan_revision",0) or 0)
        })
    ev=_plan_event(s,"local_repair",f"Lokalna korekta: {teacher} — {len(changes)} dyżur(y)",changes)
    save_state(s)
    _invalidate_active_repair_jobs("Zastosowano lokalną korektę planu.")
    return {"ok":True,"revision":ev["revision"],"changes":changes,"overrides":[r for r in s.get("local_repair_overrides",[]) if r.get("active")]}

def _manual_position_teacher(state,scope,abbr,slot,location):
    if scope=="1-3":
        row=next((r for r in state.get("last_13_assignments",[]) if r.get("abbr")==abbr and r.get("label")==slot),None)
        if not row:return ""
        rec=next((a for a in row.get("assignments",[]) if str(a.get("station") or "")==str(location or "")),None)
        return (rec or {}).get("teacher") or ""
    rec=next((d for d in state.get("school_assignments",[]) if d.get("abbr")==abbr and d.get("slot")==slot and str(d.get("location") or "")==str(location or "")),None)
    return (rec or {}).get("teacher") or ""

def _manual_remove_assignment(state,scope,abbr,slot,location,teacher):
    removed=False
    if scope=="1-3":
        for row in state.get("last_13_assignments",[]) or []:
            if row.get("abbr")==abbr and row.get("label")==slot:
                for a in row.get("assignments",[]) or []:
                    if str(a.get("station") or "")==str(location or "") and (not teacher or a.get("teacher")==teacher):
                        if a.get("teacher"):removed=True
                        a["teacher"]="";a["wait"]=0
    else:
        for d in state.get("school_assignments",[]) or []:
            if d.get("abbr")==abbr and d.get("slot")==slot and str(d.get("location") or "")==str(location or "") and (not teacher or d.get("teacher")==teacher):
                if d.get("teacher"):removed=True
                d["teacher"]="";d["wait"]=0
    return removed

def _manual_add_assignment(state,scope,abbr,slot,location,teacher):
    br=break_map().get((abbr,slot))
    if not br:raise HTTPException(400,"Nieznana przerwa.")
    if teacher not in ALL:raise HTTPException(400,"Nieznany nauczyciel.")
    if teacher in set(state.get("excluded_teachers",[])) or teacher in set(state.get("absent_teachers",[])):
        raise HTTPException(400,"Ten nauczyciel jest wykluczony lub nieobecny.")
    if duty_overlaps_lesson(teacher,br):
        raise HTTPException(400,"Nauczyciel ma w tym czasie lekcję.")
    for d in _all_current_duties(state):
        if d.get("teacher")==teacher and d.get("abbr")==abbr and d.get("slot")==slot:
            raise HTTPException(400,"Nauczyciel ma już dyżur w tym samym czasie.")
    occupied=_manual_position_teacher(state,scope,abbr,slot,location)
    if occupied and occupied!=teacher:
        raise HTTPException(400,f"To miejsce jest już obsadzone przez: {occupied}.")
    if scope=="1-3":
        row=next((r for r in state.get("last_13_assignments",[]) if r.get("abbr")==abbr and r.get("label")==slot),None)
        if row is None:
            row={"day":br.get("day"),"abbr":abbr,"label":slot,"time":br.get("time"),"assignments":[]}
            state.setdefault("last_13_assignments",[]).append(row)
        rec=next((a for a in row.get("assignments",[]) if str(a.get("station") or "")==str(location or "")),None)
        if rec is None:
            rec={"station":location,"teacher":teacher,"wait":0};row.setdefault("assignments",[]).append(rec)
        else:rec["teacher"]=teacher;rec["wait"]=0
    else:
        rec=next((d for d in state.get("school_assignments",[]) if d.get("abbr")==abbr and d.get("slot")==slot and str(d.get("location") or "")==str(location or "")),None)
        if rec is None:
            state.setdefault("school_assignments",[]).append({"day":br.get("day"),"abbr":abbr,"slot":slot,"location":location,"teacher":teacher,"wait":0})
        else:rec["teacher"]=teacher;rec["wait"]=0

@app.post("/api/plan/manual-cell")
def manual_plan_cell(x:dict):
    s=ensure_state_schema(load_state())
    actor=str(x.get("actor") or "teacher")
    operation=str(x.get("operation") or "")
    teacher=str(x.get("teacher") or "")
    comment=str(x.get("comment") or "").strip()
    scope="1-3" if str(x.get("scope")) in ("1-3","1–3","school13") else "szkoła"
    abbr=str(x.get("abbr") or "");slot=str(x.get("slot") or "");location=str(x.get("location") or "")
    if not teacher or not abbr or not slot:raise HTTPException(400,"Brakuje nauczyciela, dnia lub slotu.")
    key=f"{abbr}|{slot}"
    if operation in ("add","prefer"):
        if actor!="admin":
            prefs=s.setdefault("preference_grid",{}).setdefault(teacher,{})
            prefs[key]="prefer"
        if operation=="add":
            if not location:raise HTTPException(400,"Wybierz konkretne brakujące miejsce dyżuru.")
            _manual_add_assignment(s,scope,abbr,slot,location,teacher)
            if actor=="admin":
                s["locked_assignments"]=[r for r in s.get("locked_assignments",[]) if not(r.get("scope")==scope and r.get("abbr")==abbr and r.get("slot")==slot and str(r.get("location") or "")==location)]
                s["locked_assignments"].append({"scope":scope,"abbr":abbr,"slot":slot,"location":location,"teacher":teacher,"source":"manual_cell","comment":comment})
        summary=("Stały przydział administratora" if actor=="admin" else "Preferowany/przyjęty dyżur nauczyciela")
    elif operation=="remove":
        if not location:raise HTTPException(400,"Brakuje miejsca usuwanego dyżuru.")
        _manual_remove_assignment(s,scope,abbr,slot,location,teacher)
        s["locked_assignments"]=[r for r in s.get("locked_assignments",[]) if not(r.get("scope")==scope and r.get("abbr")==abbr and r.get("slot")==slot and str(r.get("location") or "")==location and r.get("teacher")==teacher)]
        if actor=="admin":
            vals=s.setdefault("manual_blocks",{}).setdefault(teacher,[])
            if key not in vals:vals.append(key)
            summary="Administrator usunął dyżur i zablokował ten slot nauczycielowi"
        else:
            s.setdefault("preference_grid",{}).setdefault(teacher,{})[key]="avoid"
            summary="Nauczyciel odrzucił dyżur; zapisano preferencję „niepożądany”"
    else:
        raise HTTPException(400,"Nieznana operacja.")
    ev=_plan_event(s,"manual_cell",summary,[{"actor":actor,"operation":operation,"teacher":teacher,"scope":scope,"abbr":abbr,"slot":slot,"location":location,"comment":comment}])
    save_state(s)
    with REPAIR_JOB_LOCK:
        for _j in REPAIR_JOBS.values():
            if _j.get("status") in ("queued","running","paused") and not _j.get("_cancel"):
                _j["status"]="paused";_j["auto_paused"]=False;_j["stale_due_to_manual_edit"]=True
                _j["stage"]="Wstrzymane po ręcznej zmianie planu"
                _j["message"]="Plan został ręcznie zmieniony. Ten przebieg zachowano do podglądu, ale nie można go wznowić; uruchom nowe przeliczenie."
    return {"ok":True,"revision":ev["revision"],"summary":summary,
            "manual_blocks":s.get("manual_blocks",{}),"preference_grid":s.get("preference_grid",{}),
            "locked_assignments":s.get("locked_assignments",[]),
            "assignments_13":s.get("last_13_assignments",[]),"school_assignments":s.get("school_assignments",[])}

@app.post("/api/plan/commit-solver")
def commit_solver_plan(x:dict):
    s=ensure_state_schema(load_state());before=_copy.deepcopy(s)
    a13=list(x.get("assignments_13") or [])
    school=list(x.get("school_assignments") or [])
    if not a13 or not school:
        raise HTTPException(400,"Do zatwierdzenia wersji solvera potrzebny jest plan 1\u20133 i ca\u0142ej szko\u0142y.")
    flat13=[]
    for row in a13:
        for aa in row.get("assignments",[]) or []:
            flat13.append({"day":row.get("day"),"abbr":row.get("abbr"),"slot":row.get("label"),
                           "station":aa.get("station"),"teacher":aa.get("teacher") or "",
                           "wait":aa.get("wait",0),"wait_kind":aa.get("wait_kind","")})
    audit=_plan_snapshot_audit_v577(flat13,school,s)
    if not audit.get("ok"):
        raise HTTPException(409,detail={"message":"Nie mo\u017cna zatwierdzi\u0107 planu bez realnej pe\u0142nej obsady.","audit":audit})
    s["last_13_assignments"]=_copy.deepcopy(a13)
    s["school_assignments"]=_copy.deepcopy(school)
    ev=_plan_event(s,"solver_commit",
        f"Zatwierdzono wynik pe\u0142nego solvera: {audit['filled13_real']} pozycji 1\u20133, {audit['filledSchool_real']} pozycji szko\u0142y.",
        [{"source":"solver","audit":audit}])
    _save_solver_input_change(before,s,"Zatwierdzono nowy plan solvera.")
    _persist_last_good_plan_v577(flat13,school,
        {"kind":"saved_verified","source_id":"saved:"+str(ev["revision"]),"plan_revision":ev["revision"]},
        load_state(),{"committed_by_user":True},force=True)
    return {"ok":True,"revision":ev["revision"],"event":ev,"audit":audit}

@app.get("/api/plan/provenance")
def plan_provenance():
    s=ensure_state_schema(load_state())
    active=[r for r in s.get("local_repair_overrides",[]) if r.get("active")]
    return {"revision":int(s.get("plan_revision",0) or 0),"active_overrides":active,
            "recent_events":list(reversed(s.get("plan_events",[])[-30:]))}

@app.post("/api/plan/provenance/{override_id}/release")
def release_local_override(override_id:str):
    s=ensure_state_schema(load_state())
    rec=next((r for r in s.get("local_repair_overrides",[]) if r.get("id")==override_id and r.get("active")),None)
    if not rec: raise HTTPException(404,"Nie znaleziono aktywnej korekty.")
    rec["active"]=False;rec["released_at"]=datetime.now().isoformat(timespec="seconds")
    # Remove only the fixed assignment created by this exact override.
    s["locked_assignments"]=[r for r in s.get("locked_assignments",[]) if str(r.get("override_id") or "")!=override_id]
    # Remove outgoing slot block only if no other active local override still depends on it.
    still=any(r.get("active") and r.get("id")!=override_id and r.get("source_teacher")==rec.get("source_teacher")
              and r.get("abbr")==rec.get("abbr") and r.get("slot")==rec.get("slot")
              for r in s.get("local_repair_overrides",[]))
    if not still:
        vals=s.setdefault("manual_blocks",{}).get(rec.get("source_teacher"),[])
        key=f'{rec.get("abbr")}|{rec.get("slot")}'
        s["manual_blocks"][rec.get("source_teacher")]=[x for x in vals if x!=key]
    ev=_plan_event(s,"local_repair_release",f"Zwolniono lokalną korektę {override_id}",[rec])
    save_state(s)
    _invalidate_active_repair_jobs("Zwolniono lokalną korektę planu.")
    return {"ok":True,"revision":ev["revision"]}

@app.get("/api/teacher-recalc-requests")
def teacher_recalc_requests():
    s=load_state()
    rows=[r for r in s.get("teacher_recalc_requests",[]) if r.get("status","pending")=="pending"]
    rows.sort(key=lambda r:r.get("created_at",""))
    return {"pending":rows,"count":len(rows)}

@app.post("/api/teacher-recalc-requests/{request_id}/dismiss")
def teacher_recalc_request_dismiss(request_id:str):
    s=load_state();found=False
    for r in s.get("teacher_recalc_requests",[]):
        if r.get("id")==request_id:
            r["status"]="dismissed";r["resolved_at"]=datetime.now().isoformat(timespec="seconds");found=True
    if not found: raise HTTPException(404,"Nie ma takiej prośby.")
    save_state(s);return {"ok":True}

@app.post("/api/solve/13")
def solve13(x:dict):
    s=load_state()
    _probe=_copy.deepcopy(s);_,auto_tuned=_auto_tune_capacity(_probe,"1–3")
    excluded=set(s.get("excluded_teachers",[]))
    absent=set(x.get("absent_teachers",s.get("absent_teachers",[])))
    enabled=set(ALL)-excluded-absent
    s["active_absences"]=list(absent)
    s["manual_blocks"]=x.get("manual_blocks",s.get("manual_blocks",{}))
    school=x.get("reference_school",s.get("school_assignments",[]))
    old13=x.get("reference_13",s.get("last_13_assignments",[]))
    repair_mode=bool(x.get("repair_mode",False))
    req_rules=required_slot_rules(s,"1–3")
    required_by=defaultdict(list)
    for r in req_rules:
        key=(r["day"],r["slot"])
        if r["teacher"] not in required_by[key]:
            required_by[key].append(r["teacher"])
    positions=[]; rule_conflicts=[]; required_count={}
    for b in SEED["breaks"]:
        stations=_required_stations_13(s,b["abbr"],b["label"])
        need=len(stations)
        required_count[(b["abbr"],b["label"])]=need
        names=required_by.get((b["abbr"],b["label"]),[])
        if len(names)>need:
            rule_conflicts.append({"day":b["day"],"slot":b["label"],"message":f"Wymagano {len(names)} nauczycieli przy obsadzie {need}."})
        for i,st in enumerate(stations):
            p={"day":b["day"],"abbr":b["abbr"],"slot":b["label"],"station":st,"break":b}
            required=names[i] if i<len(names) else None
            locked=locked_teacher(s,"1–3",b["abbr"],b["label"],st)
            if required and locked and required!=locked:
                rule_conflicts.append({"day":b["day"],"slot":b["label"],"message":f"Konflikt blokady {locked} z wymaganym nauczycielem {required} w punkcie {st}."})
                p["required_teacher"]="__CONFLICT__"
            elif locked or required:
                chosen=locked or required
                if chosen in excluded:
                    rule_conflicts.append({"day":b["day"],"slot":b["label"],"message":f"{chosen}: wykluczony ze wszystkich dyżurów, ale ma stały/wymagany przydział."})
                p["required_teacher"]=chosen
            positions.append(p)
    preserve13=preserve_13_map(old13) if repair_mode else None
    arr,waits,missing,meta=solve_positions(s,"1–3",positions,enabled,school,preserve_map=preserve13,repair_mode=repair_mode)
    rows=[]; by=defaultdict(list)
    for a in arr: by[(a["day"],a["abbr"],a["slot"])].append(a)
    complete_breaks=0; incomplete=[]
    for b in SEED["breaks"]:
        aa=[]
        for a in sorted(by[(b["day"],b["abbr"],b["label"])],key=lambda x:x["station"]):
            aa.append({"station":a["station"],"teacher":a["teacher"],"wait":a["wait"]})
        need=required_count[(b["abbr"],b["label"])]
        filled=sum(1 for a in aa if a.get("teacher"))
        conflict=next((x for x in rule_conflicts if x["day"]==b["day"] and x["slot"]==b["label"]),None)
        complete=(filled>=need and conflict is None)
        if complete: complete_breaks+=1
        else: incomplete.append({"day":b["day"],"abbr":b["abbr"],"slot":b["label"],"required_people":need,"filled_people":filled})
        rows.append({**b,"required_people":need,"complete":complete,"assignments":aa})
    return {"rows":rows,"waits":waits,"unresolved_details":missing,"incomplete_breaks":incomplete,"rule_conflicts":rule_conflicts,
            "summary":{"breaks":len(SEED["breaks"]),"complete_breaks":complete_breaks,"incomplete_breaks":len(SEED["breaks"])-complete_breaks,
                       "required_positions":len(positions),"filled_positions":len(positions)-len(missing),"unresolved":len(missing),
                       "wait_assignments":len(waits),"constraint_conflicts":len(rule_conflicts),"objective_cost":meta["cost"]},
            "diagnostics":meta.get("diagnostics",{}),"auto_tuned":auto_tuned}

@app.post("/api/solve/school")
def solve_school(x:dict):
    s=load_state()
    _probe=_copy.deepcopy(s);_,auto_tuned=_auto_tune_capacity(_probe,"szkoła")
    excluded=set(s.get("excluded_teachers",[]))
    absent=set(x.get("absent_teachers",s.get("absent_teachers",[])))
    enabled=set(ALL)-excluded-absent
    s["active_absences"]=list(absent)
    s["manual_blocks"]=x.get("manual_blocks",s.get("manual_blocks",{}))
    current=x.get("reference_school",s.get("school_assignments",[]))
    repair_mode=bool(x.get("repair_mode",False))
    positions,preserve,unused,conflicts=_school_positions(s,current=current,include_locks=True)
    other=[]
    for r in x.get("other_rows_13",s.get("last_13_assignments",[])):
        for a in r.get("assignments",[]):
            if a.get("teacher"):
                other.append({"day":r["day"],"abbr":r["abbr"],"slot":r["label"],"location":"1–3 "+a["station"],"teacher":a["teacher"]})
    arr,waits,missing,meta=_solve_school_decomposed_v578(
        s,positions,enabled,other,preserve_map=preserve,repair_mode=repair_mode)
    rule_conflicts=conflicts+[{"teacher":r["teacher"],"day":r["day"],"slot":r["slot"],"location":r["location"],"message":"Wymagany dyżur wskazuje wyłączone miejsce/slot."} for r in unused]
    return {"assignments":arr,"waits":waits,"unresolved_details":missing,
            "rule_conflicts":rule_conflicts,
            "summary":{"required_positions":len(positions),"filled_positions":len(positions)-len(missing),"unresolved":len(missing),
                       "wait_assignments":len(waits),"constraint_conflicts":len(rule_conflicts),"objective_cost":meta["cost"]},
            "diagnostics":meta.get("diagnostics",{}),"auto_tuned":auto_tuned}

@app.post("/api/school/current")
def save_school_current(x:dict):
    s=load_state();before=_copy.deepcopy(s); arr=x.get("assignments",[])
    s["school_assignments"]=[{k:d.get(k) for k in ["day","abbr","slot","location","teacher"]} for d in arr]
    changed=_save_solver_input_change(before,s,"Zmieniono bieżący plan szkoły.")
    return {"ok":True,"solver_input_changed":changed}

@app.post("/api/variants")
def save_variant(x:dict):
    s=load_state()
    v={"id":str(uuid.uuid4()),"name":x.get("name") or datetime.now().strftime("Wariant %Y-%m-%d %H:%M"),"created_at":datetime.now().isoformat(timespec="seconds"),"note":x.get("note",""),"school_assignments":x.get("school_assignments",s.get("school_assignments",[])),"assignments_13":x.get("assignments_13",s.get("last_13_assignments",[])),"settings":x.get("settings",{}),"global_constraints":s.get("global_constraints",[]),"individual_constraints":s.get("individual_constraints",[])}
    s.setdefault("variants",[]).append(v); save_state(s); return v

@app.get("/api/variants/{variant_id}")
def get_variant(variant_id:str):
    s=load_state()
    for v in s.get("variants",[]):
        if v["id"]==variant_id:return v
    raise HTTPException(404,"Brak wariantu")

@app.post("/api/variants/{variant_id}/load")
def load_variant(variant_id:str):
    s=load_state()
    for v in s.get("variants",[]):
        if v["id"]==variant_id:
            s["school_assignments"]=v["school_assignments"]; s["last_13_assignments"]=v["assignments_13"]
            if "global_constraints" in v:s["global_constraints"]=normalize_constraint_rows(v["global_constraints"])
            if "individual_constraints" in v:s["individual_constraints"]=normalize_constraint_rows(v["individual_constraints"])
            for k,val in v.get("settings",{}).items():s[k]=_copy.deepcopy(val)
            ev=_plan_event(s,"variant_load",f"Wczytano wariant: {v.get('name') or variant_id}",
                           [{"variant_id":variant_id}])
            save_state(s)
            _invalidate_active_repair_jobs("Wczytano wariant planu.")
            return {"ok":True,"revision":ev["revision"]}
    raise HTTPException(404,"Brak wariantu")


@app.post("/api/export/plan-pdf")
def export_plan_pdf(x:dict):
    import io
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from xml.sax.saxutils import escape as _xml_escape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception as e:
        raise HTTPException(500,f"Brak modułu PDF: {e}")

    scope=str(x.get("scope") or "school")
    a13=list(x.get("assignments_13") or [])
    school=list(x.get("school_assignments") or [])
    locations=list(x.get("school_locations") or [])
    station_names=dict(x.get("station_names") or {})
    station_order=[str(z) for z in (x.get("station_order_13") or ["A","B"])]
    revision=int(x.get("plan_revision") or 0)

    font="Helvetica"; bold="Helvetica-Bold"
    try:
        f1=r"C:\Windows\Fonts\arial.ttf"; f2=r"C:\Windows\Fonts\arialbd.ttf"
        if Path(f1).exists():
            pdfmetrics.registerFont(TTFont("ZSOArial",f1));font="ZSOArial"
        if Path(f2).exists():
            pdfmetrics.registerFont(TTFont("ZSOArialBold",f2));bold="ZSOArialBold"
    except Exception:
        pass

    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=landscape(A4),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24,
                          title="DEMO - plan dyżurów")
    styles=getSampleStyleSheet()
    title=ParagraphStyle("TitleZ",parent=styles["Title"],fontName=bold,fontSize=15,leading=18,alignment=TA_CENTER,spaceAfter=8)
    small=ParagraphStyle("SmallZ",parent=styles["Normal"],fontName=font,fontSize=7,leading=9)
    cell_left=ParagraphStyle("CellLeftZ",parent=styles["Normal"],fontName=font,fontSize=6.2,leading=7.1,alignment=TA_LEFT,spaceAfter=0,spaceBefore=0)
    story=[]
    day_order=[("Poniedziałek","Pn"),("Wtorek","Wt"),("Środa","Śr"),("Czwartek","Czw"),("Piątek","Pi")]
    today=datetime.now().strftime("%Y-%m-%d")

    def table(data,widths=None):
        rendered=[data[0]]+[[Paragraph(_xml_escape(str(v or "")),cell_left) for v in row] for row in data[1:]]
        t=Table(rendered,colWidths=widths,repeatRows=1,hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTNAME",(0,0),(-1,-1),font),("FONTNAME",(0,0),(-1,0),bold),
            ("FONTSIZE",(0,0),(-1,-1),7),("LEADING",(0,0),(-1,-1),8),
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dbeafe")),
            ("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#64748b")),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,1),(-1,-1),"LEFT"),("ALIGN",(0,0),(-1,0),"CENTER"),
            ("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),
            ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ]))
        return t

    layout=str(x.get("layout") or "")
    if layout=="teacher_grid":
        view_mode=str(x.get("view_mode") or "all")
        if view_mode not in ("all","duties","lessons"): view_mode="all"
        include_lessons=view_mode in ("all","lessons")
        include_duties=view_mode in ("all","duties")
        teachers=[t for t in (x.get("teachers") or []) if isinstance(t,dict) and t.get("name")]
        timeline=x.get("timeline") or {}
        scopes=x.get("scopes") or {}
        scope_label=", ".join(v for ok,v in (
            (scopes.get("show13"),"1–3"),
            (scopes.get("showSchool"),"cała szkoła"),
            (scopes.get("showGym"),"sala gimnastyczna"),
        ) if ok) or "wybrane zakresy"
        mode_label={"all":"lekcje + dyżury","duties":"tylko dyżury","lessons":"tylko plan lekcji"}[view_mode]
        station_label={str(k):str(v) for k,v in station_names.items()}
        by13={}
        for r in a13:
            key=(str(r.get("abbr") or ""),str(r.get("label") or ""))
            for a in r.get("assignments",[]) or []:
                n=str(a.get("teacher") or "").strip()
                if not n:continue
                place=station_label.get(str(a.get("station") or ""),str(a.get("station") or ""))
                by13.setdefault((key[0],key[1],n),[]).append("1–3: "+place)
        bys={}
        for d in school:
            n=str(d.get("teacher") or "").strip()
            if not n:continue
            bys.setdefault((str(d.get("abbr") or ""),str(d.get("slot") or ""),n),[]).append(str(d.get("location") or ""))
        chunk_size=8
        first_page=True
        for day,abbr in day_order:
            day_rows=list(timeline.get(day) or [])
            if not day_rows:
                day_rows=[{"kind":"PRZERWA","key":b.get("label"),"label":b.get("label"),"time":b.get("time")}
                          for b in SEED.get("breaks",[]) if b.get("abbr")==abbr]
            if view_mode=="duties":
                day_rows=[r for r in day_rows if str(r.get("kind") or "")=="PRZERWA"]
            elif view_mode=="lessons":
                day_rows=[r for r in day_rows if str(r.get("kind") or "")=="LEKCJA"]
            for start in range(0,max(1,len(teachers)),chunk_size):
                chunk=teachers[start:start+chunk_size]
                if not chunk:continue
                if not first_page:story.append(PageBreak())
                first_page=False
                part=(start//chunk_size)+1
                parts=max(1,(len(teachers)+chunk_size-1)//chunk_size)
                story.append(Paragraph(
                    f"DEMO – plan dyżurów – {day}"+(f" – część {part}/{parts}" if parts>1 else ""),title))
                story.append(Paragraph(
                    f"Zakres: {_xml_escape(scope_label)} • tryb: {_xml_escape(mode_label)} • rewizja: {revision} • eksport: {today}",small))
                story.append(Spacer(1,6))
                headers=["Godzina","Slot"]+[str(t.get("name") or "") for t in chunk]
                data=[headers]
                for rr in day_rows:
                    kind=str(rr.get("kind") or "")
                    slot=str(rr.get("key") or rr.get("label") or "")
                    label=("L"+str(rr.get("label") or slot)) if kind=="LEKCJA" else str(rr.get("label") or slot)
                    row=[str(rr.get("time") or ""),label]
                    for t in chunk:
                        name=str(t.get("name") or "")
                        cell=[]
                        if kind=="LEKCJA" and include_lessons:
                            lessons=((t.get("lessons") or {}).get(abbr) or {}).get(slot) or []
                            for les in lessons:
                                bits=[str(les.get("class") or "").strip(),str(les.get("subject") or "").strip(),str(les.get("room") or "").strip()]
                                txt=" ".join(b for b in bits if b)
                                if txt:cell.append(txt)
                        elif kind=="PRZERWA" and include_duties:
                            cell.extend(by13.get((abbr,slot,name),[]))
                            locs=bys.get((abbr,slot,name),[])
                            if locs:cell.append("Szkoła: "+", ".join(locs))
                        row.append("\n".join(cell))
                    data.append(row)
                usable=landscape(A4)[0]-48
                fixed=92
                widths=[52,40]+[(usable-fixed)/max(1,len(chunk))]*len(chunk)
                story.append(table(data,widths))
        suffix={"all":"lekcje_i_dyzury","duties":"tylko_dyzury","lessons":"tylko_lekcje"}[view_mode]
        filename=f"DEMO_plan_{suffix}_{today}.pdf"
    elif scope in ("13","1-3","1–3"):
        labels=[station_names.get(sid) or f"Punkt {sid}" for sid in station_order]
        for di,(day,abbr) in enumerate(day_order):
            rows=[r for r in a13 if r.get("abbr")==abbr or r.get("day")==day]
            data=[["Godzina","Przerwa",*labels]]
            for r in rows:
                m={str(a.get("station")):a.get("teacher") or "" for a in r.get("assignments",[]) or []}
                data.append([r.get("time",""),r.get("label",""),*[m.get(sid,"") for sid in station_order]])
            story.append(Paragraph(f"DEMO – dyżury 1–3 – {day}",title))
            story.append(Paragraph(f"Rewizja planu: {revision} • eksport: {today}",small));story.append(Spacer(1,6))
            usable=landscape(A4)[0]-48; n=max(1,len(station_order))
            station_w=min(155,(usable-108)/n)
            story.append(table(data,[58,50]+[station_w]*n))
            if di<len(day_order)-1: story.append(PageBreak())
        filename=f"DEMO_dyzury_1-3_{today}.pdf"
    else:
        if not locations:
            locations=list(dict.fromkeys(str(d.get("location") or "") for d in school if d.get("location")))
        # One compact A4 landscape page per day: all break columns stay together.
        for di,(day,abbr) in enumerate(day_order):
            slots=[]
            for b in SEED.get("breaks",[]):
                if b.get("abbr")==abbr and b.get("label") not in slots: slots.append(b.get("label"))
            if not slots:
                slots=list(dict.fromkeys(d.get("slot") for d in school if d.get("abbr")==abbr and d.get("slot")))
            story.append(Paragraph(f"DEMO – plan dyżurów całej szkoły – {day}",title))
            story.append(Paragraph(f"Rewizja planu: {revision} • eksport: {today}",small));story.append(Spacer(1,6))
            data=[["Miejsce",*slots]]
            for loc in locations:
                row=[loc]
                for slot in slots:
                    d=next((z for z in school if z.get("abbr")==abbr and str(z.get("location"))==str(loc) and z.get("slot")==slot),None)
                    row.append((d or {}).get("teacher") or "")
                data.append(row)
            n=max(1,len(slots));usable=landscape(A4)[0]-48
            first=72; widths=[first]+[(usable-first)/n]*n
            story.append(table(data,widths))
            if di<len(day_order)-1: story.append(PageBreak())
        filename=f"DEMO_plan_szkoly_{today}.pdf"

    doc.build(story)
    buf.seek(0)
    return StreamingResponse(buf,media_type="application/pdf",
        headers={"Content-Disposition":f'attachment; filename="{filename}"'})

@app.post("/api/import")
def import_source(x:dict):
    s=load_state();before=_copy.deepcopy(s); assignments=x.get("school_assignments") or x.get("assignments")
    if not isinstance(assignments,list):raise HTTPException(400,"JSON nie zawiera school_assignments")
    for d in assignments:
        if not all(k in d for k in ["day","abbr","slot","location"]):raise HTTPException(400,"Nieprawidłowy rekord")
        if d.get("teacher") and d["teacher"] not in ALL:raise HTTPException(400,f"Nieznany nauczyciel: {d['teacher']}")
    s["school_assignments"]=assignments
    _save_solver_input_change(before,s,"Zaimportowano plan szkoły.")
    return {"ok":True,"count":len(assignments)}

@app.get("/api/teachers")
def list_teachers():
    rows=[]
    for name,reg in TEACHER_REGISTRY.items():
        t=TBY.get(name,{})
        rows.append({"name":name,"group":reg.get("group","school"),"active":bool(reg.get("active",True)),
                     "portal_token":reg.get("portal_token",""),"lesson_slots":sum(len(ps) for ps in t.get("lessons",{}).values())})
    return {"teachers":sorted(rows,key=lambda x:x["name"])}

@app.post("/api/teachers")
def add_teacher(x:dict):
    name=str(x.get("name") or "").strip()
    group=str(x.get("group") or "school")
    if not name: raise HTTPException(400,"Podaj imię i nazwisko")
    if group not in ("school","1-3","wf"): raise HTTPException(400,"Nieprawidłowa grupa")
    before_state=load_state();before_signature=_solver_input_signature(before_state)
    t=TBY.get(name)
    if t is None:
        t={"name":name,"group":group,"core":group=="1-3","lessons":_empty_lessons(),"active":True}
        SEED.setdefault("teachers",[]).append(t)
    reg=TEACHER_REGISTRY.setdefault(name,{})
    reg.update({"group":group,"active":True})
    reg.setdefault("portal_token",secrets.token_urlsafe(18))
    persist_teacher_data(); refresh_teacher_indexes()
    st=load_state(); st.setdefault("teacher_workload",{})[name]=st.get("teacher_workload",{}).get(name,1.0)
    _save_solver_input_change(before_state,st,"Dodano lub aktywowano nauczyciela.",before_signature)
    return {"ok":True,"name":name,"group":group}

@app.post("/api/teachers/update")
def update_teacher(x:dict):
    name=str(x.get("name") or "").strip()
    if name not in TEACHER_REGISTRY: raise HTTPException(404,"Nieznany nauczyciel")
    before_state=load_state();before_signature=_solver_input_signature(before_state)
    reg=TEACHER_REGISTRY[name]
    if "group" in x:
        group=str(x["group"])
        if group not in ("school","1-3","wf"): raise HTTPException(400,"Nieprawidłowa grupa")
        reg["group"]=group
    if "active" in x: reg["active"]=bool(x["active"])
    refresh_teacher_indexes(); persist_teacher_data()
    st=load_state()
    if not reg.get("active",True):
        st["enabled_teachers_13"]=[n for n in st.get("enabled_teachers_13",[]) if n!=name]
        st["enabled_teachers_school"]=[n for n in st.get("enabled_teachers_school",[]) if n!=name]
        st["absent_teachers"]=[n for n in st.get("absent_teachers",[]) if n!=name]
    _save_solver_input_change(before_state,st,"Zmieniono dane nauczyciela.",before_signature)
    return {"ok":True,"name":name,"group":reg.get("group"),"active":reg.get("active",True)}

TEACHER_RELAX_CATALOG=[
    {"key":"before_first_short","label":"5-minutowa przerwa przed pierwszą lekcją (bez slotu 0/1)"},
    {"key":"after_last_short","label":"5-minutowa przerwa po ostatniej lekcji"},
    {"key":"before_first_long","label":"Dłuższa przerwa przed pierwszą lekcją (bez slotu 0/1)"},
    {"key":"after_last_long","label":"Dłuższa przerwa po ostatniej lekcji"},
    {"key":"avoid_wait","label":"Dodatkowe oczekiwanie na dyżur","locked_last":True},
]

def _portal_teacher(token):
    for name,reg in TEACHER_REGISTRY.items():
        if reg.get("active",True) and secrets.compare_digest(str(reg.get("portal_token","")),str(token or "")):
            return name
    raise HTTPException(404,"Nieprawidłowy link nauczyciela")

def _current_view_job_v573():
    try:
        with REPAIR_JOB_LOCK:
            jobs=list(REPAIR_JOBS.values())
            active=[j for j in jobs if j.get("status") in ("queued","running","paused") and not j.get("_cancel")]
            pool=active or jobs
            current=max(pool,key=lambda j:j.get("created_at","")) if pool else None
        # _repair_copy_public() takes REPAIR_JOB_LOCK internally.
        # Never call it while already holding the same non-reentrant lock.
        public=_repair_copy_public(current) if current else None
    except Exception:
        public=None
    return public or _latest_repair_checkpoint()

def _current_live_variant_v573():
    # Hot-path used by /api/effective-plan and /api/config.
    # Never deepcopy the whole repair job here: trial history can grow very large
    # and used to stall UI polling for tens of seconds while the solver was active.
    try:
        jobs=list(REPAIR_JOBS.values())
        active=[j for j in jobs if j.get("status") in ("queued","running","paused") and not j.get("_cancel")]
        pool_jobs=active or jobs
        raw=max(pool_jobs,key=lambda j:j.get("created_at","")) if pool_jobs else None
    except Exception:
        raw=None
    if not raw:
        job=_latest_repair_checkpoint()
        if not job:return None,None
    else:
        # Minimal job metadata needed by quality ranking and source labels.
        job={
            "id":raw.get("id"),"status":raw.get("status"),"created_at":raw.get("created_at"),
            "stale_due_to_manual_edit":raw.get("stale_due_to_manual_edit",False),
            "accepted_compromises":list(raw.get("accepted_compromises",[]) or []),
        }
    if job.get("stale_due_to_manual_edit") or str(job.get("status") or "") in ("cancelled","failed"):
        return None,job
    variants=[]
    if raw:
        # Shallow-copy the small public variant lists; selected candidate is deep-copied below.
        for bucket in ("working_variants","suggestions"):
            try: variants.extend(list(raw.get(bucket,[]) or []))
            except Exception: pass
    else:
        for bucket in ("working_variants","suggestions"):
            variants.extend(list(job.get(bucket,[]) or []))
    variants=[v for v in variants if v and v.get("live_eligible") is True and v.get("result_13") and v.get("result_school")]
    if not variants:
        return None,job
    best=min(variants,key=lambda v:(_working_quality_key_v559(v,job),int(v.get("seq",0) or 0)))
    return _copy.deepcopy(best),job

def _teacher_saved_duties_v573(name,state):
    duties=[]
    for r in state.get("last_13_assignments",[]) or []:
        for a in r.get("assignments",[]) or []:
            if a.get("teacher")==name:
                duties.append({"scope":"1-3","day":r.get("day"),"abbr":r.get("abbr"),"slot":r.get("label"),"place":a.get("station"),"wait":a.get("wait",0)})
    for a in state.get("school_assignments",[]) or []:
        if a.get("teacher")==name:
            duties.append({"scope":"school","day":a.get("day"),"abbr":a.get("abbr"),"slot":a.get("slot"),"place":a.get("location"),"wait":a.get("wait",0)})
    return duties

def _flatten_saved_13_v574(state):
    out=[]
    for r in state.get("last_13_assignments",[]) or []:
        for a in r.get("assignments",[]) or []:
            out.append({"day":r.get("day"),"abbr":r.get("abbr"),"slot":r.get("label"),
                        "station":a.get("station"),"teacher":a.get("teacher") or "",
                        "wait":a.get("wait",0),"wait_kind":a.get("wait_kind","")})
    return out

def _required_position_keys_v577(state):
    req13=set()
    for b in SEED.get("breaks",[]) or []:
        for sid in _required_stations_13(state,b.get("abbr"),b.get("label")):
            req13.add((str(b.get("abbr") or ""),str(b.get("label") or ""),str(sid)))
    reqs=set()
    vals=state.get("min_people_school",{}) or {}
    for b in SEED.get("breaks",[]) or []:
        ab=str(b.get("abbr") or ""); slot=str(b.get("label") or "")
        for loc in state.get("school_locations",[]) or []:
            try: need=int(vals.get(f"{ab}|{slot}|{loc}",0) or 0)
            except Exception: need=0
            if need==1 and _position_zone_active_school(state,ab,slot,loc):
                reqs.add((ab,slot,str(loc)))
    return req13,reqs

def _plan_snapshot_audit_v577(result13,result_school,state=None):
    state=ensure_state_schema(_copy.deepcopy(state if state is not None else load_state()))
    req13,reqs=_required_position_keys_v577(state)
    got13={}
    for a in result13 or []:
        key=(str(a.get("abbr") or ""),str(a.get("slot") or ""),str(a.get("station") or ""))
        teacher=str(a.get("teacher") or "").strip()
        if key in req13 and teacher:
            got13[key]=teacher
    gots={}
    for a in result_school or []:
        key=(str(a.get("abbr") or ""),str(a.get("slot") or ""),str(a.get("location") or ""))
        teacher=str(a.get("teacher") or "").strip()
        if key in reqs and teacher:
            gots[key]=teacher
    occupancy={}
    for (ab,slot,_),teacher in list(got13.items())+list(gots.items()):
        occupancy.setdefault((teacher,ab,slot),0)
        occupancy[(teacher,ab,slot)]+=1
    collisions=[{"teacher":t,"abbr":ab,"slot":slot,"count":n}
                for (t,ab,slot),n in occupancy.items() if n>1]
    miss13=sorted(req13-set(got13))
    misss=sorted(reqs-set(gots))
    return {
        "ok":not miss13 and not misss and not collisions,
        "required13":len(req13),"filled13_real":len(got13),"missing13_real":len(miss13),
        "requiredSchool":len(reqs),"filledSchool_real":len(gots),"missingSchool_real":len(misss),
        "slot_collisions":collisions,
        "missing13_sample":[list(x) for x in miss13[:12]],
        "missingSchool_sample":[list(x) for x in misss[:12]],
    }

def _load_last_good_plan_v577(state=None):
    if not LAST_GOOD_PLAN_PATH.exists(): return None
    try:
        x=json.loads(LAST_GOOD_PLAN_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    audit=_plan_snapshot_audit_v577(x.get("result_13") or [],x.get("result_school") or [],state)
    if not audit.get("ok"): return None
    x["audit"]=audit
    return x

def _last_good_quality_key_v577(metrics):
    m=metrics or {}
    def iv(key,default=10**8):
        try:
            v=m.get(key)
            return default if v is None else int(v)
        except Exception:
            return default
    try:
        fair=10**8 if m.get("fairness_normalized_deviation") is None else float(m.get("fairness_normalized_deviation"))
    except Exception:
        fair=10**8
    return (iv("wait_lessons_total"),iv("after_last_long"),iv("wf_assignments_total"),iv("before_first_long"),fair)

def _persist_last_good_plan_v577(result13,result_school,source,state=None,metrics=None,force=False):
    state=state if state is not None else load_state()
    audit=_plan_snapshot_audit_v577(result13,result_school,state)
    if not audit.get("ok"):
        return False
    if LAST_GOOD_PLAN_PATH.exists() and not force:
        try:
            old=json.loads(LAST_GOOD_PLAN_PATH.read_text(encoding="utf-8-sig"))
            old_audit=_plan_snapshot_audit_v577(old.get("result_13") or [],old.get("result_school") or [],state)
            if old_audit.get("ok") and _last_good_quality_key_v577(old.get("metrics"))<=_last_good_quality_key_v577(metrics):
                return False
        except Exception:
            pass
    payload={
        "saved_at":datetime.now().isoformat(timespec="seconds"),
        "source":_copy.deepcopy(source or {}),
        "audit":audit,
        "metrics":_copy.deepcopy(metrics or {}),
        "result_13":_copy.deepcopy(result13 or []),
        "result_school":_copy.deepcopy(result_school or []),
    }
    tmp=LAST_GOOD_PLAN_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(LAST_GOOD_PLAN_PATH)
    return True

def _effective_plan_v574(state=None):
    state=state if state is not None else load_state()
    live,job=_current_live_variant_v573()
    if live:
        audit=_plan_snapshot_audit_v577(live.get("result_13") or [],live.get("result_school") or [],state)
        if audit.get("ok"):
            source={"kind":"live_verified","source_id":"live:"+str((job or {}).get("id") or "")+":"+str(live.get("id") or ""),
                    "label":"Szkic roboczy #"+str(live.get("seq") or "?")+" \u2014 niezapisany",
                    "unsaved":True,"variant_id":live.get("id"),"seq":live.get("seq"),
                    "found_at":live.get("found_at"),"job_id":(job or {}).get("id"),
                    "job_status":(job or {}).get("status"),"verified":True}
            return {"source":source,"audit":audit,
                    "result_13":_copy.deepcopy(live.get("result_13") or []),
                    "result_school":_copy.deepcopy(live.get("result_school") or []),
                    "coverage13":_copy.deepcopy(live.get("coverage13") or {}),
                    "coverageSchool":_copy.deepcopy(live.get("coverageSchool") or {})}

    # Single GUI truth: an older saved/reference plan can remain an internal
    # solver baseline, but while a fresh search is active it must not be
    # presented as the current plan anywhere in the GUI.
    job_status=str((job or {}).get("status") or "")
    if False and job_status in ("queued","running","paused"):
        saved13_probe=_flatten_saved_13_v574(state)
        saved_school_probe=_copy.deepcopy(state.get("school_assignments",[]) or [])
        saved_audit_probe=_plan_snapshot_audit_v577(saved13_probe,saved_school_probe,state)
        source={"kind":"calculating_waiting",
                "source_id":"calculating:"+str((job or {}).get("id") or ""),
                "label":"Trwa liczenie — oczekiwanie na pierwszy pełny zweryfikowany szkic",
                "unsaved":True,"verified":False,
                "job_id":(job or {}).get("id"),"job_status":job_status}
        return {"source":source,"audit":saved_audit_probe,
                "result_13":[],"result_school":[],
                "coverage13":{"required":saved_audit_probe.get("required13",0),"filled":0,
                              "missing":saved_audit_probe.get("required13",0)},
                "coverageSchool":{"required":saved_audit_probe.get("requiredSchool",0),"filled":0,
                                  "missing":saved_audit_probe.get("requiredSchool",0)}}

    saved13=_flatten_saved_13_v574(state)
    saveds=_copy.deepcopy(state.get("school_assignments",[]) or [])
    saved_audit=_plan_snapshot_audit_v577(saved13,saveds,state)
    rev=int(state.get("plan_revision",0) or 0)
    if saved_audit.get("ok"):
        source={"kind":"saved_verified","source_id":"saved:"+str(rev),"label":"Plan zapisany \u2014 zweryfikowany",
                "unsaved":False,"verified":True,"plan_revision":rev,"variant_id":None,"seq":None,
                "job_id":(job or {}).get("id") if job else None,"job_status":(job or {}).get("status") if job else None}
        return {"source":source,"audit":saved_audit,"result_13":saved13,"result_school":saveds,
                "coverage13":{"required":saved_audit["required13"],"filled":saved_audit["filled13_real"],"missing":0},
                "coverageSchool":{"required":saved_audit["requiredSchool"],"filled":saved_audit["filledSchool_real"],"missing":0}}

    ref=_load_last_good_plan_v577(state)
    if ref:
        src=_copy.deepcopy(ref.get("source") or {})
        source={"kind":"reference_verified","source_id":"reference:"+str(src.get("source_id") or src.get("variant_id") or ref.get("saved_at") or ""),
                "label":"Ostatni zweryfikowany pe\u0142ny plan \u2014 plan referencyjny",
                "unsaved":True,"verified":True,"reference_saved_at":ref.get("saved_at"),
                "origin":src,"job_id":(job or {}).get("id") if job else None,
                "job_status":(job or {}).get("status") if job else None}
        audit=ref["audit"]
        return {"source":source,"audit":audit,
                "result_13":_copy.deepcopy(ref.get("result_13") or []),
                "result_school":_copy.deepcopy(ref.get("result_school") or []),
                "coverage13":{"required":audit["required13"],"filled":audit["filled13_real"],"missing":0},
                "coverageSchool":{"required":audit["requiredSchool"],"filled":audit["filledSchool_real"],"missing":0}}

    source={"kind":"invalid_saved","source_id":"invalid-saved:"+str(rev),
            "label":"Brak zweryfikowanego pe\u0142nego planu","unsaved":False,"verified":False,
            "plan_revision":rev,"saved_audit":saved_audit,
            "job_id":(job or {}).get("id") if job else None,"job_status":(job or {}).get("status") if job else None}
    return {"source":source,"audit":saved_audit,"result_13":[],"result_school":[],
            "coverage13":{"required":saved_audit["required13"],"filled":0,"missing":saved_audit["required13"]},
            "coverageSchool":{"required":saved_audit["requiredSchool"],"filled":0,"missing":saved_audit["requiredSchool"]}}

def _teacher_effective_duties_v573(name,state):
    saved=_teacher_saved_duties_v573(name,state)
    plan=_effective_plan_v574(state)
    duties=[]
    for a in plan.get("result_13",[]) or []:
        if a.get("teacher")==name:
            duties.append({"scope":"1-3","day":a.get("day"),"abbr":a.get("abbr"),"slot":a.get("slot"),"place":a.get("station"),"wait":a.get("wait",0)})
    for a in plan.get("result_school",[]) or []:
        if a.get("teacher")==name:
            duties.append({"scope":"school","day":a.get("day"),"abbr":a.get("abbr"),"slot":a.get("slot"),"place":a.get("location"),"wait":a.get("wait",0)})
    source=_copy.deepcopy(plan.get("source") or {})
    if not source.get("verified"):
        saved=[]
    return duties,source,saved

@app.get("/api/effective-plan")
def effective_plan():
    return _effective_plan_v574(load_state())

@app.get("/api/teacher-portal/{token}")
def teacher_portal(token:str):
    name=_portal_teacher(token); t=TBY[name]; st=load_state()
    duties,duty_source,saved_duties=_teacher_effective_duties_v573(name,st)
    admin_locks=[{k:r.get(k) for k in ("scope","abbr","slot","location","teacher","comment")}
                 for r in st.get("locked_assignments",[]) if r.get("teacher")==name]
    return {"teacher":{"name":name,"group":GROUP.get(name,"school")},"lessons":t.get("lessons",{}),"breaks":SEED.get("breaks",[]),
            "timeline":SEED.get("timeline",{}),"duties":duties,"saved_duties":saved_duties,"duty_source":duty_source,
            "preferences":st.get("preference_grid",{}).get(name,{}),
            "preference_comments":st.get("preference_comments",{}).get(name,{}),
            "relax_order":st.get("teacher_relax_order",{}).get(name,[x["key"] for x in TEACHER_RELAX_CATALOG]),
            "relax_catalog":TEACHER_RELAX_CATALOG,
            "relaxed_rules":st.get("teacher_relaxed_rules",{}).get(name,[]),
            "recalc_requests":[r for r in st.get("teacher_recalc_requests",[]) if r.get("teacher")==name and r.get("status","pending")=="pending"],
            "admin_locks":admin_locks}

@app.post("/api/teacher-portal/{token}/preferences")
def teacher_portal_preferences(token:str,x:dict):
    name=_portal_teacher(token); prefs=x.get("preferences",{}); comments=x.get("comments",{})
    if not isinstance(prefs,dict): raise HTTPException(400,"Nieprawid\u0142owe preferencje")
    if not isinstance(comments,dict): raise HTTPException(400,"Nieprawid\u0142owe komentarze")
    st=load_state();before=_copy.deepcopy(st)
    locked_slots={f"{r.get('abbr')}|{r.get('slot')}" for r in st.get("locked_assignments",[]) if r.get("teacher")==name}
    clean={}
    for k,v in prefs.items():
        vv=str(v).lower(); key=str(k)
        if key in locked_slots: continue
        if vv in ("prefer","avoid"): clean[key]=vv
    pref_grid=st.setdefault("preference_grid",{})
    if clean: pref_grid[name]=clean
    else: pref_grid.pop(name,None)
    valid_slots={f"{b.get('abbr')}|{b.get('label')}" for b in (SEED.get("breaks",[]) or []) if b.get("abbr") and b.get("label")}
    clean_comments={}
    for k,v in comments.items():
        key=str(k)
        if key not in valid_slots or key in locked_slots: continue
        text=str(v or "").strip()[:500]
        if text: clean_comments[key]=text
    pref_comments=st.setdefault("preference_comments",{})
    if clean_comments: pref_comments[name]=clean_comments
    else: pref_comments.pop(name,None)
    allowed=[z["key"] for z in TEACHER_RELAX_CATALOG]
    raw=[str(k) for k in (x.get("relax_order") or st.get("teacher_relax_order",{}).get(name,allowed)) if str(k) in allowed]
    order=list(dict.fromkeys(raw+[k for k in allowed if k not in raw]))
    order=[k for k in order if k!="avoid_wait"]+["avoid_wait"]
    st.setdefault("teacher_relax_order",{})[name]=order
    changed=_save_solver_input_change(before,st,"Nauczyciel zmieni\u0142 preferencje lub kolejno\u015b\u0107 ust\u0119pstw.")
    return {"ok":True,"teacher":name,"preferences":clean,"comments":clean_comments,"relax_order":order,"solver_input_changed":changed}

@app.post("/api/teacher-portal/{token}/recalc-request")
def teacher_portal_recalc_request(token:str,x:dict):
    name=_portal_teacher(token); abbr=str(x.get("abbr") or ""); slot=str(x.get("slot") or "")
    if not abbr or not slot: raise HTTPException(400,"Brak dnia lub slotu.")
    st=load_state()
    pref=str(st.get("preference_grid",{}).get(name,{}).get(f"{abbr}|{slot}","neutral"))
    pref_comment=str(st.get("preference_comments",{}).get(name,{}).get(f"{abbr}|{slot}","") or "")[:500]
    if pref!="avoid":
        raise HTTPException(400,"Prosbe o przeliczenie mozna zlozyc dla slotu oznaczonego jako niepozadany.")
    effective_duties,duty_source,_saved=_teacher_effective_duties_v573(name,st)
    has_duty=any(d.get("abbr")==abbr and d.get("slot")==slot for d in effective_duties)
    if not has_duty: raise HTTPException(400,"Nauczyciel nie ma obecnie dyzuru w tym slocie.")
    rows=st.setdefault("teacher_recalc_requests",[])
    dup=next((r for r in rows if r.get("teacher")==name and r.get("abbr")==abbr and r.get("slot")==slot and r.get("status","pending")=="pending"),None)
    if dup: return {"ok":True,"request":dup,"duplicate":True}
    rec={"id":_uuid.uuid4().hex[:12],"teacher":name,"abbr":abbr,"slot":slot,"preference":pref,"comment":pref_comment,
         "duty_source":duty_source,"status":"pending","created_at":datetime.now().isoformat(timespec="seconds"),"source":"teacher_portal"}
    rows.append(rec);save_state(st)
    return {"ok":True,"request":rec}

@app.post("/api/import/teacher-lessons")
def import_teacher_lessons(x:dict):
    teachers=x.get("teachers",[])
    if not isinstance(teachers,list):
        raise HTTPException(400,"Brak listy teachers")
    before_state=load_state();before_signature=_solver_input_signature(before_state)
    known={t["name"]:t for t in SEED["teachers"]}
    updated=[]; unknown=[]; added=[]; lesson_count=0
    backup_dir=ROOT/"data"/"import_backups"
    backup_dir.mkdir(exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    (backup_dir/f"seed_before_{stamp}.json").write_text(json.dumps(SEED,ensure_ascii=False,indent=2),encoding="utf-8")
    for item in teachers:
        name=item.get("name")
        lessons=item.get("lessons",{})
        if not name: unknown.append("?"); continue
        if name not in known:
            group=_classify_new_teacher(lessons)
            t={"name":name,"group":group,"core":group=="1-3","lessons":_empty_lessons(),"active":True}
            SEED["teachers"].append(t); known[name]=t
            TEACHER_REGISTRY[name]={"group":group,"active":True,"portal_token":secrets.token_urlsafe(18)}
            added.append({"name":name,"group":group})
        clean={d:{} for d in ["Pn","Wt","Śr","Czw","Pi"]}
        for d,rows in lessons.items():
            if d not in clean or not isinstance(rows,dict): continue
            for period,vals in rows.items():
                try: pp=str(int(period))
                except: continue
                if not isinstance(vals,list): vals=[vals]
                clean[d][pp]=[]
                for v in vals:
                    if not isinstance(v,dict): continue
                    clean[d][pp].append({
                        "class":str(v.get("class") or "—"),
                        "subject":str(v.get("subject") or "—"),
                        "room":str(v.get("room") or "—"),
                        "source":str(x.get("source_name") or "import PDF")
                    })
                if clean[d][pp]: lesson_count+=1
        known[name]["lessons"]=clean
        updated.append(name)
    persist_teacher_data(); refresh_teacher_indexes()
    s=load_state()
    s["teacher_plan_source"]={"name":x.get("source_name","PDF"),"imported_at":datetime.now().isoformat(timespec="seconds"),"updated_teachers":updated}
    _save_solver_input_change(before_state,s,"Zaimportowano plan lekcji nauczycieli.",before_signature)
    return {"ok":True,"updated_teachers":updated,"added_teachers":added,"unknown":unknown,"lesson_slots":lesson_count}


@app.get("/api/map/lessons")
def map_lessons():
    days=["Pn","Wt","Śr","Czw","Pi"]; periods=list(range(1,10))
    tmp=defaultdict(lambda: defaultdict(lambda: defaultdict(list))); seen=defaultdict(set)
    for t in SEED.get("teachers",[]):
        teacher=_display_teacher(t.get("name","")); lessons=t.get("lessons") or {}
        for day in days:
            rows=lessons.get(day,{})
            if not isinstance(rows,dict): continue
            for period,vals in rows.items():
                try: p=int(period)
                except Exception: continue
                if p not in periods: continue
                if not isinstance(vals,list): vals=[vals]
                for x in vals:
                    if not isinstance(x,dict): continue
                    room=str(x.get("room") or "").strip()
                    if not room or room=="—": continue
                    item={"class":str(x.get("class") or "—").strip(),"subject":str(x.get("subject") or "—").strip(),"teacher":teacher}
                    key=(item["class"],item["subject"],item["teacher"]); slot=(room,day,p)
                    if key in seen[slot]: continue
                    seen[slot].add(key); tmp[room][day][str(p)].append(item)
    total=len(days)*len(periods); rooms={}
    for room,by_day in tmp.items():
        schedule={d:{} for d in days}; occupied=0
        for day in days:
            for p in periods:
                items=by_day.get(day,{}).get(str(p),[])
                if items:
                    occupied+=1; schedule[day][str(p)]=sorted(items,key=lambda z:(z["class"].casefold(),z["subject"].casefold(),z["teacher"].casefold()))
        rooms[room]={"occupied_slots":occupied,"free_slots":total-occupied,"total_slots":total,"occupancy":round(occupied/total,4),"schedule":schedule}
    return {"ok":True,"days":days,"periods":periods,"total_slots":total,"rooms":dict(sorted(rooms.items())),"source":(load_state().get("teacher_plan_source") or {})}

@app.get("/vendor/vue.global.prod.js")
def vue_vendor():
    r=FileResponse(ROOT/"static"/"vendor"/"vue.global.prod.js", media_type="application/javascript")
    r.headers["Cache-Control"]="public, max-age=31536000, immutable"
    return r

@app.get("/teacher")
def teacher_page():
    r=FileResponse(ROOT/"static"/"teacher.html");r.headers["Cache-Control"]="no-store, no-cache, must-revalidate";return r

@app.get("/map")
def map_page():
    r=FileResponse(ROOT/"static"/"map.html");r.headers["Cache-Control"]="no-store, no-cache, must-revalidate";return r

@app.get("/")
def index():
    r=FileResponse(ROOT/"static"/"index.html");r.headers["Cache-Control"]="no-store, no-cache, must-revalidate";return r




