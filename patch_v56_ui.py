from pathlib import Path
p=Path("static/index.html")
s=p.read_text(encoding="utf-8")

s=s.replace(".sheet{border-collapse:separate;border-spacing:0;font-size:11px;min-width:100%}",".sheet{border-collapse:separate;border-spacing:0;font-size:11px;width:max-content;min-width:0}")
s=s.replace(".fixed1{position:sticky;left:0;z-index:6;min-width:90px;background:var(--muted)!important}",".fixed1{position:sticky;left:0;z-index:6;width:76px;min-width:76px;max-width:76px;background:var(--muted)!important;white-space:nowrap}")
s=s.replace(".fixed2{position:sticky;left:90px;z-index:6;min-width:58px;background:var(--muted)!important}",".fixed2{position:sticky;left:76px;z-index:6;width:44px;min-width:44px;max-width:44px;background:var(--muted)!important;white-space:nowrap}")
s=s.replace("@media(max-width:900px){.plan-grid,.diagnostic-grid{grid-template-columns:1fr}}",""".constraint-disabled{background:#f1f5f9!important;color:#94a3b8!important}
.constraint-disabled td,.constraint-disabled b,.constraint-disabled .note{color:#94a3b8!important}
.constraint-disabled select,.constraint-disabled input{opacity:.7;filter:grayscale(1)}
.constraint-disabled .mode-pill{background:#e2e8f0!important;color:#64748b!important}
.change-detail{border-left:3px solid #cbd5e1;padding:5px 8px;margin:5px 0;background:#f8fafc;border-radius:4px}
.change-added{color:#166534}.change-removed{color:#991b1b}.wait-flag{font-weight:700;color:#92400e}
.teacher-admin-table select{min-width:120px}.portal-link{width:min(720px,100%);font-family:monospace}
@media(max-width:900px){.plan-grid,.diagnostic-grid{grid-template-columns:1fr}}""")

s=s.replace('<button class="tab" :class="{active:mainTab===\'constraints\'}" @click="mainTab=\'constraints\'">Reguły / constrainty</button>\n','')
s=s.replace('<button class="tab" :class="{active:mainTab===\'stats\'}" @click="mainTab=\'stats\'">Statystyki</button>\n','')
s=s.replace('<button class="tab" :class="{active:mainTab===\'teachers\'}" @click="mainTab=\'teachers\'">Plany nauczycieli</button>\n',
'''<button class="tab" :class="{active:mainTab==='teachers'}" @click="mainTab='teachers'">Plany nauczycieli</button>
<button class="tab" :class="{active:mainTab==='teacherAdmin'}" @click="mainTab='teacherAdmin';loadTeacherRegistry()">Nauczyciele</button>
<button class="tab" :class="{active:mainTab==='teacherPortal'}" @click="mainTab='teacherPortal';loadTeacherRegistry()">Panel nauczyciela</button>
''')
s=s.replace('>Warianty / pliki</button>','>Warianty / pliki • import / eksport</button>')
s=s.replace('@click="mainTab=\'constraints\'">Zmień w Constraintach</button>','@click="openRules">Zmień zasady przydziału</button>')
s=s.replace('w zakładce Reguły / constrainty.','w „Regułach / zasadach przydziału”.')
s=s.replace('@click="mainTab=\'constraints\'">Przejdź do constraintów</button>','@click="openRules">Otwórz zasady przydziału</button>')

