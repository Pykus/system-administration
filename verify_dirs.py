import urllib.request,json,copy
base='http://127.0.0.1:8091'
def get(p): return json.load(urllib.request.urlopen(base+p))
def post(p,x):
 q=urllib.request.Request(base+p,data=json.dumps(x).encode(),headers={'Content-Type':'application/json'})
 return json.load(urllib.request.urlopen(q))
c=get('/api/config');s=c['state'];orig=copy.deepcopy(s);tb={t['name']:t for t in c['teachers']}
def relation(n,r):
 ps={int(k) for k in tb[n]['lessons'].get(r['abbr'],{})}; hp=r.get('prev') in ps; hn=r.get('next') in ps
 if hp and hn:return 'between'
 if hn:return 'before'
 if hp:return 'after'
 if r.get('next') is None and r.get('prev') and r['prev']-1 in ps:return 'wait_after'
 return 'none'
def run(key,banned):
 g=copy.deepcopy(s['global_constraints'])
 for x in g:
  if x['key'] in ('no_before_lesson','no_after_lesson'):x['enabled']=(x['key']==key)
 post('/api/constraints',{'global':g,'individual':s.get('individual_constraints',[])})
 r=post('/api/solve/13',{'enabled_teachers':s['enabled_teachers_13'],'manual_blocks':s.get('manual_blocks',{})})
 bad=[(z['abbr'],z['label'],a['teacher'],relation(a['teacher'],z)) for z in r['rows'] for a in z['assignments'] if a.get('teacher') and relation(a['teacher'],z) in banned]
 print(key,'violations',len(bad),bad[:3])
try:
 run('no_before_lesson',{'before'});run('no_after_lesson',{'after','wait_after'})
finally:open(r'C:\DutySolverDemo\dyzury-v5.1-ortools\data\state.json','w',encoding='utf-8').write(json.dumps(orig,ensure_ascii=False,indent=2))
