param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create the local virtual environment and install requirements first; see README.md.' }
& $pythonPath -X utf8 scripts/check_environment.py
if ($LASTEXITCODE -ne 0) { throw 'Environment checks failed; fix the listed missing items first.' }
& $pythonPath -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $Port