cstart="<template v-if=\"cfg && mainTab==='constraints'\">"
cnext="<template v-if=\"cfg && mainTab==='teachers'\">"
i=s.find(cstart); j=s.find(cnext)
if i<0 or j<0: raise SystemExit(f"constraints markers missing {i} {j}")
cblock=s[i:j]
inner=cblock[len(cstart):].rsplit("</template>",1)[0]
s=s[:i]+s[j:]
rules_details='''<details id="rulesDetails" class="card tech-details">
<summary>Reguły / zasady przydziału</summary>
<div class="note" style="margin:7px 0"><b>Jak działa kolejność?</b> Dla „Musi być” kolejność nie zmienia wyniku — wszystkie takie zasady obowiązują równocześnie. Dla „Zalecane” najpierw liczy się ważność 1–5; kolejność jest tylko rozstrzygnięciem pomocniczym przy tym samym poziomie. Kolejność jest zapisywana automatycznie i nie zmienia się po przeliczeniu.</div>
'''+inner+'''
</details>
'''

st="<template v-if=\"cfg && mainTab==='stats'\">"
adv="<template v-if=\"cfg && mainTab==='advanced'\">"
i=s.find(st); j=s.find(adv)
if i<0 or j<0: raise SystemExit(f"stats markers missing {i} {j}")
statsblock=s[i:j]
statsinner=statsblock[len(st):].rsplit("</template>",1)[0]
s=s[:i]+s[j:]
teachers_marker="<template v-if=\"cfg && mainTab==='teachers'\">"
pos=s.find(teachers_marker)+len(teachers_marker)
stats_details='''\n<details class="card tech-details">
<summary>Statystyki nauczycieli</summary>
<div class="note">Rozwiń, aby zobaczyć obciążenie dyżurami i podział na dni.</div>
'''+statsinner+'''
</details>
'''
s=s[:pos]+stats_details+s[pos:]

adv_marker="<template v-if=\"cfg && mainTab==='advanced'\">"
pos=s.find(adv_marker)+len(adv_marker)
s=s[:pos]+"\n"+rules_details+s[pos:]

s=s.replace("Reguły / constrainty","Reguły / zasady przydziału")
s=s.replace("constraintów","zasad")
s=s.replace("Constraintach","zasadach przydziału")

s=s.replace('class="constraint-row" :class="c.kind===\'soft\'?\'constraint-soft\':\'constraint-hard\'"',
            'class="constraint-row" :class="!c.enabled?\'constraint-disabled\':(c.kind===\'soft\'?\'constraint-soft\':\'constraint-hard\')"')
s=s.replace('<td>{{c.description}}</td>','<td>{{friendlyDescription(c.description)}}</td>')
s=s.replace('<tbody><tr v-for="r in filteredIndividualConstraints" :class="r.kind===\'soft\'?\'constraint-soft\':\'constraint-hard\'">',
            '<tbody><tr v-for="r in filteredIndividualConstraints" :class="!r.enabled?\'constraint-disabled\':(r.kind===\'soft\'?\'constraint-soft\':\'constraint-hard\')">')

old='''<div v-if="sug.teacher_changes" style="margin-top:5px"><b>Wpływ na plan:</b> {{sug.teacher_changes.positions_changed}} zmienionych stanowisk, {{sug.teacher_changes.teachers_changed}} nauczycieli.
        <div><span v-for="x in sug.teacher_changes.teachers" class="teacher-change">{{x.teacher}}: +{{x.added}} / −{{x.removed}}</span></div>
      </div>'''
new='''<div v-if="sug.teacher_changes" style="margin-top:5px"><b>Wpływ na plan:</b> {{sug.teacher_changes.positions_changed}} zmienionych stanowisk, {{sug.teacher_changes.teachers_changed}} nauczycieli.
        <div v-for="x in sug.teacher_changes.teachers" class="change-detail">
          <b>{{x.teacher}}</b> <span class="teacher-change">+{{x.added}} / −{{x.removed}}</span>
          <div v-for="d in (x.added_duties||[])" class="change-added">+ {{formatDutyChange(d)}} <span v-if="d.wait" class="wait-flag">• oczekiwanie: {{d.wait}} lek.</span></div>
          <div v-for="d in (x.removed_duties||[])" class="change-removed">− {{formatDutyChange(d)}}</div>
        </div>
      </div>'''
if old not in s: raise SystemExit("repair impact block missing")
s=s.replace(old,new)

