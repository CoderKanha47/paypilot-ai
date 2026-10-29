@echo off
title PayPilot AI - Stopping...
echo.
echo ============================================================
echo   PayPilot AI - Stopping Development Servers
echo ============================================================
echo.

echo Stopping backend (uvicorn) processes...
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq PayPilot Backend*" >nul 2>&1
taskkill /F /FI "IMAGENAME eq uvicorn.exe" >nul 2>&1

echo Stopping frontend (vite/node) processes...
taskkill /F /FI "IMAGENAME eq node.exe" /FI "WINDOWTITLE eq PayPilot Frontend*" >nul 2>&1
taskkill /F /FI "IMAGENAME eq cmd.exe" /FI "WINDOWTITLE eq PayPilot Frontend*" >nul 2>&1

REM Also kill any remaining vite processes on port 5173
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Also kill any remaining uvicorn processes on port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ============================================================
echo   All PayPilot AI servers stopped.
echo ============================================================
echo.
timeout /t 2 >nul