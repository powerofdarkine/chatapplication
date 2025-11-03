@echo off
REM filepath: d:\school\HK251\network\lab\Assignment\CO3094-weaprous\start_all.bat
echo ========================================
echo   CO3094 WeApRous - Auto Startup
echo   bksysnet@hcmut
echo ========================================
echo.

REM Kill existing Python processes (optional - để tránh xung đột port)
echo [1/4] Cleaning up existing processes...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 >nul

REM Start Backend (SampleApp) in new window
echo [2/4] Starting Backend (port 9001)...
start "WeApRous Backend" cmd /k "python start_sampleapp.py --server-port 9001"
timeout /t 3 >nul

REM Start Proxy in new window
echo [3/4] Starting Proxy (port 8080)...
start "WeApRous Proxy" cmd /k "python start_proxy.py"
timeout /t 2 >nul

REM Open browser
echo [4/4] Opening browser...
timeout /t 2 >nul
start http://127.0.0.1:8080/login.html

echo.
echo ========================================
echo   All services started successfully!
echo   Backend:  http://127.0.0.1:9001
echo   Proxy:    http://127.0.0.1:8080
echo   Web UI:   http://127.0.0.1:8080/login.html
echo ========================================
echo.
echo Press any key to stop all services...
pause >nul

REM Stop all services
echo Stopping all services...
taskkill /F /IM python.exe >nul 2>&1
echo Done.