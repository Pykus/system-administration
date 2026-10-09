$ErrorActionPreference='Stop'
$port=9255
$old=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if($old){$old.OwningProcess|Sort-Object -Unique|ForEach-Object{Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue};Start-Sleep -Milliseconds 300}
$edge='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$stamp=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$profile="C:\DutySolverDemo\edge-plan-filter-$stamp"
$url="http://127.0.0.1:8091/?test=$stamp"
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
  Start-Sleep -Milliseconds 1000
  $js=@'
(async()=>{
 window.__uiErrors=[]; window.addEventListener('error',e=>window.__uiErrors.push(e.message));
 for(let i=0;i<80&&!document.querySelector('[data-plan-view="place"]');i++)await new Promise(r=>setTimeout(r,100));
 const filter=[...document.querySelectorAll('[data-plan-filter] input[type=checkbox]')];
 const teacherBtn=document.querySelector('[data-plan-view="teacher"]');
 const placeBtn=document.querySelector('[data-plan-view="place"]');
 if(filter.length!==3||!teacherBtn||!placeBtn)return JSON.stringify({ok:false,fatal:'missing controls',filters:filter.length,teacher:!!teacherBtn,place:!!placeBtn});
 const set=(i,v)=>{if(filter[i].checked!==v)filter[i].click()};
 const vis=s=>{const e=document.querySelector('[data-plan-scope="'+s+'"]');return !!(e&&e.offsetParent!==null)};
 const out=[];let ok=true;
 for(const mode of ['teacher','place']){
   (mode==='teacher'?teacherBtn:placeBtn).click(); await new Promise(r=>setTimeout(r,80));
   for(const a of [false,true])for(const b of [false,true])for(const c of [false,true]){
     set(0,a);set(1,b);set(2,c);await new Promise(r=>setTimeout(r,70));
     let pass=true,detail={};
     if(mode==='teacher'){
       const actual={s13:vis('13'),school:vis('school'),gym:vis('gym')};
       const visibleSheets=[...document.querySelectorAll('table.sheet')].filter(x=>x.offsetParent!==null).length;
       const gymTables=[...document.querySelectorAll('[data-plan-scope="gym"] table.constraints-table')].filter(x=>x.offsetParent!==null).length;
       pass=actual.s13===a&&actual.school===b&&actual.gym===c&&visibleSheets===((a?1:0)+(b?1:0))&&gymTables===(c?1:0);
       detail={actual,visibleSheets,gymTables};
     }else{
       const matrix=document.querySelector('[data-plan-place-matrix]');
       const visible=!!(matrix&&matrix.offsetParent!==null);
       const headers=[...document.querySelectorAll('[data-plan-place-matrix] th[data-place-key]')].map(x=>x.getAttribute('data-place-key'));
       const expected=[...document.querySelectorAll('[data-plan-place-matrix] th[data-place-key]')].filter(()=>false);
       const has13=headers.some(x=>x.startsWith('1-3|'));
       const hasGym=headers.some(x=>x.toLowerCase().includes('sala gimnastyczna'));
       const hasSchool=headers.some(x=>x.startsWith('school|')&&!x.toLowerCase().includes('sala gimnastyczna'));
       pass=visible&&(has13===a)&&(hasSchool===b)&&(hasGym===c);
       detail={visible,headers:headers.length,has13,hasSchool,hasGym};
     }
     if(!pass)ok=false;
     out.push({mode,combo:[a,b,c],pass,...detail});
   }
 }
 if(window.__uiErrors.length)ok=false;
 return JSON.stringify({ok,errors:window.__uiErrors,out});
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