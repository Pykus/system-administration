import copy,json,tempfile,sys
from pathlib import Path
ROOT=Path(r'C:\DutySolverDemo\dyzury-v5.43-ortools');sys.path.insert(0,str(ROOT));import app
orig=(app.STATE_PATH,app.REPAIR_JOBS);base=json.loads(app.STATE_PATH.read_text(encoding='utf-8'))
def run(name,fn):
 with tempfile.TemporaryDirectory() as td:
  app.STATE_PATH=Path(td)/'state.json';app.STATE_PATH.write_text(json.dumps(base,ensure_ascii=False),encoding='utf-8')
  app.REPAIR_JOBS={'j':{'id':'j','status':'running','_cancel':False,'auto_paused':False}}
  try: fn();j=app.REPAIR_JOBS['j'];print(name,bool(j.get('stale_due_to_manual_edit')),j.get('status'))
  except Exception as e: print(name,'ERROR',type(e).__name__,str(e)[:100])
def min13():
 s=app.load_state();x=copy.deepcopy(s.get('min_people_13',{}));k=next(iter(x),None)
 if k:x[k]=0 if int(x[k] or 0) else 1
 app.save_min_people_13({'min_people_13':x})
def minschool():
 s=app.load_state();x=copy.deepcopy(s.get('min_people_school',{}));k=next(iter(x),None)
 if k:x[k]=0 if int(x[k] or 0) else 1
 app.save_min_people_school({'min_people_school':x})
def addstation(): app.add_station_13({'name':'AUDIT_TDD'})
def locations():
 s=app.load_state();x=list(s.get('school_locations',[]));x.append('AUDIT_TDD');app.save_school_locations({'locations':x})
for n,f in [('min13',min13),('minschool',minschool),('station_add',addstation),('locations',locations)]:run(n,f)
app.STATE_PATH,app.REPAIR_JOBS=orig
