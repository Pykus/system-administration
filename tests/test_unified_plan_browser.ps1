$ErrorActionPreference='Stop'
$port=9270
$old=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if($old){$old.OwningProcess|Sort-Object -Unique|ForEach-Object{Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue}}
$edge='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$stamp=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$profile="C:\DutySolverDemo\edge-unified-plan-$stamp"
$url="http://127.0.0.1:8091/?unified=$stamp"
$p0=Start-Process $edge -ArgumentList @('--headless=new','--disable-application-cache','--disk-cache-size=1',"--remote-debugging-port=$port",'--remote-allow-origins=*',"--user-data-dir=$profile",$url) -PassThru
try{
 $pages=$null;for($i=0;$i -lt 50;$i++){try{$pages=Invoke-RestMethod "http://127.0.0.1:$port/json";break}catch{Start-Sleep -Milliseconds 200}}
 $pg=$pages|Where-Object {$_.type -eq 'page' -and $_.url -like 'http://127.0.0.1:8091/*'}|Select-Object -First 1
 if(-not $pg){throw 'Planner page not found'}
 $ws=[System.Net.WebSockets.ClientWebSocket]::new();$ct=[Threading.CancellationToken]::None
 $ws.ConnectAsync([Uri]$pg.webSocketDebuggerUrl,$ct).GetAwaiter().GetResult()|Out-Null
 function Eval($expr,$id){
   $m=@{id=$id;method='Runtime.evaluate';params=@{expression=$expr;returnByValue=$true;awaitPromise=$true}}|ConvertTo-Json -Compress -Depth 8
   $b=[Text.Encoding]::UTF8.GetBytes($m);$ws.SendAsync([ArraySegment[byte]]::new($b),[Net.WebSockets.WebSocketMessageType]::Text,$true,$ct).GetAwaiter().GetResult()|Out-Null
   while($true){$buf=New-Object byte[] 1048576;$ms=New-Object IO.MemoryStream;do{$rr=$ws.ReceiveAsync([ArraySegment[byte]]::new($buf),$ct).GetAwaiter().GetResult();$ms.Write($buf,0,$rr.Count)}while(-not $rr.EndOfMessage);$o=([Text.Encoding]::UTF8.GetString($ms.ToArray())|ConvertFrom-Json);if($o.id -eq $id){if($o.result.exceptionDetails){throw ($o.result.exceptionDetails|ConvertTo-Json -Compress -Depth 8)};return $o.result.result.value}}
 }
 $js=@'
(async()=>{
 let p=null;
 for(let i=0;i<120;i++){p=document.querySelector('#app')?.__vue_app__?._container?._vnode?.component?.proxy;if(p?.cfg)break;await new Promise(r=>setTimeout(r,100))}
 if(!p?.cfg)return JSON.stringify({ok:false,fatal:'vue not ready'});
 p.mainTab='plan';p.planMatrixMode='teacher';await new Promise(r=>setTimeout(r,120));
 const combos=[];
 for(const a of [false,true])for(const b of [false,true])for(const c of [false,true]){
   p.planShow13=a;p.planShowSchool=b;p.planShowGym=c;p.planTeacherPage=0;await new Promise(r=>setTimeout(r,60));
   const all=p.sortedTeachers.length;
   const expected=b?all:new Set([
     ...(a?p.calendarTeachers13.map(t=>t.name):[]),
     ...(c?p.sortedTeachers.filter(t=>t.group==='wf').map(t=>t.name):[]),
     ...(c?(p.gymPlanDisplay||[]).map(x=>x.teacher).filter(Boolean):[])
   ]).size;
   const actual=p.planTeachersCombined.length;
   const pages=p.planTeacherPageCount;
   const matrix=[...document.querySelectorAll('[data-plan-teacher-common] table.sheet')].filter(x=>x.offsetParent!==null).length;
   combos.push({combo:[a,b,c],actual,expected,pages,matrix,pass:actual===expected&&pages===Math.max(1,Math.ceil(actual/p.teacherPageSize))&&((a||b||c)?matrix===1:matrix===0)});
 }
 p.planShow13=true;p.planShowSchool=true;p.planShowGym=true;p.planTeacherPage=0;await new Promise(r=>setTimeout(r,80));
 const allSelected={count:p.planTeachersCombined.length,all:p.sortedTeachers.length,label:p.planTeacherPageLabel(),pages:p.planTeacherPageCount,pdfButtons:[...document.querySelectorAll('[data-plan-teacher-common] button')].filter(x=>x.textContent.includes('PDF')).map(x=>x.textContent.trim())};
 p.mainTab='diagnostics';await new Promise(r=>setTimeout(r,100));
 const terminal=!!document.querySelector('[data-solver-mini-terminal]');
 const gym=(p.dutyPlaceRows||[]).filter(x=>x.zone==='gym').map(x=>x.label);
 const ok=combos.every(x=>x.pass)&&allSelected.count===allSelected.all&&allSelected.count===72&&allSelected.label.includes('1–15 z 72')&&allSelected.pdfButtons.length===2&&terminal&&gym.includes('Sala gimnastyczna A')&&gym.includes('Sala gimnastyczna B');
 return JSON.stringify({ok,combos,allSelected,terminal,gym,charset:document.characterSet});
})()
'@
 $raw=Eval $js 1
 $raw
 $x=$raw|ConvertFrom-Json
 if(-not $x.ok){exit 2}
}finally{if($ws){$ws.Dispose()};if($p0 -and -not $p0.HasExited){Stop-Process -Id $p0.Id -Force -ErrorAction SilentlyContinue}}