$ErrorActionPreference='Stop'
$port=9241
$edge='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$proc=Start-Process $edge -ArgumentList @('--headless=new',"--remote-debugging-port=$port",'--remote-allow-origins=*','--user-data-dir=C:\DutySolverDemo\edge-nav-9241','http://127.0.0.1:8091/') -PassThru
try{
$pages=$null
for($i=0;$i -lt 30;$i++){try{$pages=Invoke-RestMethod "http://127.0.0.1:$port/json";break}catch{Start-Sleep -Milliseconds 200}}
$p=$pages|Where-Object {$_.type -eq 'page' -and $_.url -like 'http://127.0.0.1:8091/*'}|Select-Object -First 1
$ws=[System.Net.WebSockets.ClientWebSocket]::new();$ct=[Threading.CancellationToken]::None
$ws.ConnectAsync([Uri]$p.webSocketDebuggerUrl,$ct).GetAwaiter().GetResult()|Out-Null
function Eval([string]$expr,[int]$id){
$m=@{id=$id;method='Runtime.evaluate';params=@{expression=$expr;returnByValue=$true;awaitPromise=$true}}|ConvertTo-Json -Compress -Depth 8
$b=[Text.Encoding]::UTF8.GetBytes($m)
$ws.SendAsync([ArraySegment[byte]]::new($b),[Net.WebSockets.WebSocketMessageType]::Text,$true,$ct).GetAwaiter().GetResult()|Out-Null
while($true){$buf=New-Object byte[] 524288;$ms=New-Object IO.MemoryStream
do{$rr=$ws.ReceiveAsync([ArraySegment[byte]]::new($buf),$ct).GetAwaiter().GetResult();$ms.Write($buf,0,$rr.Count)}while(-not $rr.EndOfMessage)
$o=([Text.Encoding]::UTF8.GetString($ms.ToArray())|ConvertFrom-Json)
if($o.id -eq $id){if($o.result.exceptionDetails){return 'EX:'+($o.result.exceptionDetails|ConvertTo-Json -Compress -Depth 5)};return $o.result.result.value}}
}
Start-Sleep -Milliseconds 1200
$js=@'
(async()=>{
 const out={buttons:[...document.querySelectorAll('.grouped-tabs button.tab')].map(b=>b.textContent.trim()),steps:[]};
 const bs=[...document.querySelectorAll('.grouped-tabs button.tab')];
 window.__uiErrors=[];window.addEventListener('error',e=>window.__uiErrors.push('window:'+e.message+' '+(e.error?.stack||'')));window.addEventListener('unhandledrejection',e=>window.__uiErrors.push('promise:'+String(e.reason)+' '+(e.reason?.stack||'')));const orig=console.error;console.error=(...a)=>{window.__uiErrors.push('console:'+a.map(x=>x instanceof Error?(x.stack||x.message):String(x)).join(' | '));orig(...a)};
 for(let i=0;i<bs.length;i++){
   window.__uiErrors.length=0;
   const b=bs[i];b.click();await new Promise(r=>setTimeout(r,180));
   const txt=document.querySelector('main')?.innerText||'';
   const visibleCards=[...document.querySelectorAll('main .card')].filter(x=>x.offsetParent!==null).length;
   const badEncoding=/[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]\?[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]/.test(txt)||/[�ÃÅÂ]/.test(txt)||txt.includes('â€“')||txt.includes('â€”');
   const step={i,label:b.textContent.trim(),active:b.classList.contains('active'),mainLen:txt.length,visibleCards,errs:window.__uiErrors.slice(-5),charset:document.characterSet,badEncoding};
   if(i===7){step.locationCards=document.querySelectorAll('table.place-pref-matrix').length;step.hasPlaces=txt.includes('14 miejsc')}
   step.pass=step.active&&visibleCards>0&&step.errs.length===0&&step.charset==='UTF-8'&&!step.badEncoding&&(i!==7||(step.locationCards===1&&step.hasPlaces));
   out.steps.push(step);
 }
 out.ok=out.steps.every(x=>x.pass);
 return JSON.stringify(out);
})()
'@
$raw=Eval $js 1
$raw
$result=$raw|ConvertFrom-Json
if(-not $result.ok){exit 2}
}finally{if($ws){$ws.Dispose()};if($proc -and -not $proc.HasExited){Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue}}