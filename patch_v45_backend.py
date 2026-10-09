from pathlib import Path
import json
root=Path(r'C:\DutySolverDemo\dyzury-v4.5-final')
p=root/'app.py'
s=p.read_text(encoding='utf-8')
s=s.replace('version="4.4"','version="4.5"')
old='''def adjacent_wait(name,br,state,scope):\n    cs=cdict(state)\n    ps=lesson_periods(name,br["abbr"])\n    if br["prev"] in ps or br["next"] in ps: return 0\n    if not cs.get("adjacent_lesson",{}).get("enabled",True): return 0\n    if state.get("allow_wait_one_period",True) and br["next"] is None and br["prev"] and br["prev"]-1 in ps:\n        return 1\n    return None\n'''
new='''def lesson_relation(name,br):\n    ps=lesson_periods(name,br["abbr"])\n    has_prev=br.get("prev") in ps\n    has_next=br.get("next") in ps\n    if has_prev and has_next: return "between"\n    if has_next: return "before"\n    if has_prev: return "after"\n    if br.get("next") is None and br.get("prev") and br["prev"]-1 in ps: return "wait_after"\n    return "none"\n\ndef directional_individual_effect(state,name,scope,relation):\n    hard=False; cost=0\n    for r in active_individual(state,name,scope):\n        typ=r.get("rule"); mode=r.get("kind","hard"); pr=int(r.get("priority") or 0)\n        hit=(typ=="no_before_lesson" and relation=="before") or (typ=="no_after_lesson" and relation in ("after","wait_after"))\n        if hit:\n            if mode=="hard": hard=True\n            else: cost+=pr\n    return hard,cost\n\ndef adjacent_wait(name,br,state,scope):\n    cs=cdict(state); rel=lesson_relation(name,br)\n    if rel=="between": return 0\n    if rel=="before":\n        return None if cs.get("no_before_lesson",{}).get("enabled",False) else 0\n    if rel=="after":\n        return None if cs.get("no_after_lesson",{}).get("enabled",False) else 0\n    if not cs.get("adjacent_lesson",{}).get("enabled",True): return 0\n    if rel=="wait_after" and state.get("allow_wait_one_period",True) and not cs.get("no_after_lesson",{}).get("enabled",False):\n        return 1\n    return None\n'''
assert old in s
s=s.replace(old,new)
old2='''            hard,idmaxd,idmaxw,icost=individual_effect(state,n,scope,br["abbr"],br["label"],location)\n            if hard: continue\n            wait=adjacent_wait(n,br,state,scope)\n'''
new2='''            hard,idmaxd,idmaxw,icost=individual_effect(state,n,scope,br["abbr"],br["label"],location)\n            rel=lesson_relation(n,br)\n            dhard,dcost=directional_individual_effect(state,n,scope,rel)\n            if hard or dhard: continue\n            icost+=dcost\n            wait=adjacent_wait(n,br,state,scope)\n'''
assert old2 in s
s=s.replace(old2,new2)
p.write_text(s,encoding='utf-8')
sp=root/'data'/'state.json'; st=json.loads(sp.read_text(encoding='utf-8')); st['version']='4.5'
keys={c.get('key') for c in st.get('global_constraints',[])}
add=[]
if 'no_before_lesson' not in keys:add.append({'key':'no_before_lesson','label':'Zakaz dyżuru tylko przed lekcją','scope':'oba','enabled':False,'kind':'hard','priority':None,'value':None,'description':'Nie przydzielaj dyżuru, gdy nauczyciel ma lekcję tylko po tej przerwie. Przerwa między dwiema lekcjami pozostaje dozwolona.'})
if 'no_after_lesson' not in keys:add.append({'key':'no_after_lesson','label':'Zakaz dyżuru tylko po lekcji','scope':'oba','enabled':False,'kind':'hard','priority':None,'value':None,'description':'Nie przydzielaj dyżuru, gdy nauczyciel ma lekcję tylko przed tą przerwą. Przerwa między dwiema lekcjami pozostaje dozwolona; zakaz obejmuje też awaryjne oczekiwanie po ostatniej lekcji.'})
st.setdefault('global_constraints',[]).extend(add)
sp.write_text(json.dumps(st,ensure_ascii=False,indent=2),encoding='utf-8')
seedp=root/'data'/'seed.json'; seed=json.loads(seedp.read_text(encoding='utf-8')); seed['version']='4.5'; seedp.write_text(json.dumps(seed,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print('backend patched',len(add))
