@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 start.py
) else (
  where python >nul 2>nul
  if not errorlevel 1 (
    python start.py
  ) else (
    echo Python chua duoc cai. Tai tai https://www.python.org/downloads/
    echo Nho chon Add Python to PATH khi cai dat.
    pause
    exit /b 1
  )
)
set "SORTINGLAB_EXIT_CODE=%errorlevel%"
if not "%SORTINGLAB_EXIT_CODE%"=="0" pause
exit /b %SORTINGLAB_EXIT_CODE%
