@echo off
setlocal

COLOR 0B
title T07FakeMediaDetect - Status

echo.
echo ========================================================
echo  T07FakeMediaDetect - System Status
echo ========================================================
echo.

echo [CHECK 1/7] Python Installation (System):
python --version 2>nul
if %errorlevel% equ 0 (
    echo   Status: OK
) else (
    echo   Status: NOT FOUND
)
echo.

echo [CHECK 2/7] Virtual Environment (.venv-tf):
if exist ".venv-tf\Scripts\python.exe" (
    echo   Status: OK
    .venv-tf\Scripts\python.exe --version
    echo   Default primary detector: cnn_only
) else (
    echo   Status: NOT FOUND
    echo   Run install.bat to create the virtual environment.
)
echo.

echo [CHECK 3/7] Image/PDF Runtime Bundle:
if exist ".venv-tf\Scripts\python.exe" (
    .venv-tf\Scripts\python.exe scripts\check_dev_runtime.py --mode status
) else (
    echo   Status: UNKNOWN
    echo   Create the virtual environment first with install.bat.
)
echo.

echo [CHECK 4/7] BenfordRich Detector (debug/benchmark):
if exist ".venv-tf\Scripts\python.exe" (
    .venv-tf\Scripts\python.exe scripts\manage_benford_rich_detector.py status
    if %errorlevel% neq 0 (
        echo   Status: FAILED
        echo   BenfordRich is optional; run install.bat or set T07_START_BENFORD_RICH=1 when benchmarking.
    )
) else (
    echo   Status: UNKNOWN
    echo   Create the virtual environment first with install.bat.
)
echo.

echo [CHECK 5/7] Hidden MUN Detector:
if exist ".venv-tf\Scripts\python.exe" (
    .venv-tf\Scripts\python.exe scripts\manage_hidden_detector.py status
    if %errorlevel% neq 0 (
        echo   Status: FAILED
        echo   Run install.bat or start.bat to repair the hidden detector runtime.
    )
) else (
    echo   Status: UNKNOWN
    echo   Create the virtual environment first with install.bat.
)
echo.

echo [CHECK 6/7] Django Server (Port 8001):
netstat -ano | findstr :8001 | findstr LISTENING >nul 2>&1
if %errorlevel% equ 0 (
    echo   Status: RUNNING
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001 ^| findstr LISTENING') do (
        echo   Process ID: %%a
    )
) else (
    echo   Status: STOPPED
)
echo.

echo [CHECK 7/7] Database:
if exist "db.sqlite3" (
    echo   Status: OK - db.sqlite3
    for %%A in ("db.sqlite3") do echo   Size: %%~zA bytes
) else (
    echo   Status: NOT FOUND
    echo   Database will be created on first run.
)
echo.

echo ========================================================
echo  System Check Complete
echo ========================================================
echo.
echo Quick Actions:
echo   - Start server: start.bat
echo   - Stop server:  stop.bat
echo   - Install deps: install.bat
echo.
pause
