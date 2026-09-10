param(
  [string]$DemoUrl = $env:ALPHAQUANT_DEMO_URL
)

if (-not $DemoUrl) {
  $DemoUrl = "https://gsym236998-alphaquant.ms.show"
}

$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
Write-Host "Target: $DemoUrl"

# Step 1: ping the demo URL to keep it warm
try {
  $resp = Invoke-WebRequest -Uri $DemoUrl -UserAgent $ua -TimeoutSec 30 -MaximumRedirection 5 -UseBasicParsing
  Write-Host "Demo HTTP $($resp.StatusCode)"
} catch {
  $code = $null
  if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
  if ($code -eq 403) {
    Write-Host "Demo HTTP 403 - studio may be private; ping logged, not failed"
  } else {
    Write-Host "Demo ping logged: $($_.Exception.Message)"
  }
}

# Step 2: health check - verify /health returns ok:true in response body
$healthUrl = "$DemoUrl/health"
try {
  $hResp = Invoke-WebRequest -Uri $healthUrl -UserAgent $ua -TimeoutSec 15 -UseBasicParsing
  $body = $hResp.Content
  Write-Host "Health HTTP $($hResp.StatusCode)"
  if ($body -match '"ok"\s*:\s*true') {
    Write-Host "Health check PASSED: ok=true confirmed in response body"
    exit 0
  } else {
    Write-Host "Health check WARNING: response does not contain ok:true"
    Write-Host "Response body (first 200 chars): $($body.Substring(0, [Math]::Min(200, $body.Length)))"
    exit 1
  }
} catch {
  Write-Host "Health check FAILED: $($_.Exception.Message)"
  exit 1
}