s=s.replace('<b>Plan opublikowany i zastępstwa / nieobecności</b>','<b>Punkt odniesienia i zastępstwa / nieobecności</b>')
s=s.replace('Tryb operacyjny nie nadpisuje planu bazowego. Minimalizuje liczbę zmian względem opublikowanego planu i zapisuje osobną historię zastępstw.',
'''To nie publikuje planu na zewnątrz. Punkt odniesienia jest migawką bieżącego planu używaną wyłącznie po to, aby przy nieobecnościach zmienić możliwie mało dyżurów. Tryb zastępstw zapisuje osobną historię.''')
s=s.replace('Opublikuj bieżący plan jako bazę','Ustal bieżący plan jako punkt odniesienia dla zastępstw')
s=s.replace('opublikowano: {{publishedSnapshot.published_at}}','punkt odniesienia: {{publishedSnapshot.published_at}}')

s=s.replace('<b>Strefy / koszt przejścia</b>','<b>Strefy lokalizacji / koszt przejścia</b>')
s=s.replace('Dla sal solver rozpoznaje piętro z pierwszej cyfry numeru. Tu przypisz analogiczną strefę miejscom dyżurów (np. 0, 1, 2). Wpływ pojawia się po włączeniu constraintu przejść między strefami.',
'''Użyj umownej skali 1–10. To nie jest bezpośrednia „kara”, tylko położenie na osi od blisko do daleko: 1 = bardzo blisko / ta sama strefa, 5 = średnio daleko, 10 = skrajnie daleko. Koszt przejścia rośnie wraz z różnicą wartości (np. 2→3 jest małą zmianą, 2→9 dużą). Dla sal solver nadal rozpoznaje podstawową strefę z numeru sali. Mechanizm wpływa na plan dopiero po włączeniu zasady przejść między strefami.''')
s=s.replace('<td><input v-model="locationZones[z.key]" placeholder="np. 1"></td>','<td><input type="number" min="1" max="10" step="1" v-model.number="locationZones[z.key]" placeholder="1–10"></td>')

s=s.replace("cg.push([c.label,c.scope,c.kind,c.enabled?'TAK':'NIE',c.priority??'',c.value??''])",
            "cg.push([c.label,c.scope,c.kind==='hard'?'Musi być':'Zalecane',c.enabled?'TAK':'NIE',c.priority??'',c.value??''])")
s=s.replace("['Reguła','Zakres','Typ','Aktywna','Priorytet','Wartość']","['Reguła','Zakres','Charakter','Aktywna','Priorytet','Wartość']")

