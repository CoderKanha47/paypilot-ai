@echo off
title PayPilot AI - Starting...
echo.
echo ============================================================
echo   PayPilot AI - Starting Development Servers
echo ============================================================
echo.

REM Check if backend venv exists
if not exist "backend\.venv" (
    echo [ERROR] Backend virtual environment not found.
    echo Run this first:
    echo   cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -e .
    pause
    exit /b 1
)

REM Check if frontend node_modules exists
if not exist "frontend\node_modules" (
    echo [ERROR] Frontend dependencies not installed.
    echo Run this first:
    echo   cd frontend && npm install
    pause
    exit /b 1
)

echo [1/2] Starting Backend (FastAPI on port 8000)...
start "PayPilot Backend" cmd /k "cd /d backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"

timeout /t 2 >nul

echo [2/2] Starting Frontend (Vite on port 5173)...
start "PayPilot Frontend" cmd /k "cd /d frontend && npm run dev"

echo.
echo ============================================================
echo   Both servers starting in separate windows...
echo ============================================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/api/docs
echo.
echo Close the server windows to stop.
echo ============================================================
echo.