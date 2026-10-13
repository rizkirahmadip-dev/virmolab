"""Lokasi berkas: program bawaan, data aplikasi, pengaturan, log, dan folder kerja.

Mode portable: bila ada berkas `portable.flag` di samping VirmoLab.exe (atau di akar
proyek saat pengembangan), pengaturan, log, dan proyek bawaan disimpan di folder
aplikasi - tidak menyentuh registry atau %LOCALAPPDATA%.
"""
import os
import sys
from pathlib import Path

BEKU = getattr(sys, "frozen", False)
# akar paket (saat dibekukan PyInstaller: folder _internal / _MEIPASS)
AKAR = Path(sys._MEIPASS) if BEKU else Path(__file__).resolve().parents[2]
FOLDER_APP = Path(sys.executable).resolve().parent if BEKU else AKAR
# exe GUI (proses pekerja PoseBusters/ADMET selalu lewat VirmoLab.exe, juga bila dipanggil dari VirmoLab-cli.exe)
EXE_UTAMA = FOLDER_APP / "VirmoLab.exe" if BEKU else Path(sys.executable)
PAKET = AKAR / "virmolab" if (AKAR / "virmolab").exists() else Path(__file__).resolve().parents[1]
BIN = AKAR / "bin" if (AKAR / "bin").exists() else AKAR / "vendor" / "bin"
VIEWER = PAKET / "viewer"
DOCS = AKAR / "docs"
KETCHER = AKAR / "ketcher" if (AKAR / "ketcher").exists() else AKAR / "vendor" / "ketcher"

PORTABLE = (FOLDER_APP / "portable.flag").exists()
APPDATA = FOLDER_APP / "data" if PORTABLE else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VirmoLab"
# Nama lama (sebelum rebrand 1.2.0); data & pengaturannya dipindahkan sekali saat pertama jalan
NAMA_LAMA = "VirmoDock"
APPDATA_LAMA = None if PORTABLE else APPDATA.parent / NAMA_LAMA


def _migrasi_appdata():
    """Folder data nama lama di %LOCALAPPDATA% -> %LOCALAPPDATA%\\VirmoLab, sekali saja.

    Folder baru belum ada: folder lama dipindah utuh. Sudah ada (atau pemindahan gagal karena terkunci):
    isi lama disalin tanpa menimpa berkas baru. Folder lama dibiarkan sebagai cadangan."""
    if PORTABLE or not APPDATA_LAMA.is_dir():
        return
    tanda = APPDATA / "migrasi_nama_lama.selesai"
    if tanda.exists():
        return
    if not APPDATA.exists():
        try:
            APPDATA_LAMA.rename(APPDATA)
        except OSError:
            pass
    if APPDATA_LAMA.is_dir():
        import shutil
        for sumber in APPDATA_LAMA.rglob("*"):
            tujuan = APPDATA / sumber.relative_to(APPDATA_LAMA)
            try:
                if sumber.is_dir():
                    tujuan.mkdir(parents=True, exist_ok=True)
                elif not tujuan.exists():
                    tujuan.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sumber, tujuan)
            except OSError:
                pass
    try:
        APPDATA.mkdir(parents=True, exist_ok=True)
        tanda.write_text(str(APPDATA_LAMA), encoding="utf-8")
    except OSError:
        pass


_migrasi_appdata()
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
    st = QSettings("VirmoLab", "VirmoLab")
    _migrasi_pengaturan(st)
    return st


_pengaturan_dicek = False


def _migrasi_pengaturan(st):
    """Salin sekali pengaturan registry nama lama ke VirmoLab bila pengaturan baru masih kosong.

    Jalur yang menunjuk ke folder data lama disesuaikan ke folder data yang baru."""
    global _pengaturan_dicek
    if _pengaturan_dicek:
        return
    _pengaturan_dicek = True
    if st.allKeys():
        return
    from PySide6.QtCore import QSettings
    lama = QSettings(NAMA_LAMA, NAMA_LAMA)
    kunci = lama.allKeys()
    if not kunci:
        return
    awalan_lama = str(APPDATA_LAMA)
    for k in kunci:
        v = lama.value(k)
        if isinstance(v, str) and v.replace("/", "\\").lower().startswith(awalan_lama.lower()):
            v = str(APPDATA) + v[len(awalan_lama):]
        st.setValue(k, v)
    st.setValue("migrasi_dari", NAMA_LAMA)
    st.sync()


def program(nama):
    """Jalur program bawaan (vina.exe, autodock_gpu.exe, ...)."""
    p = BIN / nama
    return str(p) if p.exists() else None


def folder_kerja_bawaan():
    if PORTABLE:
        return FOLDER_APP / "Proyek"
    baru, lama = Path.home() / "Documents" / "VirmoLab", Path.home() / "Documents" / NAMA_LAMA
    # folder proyek pengguna tidak dipindah: tetap pakai Documents\<nama lama> bila sudah ada
    return lama if lama.is_dir() and not baru.exists() else baru
