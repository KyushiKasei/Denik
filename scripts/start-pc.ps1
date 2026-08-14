$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Vytvářím virtuální prostředí .venv ..."
    python -m venv (Join-Path $Root ".venv")
}

Write-Host "Instaluji závislosti ..."
& $venvPython -m pip install -q -e ".[dev]"

Write-Host "Aplikace: http://127.0.0.1:8765"
Write-Host "SQLite: %LOCALAPPDATA%\PamatkyDenik\pamatky.sqlite3 (mimo Dropbox)"
Write-Host "Ukončení: Ctrl+C"

Start-Process powershell -ArgumentList "-NoProfile -WindowStyle Hidden -Command `"Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765'`""

& $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --app-dir (Join-Path $Root "pc-app")
