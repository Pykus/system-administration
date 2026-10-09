from html.parser import HTMLParser
from pathlib import Path
import re
html=Path(r"C:\DutySolverDemo\dyzury-v5.43-ortools\static\index.html").read_text(encoding="utf-8")
class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.buttons=[]; self.inputs=[]; self.selects=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="button": self.buttons.append(d)
        elif tag=="input": self.inputs.append(d)
        elif tag=="select": self.selects.append(d)
p=P();p.feed(html)
def handlers(d):
    return [k for k in d if k and k.startswith("@")]
bad=[d for d in p.buttons if not handlers(d) and d.get("type")!="submit"]
print("BUTTONS",len(p.buttons),"NO_EVENT",len(bad))
for d in bad: print("BUTTON_NO_EVENT",d)
for typ,rows in [("INPUT",p.inputs),("SELECT",p.selects)]:
    interactive=[d for d in rows if d.get("disabled") is None and d.get(":disabled") is None]
    no_model=[d for d in interactive if not handlers(d) and "v-model" not in d and "v-model.number" not in d and d.get("type") not in ("hidden","file")]
    print(typ,"TOTAL",len(rows),"NO_MODEL_OR_EVENT",len(no_model))
    for d in no_model[:20]: print(typ+"_NO_BIND",d)
print("--- PROFILE / STATE SYNC ---")
for name in ["syncWorkingState","saveAdvanced","saveSettingsProfile","loadSettingsProfile"]:
    m=re.search(r"(?:async\s+)?"+name+r"\([^)]*\)\{([\s\S]*?)(?=\n(?:async\s+)?[A-Za-z_$][\w$]*\([^)]*\)\{|\Z)",html)
    print(name,(m.group(1)[:1600] if m else "MISSING").replace("\n"," "))
