from pathlib import Path
import subprocess, tempfile, shutil, re, json, sys

root=Path(r"C:\DutySolverDemo\dyzury-v5.19-ortools")
p=root/"static"/"index.html"
edge=Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
original=p.read_text(encoding="utf-8")
tabs=["13","school","teachers","teacherAdmin","teacherPortal","diagnostics","advanced","variants"]
rows=[]
capture="""<script>const __ce=console.error;console.error=(...a)=>{try{let e=document.getElementById('__console_errors');if(!e){e=document.createElement('pre');e.id='__console_errors';document.body.appendChild(e)}e.textContent+='\\n'+a.map(x=>String(x)).join(' ')}catch(_){};__ce(...a)};"""
try:
    for tab in tabs:
        s=re.sub(r"cfg:null,mainTab:'[^']+'",f"cfg:null,mainTab:'{tab}'",original,count=1)
        s=s.replace("<script>",capture,1)
        p.write_text(s,encoding="utf-8")
        ud=Path(tempfile.mkdtemp(prefix="edge_v519_"))
        try:
            cp=subprocess.run([str(edge),"--headless=new","--disable-gpu","--no-first-run",f"--user-data-dir={ud}","--virtual-time-budget=2500","--dump-dom","http://127.0.0.1:8092"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=15)
            dom=cp.stdout
            m=re.search(r'<pre id="__console_errors">(.*?)</pre>',dom,re.S)
            err=(m.group(1).strip() if m else "")
            rows.append({"tab":tab,"dom_len":len(dom),"error":err})
        finally:
            shutil.rmtree(ud,ignore_errors=True)
finally:
    p.write_text(original,encoding="utf-8")
bad=[x for x in rows if x["error"] or x["dom_len"]<50000]
print(json.dumps({"ok":not bad,"rows":rows,"bad":bad},ensure_ascii=False,indent=2))
sys.exit(1 if bad else 0)

