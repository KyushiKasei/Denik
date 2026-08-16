@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Pamatky - PWA
echo Spoustim vyvojovy server PWA...
echo Prohlizec se otevre na http://127.0.0.1:5173
echo Ukonceni: Ctrl+C v tomto okne.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-pwa.ps1"
if errorlevel 1 (
  echo.
  echo Spusteni selhalo. Je nainstalovany Node.js 18+?
  pause
)
