$ErrorActionPreference='Stop'
$port=9258
$old=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if($old){$old.OwningProcess|Sort-Object -Unique|ForEach-Object{Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue};Start-Sleep -Milliseconds 300}
$edge='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$stamp=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$profile="C:\DutySolverDemo\edge-stats-$stamp"
$url="http://127.0.0.1:8091/?stats=$stamp"
$proc=Start-Process -FilePath $edge -ArgumentList @('--headless=new','--disable-application-cache','--disk-cache-size=1',"--remote-debugging-port=$port",'--remote-allow-origins=*',"--user-data-dir=$profile",$url) -PassThru
try {
 $pages=$null
 for($i=0;$i -lt 30;$i++){try{$pages=Invoke-RestMethod "http://127.0.0.1:$port/json";break}catch{Start-Sleep -Milliseconds 200}}
 if(-not $pages){throw 'Edge DevTools did not start'}
 $p=$pages|Where-Object {$_.type -eq 'page' -and $_.url -like 'http://127.0.0.1:8091/*'}|Select-Object -First 1
 if(-not $p){throw 'Planner page not found'}
 $ws=[System.Net.WebSockets.ClientWebSocket]::new();$ct=[Threading.CancellationToken]::None
 $ws.ConnectAsync([Uri]$p.webSocketDebuggerUrl,$ct).GetAwaiter().GetResult()|Out-Null
 function Eval([string]$expr,[int]$id){
   $msg=@{id=$id;method='Runtime.evaluate';params=@{expression=$expr;returnByValue=$true;awaitPromise=$true}}|ConvertTo-Json -Compress -Depth 8
   $bytes=[Text.Encoding]::UTF8.GetBytes($msg)
   $ws.SendAsync([ArraySegment[byte]]::new($bytes),[Net.WebSockets.WebSocketMessageType]::Text,$true,$ct).GetAwaiter().GetResult()|Out-Null
   while($true){$buf=New-Object byte[] 524288;$ms=New-Object IO.MemoryStream
     do{$res=$ws.ReceiveAsync([ArraySegment[byte]]::new($buf),$ct).GetAwaiter().GetResult();$ms.Write($buf,0,$res.Count)}while(-not $res.EndOfMessage)
     $o=([Text.Encoding]::UTF8.GetString($ms.ToArray())|ConvertFrom-Json)
     if($o.id -eq $id){if($o.result.exceptionDetails){throw ($o.result.exceptionDetails|ConvertTo-Json -Compress -Depth 6)};return $o.result.result.value}
   }
 }
 $js=@'
(async()=>{
  for(let i=0;i<80&&!document.querySelector('#app')?.__vue_app__?._container?._vnode?.component?.proxy?.cfg;i++)await new Promise(r=>setTimeout(r,100));
  const app=document.querySelector('#app')?.__vue_app__?._container?._vnode?.component?.proxy;
  if(!app?.cfg)return JSON.stringify({ok:false,fatal:'vue not ready'});
  app.mainTab='stats'; await new Promise(r=>setTimeout(r,100));
  const originalPlan=app.effectivePlan;
  const originalJob=app.repairJob;
  const originalRecalc=app.recalculating;
  const basePlan=originalPlan||{source:{kind:'saved_verified',verified:true,source_id:'test'},result_13:[],result_school:[],coverage13:{},coverageSchool:{}};
  const snap=label=>({label,waiting:!!document.querySelector('[data-stats-waiting]'),content:!!document.querySelector('[data-stats-content]'),source:(document.querySelector('[data-stats-source] b')?.textContent||'').trim()});
  app.repairJob=null;app.recalculating=false;app.effectivePlan={...basePlan,source:{...(basePlan.source||{}),kind:'saved_verified',verified:true,job_status:null,source_id:'test-saved'}};
  await new Promise(r=>setTimeout(r,100)); const saved=snap('saved');
  app.recalculating=true; await new Promise(r=>setTimeout(r,100)); const initial=snap('recalculating');
  app.recalculating=false;app.repairJob={id:'test',status:'running'};app.effectivePlan={...basePlan,source:{...(basePlan.source||{}),kind:'saved_verified',verified:true,job_status:'running',source_id:'test-old'}};
  await new Promise(r=>setTimeout(r,100)); const searching=snap('searching-no-live');
  app.effectivePlan={...basePlan,source:{...(basePlan.source||{}),kind:'live_verified',verified:true,job_status:'running',source_id:'test-live',variant_id:'v1',seq:1,label:'Szkic roboczy #1'}};
  await new Promise(r=>setTimeout(r,100)); const live=snap('live');
  app.effectivePlan=originalPlan;app.repairJob=originalJob;app.recalculating=originalRecalc;
  const ok=!saved.waiting&&saved.content&&initial.waiting&&!initial.content&&searching.waiting&&!searching.content&&!live.waiting&&live.content&&searching.source.includes('oczekiwanie')&&live.source.includes('Szkic roboczy #1');
  return JSON.stringify({ok,saved,initial,searching,live});
})()
'@
 $raw=Eval $js 1
 $result=$raw|ConvertFrom-Json
 $raw
 if(-not $result.ok){exit 2}
} finally {
 if($ws){$ws.Dispose()}
 if($proc -and -not $proc.HasExited){Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue}
}