diag_marker="<template v-if=\"cfg && mainTab==='diagnostics'\">"
admin_tpl='''<template v-if="cfg && mainTab==='teacherAdmin'">
<div class="card">
<b>Zarządzanie nauczycielami</b>
<div class="note">To jest trwały rejestr nauczycieli. Zmiana grupy lub aktywności jest zapisywana w <code>teacher_registry.json</code> i nie ginie po przeliczeniu. Import nowego planu PDF automatycznie dodaje nowe nazwisko i wstępnie przypisuje kategorię.</div>
<div class="controls" style="margin-top:8px">
<label>Imię i nazwisko<input v-model="newTeacher.name" placeholder="np. Jan Kowalski"></label>
<label>Kategoria<select v-model="newTeacher.group"><option value="school">ogólny</option><option value="1-3">1–3</option><option value="wf">WF</option></select></label>
<div><button class="btn primary" @click="addTeacherAdmin">Dodaj nauczyciela</button></div>
</div>
<div v-if="teacherAdminMessage" class="detailbox">{{teacherAdminMessage}}</div>
</div>
<div class="card" style="overflow:auto">
<table class="constraints-table teacher-admin-table"><thead><tr><th>Aktywny</th><th>Nauczyciel</th><th>Kategoria</th><th>Sloty lekcji</th><th>Panel nauczyciela</th></tr></thead><tbody>
<tr v-for="t in sortedTeacherRegistry" :class="!t.active?'constraint-disabled':''">
<td><input type="checkbox" v-model="t.active" @change="updateTeacherAdmin(t)"></td>
<td><b>{{t.name}}</b></td>
<td><select v-model="t.group" @change="updateTeacherAdmin(t)"><option value="school">ogólny</option><option value="1-3">1–3</option><option value="wf">WF</option></select></td>
<td>{{t.lesson_slots}}</td>
<td><button class="btn small" @click="openTeacherPortalFor(t)">Otwórz</button> <button class="btn small" @click="copyTeacherPortalFor(t)">Kopiuj link</button></td>
</tr></tbody></table>
</div>
</template>

<template v-if="cfg && mainTab==='teacherPortal'">
<div class="card">
<b>Panel nauczyciela</b>
<div class="note">Nauczyciel otrzymuje indywidualny link. Strona pod tym linkiem pokazuje wyłącznie jego plan lekcji, jego dyżury i jego preferencje — bez dostępu do administracyjnego planu szkoły.</div>
<label style="display:block;margin-top:8px">Nauczyciel<select v-model="portalTeacherName"><option value="">— wybierz —</option><option v-for="t in activeTeacherRegistry" :value="t.name">{{t.name}}</option></select></label>
<div v-if="selectedPortalTeacher" style="margin-top:8px">
<input class="portal-link" readonly :value="teacherPortalUrl(selectedPortalTeacher)">
<div class="actions" style="margin-top:6px"><button class="btn primary" @click="openTeacherPortalFor(selectedPortalTeacher)">Otwórz panel</button><button class="btn" @click="copyTeacherPortalFor(selectedPortalTeacher)">Kopiuj link dla nauczyciela</button></div>
</div>
<div class="note" style="margin-top:8px">Link zawiera losowy token dostępu. Nie udostępnia pozostałych nauczycieli ani ustawień administratora.</div>
</div>
</template>

'''
pos=s.find(diag_marker)
if pos<0: raise SystemExit("diag marker missing")
s=s[:pos]+admin_tpl+s[pos:]

s=s.replace("teacherPlanSearch:'',teacherPage13:0,teacherPageSchool:0,teacherPageSize:12,lastTechnicalError:''",
            "teacherPlanSearch:'',teacherPage13:0,teacherPageSchool:0,teacherPageSize:12,lastTechnicalError:'',teacherRegistry:[],newTeacher:{name:'',group:'school'},teacherAdminMessage:'',portalTeacherName:''")

s=s.replace("sortedTeachers(){return [...this.cfg.teachers].sort((a,b)=>a.name.localeCompare(b.name,'pl'))},",
"""sortedTeachers(){return [...this.cfg.teachers].sort((a,b)=>a.name.localeCompare(b.name,'pl'))},
sortedTeacherRegistry(){return [...this.teacherRegistry].sort((a,b)=>a.name.localeCompare(b.name,'pl'))},
activeTeacherRegistry(){return this.sortedTeacherRegistry.filter(x=>x.active)},
selectedPortalTeacher(){return this.teacherRegistry.find(x=>x.name===this.portalTeacherName&&x.active)||null},""")

