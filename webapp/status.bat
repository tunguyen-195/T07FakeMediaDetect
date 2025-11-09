@echo off
:: ====================================================================
:: T07FakeMediaDetect - Status Check Script
:: Hệ thống phát hiện tệp đa phương tiện giả mạo T07
:: ====================================================================

COLOR 0B
title T07FakeMediaDetect - System Status

echo.
echo ========================================================
echo  T07FakeMediaDetect - System Status
echo  Hệ thống phát hiện tệp đa phương tiện giả mạo T07
echo ========================================================
echo.

:: Check Python
echo [CHECK 1/5] Python Installation (System):
python --version 2>nul
if %errorlevel% equ 0 (
    echo   Status: OK
) else (
    echo   Status: NOT FOUND
)
echo.

:: Check Virtual Environment
echo [CHECK 2/5] Virtual Environment:
if exist ".venv-tf\Scripts\python.exe" (
    echo   Status: OK
    .venv-tf\Scripts\python.exe --version
) else (
    echo   Status: NOT FOUND
    echo   Run 'install.bat' to create virtual environment
)
echo.

:: Check Model Files
echo [CHECK 3/5] Model Files:
if exist "models\proposed_ela_50_casia_fidac.h5" (
    echo   Image Model: OK
) else (
    echo   Image Model: MISSING
)
if exist "models\segmenter_weights.h5" (
    echo   Segmenter Model: OK
) else (
    echo   Segmenter Model: MISSING
)
if exist "models\forgery_model_me.hdf5" (
    echo   Video Model: OK
) else (
    echo   Video Model: MISSING
)
echo.

:: Check Port 8001
echo [CHECK 4/5] Server Status (Port 8001):
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

:: Check Database
echo [CHECK 5/5] Database:
if exist "db.sqlite3" (
    echo   Status: OK (db.sqlite3)
    for %%A in ("db.sqlite3") do echo   Size: %%~zA bytes
) else (
    echo   Status: NOT FOUND
    echo   Database will be created on first run
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
