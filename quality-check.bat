@echo off
rem ══════════════════════════════════════════════════════════════
rem  بررسی کیفیت سیگنال — یک کلیک (ویندوز)
rem  مسیر داده پیش‌فرض: %USERPROFILE%\odin-m15
rem  برای مسیر دیگر:  quality-check.bat "D:\data\odin-m15"
rem ══════════════════════════════════════════════════════════════
setlocal
cd /d "%~dp0"

set "DATA=%~1"
if "%DATA%"=="" set "DATA=%USERPROFILE%\odin-m15"

if exist "%~dp0.venv\Scripts\python.exe" (
  set "PY=%~dp0.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo.
echo  داده: %DATA%
echo.
"%PY%" "%~dp0tools\quality_check.py" --data-dir "%DATA%" --jobs 2
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo  [!] ابزار با کد %RC% تمام شد.
pause