s=s.replace("dropConstraint(i){let from=this.draggedConstraintIndex;if(from===null||from===i)return;let [row]=this.globalConstraints.splice(from,1);this.globalConstraints.splice(i,0,row);this.draggedConstraintIndex=null},",
"""async dropConstraint(i){let from=this.draggedConstraintIndex;if(from===null||from===i)return;let [row]=this.globalConstraints.splice(from,1);this.globalConstraints.splice(i,0,row);this.draggedConstraintIndex=null;let r=await fetch('/api/constraints',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({global:this.globalConstraints,individual:this.individualConstraints})});if(!r.ok)this.lastTechnicalError='Nie udało się zapisać kolejności zasad.'},
openRules(){this.mainTab='advanced';this.$nextTick(()=>{let e=document.getElementById('rulesDetails');if(e){e.open=true;e.scrollIntoView({behavior:'smooth',block:'start'})}})},
friendlyDescription(x){return String(x||'').replace(/\\bHARD\\b/gi,'Musi być').replace(/\\bSOFT\\b/gi,'Zalecane')},
formatDutyChange(d){let scope=d.scope==='1–3'?'1–3':'szkoła';return [scope,d.abbr,d.slot,d.place].filter(Boolean).join(' • ')},
async loadTeacherRegistry(){try{let r=await fetch('/api/teachers?ts='+Date.now(),{cache:'no-store'});let x=await r.json();this.teacherRegistry=x.teachers||[];if(!this.portalTeacherName)this.portalTeacherName=this.teacherRegistry.find(t=>t.active)?.name||''}catch(e){this.teacherAdminMessage='Nie udało się wczytać rejestru: '+e.message}},
async addTeacherAdmin(){let name=this.newTeacher.name.trim();if(!name){this.teacherAdminMessage='Podaj imię i nazwisko.';return}let r=await fetch('/api/teachers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(this.newTeacher)});let x=await r.json();if(!r.ok){this.teacherAdminMessage=x.detail||'Błąd dodawania';return}this.newTeacher={name:'',group:'school'};this.teacherAdminMessage='Dodano '+x.name+'.';await this.reload();await this.loadTeacherRegistry()},
async updateTeacherAdmin(t){let r=await fetch('/api/teachers/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:t.name,group:t.group,active:t.active})});if(!r.ok){let x=await r.json();this.teacherAdminMessage=x.detail||'Błąd zapisu';return}this.teacherAdminMessage='Zapisano: '+t.name;await this.reload();await this.loadTeacherRegistry()},
teacherPortalUrl(t){return location.origin+'/teacher?t='+encodeURIComponent(t.portal_token)},
openTeacherPortalFor(t){window.open(this.teacherPortalUrl(t),'_blank','noopener')},
async copyTeacherPortalFor(t){try{await navigator.clipboard.writeText(this.teacherPortalUrl(t));this.teacherAdminMessage='Skopiowano link dla '+t.name}catch(e){this.teacherAdminMessage='Nie udało się skopiować linku.'}},""")

s=s.replace("let name=nameMap.get(canonName(raw));if(!name){unmatched.push(raw);continue}","let name=nameMap.get(canonName(raw))||raw")
s=s.replace("this.importPdfReport='zaktualizowano '+out.updated_teachers.length+' nauczycieli, '+out.lesson_slots+' zajętych slotów'+(unmatched.length?'; nierozpoznane: '+[...new Set(unmatched)].join(', '):'')+(out.unknown?.length?'; brak w bazie: '+out.unknown.join(', '):'')",
            "this.importPdfReport='zaktualizowano '+out.updated_teachers.length+' nauczycieli, '+out.lesson_slots+' zajętych slotów'+(out.added_teachers?.length?'; automatycznie dodano: '+out.added_teachers.map(x=>x.name+' ('+groupLabelText(x.group)+')').join(', '):'')+(out.unknown?.length?'; nierozpoznane: '+out.unknown.join(', '):'')")
s=s.replace("function canonName(s){","function groupLabelText(g){return g==='1-3'?'1–3':(g==='wf'?'WF':'ogólny')}\nfunction canonName(s){")

# ensure registry loads during reload
needle="await Promise.all([this.refreshValidation(),this.refreshHealth()])}"
if needle in s:
    s=s.replace(needle,"await Promise.all([this.refreshValidation(),this.refreshHealth(),this.loadTeacherRegistry()])}",1)

s=s.replace("Dyżury v5.5","Dyżury v5.6")
p.write_text(s,encoding="utf-8")
print("patched ui",len(s.splitlines()))
