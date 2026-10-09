from pathlib import Path
import re

ROOT=Path(r"C:\DutySolverDemo\dyzury-v5.8-ortools")
APP=ROOT/"app.py"
SOL=ROOT/"solver_ortools.py"
UI=ROOT/"static"/"index.html"
TP=ROOT/"static"/"teacher.html"

def rep(text, old, new, label, count=1):
    if old not in text:
        raise SystemExit("ANCHOR MISSING: "+label)
    return text.replace(old,new,count)

# ---------- solver ----------
s=SOL.read_text(encoding="utf-8")
old='''def _is_after_last_lesson(tby,name,br):
    ps=_lesson_periods(tby,name,br["abbr"])
    prev=br.get("prev")
    return bool(ps and prev in ps and int(prev)==max(ps))

def _relation(tby,name,br):
'''
new='''def _is_before_first_lesson(tby,name,br):
    ps=_lesson_periods(tby,name,br["abbr"])
    nxt=br.get("next")
    return bool(ps and nxt in ps and int(nxt)==min(ps))

def _is_after_last_lesson(tby,name,br):
    ps=_lesson_periods(tby,name,br["abbr"])
    prev=br.get("prev")
    return bool(ps and prev in ps and int(prev)==max(ps))

def _lesson_count(tby,name):
    return sum(len(periods or {}) for periods in tby.get(name,{}).get("lessons",{}).values())

def _relation(tby,name,br):
'''
s=rep(s,old,new,"before-first helper")

old='''def _individual_direction(state,name,scope,relation):
    hard=[]; cost=0
    for r in _active_individual(state,name,scope):
        typ=r.get("rule")
        hit=(typ=="no_before_lesson" and relation=="before") or (typ=="no_after_lesson" and relation in ("after","wait_after"))
        if not hit: continue
        if _kind(r)=="hard": hard.append("reguła indywidualna: "+typ)
        else: cost+=PRIORITY_BASE[normalize_priority(r.get("priority",3))]
    return hard,cost
'''
new='''def _individual_direction(state,name,scope,before_first,after_last):
    hard=[]; cost=0
    for r in _active_individual(state,name,scope):
        typ=r.get("rule")
        hit=(typ=="no_before_lesson" and before_first) or (typ=="no_after_lesson" and after_last)
        if not hit: continue
        if _kind(r)=="hard": hard.append("reguła indywidualna: "+typ)
        else: cost+=PRIORITY_BASE[normalize_priority(r.get("priority",3))]
    return hard,cost
'''
s=rep(s,old,new,"individual first-last semantics")

old='''            rel=_relation(tby,n,br)
            is_long=int(br.get("minutes",0) or 0)>=long_threshold
            after_last=_is_after_last_lesson(tby,n,br)
            dh,dc=_individual_direction(state,n,scope,rel); reasons.extend(dh); cost+=dc
            if rel=="before":
                if _mode(cs,"no_before_lesson")=="hard": reasons.append("dyżur tylko przed lekcją")
                elif _mode(cs,"no_before_lesson")=="soft": cost+=_weight(state,"no_before_lesson",4)
            if after_last:
                key="after_last_long" if is_long else "after_last_short"
                label="długa przerwa po ostatniej lekcji" if is_long else "krótka przerwa po ostatniej lekcji"
                if _mode(cs,key)=="hard": reasons.append(label)
                elif _mode(cs,key)=="soft": cost+=_weight(state,key,4 if is_long else 1)
'''
new='''            rel=_relation(tby,n,br)
            minutes=int(br.get("minutes",0) or 0)
            is_long=minutes>=long_threshold
            edge_is_short=minutes<=5
            before_first=_is_before_first_lesson(tby,n,br)
            after_last=_is_after_last_lesson(tby,n,br)
            dh,dc=_individual_direction(state,n,scope,before_first,after_last); reasons.extend(dh); cost+=dc
            if before_first:
                key="before_first_short" if edge_is_short else "before_first_long"
                label="5-minutowa przerwa przed pierwszą lekcją" if edge_is_short else "przerwa >5 min przed pierwszą lekcją"
                if _mode(cs,key)=="hard": reasons.append(label)
                elif _mode(cs,key)=="soft": cost+=_weight(state,key,1 if edge_is_short else 5)
            if after_last:
                key="after_last_short" if edge_is_short else "after_last_long"
                label="5-minutowa przerwa po ostatniej lekcji" if edge_is_short else "przerwa >5 min po ostatniej lekcji"
                if _mode(cs,key)=="hard": reasons.append(label)
                elif _mode(cs,key)=="soft": cost+=_weight(state,key,1 if edge_is_short else 5)
'''
s=rep(s,old,new,"first-last break policy")

