from pathlib import Path
import json, copy, re

ROOT=Path(__file__).parent

# Rebuild the bell source from the full Tuesday template.
sp=ROOT/"data"/"seed.json"
seed=json.loads(sp.read_text(encoding="utf-8"))
tpl=[copy.deepcopy(b) for b in seed["breaks"] if b.get("abbr")=="Wt"]
days=[("Poniedzia\u0142ek","Pn"),("Wtorek","Wt"),("\u015Aroda","\u015Ar"),("Czwartek","Czw"),("Pi\u0105tek","Pi")]
breaks=[]
for day,abbr in days:
    for b in tpl:
        x=copy.deepcopy(b)
        x["day"],x["abbr"]=day,abbr
        breaks.append(x)
seed["breaks"]=breaks
tline=copy.deepcopy(seed["timeline"].get("Wtorek",[]))
seed["timeline"]={day:copy.deepcopy(tline) for day,_ in days}
sp.write_text(json.dumps(seed,ensure_ascii=False,indent=2),encoding="utf-8")

# Ensure staffing state contains all break keys.
statep=ROOT/"data"/"state.json"
state=json.loads(statep.read_text(encoding="utf-8"))
mp=state.setdefault("min_people_13",{})
for b in breaks:
    mp.setdefault(b["abbr"]+"|"+b["label"],2)
statep.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")

