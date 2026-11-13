$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py*--port 8188*' }
foreach ($p in $procs) {
    Write-Output ("kill " + $p.ProcessId + " cmd=" + $p.CommandLine.Substring(0, [Math]::Min(120, $p.CommandLine.Length)))
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 4
$left = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py*--port 8188*' }
Write-Output ("remaining=" + @($left).Count)

$py  = 'E:\ComfyUI\venv\Scripts\python.exe'
$log = 'E:\ComfyUI\user\wlp4.log'
$err = 'E:\ComfyUI\user\wlp4.err'
$argLine = 'main.py --listen 127.0.0.1 --port 8188 --enable-manager --use-sage-attention --disable-pinned-memory --disable-comfy-compiler'
$inner = '"' + $py + '" ' + $argLine + ' 1> "' + $log + '" 2> "' + $err + '"'
$cmd = 'cmd.exe /c cd /d "E:\ComfyUI" && ' + $inner
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$cmd}
Write-Output ("spawned PID=" + $r.ProcessId)

for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 3
    $code = 'down'
    try { $code = (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8188/system_stats' -TimeoutSec 2).StatusCode } catch { $code = 'down' }
    if ($code -eq 200) { Write-Output ("API_UP at " + (($i + 1) * 3) + "s"); break }
}
$mgr = Select-String -Path $log, $err -Pattern 'All startup tasks have been completed' -ErrorAction SilentlyContinue
if ($mgr) { Write-Output 'MANAGER_DONE' } else { Write-Output 'MANAGER_BUSY' }
