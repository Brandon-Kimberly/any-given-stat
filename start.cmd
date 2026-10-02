@echo off
rem Any Given Stat: build what is missing, then serve the site at http://localhost:4173
rem Double-click this file, or run .\start.cmd from PowerShell. Extra args go to "ags up".
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed. Get it from https://docs.astral.sh/uv/ and try again.
  pause
  exit /b 1
)
uv run --project pipeline ags up %*
if errorlevel 1 pause