htmlp=ROOT/"static"/"index.html"
html=htmlp.read_text(encoding="utf-8")
diag=r'''<template v-if="cfg && mainTab==='diagnostics'">
<div class="card">
<b>Diagnostyka solvera i od&#347;wie&#380;ania</b>
<div class="note">Po ka&#380;dym pe&#322;nym przeliczeniu ten widok otrzymuje nowe dane. Pokazuje braki, powody odrzucenia kandydat&#243;w oraz sp&#243;jno&#347;&#263; konfiguracji.</div>
<div class="kpis" style="margin-top:8px">
<div class="kpi" :class="{bad:serverHealth && !serverHealth.ok}"><b>{{serverHealth?.ok?'OK':'&#8212;'}}</b><br><small>backend</small></div>
<div class="kpi"><b>{{serverHealth?.engine||'OR-Tools CP-SAT'}}</b><br><small>silnik</small></div>
<div class="kpi"><b>{{serverHealth?.version||'5.2'}}</b><br><small>wersja</small></div>
<div class="kpi" :class="{bad:diagnosticCount}"><b>{{diagnosticCount}}</b><br><small>nieobsadzonych pozycji</small></div>
</div>
<div class="actions" style="margin-top:8px"><button class="btn" @click="refreshHealth">Od&#347;wie&#380; stan serwera</button><button class="btn primary" :disabled="recalculating" @click="recalculateAll"><span v-if="recalculating" class="spinner"></span>{{recalculating?'Przeliczam...':'Przelicz wszystko'}}</button></div>
</div>
<div class="diagnostic-grid">
<div class="card"><b>Korytarz 1&#8211;3</b><div v-if="diag13 && diag13.engine" class="note">{{diag13.engine}} &#8226; {{diag13.status}} &#8226; {{diag13.wall_time_s}} s</div>
<div v-if="!diag13 || !diag13.engine" class="note">Brak bie&#380;&#261;cych danych &#8212; uruchom pe&#322;ne przeliczenie.</div>
<div v-for="x in (diag13?.unresolved||[])" class="problem error"><b>{{x.position.day}} {{x.position.slot}} &#8226; {{x.position.station||x.position.location}}</b><br><small>Legalnych kandydat&#243;w: {{x.legal_candidates}}</small><div><span class="reason-chip" v-for="r in x.blocked_reasons">{{r.reason}} ({{r.count}})</span></div></div>
<div v-if="diag13?.hard_rejections?.length"><b>Najcz&#281;stsze blokady:</b><div><span class="reason-chip" v-for="r in diag13.hard_rejections">{{r.reason}}: {{r.count}}</span></div></div></div>
<div class="card"><b>Ca&#322;a szko&#322;a</b><div v-if="diagSchool && diagSchool.engine" class="note">{{diagSchool.engine}} &#8226; {{diagSchool.status}} &#8226; {{diagSchool.wall_time_s}} s</div>
<div v-if="!diagSchool || !diagSchool.engine" class="note">Brak bie&#380;&#261;cych danych &#8212; uruchom pe&#322;ne przeliczenie.</div>
<div v-for="x in (diagSchool?.unresolved||[])" class="problem error"><b>{{x.position.day}} {{x.position.slot}} &#8226; {{x.position.location||x.position.station}}</b><br><small>Legalnych kandydat&#243;w: {{x.legal_candidates}}</small><div><span class="reason-chip" v-for="r in x.blocked_reasons">{{r.reason}} ({{r.count}})</span></div></div>
<div v-if="diagSchool?.hard_rejections?.length"><b>Najcz&#281;stsze blokady:</b><div><span class="reason-chip" v-for="r in diagSchool.hard_rejections">{{r.reason}}: {{r.count}}</span></div></div></div>
</div>
<div class="card">
<div class="diagnostic-grid">
<div><b>Walidacja konfiguracji</b><div class="note">To nie jest ocena jako&#347;ci planu. Walidacja sprawdza, czy dane i constrainty s&#261; logicznie sp&#243;jne: czy regu&#322;y <b>Musi by&#263;</b> nie przecz&#261; sobie, czy wymagany dy&#380;ur nie koliduje z lekcj&#261;, czy limity maj&#261; poprawne zakresy oraz czy wskazani nauczyciele i sloty istniej&#261;.</div></div>
<div><div class="kpis"><div class="kpi" :class="{bad:validation?.errors}"><b>{{validation?.errors||0}}</b><br><small>b&#322;&#281;d&#243;w</small></div><div class="kpi warn"><b>{{validation?.warnings||0}}</b><br><small>ostrze&#380;e&#324;</small></div><div class="kpi"><b>{{validation?.ok?'OK':'WYMAGA UWAGI'}}</b><br><small>sp&#243;jno&#347;&#263; konfiguracji</small></div></div><div class="actions" style="margin-top:8px"><button class="btn" @click="refreshValidation">Sprawd&#378; ponownie</button></div></div>
</div>
<div v-if="validation && !validation.problems.length" class="problem ok"><b>Brak sprzeczno&#347;ci konfiguracji.</b></div>
<div v-for="p in (validation?.problems||[])" class="problem" :class="{error:p.severity==='error'}"><b>{{p.severity==='error'?'B&#321;&#260;D':'OSTRZE&#379;ENIE'}}</b> &#8212; {{p.message}}</div>
</div>
<div class="card repair-card">
<b>Automatyczna propozycja doj&#347;cia do pe&#322;nej obsady</b>
<div class="note">Solver sam sprawdza, kt&#243;re konfigurowalne regu&#322;y <b>Musi by&#263;</b> mo&#380;na zmieni&#263; na <b>Zalecane</b>. Najpierw testuje jedn&#261; zmian&#281;, potem najmniejsze pary zmian. Nie narusza sta&#322;ych regu&#322; fizycznych.</div>
<div class="actions" style="margin-top:8px"><button class="btn primary" :disabled="repairBusy" @click="refreshRepair"><span v-if="repairBusy" class="spinner"></span>{{repairBusy?'Szukam najmniejszej zmiany...':'Znajd&#378; najmniejsz&#261; zmian&#281;'}}</button></div>
<div v-if="repair">
<div v-for="g in repairGroups" class="repair-option"><b>{{g.title}}</b> &#8212; obecnie {{g.data.baseline.filled}} / {{g.data.baseline.required}} obsadzonych.<div class="note">{{g.data.message}}</div>
<div v-for="(sug,idx) in g.data.suggestions" class="repair-option"><b>Wariant {{idx+1}}:</b> {{sug.coverage.filled}} / {{sug.coverage.required}} obsadzonych; zmie&#324;: <span v-for="(c,ci) in sug.changes"><b>{{c.label}}</b>{{ci<sug.changes.length-1?', ':''}}</span> &#8594; <b>Zalecane</b>. <button class="btn small" @click="applyRepairSuggestion(sug)">Zastosuj i przelicz wszystko</button></div>
</div></div>
</div>
</template>'''
html=re.sub(r'<template v-if="cfg && mainTab===\'diagnostics\'">.*?</template>\s*<template v-if="cfg && mainTab===\'stats\'">',diag+"\n\n<template v-if=\"cfg && mainTab==='stats'\">",html,count=1,flags=re.S)
newmethods=r'''async syncWorkingState(){this.syncManual();let c=await fetch('/api/constraints',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({global:this.globalConstraints,individual:this.individualConstraints})});if(!c.ok)throw new Error('nie zapisano constraintów');let m=await fetch('/api/min-people-13',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({min_people_13:this.minPeople13})});if(!m.ok)throw new Error('nie zapisano obsady 1–3');let st=await fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled_teachers_13:this.f13.enabled_teachers,enabled_teachers_school:this.fschool.enabled_teachers,manual_blocks:this.manualBlocks,station_names:this.f13.station_names})});if(!st.ok)throw new Error('nie zapisano stanu roboczego')},
async recalculateAll(){if(this.recalculating)return;this.recalculating=true;this.solveError13='';this.repair=null;try{this.calcMessage='1/5 Zapisuję bieżące ustawienia i constrainty…';await this.syncWorkingState();this.calcMessage='2/5 Przeliczam dyżury 1–3…';await this.solve13();if(this.solveError13)throw new Error(this.solveError13);this.calcMessage='3/5 Przeliczam plan całej szkoły…';await this.solveSchool();if(this.diagSchool?.status==='ERROR')throw new Error(this.diagSchool.error||'błąd solvera szkoły');this.calcMessage='4/5 Odświeżam tabele, liczniki, walidację i dane źródłowe…';let fresh=await(await fetch('/api/config?ts='+Date.now(),{cache:'no-store'})).json();this.cfg=fresh;for(let b of this.cfg.breaks){let k=b.abbr+'|'+b.label;if(!(k in this.minPeople13))this.minPeople13[k]=Number((fresh.state.min_people_13||{})[k]||2)}await Promise.all([this.refreshValidation(),this.refreshHealth()]);this.refreshEpoch++;this.lastFullRecalc=new Date().toLocaleTimeString('pl-PL');if(this.diagnosticCount>0){this.calcMessage='5/5 Szukam najmniejszego poluzowania reguł dla pełnej obsady…';await this.refreshRepair(true)}else{this.calcMessage='Przeliczono cały plan. Wszystkie stanowiska są obsadzone.'}}catch(e){this.calcMessage='Błąd pełnego przeliczenia: '+e.message;this.solveError13=this.calcMessage}finally{this.recalculating=false;if(!this.calcMessage.startsWith('Błąd')&&this.diagnosticCount>0)this.calcMessage='Przeliczono cały plan. Pozostało '+this.diagnosticCount+' nieobsadzonych stanowisk — propozycje są w Diagnostyce.'}},
async refreshRepair(silent=false){if(this.repairBusy)return;this.repairBusy=true;try{let body={global:this.globalConstraints,individual:this.individualConstraints,min_people_13:this.minPeople13,manual_blocks:this.manualBlocks,last_13_assignments:this.rows13,school_assignments:this.schoolCurrent,enabled_teachers_13:this.f13.enabled_teachers,enabled_teachers_school:this.fschool.enabled_teachers};let r=await fetch('/api/diagnostics/repair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error('HTTP '+r.status);this.repair=await r.json()}catch(e){if(!silent)alert('Nie udało się policzyć propozycji: '+e.message)}finally{this.repairBusy=false}},
async applyRepairSuggestion(sug){for(let ch of(sug.changes||[])){if(ch.token.startsWith('g:')){let key=ch.token.slice(2),c=this.globalConstraints.find(x=>x.key===key);if(c){c.enabled=true;c.kind='soft'}}else if(ch.token.startsWith('i:')){let id=ch.token.slice(2),c=this.individualConstraints.find(x=>String(x.id)===id);if(c)c.kind='soft'}}await this.recalculateAll()},'''
html=re.sub(r'async syncWorkingState\(\).*?async applyRepairSuggestion\(sug\).*?\},\s*\n\s*lessonText',newmethods+"\nlessonText",html,count=1,flags=re.S)
html=re.sub(r'<div><button class="btn primary" :disabled="solving13" @click="solve13">.*?</div></div>','<div><button class="btn primary" :disabled="recalculating" @click="recalculateAll"><span v-if="recalculating" class="spinner"></span>{{recalculating?\'Przeliczam cały plan…\':\'Przelicz wszystko\'}}</button><div class="note" v-if="lastFullRecalc">Ostatnie pełne przeliczenie: {{lastFullRecalc}}</div><div class="note" style="color:#9c0006" v-if="solveError13">{{solveError13}}</div></div>',html,count=1,flags=re.S)
html=re.sub(r'<div><button class="btn primary" @click="solveSchool">.*?</button></div>','<div><button class="btn primary" :disabled="recalculating" @click="recalculateAll"><span v-if="recalculating" class="spinner"></span>{{recalculating?\'Przeliczam cały plan…\':\'Przelicz wszystko\'}}</button></div>',html,count=1,flags=re.S)
html=re.sub(r'async saveConstraints\(andSolve\)\{.*?\},\s*\nresetMinPeople',"""async saveConstraints(andSolve){let r=await fetch('/api/constraints',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({global:this.globalConstraints,individual:this.individualConstraints})});if(!r.ok){alert('Błąd zapisu reguł');return}await this.refreshValidation();if(andSolve){await this.recalculateAll()}else{this.diag13={};this.diagSchool={};this.repair=null;alert('Reguły zapisane. Uruchom „Przelicz wszystko”, aby odświeżyć plan.')}},
resetMinPeople""",html,count=1,flags=re.S)
html=re.sub(r'async saveMinPeople\(andSolve\)\{.*?\},\s*\nallNames',"""async saveMinPeople(andSolve){let r=await fetch('/api/min-people-13',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({min_people_13:this.minPeople13})});if(!r.ok){alert('Błąd zapisu obsady');return}await this.refreshValidation();if(andSolve)await this.recalculateAll()},
allNames""",html,count=1,flags=re.S)
html=re.sub(r'async mounted\(\)\{.*?\}\s*\n\}\)\.mount',"""async mounted(){await this.reload();this.calcMessage='Gotowe. „Przelicz wszystko” zapisze bieżące ustawienia i odświeży cały interfejs.'}
}).mount""",html,count=1,flags=re.S)
html=html.replace('v5.1 OR-Tools','v5.2 OR-Tools').replace('v5.1 • OR-Tools','v5.2 • OR-Tools')
htmlp.write_text(html,encoding="utf-8")

# Backend version label.
ap=ROOT/"app.py"
apptext=ap.read_text(encoding="utf-8").replace('"version":"5.1"','"version":"5.2"')
ap.write_text(apptext,encoding="utf-8")
print("patched v5.2 encoding/ui")
