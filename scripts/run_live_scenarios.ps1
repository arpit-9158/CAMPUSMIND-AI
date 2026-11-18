$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8000'
$questions = @(
  'What is the attendance requirement and when is my DBMS class on Monday?',
  'When is the next examination, and what are the reappear examination rules?',
  'Who should I contact for a leave application and help me draft an email to them?',
  'Find my AI class on Tuesday and tell me whether any academic event is scheduled that day.',
  'Tell me the minimum attendance requirement, my next DBMS class, and the next examination date.'
)
$records = @()
for ($i = 0; $i -lt $questions.Count; $i++) {
  $question = $questions[$i]
  $payload = @{ question = $question } | ConvertTo-Json -Compress
  $response = Invoke-RestMethod -Method Post -Uri "$base/chat" -ContentType 'application/json' -Body $payload -TimeoutSec 240
  $records += [pscustomobject]@{ scenario = $i + 1; question = $question; response = $response }
  Write-Host "Scenario $($i + 1): $($response.tools_used -join ', ')"
  Write-Host "Answer: $($response.answer -replace "`r?`n", ' ')"
}
$records | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath 'docs/live-scenarios.json' -Encoding utf8
Write-Host 'Saved actual API responses to docs/live-scenarios.json'
