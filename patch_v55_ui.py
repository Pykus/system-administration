from pathlib import Path
p=Path("static/index.html")
s=p.read_text(encoding="utf-8")
s=s.replace("<title>DEMO – Dyżury v5.4 OR-Tools</title>","<title>DEMO – Dyżury v5.5 OR-Tools</title>")
s=s.replace("<header><b>DEMO – Dyżury v5.3 • OR-Tools CP-SAT</b>","<header><b>DEMO – Dyżury v5.5 • OR-Tools CP-SAT</b>")
s=s.replace("@media(max-width:900px){.plan-grid,.diagnostic-grid{grid-template-columns:1fr}}",
'''@media(max-width:900px){.plan-grid,.diagnostic-grid{grid-template-columns:1fr}}
.pager{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;margin-top:8px}.pager-info{min-width:180px;text-align:center;font-weight:650}.friendly-ok{border-left:5px solid #15803d;background:#f0fdf4}.teacher-change{display:inline-block;margin:2px 5px 2px 0;padding:2px 7px;border-radius:10px;background:#eef2ff;font-size:11px}.tech-details summary{cursor:pointer;font-weight:700;padding:3px}.repair-option.best{border:2px solid #15803d;background:#f7fff9}''')

# Incomplete duties: show only full proposal and emergency action.
old='''<div v-if="showMissing13 && incomplete13.length" class="card detailbox"><b>Niekompletne dyżury:</b><div v-for="x in incomplete13">• {{x.day}}, {{x.slot}} — {{x.filled_people}} / {{x.required_people}} osób</div><div style="margin-top:7px"><button class="btn small" @click="addGroup13AndSolve('school')">Dodaj nauczycieli ogólnych awaryjnie i przelicz</button></div></div>'''
new='''<div v-if="showMissing13 && incomplete13.length" class="card detailbox">
<b>Niekompletne dyżury:</b><div v-for="x in incomplete13">• {{x.day}}, {{x.slot}} — {{x.filled_people}} / {{x.required_people}} osób</div>
<div v-if="bestRepair13" class="problem ok" style="margin-top:8px"><b>Jest wariant, który rozwiązuje wszystkie braki.</b><br><span>{{bestRepair13.title}}</span>
<div class="note">{{bestRepair13.explanation}}</div><button class="btn small primary" @click="applyRepairSuggestion(bestRepair13)">Zastosuj ten wariant</button></div>
<div style="margin-top:7px"><button class="btn small" @click="addGeneral13Emergency">Dodaj/przenieś nauczycieli ogólnych awaryjnie i przelicz</button></div>
</div>'''
assert old in s
s=s.replace(old,new,1)
s=s.replace("@click=\"addGroup13AndSolve('school')\">+ zwykli awaryjnie","@click=\"addGeneral13Emergency\">+ zwykli awaryjnie")

# Teacher lists/selects alphabetical.
s=s.replace('v-for="t in cfg.teachers"','v-for="t in sortedTeachers"')

