@echo off
title VirmoDock
cd /d "%~dp0"

REM 1. Cek pythonw di virtual environment lokal (.venv)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m virmodock %*
    exit /b 0
)

REM 2. Cek python di virtual environment lokal (.venv)
if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" -m virmodock %*
    exit /b 0
)

REM 3. Jika .venv belum ada, coba deteksi python sistem
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo ===============================================================
    echo               VirmoDock - Peluncur Desktop
    echo ===============================================================
    echo Lingkungan .venv belum ditemukan.
    echo Menjalankan dengan Python sistem...
    python -m virmodock %*
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [INFO] Jika dependensi belum terpasang, buat virtual environment:
        echo        python -m venv .venv
        echo        .venv\Scripts\pip install -r requirements.txt
        pause
    )
    exit /b 0
)

echo [GALAT] Python atau .venv tidak ditemukan di komputer ini.
echo Silakan pasang Python 3.10-3.14 dari python.org.
pause
exit /b 1