pattern=r'''    # Opcjonalna sprawiedliwość proporcjonalna do współczynnika pensum/obciążenia\.
    if _enabled\(cs,"workload_fairness"\) and by_teacher_week:
.*?
    for key,rule_key,base_counts,groups in \['''
m=re.search(pattern,s,re.S)
if not m:
    raise SystemExit("ANCHOR MISSING: fairness block")
new='''    # v5.8: dwie jawne warstwy sprawiedliwości.
    # - lesson_load_fairness: udział proporcjonalny do liczby lekcji w tygodniu,
    # - workload_fairness: ręczna waga udziału; gdy obie są aktywne, jest mnożnikiem korekcyjnym.
    manual_fair=_enabled(cs,"workload_fairness")
    lesson_fair=_enabled(cs,"lesson_load_fairness")
    if (manual_fair or lesson_fair) and by_teacher_week:
        names=list(by_teacher_week)
        factors={}
        for n in names:
            try: manual=max(0.1,float(state.get("teacher_workload",{}).get(n,1.0)))
            except Exception: manual=1.0
            lessons=max(0,_lesson_count(tby,n))
            if lesson_fair:
                raw=float(lessons)
                if manual_fair: raw*=manual
            else:
                raw=manual
            factors[n]=max(0,int(round(raw*100)))
        sum_factor=sum(factors.values())
        if sum_factor<=0:
            factors={n:100 for n in names}
            sum_factor=100*len(names)
        combined_required=len(positions)+sum(base_week[n] for n in names)
        active_keys=[k for k,on in (("lesson_load_fairness",lesson_fair),("workload_fairness",manual_fair)) if on]
        mode="hard" if any(_mode(cs,k)=="hard" for k in active_keys) else "soft"
        weight=max([_weight(state,k,2) for k in active_keys] or [PRIORITY_BASE[2]])
        for n in names:
            vars_=by_teacher_week[n]; total=sum(vars_)+base_week[n]
            target=int(round(combined_required*factors[n]/sum_factor))
            if mode=="hard":
                model.Add(total>=max(0,target-1)); model.Add(total<=target+1)
            else:
                dev=model.NewIntVar(0,len(positions)+base_week[n],f"workload_dev_{abs(hash(n))%10**8}")
                model.AddAbsEquality(dev,total-target)
                objective.append(weight*dev)

    for key,rule_key,base_counts,groups in ['''
s=s[:m.start()]+new+s[m.end():]
SOL.write_text(s,encoding="utf-8")

# ---------- backend/schema ----------
s=APP.read_text(encoding="utf-8")
s=s.replace('version="5.7"','version="5.8"')
s=s.replace('"version":"5.7"','"version":"5.8"')

old='''        if key=="max_long_day":
            try: r["value"]=min(2,max(0,int(r.get("value",1))))
            except Exception: r["value"]=1
        elif key=="max_long_week":
'''
new='''        if key in {"before_first_long","after_last_long"}:
            r["enabled"]=True
            r["kind"]="hard"
            r["priority"]=5
        if key=="max_long_day":
            try: r["value"]=min(2,max(0,int(r.get("value",1))))
            except Exception: r["value"]=1
        elif key=="max_long_week":
'''
s=rep(s,old,new,"mandatory long edge constraints")

old='''    rows=[r for r in normalize_constraint_rows(state.get("global_constraints",[])) if r.get("key")!="no_after_lesson"]
'''
new='''    rows=[r for r in normalize_constraint_rows(state.get("global_constraints",[])) if r.get("key") not in {"no_after_lesson","no_before_lesson"}]
'''
s=rep(s,old,new,"retire legacy before/after keys")

