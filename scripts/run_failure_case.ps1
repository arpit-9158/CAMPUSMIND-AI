$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8000'
$payload = @{ question = 'What class is scheduled on Sunday?' } | ConvertTo-Json -Compress
$noMatch = Invoke-RestMethod -Method Post -Uri "$base/chat" -ContentType 'application/json' -Body $payload -TimeoutSec 240
$blankStatus = 0
$blankBody = ''
try {
  Invoke-RestMethod -Method Post -Uri "$base/chat" -ContentType 'application/json' -Body '{"question":"   "}' -TimeoutSec 30 | Out-Null
} catch {
  $blankStatus = $_.Exception.Response.StatusCode.value__
  $blankBody = $_.ErrorDetails.Message
  if ([string]::IsNullOrWhiteSpace($blankBody)) {
    $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
    $blankBody = $reader.ReadToEnd()
    $reader.Dispose()
  }
}
$record = [pscustomobject]@{ missing_class_response = $noMatch; blank_question_status = $blankStatus; blank_question_body = $blankBody }
$record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath 'docs/live-failure-case.json' -Encoding utf8
Write-Host "Missing class tools: $($noMatch.tools_used -join ', ')"
Write-Host "Missing class answer: $($noMatch.answer -replace "`r?`n", ' ')"
Write-Host "Blank question HTTP status: $blankStatus"
Write-Host "Blank question body: $blankBody"
Write-Host 'Saved actual failure evidence to docs/live-failure-case.json'
