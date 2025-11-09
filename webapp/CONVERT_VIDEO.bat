@echo off
:: ====================================================================
:: Video Converter - AV1/VP9 to H.264
:: Convert video sang codec H.264 để dùng với OpenCV
:: ====================================================================

COLOR 0E
title T07FakeMediaDetect - Video Converter

echo.
echo ========================================================
echo  Video Converter - AV1/VP9 to H.264
echo  Convert video sang codec tương thích với OpenCV
echo ========================================================
echo.

:: Check if ffmpeg exists
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] FFmpeg not found!
    echo Please install FFmpeg first.
    echo Download: https://ffmpeg.org/download.html
    echo.
    pause
    exit /b 1
)

:: Check if input file provided
if "%~1"=="" (
    echo Usage: CONVERT_VIDEO.bat "input_video.mp4"
    echo.
    echo Example:
    echo   CONVERT_VIDEO.bat "short .mp4"
    echo   CONVERT_VIDEO.bat "video_av1.mp4"
    echo.
    echo Output will be saved as: input_video_h264.mp4
    echo.
    pause
    exit /b 1
)

set INPUT_FILE=%~1
set OUTPUT_FILE=%~n1_h264%~x1

echo [INFO] Input file: %INPUT_FILE%
echo [INFO] Output file: %OUTPUT_FILE%
echo.

:: Check if input exists
if not exist "%INPUT_FILE%" (
    echo [ERROR] Input file not found: %INPUT_FILE%
    pause
    exit /b 1
)

echo [INFO] Starting conversion...
echo.
echo Parameters:
echo   - Video Codec: H.264 (libx264)
echo   - Quality: CRF 23 (good quality)
echo   - Preset: medium (balanced speed/quality)
echo   - Audio: AAC (copy if already AAC)
echo.

:: Run conversion
ffmpeg -i "%INPUT_FILE%" -c:v libx264 -crf 23 -preset medium -c:a aac -y "%OUTPUT_FILE%"

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo [SUCCESS] Conversion completed!
    echo ========================================================
    echo.
    echo Input:  %INPUT_FILE%
    echo Output: %OUTPUT_FILE%
    echo.
    echo You can now upload "%OUTPUT_FILE%" to the system.
    echo.
) else (
    echo.
    echo [ERROR] Conversion failed!
    echo Check the error messages above.
    echo.
)

pause
