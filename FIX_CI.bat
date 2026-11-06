@echo off
setlocal
cd /d "%~dp0"
if not exist "sortinglab\real_data_plus.py" (
 echo ERROR: Place FIX_CI.bat in the SortingLab_FINAL project root.
 pause
 exit /b 1
)
python -m pip install "autopep8>=2.3,<3" "flake8>=7,<8" "pytest>=8,<10" "pytest-cov>=6,<8"
if errorlevel 1 goto :failed
python -m autopep8 --in-place --recursive --aggressive --max-line-length 100 sortinglab tests
if errorlevel 1 goto :failed
python -c "from pathlib import Path; p=Path('sortinglab/desktop_realdata.py'); s=p.read_text(encoding='utf-8'); s=s.replace('import csv\n','',1); p.write_text(s,encoding='utf-8')"
if errorlevel 1 goto :failed
python -m flake8 sortinglab tests
if errorlevel 1 (
 echo.
 echo Flake8 still reports issues. Do NOT push yet. Copy the errors for review.
 pause
 exit /b 2
)
python -m pytest -q
if errorlevel 1 (
 echo.
 echo Tests failed. Do NOT push yet. Copy the errors for review.
 pause
 exit /b 3
)
echo.
echo SUCCESS: Flake8 and pytest passed. Review changes with git diff.
git status --short
echo.
echo To publish: git add sortinglab tests ^&^& git commit -m "Fix CI formatting" ^&^& git push origin main
pause
exit /b 0
:failed
echo Failed before validation. No changes have been pushed.
pause
exit /b 1
