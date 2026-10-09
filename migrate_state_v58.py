import sys
from pathlib import Path
root=Path(r'C:\DutySolverDemo\dyzury-v5.8-ortools')
sys.path.insert(0,str(root))
import app
s=app.load_state()
app.save_state(s)
cm={x['key']:x for x in s.get('global_constraints',[])}
print('MIGRATION_OK',len(s.get('school_locations',[])),len(s.get('min_people_school',{})),cm['before_first_long']['kind'],cm['after_last_long']['kind'])
