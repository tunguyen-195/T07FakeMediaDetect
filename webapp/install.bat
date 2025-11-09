@echo off
:: ====================================================================
:: T07FakeMediaDetect - Installation Script
:: Hệ thống phát hiện tệp đa phương tiện giả mạo T07
:: ====================================================================

COLOR 0B
title T07FakeMediaDetect - Installation

echo.
echo ========================================================
echo  T07FakeMediaDetect - Installation Setup
echo  Hệ thống phát hiện tệp đa phương tiện giả mạo T07
echo ========================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.9 or higher from:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [INFO] Python detected:
python --version
echo.

:: Check if virtual environment exists
if exist ".venv-tf" (
    echo [INFO] Virtual environment already exists.
    echo Do you want to recreate it? (This will delete existing environment)
    choice /C YN /M "Recreate virtual environment"
    if errorlevel 2 goto :skip_venv
    if errorlevel 1 (
        echo [INFO] Removing old virtual environment...
        rmdir /s /q .venv-tf
    )
)

:create_venv
echo [INFO] Creating virtual environment...
python -m venv .venv-tf
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment!
    echo Make sure you have python3-venv installed.
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
echo ========================================================
echo  Installation completed successfully!
echo ========================================================
echo.
echo Next steps:
echo 1. Download model files from:
echo    https://drive.google.com/drive/folders/1B4ODeK_QQ6XMFo6i6EEup1nZC6PllVfu
echo.
echo 2. Place model files in the 'models' folder:
echo    - proposed_ela_50_casia_fidac.h5
echo    - segmenter_weights.h5
echo.
echo 3. Run 'start.bat' to launch the server
echo.
echo ========================================================
echo.

pause