old='''    defaults=[
        {"key":"after_last_short","label":"Unikaj dyżuru po ostatniej lekcji – krótka przerwa","scope":"oba","enabled":False,"kind":"soft","priority":1,"value":None,
         "description":"Krótki dyżur bezpośrednio po ostatniej lekcji nauczyciela jest dopuszczalny. Włącz jako ZALECANE, jeśli chcesz go lekko ograniczać; MUSI BYĆ oznacza zakaz."},
        {"key":"after_last_long","label":"Unikaj dyżuru po ostatniej lekcji – długa przerwa","scope":"oba","enabled":True,"kind":"soft","priority":4,"value":None,
         "description":"Długiej przerwy bezpośrednio po ostatniej lekcji chcemy unikać. ZALECANE = kara, MUSI BYĆ = bezwzględny zakaz."},
'''
new='''    defaults=[
        {"key":"before_first_short","label":"Przed pierwszą lekcją – krótka przerwa 5 min","scope":"oba","enabled":False,"kind":"soft","priority":1,"value":None,
         "description":"Dotyczy wyłącznie 5-minutowej przerwy bezpośrednio przed PIERWSZĄ lekcją nauczyciela danego dnia. Może być dopuszczona; przerwy między lekcjami nie podlegają tej regule."},
        {"key":"before_first_long","label":"Przed pierwszą lekcją – przerwa >5 min — ZAKAZ","scope":"oba","enabled":True,"kind":"hard","priority":5,"value":None,
         "description":"Bezwzględny zakaz dyżuru na przerwie dłuższej niż 5 minut przed PIERWSZĄ lekcją nauczyciela, aby nie musiał przychodzić wcześniej do szkoły."},
        {"key":"after_last_short","label":"Po ostatniej lekcji – krótka przerwa 5 min","scope":"oba","enabled":False,"kind":"soft","priority":1,"value":None,
         "description":"Dotyczy wyłącznie 5-minutowej przerwy bezpośrednio po OSTATNIEJ lekcji nauczyciela danego dnia. Może być dopuszczona."},
        {"key":"after_last_long","label":"Po ostatniej lekcji – przerwa >5 min — ZAKAZ","scope":"oba","enabled":True,"kind":"hard","priority":5,"value":None,
         "description":"Bezwzględny zakaz dyżuru na przerwie dłuższej niż 5 minut po OSTATNIEJ lekcji nauczyciela, aby nie musiał zostawać dłużej w szkole."},
'''
s=rep(s,old,new,"edge defaults")

old='''        {"key":"workload_fairness","label":"Sprawiedliwość proporcjonalna do pensum / obciążenia","scope":"oba","enabled":False,"kind":"soft","priority":2,"value":None,
         "description":"Rozkłada łączną liczbę dyżurów proporcjonalnie do współczynnika nauczyciela. Domyślnie wyłączone do czasu uzupełnienia pensum."},
'''
new='''        {"key":"lesson_load_fairness","label":"Proporcjonalnie do liczby lekcji w planie","scope":"oba","enabled":False,"kind":"soft","priority":2,"value":None,
         "description":"Automatycznie wylicza udział w dyżurach z liczby lekcji w tygodniowym planie. Nauczyciel z 10 lekcjami ma około dwa razy większy docelowy udział niż nauczyciel z 5 lekcjami."},
        {"key":"workload_fairness","label":"Ręczna waga udziału w dyżurach","scope":"oba","enabled":False,"kind":"soft","priority":2,"value":None,
         "description":"Ręczna decyzja o większym lub mniejszym udziale w dyżurach. 1,0 = neutralnie; 0,5 = połowa udziału względem 1,0. Jeśli aktywna jest też proporcjonalność do liczby lekcji, ta waga mnoży współczynnik wyliczony z planu."},
'''
s=rep(s,old,new,"fairness defaults")

s=s.replace('"after_last_short":650,"after_last_long":720,','"before_first_short":650,"after_last_short":650,')
s=s.replace('"adjacent_lesson":800,"no_before_lesson":850,','"adjacent_lesson":800,')
s=s.replace('c.get("key") not in FIXED_HARD_KEYS','c.get("key") not in FIXED_HARD_KEYS and c.get("key") not in {"before_first_long","after_last_long"}')

old='''    return {"teacher":{"name":name,"group":GROUP.get(name,"school")},"lessons":t.get("lessons",{}),"breaks":SEED.get("breaks",[]),
            "duties":duties,"preferences":st.get("preference_grid",{}).get(name,{})}
'''
new='''    return {"teacher":{"name":name,"group":GROUP.get(name,"school")},"lessons":t.get("lessons",{}),"breaks":SEED.get("breaks",[]),
            "timeline":SEED.get("timeline",{}),"duties":duties,"preferences":st.get("preference_grid",{}).get(name,{})}
'''
s=rep(s,old,new,"teacher portal timeline")
APP.write_text(s,encoding="utf-8")

# ---------- main UI ----------
h=UI.read_text(encoding="utf-8")
h=h.replace("Dyżury v5.7","Dyżury v5.8").replace("Dyżury v5.7","Dyżury v5.8")
h=h.replace("Dyżury v5.7 •","Dyżury v5.8 •")
h=h.replace("teacherPageSize:12","teacherPageSize:15")
h=h.replace("schoolStaffingDay:'Poniedziałek',newSchoolLocation:''","schoolStaffingDay:'Poniedziałek',staffing13Day:'Poniedziałek',newSchoolLocation:''")

