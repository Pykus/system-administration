import json, urllib.request
base="http://127.0.0.1:8091"
def get(path):
    with urllib.request.urlopen(base+path, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

cfg=get("/api/config?pdf-final=1")
plan=get("/api/effective-plan")
st=cfg["state"]
rows=[]
for mode in ("all","duties","lessons"):
    payload={
        "layout":"teacher_grid",
        "view_mode":mode,
        "assignments_13":plan.get("result_13",[]),
        "school_assignments":plan.get("result_school",[]),
        "teachers":cfg.get("teachers",[]),
        "timeline":cfg.get("timeline",{}),
        "station_names":st.get("station_names",{}),
        "station_order_13":st.get("station_order_13",[]),
        "plan_revision":st.get("plan_revision",0),
        "scopes":{"show13":True,"showSchool":True,"showGym":True},
    }
    req=urllib.request.Request(
        base+"/api/export/plan-pdf",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type":"application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data=r.read()
        rows.append({
            "mode":mode,
            "status":r.status,
            "content_type":r.headers.get("Content-Type"),
            "disposition":r.headers.get("Content-Disposition"),
            "bytes":len(data),
            "pdf":data.startswith(b"%PDF"),
        })
print(json.dumps({"ok":all(x["status"]==200 and x["pdf"] and x["bytes"]>1000 for x in rows),"rows":rows},ensure_ascii=False))
