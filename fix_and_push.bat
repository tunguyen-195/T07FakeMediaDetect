@echo off
:: ====================================================================
:: Fix and Push T07FakeMediaDetect to GitHub
:: Handles case when remote repository already has commits
:: ====================================================================

COLOR 0A
title Fix and Push to GitHub - T07FakeMediaDetect

echo.
echo ========================================================
echo  Fix and Push T07FakeMediaDetect to GitHub
echo  Repository: tunguyen-195/T07FakeMediaDetect
echo ========================================================
echo.

echo [INFO] Current git status:
git status --short
echo.

echo ========================================================
echo [STEP 1/3] Pull existing commits from GitHub...
echo ========================================================
echo.

git pull origin main --allow-unrelated-histories --no-edit

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Pull failed or had conflicts.
    echo [INFO] Trying alternative method...
    echo.
    
    :: Try rebase strategy
    git pull origin main --rebase --allow-unrelated-histories
    
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Still failed. Trying force push option...
        echo.
        
        :: Ask user if they want to force push
        echo WARNING: This will OVERWRITE everything on GitHub!
        echo.
        set /p CONFIRM="Do you want to FORCE PUSH (overwrite GitHub)? (y/n): "
        
        if /i "%CONFIRM%"=="y" (
            goto FORCE_PUSH
        ) else (
            echo.
            echo [INFO] Aborted. Please resolve manually.
            pause
            exit /b 1
        )
    )
)

echo.
echo [SUCCESS] Pull completed!
echo.

:: Normal push
echo ========================================================
echo [STEP 2/3] Pushing to GitHub...
echo ========================================================
echo.

git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Push failed!
    pause
    exit /b 1
)

goto SUCCESS

:FORCE_PUSH
echo.
echo ========================================================
echo [FORCE PUSH] Overwriting GitHub repository...
echo ========================================================
echo.

git push -u origin main --force

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Force push failed!
    pause
    exit /b 1
)

:SUCCESS
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
echo.
echo [INFO] Final git log:
git log --oneline -3
echo.

pause
