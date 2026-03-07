@echo off
setlocal

COLOR 0C
title T07FakeMediaDetect - Stop

echo.
echo ========================================================
echo  T07FakeMediaDetect - Stop
echo ========================================================
echo.

if exist ".venv-tf\Scripts\python.exe" (
    echo [INFO] Stopping BenfordRich detector...
    .venv-tf\Scripts\python.exe scripts\manage_benford_rich_detector.py stop
    echo.

    echo [INFO] Stopping hidden MUN detector...
    .venv-tf\Scripts\python.exe scripts\manage_hidden_detector.py stop
    echo.
)

echo [INFO] Searching for Django server on port 8001...
set "DJANGO_FOUND=0"
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001 ^| findstr LISTENING') do (
    set "DJANGO_FOUND=1"
    echo   Stopping PID %%a on port 8001
    taskkill /PID %%a /F >nul 2>&1
)

if "%DJANGO_FOUND%"=="0" (
    echo   No Django process is listening on port 8001.
)

echo.
echo [SUCCESS] Stop sequence completed.
echo ========================================================
echo.
