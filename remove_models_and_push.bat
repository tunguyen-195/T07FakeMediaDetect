@echo off
:: ====================================================================
:: Remove Large Models and Push to GitHub
:: Alternative: Ignore model files and provide download link
:: ====================================================================

COLOR 0E
title Remove Models and Push - T07FakeMediaDetect

echo.
echo ========================================================
echo  Remove Large Models from Git and Push
echo  Repository: tunguyen-195/T07FakeMediaDetect
echo ========================================================
echo.

echo [WARNING] This will remove model files from git tracking.
echo Models will still exist locally in webapp/models/ folder.
echo.
echo You will need to provide a download link for models separately.
echo.
set /p CONFIRM="Continue? (y/n): "

if /i not "%CONFIRM%"=="y" (
    echo Aborted.
    pause
    exit /b 0
)

echo.
echo ========================================================
echo [STEP 1/5] Update .gitignore to exclude models...
echo ========================================================
echo.

:: Add models to .gitignore
echo # Model files (too large for GitHub - provide download link instead) >> .gitignore
echo webapp/models/*.h5 >> .gitignore
echo webapp/models/*.hdf5 >> .gitignore

echo [SUCCESS] .gitignore updated!
echo.

:: Remove models from git cache
echo ========================================================
echo [STEP 2/5] Remove models from git cache...
echo ========================================================
echo.

git rm --cached webapp/models/*.h5
git rm --cached webapp/models/*.hdf5

echo [SUCCESS] Models removed from git tracking!
echo.

:: Reset commit
echo ========================================================
echo [STEP 3/5] Reset and recommit without models...
echo ========================================================
echo.

git reset --soft HEAD~1

git add .

git commit -m "Initial commit: T07FakeMediaDetect - AI-powered Image/Video Forgery Detection System" -m "" -m "- Django web application for fake media detection" -m "- 3 AI models: Image ELA-CNN, Video Forgery Detection, Image Segmentation" -m "- Supports both image and video analysis" -m "- Fixed AV1 codec compatibility issues with H.264 conversion" -m "- Comprehensive documentation and setup guides" -m "- Batch scripts for easy installation and management" -m "" -m "Note: Model files are excluded from repository due to size." -m "Please download models separately (see README.md for download link)"

if %errorlevel% neq 0 (
    echo [ERROR] Commit failed!
    pause
    exit /b 1
)

echo [SUCCESS] Commit created without models!
echo.

:: Create models README
echo ========================================================
echo [STEP 4/5] Create models download instructions...
echo ========================================================
echo.

(
echo # AI Models Download
echo.
echo ## Model Files Required
echo.
echo This project requires 3 AI model files that are too large to store on GitHub:
echo.
echo 1. **forgery_model_me.hdf5** ^(272 MB^)
echo    - Video Forgery Detection Model
echo.
echo 2. **proposed_ela_50_casia_fidac.h5** ^(37.5 MB^)
echo    - Image ELA-CNN Forgery Detection Model
echo.
echo 3. **segmenter_weights.h5** ^(9.1 MB^)
echo    - Image Segmentation Model
echo.
echo ## Download Instructions
echo.
echo ### Option 1: Google Drive
echo.
echo Download all models from Google Drive:
echo - Link: [Provide your Google Drive link here]
echo.
echo ### Option 2: Direct Download
echo.
echo Download individually:
echo - forgery_model_me.hdf5: [Link]
echo - proposed_ela_50_casia_fidac.h5: [Link]
echo - segmenter_weights.h5: [Link]
echo.
echo ## Installation
echo.
echo 1. Download the model files
echo 2. Place them in `webapp/models/` directory:
echo    ```
echo    T07FakeMediaDetect/
echo    └── webapp/
echo        └── models/
echo            ├── forgery_model_me.hdf5
echo            ├── proposed_ela_50_casia_fidac.h5
echo            └── segmenter_weights.h5
echo    ```
echo.
echo 3. Run `webapp/status.bat` to verify all models are present
echo.
echo ## Verification
echo.
echo Check if models are correctly installed:
echo ```bash
echo cd webapp
echo status.bat
echo ```
echo.
echo You should see:
echo ```
echo [✓] proposed_ela_50_casia_fidac.h5 - OK
echo [✓] segmenter_weights.h5 - OK
echo [✓] forgery_model_me.hdf5 - OK
echo ```
) > webapp\models\README.md

echo [SUCCESS] Models README created!
echo.

:: Push
echo ========================================================
echo [STEP 5/5] Push to GitHub...
echo ========================================================
echo.

git push -u origin main --force

if %errorlevel% neq 0 (
    echo [ERROR] Push failed!
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
echo [IMPORTANT] Next steps:
echo   1. Upload model files to Google Drive or file hosting
echo   2. Update webapp/models/README.md with download links
echo   3. Commit and push the updated README
echo.
echo Model files location on your PC:
echo   E:\Freelance\Research\D11_9_2025_Image_fixed_Detect\Project\T07FakeMediaDetect\webapp\models\
echo.

pause
