@echo off
title Q-SAT Mission Control Platform
echo =======================================================================
echo    Starting Q-SAT Adaptive Ground Station Server
echo    Ground Station: Tiruchirappalli Reference Ground Station [10.79 N, 78.70 E]
echo =======================================================================
echo.

cd /d "%~dp0"

echo [1/2] Opening Mission Control Dashboard in your web browser...
start "" "http://localhost:8000/dashboard/"

echo [2/2] Starting FastAPI backend on http://localhost:8000 ...
echo (Keep this window open while using the dashboard)
echo.

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

pause

