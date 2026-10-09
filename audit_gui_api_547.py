import re
from pathlib import Path
root=Path(r"C:\DutySolverDemo\dyzury-v5.46-ortools")
html=(root/"static"/"index.html").read_text(encoding="utf-8")
src=(root/"app.py").read_text(encoding="utf-8")

# Extract frontend methods approximately by top-level object method starts.
starts=list(re.finditer(r"(?m)^(?:async\s+)?([A-Za-z_$][\w$]*)\([^\n]*?\)\{",html))
print("FETCH METHODS WITHOUT ok/status CHECK")
for i,m in enumerate(starts):
    end=starts[i+1].start() if i+1<len(starts) else len(html)
    body=html[m.start():end]
    if "fetch(" in body and ".ok" not in body and ".status" not in body:
        urls=re.findall(r"fetch\(([^,\n]+)",body)
        print(m.group(1),"::", " | ".join(u[:120] for u in urls))

print("--- DYNAMIC FETCH LITERAL CONTRACT ---")
routes=[]
for mm in re.finditer(r'@app\.(?:get|post|put|patch|delete)\("([^"]+)"\)',src):
    routes.append(mm.group(1))
fetch_args=re.findall(r"fetch\(([^\n;]+?)(?:,\{|\))",html)
seen=set()
for expr in fetch_args:
    if "/api/" not in expr: continue
    lits=re.findall(r"['\"]([^'\"]*)['\"]",expr)
    lits=[x.split("?")[0] for x in lits if x]
    if not lits: continue
    key=tuple(lits)
    if key in seen:continue
    seen.add(key)
    ok=False
    for route in routes:
        pos=0; good=True
        for lit in lits:
            j=route.find(lit,pos)
            if j<0: good=False;break
            pos=j+len(lit)
        if good:ok=True;break
    if not ok: print("UNMATCHED",expr[:240],"LITS",lits)
print("FETCH_FAMILIES",len(seen),"ROUTES",len(routes))
