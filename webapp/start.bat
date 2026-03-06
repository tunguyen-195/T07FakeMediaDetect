@echo off
:: ====================================================================
:: T07FakeMediaDetect - Start Script
:: Hệ thống phát hiện tệp đa phương tiện đã bị chỉnh sửa T07
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

echo [INFO] Activating virtual environment...

echo [INFO] Checking Python version...
.venv-tf\Scripts\python.exe --version

echo.
echo [INFO] Ensuring Poppler is available for PDF analysis...
if not exist "poppler\Library\bin\pdfinfo.exe" (
    call install_poppler.bat --no-pause
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Poppler setup failed. Cannot start PDF-ready dev environment.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Poppler already present in project folder.
)

echo.
echo [INFO] Validating active image/PDF runtime...
.venv-tf\Scripts\python.exe scripts\check_dev_runtime.py --mode start
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Active image/PDF runtime is not ready.
    echo Run install.bat again or verify models\active_release.json and release files.
    pause
    exit /b 1
)

if not exist "models\forgery_model_me.hdf5" (
    echo.
    echo [WARNING] Optional video model missing: models\forgery_model_me.hdf5
    echo Video analysis will stay unavailable until you copy the file manually.
    echo.
)

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
