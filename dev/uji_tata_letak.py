"""Uji tata letak adaptif di beberapa ukuran jendela: proporsi dok, mode ringkas, panel bawah pintar.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_tata_letak.py
Keluaran: dev/uji/tata_letak/<lebar>x<tinggi>.png
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
OUT = Path("dev/uji/tata_letak").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", "terang")
for k in ("layout_v2", "geometri", "sesi_terbuka", "layar_layout"):
    st.remove(k)
st.setValue("folder_kerja", str(OUT))

import virmodock.app as A
from PySide6.QtWidgets import QApplication

UKURAN = [(1366, 768), (1600, 900), (1920, 1080), (2560, 1440)]
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def hook():
    from virmodock.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            QTimer.singleShot(2500, lambda: s.jalan(0))
            QTimer.singleShot(240000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def jalan(s, i):
            if i >= len(UKURAN):
                return s.akhir()
            w, h = UKURAN[i]
            s.showNormal()
            s.resize(w, h)
            s.reset_layout()
            QApplication.processEvents()
            QTimer.singleShot(700, lambda: s.periksa(i))

        def periksa(s, i):
            w, h = UKURAN[i]
            QApplication.processEvents()
            kiri = s.d_hier.width()
            kanan = s.d_kerja.width()
            tengah = s.tab_tengah.width()
            ringkas = s.ringkas()
            s.grab().save(str(OUT / f"{w}x{h}.png"))
            cek(0.10 * w <= kiri <= 0.30 * w, f"{w}×{h}: dok kiri {kiri} px ({kiri / w:.0%} lebar)")
            cek(0.15 * w <= kanan <= 0.36 * w, f"{w}×{h}: dok kanan {kanan} px ({kanan / w:.0%} lebar)")
            cek(tengah >= 0.40 * w, f"{w}×{h}: area tengah {tengah} px ({tengah / w:.0%} lebar)")
            cek(ringkas == (h < 800), f"{w}×{h}: mode ringkas = {ringkas}")
            cek(not any(d.isVisible() for d in (s.d_antre, s.d_log, s.d_pesan)),
                f"{w}×{h}: panel bawah tertutup saat tidak ada pesan")
            QTimer.singleShot(200, lambda: s.jalan(i + 1))

        def akhir(s):
            # panel bawah terbuka sendiri saat ada galat, lalu tertutup lagi setelah dibaca
            s._galat("Uji: pesan contoh")
            QApplication.processEvents()
            cek(s.d_pesan.isVisible(), "panel bawah terbuka sendiri saat ada galat")
            # pengguna menutup panel: galat berikutnya cukup jadi lencana, panel tidak dipaksa terbuka lagi
            s._bawah_oleh_pengguna(False)
            s._galat("Uji: galat kedua")
            QApplication.processEvents()
            cek(not s.d_pesan.isVisible(), "panel tetap tertutup setelah pengguna menutupnya")
            cek("pesan baru" in s.b_antre.text(), f"lencana bilah status: {s.b_antre.text()}")
            s._bawah_ditutup_pengguna = False
            s._pesan_belum_dibaca = 0
            s._bawah_dikunci = False
            s._tutup_bawah_bila_selesai()
            QApplication.processEvents()
            cek(not s.d_pesan.isVisible(), "panel bawah tertutup lagi setelah pesan dibaca")
            # job dibatalkan/gagal: antrean habis, panel juga harus menutup sendiri
            s._bawah_ditutup_pengguna = False
            s._bawah_dikunci = False
            s._tampil_bawah(True)
            s.proyek = type("P", (), {"job": [{"status": "dibatalkan", "ligan": [], "mesin": "vina"}]})()
            s._sinkron_bawah()
            cek(s._t_tutup_bawah.isActive(), "penutupan dijadwalkan setelah job dibatalkan")
            s.proyek = type("P", (), {"job": [{"status": "menunggu", "ligan": [], "mesin": "vina"}]})()
            s._sinkron_bawah()
            cek(not s._t_tutup_bawah.isActive(), "penutupan dibatalkan selama masih ada job menunggu")
            s.proyek = None
            s._tampil_bawah(False)
            # pengguna membuka sendiri: tidak boleh ditutup otomatis
            s._bawah_oleh_pengguna(True)
            s._tutup_bawah_bila_selesai()
            QApplication.processEvents()
            cek(s.d_antre.isVisible(), "panel yang dibuka pengguna tidak ditutup otomatis")
            print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
try:
    A.main()
except SystemExit:
    pass
