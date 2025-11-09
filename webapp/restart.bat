@echo off
:: ====================================================================
:: T07FakeMediaDetect - Restart Script
:: Hệ thống phát hiện tệp đa phương tiện giả mạo T07
:: ====================================================================

COLOR 0E
title T07FakeMediaDetect - Restarting Server

echo.
echo ========================================================
echo  T07FakeMediaDetect - Restarting Server
echo  Hệ thống phát hiện tệp đa phương tiện giả mạo T07
echo ========================================================
echo.

echo [STEP 1/2] Stopping existing server...
call stop.bat

echo.
echo [STEP 2/2] Starting server...
timeout /t 2 >nul
call start.bat
