from pathlib import Path
import json
src=Path(r'C:\DutySolverDemo\dyzury-v4.4-final\data\state.json')
dst=Path(r'C:\DutySolverDemo\dyzury-v4.5-final\data\state.json')
cur=json.loads(src.read_text(encoding='utf-8')); tpl=json.loads(dst.read_text(encoding='utf-8'))
cur['version']='4.5'
cur.setdefault('min_people_13',tpl.get('min_people_13',{}))
keys={x.get('key') for x in cur.get('global_constraints',[])}
for x in tpl.get('global_constraints',[]):
    if x.get('key') in ('no_before_lesson','no_after_lesson') and x.get('key') not in keys: cur.setdefault('global_constraints',[]).append(x)
dst.write_text(json.dumps(cur,ensure_ascii=False,indent=2),encoding='utf-8')
print('merged',len(cur.get('global_constraints',[])),len(cur.get('individual_constraints',[])))
