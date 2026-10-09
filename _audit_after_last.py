import json,urllib.request,copy,time,traceback
import app
OUT=[]
def log(*x): OUT.append(" ".join(str(z) for z in x))
try:
 base="http://127.0.0.1:8091"
 eff=json.load(urllib.request.urlopen(base+"/api/effective-plan",timeout=5))
 st=app.ensure_state_schema(copy.deepcopy(app.load_state()))
 by={}
 for a in eff["result_13"]:
  k=(a.get("day"),a.get("abbr"),a.get("slot"),a.get("time"))
  by.setdefault(k,[]).append({"station":a.get("station"),"teacher":a.get("teacher"),"wait":a.get("wait",0),"wait_kind":a.get("wait_kind","")})
 st["last_13_assignments"]=[{"day":k[0],"abbr":k[1],"label":k[2],"time":k[3],"assignments":v} for k,v in by.items()]
 st["school_assignments"]=copy.deepcopy(eff["result_school"])
 for r in st["global_constraints"]:
  if r.get("key")=="after_last_long":r["enabled"]=True;r["kind"]="hard";r["priority"]=5
 for n in list(st.get("teacher_relaxed_rules",{})):st["teacher_relaxed_rules"][n]=[x for x in (st["teacher_relaxed_rules"][n] or []) if x!="after_last_long"]
 bm=app.break_map();bad=[]
 for a in eff["result_school"]:
  br=bm.get((a.get("abbr"),a.get("slot")))
  if br and int(br.get("minutes",0) or 0)>10 and app.is_after_last_lesson(a.get("teacher"),br):
   bad.append({"scope":"szkoła","abbr":a["abbr"],"slot":a["slot"],"location":a["location"],"teacher":a["teacher"]})
 log("BAD",json.dumps(bad,ensure_ascii=True))
 for t in bad:
  good=[]
  for n in app.ALL:
   c,why=app._local_candidate(st,t["teacher"],t,n,[t])
   if c:good.append(c)
  good.sort(key=lambda x:(x["score"],app._teacher_sort_key(x["teacher"])))
  log("DIRECT",t["teacher"],t["abbr"],t["slot"],t["location"],json.dumps(good[:20],ensure_ascii=True))
 all_duties=app._all_current_duties(st)
 for t in bad:
  swaps=[]
  same=[x for x in all_duties if x.get("scope")=="szkoła" and x.get("abbr")==t["abbr"] and x.get("slot")==t["slot"] and x.get("teacher")!=t["teacher"]]
  for other in same:
   remove=[t,other]
   c1,w1=app._local_candidate(st,t["teacher"],t,other.get("teacher"),remove)
   c2,w2=app._local_candidate(st,other.get("teacher"),other,t["teacher"],remove)
   if c1 and c2:swaps.append({"with":other.get("teacher"),"other_place":other.get("location"),"score":c1["score"]+c2["score"]})
  swaps.sort(key=lambda x:x["score"]);log("SWAPS",t["teacher"],json.dumps(swaps[:20],ensure_ascii=True))
 current=[n for n in st.get("enabled_teachers_school",[]) if n in app.ALL and n not in set(st.get("excluded_teachers",[])) and n not in set(st.get("absent_teachers",[]))]
 general=[n for n in app.ALL if app.GROUP.get(n)=="school" and n not in set(st.get("excluded_teachers",[])) and n not in set(st.get("absent_teachers",[]))]
 nonwf=[n for n in app.ALL if app.GROUP.get(n)!="wf" and n not in set(st.get("excluded_teachers",[])) and n not in set(st.get("absent_teachers",[]))]
 allok=[n for n in app.ALL if n not in set(st.get("excluded_teachers",[])) and n not in set(st.get("absent_teachers",[]))]
 pools=[("current",current),("all_general",list(dict.fromkeys(current+general))),("all_nonwf",list(dict.fromkeys(current+nonwf))),("all_teachers",allok)]
 log("POOLS",json.dumps([(k,len(v)) for k,v in pools]))
 for label,pool in pools:
  t0=time.perf_counter();out=app._coverage(st,"szkoła",pool,other_override=eff["result_13"],preserve_override={},optimize=False);dt=round(time.perf_counter()-t0,3)
  dg=out["diagnostics"];log("STRICT",label,json.dumps({"filled":out["filled"],"required":out["required"],"missing":out["missing"],"inconclusive":out["inconclusive"],"after_min":dg.get("minimum_after_last_long"),"after_lex":dg.get("after_last_long_lex_status"),"seconds":dt},ensure_ascii=True))
except Exception:
 log("ERROR",traceback.format_exc())
open("_after_last_audit.txt","w",encoding="utf-8").write("\n".join(OUT))
