from pathlib import Path
import json
p=Path(r'C:\DutySolverDemo\dyzury-v4.4-final\data\seed.json')
s=json.loads(p.read_text(encoding='utf-8'))
s['version']='4.4'
p.write_text(json.dumps(s,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print('seed',s['version'])
