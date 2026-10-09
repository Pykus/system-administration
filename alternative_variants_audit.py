import copy,json,sys
from pathlib import Path
ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.9-ortools")
sys.path.insert(0,str(ROOT))
import app

base=app.load_state()
e13=base.get("enabled_teachers_13",[])
es=base.get("enabled_teachers_school",[])

def setc(st,key,**kw):
    for r in st["global_constraints"]:
        if r.get("key")==key:
            r.update(kw); return

def cov13(st):
    return app._coverage(st,"1–3",e13,optimize=True)

def covschool(st,other):
    return app._coverage(st,"szkoła",es,other_override=app._flat13_other(other["assignments"]),optimize=True)

variants=[]
def add(name,mods):
    st=copy.deepcopy(base)
    for key,kw in mods:
        setc(st,key,**kw)
    a=cov13(st); b=covschool(st,a)
    variants.append({"name":name,
      "13":{"filled":a["filled"],"required":a["required"],"missing":a["missing"]},
      "school":{"filled":b["filled"],"required":b["required"],"missing":b["missing"]}})

add("BASE",[])
add("max_day_13=5",[("max_day_13",{"value":5})])
add("max_day_13=6",[("max_day_13",{"value":6})])
add("max_long_day=2",[("max_long_day",{"value":2})])
add("max_long_week=5",[("max_long_week",{"value":5})])
add("max_long_week=6",[("max_long_week",{"value":6})])
add("max_day13=5 + max_long_day=2",[("max_day_13",{"value":5}),("max_long_day",{"value":2})])
add("long_limits_soft",[("max_long_day",{"kind":"soft"}),("max_long_week",{"kind":"soft"})])
add("max_day13=5 + long_limits_soft",[("max_day_13",{"value":5}),("max_long_day",{"kind":"soft"}),("max_long_week",{"kind":"soft"})])
add("max_day_school=5",[("max_day_school",{"value":5})])
add("max_day_school=5 + long_limits_soft",[("max_day_school",{"value":5}),("max_long_day",{"kind":"soft"}),("max_long_week",{"kind":"soft"})])
print(json.dumps({"enabled13":len(e13),"enabledSchool":len(es),"variants":variants},ensure_ascii=False,indent=2))
(ROOT/"ALTERNATIVE-VARIANTS-AUDIT-v5.9.json").write_text(json.dumps({"enabled13":len(e13),"enabledSchool":len(es),"variants":variants},ensure_ascii=False,indent=2),encoding="utf-8")
