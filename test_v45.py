import urllib.request,json,copy
base='http://127.0.0.1:8091'
def get(p): return json.load(urllib.request.urlopen(base+p))
def post(p,x):
 q=urllib.request.Request(base+p,data=json.dumps(x).encode(),headers={'Content-Type':'application/json'})
 return json.load(urllib.request.urlopen(q))
c=get('/api/config');s=c['state'];orig=copy.deepcopy(s)
try:
 r=post('/api/solve/13',{'enabled_teachers':s['enabled_teachers_13'],'manual_blocks':s.get('manual_blocks',{})})
 print('BASE',r['summary'])
 g=copy.deepcopy(s['global_constraints'])
 next(x for x in g if x['key']=='no_before_lesson')['enabled']=True
 post('/api/constraints',{'global':g,'individual':s.get('individual_constraints',[])})
 a=post('/api/solve/13',{'enabled_teachers':s['enabled_teachers_13'],'manual_blocks':s.get('manual_blocks',{})})
 print('NO_BEFORE',a['summary'])
 next(x for x in g if x['key']=='no_before_lesson')['enabled']=False
 next(x for x in g if x['key']=='no_after_lesson')['enabled']=True
 post('/api/constraints',{'global':g,'individual':s.get('individual_constraints',[])})
 b=post('/api/solve/13',{'enabled_teachers':s['enabled_teachers_13'],'manual_blocks':s.get('manual_blocks',{})})
 print('NO_AFTER',b['summary'])
finally:
 open(r'C:\DutySolverDemo\dyzury-v5.1-ortools\data\state.json','w',encoding='utf-8').write(json.dumps(orig,ensure_ascii=False,indent=2))
