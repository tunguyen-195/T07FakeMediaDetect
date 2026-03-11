@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 download_data.py %*
) else (
    python download_data.py %*
)

set EXIT_CODE=%errorlevel%
endlocal & exit /b %EXIT_CODE%
