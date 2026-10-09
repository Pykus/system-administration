from pathlib import Path
p=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools\worker_main.py")
s=p.read_text(encoding="utf-8")
s=s.replace("import json, os, socket, sys, time, uuid, urllib.request","import json, os, socket, sys, time, uuid, urllib.request, threading")
s=s.replace('PROGRAM=Path(os.environ.get("PROGRAMDATA",str(Path.home())))/"DEMO-DutySolverWorker"','PROGRAM=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"DEMO-DutySolverWorker"')
old='''        started=time.perf_counter()
        try: result=compute(t["payload"]);err=None
        except Exception as e: result=None;err=repr(e)
        elapsed=time.perf_counter()-started
'''
new='''        started=time.perf_counter()
        box={"result":None,"error":None}
        def _do_compute():
            try: box["result"]=compute(t["payload"])
            except Exception as e: box["error"]=repr(e)
        th=threading.Thread(target=_do_compute,daemon=True)
        th.start()
        while th.is_alive():
            th.join(4.0)
            if th.is_alive():
                try:req(base,"/worker/heartbeat",{"worker_id":WORKER_ID,"status":"busy","current_task":tid},5)
                except Exception:pass
        result,err=box["result"],box["error"]
        elapsed=time.perf_counter()-started
'''
if old not in s: raise SystemExit("worker compute anchor missing")
s=s.replace(old,new,1)
p.write_text(s,encoding="utf-8")
print("WORKER_PATCH_OK")
