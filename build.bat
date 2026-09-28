@echo off
setlocal
cd /d "%~dp0"

REM One-click local build. ASCII only: Chinese Windows cmd is GBK.
REM Output: dist\JevChat-DeepSeek\JevChat-DeepSeek.exe

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtualenv .venv ...
    python -m venv .venv || goto :fail
)
call ".venv\Scripts\activate.bat" || goto :fail

echo Installing dependencies ...
python -m pip install -r requirements.txt pyinstaller || goto :fail

echo Building ...
pyinstaller --noconfirm --clean JevChat-DeepSeek.spec || goto :fail

REM MIT requires the license text to ship with every copy. release.yml does the
REM same step, but only for tags - a local build would otherwise miss it.
if exist LICENSE copy /Y LICENSE "dist\JevChat-DeepSeek\" >nul || goto :fail

REM --- Shippable zip ---------------------------------------------------------
REM dist\ is a *working* install, not a release. Once you run it, the app drops
REM config.json (your API keys) and docs\wiki\*.md (real conversations) right
REM next to the exe. Zipping dist\ as-is publishes both. So the zip is staged
REM from a copy with that machine-local data stripped - upload the zip, not dist.
set "STAGE=%TEMP%\JevChat-DeepSeek-stage"
set "ZIP=%cd%\JevChat-DeepSeek.zip"
echo Staging a clean copy ...
if exist "%STAGE%" rmdir /S /Q "%STAGE%" || goto :fail
xcopy /E /I /Q "dist\JevChat-DeepSeek" "%STAGE%\JevChat-DeepSeek" >nul || goto :fail
if exist "%STAGE%\JevChat-DeepSeek\config.json" del /Q "%STAGE%\JevChat-DeepSeek\config.json"
if exist "%STAGE%\JevChat-DeepSeek\docs\wiki" rmdir /S /Q "%STAGE%\JevChat-DeepSeek\docs\wiki"
if exist "%ZIP%" del /Q "%ZIP%"
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\JevChat-DeepSeek' -DestinationPath '%ZIP%' -Force" || goto :fail
rmdir /S /Q "%STAGE%"

echo.
echo Build OK.
echo   Run it:  %cd%\dist\JevChat-DeepSeek\JevChat-DeepSeek.exe
echo   Ship it: %ZIP%
echo.
echo dist\ is your working copy - it holds your API keys and chat pages. Upload
echo the zip, never dist\ itself.
pause
exit /b 0

:fail
echo.
echo Build FAILED. Scroll up for the error.
pause
exit /b 1