# Workload table CSS.
css_anchor=".teacher-admin-table select{min-width:120px}.portal-link{width:min(720px,100%);font-family:monospace}"
css_new=css_anchor+".workload-table{width:auto;min-width:680px;max-width:840px}.workload-table .wl-name{width:190px;max-width:190px}.workload-table .wl-num{width:105px;max-width:105px;text-align:center}.workload-table input{width:82px}.policy-lock{font-size:10px;font-weight:700;color:#7f1d1d;white-space:nowrap}"
h=rep(h,css_anchor,css_new,"workload CSS")

# Global constraint controls: show but lock absolute long-edge policy.
h=h.replace('<td><input type="checkbox" v-model="c.enabled"></td>','<td><input type="checkbox" v-model="c.enabled" :disabled="isPolicyLocked(c)"><div v-if="isPolicyLocked(c)" class="policy-lock">polityka stała</div></td>',1)
h=h.replace('<td><select v-model="c.kind"><option value="hard">Musi być</option><option value="soft">Zalecane</option></select><div class="mode-pill" :class="c.kind">{{c.kind===\'hard\'?\'MUSI BYĆ\':\'ZALECANE\'}}</div></td>',
'''<td><select v-model="c.kind" :disabled="isPolicyLocked(c)"><option value="hard">Musi być</option><option value="soft">Zalecane</option></select><div class="mode-pill" :class="c.kind">{{c.kind==='hard'?'MUSI BYĆ':'ZALECANE'}}</div></td>''',1)

# 1-3 staffing clearer and day-scoped, visually aligned with school matrix.
old='''<div class="card">
<b>Minimalna obsada dyżurów 1–3</b>
<div class="note">Domyślnie każdy dyżur wymaga 2 osób. Ustaw „1 osoba” tylko dla świadomie wybranego wyjątku.</div>
<div style="max-height:420px;overflow:auto;margin-top:8px">
<table class="constraints-table"><thead><tr><th>Dzień</th><th>Slot</th><th>Godzina</th><th>Wymagana obsada</th></tr></thead>
<tbody><tr v-for="r in staffingRows" :class="minPeople13[r.key]===1?'constraint-soft':''">
<td>{{r.day}}</td><td>{{r.slot}}</td><td>{{r.time}}</td>
<td><select v-model.number="minPeople13[r.key]"><option :value="2">2 osoby</option><option :value="1">1 osoba — wyjątek</option></select></td>
</tr></tbody></table></div>
<div class="actions" style="margin-top:8px"><button class="btn" @click="resetMinPeople">Ustaw wszędzie 2 osoby</button><button class="btn primary" @click="saveMinPeople(true)">Zapisz i przelicz 1–3</button></div>
</div>
'''
new='''<div class="card">
<b>Wymagana liczba dyżurujących – strefa 1–3 (ustawienie solvera)</b>
<div class="note">To jest <b>ustawienie wejściowe</b>, nie wynik rozwiązania. Dla każdej przerwy określasz łączną liczbę osób potrzebnych na wspólnej strefie 1–3. Standard to 2 osoby; 1 osoba jest świadomym wyjątkiem.</div>
<div class="daytabs" style="margin-top:8px"><button class="tab" v-for="d in days" :class="{active:staffing13Day===d}" @click="staffing13Day=d">{{d}}</button></div>
<div style="max-height:420px;overflow:auto;margin-top:8px">
<table class="constraints-table"><thead><tr><th>Przerwa</th><th>Godzina</th><th>Wymagana liczba osób</th></tr></thead>
<tbody><tr v-for="r in staffingRows.filter(x=>x.day===staffing13Day)" :class="minPeople13[r.key]===1?'constraint-soft':''">
<td>{{r.slot}}</td><td>{{r.time}}</td>
<td><select v-model.number="minPeople13[r.key]"><option :value="2">2 osoby — standard</option><option :value="1">1 osoba — wyjątek</option></select></td>
</tr></tbody></table></div>
<div class="actions" style="margin-top:8px"><button class="btn" @click="resetMinPeople">Ustaw wszędzie 2 osoby</button><button class="btn primary" @click="saveMinPeople(true)">Zapisz i przelicz 1–3</button></div>
</div>
'''
h=rep(h,old,new,"1-3 staffing UI")

