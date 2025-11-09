@echo off
:: ====================================================================
:: T07FakeMediaDetect - Stop Script
:: Hệ thống phát hiện tệp đa phương tiện giả mạo T07
:: ====================================================================

COLOR 0C
title T07FakeMediaDetect - Stopping Server

echo.
echo ========================================================
echo  T07FakeMediaDetect - Stopping Server
echo  Hệ thống phát hiện tệp đa phương tiện giả mạo T07
echo ========================================================
echo.

echo [INFO] Searching for Django server processes...
echo.

:: Find and kill all Python processes running manage.py
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| find "PID:"') do (
    echo Found Python process: %%i
    taskkill /PID %%i /F >nul 2>&1
)

:: Also try to kill any process using port 8001
echo.
echo [INFO] Checking port 8001...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001 ^| findstr LISTENING') do (
    echo Found process on port 8001: %%a
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo [SUCCESS] Django server stopped successfully!
echo ========================================================
echo.

timeout /t 3
