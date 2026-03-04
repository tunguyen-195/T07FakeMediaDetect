@echo off
:: ====================================================================
:: Download and setup Poppler for PDF analysis on Windows
:: ====================================================================

echo.
echo ========================================================
echo  Poppler Setup for T07FakeMediaDetect
echo ========================================================
echo.

:: Check if poppler already exists in project
if exist "poppler\Library\bin\pdfinfo.exe" (
    echo [INFO] Poppler is already installed in project folder.
    echo Path: %cd%\poppler\Library\bin
    echo.
    pause
    exit /b 0
)

echo [INFO] Downloading Poppler for Windows...
echo.

:: Use PowerShell to download
powershell -Command "& { $url = 'https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip'; $output = 'poppler_temp.zip'; Write-Host 'Downloading from GitHub...'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri $url -OutFile $output -UseBasicParsing; Write-Host 'Download complete!' }"

if not exist "poppler_temp.zip" (
    echo [ERROR] Download failed!
    echo Please download manually from:
    echo   https://github.com/oschwartz10612/poppler-windows/releases
    echo Extract to: %cd%\poppler\
    pause
    exit /b 1
)

echo [INFO] Extracting Poppler...
powershell -Command "& { Expand-Archive -Path 'poppler_temp.zip' -DestinationPath 'poppler_extract' -Force }"

:: Move the extracted folder to the right place
if exist "poppler_extract\poppler-24.08.0" (
    move "poppler_extract\poppler-24.08.0" "poppler" >nul
) else (
    :: Try to find the extracted folder
    for /d %%i in (poppler_extract\*) do (
        move "%%i" "poppler" >nul
        goto :extracted
    )
)
:extracted

:: Cleanup
if exist "poppler_temp.zip" del "poppler_temp.zip"
if exist "poppler_extract" rmdir /s /q "poppler_extract"

:: Verify
if exist "poppler\Library\bin\pdfinfo.exe" (
    echo.
    echo [SUCCESS] Poppler installed successfully!
    echo Path: %cd%\poppler\Library\bin
) else (
    echo.
    echo [WARNING] Poppler extracted but pdfinfo.exe not found at expected path.
    echo Please check the poppler folder structure.
    dir /s /b poppler\pdfinfo.exe 2>nul
)

echo.
pause