# Pagination above the two wide plans.
old='''<div class="card sheet-wrap"><matrix-view :key="'m13-'+refreshEpoch+'-'+selected13Day" :cfg="cfg" :day="selected13Day" :assign13="rows13" :school="schoolCurrent" :manual="manualBlocks" :mode="displayMode13"></matrix-view></div>'''
new='''<div class="card">
<div class="pager"><button class="btn small" :disabled="teacherPage13===0" @click="teacherPage13--">← Poprzedni</button><span class="pager-info">Nauczyciele {{teacherPageLabel(teacherPage13)}} • strona {{teacherPage13+1}} / {{teacherPageCount}}</span><button class="btn small" :disabled="teacherPage13>=teacherPageCount-1" @click="teacherPage13++">Następny →</button></div>
</div>
<div class="card sheet-wrap"><matrix-view :key="'m13-'+refreshEpoch+'-'+selected13Day+'-'+teacherPage13" :cfg="cfg" :teachers="pagedTeachers13" :day="selected13Day" :assign13="rows13" :school="schoolCurrent" :manual="manualBlocks" :mode="displayMode13"></matrix-view></div>'''
assert old in s
s=s.replace(old,new,1)
old='''<div class="card sheet-wrap"><matrix-view :key="'ms-'+refreshEpoch+'-'+selectedSchoolDay" :cfg="cfg" :day="selectedSchoolDay" :assign13="rows13" :school="schoolDisplay" :manual="manualBlocks" :mode="displayModeSchool"></matrix-view></div>'''
new='''<div class="card">
<div class="pager"><button class="btn small" :disabled="teacherPageSchool===0" @click="teacherPageSchool--">← Poprzedni</button><span class="pager-info">Nauczyciele {{teacherPageLabel(teacherPageSchool)}} • strona {{teacherPageSchool+1}} / {{teacherPageCount}}</span><button class="btn small" :disabled="teacherPageSchool>=teacherPageCount-1" @click="teacherPageSchool++">Następny →</button></div>
</div>
<div class="card sheet-wrap"><matrix-view :key="'ms-'+refreshEpoch+'-'+selectedSchoolDay+'-'+teacherPageSchool" :cfg="cfg" :teachers="pagedTeachersSchool" :day="selectedSchoolDay" :assign13="rows13" :school="schoolDisplay" :manual="manualBlocks" :mode="displayModeSchool"></matrix-view></div>'''
assert old in s
s=s.replace(old,new,1)