h=h.replace("<b>Minimalna obsada dyżurów – cała szkoła</b>","<b>Wymagana obsada stanowisk – cała szkoła (ustawienie solvera)</b>")
h=h.replace('Dla każdego miejsca i przerwy ustaw, czy wymagany jest 1 nauczyciel. „Brak dyżuru” usuwa to stanowisko z solvera. Ustawienia są trwałe.',
'''To jest <b>ustawienie wejściowe</b>, nie gotowe rozwiązanie. Dla każdego miejsca i przerwy określasz, czy stanowisko w ogóle istnieje. „0 — brak stanowiska” oznacza: solver nie ma tam nikogo przydzielać. „1 osoba” oznacza: stanowisko ma istnieć i solver ma je obsadzić. „Odtwórz z bieżącego planu” tylko kopiuje obecny plan jako punkt startowy ustawień.''')
h=h.replace("Odtwórz obsadę z bieżącego planu","Odtwórz ustawienie z bieżącego planu")
h=h.replace('<option :value="0">brak dyżuru</option><option :value="1">1 osoba</option>','<option :value="0">0 — brak stanowiska</option><option :value="1">1 osoba</option>')

# Workload / fairness UI.
old='''<div class="card">
<b>Pensum / współczynnik obciążenia</b>
<div class="note">1,0 = pełny punkt odniesienia. Np. 0,5 oznacza połowę docelowego udziału w dyżurach. Mechanizm zaczyna wpływać na plan dopiero po włączeniu constraintu „Sprawiedliwość proporcjonalna…”.</div>
<div style="max-height:320px;overflow:auto;margin-top:8px"><table class="constraints-table"><thead><tr><th>Nauczyciel</th><th>Współczynnik</th></tr></thead><tbody>
<tr v-for="t in sortedTeachers"><td>{{t.name}}</td><td><input type="number" min="0.1" max="3" step="0.1" v-model.number="teacherWorkload[t.name]"></td></tr>
</tbody></table></div>
</div>
'''
new='''<div class="card">
<b>Sprawiedliwość obciążenia dyżurami</b>
<div class="note"><b>Dwie osobne rzeczy:</b> „Proporcjonalnie do liczby lekcji w planie” jest wyliczane automatycznie z tygodniowego planu. Nauczyciel z 10 lekcjami ma wtedy około 2× większy docelowy udział niż nauczyciel z 5 lekcjami. „Ręczna waga udziału” jest świadomą korektą użytkownika: 1,0 = bez korekty, 0,5 = połowa udziału, 1,5 = półtora udziału. Jeśli oba mechanizmy są aktywne, solver mnoży współczynnik z planu przez ręczną wagę.</div>
<div class="detailbox"><b>Aktualnie:</b> proporcjonalność wg lekcji: <b>{{constraintEnabled('lesson_load_fairness')?'WŁĄCZONA':'wyłączona'}}</b> • ręczna waga: <b>{{constraintEnabled('workload_fairness')?'WŁĄCZONA':'wyłączona'}}</b>. Współczynnik z planu ma średnią 1,00 dla nauczycieli mających lekcje; jest wyłącznie informacyjny, dopóki odpowiednia reguła nie jest włączona.</div>
<div style="max-height:360px;overflow:auto;margin-top:8px"><table class="constraints-table workload-table"><thead><tr><th class="wl-name">Nauczyciel</th><th class="wl-num">Lekcji / tydz.</th><th class="wl-num">Wsp. z planu</th><th class="wl-num">Ręczna waga</th><th class="wl-num">Efektywny wsp.</th></tr></thead><tbody>
<tr v-for="t in sortedTeachers"><td class="wl-name">{{t.name}}</td><td class="wl-num">{{lessonCount(t)}}</td><td class="wl-num">{{lessonLoadFactor(t)}}</td><td class="wl-num"><input type="number" min="0.1" max="3" step="0.1" v-model.number="teacherWorkload[t.name]"></td><td class="wl-num"><b>{{effectiveWorkloadFactor(t)}}</b></td></tr>
</tbody></table></div>
<div class="actions" style="margin-top:8px"><button class="btn" @click="saveAdvanced">Zapisz wagi</button><button class="btn primary" @click="recalculateAll">Zapisz i przelicz</button><button class="btn" @click="openRules">Otwórz reguły proporcjonalności</button></div>
</div>
'''
h=rep(h,old,new,"fairness UI")

# Computed average.
old='''sortedTeachers(){return [...this.cfg.teachers].sort((a,b)=>a.name.localeCompare(b.name,'pl'))},
sortedTeacherRegistry()'''
new='''sortedTeachers(){return [...this.cfg.teachers].sort((a,b)=>a.name.localeCompare(b.name,'pl'))},
lessonAverage(){let v=this.sortedTeachers.map(t=>Object.values(t.lessons||{}).reduce((n,d)=>n+Object.keys(d||{}).length,0)).filter(x=>x>0);return v.length?v.reduce((a,b)=>a+b,0)/v.length:1},
sortedTeacherRegistry()'''
h=rep(h,old,new,"lesson average")

