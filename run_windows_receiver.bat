@echo off
setlocal

cd /d "%~dp0"
set VENV_DIR=.venv_windows

py -3.12 --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON=py -3.12
) else (
    py -3 --version >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON=py -3
    ) else (
        where python >nul 2>nul
        if %errorlevel% neq 0 (
            echo Python 3.12 or newer is required. Install it from https://www.python.org/downloads/windows/
            pause
            exit /b 1
        )
        set PYTHON=python
    )
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    %PYTHON% -m venv "%VENV_DIR%"
)

"%VENV_DIR%\Scripts\python.exe" --version >nul 2>nul
if %errorlevel% neq 0 (
    echo Existing Windows venv is broken. Recreating %VENV_DIR%...
    rmdir /s /q "%VENV_DIR%"
    %PYTHON% -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"
python -m pip install -r requirements.txt

echo.
echo Starting CarrotKeyboard Windows...
echo Allow this app through Windows Firewall when prompted.
echo Find this PC IP with: ipconfig
echo.

python win.py
pause
