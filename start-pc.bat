@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Pamatky - katalog
echo Spoustim PC aplikaci...
echo Prohlizec se otevre na http://127.0.0.1:8765
echo Ukonceni: Ctrl+C v tomto okne.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-pc.ps1"
if errorlevel 1 (
  echo.
  echo Spusteni selhalo. Je nainstalovany Python 3.12+?
  pause
)
