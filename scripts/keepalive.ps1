param(
  [string]$DemoUrl = $env:ALPHAQUANT_DEMO_URL
)

if (-not $DemoUrl) {
  $DemoUrl = "https://gsym236998-alphaquant.ms.show"
}

$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
Write-Host "Target: $DemoUrl"

try {
  $resp = Invoke-WebRequest -Uri $DemoUrl -UserAgent $ua -TimeoutSec 30 -MaximumRedirection 5 -UseBasicParsing
  Write-Host "HTTP $($resp.StatusCode)"
} catch {
  $code = $null
  if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
  if ($code -eq 403) {
    Write-Host "HTTP 403 — studio may be private; ping logged, not failed"
    exit 0
  }
  Write-Host "Ping logged: $($_.Exception.Message)"
  exit 0
}
