
pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
function canonName(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim().split(/\s+/).filter(Boolean).sort().join(' ')}
function dlBlob(blob,name){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},200)}
const {createApp}=Vue;
const MatrixView={
props:['cfg','day','assign13','school','manual','mode'],
computed:{dc(){return{'PoniedziaĹ‚ek':'Pn','Wtorek':'Wt','Ĺšroda':'Ĺšr','Czwartek':'Czw','PiÄ…tek':'Pi'}[this.day]},
teachers(){return this.cfg.teachers},
rows(){let a=this.cfg.timeline[this.day]||[];if(this.mode==='duties')return a.filter(x=>x.kind==='PRZERWA');if(this.mode==='lessons')return a.filter(x=>x.kind==='LEKCJA');return a},
new13(){let m={};for(let r of(this.assign13||[]))for(let a of(r.assignments||[]))if(a.teacher)m[r.abbr+'|'+r.label+'|'+a.teacher]=a;return m},
sch(){let m={};for(let x of(this.school||[]))if(x.teacher){let k=x.abbr+'|'+x.slot+'|'+x.teacher;(m[k]||(m[k]=[])).push(x.location)}return m}},
methods:{
dutyRow(slot){return (this.assign13||[]).find(r=>r.abbr===this.dc&&r.label===slot.key)},
lessons(t,slot){return t.lessons?.[this.dc]?.[slot.key]||[]},
d13(t,slot){return this.new13[this.dc+'|'+slot.key+'|'+t.name]},
schoolLoc(t,slot){return this.sch[this.dc+'|'+slot.key+'|'+t.name]||[]},
manualBlock(t,slot){return (this.manual[t.name]||[]).includes(this.dc+'|'+slot.key)},
short(s){return String(s).replace('e_wczesnoszk','wczesn.').replace('e_wczesnosz','wczesn.').replace('zaj_komp_1_3','komp.').replace('j. angielski','ang.').replace('ang_1_3','ang.').replace('wf_1_3','WF').replace('e_plastyczna','plastyka').replace('e_muzyczna','muzyka')},
klass(t,slot){if(slot.kind==='LEKCJA'&&this.lessons(t,slot).length)return'lesson';if(slot.kind==='PRZERWA'){if(this.schoolLoc(t,slot).length)return'schoold';let d=this.d13(t,slot);if(d)return'd13 '+(d.wait?'wait':'');if(this.manualBlock(t,slot))return'manual'}return''}
},
template:`<table class="sheet"><thead><tr><th class="fixed1">Godzina</th><th class="fixed2">Slot</th><th v-for="t in teachers" class="teacher-head" :class="{secondary:!t.core}"><div>{{t.name}}</div></th></tr></thead>
<tbody><tr v-for="slot in rows"><td class="fixed1">{{slot.time}}</td><td class="fixed2">{{slot.kind==='LEKCJA'?'L'+slot.label:(slot.label+(dutyRow(slot)?.required_people===1?' â€˘ 1 os.':''))}}</td>
<td v-for="t in teachers" :class="klass(t,slot)">
<template v-if="slot.kind==='LEKCJA'"><div v-for="x in lessons(t,slot)"><div class="c">{{x.class}}</div><div class="s">{{short(x.subject)}}</div><div class="r">{{x.room}}</div></div></template>
<template v-else><div v-if="schoolLoc(t,slot).length">SZKOĹA<br>{{schoolLoc(t,slot).join(', ')}}</div><div v-else-if="d13(t,slot)">1â€“3 â€˘ {{d13(t,slot).station}}<span v-if="d13(t,slot).wait"><br>âš  czekanie</span></div><div v-else-if="manualBlock(t,slot)">â›”</div></template>
</td></tr></tbody></table>`
};
createApp({
components:{MatrixView},
data(){return{cfg:null,mainTab:'13',selected13Day:'PoniedziaĹ‚ek',selectedSchoolDay:'PoniedziaĹ‚ek',search13:'',searchSchool:'',blockTeacher:'',
manualBlocks:{},rows13:[],schoolCurrent:[],schoolPreview:[],displayMode13:'all',displayModeSchool:'all',sum13:null,sumSchool:null,waits13:[],waitsSchool:[],missing13:[],incomplete13:[],minPeople13:{},showWait13:false,showMissing13:false,showWaitSchool:false,solving13:false,lastSolve13:'',solveError13:'',recalculating:false,calcMessage:'',lastFullRecalc:'',refreshEpoch:0,repair:null,repairBusy:false,statsSearch:'',statsGroupFilter:'',
variantName:'',variantNote:'',variants:[],importPdfBusy:false,importPdfReport:'',mapSlot:'1/2',edit:{day:'PoniedziaĹ‚ek',slot:'1/2',location:'15',teacher:''},globalConstraints:[],individualConstraints:[],constraintFilter:'',constraintScopeFilter:'',newConstraint:{teacher:'',scope:'oba',rule:'unavailable',kind:'hard',priority:3,day:'',slot:'',location:'',value:0,enabled:true},
teacherPlanSearch:'',diag13:{},diagSchool:{},validation:{ok:true,errors:0,warnings:0,problems:[]},serverHealth:null,draggedConstraintIndex:null,
f13:{enabled_teachers:[],manual_blocks:{},max_per_day:3,station_names:{A:'',B:''}},
fschool:{enabled_teachers:[],manual_blocks:{},max_per_day:4}}},
computed:{
days(){return['PoniedziaĹ‚ek','Wtorek','Ĺšroda','Czwartek','PiÄ…tek']},schoolSlots(){return this.cfg.schoolDuty.slots},
filtered13(){let q=this.search13.toLowerCase();return this.cfg.teachers.filter(t=>t.name.toLowerCase().includes(q))},
filteredSchool(){let q=this.searchSchool.toLowerCase();return this.cfg.teachers.filter(t=>t.name.toLowerCase().includes(q))},
filteredTeacherPlans(){let q=this.teacherPlanSearch.toLowerCase();return this.cfg.teachers.filter(t=>!q||t.name.toLowerCase().includes(q))},
dayCodeOptions(){return[{label:'PoniedziaĹ‚ek',code:'Pn'},{label:'Wtorek',code:'Wt'},{label:'Ĺšroda',code:'Ĺšr'},{label:'Czwartek',code:'Czw'},{label:'PiÄ…tek',code:'Pi'}]},
priorityOptions(){return[{value:1,label:'Drobna preferencja'},{value:2,label:'Niska'},{value:3,label:'Normalna'},{value:4,label:'Wysoka'},{value:5,label:'NajwyĹĽsza'}]},
allBreakSlots(){return[...new Set(this.cfg.breaks.map(b=>b.label))]},
staffingRows(){return this.cfg.breaks.map(b=>({day:b.day,abbr:b.abbr,slot:b.label,time:b.time,key:b.abbr+'|'+b.label}))},
individualRuleTypes(){return[
{key:'unavailable',label:'NiedostÄ™pny w slocie'},
{key:'avoid_slot',label:'Unikaj slotu'},
{key:'prefer_slot',label:'Preferuj slot'},
{key:'require_slot',label:'Wymagaj tego nauczyciela w slocie'},
{key:'avoid_day',label:'Unikaj dnia'},
{key:'prefer_day',label:'Preferuj dzieĹ„'},
{key:'avoid_location',label:'Unikaj miejsca'},
{key:'prefer_location',label:'Preferuj miejsce'},
{key:'no_before_lesson',label:'Nie dawaj tylko przed lekcjÄ…'},
{key:'no_after_lesson',label:'Nie dawaj tylko po lekcji'},
{key:'max_day',label:'Maksimum dziennie'},
{key:'max_week',label:'Maksimum tygodniowo'}]},
filteredIndividualConstraints(){let q=this.constraintFilter.toLowerCase();return this.individualConstraints.filter(r=>(!q||r.teacher.toLowerCase().includes(q))&&(!this.constraintScopeFilter||r.scope===this.constraintScopeFilter))},
blockRows(){let out=[];for(let d of[{day:'PoniedziaĹ‚ek',code:'Pn'},{day:'Wtorek',code:'Wt'},{day:'Ĺšroda',code:'Ĺšr'},{day:'Czwartek',code:'Czw'},{day:'PiÄ…tek',code:'Pi'}])for(let s of this.cfg.breaks.filter(b=>b.abbr===d.code))out.push({day:d.day,code:d.code,slot:s.label});return out},
schoolDisplay(){return this.schoolPreview.length?this.schoolPreview:this.schoolCurrent},
selectedSchoolCode(){return{'PoniedziaĹ‚ek':'Pn','Wtorek':'Wt','Ĺšroda':'Ĺšr','Czwartek':'Czw','PiÄ…tek':'Pi'}[this.selectedSchoolDay]},
statisticsRows(){let m={};for(let t of this.cfg.teachers)m[t.name]={name:t.name,group:t.group,d13:0,school:0,total:0,minutes:0,long:0,wait:0,Pn:0,Wt:0,'Ĺšr':0,Czw:0,Pi:0};let mins={};for(let b of this.cfg.breaks)mins[b.abbr+'|'+b.label]=Number(b.minutes||0);for(let r of(this.rows13||[]))for(let a of(r.assignments||[])){if(!a.teacher||!m[a.teacher])continue;let x=m[a.teacher],mm=mins[r.abbr+'|'+r.label]||0;x.d13++;x.total++;x.minutes+=mm;if(mm>=15)x.long++;if(a.wait)x.wait++;x[r.abbr]++}for(let d of(this.schoolDisplay||[])){if(!d.teacher||!m[d.teacher])continue;let x=m[d.teacher],mm=mins[d.abbr+'|'+d.slot]||0;x.school++;x.total++;x.minutes+=mm;if(mm>=15)x.long++;if(d.wait)x.wait++;x[d.abbr]++}return Object.values(m).sort((a,b)=>b.total-a.total||a.name.localeCompare(b.name,'pl'))},
filteredStatistics(){let q=this.statsSearch.toLowerCase();return this.statisticsRows.filter(x=>(!q||x.name.toLowerCase().includes(q))&&(!this.statsGroupFilter||x.group===this.statsGroupFilter))},
validationCount(){return Number(this.validation?.errors||0)+Number(this.validation?.warnings||0)},
diagnosticCount(){return Number(this.diag13?.unresolved?.length||0)+Number(this.diagSchool?.unresolved?.length||0)},
diagnosticProblemCount(){return this.diagnosticCount+this.validationCount},
repairGroups(){if(!this.repair)return[];return[{title:'Korytarz 1?3',data:this.repair.school13},{title:'Ca?a szko?a',data:this.repair.school}]},
statsSummary(){let rows=this.statisticsRows,active=rows.filter(x=>x.total>0),sum=rows.reduce((a,x)=>a+x.total,0),minutes=rows.reduce((a,x)=>a+x.minutes,0),mx=active.length?Math.max(...active.map(x=>x.total)):0;return{active:active.length,total:sum,minutes,avg:active.length?(sum/active.length).toFixed(1):'0.0',max:mx}}
},
watch:{
mainTab(v){if(v==='diagnostics')this.$nextTick(()=>Promise.all([this.refreshValidation(),this.refreshHealth()]))}
},
methods:{
isFixedConstraint(c){return['no_lesson_overlap','one_place_per_slot','cross_scope_conflict','manual_blocks'].includes(c?.key)},
constraintValue(k){let c=this.globalConstraints.find(x=>x.key===k);return c&&c.enabled?c.value:'wyĹ‚Ä…czony'},
ruleLabel(k){let r=this.individualRuleTypes.find(x=>x.key===k);return r?r.label:k},
constraintConfig(c){let m={
max_day_13:{label:'Maksimum dyĹĽurĂłw / dzieĹ„',min:0,max:10},
max_day_school:{label:'Maksimum dyĹĽurĂłw / dzieĹ„',min:0,max:10},
max_week:{label:'Maksimum dyĹĽurĂłw / tydzieĹ„',min:0,max:30},
long_break_penalty:{label:'DĹ‚uga przerwa od (min)',min:5,max:30},
max_long_day:{label:'Limit dzienny (0â€“2)',min:0,max:2},
max_long_week:{label:'Limit tygodniowy (0â€“10)',min:0,max:10}
};return m[c.key]||null},
dragConstraintStart(i){this.draggedConstraintIndex=i},
dropConstraint(i){let from=this.draggedConstraintIndex;if(from===null||from===i)return;let [row]=this.globalConstraints.splice(from,1);this.globalConstraints.splice(i,0,row);this.draggedConstraintIndex=null},
async refreshValidation(){try{let r=await fetch('/api/validation',{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({global:this.globalConstraints,individual:this.individualConstraints,min_people_13:this.minPeople13})});if(!r.ok)throw new Error('HTTP '+r.status);this.validation=await r.json()}catch(e){this.validation={ok:false,errors:1,warnings:0,problems:[{severity:'error',message:'Nie moĹĽna pobraÄ‡ walidacji: '+e.message}]}}},
async refreshHealth(){try{let r=await fetch('/api/health?ts='+Date.now(),{cache:'no-store'});this.serverHealth=await r.json()}catch(e){this.serverHealth={ok:false,version:'?',engine:'OR-Tools CP-SAT',error:e.message}}},
async syncWorkingState(){this.syncManual();let c=await fetch('/api/constraints',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({global:this.globalConstraints,individual:this.individualConstraints})});if(!c.ok)throw new Error('nie zapisano constraintĂłw');let m=await fetch('/api/min-people-13',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({min_people_13:this.minPeople13})});if(!m.ok)throw new Error('nie zapisano obsady 1â€“3');let st=await fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled_teachers_13:this.f13.enabled_teachers,enabled_teachers_school:this.fschool.enabled_teachers,manual_blocks:this.manualBlocks,station_names:this.f13.station_names})});if(!st.ok)throw new Error('nie zapisano stanu roboczego')},
async recalculateAll(){if(this.recalculating)return;this.recalculating=true;this.solveError13='';this.repair=null;try{this.calcMessage='1/5 ZapisujÄ™ bieĹĽÄ…ce ustawienia i constraintyâ€¦';await this.syncWorkingState();this.calcMessage='2/5 Przeliczam dyĹĽury 1â€“3â€¦';await this.solve13();if(this.solveError13)throw new Error(this.solveError13);this.calcMessage='3/5 Przeliczam plan caĹ‚ej szkoĹ‚yâ€¦';await this.solveSchool();if(this.diagSchool?.status==='ERROR')throw new Error(this.diagSchool.error||'bĹ‚Ä…d solvera szkoĹ‚y');this.calcMessage='4/5 OdĹ›wieĹĽam tabele, liczniki, walidacjÄ™ i dane ĹşrĂłdĹ‚oweâ€¦';let fresh=await(await fetch('/api/config?ts='+Date.now(),{cache:'no-store'})).json();this.cfg=fresh;for(let b of this.cfg.breaks){let k=b.abbr+'|'+b.label;if(!(k in this.minPeople13))this.minPeople13[k]=Number((fresh.state.min_people_13||{})[k]||2)}await Promise.all([this.refreshValidation(),this.refreshHealth()]);this.refreshEpoch++;this.lastFullRecalc=new Date().toLocaleTimeString('pl-PL');if(this.diagnosticCount>0){this.calcMessage='5/5 Szukam najmniejszego poluzowania reguĹ‚ dla peĹ‚nej obsadyâ€¦';await this.refreshRepair(true)}else{this.calcMessage='Przeliczono caĹ‚y plan. Wszystkie stanowiska sÄ… obsadzone.'}}catch(e){this.calcMessage='BĹ‚Ä…d peĹ‚nego przeliczenia: '+e.message;this.solveError13=this.calcMessage}finally{this.recalculating=false;if(!this.calcMessage.startsWith('BĹ‚Ä…d')&&this.diagnosticCount>0)this.calcMessage='Przeliczono caĹ‚y plan. PozostaĹ‚o '+this.diagnosticCount+' nieobsadzonych stanowisk â€” propozycje sÄ… w Diagnostyce.'}},
async refreshRepair(silent=false){if(this.repairBusy)return;this.repairBusy=true;try{let body={global:this.globalConstraints,individual:this.individualConstraints,min_people_13:this.minPeople13,manual_blocks:this.manualBlocks,last_13_assignments:this.rows13,school_assignments:this.schoolCurrent,enabled_teachers_13:this.f13.enabled_teachers,enabled_teachers_school:this.fschool.enabled_teachers};let r=await fetch('/api/diagnostics/repair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error('HTTP '+r.status);this.repair=await r.json()}catch(e){if(!silent)alert('Nie udaĹ‚o siÄ™ policzyÄ‡ propozycji: '+e.message)}finally{this.repairBusy=false}},
async applyRepairSuggestion(sug){for(let ch of(sug.changes||[])){if(ch.token.startsWith('g:')){let key=ch.token.slice(2),c=this.globalConstraints.find(x=>x.key===key);if(c){c.enabled=true;c.kind='soft'}}else if(ch.token.startsWith('i:')){let id=ch.token.slice(2),c=this.individualConstraints.find(x=>String(x.id)===id);if(c)c.kind='soft'}}await this.recalculateAll()},
lessonText(t,dc,p){let a=t.lessons?.[dc]?.[String(p)]||[];return a.map(x=>[x.class,x.subject,x.room].filter(Boolean).join(' â€˘ ')).join(' / ')},
dutyText(name,dc,slot){let out=[];let r=(this.rows13||[]).find(x=>x.abbr===dc&&x.label===slot);for(let a of (r?.assignments||[]))if(a.teacher===name)out.push('1â€“3 '+a.station);for(let x of (this.schoolDisplay||[]))if(x.teacher===name&&x.abbr===dc&&x.slot===slot)out.push('szkoĹ‚a '+x.location);return out.join(' â€˘ ')},
teacherStats(name){return this.statisticsRows.find(x=>x.name===name)||null},
addIndividualConstraint(){if(!this.newConstraint.teacher){alert('Wybierz nauczyciela.');return}if(this.newConstraint.rule==='require_slot'&&(!this.newConstraint.day||!this.newConstraint.slot)){alert('Dla przypisania wybierz dzieĹ„ i slot.');return}let r=JSON.parse(JSON.stringify(this.newConstraint));r.id='ic_'+Date.now()+'_'+Math.random().toString(36).slice(2,7);this.individualConstraints.push(r)},
removeIndividualConstraint(id){this.individualConstraints=this.individualConstraints.filter(x=>x.id!==id)},
async saveConstraints(andSolve){let r=await fetch('/api/constraints',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({global:this.globalConstraints,individual:this.individualConstraints})});if(!r.ok){alert('BĹ‚Ä…d zapisu reguĹ‚');return}await this.refreshValidation();if(andSolve){await this.recalculateAll()}else{this.diag13={};this.diagSchool={};this.repair=null;alert('ReguĹ‚y zapisane. Uruchom â€žPrzelicz wszystkoâ€ť, aby odĹ›wieĹĽyÄ‡ plan.')}},
resetMinPeople(){for(let r of this.staffingRows)this.minPeople13[r.key]=2},
async saveMinPeople(andSolve){let r=await fetch('/api/min-people-13',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({min_people_13:this.minPeople13})});if(!r.ok){alert('BĹ‚Ä…d zapisu obsady');return}await this.refreshValidation();if(andSolve)await this.recalculateAll()},
allNames(){return this.cfg.teachers.map(t=>t.name)},coreNames(){return this.groupNames('1-3')},nonCoreNames(){return this.groupNames('school')},
groupNames(g){return this.cfg.teachers.filter(t=>t.group===g).map(t=>t.name)},
groupLabel(g){return g==='1-3'?'1â€“3':(g==='wf'?'WF':'ogĂłlni')},
addGroup13(g){this.f13.enabled_teachers=[...new Set([...this.f13.enabled_teachers,...this.groupNames(g)])]},
async addGroup13AndSolve(g){this.addGroup13(g);await this.recalculateAll()},
addGroupSchool(g){this.fschool.enabled_teachers=[...new Set([...this.fschool.enabled_teachers,...this.groupNames(g)])]},
isManual(n,dc,s){return(this.manualBlocks[n]||[]).includes(dc+'|'+s)},toggleBlock(n,dc,s){if(!this.manualBlocks[n])this.manualBlocks[n]=[];let k=dc+'|'+s,a=this.manualBlocks[n],i=a.indexOf(k);if(i>=0)a.splice(i,1);else a.push(k);this.syncManual()},
syncManual(){this.f13.manual_blocks=this.manualBlocks;this.fschool.manual_blocks=this.manualBlocks},
async solve13(){this.solving13=true;this.solveError13='';this.syncManual();try{let mr=await fetch('/api/min-people-13',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({min_people_13:this.minPeople13})});if(!mr.ok)throw new Error('zapis obsady HTTP '+mr.status);let r=await fetch('/api/solve/13',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(this.f13)});if(!r.ok)throw new Error('solver HTTP '+r.status);let d=await r.json();this.rows13=d.rows;this.sum13=d.summary;this.waits13=d.waits||[];this.missing13=d.unresolved_details||[];this.incomplete13=d.incomplete_breaks||[];this.diag13=d.diagnostics||{};this.showWait13=this.waits13.length>0;this.showMissing13=this.incomplete13.length>0;let sr=await fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({last_13_assignments:this.rows13,manual_blocks:this.manualBlocks,enabled_teachers_13:this.f13.enabled_teachers,station_names:this.f13.station_names})});if(!sr.ok)throw new Error('zapis stanu HTTP '+sr.status);this.lastSolve13=new Date().toLocaleTimeString('pl-PL');await this.refreshValidation();}catch(err){this.solveError13='BĹ‚Ä…d przeliczania: '+err.message;}finally{this.solving13=false}},
async solveSchool(){this.syncManual();try{let r=await fetch('/api/solve/school',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(this.fschool)});if(!r.ok)throw new Error('solver HTTP '+r.status);let d=await r.json();this.schoolPreview=d.assignments;this.sumSchool=d.summary;this.waitsSchool=d.waits||[];this.diagSchool=d.diagnostics||{};await this.refreshValidation()}catch(e){this.diagSchool={status:'ERROR',unresolved:[],hard_rejections:[],error:e.message};alert('BĹ‚Ä…d solvera szkoĹ‚y: '+e.message)}},
async applySchoolPreview(){if(!this.schoolPreview.length)return;this.schoolCurrent=JSON.parse(JSON.stringify(this.schoolPreview));this.schoolPreview=[];await this.saveSchoolCurrent()},
editSchoolCell(){let dc={'PoniedziaĹ‚ek':'Pn','Wtorek':'Wt','Ĺšroda':'Ĺšr','Czwartek':'Czw','PiÄ…tek':'Pi'}[this.edit.day];let x=this.schoolCurrent.find(x=>x.abbr===dc&&x.slot===this.edit.slot&&x.location===this.edit.location);if(x)x.teacher=this.edit.teacher;else alert('W ĹşrĂłdle nie ma takiego stanowiska.')},
async saveSchoolCurrent(){await fetch('/api/school/current',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({assignments:this.schoolCurrent})});await fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({manual_blocks:this.manualBlocks,enabled_teachers_school:this.fschool.enabled_teachers,max_per_day_school:this.fschool.max_per_day})});await this.refreshValidation();alert('BieĹĽÄ…cy plan zapisany.')},
schoolWho(dc,loc,slot){let x=this.schoolDisplay.find(x=>x.abbr===dc&&x.location===loc&&x.slot===slot);return x?.teacher||''},
async saveVariant(){let settings={enabled_teachers_13:this.f13.enabled_teachers,enabled_teachers_school:this.fschool.enabled_teachers,manual_blocks:this.manualBlocks,max_per_day_13:this.f13.max_per_day,max_per_day_school:this.fschool.max_per_day,station_names:this.f13.station_names,min_people_13:this.minPeople13};let body={name:this.variantName,note:this.variantNote,school_assignments:this.schoolDisplay,assignments_13:this.rows13,settings};let r=await fetch('/api/variants',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let v=await r.json();this.variants.push({id:v.id,name:v.name,created_at:v.created_at,note:v.note});this.variantName='';this.variantNote=''},
async loadVariant(id){await fetch('/api/variants/'+id+'/load',{method:'POST'});await this.reload();this.mainTab='variants'},
exportExcel(){
let wb=XLSX.utils.book_new();
let a13=[['DzieĹ„','Godzina','Slot','Punkt A','Punkt B']];
for(let r of this.rows13){let m={};for(let a of(r.assignments||[]))m[a.station]=a.teacher||'';a13.push([r.day,r.time,r.label,m.A||'',m.B||''])}
let ws13=XLSX.utils.aoa_to_sheet(a13);ws13['!cols']=[{wch:16},{wch:15},{wch:8},{wch:28},{wch:28}];XLSX.utils.book_append_sheet(wb,ws13,'Korytarz 1-3');
for(let d of this.days){let dc={'PoniedziaĹ‚ek':'Pn','Wtorek':'Wt','Ĺšroda':'Ĺšr','Czwartek':'Czw','PiÄ…tek':'Pi'}[d];let aoa=[[d,...this.schoolSlots]];for(let loc of this.cfg.schoolDuty.locations){let row=[loc];for(let s of this.schoolSlots){let x=this.schoolDisplay.find(z=>z.abbr===dc&&z.location===loc&&z.slot===s);row.push(x?.teacher||'')}aoa.push(row)}let ws=XLSX.utils.aoa_to_sheet(aoa);ws['!cols']=[{wch:18},...this.schoolSlots.map(()=>({wch:24}))];XLSX.utils.book_append_sheet(wb,ws,'SzkoĹ‚a '+dc)}
let cg=[['ReguĹ‚a','Zakres','Typ','Aktywna','Priorytet','WartoĹ›Ä‡']];for(let c of this.globalConstraints)cg.push([c.label,c.scope,c.kind,c.enabled?'TAK':'NIE',c.priority??'',c.value??'']);XLSX.utils.book_append_sheet(wb,XLSX.utils.aoa_to_sheet(cg),'Constrainty');
XLSX.writeFile(wb,'DEMO_dyzury_'+new Date().toISOString().slice(0,10)+'.xlsx')},
async exportA4(scope){
let box=document.createElement('div');box.style.cssText='position:fixed;left:-10000px;top:0;width:1400px;height:990px;background:white;padding:22px;font-family:Arial;color:#111;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:repeat(3,1fr);gap:14px';
const mk=(title,headers,rows)=>{let d=document.createElement('div');d.style.cssText='border:1px solid #777;padding:7px;overflow:hidden';let h=document.createElement('div');h.textContent=title;h.style.cssText='font-size:18px;font-weight:bold;text-align:center;margin-bottom:5px';d.appendChild(h);let t=document.createElement('table');t.style.cssText='border-collapse:collapse;width:100%;font-size:10px';let tr=document.createElement('tr');for(let x of headers){let th=document.createElement('th');th.textContent=x;th.style.cssText='border:1px solid #777;background:#d9eaf7;padding:3px';tr.appendChild(th)}t.appendChild(tr);for(let row of rows){let rr=document.createElement('tr');for(let x of row){let td=document.createElement('td');td.textContent=x||'';td.style.cssText='border:1px solid #aaa;padding:2px;text-align:center;height:19px';rr.appendChild(td)}t.appendChild(rr)}d.appendChild(t);return d};
if(scope==='school'){for(let day of this.days){let dc={'PoniedziaĹ‚ek':'Pn','Wtorek':'Wt','Ĺšroda':'Ĺšr','Czwartek':'Czw','PiÄ…tek':'Pi'}[day];let rows=this.cfg.schoolDuty.locations.map(loc=>[loc,...this.schoolSlots.map(s=>this.schoolDisplay.find(x=>x.abbr===dc&&x.location===loc&&x.slot===s)?.teacher||'')]);box.appendChild(mk(day,['Miejsce',...this.schoolSlots],rows))}}
else{for(let day of this.days){let rs=this.rows13.filter(x=>x.day===day);let rows=rs.map(r=>{let m={};for(let a of r.assignments||[])m[a.station]=a.teacher||'';return[r.time,r.label,m.A||'',m.B||'']});box.appendChild(mk(day,['Godzina','Slot','Punkt A','Punkt B'],rows))}}
document.body.appendChild(box);let canvas=await html2canvas(box,{scale:2,backgroundColor:'#fff',useCORS:true});box.remove();canvas.toBlob(b=>dlBlob(b,'DEMO_'+(scope==='school'?'plan_szkoly':'dyzury_1-3')+'_A4_'+new Date().toISOString().slice(0,10)+'.png'),'image/png')},
async importTeacherPdf(e){
let files=[...e.target.files];e.target.value='';if(!files.length)return;this.importPdfBusy=true;this.importPdfReport='';let all=[];let unmatched=[];try{for(let f of files){let parsed=await this.parseAscPdf(f);all.push(...parsed.teachers);unmatched.push(...parsed.unmatched)}let by=new Map();for(let t of all)by.set(t.name,t);let payload={source_name:files.map(f=>f.name).join(', '),teachers:[...by.values()]};let r=await fetch('/api/import/teacher-lessons',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});let out=await r.json();if(!r.ok)throw new Error(out.detail||'BĹ‚Ä…d serwera');await this.reload();this.importPdfReport='zaktualizowano '+out.updated_teachers.length+' nauczycieli, '+out.lesson_slots+' zajÄ™tych slotĂłw'+(unmatched.length?'; nierozpoznane: '+[...new Set(unmatched)].join(', '):'')+(out.unknown?.length?'; brak w bazie: '+out.unknown.join(', '):'')}catch(err){this.importPdfReport='BĹÄ„D: '+err.message}finally{this.importPdfBusy=false}},
async parseAscPdf(file){
let pdf=await pdfjsLib.getDocument({data:await file.arrayBuffer()}).promise;let teachers=[];let unmatched=[];let nameMap=new Map(this.cfg.teachers.map(t=>[canonName(t.name),t.name]));
for(let pn=1;pn<=pdf.numPages;pn++){let page=await pdf.getPage(pn),vp=page.getViewport({scale:1}),tc=await page.getTextContent();let its=tc.items.filter(i=>String(i.str||'').trim()).map(i=>({str:String(i.str).trim(),x:i.transform[4],y:vp.height-i.transform[5],w:i.width||0,h:i.height||Math.abs(i.transform[3])||8}));let heads=its.filter(i=>i.str.startsWith('Nauczyciel ')&&i.y<35).sort((a,b)=>a.x-b.x);if(!heads.length)continue;let hc=heads.map(h=>h.x+h.w/2);for(let hi=0;hi<heads.length;hi++){let L=hi?(hc[hi-1]+hc[hi])/2:0,R=hi<heads.length-1?(hc[hi]+hc[hi+1])/2:vp.width;let raw=heads[hi].str.replace(/^Nauczyciel\s+/,'');let name=nameMap.get(canonName(raw));if(!name){unmatched.push(raw);continue}let block=its.filter(i=>{let cx=i.x+i.w/2;return cx>=L&&cx<R});let dayNames=['Pn','Wt','Ĺšr','Czw','Pi'];let dx={};for(let i of block)if(dayNames.includes(i.str)&&i.y>28&&i.y<55)dx[i.str]=i.x+i.w/2;let bw=R-L;if(Object.keys(dx).length<5)dayNames.forEach((d,k)=>dx[d]=L+bw*[.198,.373,.548,.723,.898][k]);let xs=dayNames.map(d=>dx[d]),xe=[L+40];for(let k=0;k<4;k++)xe.push((xs[k]+xs[k+1])/2);xe.push(R-5);let py={};for(let i of block)if(/^[1-9]$/.test(i.str)&&i.x<L+50&&i.y>45&&i.y<285)py[+i.str]=i.y;for(let k=1;k<=9;k++)if(!py[k])py[k]=67.6+(k-1)*25.32;let ys=[1,2,3,4,5,6,7,8,9].map(k=>py[k]),ye=[49];for(let k=0;k<8;k++)ye.push((ys[k]+ys[k+1])/2);ye.push(283);let lessons={Pn:{},Wt:{},'Ĺšr':{},Czw:{},Pi:{}};
for(let di=0;di<5;di++){let temp={};for(let per=1;per<=9;per++){let xL=xe[di],xR=xe[di+1],yT=ye[per-1],yB=ye[per];let cc=block.filter(i=>{let cx=i.x+i.w/2;return cx>=xL&&cx<xR&&i.y>=yT&&i.y<yB&&!dayNames.includes(i.str)&&!/^[1-9]$/.test(i.str)});if(!cc.length)continue;let sub=[],cl=[],room=[];for(let i of cc.sort((a,b)=>a.x-b.x)){let rx=(i.x+i.w/2-xL)/(xR-xL);if(rx<.47)sub.push(i.str);else if(rx<.72)cl.push(i.str);else room.push(i.str)}temp[per]={class:cl.join(' ').trim(),subject:sub.join(' ').trim(),room:room.join(' ').trim()}}
for(let per=1;per<=8;per++){let a=temp[per],b=temp[per+1];if(a&&b&&a.subject&&!a.class&&b.class&&!b.subject&&!b.room){let v={class:b.class,subject:a.subject,room:a.room||'â€”'};temp[per]=v;temp[per+1]={...v}}}
for(let per=1;per<=9;per++){let a=temp[per];if(!a)continue;if(!a.subject&&a.class&&!a.room)continue;lessons[dayNames[di]][String(per)]=[{class:a.class||'â€”',subject:a.subject||'â€”',room:a.room||'â€”'}]}}
teachers.push({name,lessons})}}
return{teachers,unmatched}},
exportJson(){let payload={school_assignments:this.schoolCurrent};let blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='DEMO_plan_dyzurow_'+new Date().toISOString().slice(0,10)+'.json';a.click();URL.revokeObjectURL(a.href)},
async importJson(e){let f=e.target.files[0];if(!f)return;try{let obj=JSON.parse(await f.text());let r=await fetch('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});if(!r.ok)throw new Error(await r.text());await this.reload();alert('Wczytano plik jako nowy punkt startowy.')}catch(err){alert('BĹ‚Ä…d importu: '+err.message)}e.target.value=''},
async reload(){this.cfg=await(await fetch('/api/config')).json();let s=this.cfg.state;this.manualBlocks=JSON.parse(JSON.stringify(s.manual_blocks||{}));this.schoolCurrent=JSON.parse(JSON.stringify(s.school_assignments||[]));this.rows13=JSON.parse(JSON.stringify(s.last_13_assignments||[]));this.variants=this.cfg.variant_meta||[];this.globalConstraints=JSON.parse(JSON.stringify(s.global_constraints||[]));this.individualConstraints=JSON.parse(JSON.stringify(s.individual_constraints||[]));this.minPeople13={};for(let b of this.cfg.breaks){let k=b.abbr+'|'+b.label;this.minPeople13[k]=Number((s.min_people_13||{})[k]||2)}this.newConstraint.teacher=this.cfg.teachers[0]?.name||'';this.f13={enabled_teachers:[...(s.enabled_teachers_13||this.allNames())],manual_blocks:this.manualBlocks,max_per_day:s.max_per_day_13||3,station_names:{...(s.station_names||{})}};this.fschool={enabled_teachers:[...(s.enabled_teachers_school||this.allNames())],manual_blocks:this.manualBlocks,max_per_day:s.max_per_day_school||4};this.blockTeacher=this.cfg.teachers[0]?.name||'';await Promise.all([this.refreshValidation(),this.refreshHealth()])}
},
async mounted(){await this.reload();this.calcMessage='Gotowe. â€žPrzelicz wszystkoâ€ť zapisze bieĹĽÄ…ce ustawienia i odĹ›wieĹĽy caĹ‚y interfejs.'}
}).mount('#app');

