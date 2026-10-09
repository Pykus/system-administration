import re
from pathlib import Path
root=Path(r"C:\DutySolverDemo\dyzury-v5.43-ortools")
html=(root/"static"/"index.html").read_text(encoding="utf-8")
src=(root/"app.py").read_text(encoding="utf-8")
defs=set(re.findall(r"(?:async\s+)?([A-Za-z_$][\w$]*)\([^)]*\)\{",html))
buttons=re.findall(r"<button\b[^>]*>",html,re.I)
no_action=[b for b in buttons if "@click" not in b and "type=\"submit\"" not in b and ":type" not in b]
print("BUTTONS",len(buttons),"NO_ACTION",len(no_action))
for b in no_action[:20]: print("NO_ACTION",re.sub(r"\s+"," ",b)[:220])
events=re.findall(r"@(click(?:\.stop)?|change|input|submit(?:\.prevent)?|keyup(?:\.[\w]+)?)=\"([^\"]+)\"",html)
known={"confirm","alert","prompt","Date","Number","String","Object","Array","Math","JSON","parseInt","parseFloat","setTimeout","clearTimeout"}
missing=set()
for evt,expr in events:
    for name in re.findall(r"(?<![.$\w])([A-Za-z_$][\w$]*)\s*\(",expr):
        if name not in defs and name not in known:
            missing.add((evt,name,expr))
print("EVENTS",len(events),"MISSING_CALLS",len(missing))
for x in sorted(missing)[:30]: print("MISSING",x)
print("--- ROUTE MUTATIONS WITHOUT JOB INVALIDATION ---")
route_re=re.compile(r'@app\.(post|put|patch|delete)\("([^"]+)"\)\s*\ndef ([^(]+)\([^)]*\):([\s\S]*?)(?=\n@app\.|\Z)')
for method,path,fn,body in route_re.findall(src):
    if "save_state(s)" in body and "_invalidate_active_repair_jobs" not in body:
        print(method.upper(),path,fn.strip())
print("--- PROFILE KEYS ---")
m=re.search(r"_PROFILE_STATE_KEYS=\(([^)]*)\)",src,re.S)
print(re.sub(r"\s+"," ",m.group(1)).strip() if m else "not found")
print("--- PROFILE UI ---")
for line in html.splitlines():
    if "profil" in line.lower() and ("ustaw" in line.lower() or "profile" in line.lower()):
        print(re.sub(r"\s+"," ",line.strip())[:400])
