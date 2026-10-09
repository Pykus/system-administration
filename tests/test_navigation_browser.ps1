$ErrorActionPreference='Stop'
$port=9238
$edge='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$proc=Start-Process -FilePath $edge -ArgumentList @('--headless=new',"--remote-debugging-port=$port",'--remote-allow-origins=*','--user-data-dir=C:\DutySolverDemo\edge-nav-test','http://127.0.0.1:8091/') -PassThru
try {
 $pages=$null;for($i=0;$i -lt 30;$i++){try{$pages=Invoke-RestMethod "http://127.0.0.1:$port/json";break}catch{Start-Sleep -Milliseconds 200}}
 $p=$pages|Where-Object {$_.type -eq 'page' -and $_.url -like 'http://127.0.0.1:8091/*'}|Select-Object -First 1
 $ws=[System.Net.WebSockets.ClientWebSocket]::new();$ct=[Threading.CancellationToken]::None;$ws.ConnectAsync([Uri]$p.webSocketDebuggerUrl,$ct).GetAwaiter().GetResult()|Out-Null
 function Eval([string]$expr,[int]$id){
  $m=@{id=$id;method='Runtime.evaluate';params=@{expression=$expr;returnByValue=$true;awaitPromise=$true}}|ConvertTo-Json -Compress -Depth 8
  $b=[Text.Encoding]::UTF8.GetBytes($m);$ws.SendAsync([ArraySegment[byte]]::new($b),[Net.WebSockets.WebSocketMessageType]::Text,$true,$ct).GetAwaiter().GetResult()|Out-Null
  while($true){$buf=New-Object byte[] 524288;$ms=New-Object IO.MemoryStream;do{$rr=$ws.ReceiveAsync([ArraySegment[byte]]::new($buf),$ct).GetAwaiter().GetResult();$ms.Write($buf,0,$rr.Count)}while(-not $rr.EndOfMessage);$o=([Text.Encoding]::UTF8.GetString($ms.ToArray())|ConvertFrom-Json);if($o.id -eq $id){if($o.result.exceptionDetails){throw ($o.result.exceptionDetails|ConvertTo-Json -Compress -Depth 5)};return $o.result.result.value}}
 }
 Start-Sleep -Milliseconds 1200
