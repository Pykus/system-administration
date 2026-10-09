$ErrorActionPreference='Stop'
$port=9265
$old=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if($old){$old.OwningProcess|Sort-Object -Unique|ForEach-Object{Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue}}
$edge='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$stamp=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$profile="C:\DutySolverDemo\edge-gui-truth-$stamp"
$url="http://127.0.0.1:8091/?guitruth=$stamp"
$p0=Start-Process $edge -ArgumentList @('--headless=new','--disable-application-cache','--disk-cache-size=1',"--remote-debugging-port=$port",'--remote-allow-origins=*',"--user-data-dir=$profile",$url) -PassThru
try{
 $pages=$null;for($i=0;$i -lt 50;$i++){try{$pages=Invoke-RestMethod "http://127.0.0.1:$port/json";break}catch{Start-Sleep -Milliseconds 200}}
 $pg=$pages|Where-Object {$_.type -eq 'page' -and $_.url -like 'http://127.0.0.1:8091/*'}|Select-Object -First 1
 if(-not $pg){throw 'Planner page not found'}
 $ws=[System.Net.WebSockets.ClientWebSocket]::new();$ct=[Threading.CancellationToken]::None;$ws.ConnectAsync([Uri]$pg.webSocketDebuggerUrl,$ct).GetAwaiter().GetResult()|Out-Null
 function Eval($expr,$id){$m=@{id=$id;method='Runtime.evaluate';params=@{expression=$expr;returnByValue=$true;awaitPromise=$true}}|ConvertTo-Json -Compress -Depth 8;$b=[Text.Encoding]::UTF8.GetBytes($m);$ws.SendAsync([ArraySegment[byte]]::new($b),[Net.WebSockets.WebSocketMessageType]::Text,$true,$ct).GetAwaiter().GetResult()|Out-Null;while($true){$buf=New-Object byte[] 524288;$ms=New-Object IO.MemoryStream;do{$rr=$ws.ReceiveAsync([ArraySegment[byte]]::new($buf),$ct).GetAwaiter().GetResult();$ms.Write($buf,0,$rr.Count)}while(-not $rr.EndOfMessage);$o=([Text.Encoding]::UTF8.GetString($ms.ToArray())|ConvertFrom-Json);if($o.id -eq $id){return $o.result.result.value}}}
 $js=@'
(async()=>{
 let p=null;
 for(let i=0;i<120;i++){
   p=document.querySelector('#app')?.__vue_app__?._container?._vnode?.component?.proxy;
   if(p?.cfg&&p?.effectivePlan?.source?.kind)break;
   await new Promise(r=>setTimeout(r,100));
 }
 if(!p?.cfg)return JSON.stringify({ok:false,fatal:'vue not ready'});
 p.mainTab='teachers';await new Promise(r=>setTimeout(r,150));
 const teachers={
   waiting:!!p.planAwaitingFreshPlan,
   source:p.effectivePlan?.source?.kind||null,
   rows13:p.rows13PlanDisplay?.length??-1,
   school:p.schoolPlanDisplay?.length??-1,
   dutyPicks:[...document.querySelectorAll('.teacher-schedule .duty-pick')].filter(x=>x.offsetParent!==null).length,
   visibleTeacherKpis:[...document.querySelectorAll('.plan-card .kpis')].filter(x=>x.offsetParent!==null).length,
   globalWaiting:!!document.querySelector('[data-global-plan-waiting]')
 };
 p.mainTab='stats';await new Promise(r=>setTimeout(r,100));
 const stats={waiting:!!document.querySelector('[data-stats-waiting]'),content:!!document.querySelector('[data-stats-content]')};
 p.mainTab='plan';await new Promise(r=>setTimeout(r,100));
 const plan={
   rows13:p.rows13PlanDisplay?.length??-1,
   school:p.schoolPlanDisplay?.length??-1,
   dutyButtons:[...document.querySelectorAll('.duty-cell-btn')].filter(x=>x.offsetParent!==null&&/(SZKOŁA|1–3 •)/.test(x.innerText)).length
 };
 const ok=teachers.waiting&&teachers.source==='calculating_waiting'&&teachers.rows13===0&&teachers.school===0&&teachers.dutyPicks===0&&teachers.visibleTeacherKpis===0&&teachers.globalWaiting&&stats.waiting&&!stats.content&&plan.rows13===0&&plan.school===0&&plan.dutyButtons===0;
 return JSON.stringify({ok,teachers,stats,plan});
})()
'@
 $raw=Eval $js 1
 $raw
 $x=$raw|ConvertFrom-Json
 if(-not $x.ok){exit 2}
}finally{if($ws){$ws.Dispose()};if($p0 -and -not $p0.HasExited){Stop-Process -Id $p0.Id -Force -ErrorAction SilentlyContinue}}