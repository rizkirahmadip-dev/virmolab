"""Uji kamera setelah buka proyek + gambar 3D besar (render per ubin) vs render utuh.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_ubin.py
Hasil di dev/uji/ubin/: jendela.png (setelah buka proyek), utuh_3000.png, ubin_9000.png.
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

SUMBER = Path(str(sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1])).resolve()
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/ubin").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
shutil.copytree(SUMBER, KERJA / SUMBER.name)
st = QSettings("VirmoDock", "VirmoDock")
for k in ("sesi_terbuka", "proyek_terakhir"):
    st.remove(k)
st.setValue("wizard_selesai", True)

import virmodock.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: None)


def hook():
    from virmodock.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1300, 850)
            s._galat = lambda t: print("GALAT", t, flush=True)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(240000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(5000, s.l2)

        def gambar(s, nama, w):
            s._path = lambda *a: str(KERJA / nama)
            s._ekspor_gambar3d({"fmt": "png", "lebar": w, "tinggi": int(w * 0.75), "dpi": 300, "latar": "putih"})

        def l2(s):
            s.grab().save(str(KERJA / "jendela.png"))
            s.viewer.page().runJavaScript("JSON.stringify(VM.v.getView())", 0, lambda r: print("VIEW", r, flush=True))
            s.gambar("utuh_3000.png", 3000)
            QTimer.singleShot(6000, s.l3)

        def l3(s):
            s.gambar("ubin_9000.png", 9000)
            s.tunggu = 0
            QTimer.singleShot(2000, s.l4)

        def l4(s):
            if not (KERJA / "ubin_9000.png").exists() and s.tunggu < 60:
                s.tunggu += 1
                return QTimer.singleShot(2000, s.l4)
            QTimer.singleShot(1500, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
