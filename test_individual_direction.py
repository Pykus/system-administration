import urllib.request,json,copy
base='http://127.0.0.1:8091'
def get(p):return json.load(urllib.request.urlopen(base+p))
def post(p,x):
 q=urllib.request.Request(base+p,data=json.dumps(x).encode(),headers={'Content-Type':'application/json'});return json.load(urllib.request.urlopen(q))
c=get('/api/config');s=c['state'];orig=copy.deepcopy(s);tb={t['name']:t for t in c['teachers']}
def rel(n,r):
 ps={int(k) for k in tb[n]['lessons'].get(r['abbr'],{})};hp=r.get('prev') in ps;hn=r.get('next') in ps
 return 'between' if hp and hn else ('before' if hn else ('after' if hp else 'none'))
try:
 b=post('/api/solve/13',{'enabled_teachers':s['enabled_teachers_13'],'manual_blocks':s.get('manual_blocks',{})})
 pair=next(( (r,a) for r in b['rows'] for a in r['assignments'] if a.get('teacher') and rel(a['teacher'],r)=='before'),None)
 if pair:
  r,a=pair;rules=copy.deepcopy(s.get('individual_constraints',[]));rules.append({'id':'dirtest','teacher':a['teacher'],'scope':'1–3','rule':'no_before_lesson','kind':'hard','priority':0,'day':'','slot':'','location':'','value':0,'enabled':True});post('/api/constraints',{'global':s['global_constraints'],'individual':rules});z=post('/api/solve/13',{'enabled_teachers':s['enabled_teachers_13'],'manual_blocks':s.get('manual_blocks',{})});bad=[(rr['abbr'],rr['label']) for rr in z['rows'] for aa in rr['assignments'] if aa.get('teacher')==a['teacher'] and rel(a['teacher'],rr)=='before'];print(a['teacher'],'viol',bad)
 else:print('no before assignment in baseline')
finally:open(r'C:\DutySolverDemo\dyzury-v5.1-ortools\data\state.json','w',encoding='utf-8').write(json.dumps(orig,ensure_ascii=False,indent=2))
