param([ValidateSet('setup','backend','frontend','ingest','test','validate')][string]$Task = 'setup')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
switch ($Task) {
  'setup' {
    if (-not (Test-Path .venv)) { python -m venv .venv }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if (-not (Test-Path .env)) { Copy-Item .env.example .env }
    Push-Location frontend
    npm install
    Pop-Location
    Write-Host 'Setup complete. Pull the exact model and ingest with: ollama pull llama3.2:3b; .\.venv\Scripts\python.exe -m backend.app.cli ingest --rebuild'
  }
  'backend' { .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload }
  'frontend' { Push-Location frontend; npm run dev; Pop-Location }
  'ingest' { .\.venv\Scripts\python.exe -m backend.app.cli ingest --rebuild }
  'test' { .\.venv\Scripts\python.exe -m pytest backend/tests -q }
  'validate' { .\.venv\Scripts\python.exe -m backend.app.cli validate }
}