# Replace Diagnostics template completely.
start=s.index('<template v-if="cfg && mainTab===\'diagnostics\'">')
end=s.index('<template v-if="cfg && mainTab===\'stats\'">',start)
diag=r'''<template v-if="cfg && mainTab==='diagnostics'">
<div class="card repair-card">
<b>Propozycje dojścia do pełnej obsady</b>
<div class="note">Pokazuję tylko warianty, które faktycznie usuwają wszystkie braki. Najpierw próbuję przełożyć nauczycieli między planem 1–3 i planem całej szkoły bez luzowania reguł. Dopiero później sprawdzam zmianę constraintów.</div>
<div class="actions" style="margin-top:8px"><button class="btn primary" :disabled="repairBusy" @click="refreshRepair"><span v-if="repairBusy" class="spinner"></span>{{repairBusy?'Szukam pełnych rozwiązań...':'Znajdź pełne rozwiązania'}}</button></div>
<div v-if="repair">
  <div v-for="g in repairGroups" class="repair-option">
    <div><b>{{g.title}}</b> — obecnie {{g.data.baseline.filled}} / {{g.data.baseline.required}} obsadzonych.</div>
    <div class="note">{{g.data.message}}</div>
    <div v-for="(sug,idx) in g.data.suggestions" class="repair-option best">
      <div><b>Wariant {{idx+1}}: {{sug.title}}</b> <span class="pill soft">pełna obsada {{sug.coverage.filled}} / {{sug.coverage.required}}</span></div>
      <div class="note">{{sug.explanation}}</div>
      <div v-if="sug.action==='rebalance'" style="margin-top:5px"><b>Constrainty:</b> bez zmian.
        <div v-if="sug.general_teachers?.length"><b>Nauczyciele ogólni użyci na 1–3:</b> <span v-for="x in sug.general_teachers" class="teacher-change">{{x.teacher}}<span v-if="x.reason"> — {{x.reason}}</span></span></div>
      </div>
      <div v-if="sug.changes?.length" style="margin-top:5px"><b>Zmiana reguł:</b> <span v-for="(c,ci) in sug.changes"><b>{{c.label}}</b>: Musi być → Zalecane<span v-if="ci<sug.changes.length-1">; </span></span></div>
      <div v-if="sug.teacher_changes" style="margin-top:5px"><b>Wpływ na plan:</b> {{sug.teacher_changes.positions_changed}} zmienionych stanowisk, {{sug.teacher_changes.teachers_changed}} nauczycieli.
        <div><span v-for="x in sug.teacher_changes.teachers" class="teacher-change">{{x.teacher}}: +{{x.added}} / −{{x.removed}}</span></div>
      </div>
      <button class="btn small primary" style="margin-top:6px" @click="applyRepairSuggestion(sug)">Zastosuj i przelicz wszystko</button>
    </div>
    <div v-if="!g.data.suggestions.length && g.data.baseline.missing" class="problem"><b>Brak wariantu 100%.</b> Nie proponuję częściowego rozwiązania.</div>
  </div>
</div>
</div>

<div class="card">
<div class="diagnostic-grid">
<div><b>Walidacja konfiguracji</b><div class="note">Sprawdza sprzeczne ustawienia, nieistniejących nauczycieli/sloty i błędne zakresy. Nie ocenia „jakości” planu.</div></div>
<div><div class="kpis"><div class="kpi" :class="{bad:validation?.errors}"><b>{{validation?.errors||0}}</b><br><small>błędów</small></div><div class="kpi warn"><b>{{validation?.warnings||0}}</b><br><small>ostrzeżeń</small></div><div class="kpi"><b>{{validation?.ok?'OK':'WYMAGA UWAGI'}}</b><br><small>spójność konfiguracji</small></div></div><div class="actions" style="margin-top:8px"><button class="btn" @click="refreshValidation">Sprawdź ponownie</button></div></div>
</div>
<div v-if="validation && !validation.problems.length" class="problem ok"><b>Brak sprzeczności konfiguracji.</b></div>
<div v-for="p in (validation?.problems||[])" class="problem" :class="{error:p.severity==='error'}"><b>{{p.severity==='error'?'BŁĄD':'OSTRZEŻENIE'}}</b> — {{p.message}}</div>
</div>

<details class="card tech-details">
<summary>Uwagi techniczne i szczegółowa diagnostyka solvera</summary>
<div class="note">Te dane są pomocne przy analizie problemów; nie są potrzebne do zwykłej obsługi aplikacji.</div>
<div class="kpis" style="margin-top:8px">
<div class="kpi" :class="{bad:serverHealth && !serverHealth.ok}"><b>{{serverHealth?.ok?'OK':'—'}}</b><br><small>backend</small></div>
<div class="kpi"><b>{{serverHealth?.engine||'OR-Tools CP-SAT'}}</b><br><small>silnik</small></div>
<div class="kpi"><b>{{serverHealth?.version||'5.5'}}</b><br><small>wersja</small></div>
<div class="kpi" :class="{bad:diagnosticCount}"><b>{{diagnosticCount}}</b><br><small>nieobsadzonych pozycji</small></div>
</div>
<div class="actions" style="margin-top:8px"><button class="btn" @click="refreshHealth">Odśwież stan serwera</button><button class="btn primary" :disabled="recalculating" @click="recalculateAll">{{recalculating?'Przeliczam...':'Przelicz wszystko'}}</button></div>
<div class="diagnostic-grid" style="margin-top:8px">
<div><b>Korytarz 1–3</b><div v-if="diag13?.engine" class="note">{{diag13.engine}} • {{diag13.status}} • {{diag13.wall_time_s}} s</div><div v-for="x in (diag13?.unresolved||[])" class="problem error"><b>{{x.position.day}} {{x.position.slot}} • {{x.position.station||x.position.location}}</b><br><small>Legalnych kandydatów: {{x.legal_candidates}}</small><div><span class="reason-chip" v-for="r in x.blocked_reasons">{{r.reason}} ({{r.count}})</span></div></div></div>
<div><b>Cała szkoła</b><div v-if="diagSchool?.engine" class="note">{{diagSchool.engine}} • {{diagSchool.status}} • {{diagSchool.wall_time_s}} s</div><div v-for="x in (diagSchool?.unresolved||[])" class="problem error"><b>{{x.position.day}} {{x.position.slot}} • {{x.position.location||x.position.station}}</b><br><small>Legalnych kandydatów: {{x.legal_candidates}}</small><div><span class="reason-chip" v-for="r in x.blocked_reasons">{{r.reason}} ({{r.count}})</span></div></div></div>
</div>
</details>
</template>

'''
s=s[:start]+diag+s[end:]

