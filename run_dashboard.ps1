# Q-SAT Mission Control Platform Launcher
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "   Starting Q-SAT Adaptive Ground Station Server" -ForegroundColor Green
Write-Host "   Ground Station: Tiruchirappalli Reference Ground Station [10.79 N, 78.70 E]" -ForegroundColor Yellow
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

Write-Host "[1/2] Opening Mission Control Dashboard in your default browser..." -ForegroundColor Green
Start-Process "http://localhost:8000/dashboard/"

Write-Host "[2/2] Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Green
Write-Host "(Keep this window open while using the dashboard. Press Ctrl+C to stop.)`n" -ForegroundColor DarkGray

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

