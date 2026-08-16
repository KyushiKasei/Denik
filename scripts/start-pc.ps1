$ErrorActionPreference = "Stop"

# Windows PowerShell 5.1 jinak čte tento soubor jako Windows-1250 a rozbije češtinu.
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
chcp 65001 | Out-Null
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

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

& $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload --app-dir (Join-Path $Root "pc-app")