# Seed is internal; keep only deterministic toggle under technical details.
old='''<div class="card">
<b>Powtarzalność solvera</b>
<div class="controls" style="margin-top:8px">
<label>Seed solvera<input type="number" v-model.number="solverSeed"></label>
<label class="checkline"><input type="checkbox" v-model="deterministicMode"> Tryb deterministyczny (1 worker)</label>
</div>
<div class="note">Tryb deterministyczny ułatwia dokładne odtworzenie wyniku dla tej samej wersji danych i reguł.</div>
</div>'''
new='''<details class="card tech-details">
<summary>Ustawienia techniczne solvera</summary>
<label class="checkline" style="margin-top:8px"><input type="checkbox" v-model="deterministicMode"> Tryb deterministyczny (dla testów i dokładnego odtwarzania wyniku)</label>
<div class="note">Seed jest ustawiany automatycznie i nie wymaga edycji przez użytkownika.</div>
</details>'''
assert old in s
s=s.replace(old,new,1)

# Matrix gets explicit paginated teacher list.
s=s.replace("props:['cfg','day','assign13','school','manual','mode'],\ncomputed:{dc()", "props:['cfg','teachers','day','assign13','school','manual','mode'],\ncomputed:{dc()",1)
s=s.replace("computed:{dc(){return{'Poniedziałek':'Pn','Wtorek':'Wt','Środa':'Śr','Czwartek':'Czw','Piątek':'Pi'}[this.day]},\nteachers(){return this.cfg.teachers},\nrows()",
            "computed:{dc(){return{'Poniedziałek':'Pn','Wtorek':'Wt','Środa':'Śr','Czwartek':'Czw','Piątek':'Pi'}[this.day]},\nrows()",1)

# Add paging state.
s=s.replace("teacherPlanSearch:'',diag13:{}", "teacherPlanSearch:'',teacherPage13:0,teacherPageSchool:0,teacherPageSize:12,diag13:{}",1)

# Computed alphabetical lists and pages.
old='''filtered13(){let q=this.search13.toLowerCase();return this.cfg.teachers.filter(t=>t.name.toLowerCase().includes(q))},
filteredSchool(){let q=this.searchSchool.toLowerCase();return this.cfg.teachers.filter(t=>t.name.toLowerCase().includes(q))},
filteredTeacherPlans(){let q=this.teacherPlanSearch.toLowerCase();return this.cfg.teachers.filter(t=>!q||t.name.toLowerCase().includes(q))},'''
new='''sortedTeachers(){return [...this.cfg.teachers].sort((a,b)=>a.name.localeCompare(b.name,'pl'))},
filtered13(){let q=this.search13.toLowerCase();return this.sortedTeachers.filter(t=>t.name.toLowerCase().includes(q))},
filteredSchool(){let q=this.searchSchool.toLowerCase();return this.sortedTeachers.filter(t=>t.name.toLowerCase().includes(q))},
filteredTeacherPlans(){let q=this.teacherPlanSearch.toLowerCase();return this.sortedTeachers.filter(t=>!q||t.name.toLowerCase().includes(q))},
teacherPageCount(){return Math.max(1,Math.ceil(this.sortedTeachers.length/this.teacherPageSize))},
pagedTeachers13(){let p=Math.min(this.teacherPage13,this.teacherPageCount-1),a=p*this.teacherPageSize;return this.sortedTeachers.slice(a,a+this.teacherPageSize)},
pagedTeachersSchool(){let p=Math.min(this.teacherPageSchool,this.teacherPageCount-1),a=p*this.teacherPageSize;return this.sortedTeachers.slice(a,a+this.teacherPageSize)},'''
assert old in s
s=s.replace(old,new,1)

