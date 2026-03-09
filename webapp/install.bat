@echo off
setlocal

COLOR 0B
title T07FakeMediaDetect - Installation

echo.
echo ========================================================
echo  T07FakeMediaDetect - Installation Setup
echo  Dev runtime for image, PDF, BenfordRich, and hidden backend
echo ========================================================
echo.

if not defined T07_HIDDEN_BACKEND (
    set "T07_HIDDEN_BACKEND=off"
)

set "PYTHON_CMD="
set "PY_VER=not-found"

py -3.9 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3.9"
    goto :python_found
)

python3.9 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3.9"
    goto :python_found
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo [INFO] Default Python version: %PY_VER%
echo %PY_VER% | findstr /B "3.9" >nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :python_found
)

echo.
echo [ERROR] Python 3.9 is required but not found.
echo Current detected version: %PY_VER%
echo Install Python 3.9 and run this script again.
pause
exit /b 1

:python_found
echo [INFO] Using Python:
%PYTHON_CMD% --version
echo.

if exist ".venv-tf" (
    echo [INFO] Virtual environment already exists.
    choice /C YN /M "Recreate .venv-tf, .venv-benford, .venv-mun, and .venv-photoholmes311"
    if errorlevel 2 goto :skip_venv
    if errorlevel 1 (
        echo [INFO] Removing old virtual environments...
        if exist ".venv-tf" rmdir /s /q .venv-tf
        if exist ".venv-benford" rmdir /s /q .venv-benford
        if exist ".venv-mun" rmdir /s /q .venv-mun
        if exist ".venv-photoholmes" rmdir /s /q .venv-photoholmes
        if exist ".venv-photoholmes311" rmdir /s /q .venv-photoholmes311
    )
)

:create_venv
echo [INFO] Creating .venv-tf with Python 3.9...
%PYTHON_CMD% -m venv .venv-tf
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create .venv-tf.
    pause
    exit /b 1
)

:skip_venv
if not exist ".venv-tf\Scripts\python.exe" (
    echo [ERROR] .venv-tf is missing after setup.
    pause
    exit /b 1
)

echo [INFO] Upgrading pip in .venv-tf...
.venv-tf\Scripts\python.exe -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [ERROR] Failed to upgrade pip in .venv-tf.
    pause
    exit /b 1
)

echo.
echo [INFO] Installing TensorFlow-side dependencies...
.venv-tf\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requirements.txt.
    pause
    exit /b 1
)

echo.
echo [INFO] Ensuring Poppler is available for PDF analysis...
if not exist "poppler\Library\bin\pdfinfo.exe" (
    call install_poppler.bat --no-pause
    if %errorlevel% neq 0 (
        echo [ERROR] Poppler setup failed.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Poppler already present in project folder.
)

echo.
echo [INFO] Validating active image and PDF runtime bundle...
.venv-tf\Scripts\python.exe scripts\check_dev_runtime.py --mode install
if %errorlevel% neq 0 (
    echo [ERROR] Active image/PDF runtime bundle is incomplete.
    pause
    exit /b 1
)

echo.
echo [INFO] Installing BenfordRich detector runtime...
.venv-tf\Scripts\python.exe scripts\manage_benford_rich_detector.py install
if %errorlevel% neq 0 (
    echo [WARNING] BenfordRich detector installation failed.
    echo BenfordRich is currently experimental and will not block the default app runtime.
    echo Check the committed BenfordRich artifacts and Python package install logs later.
)

echo.
echo [INFO] Installing hidden backend runtime (%T07_HIDDEN_BACKEND%)...
.venv-tf\Scripts\python.exe scripts\manage_hidden_backend.py install --backend %T07_HIDDEN_BACKEND%
if %errorlevel% neq 0 (
    echo [ERROR] Hidden backend installation failed.
    echo Check backend dependencies, local runtime logs, and environment settings.
    pause
    exit /b 1
)

echo.
echo [INFO] Running database migrations...
.venv-tf\Scripts\python.exe manage.py migrate
if %errorlevel% neq 0 (
    echo [ERROR] Database migration failed.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Installation completed successfully
echo ========================================================
echo.
echo Next steps:
echo   1. Run start.bat to launch Django and the selected hidden backend
echo   2. Optional: copy forgery_model_me.hdf5 into models\ for video analysis
echo   3. Run status.bat to verify all runtimes before demo
echo.
pause
