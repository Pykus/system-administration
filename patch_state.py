from pathlib import Path
import json
root=Path(r'C:\DutySolverDemo\dyzury-v4.4-final')
sp=root/'data'/'state.json'
st=json.loads(sp.read_text(encoding='utf-8'))
seed=json.loads((root/'data'/'seed.json').read_text(encoding='utf-8'))
st['version']='4.4'
st.setdefault('min_people_13',{})
for b in seed['breaks']:
    st['min_people_13'].setdefault(b['abbr']+'|'+b['label'],2)
sp.write_text(json.dumps(st,ensure_ascii=False,indent=2),encoding='utf-8')
print('OK',len(st['min_people_13']))
