"""Uji halaman sambutan + tampilan kosong (tanpa proyek), lalu impor 1HSG lokal -> viewer muncul & langkah 1.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_ux_awal.py   (VD_TEMA=gelap, VD_UKURAN=WxH)
"""
import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", os.environ.get("VD_TEMA", "terang"))
st.setValue("wizard_selesai", True)
for k in ("layout", "layout_v2", "sesi_terbuka"):
    st.remove(k)
UKURAN = [int(x) for x in os.environ.get("VD_UKURAN", "1700x1000").split("x")]
OUT = Path("dev/uji/ux").resolve()
OUT.mkdir(parents=True, exist_ok=True)
akhir = f"_{st.value('tema')}"

import virmodock.app as A
from PySide6.QtWidgets import QApplication


def hook():
    from virmodock.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(*UKURAN)
            s.move(10, 10)
            QTimer.singleShot(3000, s.l1)
            QTimer.singleShot(90000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            print("halaman sambutan:", s.stak_view.currentIndex() == 1, "| ruang:", s._ruang_aktif, flush=True)
            s.grab().save(str(OUT / f"awal{akhir}.png"))
            if os.environ.get("VD_ANALISIS", "1") == "1":
                s.atur_ruang("analisis")
            QTimer.singleShot(500, s.l2)

        def l2(s):
            s.grab().save(str(OUT / f"awal_hasil_kosong{akhir}.png"))
            s.atur_ruang("siapkan")
            s.impor([str(Path("dev/uji/1HSG.pdb").resolve())])
            QTimer.singleShot(7000, s.l3)

        def l3(s):
            print("setelah impor: viewer", s.stak_view.currentIndex() == 0, "| langkah:",
                  [(b.status, b.ket) for b in s.langkah.baris][:2], flush=True)
            s.grab().save(str(OUT / f"awal_impor{akhir}.png"))
            js = ("(function(){const g=document.getElementById('gl');const c=g.querySelector('canvas');"
                  "return JSON.stringify({win:[innerWidth,innerHeight],gl:[g.clientWidth,g.clientHeight],"
                  "canvas:c?[c.width,c.height,c.clientWidth,c.clientHeight]:null,dpr:devicePixelRatio});})()")
            s.viewer.page().runJavaScript(js, 0, lambda r: print("ukuran:", r, flush=True))
            s.viewer.js("ukurUlang")
            QTimer.singleShot(1500, lambda: (s.grab().save(str(OUT / f"awal_impor_ulang{akhir}.png")),
                                             QApplication.quit()))

    mainwindow.JendelaUtama = Uji


hook()
A.main()
