from pathlib import Path
root=Path(r"C:\DutySolverDemo\dyzury-v5.63-ortools")
def edit(rel, reps):
    p=root/rel
    s=p.read_text(encoding="utf-8")
    for old,new in reps:
        if old not in s:
            raise SystemExit(f"MISSING {rel}: {old!r}")
        s=s.replace(old,new)
    p.write_text(s,encoding="utf-8")
edit("app.py",[
('PLANNER_VERSION="5.62"','PLANNER_VERSION="5.63"'),
('LONG_BREAK_MINUTES=15','SHORT_BREAK_MAX_MINUTES=10\nLONG_BREAK_MINUTES=11'),
('edge_short=int(br.get("minutes",0) or 0)<=5','edge_short=int(br.get("minutes",0) or 0)<=SHORT_BREAK_MAX_MINUTES'),
('if not br or int(br.get("minutes",0) or 0)<=5:continue','if not br or int(br.get("minutes",0) or 0)<=SHORT_BREAK_MAX_MINUTES:continue'),
('short=minutes<=5','short=minutes<=SHORT_BREAK_MAX_MINUTES'),
('is_long=minutes>=15','is_long=minutes>=LONG_BREAK_MINUTES'),
('int(bb.get("minutes",0) or 0)>=15','int(bb.get("minutes",0) or 0)>=LONG_BREAK_MINUTES'),
('("after_last_long","przerwa >5 min po ostatniej lekcji")','("after_last_long","przerwa >10 min po ostatniej lekcji")'),
('("before_first_long","przerwa >5 min przed pierwszą lekcją")','("before_first_long","przerwa >10 min przed pierwszą lekcją")'),
('job["_working_hardened"]=["avoid_wait"]','job["_working_hardened"]=["avoid_wait","after_last_long","before_first_long"]'),
('hardened.add("avoid_wait")','hardened.update({"avoid_wait","after_last_long","before_first_long"})'),
('stage=4 if key=="avoid_wait" else 2','stage=4 if key=="avoid_wait" else (3 if key in {"after_last_long","before_first_long"} else 2)'),
('return (wait,foreign13,wf13,foreign_school,fair_dev,fair_ratio,after,before,consec,relax)','return (wait,after,before,consec,foreign13,wf13,foreign_school,fair_dev,fair_ratio,relax)'),
])
p=root/"app.py"; s=p.read_text(encoding="utf-8")
s=s.replace(">5 min",">10 min").replace("dłuższej niż 5 minut","dłuższej niż 10 minut").replace("krótka przerwa 5 min","krótka przerwa 5-10 min").replace("5-minutowej przerwy","krótkiej przerwy 5-10 min")
p.write_text(s,encoding="utf-8")
edit("solver_ortools.py",[
('PRIORITY_BASE={1:100,2:10_000,3:1_000_000,4:100_000_000,5:10_000_000_000}','PRIORITY_BASE={1:100,2:10_000,3:1_000_000,4:100_000_000,5:10_000_000_000}\nSHORT_BREAK_MAX_MINUTES=10\nLONG_BREAK_MINUTES=11'),
('int(br.get("minutes",0) or 0)>=15','int(br.get("minutes",0) or 0)>=LONG_BREAK_MINUTES'),
('long_threshold=15','long_threshold=LONG_BREAK_MINUTES'),
('edge_is_short=minutes<=5','edge_is_short=minutes<=SHORT_BREAK_MAX_MINUTES'),
])
p=root/"solver_ortools.py"; s=p.read_text(encoding="utf-8").replace(">5 min",">10 min").replace("5-minutowa przerwa","krótka przerwa 5-10 min"); p.write_text(s,encoding="utf-8")
p=root/"static"/"index.html"; s=p.read_text(encoding="utf-8")
s=s.replace("&gt;5 min","&gt;10 min").replace(">5 min",">10 min").replace("dłuższą niż 5 minut","dłuższą niż 10 minut").replace("także 10-minutową; nie tylko szkolne długie przerwy.","10-minutowa pozostaje krótką przerwą.").replace("gdzie próg wynosi 15 minut","gdzie długa przerwa zaczyna się powyżej 10 minut")
s=s.replace("NA ŻYWO — najlepszy pełny szkic #'+(w.seq||'?')+' · auto-odświeżanie","NA ŻYWO — najlepszy pełny szkic #'+(w.seq||'?')+' z '+(this.repairJob?.working_found_total||this.repairJob?.working_variants?.length||1)+' znalezionych · auto-odświeżanie")
p.write_text(s,encoding="utf-8")
p=root/"tests"/"test_v556_break_threshold_labels.py"; s=p.read_text(encoding="utf-8")
s=s.replace("over_five","over_ten").replace("&gt;5 min","&gt;10 min").replace(">5 min",">10 min").replace('self.assertEqual(app.LONG_BREAK_MINUTES,15)','self.assertEqual(app.LONG_BREAK_MINUTES,11)').replace("próg wynosi 15 minut","długa przerwa zaczyna się powyżej 10 minut").replace("także 10-minutową","10-minutowa pozostaje krótką przerwą")
p.write_text(s,encoding="utf-8")
print("PATCHED")