s=s.replace("return Object.values(m).sort((a,b)=>b.total-a.total||a.name.localeCompare(b.name,'pl'))",
            "return Object.values(m).sort((a,b)=>a.name.localeCompare(b.name,'pl'))",1)
s=s.replace("repairGroups(){if(!this.repair)return[];return[{title:'Korytarz 1?3',data:this.repair.school13},{title:'Ca?a szko?a',data:this.repair.school}]},",
            "repairGroups(){if(!this.repair)return[];return[{title:'Korytarz 1–3',data:this.repair.school13},{title:'Cała szkoła',data:this.repair.school}]},\nbestRepair13(){return this.repair?.school13?.suggestions?.[0]||null},\nbestRebalance13(){return (this.repair?.school13?.suggestions||[]).find(x=>x.action==='rebalance')||null},",1)

# Friendly helpers and repair apply.
old='''async applyRepairSuggestion(sug){for(let ch of(sug.changes||[])){if(ch.token.startsWith('g:')){let key=ch.token.slice(2),c=this.globalConstraints.find(x=>x.key===key);if(c){c.enabled=true;c.kind='soft'}}else if(ch.token.startsWith('i:')){let id=ch.token.slice(2),c=this.individualConstraints.find(x=>String(x.id)===id);if(c)c.kind='soft'}}await this.recalculateAll()},'''
new='''teacherPageLabel(page){let a=page*this.teacherPageSize,b=Math.min(this.sortedTeachers.length,a+this.teacherPageSize);if(!this.sortedTeachers.length)return '—';return (a+1)+'–'+b+' z '+this.sortedTeachers.length},
formatRows13FromFlat(flat){let by={};for(let a of(flat||[])){let k=a.abbr+'|'+a.slot;(by[k]||(by[k]=[])).push({station:a.station,teacher:a.teacher||'',wait:a.wait||0})}return this.cfg.breaks.map(b=>{let k=b.abbr+'|'+b.label,need=Number(this.minPeople13[k]||2),aa=(by[k]||[]).sort((x,y)=>x.station.localeCompare(y.station));let filled=aa.filter(x=>x.teacher).length;return{...b,required_people:need,complete:filled>=need,assignments:aa}})},
async applyRepairSuggestion(sug){
 if(sug.action==='rebalance'){
   this.rows13=this.formatRows13FromFlat(sug.result_13||[]);
   this.schoolCurrent=(sug.result_school||[]).map(x=>({day:x.day,abbr:x.abbr,slot:x.slot,location:x.location,teacher:x.teacher||''}));
   this.schoolPreview=[];
   this.f13.enabled_teachers=[...new Set([...this.f13.enabled_teachers,...(sug.general_teachers||[]).map(x=>x.teacher)])].sort((a,b)=>a.localeCompare(b,'pl'));
   let r=await fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({last_13_assignments:this.rows13,school_assignments:this.schoolCurrent,enabled_teachers_13:this.f13.enabled_teachers})});
   if(!r.ok){alert('Nie udało się zapisać wariantu.');return}
 }else{
   for(let ch of(sug.changes||[])){if(ch.token.startsWith('g:')){let key=ch.token.slice(2),c=this.globalConstraints.find(x=>x.key===key);if(c){c.enabled=true;c.kind='soft'}}else if(ch.token.startsWith('i:')){let id=ch.token.slice(2),c=this.individualConstraints.find(x=>String(x.id)===id);if(c)c.kind='soft'}}
 }
 await this.recalculateAll()
},
async addGeneral13Emergency(){
 await this.refreshRepair(true);
 if(this.bestRebalance13){await this.applyRepairSuggestion(this.bestRebalance13);return}
 let preferred=this.schoolTeachersFor13Affinity();
 let missing=preferred.filter(n=>!this.f13.enabled_teachers.includes(n));
 if(missing.length)this.f13.enabled_teachers=[...new Set([...this.f13.enabled_teachers,...missing])].sort((a,b)=>a.localeCompare(b,'pl'));
 else this.addGroup13('school');
 await this.recalculateAll()
},
schoolTeachersFor13Affinity(){
 let coreClasses=new Set(),rooms=new Set(['122','123','124','125','129','130']);
 for(let t of this.cfg.teachers.filter(x=>x.group==='1-3'))for(let ps of Object.values(t.lessons||{}))for(let ls of Object.values(ps||{}))for(let x of(ls||[])){if(x.class)coreClasses.add(String(x.class));let r=String(x.room||'');if(/^1[23][0-9]$/.test(r))rooms.add(r)}
 let scored=this.cfg.teachers.filter(t=>t.group==='school').map(t=>{let score=0;for(let ps of Object.values(t.lessons||{}))for(let ls of Object.values(ps||{}))for(let x of(ls||[])){if(coreClasses.has(String(x.class||'')))score+=20;if(rooms.has(String(x.room||'')))score+=8}return{name:t.name,score}}).filter(x=>x.score>0);
 return scored.sort((a,b)=>b.score-a.score||a.name.localeCompare(b.name,'pl')).map(x=>x.name)
},'''
assert old in s
s=s.replace(old,new,1)

