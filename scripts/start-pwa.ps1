$ErrorActionPreference = "Stop"

$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
chcp 65001 | Out-Null

$Root = Split-Path -Parent $PSScriptRoot
$Pwa = Join-Path $Root "pwa"
Set-Location $Pwa

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js / npm neni nainstalovany. Na vyvojarskem PC je potreba Node 18+."
}

if (-not (Test-Path (Join-Path $Pwa "node_modules"))) {
    Write-Host "Instaluji npm zavislosti ..."
    npm install
}

Write-Host "PWA: http://127.0.0.1:5173"
Write-Host "Katalog se nahrava souborem catalog.json, neni v aplikaci."
Write-Host "Ukonceni: Ctrl+C"

Start-Process powershell -ArgumentList "-NoProfile -WindowStyle Hidden -Command `"Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5173'`""

npm run dev
