@echo off
:: ====================================================================
:: Setup Git LFS and Push Large Model Files
:: Handles large AI model files (>100MB) with Git LFS
:: ====================================================================

COLOR 0A
title Setup Git LFS and Push - T07FakeMediaDetect

echo.
echo ========================================================
echo  Setup Git LFS for Large Model Files
echo  Repository: tunguyen-195/T07FakeMediaDetect
echo ========================================================
echo.

:: Check if git-lfs is installed
where git-lfs >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git LFS not installed!
    echo.
    echo Please install Git LFS first:
    echo   Download: https://git-lfs.github.com/
    echo   Or use: winget install GitHub.GitLFS
    echo.
    echo After installation, run this script again.
    pause
    exit /b 1
)

echo [INFO] Git LFS is installed!
git lfs version
echo.

:: Initialize Git LFS
echo ========================================================
echo [STEP 1/5] Initialize Git LFS...
echo ========================================================
echo.

git lfs install

if %errorlevel% neq 0 (
    echo [ERROR] Failed to initialize Git LFS!
    pause
    exit /b 1
)

echo [SUCCESS] Git LFS initialized!
echo.

:: Track large model files
echo ========================================================
echo [STEP 2/5] Track large model files with LFS...
echo ========================================================
echo.

git lfs track "*.hdf5"
git lfs track "*.h5"

if %errorlevel% neq 0 (
    echo [ERROR] Failed to track files!
    pause
    exit /b 1
)

echo [SUCCESS] Model files tracked!
echo.

:: Add .gitattributes
echo ========================================================
echo [STEP 3/5] Add .gitattributes...
echo ========================================================
echo.

git add .gitattributes

if %errorlevel% neq 0 (
    echo [WARNING] .gitattributes not found, but continuing...
)

echo [SUCCESS] .gitattributes added!
echo.

:: Reset the commit to remove large files from history
echo ========================================================
echo [STEP 4/5] Reset and recommit with LFS...
echo ========================================================
echo.

echo [INFO] Resetting previous commit...
git reset --soft HEAD~1

echo [INFO] Adding all files (now with LFS)...
git add .

echo [INFO] Creating new commit with LFS...
git commit -m "Initial commit: T07FakeMediaDetect - AI-powered Image/Video Forgery Detection System" -m "" -m "- Django web application for fake media detection" -m "- 3 AI models: Image ELA-CNN, Video Forgery Detection, Image Segmentation" -m "- Supports both image and video analysis" -m "- Fixed AV1 codec compatibility issues with H.264 conversion" -m "- Comprehensive documentation and setup guides" -m "- Batch scripts for easy installation and management" -m "" -m "Note: Large model files (*.h5, *.hdf5) are stored with Git LFS"

if %errorlevel% neq 0 (
    echo [ERROR] Commit failed!
    pause
    exit /b 1
)

echo [SUCCESS] Commit created with LFS!
echo.

:: Push with LFS
echo ========================================================
echo [STEP 5/5] Push to GitHub with LFS...
echo ========================================================
echo.

git push -u origin main --force

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Push failed!
    echo.
    echo Possible issues:
    echo   1. Git LFS quota exceeded (GitHub free: 1GB storage, 1GB bandwidth/month)
    echo   2. Authentication failed
    echo   3. Network issue
    echo.
    echo Alternative: Remove models from git and provide download link instead
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  SUCCESS! Project pushed to GitHub with Git LFS
echo ========================================================
echo.
echo Repository URL:
echo   https://github.com/tunguyen-195/T07FakeMediaDetect
echo.
echo Model files are stored with Git LFS:
echo   - forgery_model_me.hdf5 (272 MB)
echo   - proposed_ela_50_casia_fidac.h5 (37.5 MB)
echo   - segmenter_weights.h5 (9.1 MB)
echo.
echo Total LFS storage: ~319 MB
echo.
echo Note: GitHub free tier includes:
echo   - 1 GB LFS storage
echo   - 1 GB LFS bandwidth per month
echo.

pause
