@echo off
:: ====================================================================
:: T07FakeMediaDetect - Start Script
:: Hệ thống phát hiện tệp đa phương tiện giả mạo T07
:: ====================================================================

COLOR 0A
title T07FakeMediaDetect - Starting Server

echo.
echo ========================================================
echo  T07FakeMediaDetect - Image/Video Forgery Detection
echo  Hệ thống phát hiện tệp đa phương tiện giả mạo T07
echo ========================================================
echo.

:: Check if virtual environment exists
if not exist ".venv-tf\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please ensure .venv-tf folder exists with Python installed.
    echo.
    pause
    exit /b 1
)

:: Check if models folder exists
if not exist "models" (
    echo [WARNING] Models folder not found!
    echo Creating models folder...
    mkdir models
)

:: Check if model files exist
if not exist "models\proposed_ela_50_casia_fidac.h5" (
    echo.
    echo [WARNING] Image model not found: proposed_ela_50_casia_fidac.h5
    echo Please download the model from:
    echo https://drive.google.com/drive/folders/1B4ODeK_QQ6XMFo6i6EEup1nZC6PllVfu
    echo.
)

if not exist "models\segmenter_weights.h5" (
    echo.
    echo [WARNING] Segmenter model not found: segmenter_weights.h5
    echo Please download the model from the same link above.
    echo.
)

echo [INFO] Activating virtual environment...

echo [INFO] Checking Python version...
.venv-tf\Scripts\python.exe --version

echo.
echo [INFO] Starting Django development server...
echo.
echo Server will be available at:
echo   - http://127.0.0.1:8001/
echo   - http://localhost:8001/
echo.
echo Press Ctrl+C to stop the server
echo ========================================================
echo.

:: Start Django server using virtual environment's Python directly
.venv-tf\Scripts\python.exe manage.py runserver 0.0.0.0:8001

:: If server stops, pause to show any error messages
echo.
echo [INFO] Server stopped.
pause
