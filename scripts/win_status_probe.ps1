$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$logPath = 'E:\ComfyUI\user\wlp4.err'
$outDir  = 'E:\ComfyUI\output\video'
$prefix  = 'wlp_fin'

# ---- ComfyUI queue ----
$running = 0
$pending = 0
$pid_ = ''
try {
    $q = (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8188/queue' -TimeoutSec 6).Content | ConvertFrom-Json
    $running = @($q.queue_running).Count
    $pending = @($q.queue_pending).Count
    if ($running -gt 0) { $pid_ = [string]$q.queue_running[0][1] }
} catch { }

# ---- GPU ----
$gpuUsed = -1
$gpuUtil = -1
try {
    $s = (nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits) -join ''
    $parts = $s.Trim() -split ',\s*'
    $gpuUsed = [int]$parts[0]
    $gpuUtil = [int]$parts[1]
} catch { }

# ---- log parse ----
$doneCount = 0
$totalSeg = 0
$curStep = 0
$curStepsTotal = 0
$phase = ''
$lines = @()
if (Test-Path $logPath) { $lines = Get-Content $logPath -Tail 4000 }

$startIdx = -1
for ($i = $lines.Count - 1; $i -ge 0; $i--) {
    if ($lines[$i] -match '\(segment\):\s*(\d+)\s*segment\(s\)') {
        $startIdx = $i
        $totalSeg = [int]$matches[1]
        break
    }
}
if ($startIdx -ge 0) {
    for ($i = $startIdx; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'segment (\d+)/(\d+) done') { $doneCount = [int]$matches[1] }
    }
    for ($i = $lines.Count - 1; $i -ge $startIdx; $i--) {
        if ($lines[$i] -match 'refine pass') { $phase = 'refine'; break }
        if ($lines[$i] -match '(\d+)/4 \[') {
            $curStep = [int]$matches[1]
            $curStepsTotal = 4
            $phase = 'sampling'
            break
        }
        if ($lines[$i] -match 'spatial tiles') { $phase = 'refine'; break }
    }
}

# ---- outputs ----
$outs = @()
Get-ChildItem $outDir -Filter ($prefix + '*') | Sort-Object LastWriteTime -Descending | Select-Object -First 3 | ForEach-Object {
    $outs += [pscustomobject]@{
        name  = $_.Name
        mb    = [math]::Round($_.Length / 1MB, 2)
        mtime = $_.LastWriteTime.ToString('HH:mm:ss')
    }
}

$result = [pscustomobject]@{
    ts             = (Get-Date).ToString('HH:mm:ss')
    running        = $running
    pending        = $pending
    prompt_id      = $pid_
    total_segments = $totalSeg
    done_segments  = $doneCount
    phase          = $phase
    step           = $curStep
    steps_total    = $curStepsTotal
    gpu_used_mb    = $gpuUsed
    gpu_util       = $gpuUtil
    outputs        = $outs
}
$result | ConvertTo-Json -Depth 4 -Compress
