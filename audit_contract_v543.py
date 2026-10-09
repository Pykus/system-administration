import re, sys
from pathlib import Path
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT))
import app
html=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
routes=[]
for r in app.app.routes:
    p=getattr(r,'path',None)
    methods=sorted(getattr(r,'methods',[]) or [])
    if p and p.startswith('/api/'): routes.append((p,methods))
print('ROUTES',len(routes))
for p,m in sorted(routes): print(','.join(m),p)
print('--- FETCH URLS ---')
patterns=[
    r"fetch\(\s*'([^']+)'",
    r'fetch\(\s*"([^"]+)"',
    r"fetch\(\s*\`([^\`]+)\`",
]
urls=set()
for pat in patterns:
    urls.update(re.findall(pat,html))
for u in sorted(urls):
    if u.startswith('/api/'): print(u)
print('FETCH_COUNT',len([u for u in urls if u.startswith('/api/')]))
