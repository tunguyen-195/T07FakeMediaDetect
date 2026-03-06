@echo off
:: ====================================================================
:: T07FakeMediaDetect - Installation Script
:: Hệ thống phát hiện tệp đa phương tiện đã bị chỉnh sửa T07
:: Yêu cầu: Python 3.9 (TensorFlow 2.6 không hỗ trợ Python 3.10+)
:: ====================================================================

COLOR 0B
title T07FakeMediaDetect - Installation

echo.
echo ========================================================
echo  T07FakeMediaDetect - Installation Setup
echo  He thong phat hien tep da phuong tien gia mao T07
echo ========================================================
echo.

:: ============================================================
:: Auto-detect Python 3.9 using py launcher or direct path
:: ============================================================
set PYTHON_CMD=

:: Try 1: py -3.9 (Windows Python Launcher)
py -3.9 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3.9
    goto :python_found
)

:: Try 2: python3.9
python3.9 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python3.9
    goto :python_found
)

:: Try 3: Check default python version
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [INFO] Default Python version: %PY_VER%
echo %PY_VER% | findstr /B "3.9" >nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :python_found
)

:: Python 3.9 not found
echo.
echo [ERROR] Python 3.9 is REQUIRED but not found!
echo.
echo This project uses TensorFlow 2.6 which only supports Python 3.6-3.9.
echo Your current Python version is: %PY_VER%
echo.
echo Please install Python 3.9 from:
echo   https://www.python.org/downloads/release/python-3913/
echo.
echo NOTE: You can install Python 3.9 alongside your current Python.
echo       After installing, run this script again.
echo.
pause
exit /b 1

:python_found
echo [INFO] Using Python 3.9:
%PYTHON_CMD% --version
echo.

:: Check if virtual environment exists
if exist ".venv-tf" (
    echo [INFO] Virtual environment already exists.
    echo Do you want to recreate it? (This will delete existing environment^)
    choice /C YN /M "Recreate virtual environment"
    if errorlevel 2 goto :skip_venv
    if errorlevel 1 (
        echo [INFO] Removing old virtual environment...
        rmdir /s /q .venv-tf
    )
)

:create_venv
echo [INFO] Creating virtual environment with Python 3.9...
%PYTHON_CMD% -m venv .venv-tf
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment!
    pause
    exit /b 1
)

:skip_venv
echo [INFO] Activating virtual environment...
call .venv-tf\Scripts\activate.bat

echo.
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [INFO] Installing required packages...
echo This may take several minutes...
echo.

pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install dependencies!
    echo Please check requirements.txt and try again.
    pause
    exit /b 1
)

echo.
echo [INFO] Checking installed packages...
pip list

echo.
echo [INFO] Ensuring Poppler is available for PDF analysis...
if not exist "poppler\Library\bin\pdfinfo.exe" (
    call install_poppler.bat --no-pause
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Poppler setup failed!
        echo PDF analysis will not work until Poppler is installed.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Poppler already present in project folder.
)

echo.
echo [INFO] Validating bundled image/PDF runtime...
.venv-tf\Scripts\python.exe scripts\check_dev_runtime.py --mode install
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Active image/PDF runtime bundle is incomplete.
    echo Expected active release files under models\releases\run_20260306_055001\
    pause
    exit /b 1
)

echo.
echo [INFO] Running database migrations...
.venv-tf\Scripts\python.exe manage.py migrate
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Database migration failed!
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Installation completed successfully!
echo ========================================================
echo.
echo Next steps:
echo 1. Run 'start.bat' to launch the server
echo 2. Optional: copy forgery_model_me.hdf5 into models\ if you want video analysis
echo 3. Optional: copy .env.example to .env if your local setup needs it
echo.
echo ========================================================
echo.

pause
