@echo off
chcp 65001 >nul 2>&1
setlocal
title SPS Browser - Build
cd /d "%~dp0"
set "B=%~dp0"
if "%B:~-1%"=="\" set "B=%B:~0,-1%"

echo.
echo  ====================================================
echo   SPS BROWSER - Build  (Sandbox exe + Browser exe)
echo  ====================================================
echo.

echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11 or 3.12 ^(64-bit^) and tick "Add to PATH".
    pause & exit /b 1
)
python --version
echo.

echo [2/5] Installing build tools...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements-build.txt --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed. Check your internet connection.
    pause & exit /b 1
)
echo.
python -c "import llama_cpp,sys; print('[OK] llama-cpp-python', llama_cpp.__version__, '- local AI will be bundled')" 2>nul
if errorlevel 1 (
    echo Installing the local AI engine ^(llama-cpp-python 0.3.21, ready-made CPU build^)...
    python tools\install_ai.py
)
python -m pip install -r requirements-optional.txt --quiet 2>nul
echo.
if not exist "%B%\installer\redist" mkdir "%B%\installer\redist"
if not exist "%B%\installer\redist\vc_redist.x64.exe" (
    echo Downloading Microsoft Visual C++ runtime for the installer...
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%B%\installer\redist\vc_redist.x64.exe' -UseBasicParsing } catch { exit 1 }"
    if errorlevel 1 echo [WARNING] Could not download vc_redist.x64.exe - download it manually into installer\redist\
)
if exist "%B%\installer\redist\vc_redist.x64.exe" for %%A in ("%B%\installer\redist\vc_redist.x64.exe") do if %%~zA LSS 10000000 (
    echo [WARNING] vc_redist.x64.exe looks incomplete - deleting it so it is downloaded again next time.
    del "%B%\installer\redist\vc_redist.x64.exe"
)
echo.

echo [3/5] Cleaning old build...
if exist "%B%\dist"       rmdir /s /q "%B%\dist"
if exist "%B%\build"      rmdir /s /q "%B%\build"
if exist "%B%\_generated" rmdir /s /q "%B%\_generated"
echo.

echo [4/5] Building (2-5 minutes, please wait)...
python -m PyInstaller SPS_Browser.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed - read the red text above.
    pause & exit /b 1
)
set "D=%B%\dist\SPS_Browser"
if not exist "%D%\SPS_Browser.exe"      ( echo [ERROR] SPS_Browser.exe missing      & pause & exit /b 1 )
if not exist "%D%\SPS_Browser_Core.exe" ( echo [ERROR] SPS_Browser_Core.exe missing & pause & exit /b 1 )

:: guide + AI models folder must sit next to the exe
copy /y "%B%\extras\SPS_BROWSER_GUIDE.md" "%D%\" >nul
if not exist "%D%\local_ai\models" mkdir "%D%\local_ai\models"
copy /y "%B%\extras\local_ai\models\README_AI_MODELS.txt" "%D%\local_ai\models\" >nul

:: prove that llama.cpp was packed
if exist "%D%\_internal\llama_cpp" (
    echo [OK] llama_cpp packed:
    dir /b "%D%\_internal\llama_cpp\lib\*.dll" 2>nul
) else (
    echo [WARNING] llama_cpp is NOT inside the build - local AI will not work in the exe.
)

:: licence files next to the exe (GPL-3.0)
for %%L in (LICENSE.txt SPS_BROWSER_NOTICE.txt THIRD_PARTY_NOTICES.txt) do (
    if exist "%B%\extras\%%L" (copy /y "%B%\extras\%%L" "%D%\" >nul) else (echo [ERROR] extras\%%L is missing & pause & exit /b 1)
)

:: logo next to the exes (window + tray icon)
if not exist "%D%\assets" mkdir "%D%\assets"
copy /y "%B%\assets\sps_browser.ico" "%D%\assets\" >nul
copy /y "%B%\assets\sps_browser.png" "%D%\assets\" >nul

:: support form link (edit this file next to the exe any time - no rebuild needed)
copy /y "%B%\extras\support_form.txt" "%D%\" >nul

:: OPTIONAL real code signing (see TRUSTED_PUBLISHER.md). Only runs when you set SPS_SIGN_PFX + SPS_SIGN_PASS, or when
:: signtool is configured by SignPath / your own certificate. Without it the build simply stays unsigned.
if defined SPS_SIGN_PFX (
    where signtool >nul 2>nul
    if errorlevel 1 (
        echo [WARNING] SPS_SIGN_PFX is set but signtool.exe was not found - build stays UNSIGNED.
    ) else (
        echo Signing exes with your certificate...
        signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f "%SPS_SIGN_PFX%" /p "%SPS_SIGN_PASS%" "%D%\SPS_Browser.exe" "%D%\SPS_Browser_Core.exe"
    )
)

:: remove the unfinished build\ folder - its exe can NOT run (that was the "failed to load python dll" error)
if exist "%B%\build"      rmdir /s /q "%B%\build"
if exist "%B%\_generated" rmdir /s /q "%B%\_generated"
echo.

echo [5/5] Self-test (checks that every library was packed)...
if exist "%D%\selftest_result.txt" del "%D%\selftest_result.txt"
start /wait "" "%D%\SPS_Browser_Core.exe" --selftest
echo ----------------------------------------------------
if exist "%D%\selftest_result.txt" (
    type "%D%\selftest_result.txt"
) else (
    echo [FAIL] Self-test did not run. Look for SPS_Browser_error.txt in %TEMP%
)
echo.
echo ----------------------------------------------------
echo.
echo  RUN THIS:  %D%\SPS_Browser.exe
echo  (never run anything inside the "build" folder)
echo.

set "INNO="
for %%P in ("C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "C:\Program Files\Inno Setup 6\ISCC.exe") do if exist %%P set "INNO=%%~P"
if "%INNO%"=="" (
    echo  Installer: install Inno Setup 6 ^(free^), open installer\SPS_Browser_Setup.iss and press F9.
) else (
    echo  Building installer...
    "%INNO%" "%B%\installer\SPS_Browser_Setup.iss"
)
echo.
pause
