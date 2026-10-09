$ErrorActionPreference='Stop'
$port=9274
$old=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if($old){$old.OwningProcess|Sort-Object -Unique|ForEach-Object{Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue}}
$edge='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$stamp=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$profile="C:\DutySolverDemo\edge-backend-truth-$stamp"
$url="http://127.0.0.1:8091/?truth=$stamp"
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
 p.mainTab='diagnostics';
 const snaps=[];
 for(let n=0;n<4;n++){
   await new Promise(r=>setTimeout(r,1100));
   const b=await fetch('/api/diagnostics/repair/search/current?browsercheck='+Date.now(),{cache:'no-store'}).then(r=>r.json());
   const bj=b.job||null, fj=p.repairJob||null;
   const term=document.querySelector('[data-solver-mini-terminal]');
   const worker=document.querySelector('.worker-farm');
   const topStatus=[...document.querySelectorAll('.repair-statusline')].find(x=>x.offsetParent!==null)?.innerText||'';
   snaps.push({
     backend:{id:bj?.id,status:bj?.status,stage:bj?.stage,probe:bj?.current_probe?.id||null,done:bj?.block_done,total:bj?.block_total},
     front:{id:fj?.id,status:fj?.status,stage:fj?.stage,probe:fj?.current_probe?.id||null,done:fj?.block_done,total:fj?.block_total},
     terminalVisible:!!term&&term.offsetParent!==null,
     terminalText:(term?.innerText||'').slice(0,500),
     terminalBeforeWorkers:!!term&&!!worker&&(term.compareDocumentPosition(worker)&Node.DOCUMENT_POSITION_FOLLOWING)!==0,
     topStatus
   });
 }
 const eq=x=>JSON.stringify(x.backend)===JSON.stringify(x.front);
 const ok=snaps.every(s=>eq(s)&&s.terminalVisible&&s.terminalBeforeWorkers&&s.topStatus.includes((s.backend.status==='running'?'LICZY':String(s.backend.status||'').toUpperCase())));
 return JSON.stringify({ok,snaps,charset:document.characterSet});
})()
'@
 $raw=Eval $js 1
 $raw
 $x=$raw|ConvertFrom-Json
 if(-not $x.ok){exit 2}
}finally{if($ws){$ws.Dispose()};if($p0 -and -not $p0.HasExited){Stop-Process -Id $p0.Id -Force -ErrorAction SilentlyContinue}}