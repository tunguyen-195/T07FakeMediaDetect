@echo off
:: ====================================================================
:: Push T07FakeMediaDetect to GitHub
:: Repository: https://github.com/tunguyen-195/T07FakeMediaDetect.git
:: ====================================================================

COLOR 0A
title Push to GitHub - T07FakeMediaDetect

echo.
echo ========================================================
echo  Push T07FakeMediaDetect to GitHub
echo  Repository: tunguyen-195/T07FakeMediaDetect
echo ========================================================
echo.

:: Check if git is installed
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git not found! Please install Git first.
    echo Download: https://git-scm.com/download/win
    pause
    exit /b 1
)

:: Check if we're in the right directory
if not exist ".git" (
    echo [ERROR] Not a git repository!
    echo Please run this script from the project root directory.
    pause
    exit /b 1
)

echo [INFO] Checking git status...
git status
echo.

:: Commit
echo ========================================================
echo [STEP 1/3] Creating commit...
echo ========================================================
echo.

git commit -m "Initial commit: T07FakeMediaDetect - AI-powered Image/Video Forgery Detection System" -m "" -m "- Django web application for fake media detection" -m "- 3 AI models: Image ELA-CNN, Video Forgery Detection, Image Segmentation" -m "- Supports both image and video analysis" -m "- Fixed AV1 codec compatibility issues with H.264 conversion" -m "- Comprehensive documentation and setup guides" -m "- Batch scripts for easy installation and management"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Commit failed!
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Commit created!
echo.

:: Set main branch
echo ========================================================
echo [STEP 2/3] Setting main branch...
echo ========================================================
echo.

git branch -M main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to set main branch!
    pause
    exit /b 1
)

echo [SUCCESS] Main branch set!
echo.

:: Add remote (if not exists)
echo ========================================================
echo [STEP 3/3] Adding remote and pushing...
echo ========================================================
echo.

git remote add origin https://github.com/tunguyen-195/T07FakeMediaDetect.git 2>nul

:: Push
echo [INFO] Pushing to GitHub...
echo.

git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Push failed!
    echo.
    echo Possible reasons:
    echo   1. Remote already exists (try: git remote remove origin)
    echo   2. Authentication failed (check GitHub credentials)
    echo   3. Network connection issue
    echo   4. Repository already has commits (try: git pull origin main --allow-unrelated-histories)
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  SUCCESS! Project pushed to GitHub
echo ========================================================
echo.
echo Repository URL:
echo   https://github.com/tunguyen-195/T07FakeMediaDetect
echo.
echo View your repository at:
echo   https://github.com/tunguyen-195/T07FakeMediaDetect
echo.
echo Clone command for others:
echo   git clone https://github.com/tunguyen-195/T07FakeMediaDetect.git
echo.
pause
