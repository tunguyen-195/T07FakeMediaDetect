@echo off
setlocal

COLOR 0A
title T07FakeMediaDetect - Start

echo.
echo ========================================================
echo  T07FakeMediaDetect - Start
echo  Django + active image/PDF bundle + CNN-only primary + hidden backend
echo ========================================================
echo.

if not defined T07_PRIMARY_IMAGE_DETECTOR (
    set "T07_PRIMARY_IMAGE_DETECTOR=cnn_only"
)
if not defined T07_START_BENFORD_RICH (
    set "T07_START_BENFORD_RICH=0"
)
if not defined T07_HIDDEN_BACKEND (
    set "T07_HIDDEN_BACKEND=off"
)
if not defined T07_HIDDEN_GATE_REQUIRED (
    set "T07_HIDDEN_GATE_REQUIRED=1"
)
if not defined T07_HIDDEN_FAIL_FAST (
    if defined T07_MUN_FAIL_FAST (
        set "T07_HIDDEN_FAIL_FAST=%T07_MUN_FAIL_FAST%"
    ) else (
        set "T07_HIDDEN_FAIL_FAST=0"
    )
)
set "T07_HIDDEN_AVAILABLE=0"

if not exist ".venv-tf\Scripts\python.exe" (
    echo [ERROR] .venv-tf is missing.
    echo Run install.bat first.
    pause
    exit /b 1
)

if not exist "models" (
    echo [INFO] models folder missing, creating it now...
    mkdir models
)

echo [INFO] Python in .venv-tf:
.venv-tf\Scripts\python.exe --version

echo.
echo [INFO] Ensuring Poppler is available...
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
echo [INFO] Validating active image/PDF runtime...
.venv-tf\Scripts\python.exe scripts\check_dev_runtime.py --mode start
if %errorlevel% neq 0 (
    echo [ERROR] Active image/PDF runtime is not ready.
    echo Run install.bat again or repair models\active_release.json.
    pause
    exit /b 1
)

if /I "%T07_START_BENFORD_RICH%"=="1" (
    echo.
    echo [INFO] Starting BenfordRich detector...
    .venv-tf\Scripts\python.exe scripts\manage_benford_rich_detector.py start
    if %errorlevel% neq 0 (
        echo [WARNING] BenfordRich detector failed to start.
        echo BenfordRich is experimental and the default app runtime will continue without it.
    )
) else (
    echo.
    echo [INFO] Skipping BenfordRich detector startup - debug only.
)

echo.
echo [INFO] Hidden backend configured: %T07_HIDDEN_BACKEND%
if /I "%T07_HIDDEN_BACKEND%"=="off" (
    echo [INFO] Hidden backend is disabled. Running CNN-only/fallback mode.
) else (
    echo [INFO] Starting hidden backend runtime...
    .venv-tf\Scripts\python.exe scripts\manage_hidden_backend.py start --backend %T07_HIDDEN_BACKEND%
    if %errorlevel% neq 0 (
        if /I "%T07_HIDDEN_FAIL_FAST%"=="1" (
            echo [ERROR] Hidden backend "%T07_HIDDEN_BACKEND%" failed to start.
            echo Strict mode enabled via T07_HIDDEN_FAIL_FAST=1. Startup is blocked.
            echo Check backend log files: hidden_detector_*.log
            pause
            exit /b 1
        ) else (
            echo [WARNING] Hidden backend "%T07_HIDDEN_BACKEND%" failed to start.
            echo [WARNING] Continuing with fallback runtime: CNN-only.
            echo [WARNING] Set T07_HIDDEN_FAIL_FAST=1 to restore strict fail-fast behavior.
            echo [WARNING] Check backend log files: hidden_detector_*.log
        )
    ) else (
        set "T07_HIDDEN_AVAILABLE=1"
    )
)

if not exist "models\forgery_model_me.hdf5" (
    echo.
    echo [WARNING] Optional video model missing: models\forgery_model_me.hdf5
    echo Video analysis will remain unavailable until you copy the file manually.
)

echo.
echo [INFO] Starting Django development server...
echo.
echo Server URLs:
echo   - http://127.0.0.1:8001/
echo   - http://localhost:8001/
echo Primary detector mode:
echo   - %T07_PRIMARY_IMAGE_DETECTOR%
if /I "%T07_START_BENFORD_RICH%"=="1" (
echo BenfordRich detector health:
echo   - http://127.0.0.1:8012/health
)
echo Hidden backend:
echo   - %T07_HIDDEN_BACKEND%
if /I "%T07_HIDDEN_BACKEND%"=="noiseprint" (
    if /I "%T07_HIDDEN_AVAILABLE%"=="1" (
        echo Hidden detector health:
        echo   - http://127.0.0.1:8013/health
    ) else (
        echo Hidden detector status:
        echo   - unavailable ^(running fallback CNN-only mode^)
    )
) else (
    if /I "%T07_HIDDEN_BACKEND%"=="comprint" (
        if /I "%T07_HIDDEN_AVAILABLE%"=="1" (
            echo Hidden detector health:
            echo   - http://127.0.0.1:8014/health
        ) else (
            echo Hidden detector status:
            echo   - unavailable ^(running fallback CNN-only mode^)
        )
    ) else (
        if /I "%T07_HIDDEN_BACKEND%"=="mun" (
            if /I "%T07_HIDDEN_AVAILABLE%"=="1" (
                echo Hidden detector health:
                echo   - http://127.0.0.1:8011/health
            ) else (
                echo Hidden detector status:
                echo   - unavailable ^(running fallback CNN-only mode^)
            )
        ) else (
            if /I "%T07_HIDDEN_BACKEND%"=="off" (
                echo Hidden detector status:
                echo   - disabled
            ) else (
                echo Hidden detector status:
                echo   - external backend, verify its health endpoint separately
            )
        )
    )
)
echo.
echo Press Ctrl+C to stop the server.
echo ========================================================
echo.

.venv-tf\Scripts\python.exe manage.py runserver 0.0.0.0:8001

echo.
echo [INFO] Django server stopped.
pause