# Methods for policy locks and factors.
old='''isFixedConstraint(c){return['no_lesson_overlap','one_place_per_slot','cross_scope_conflict','manual_blocks'].includes(c?.key)},
constraintValue(k)'''
new='''isFixedConstraint(c){return['no_lesson_overlap','one_place_per_slot','cross_scope_conflict','manual_blocks'].includes(c?.key)},
isPolicyLocked(c){return['before_first_long','after_last_long'].includes(c?.key)},
constraintEnabled(k){let c=this.globalConstraints.find(x=>x.key===k);return !!(c&&c.enabled)},
lessonCount(t){return Object.values(t?.lessons||{}).reduce((n,d)=>n+Object.keys(d||{}).length,0)},
lessonLoadFactor(t){return (this.lessonCount(t)/(this.lessonAverage||1)).toFixed(2)},
effectiveWorkloadFactor(t){let auto=this.constraintEnabled('lesson_load_fairness'),manual=this.constraintEnabled('workload_fairness'),m=Math.max(.1,Number(this.teacherWorkload[t.name]||1)),lf=this.lessonCount(t)/(this.lessonAverage||1);if(!auto&&!manual)return '—';return ((auto?lf:1)*(manual?m:1)).toFixed(2)},
constraintValue(k)'''
h=rep(h,old,new,"fairness methods")

h=h.replace("{key:'no_before_lesson',label:'Nie dawaj tylko przed lekcją'}","{key:'no_before_lesson',label:'Nie dawaj przed pierwszą lekcją'}")
h=h.replace("{key:'no_after_lesson',label:'Nie dawaj tylko po lekcji'}","{key:'no_after_lesson',label:'Nie dawaj po ostatniej lekcji'}")

UI.write_text(h,encoding="utf-8")

