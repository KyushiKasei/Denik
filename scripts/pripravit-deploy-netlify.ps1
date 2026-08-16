$ErrorActionPreference = "Stop"

$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
chcp 65001 | Out-Null

$Root = Split-Path -Parent $PSScriptRoot
$Pwa = Join-Path $Root "pwa"
$Dest = Join-Path $Root "deploy-netlify"
$Dist = Join-Path $Pwa "dist"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js / npm neni nainstalovany. Skript bezi jen na vyvojarskem PC."
}

Set-Location $Pwa
Write-Host "Instaluji zavislosti a stavim PWA ..."
npm install
npm run build

if (-not (Test-Path $Dist)) {
    throw "Build nevytvoril slozku pwa/dist."
}

function Invoke-WithRetry {
    param(
        [scriptblock]$Action,
        [string]$Label,
        [int]$Attempts = 8
    )
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            & $Action
            return
        } catch {
            if ($i -eq $Attempts) { throw }
            Write-Host "${Label}: soubor je zamceny (casto Dropbox), pokus $i/$Attempts ..."
            Start-Sleep -Seconds (2 * $i)
        }
    }
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Get-ChildItem -Path $Dest -Force | Where-Object {
    $_.Name -notin @("README.md", ".gitkeep")
} | ForEach-Object {
    $item = $_
    Invoke-WithRetry -Label "Cistim $($item.Name)" -Action {
        Remove-Item -LiteralPath $item.FullName -Recurse -Force
    }
}

Invoke-WithRetry -Label "Kopiruji dist" -Action {
    Copy-Item -Path (Join-Path $Dist "*") -Destination $Dest -Recurse -Force
}

$forbidden = Get-ChildItem -Path $Dest -Recurse -File | Where-Object {
    $_.Name -in @("catalog.json", "diary.json", "catalog.sample.json", "diary.sample.json")
}
if ($forbidden) {
    $names = ($forbidden | ForEach-Object { $_.FullName }) -join ", "
    throw "Na Netlify nesmi jit katalog ani denik. Nalezeno: $names"
}

Write-Host ""
Write-Host "Slozka je pripravena: $Dest"
Write-Host "1. Otevri https://app.netlify.com/drop"
Write-Host "2. Pretahni celou slozku deploy-netlify"
Write-Host "3. Na iPhonu otevri vygenerovanou HTTPS URL v Safari a zvol Sdilat -> Pridat na plochu"
Write-Host "Na Netlify je jen prazdny app shell. catalog.json a diary.json se nahravaji v aplikaci ze souboru."
