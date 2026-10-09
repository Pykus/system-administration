from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")

s=s.replace("import json, uuid, heapq, math","import json, uuid, heapq, math, secrets, re")

old='''ROOT=Path(__file__).parent
SEED=json.loads((ROOT/"data"/"seed.json").read_text(encoding="utf-8"))
STATE_PATH=ROOT/"data"/"state.json"
app=FastAPI(title="DEMO Dyżury",version="5.5")
CORE={t["name"] for t in SEED["teachers"] if t.get("group")=="1-3"}
WF={t["name"] for t in SEED["teachers"] if t.get("group")=="wf"}
SCHOOL={t["name"] for t in SEED["teachers"] if t.get("group")=="school"}
GROUP={t["name"]:t.get("group","school") for t in SEED["teachers"]}
ALL={t["name"] for t in SEED["teachers"]}
TBY={t["name"]:t for t in SEED["teachers"]}
'''
new='''ROOT=Path(__file__).parent
SEED=json.loads((ROOT/"data"/"seed.json").read_text(encoding="utf-8"))
STATE_PATH=ROOT/"data"/"state.json"
TEACHER_REGISTRY_PATH=ROOT/"data"/"teacher_registry.json"
app=FastAPI(title="DEMO Dyżury",version="5.6")

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
'''
if old not in s: raise SystemExit("top block not found")
s=s.replace(old,new)

s=s.replace('''    for r in rows:
        if r.get("key")=="preserve_school_current":
            r["label"]="Zachowuj istniejący plan"
            r["description"]="W zwykłym przeliczeniu preferuje obecne przydziały szkoły; tryb naprawczy dodatkowo używa ścisłej minimalizacji liczby zmian."
''','''    for r in rows:
        if r.get("key")=="preserve_school_current":
            r["label"]="Zachowuj istniejący plan"
            r["description"]="W zwykłym przeliczeniu preferuje obecne przydziały szkoły; tryb naprawczy dodatkowo używa ścisłej minimalizacji liczby zmian."
        desc=str(r.get("description") or "")
        desc=re.sub(r"\\bHARD\\b","Musi być",desc,flags=re.I)
        desc=re.sub(r"\\bSOFT\\b","Zalecane",desc,flags=re.I)
        r["description"]=desc
''')

s=s.replace('''def _map13_from_state(state):
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
''','''def _duty_rec(teacher,scope,abbr,slot,place,wait=0):
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
    rows.sort(key=lambda x:x["teacher"])
    return {"positions_changed":changed,"teachers_changed":len(rows),"teachers":rows}
''')

s=s.replace('''@app.get("/api/config")
def config():
    s=load_state()
    return {**SEED,"state":s,"variant_meta":[{"id":v["id"],"name":v["name"],"created_at":v["created_at"],"note":v.get("note","")} for v in s.get("variants",[])]}
''','''@app.get("/api/config")
def config():
    s=load_state()
    view={**SEED,"teachers":[t for t in SEED.get("teachers",[]) if t.get("name") in ALL]}
    return {**view,"state":s,"variant_meta":[{"id":v["id"],"name":v["name"],"created_at":v["created_at"],"note":v.get("note","")} for v in s.get("variants",[])]}
''')

s=s.replace('''    return {"ok":True,"version":"5.5","engine":"OR-Tools CP-SAT","ortools_version":getattr(ortools,"__version__","?"),
''','''    return {"ok":True,"version":"5.6","engine":"OR-Tools CP-SAT","ortools_version":getattr(ortools,"__version__","?"),
''')

