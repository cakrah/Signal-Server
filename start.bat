@echo off
chcp 65001 > nul
title Trading Signal System with TP - Starting...

echo ========================================
echo      TRADING SIGNAL SYSTEM v2.1 (with TP)
echo ========================================
echo.
echo Initializing system with Take Profit support...
echo.

:: Check Python installation
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python not found!
    echo Please install Python 3.7 or higher
    pause
    exit /b 1
)

echo ✅ Python found

:: Update database structure for TP support
echo Updating database for TP support...
python update_database.py
echo.

:: Create necessary directories
if not exist "logs" mkdir logs
if not exist "templates" mkdir templates

echo ✅ Directories created/checked

echo.
echo ========================================
echo         STARTING COMPONENTS
echo ========================================
echo.

:: 1. Start Server
echo [1/4] Starting Signal Server (with TP)...
start "Trading Server" cmd /k "python server.py"
timeout /t 3 /nobreak > nul

:: 2. Start Web Dashboard
echo [2/4] Starting Web Dashboard (with TP)...
start "Web Dashboard" cmd /k "python web_dashboard.py"
timeout /t 3 /nobreak > nul

:: 3. Start Admin Client
echo [3/4] Starting Admin Client (with TP)...
start "Admin Client" cmd /k "python admin_client.py"
timeout /t 2 /nobreak > nul

:: 4. Start Customer Client
echo [4/4] Starting Customer Client (with TP)...
start "Customer Client" cmd /k "python customer_client.py"

echo.
echo ========================================
echo          SYSTEM INFORMATION
echo ========================================
echo.
echo ✅ All components started successfully!
echo.
echo 📍 URLs to access:
echo    Web Dashboard: http://localhost:5000
echo    Server API:    localhost:9999
echo.
echo 📊 New features:
echo    ✅ Take Profit (TP) support
echo    ✅ Risk/Reward ratio calculation
echo    ✅ TP validation (BUY: TP > Entry, SELL: TP < Entry)
echo    ✅ Enhanced dashboard with TP display
echo.
echo 🛠️  Components running:
echo    1. Trading Server with TP (Port 9999)
echo    2. Web Dashboard with TP (Port 5000)
echo    3. Admin Client with TP
echo    4. Customer Client with TP
echo.
echo ⚠️  Press any key to open Web Dashboard in browser...
pause > nul

:: Open web dashboard in default browser
start http://localhost:5000

echo.
echo 🌐 Opening Web Dashboard in your browser...
echo.
echo 📝 To stop all components, close all CMD windows.
echo.
pause