from __future__ import annotations
import json, sqlite3, time, uuid
from pathlib import Path

ROOT=Path(__file__).parent
SHARED_FARM_ROOT=Path(r"C:\DutySolverDemo\DEMO-WorkerFarm")
DB=SHARED_FARM_ROOT/"repair_farm.sqlite"

def _con():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=15,isolation_level=None)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=15000")
    return c

def init():
    with _con() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS workers(
          worker_id TEXT PRIMARY KEY, hostname TEXT, version TEXT, seed_sha TEXT,
          cpu_count INTEGER, status TEXT, current_task TEXT, last_seen REAL,
          completed INTEGER DEFAULT 0, failed INTEGER DEFAULT 0,
          total_seconds REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tasks(
          task_id TEXT PRIMARY KEY, job_id TEXT, version TEXT, seed_sha TEXT,
          payload TEXT, status TEXT, assigned_worker TEXT,
          created_at REAL, leased_at REAL, completed_at REAL,
          result TEXT, error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status,created_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_job ON tasks(job_id,status);
        CREATE INDEX IF NOT EXISTS idx_tasks_worker ON tasks(assigned_worker,status);
        """)
        cols={r[1] for r in c.execute("PRAGMA table_info(tasks)")}
        if "elapsed_seconds" not in cols:
            c.execute("ALTER TABLE tasks ADD COLUMN elapsed_seconds REAL")

def register(worker_id,hostname,version,seed_sha,cpu_count):
    init(); now=time.time()
    with _con() as c:
        # A worker process restart invalidates any task it leased before restart.
        c.execute("UPDATE tasks SET status='pending',assigned_worker=NULL,leased_at=NULL WHERE status='leased' AND assigned_worker=?",(worker_id,))
        # One physical computer = one worker card. A redeploy may generate a new
        # worker_id, but an old record for the same hostname must not remain.
        old=list(c.execute(
            "SELECT worker_id,completed,failed,total_seconds FROM workers WHERE lower(hostname)=lower(?) AND worker_id<>?",
            (hostname,worker_id)))
        old_ids=[r["worker_id"] for r in old]
        carry_completed=sum(int(r["completed"] or 0) for r in old)
        carry_failed=sum(int(r["failed"] or 0) for r in old)
        carry_seconds=sum(float(r["total_seconds"] or 0) for r in old)
        if old_ids:
            q=",".join("?"*len(old_ids))
            c.execute(f"UPDATE tasks SET status='pending',assigned_worker=NULL,leased_at=NULL WHERE status='leased' AND assigned_worker IN ({q})",old_ids)
            c.execute(f"DELETE FROM workers WHERE worker_id IN ({q})",old_ids)
        c.execute("""INSERT INTO workers(worker_id,hostname,version,seed_sha,cpu_count,status,current_task,last_seen,completed,failed,total_seconds)
          VALUES(?,?,?,?,?,'idle','',?,?,?,?)
          ON CONFLICT(worker_id) DO UPDATE SET hostname=excluded.hostname,version=excluded.version,
          seed_sha=excluded.seed_sha,cpu_count=excluded.cpu_count,last_seen=excluded.last_seen,status='idle'""",
          (worker_id,hostname,version,seed_sha,int(cpu_count or 1),now,0,0,0))
        if old_ids:
            c.execute("UPDATE workers SET completed=completed+?,failed=failed+?,total_seconds=total_seconds+? WHERE worker_id=?",
                      (carry_completed,carry_failed,carry_seconds,worker_id))
    return worker_id

def heartbeat(worker_id,status="idle",current_task=""):
    init()
    with _con() as c:
        c.execute("UPDATE workers SET last_seen=?,status=?,current_task=? WHERE worker_id=?",
                  (time.time(),status,current_task or "",worker_id))

def reset_stale(stale_seconds=90):
    init(); cutoff=time.time()-stale_seconds
    with _con() as c:
        stale=[r["worker_id"] for r in c.execute("SELECT worker_id FROM workers WHERE last_seen<?",(cutoff,))]
        if stale:
            q=",".join("?"*len(stale))
            c.execute(f"UPDATE tasks SET status='pending',assigned_worker=NULL,leased_at=NULL WHERE status='leased' AND assigned_worker IN ({q})",stale)
            c.execute(f"UPDATE workers SET status='offline',current_task='' WHERE worker_id IN ({q})",stale)

def active_workers(version=None,seed_sha=None,within=90):
    reset_stale()
    q="SELECT * FROM workers WHERE last_seen>=?"; args=[time.time()-within]
    if version is not None: q+=" AND version=?";args.append(version)
    if seed_sha is not None: q+=" AND seed_sha=?";args.append(seed_sha)
    with _con() as c:return [dict(r) for r in c.execute(q,args)]

def enqueue(job_id,version,seed_sha,payload):
    init(); tid=uuid.uuid4().hex
    with _con() as c:
        c.execute("INSERT INTO tasks(task_id,job_id,version,seed_sha,payload,status,created_at) VALUES(?,?,?,?,?,'pending',?)",
                  (tid,job_id,version,seed_sha,json.dumps(payload,ensure_ascii=False,separators=(",",":")),time.time()))
    return tid

def lease(worker_id,version,seed_sha):
    init(); reset_stale()
    with _con() as c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT * FROM tasks WHERE status='pending' AND version=? AND seed_sha=? ORDER BY created_at LIMIT 1",
                      (version,seed_sha)).fetchone()
        if not row:
            c.execute("COMMIT");return None
        now=time.time()
        c.execute("UPDATE tasks SET status='leased',assigned_worker=?,leased_at=? WHERE task_id=? AND status='pending'",
                  (worker_id,now,row["task_id"]))
        c.execute("UPDATE workers SET status='busy',current_task=?,last_seen=? WHERE worker_id=?",
                  (row["task_id"],now,worker_id))
        c.execute("COMMIT")
        out=dict(row);out["payload"]=json.loads(out["payload"]);return out

def submit(worker_id,task_id,result=None,error=None,elapsed=0):
    init(); now=time.time(); status="failed" if error else "done"
    with _con() as c:
        cur=c.execute("UPDATE tasks SET status=?,result=?,error=?,completed_at=?,elapsed_seconds=? WHERE task_id=? AND assigned_worker=? AND status='leased'",
                  (status,json.dumps(result,ensure_ascii=False,separators=(",",":")) if result is not None else None,
                   str(error or ""),now,float(elapsed or 0),task_id,worker_id))
        accepted=(cur.rowcount==1)
        if accepted:
            c.execute("""UPDATE workers SET status='idle',current_task='',last_seen=?,
                      completed=completed+?,failed=failed+?,total_seconds=total_seconds+? WHERE worker_id=?""",
                      (now,0 if error else 1,1 if error else 0,float(elapsed or 0),worker_id))
        else:
            c.execute("UPDATE workers SET last_seen=? WHERE worker_id=?",(now,worker_id))
    return accepted

def get_task(task_id):
    init()
    with _con() as c:
        r=c.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
    if not r:return None
    out=dict(r)
    if out.get("result"):
        try:out["result"]=json.loads(out["result"])
        except Exception:pass
    return out

def cancel_task(task_id):
    init()
    with _con() as c:c.execute("UPDATE tasks SET status='cancelled' WHERE task_id=? AND status IN ('pending','leased')",(task_id,))

def cancel_job(job_id):
    init()
    with _con() as c:c.execute("UPDATE tasks SET status='cancelled' WHERE job_id=? AND status IN ('pending','leased')",(job_id,))

def status(current_job_id=None):
    init();reset_stale(stale_seconds=180)
    with _con() as c:
        workers=[dict(r) for r in c.execute("SELECT * FROM workers ORDER BY hostname")]
        counts={r["status"]:r["n"] for r in c.execute("SELECT status,COUNT(*) n FROM tasks GROUP BY status")}
        task_info={}
        tids=[]
        for w in workers:
            tids.extend([x for x in str(w.get("current_task") or "").split(",") if x])
        for tid in dict.fromkeys(tids):
            row=c.execute("SELECT task_id,job_id,status,payload,leased_at FROM tasks WHERE task_id=?",(tid,)).fetchone()
            if row:
                x=dict(row)
                try:
                    payload=json.loads(x.get("payload") or "{}")
                    x["tokens"]=payload.get("tokens",[])
                except Exception:x["tokens"]=[]
                x.pop("payload",None);task_info[tid]=x
        current_stats={}
        if current_job_id:
            for r in c.execute("""SELECT assigned_worker,
                    SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) done_n,
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) failed_n,
                    AVG(CASE WHEN status='done' THEN elapsed_seconds END) avg_s
                    FROM tasks WHERE job_id=? AND assigned_worker IS NOT NULL
                    GROUP BY assigned_worker""",(current_job_id,)):
                current_stats[r["assigned_worker"]]={"job_completed":int(r["done_n"] or 0),
                    "job_failed":int(r["failed_n"] or 0),"job_avg_seconds":round(float(r["avg_s"] or 0),2)}
    now=time.time()
    for w in workers:
        # Portable worker polls every 30 s. 90 s avoids false offline flicker.
        w["online"]=bool(w.get("last_seen",0)>=now-90)
        w["last_seen_seconds"]=round(max(0,now-w.get("last_seen",0)),1)
        done=int(w.get("completed",0) or 0)
        w["avg_seconds"]=round(float(w.get("total_seconds",0) or 0)/done,2) if done else 0
        ids=[x for x in str(w.get("current_task") or "").split(",") if x]
        infos=[task_info[x] for x in ids if x in task_info]
        w["current_job_id"]=next((x.get("job_id") for x in infos if x.get("job_id")),None)
        toks=[]
        for x in infos:
            for tok in x.get("tokens",[]):
                if tok not in toks:toks.append(tok)
        w["current_tokens"]=toks
        w["task_seconds"]=round(max([max(0,now-float(x.get("leased_at") or now)) for x in infos] or [0]),1)
        w["active_tasks"]=len(infos)
        w.update(current_stats.get(w.get("worker_id"),{"job_completed":0,"job_failed":0,"job_avg_seconds":0}))
    return {"workers":workers,"tasks":counts,"current_job_id":current_job_id}

init()
