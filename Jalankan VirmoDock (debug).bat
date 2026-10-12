@echo off
title VirmoDock (Konsol Debug & Log)
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

if exist ".venv\Scripts\python.exe" (
    echo [VirmoDock] Menjalankan dalam mode konsol debug...
    ".venv\Scripts\python.exe" -m virmodock %*
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [INFO] Aplikasi keluar dengan kode galat %ERRORLEVEL%.
        pause
    )
) else (
    echo [GALAT] Virtual environment .venv tidak ditemukan di "%~dp0.venv"
    pause
)
