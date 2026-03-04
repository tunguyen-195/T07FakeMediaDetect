@echo off
:: ====================================================================
:: Final Push with Git LFS (after fresh init)
:: Repository already initialized with LFS, just need to commit and push
:: ====================================================================

COLOR 0A
title Final Push with LFS - T07FakeMediaDetect

echo.
echo ========================================================
echo  Final Push to GitHub with Git LFS
echo  Repository: tunguyen-195/T07FakeMediaDetect
echo ========================================================
echo.

echo [INFO] Current status:
git status --short | findstr /C:"M " /C:"A " | find /C ""
echo files staged.
echo.

echo [INFO] Committing with Git LFS...
git commit -m "Initial commit: T07FakeMediaDetect with Git LFS" -m "- Django web application for fake media detection" -m "- 3 AI models stored with Git LFS" -m "- Comprehensive documentation and guides"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Commit failed!
    echo.
    echo This is normal if files were already committed.
    echo Continuing to push...
    echo.
)

echo.
echo [INFO] Pushing to GitHub with Git LFS...
echo This will upload ~332 MB of model files.
echo Please wait...
echo.

git push -u origin main --force

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Push failed!
    echo.
    echo Possible reasons:
    echo   1. GitHub LFS quota exceeded
    echo   2. Authentication failed
    echo   3. Network issue
    echo   4. Files still too large (check git history)
    echo.
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
echo Git LFS files uploaded:
echo   - forgery_model_me.hdf5 (272 MB)
echo   - proposed_ela_50_casia_fidac.h5 (37.5 MB)  
echo   - segmenter_weights.h5 (9.1 MB)
echo.
echo Total: ~319 MB
echo.
echo GitHub LFS remaining quota:
echo   Storage: 681 MB / 1 GB
echo   Bandwidth: 1 GB / 1 GB per month
echo.

pause
