import json, time
import app

def score(order):
    t=time.perf_counter()
    if order=="school-first":
        school=app.solve_school({"other_rows_13":[]})
        r13=app.solve13({"reference_school":school["assignments"]})
    else:
        r13=app.solve13({"reference_school":[]})
        school=app.solve_school({"other_rows_13":r13["rows"]})
    dt=time.perf_counter()-t
    out={
        "order":order,
        "seconds":round(dt,3),
        "missing_13":r13["summary"]["unresolved"],
        "missing_school":school["summary"]["unresolved"],
        "missing_total":r13["summary"]["unresolved"]+school["summary"]["unresolved"],
        "filled_13":r13["summary"]["filled_positions"],
        "required_13":r13["summary"]["required_positions"],
        "filled_school":school["summary"]["filled_positions"],
        "required_school":school["summary"]["required_positions"],
        "cost_13":r13["summary"]["objective_cost"],
        "cost_school":school["summary"]["objective_cost"],
        "status_13":r13.get("diagnostics",{}).get("status"),
        "status_school":school.get("diagnostics",{}).get("status"),
    }
    return out

results=[score("school-first"),score("13-first")]
print(json.dumps(results,ensure_ascii=False,indent=2))
