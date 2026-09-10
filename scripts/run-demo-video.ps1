param(
    [ValidateSet("record", "screenshot")]
    [string]$Mode = "record"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$health = "http://127.0.0.1:8010/health"
$front = "http://localhost:3000"
try {
    $null = Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 8
} catch {
    throw "后端不可达 $health ，请先 .\scripts\dev.ps1"
}
try {
    $null = Invoke-WebRequest -Uri $front -UseBasicParsing -TimeoutSec 8
} catch {
    throw "前端不可达 $front ，请先 .\scripts\dev.ps1"
}

$engine = Join-Path $env:USERPROFILE ".cursor\skills\demo-video-factory\scripts\run_demo_video.ps1"
if (-not (Test-Path $engine)) {
    throw "找不到 demo-video-factory 引擎: $engine"
}

powershell -File $engine -Storyboard (Join-Path $Root "demo.storyboard.json") -Mode $Mode
