@echo off
cd /d "%~dp0.."
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m virmolab %*
) else (
    echo [GALAT] Virtual environment .venv tidak ditemukan di: "%~dp0.venv"
    echo Pastikan Python virtual environment telah terpasang.
    pause
)
