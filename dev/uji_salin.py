"""Uji fitur salin gambar ke clipboard (viewport 3D, diagram 2D, BOILED-Egg, statistik).

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_salin.py [folder_proyek.vmd]
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

SUMBER = Path(sys.argv[1] if len(sys.argv) > 1 else str(sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1])).resolve()
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/salin").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
shutil.copytree(SUMBER, KERJA / SUMBER.name)
st = QSettings("VirmoDock", "VirmoDock")
for k in ("sesi_terbuka", "proyek_terakhir"):
    st.remove(k)
st.setValue("wizard_selesai", True)

import virmodock.app as A
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: None)
hasil = {}


def hook():
    from virmodock.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1300, 850)
            s._galat = lambda t: print("GALAT", t, flush=True)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(120000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def cek(s, nama):
            img = QGuiApplication.clipboard().image()
            hasil[nama] = (img.width(), img.height())
            print(nama, img.width(), img.height(), flush=True)
            QGuiApplication.clipboard().clear()

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(5000, s.l2)

        def l2(s):
            s.tab_tengah.setCurrentWidget(s.w_view)
            s.salin_gambar()
            QTimer.singleShot(3000, lambda: (s.cek("3d"), s.l3()))

        def l3(s):
            pose = [o for o in s.objek.values() if o.jenis == "pose"]
            if pose:
                s.analisis_objek(pose[0])
            print("SESI", s._tulis_sesi(KERJA / "sesi"), flush=True)
            for w, n in ((s.diagram, "2d"), (s.sifat, "sifat"), (s.statistik, "statistik")):
                s.tab_tengah.setCurrentWidget(w)
                QApplication.processEvents()
                s.salin_gambar()
                s.cek(n)
            QTimer.singleShot(500, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
print("HASIL", hasil)