# ---------- teacher portal: one unified timeline table ----------
teacher=r'''<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mój plan i dyżury – DEMO</title>
<style>
:root{font-family:Arial,sans-serif;color:#172554;background:#f3f6f9}body{margin:0}header{background:#dcecf9;padding:14px 20px;border-bottom:1px solid #b7c8d8}main{max-width:1280px;margin:auto;padding:14px}.card{background:white;border:1px solid #cbd5e1;border-radius:8px;padding:12px;margin:10px 0}.note{font-size:13px;color:#475569}.error{border-left:5px solid #b91c1c;background:#fef2f2}.gridwrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #cbd5e1;padding:5px;vertical-align:top}th{background:#e8f0f7}.time{width:96px;white-space:nowrap}.slot{width:62px;text-align:center;white-space:nowrap}.lesson{background:#d9eaf7}.duty{background:#fff2cc;font-weight:600}.wait{color:#92400e;font-weight:700}.mutedcell{color:#94a3b8;text-align:center}select,button{padding:6px 8px;border:1px solid #94a3b8;border-radius:5px;background:white}button{cursor:pointer}.primary{background:#2563eb;color:white;border-color:#1d4ed8}.prefs{overflow:auto}.prefs table{min-width:760px}.prefs td{text-align:center}.prefs select{min-width:112px}.legend{display:flex;gap:10px;flex-wrap:wrap;font-size:12px}.dot{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:-2px}@media(max-width:800px){main{padding:8px}.schedule{min-width:900px}}</style>
</head><body>
<header><b>DEMO – mój plan lekcji i dyżury</b><div id="who" class="note"></div></header>
<main><div id="status" class="card">Wczytuję plan…</div>
<div id="content" hidden>
<div class="card">
<b>Plan tygodnia – lekcje i dyżury w jednej osi czasu</b>
<div class="note">Niebieskie komórki to lekcje, żółte to dyżury. Dzięki wspólnej osi czasu od razu widać, czy dyżur jest przed pierwszą lekcją, między lekcjami czy po ostatniej lekcji.</div>
<div class="legend" style="margin:8px 0"><span><i class="dot" style="background:#d9eaf7"></i>lekcja</span><span><i class="dot" style="background:#fff2cc"></i>dyżur</span></div>
<div class="gridwrap"><div id="schedule"></div></div>
</div>
<div class="card">
<b>Moje preferencje dotyczące dyżurów</b>
<div class="note">„Preferowana” pomaga solverowi wybierać dany termin. „Niepożądana” oznacza, że solver powinien go unikać. „Zabroniona” jest najsilniejszą deklaracją i ma znaczenie zgodnie z ustawieniami szkoły. Zmiana tutaj nie daje dostępu do planu innych nauczycieli.</div>
<div class="legend" style="margin:8px 0"><span><i class="dot" style="background:#dcfce7"></i>preferowana</span><span><i class="dot" style="background:#fef3c7"></i>niepożądana</span><span><i class="dot" style="background:#fee2e2"></i>zabroniona</span></div>
<div class="prefs" id="prefs"></div>
<button class="primary" id="save">Zapisz moje preferencje</button> <span id="saved" class="note"></span>
</div></div></main>
<script>
const qs=new URLSearchParams(location.search), token=qs.get('t')||'';
const days=[['Pn','Poniedziałek'],['Wt','Wtorek'],['Śr','Środa'],['Czw','Czwartek'],['Pi','Piątek']];
let data=null,prefs={};
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function lessonText(day,p){let a=data.lessons?.[day]?.[String(p)]||[];return a.map(x=>[x.class,x.subject,x.room].filter(Boolean).map(esc).join(' • ')).join('<br>')}
function dutiesAt(day,slot){return (data.duties||[]).filter(x=>x.abbr===day&&x.slot===slot)}
function dutyText(day,slot){let a=dutiesAt(day,slot);return a.map(x=>esc(x.scope)+' • '+esc(x.place)+(x.wait?'<div class="wait">oczekiwanie: '+esc(x.wait)+' lek.</div>':'')).join('<br>')}
function timelineRows(){
 let rows=[],seen=new Set();
 for(const pair of days){for(const r of (data.timeline?.[pair[1]]||[])){let k=[r.time,r.kind,r.key,r.label].join('|');if(!seen.has(k)){seen.add(k);rows.push({...r})}}}
 function mins(x){let m=String(x.time||'').match(/^(\d{1,2}):(\d{2})/);return m?Number(m[1])*60+Number(m[2]):9999}
 rows.sort((a,b)=>mins(a)-mins(b)||String(a.kind).localeCompare(String(b.kind)));
 return rows
}
function dayHasRow(dayName,row){return (data.timeline?.[dayName]||[]).some(x=>x.kind===row.kind&&String(x.key)===String(row.key)&&String(x.time)===String(row.time))}
function render(){
 document.getElementById('who').textContent=data.teacher.name;
 let h='<table class="schedule"><thead><tr><th class="time">Godzina</th><th class="slot">Slot</th>'+days.map(d=>'<th>'+d[0]+'</th>').join('')+'</tr></thead><tbody>';
 for(const row of timelineRows()){
   let label=row.kind==='LEKCJA'?'L'+esc(row.label):esc(row.label);
   h+='<tr><th class="time">'+esc(row.time)+'</th><th class="slot">'+label+'</th>';
   for(const d of days){
     if(!dayHasRow(d[1],row)){h+='<td class="mutedcell">—</td>';continue}
     if(row.kind==='LEKCJA'){let x=lessonText(d[0],row.key);h+='<td class="'+(x?'lesson':'')+'">'+(x||'—')+'</td>'}
     else {let x=dutyText(d[0],row.label);h+='<td class="'+(x?'duty':'')+'">'+(x||'—')+'</td>'}
   }
   h+='</tr>';
 }
 h+='</tbody></table>';document.getElementById('schedule').innerHTML=h;
 let slots=[...new Set(data.breaks.map(b=>b.label))];
 let timeBy={};for(const b of data.breaks||[])if(!(b.label in timeBy))timeBy[b.label]=b.time||'';
 let ph='<table><thead><tr><th>Przerwa</th><th>Godzina</th>'+days.map(d=>'<th>'+d[0]+'</th>').join('')+'</tr></thead><tbody>';
 for(const slot of slots){ph+='<tr><th>'+esc(slot)+'</th><td>'+esc(timeBy[slot]||'')+'</td>'+days.map(d=>{let k=d[0]+'|'+slot,v=prefs[k]||'neutral';return '<td><select data-k="'+esc(k)+'"><option value="neutral" '+(v==='neutral'?'selected':'')+'>neutralna</option><option value="prefer" '+(v==='prefer'?'selected':'')+'>preferowana</option><option value="avoid" '+(v==='avoid'?'selected':'')+'>niepożądana</option><option value="forbid" '+(v==='forbid'?'selected':'')+'>zabroniona</option></select></td>'}).join('')+'</tr>'}
 ph+='</tbody></table>';document.getElementById('prefs').innerHTML=ph;
 document.querySelectorAll('#prefs select').forEach(x=>x.onchange=()=>{if(x.value==='neutral')delete prefs[x.dataset.k];else prefs[x.dataset.k]=x.value});
}
async function load(){
 if(!token){document.getElementById('status').className='card error';document.getElementById('status').textContent='Brak indywidualnego tokenu w linku.';return}
 try{let r=await fetch('/api/teacher-portal/'+encodeURIComponent(token),{cache:'no-store'});if(!r.ok)throw new Error('Nieprawidłowy lub nieaktywny link.');data=await r.json();prefs={...(data.preferences||{})};document.getElementById('status').hidden=true;document.getElementById('content').hidden=false;render()}catch(e){document.getElementById('status').className='card error';document.getElementById('status').textContent=e.message}
}
document.getElementById('save').onclick=async()=>{let r=await fetch('/api/teacher-portal/'+encodeURIComponent(token)+'/preferences',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preferences:prefs})});document.getElementById('saved').textContent=r.ok?'Zapisano.':'Nie udało się zapisać.';if(r.ok)setTimeout(()=>document.getElementById('saved').textContent='',2500)};
load();
</script></body></html>
'''
TP.write_text(teacher,encoding="utf-8")

