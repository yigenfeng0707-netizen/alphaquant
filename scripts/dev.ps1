$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "AlphaQuant 开发启动（后端 8010 + 前端 localhost:3000）"

if (-not (Test-Path "data\offline\prices.csv")) {
  python "$Root\scripts\generate_offline_data.py"
}

$py = Get-Command python | Select-Object -ExpandProperty Source
$backend = Join-Path $Root "backend"
$frontend = Join-Path $Root "frontend"

$backendCmd = @"
Set-Location '$backend'
pip install -r requirements.txt
`$env:PYTHONPATH = '$backend'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
"@

$frontendCmd = @"
Set-Location '$frontend'
if (-not (Test-Path 'node_modules')) { npm install }
npm run dev
"@

Start-Process powershell -ArgumentList @("-NoExit", "-Command", $backendCmd)
Start-Process powershell -ArgumentList @("-NoExit", "-Command", $frontendCmd)

Write-Host "已打开两个窗口。后端 http://127.0.0.1:8010/health  前端 http://localhost:3000"
