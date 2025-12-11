@echo off
chcp 65001 > nul
title Trading System with Database

echo ========================================
echo      TRADING SYSTEM WITH DATABASE
echo ========================================

cd /d "%~dp0"

:: Stop old
taskkill /F /IM python.exe 2>nul
timeout /t 1 >nul

:: Check database
echo 📊 Checking database...
if exist "signals.db" (
    echo ✅ Database found: signals.db
) else (
    echo 📝 Creating new database...
)

:: Start services
echo.
echo 🚀 Starting services...
echo.

:: 1. Trading Server (Database enabled)
echo [1] Trading Server...
start "Trading-Server" cmd /k "python server.py"
timeout /t 5 >nul

:: 2. Auto Cleanup Service
echo [2] Auto Cleanup Service...
start "Cleanup-Service" cmd /k "python cleanup_all.py"

:: 3. Web Server
echo [3] Web Server...
start "Web-Server" cmd /k "python -m http.server 8080"

echo.
echo ========================================
echo          SERVICES RUNNING
echo ========================================
echo.
echo ✅ Trading Server: localhost:9999
echo ✅ Database: signals.db
echo ✅ Cleanup: Auto at 00:00 daily
echo ✅ Web: http://localhost:8080
echo.
echo 📊 Signal history saved to database
echo 🗑️  Logs auto-cleaned daily at 00:00
echo.
echo Press any key to continue...
pause >nul