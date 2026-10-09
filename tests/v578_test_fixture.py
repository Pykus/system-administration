from collections import defaultdict

def full_snapshot(app,state=None):
    st=app.ensure_state_schema(state if state is not None else app.load_state())
    req13,reqs=app._required_position_keys_v577(st)
    teachers=sorted(app.ALL,key=app._teacher_sort_key)
    assert teachers
    byslot=defaultdict(int)
    r13=[]; rs=[]
    bm=app.break_map()
    for ab,slot,station in sorted(req13):
        idx=byslot[(ab,slot)]; byslot[(ab,slot)]+=1
        teacher=teachers[idx % len(teachers)]
        br=bm.get((ab,slot),{})
        r13.append({"day":br.get("day",""),"abbr":ab,"slot":slot,"station":station,"teacher":teacher,"wait":0})
    for ab,slot,location in sorted(reqs):
        idx=byslot[(ab,slot)]; byslot[(ab,slot)]+=1
        teacher=teachers[idx % len(teachers)]
        br=bm.get((ab,slot),{})
        rs.append({"day":br.get("day",""),"abbr":ab,"slot":slot,"location":location,"teacher":teacher,"wait":0})
    audit=app._plan_snapshot_audit_v577(r13,rs,st)
    assert audit["ok"], audit
    return r13,rs,audit

def grouped_13(flat):
    rows={}
    for x in flat:
        key=(x.get("day"),x.get("abbr"),x.get("slot"))
        row=rows.setdefault(key,{"day":x.get("day"),"abbr":x.get("abbr"),"label":x.get("slot"),"assignments":[]})
        row["assignments"].append({"station":x.get("station"),"teacher":x.get("teacher"),"wait":x.get("wait",0)})
    return list(rows.values())