marker='''@app.post("/api/import/teacher-lessons")
def import_teacher_lessons(x:dict):
'''
insert='''@app.get("/api/teachers")
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
    t=TBY.get(name)
    if t is None:
        t={"name":name,"group":group,"core":group=="1-3","lessons":_empty_lessons(),"active":True}
        SEED.setdefault("teachers",[]).append(t)
    reg=TEACHER_REGISTRY.setdefault(name,{})
    reg.update({"group":group,"active":True})
    reg.setdefault("portal_token",secrets.token_urlsafe(18))
    persist_teacher_data(); refresh_teacher_indexes()
    st=load_state(); st.setdefault("teacher_workload",{})[name]=st.get("teacher_workload",{}).get(name,1.0); save_state(st)
    return {"ok":True,"name":name,"group":group}

@app.post("/api/teachers/update")
def update_teacher(x:dict):
    name=str(x.get("name") or "").strip()
    if name not in TEACHER_REGISTRY: raise HTTPException(404,"Nieznany nauczyciel")
    reg=TEACHER_REGISTRY[name]
    if "group" in x:
        group=str(x["group"])
        if group not in ("school","1-3","wf"): raise HTTPException(400,"Nieprawidłowa grupa")
        reg["group"]=group
    if "active" in x: reg["active"]=bool(x["active"])
    persist_teacher_data(); refresh_teacher_indexes()
    st=load_state()
    if not reg.get("active",True):
        st["enabled_teachers_13"]=[n for n in st.get("enabled_teachers_13",[]) if n!=name]
        st["enabled_teachers_school"]=[n for n in st.get("enabled_teachers_school",[]) if n!=name]
        st["absent_teachers"]=[n for n in st.get("absent_teachers",[]) if n!=name]
    save_state(st)
    return {"ok":True,"name":name,"group":reg.get("group"),"active":reg.get("active",True)}

def _portal_teacher(token):
    for name,reg in TEACHER_REGISTRY.items():
        if reg.get("active",True) and secrets.compare_digest(str(reg.get("portal_token","")),str(token or "")):
            return name
    raise HTTPException(404,"Nieprawidłowy link nauczyciela")

@app.get("/api/teacher-portal/{token}")
def teacher_portal(token:str):
    name=_portal_teacher(token); t=TBY[name]; st=load_state(); duties=[]
    for r in st.get("last_13_assignments",[]):
        for a in r.get("assignments",[]):
            if a.get("teacher")==name:
                duties.append({"scope":"1–3","day":r.get("day"),"abbr":r.get("abbr"),"slot":r.get("label"),"place":a.get("station"),"wait":a.get("wait",0)})
    for a in st.get("school_assignments",[]):
        if a.get("teacher")==name:
            duties.append({"scope":"szkoła","day":a.get("day"),"abbr":a.get("abbr"),"slot":a.get("slot"),"place":a.get("location"),"wait":a.get("wait",0)})
    return {"teacher":{"name":name,"group":GROUP.get(name,"school")},"lessons":t.get("lessons",{}),"breaks":SEED.get("breaks",[]),
            "duties":duties,"preferences":st.get("preference_grid",{}).get(name,{})}

@app.post("/api/teacher-portal/{token}/preferences")
def teacher_portal_preferences(token:str,x:dict):
    name=_portal_teacher(token); prefs=x.get("preferences",{})
    if not isinstance(prefs,dict): raise HTTPException(400,"Nieprawidłowe preferencje")
    clean={}
    for k,v in prefs.items():
        vv=str(v).lower()
        if vv in ("prefer","avoid","forbid"): clean[str(k)]=vv
    st=load_state(); st.setdefault("preference_grid",{})[name]=clean; save_state(st)
    return {"ok":True,"teacher":name,"preferences":clean}

'''
if marker not in s: raise SystemExit("import marker not found")
s=s.replace(marker,insert+marker)

# replace import function body by targeted changes
s=s.replace('''    known={t["name"]:t for t in SEED["teachers"]}
    updated=[]; unknown=[]; lesson_count=0
''','''    known={t["name"]:t for t in SEED["teachers"]}
    updated=[]; unknown=[]; added=[]; lesson_count=0
''')
s=s.replace('''        if name not in known:
            unknown.append(name or "?")
            continue
        clean={d:{} for d in ["Pn","Wt","Śr","Czw","Pi"]}
''','''        if not name: unknown.append("?"); continue
        if name not in known:
            group=_classify_new_teacher(lessons)
            t={"name":name,"group":group,"core":group=="1-3","lessons":_empty_lessons(),"active":True}
            SEED["teachers"].append(t); known[name]=t
            TEACHER_REGISTRY[name]={"group":group,"active":True,"portal_token":secrets.token_urlsafe(18)}
            added.append({"name":name,"group":group})
        clean={d:{} for d in ["Pn","Wt","Śr","Czw","Pi"]}
''')
s=s.replace('''    (ROOT/"data"/"seed.json").write_text(json.dumps(SEED,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    s=load_state()
''','''    persist_teacher_data(); refresh_teacher_indexes()
    s=load_state()
''',1)
s=s.replace('''    return {"ok":True,"updated_teachers":updated,"unknown":unknown,"lesson_slots":lesson_count}
''','''    return {"ok":True,"updated_teachers":updated,"added_teachers":added,"unknown":unknown,"lesson_slots":lesson_count}
''')

s=s.replace('''@app.get("/")
def index():
    r=FileResponse(ROOT/"static"/"index.html");r.headers["Cache-Control"]="no-store, no-cache, must-revalidate";return r
''','''@app.get("/teacher")
def teacher_page():
    r=FileResponse(ROOT/"static"/"teacher.html");r.headers["Cache-Control"]="no-store, no-cache, must-revalidate";return r

@app.get("/")
def index():
    r=FileResponse(ROOT/"static"/"index.html");r.headers["Cache-Control"]="no-store, no-cache, must-revalidate";return r
''')

p.write_text(s,encoding="utf-8")
print("patched backend", len(s.splitlines()))
