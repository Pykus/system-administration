
const qs=new URLSearchParams(location.search), token=qs.get('t')||'';
const days=[['Pn','Poniedziałek'],['Wt','Wtorek'],['Śr','Środa'],['Czw','Czwartek'],['Pi','Piątek']];
let data=null,prefs={},prefComments={},relaxOrder=[],dragRelax=null,lastDutySig="",dutyPollTimer=null;
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function lessonText(day,p){let a=data.lessons?.[day]?.[String(p)]||[];return a.map(x=>[x.class,x.subject,x.room].filter(Boolean).map(esc).join(' • ')).join('<br>')}
function dutiesAt(day,slot){return (data.duties||[]).filter(x=>x.abbr===day&&x.slot===slot)}
function dutySourceText(){
 let s=data?.duty_source||{kind:'invalid_saved',label:'Brak zweryfikowanego planu',verified:false};
 let el=document.getElementById('dutySource');if(!el)return;
 let verified=!!s.verified;el.className='card '+(verified?'source-live':'source-saved');
 if(s.kind==='live_verified')el.innerHTML='<b>'+esc(s.label||'Szkic roboczy')+'</b><div class="note"><b>Widok roboczy, jeszcze niezapisany.</b> Ten panel korzysta z tego samego zweryfikowanego source_id co plan administratora: '+esc(s.source_id||'')+'.</div>';
 else if(s.kind==='reference_verified')el.innerHTML='<b>Plan referencyjny</b><div class="note">Nowy Solver jeszcze nie znalaz&#322; lepszego pe&#322;nego szkicu. Pokazywany jest ostatni zweryfikowany pe&#322;ny plan, identyczny z widokiem administratora. source_id: '+esc(s.source_id||'')+'.</div>';
 else if(s.kind==='saved_verified')el.innerHTML='<b>Plan zapisany i zweryfikowany</b><div class="note">source_id: '+esc(s.source_id||'')+'.</div>';
 else el.innerHTML='<b>UWAGA: brak zweryfikowanego pe&#322;nego planu</b><div class="note">Ten stan nie jest oznaczany jako pe&#322;ny.</div>';
}
function dutySignature(x){let s=x?.duty_source||{},d=x?.duties||[];return JSON.stringify([s.kind,s.variant_id,s.seq,s.job_status,d.map(z=>[z.scope,z.abbr,z.slot,z.place,z.wait])])}
async function refreshDuties(){
 try{
   let r=await fetch('/api/teacher-portal/'+encodeURIComponent(token),{cache:'no-store'});
   if(r.ok){
     let next=await r.json(),sig=dutySignature(next);
     if(sig!==lastDutySig){
       data.duties=next.duties||[];data.duty_source=next.duty_source||{};data.admin_locks=next.admin_locks||[];
       lastDutySig=sig;render()
     }
   }
 }catch(e){}
 clearTimeout(dutyPollTimer);dutyPollTimer=setTimeout(refreshDuties,5000)
}
function lockAt(day,slot){return (data.admin_locks||[]).find(x=>x.abbr===day&&x.slot===slot)||null}
function dutyText(day,slot){let a=dutiesAt(day,slot),l=lockAt(day,slot);let txt=a.map(x=>esc(x.scope)+' &bull; '+esc(x.place)+(x.wait?'<div class="wait">oczekiwanie: '+esc(x.wait)+' lek.</div>':'')).join('<br>');if(l)txt+=(txt?'<br>':'')+'<span class="adminlock">sta&#322;y przydzia&#322; administratora'+(l.location?' &bull; '+esc(l.location):'')+(l.comment?' &bull; '+esc(l.comment):'')+'</span>';return txt}
function timelineRows(){
 let rows=[],seen=new Set();
 for(const pair of days){for(const r of (data.timeline?.[pair[1]]||[])){let k=[r.time,r.kind,r.key,r.label].join('|');if(!seen.has(k)){seen.add(k);rows.push({...r})}}}
 function mins(x){let m=String(x.time||'').match(/^(\d{1,2}):(\d{2})/);return m?Number(m[1])*60+Number(m[2]):9999}
 rows.sort((a,b)=>mins(a)-mins(b)||String(a.kind).localeCompare(String(b.kind)));
 return rows
}
function dayHasRow(dayName,row){return (data.timeline?.[dayName]||[]).some(x=>x.kind===row.kind&&String(x.key)===String(row.key)&&String(x.time)===String(row.time))}
function renderRelaxOrder(){
 const cat=Object.fromEntries((data.relax_catalog||[]).map(x=>[x.key,x]));
 let list=relaxOrder.filter(k=>cat[k]);for(const x of (data.relax_catalog||[]))if(!list.includes(x.key))list.push(x.key);
 list=list.filter(k=>k!=='avoid_wait').concat(list.includes('avoid_wait')?['avoid_wait']:[]);
 relaxOrder=list;
 document.getElementById('relaxOrder').innerHTML=list.map((k,i)=>{let x=cat[k]||{label:k},locked=!!x.locked_last,active=(data.relaxed_rules||[]).includes(k);return '<div class="relax-item '+(locked?'locked-last ':'')+(active?'duty':'')+'" draggable="'+(!locked)+'" data-k="'+esc(k)+'"><span class="ord">'+(i+1)+'.</span><span class="grab">'+(locked?'':'☷')+'</span><span>'+esc(x.label)+(active?' <b>(aktywnie poluzowane w bieżącym planie)</b>':'')+'</span></div>'}).join('');
 document.querySelectorAll('#relaxOrder .relax-item[draggable="true"]').forEach(el=>{
  el.ondragstart=()=>{dragRelax=el.dataset.k;el.classList.add('dragging')};el.ondragend=()=>el.classList.remove('dragging');el.ondragover=e=>e.preventDefault();
  el.ondrop=e=>{e.preventDefault();let to=el.dataset.k;if(!dragRelax||dragRelax===to)return;let a=relaxOrder.filter(k=>k!=='avoid_wait'),from=a.indexOf(dragRelax),idx=a.indexOf(to);if(from<0||idx<0)return;a.splice(from,1);a.splice(idx,0,dragRelax);relaxOrder=a.concat(relaxOrder.includes('avoid_wait')?['avoid_wait']:[]);dragRelax=null;renderRelaxOrder()}
 });
}
function render(){
 document.getElementById('who').textContent=data.teacher.name;dutySourceText();
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
 for(const slot of slots){ph+='<tr><th>'+esc(slot)+'</th><td>'+esc(timeBy[slot]||'')+'</td>'+days.map(d=>{let k=d[0]+'|'+slot,v=prefs[k]||'neutral',c=prefComments[k]||'',l=lockAt(d[0],slot),dis=l?' disabled':'';return '<td><select data-k="'+esc(k)+'"'+dis+'><option value="neutral" '+(v==='neutral'?'selected':'')+'>neutralna</option><option value="prefer" '+(v==='prefer'?'selected':'')+'>preferowana</option><option value="avoid" '+(v==='avoid'?'selected':'')+'>niepo&#380;&#261;dana</option></select><input type="text" class="pref-comment" data-comment-k="'+esc(k)+'" value="'+esc(c)+'" placeholder="opcjonalny komentarz / pow&#243;d"'+dis+'>'+(l?'<div class="adminlock">sta&#322;y przydzia&#322; administratora'+(l.comment?' &bull; '+esc(l.comment):'')+'</div>':'')+'</td>'}).join('')+'</tr>'}
 ph+='</tbody></table>';document.getElementById('prefs').innerHTML=ph;
 document.querySelectorAll('#prefs select').forEach(x=>x.onchange=()=>{if(x.value==='neutral')delete prefs[x.dataset.k];else prefs[x.dataset.k]=x.value});document.querySelectorAll('#prefs input[data-comment-k]').forEach(x=>x.oninput=()=>{let k=x.dataset.commentK,v=x.value.trim();if(v)prefComments[k]=v.slice(0,500);else delete prefComments[k]});
 renderRelaxOrder();
}
async function load(){
 if(!token){document.getElementById('status').className='card error';document.getElementById('status').textContent='Brak indywidualnego tokenu w linku.';return}
 try{let r=await fetch('/api/teacher-portal/'+encodeURIComponent(token),{cache:'no-store'});if(!r.ok)throw new Error('Nieprawidłowy lub nieaktywny link.');data=await r.json();prefs={...(data.preferences||{})};prefComments={...(data.preference_comments||{})};relaxOrder=[...(data.relax_order||[])];lastDutySig=dutySignature(data);document.getElementById('status').hidden=true;document.getElementById('content').hidden=false;render();clearTimeout(dutyPollTimer);dutyPollTimer=setTimeout(refreshDuties,5000)}catch(e){document.getElementById('status').className='card error';document.getElementById('status').textContent=e.message}
}
document.getElementById('save').onclick=async()=>{let r=await fetch('/api/teacher-portal/'+encodeURIComponent(token)+'/preferences',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preferences:prefs,comments:prefComments,relax_order:relaxOrder})});document.getElementById('saved').textContent=r.ok?'Zapisano.':'Nie udało się zapisać.';if(r.ok)setTimeout(()=>document.getElementById('saved').textContent='',2500)};
load();
