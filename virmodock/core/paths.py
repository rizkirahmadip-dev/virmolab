"""Lokasi berkas: program bawaan, data aplikasi, pengaturan, log, dan folder kerja.

Mode portable: bila ada berkas `portable.flag` di samping VirmoDock.exe (atau di akar
proyek saat pengembangan), pengaturan, log, dan proyek bawaan disimpan di folder
aplikasi — tidak menyentuh registry atau %LOCALAPPDATA%.
"""
import os
import sys
from pathlib import Path

BEKU = getattr(sys, "frozen", False)
# akar paket (saat dibekukan PyInstaller: folder _internal / _MEIPASS)
AKAR = Path(sys._MEIPASS) if BEKU else Path(__file__).resolve().parents[2]
FOLDER_APP = Path(sys.executable).resolve().parent if BEKU else AKAR
# exe GUI (proses pekerja PoseBusters/ADMET selalu lewat VirmoDock.exe, juga bila dipanggil dari VirmoDock-cli.exe)
EXE_UTAMA = FOLDER_APP / "VirmoDock.exe" if BEKU else Path(sys.executable)
PAKET = AKAR / "virmodock" if (AKAR / "virmodock").exists() else Path(__file__).resolve().parents[1]
BIN = AKAR / "bin" if (AKAR / "bin").exists() else AKAR / "vendor" / "bin"
VIEWER = PAKET / "viewer"
DOCS = AKAR / "docs"
KETCHER = AKAR / "ketcher" if (AKAR / "ketcher").exists() else AKAR / "vendor" / "ketcher"

PORTABLE = (FOLDER_APP / "portable.flag").exists()
APPDATA = FOLDER_APP / "data" if PORTABLE else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VirmoDock"
APPDATA.mkdir(parents=True, exist_ok=True)
CACHE = APPDATA / "cache"
CACHE.mkdir(exist_ok=True)
LOG = APPDATA / "log"
LOG.mkdir(exist_ok=True)


def settings():
    """QSettings aplikasi: registry (terpasang) atau INI di folder aplikasi (portable)."""
    from PySide6.QtCore import QSettings
    if PORTABLE:
        return QSettings(str(APPDATA / "pengaturan.ini"), QSettings.IniFormat)
    return QSettings("VirmoDock", "VirmoDock")


def program(nama):
    """Jalur program bawaan (vina.exe, autodock_gpu.exe, ...)."""
    p = BIN / nama
    return str(p) if p.exists() else None


def folder_kerja_bawaan():
    if PORTABLE:
        return FOLDER_APP / "Proyek"
    return Path.home() / "Documents" / "VirmoDock"
