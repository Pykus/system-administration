from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v4.6-final\app.py")
s=p.read_text(encoding="utf-8")

needle='''def global_limit_spec(cs,key):
    if not cenabled(cs,key):
        return None
    try:
        value=max(0,int(cs[key].get("value") or 0))
    except Exception:
        value=0
    return {"value":value,"kind":ckind(cs,key),"priority":cpriority(cs,key,1000)}

'''
insert=needle+'''def normalize_constraint_rows(rows):
    out=[]
    for raw in rows or []:
        r=dict(raw)
        r["kind"]=normalize_kind(r.get("kind","hard"))
        try:
            r["priority"]=max(0,int(r.get("priority") if r.get("priority") is not None else 1000))
        except Exception:
            r["priority"]=1000
        r["enabled"]=bool(r.get("enabled",True))
        out.append(r)
    return out

'''
if s.count(needle)!=1:
    raise RuntimeError("global_limit_spec insertion point")
s=s.replace(needle,insert,1)

old='''@app.post("/api/constraints")
def save_constraints(x:dict):
    s=load_state()
    if "global" in x: s["global_constraints"]=x["global"]
    if "individual" in x: s["individual_constraints"]=x["individual"]
    save_state(s); return {"ok":True}
'''
new='''@app.post("/api/constraints")
def save_constraints(x:dict):
    s=load_state()
    if "global" in x:
        s["global_constraints"]=normalize_constraint_rows(x["global"])
    if "individual" in x:
        s["individual_constraints"]=normalize_constraint_rows(x["individual"])
    save_state(s)
    return {"ok":True}
'''
if s.count(old)!=1:
    raise RuntimeError("save_constraints point")
s=s.replace(old,new,1)

old='''            if "global_constraints" in v:s["global_constraints"]=v["global_constraints"]
            if "individual_constraints" in v:s["individual_constraints"]=v["individual_constraints"]
'''
new='''            if "global_constraints" in v:s["global_constraints"]=normalize_constraint_rows(v["global_constraints"])
            if "individual_constraints" in v:s["individual_constraints"]=normalize_constraint_rows(v["individual_constraints"])
'''
if s.count(old)!=1:
    raise RuntimeError("load_variant point")
s=s.replace(old,new,1)

p.write_text(s,encoding="utf-8")
print("PATCH2_OK")
