import urllib.request,json
base='http://127.0.0.1:8091'
def get(p): return json.load(urllib.request.urlopen(base+p))
def post(p,x):
 q=urllib.request.Request(base+p,data=json.dumps(x).encode(),headers={'Content-Type':'application/json'}); return json.load(urllib.request.urlopen(q))
c=get('/api/config');s=c['state'];en=s['enabled_teachers_13'];bl=s.get('manual_blocks',{})
r=post('/api/solve/13',{'enabled_teachers':en,'manual_blocks':bl})
print('enabled',len(en),'Daniel', 'Piotr Wiśniewski' in en,'block',bl.get('Piotr Wiśniewski'))
print('summary',r['summary']);print('missing',r['unresolved_details']);print('incomplete',r['incomplete_breaks'])
print('limits',[(x['key'],x['value']) for x in s['global_constraints'] if x['key'] in ('max_day_13','max_week')])
