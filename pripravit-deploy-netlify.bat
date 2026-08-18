@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Pamatky - obal pro Netlify
echo Stavim prazdny obal PWA do slozky deploy-netlify ...
echo Katalog ani denik se tam nedavaji.
echo Po dokonceni slozku pretahnete na https://app.netlify.com/drop
echo (prihlaseni, jinak web za hodinu zmizi).
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pripravit-deploy-netlify.ps1"
if errorlevel 1 (
  echo.
  echo Priprava selhala. Je nainstalovany Node.js 18+?
  pause
  exit /b 1
)
echo.
start "" "%~dp0deploy-netlify"
pause
