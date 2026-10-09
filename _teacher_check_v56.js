
const qs=new URLSearchParams(location.search), token=qs.get('t')||'';
const days=[['Pn','Poniedziałek'],['Wt','Wtorek'],['Śr','Środa'],['Czw','Czwartek'],['Pi','Piątek']];
let data=null,prefs={};
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function lessonText(day,p){let a=data.lessons?.[day]?.[String(p)]||[];return a.map(x=>[x.class,x.subject,x.room].filter(Boolean).map(esc).join(' • ')).join('<br>')}
function render(){
 document.getElementById('who').textContent=data.teacher.name;
 let h='<table><thead><tr><th>Lekcja</th>'+days.map(d=>'<th>'+d[0]+'</th>').join('')+'</tr></thead><tbody>';
 for(let p=1;p<=9;p++){h+='<tr><th>'+p+'</th>'+days.map(d=>{let x=lessonText(d[0],p);return '<td class="'+(x?'lesson':'')+'">'+(x||'—')+'</td>'}).join('')+'</tr>'}h+='</tbody></table>';document.getElementById('lessons').innerHTML=h;
 let ds=[...data.duties].sort((a,b)=>a.abbr.localeCompare(b.abbr)||a.slot.localeCompare(b.slot));
 document.getElementById('duties').innerHTML=ds.length?'<table><thead><tr><th>Dzień</th><th>Przerwa</th><th>Miejsce</th></tr></thead><tbody>'+ds.map(x=>'<tr><td>'+esc(x.day||x.abbr)+'</td><td>'+esc(x.slot)+'</td><td class="duty">'+esc(x.scope)+' • '+esc(x.place)+(x.wait?'<div class="wait">oczekiwanie: '+x.wait+' lek.</div>':'')+'</td></tr>').join('')+'</tbody></table>':'<div class="note">Brak dyżurów w aktualnym planie.</div>';
 let slots=[...new Set(data.breaks.map(b=>b.label))];
 let ph='<table><thead><tr><th>Przerwa</th>'+days.map(d=>'<th>'+d[0]+'</th>').join('')+'</tr></thead><tbody>';
 for(const slot of slots){ph+='<tr><th>'+esc(slot)+'</th>'+days.map(d=>{let k=d[0]+'|'+slot,v=prefs[k]||'neutral';return '<td><select data-k="'+esc(k)+'"><option value="neutral" '+(v==='neutral'?'selected':'')+'>neutralna</option><option value="prefer" '+(v==='prefer'?'selected':'')+'>preferowana</option><option value="avoid" '+(v==='avoid'?'selected':'')+'>niepożądana</option><option value="forbid" '+(v==='forbid'?'selected':'')+'>zabroniona</option></select></td>'}).join('')+'</tr>'}ph+='</tbody></table>';document.getElementById('prefs').innerHTML=ph;
 document.querySelectorAll('#prefs select').forEach(s=>s.onchange=()=>{if(s.value==='neutral')delete prefs[s.dataset.k];else prefs[s.dataset.k]=s.value});
}
async function load(){
 if(!token){document.getElementById('status').className='card error';document.getElementById('status').textContent='Brak indywidualnego tokenu w linku.';return}
 try{let r=await fetch('/api/teacher-portal/'+encodeURIComponent(token),{cache:'no-store'});if(!r.ok)throw new Error('Nieprawidłowy lub nieaktywny link.');data=await r.json();prefs={...(data.preferences||{})};document.getElementById('status').hidden=true;document.getElementById('content').hidden=false;render()}catch(e){document.getElementById('status').className='card error';document.getElementById('status').textContent=e.message}
}
document.getElementById('save').onclick=async()=>{let r=await fetch('/api/teacher-portal/'+encodeURIComponent(token)+'/preferences',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preferences:prefs})});document.getElementById('saved').textContent=r.ok?'Zapisano.':'Nie udało się zapisać.';if(r.ok)setTimeout(()=>document.getElementById('saved').textContent='',2500)};
load();
