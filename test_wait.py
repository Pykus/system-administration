import urllib.request,json,copy
base='http://127.0.0.1:8091'
def get(p): return json.load(urllib.request.urlopen(base+p))
def post(p,x):
 q=urllib.request.Request(base+p,data=json.dumps(x).encode(),headers={'Content-Type':'application/json'}); return json.load(urllib.request.urlopen(q))
c=get('/api/config');s=c['state'];orig=copy.deepcopy(s)
mins={b['abbr']+'|'+b['label']:2 for b in c['breaks']};mins['Wt|9/po']=1
post('/api/min-people-13',{'min_people_13':mins})
r=post('/api/solve/13',{'enabled_teachers':s['enabled_teachers_13'],'manual_blocks':s.get('manual_blocks',{})})
print(r['summary']);print([x for x in r['rows'] if x['abbr']=='Wt' and x['label']=='9/po'][0]);print(r['waits'])
open(r'C:\DutySolverDemo\dyzury-v5.1-ortools\data\state.json','w',encoding='utf-8').write(json.dumps(orig,ensure_ascii=False,indent=2))