# Alphabetical name helpers.
s=s.replace("allNames(){return this.cfg.teachers.map(t=>t.name)},coreNames(){return this.groupNames('1-3')},nonCoreNames(){return this.groupNames('school')},\ngroupNames(g){return this.cfg.teachers.filter(t=>t.group===g).map(t=>t.name)},",
            "allNames(){return this.sortedTeachers.map(t=>t.name)},coreNames(){return this.groupNames('1-3')},nonCoreNames(){return this.groupNames('school')},\ngroupNames(g){return this.sortedTeachers.filter(t=>t.group===g).map(t=>t.name)},",1)
s=s.replace("addGroup13(g){this.f13.enabled_teachers=[...new Set([...this.f13.enabled_teachers,...this.groupNames(g)])]},",
            "addGroup13(g){this.f13.enabled_teachers=[...new Set([...this.f13.enabled_teachers,...this.groupNames(g)])].sort((a,b)=>a.localeCompare(b,'pl'))},",1)
s=s.replace("addGroupSchool(g){this.fschool.enabled_teachers=[...new Set([...this.fschool.enabled_teachers,...this.groupNames(g)])]},",
            "addGroupSchool(g){this.fschool.enabled_teachers=[...new Set([...this.fschool.enabled_teachers,...this.groupNames(g)])].sort((a,b)=>a.localeCompare(b,'pl'))},",1)

# Friendly error messages, technical detail stays in diagnostics objects.
s=s.replace("catch(err){this.solveError13='Błąd przeliczania: '+err.message;}finally",
            "catch(err){this.diag13={status:'ERROR',unresolved:[],hard_rejections:[],error:err.message};this.solveError13='Nie udało się przeliczyć dyżurów 1–3. Szczegóły są w Diagnostyce.';}finally",1)
s=s.replace("alert('Błąd solvera szkoły: '+e.message)","this.calcMessage='Nie udało się przeliczyć planu szkoły. Szczegóły są w Diagnostyce.'",1)

# Pick alphabetically first teacher on reload.
s=s.replace("this.newConstraint.teacher=this.cfg.teachers[0]?.name||''","this.newConstraint.teacher=this.sortedTeachers[0]?.name||''")
s=s.replace("this.blockTeacher=this.cfg.teachers[0]?.name||''","this.blockTeacher=this.sortedTeachers[0]?.name||''")
s=s.replace("this.prefTeacher=this.cfg.teachers[0]?.name||''","this.prefTeacher=this.sortedTeachers[0]?.name||''")
s=s.replace("this.lockDraft.teacher=this.cfg.teachers[0]?.name||''","this.lockDraft.teacher=this.sortedTeachers[0]?.name||''")

p.write_text(s,encoding="utf-8")
print("ui patched")

