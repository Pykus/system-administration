from pathlib import Path
import sys, hashlib
root=Path(r"C:\DutySolverDemo\dyzury-v5.11-ortools")
sys.path.insert(0,str(root))
import app
cfg=app._farm_config()
ip=app._node_lan_ip()
sha=app._seed_sha()
text=f'''WORKER_VERSION="1.0.0"
VERSION="5.11"
SEED_SHA="{sha}"
TOKEN="{cfg["token"]}"
BROKER_URLS=["http://DEMO-AI-NODE00:{cfg["port"]}","http://{ip}:{cfg["port"]}"]
'''
(root/"worker_embedded_config.py").write_text(text,encoding="utf-8")
print("IP",ip,"PORT",cfg["port"],"SEED",sha)