# ---------- tests/docs ----------
test=r'''import unittest
from pathlib import Path
import app
import solver_ortools as so

ROOT=Path(__file__).parent

class TestV58(unittest.TestCase):
    def test_version(self):
        self.assertEqual(app.app.version,"5.8")
        self.assertEqual(app.health()["version"],"5.8")

    def test_first_and_last_mean_day_edges(self):
        tby={"T":{"lessons":{"Pn":{"2":[{}],"4":[{}]}}}}
        self.assertTrue(so._is_before_first_lesson(tby,"T",{"abbr":"Pn","next":2}))
        self.assertFalse(so._is_before_first_lesson(tby,"T",{"abbr":"Pn","next":4}))
        self.assertTrue(so._is_after_last_lesson(tby,"T",{"abbr":"Pn","prev":4}))
        self.assertFalse(so._is_after_last_lesson(tby,"T",{"abbr":"Pn","prev":2}))

    def test_long_edge_policy_is_hard(self):
        st=app.ensure_state_schema({})
        cm={x["key"]:x for x in st["global_constraints"]}
        for key in ("before_first_long","after_last_long"):
            self.assertTrue(cm[key]["enabled"])
            self.assertEqual(cm[key]["kind"],"hard")
            self.assertEqual(cm[key]["priority"],5)
        self.assertIn("before_first_short",cm)
        self.assertIn("after_last_short",cm)

    def test_legacy_before_constraint_removed(self):
        st=app.ensure_state_schema({"global_constraints":[{"key":"no_before_lesson","enabled":True,"kind":"soft","priority":1}]})
        self.assertNotIn("no_before_lesson",{x["key"] for x in st["global_constraints"]})

    def test_lesson_count(self):
        tby={"A":{"lessons":{"Pn":{"1":[],"2":[]},"Wt":{"1":[]} }}}
        self.assertEqual(so._lesson_count(tby,"A"),3)

    def test_ui_contract(self):
        h=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        for phrase in ("teacherPageSize:15","Proporcjonalnie do liczby lekcji w planie","Ręczna waga udziału","Efektywny wsp.","0 — brak stanowiska","ustawienie wejściowe"):
            self.assertIn(phrase,h)
        tp=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")
        self.assertIn("Plan tygodnia – lekcje i dyżury w jednej osi czasu",tp)
        self.assertIn("Godzina",tp)
        self.assertNotIn('<div class="grid">',tp)

if __name__=="__main__":
    unittest.main(verbosity=2)
'''
(ROOT/"test_v58.py").write_text(test,encoding="utf-8")
(ROOT/"CURRENT_RELEASE.txt").write_text("5.8\n",encoding="utf-8")

ch=ROOT/"docs"/"CHANGELOG.md"
old=ch.read_text(encoding="utf-8-sig") if ch.exists() else "# Changelog\n"
entry='''# v5.8 — 2026-09-19

- poprawiono semantykę „przed lekcją”: dotyczy wyłącznie przerwy przed pierwszą lekcją nauczyciela danego dnia,
- długie/dłuższe niż 5 min przerwy przed pierwszą i po ostatniej lekcji są stałą twardą polityką i nie są proponowane do poluzowania,
- 5-minutowe przerwy przed pierwszą i po ostatniej lekcji są osobnymi, opcjonalnymi constraintami,
- dodano automatyczną proporcjonalność dyżurów do liczby lekcji w tygodniowym planie,
- ręczna waga udziału i współczynnik z planu są pokazane osobno; przy obu aktywnych ręczna waga jest mnożnikiem korekcyjnym,
- ekran nauczyciela łączy lekcje i dyżury w jednej osi czasu z godzinami lekcji i przerw,
- widok zbiorczy zwiększono z 12 do 15 nauczycieli na stronę,
- doprecyzowano, że macierze obsady 1–3 i całej szkoły są ustawieniami wejściowymi solvera, a nie wynikami.
'''
ch.write_text(entry+old,encoding="utf-8")

print("PATCH_V58_OK")
