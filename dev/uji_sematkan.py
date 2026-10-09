"""Uji sematkan pose: pose tersemat tetap tampil saat pose/ligan lain dibuka.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_sematkan.py
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

SUMBER = Path(str(sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1])).resolve()
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/sematkan").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
shutil.copytree(SUMBER, KERJA / SUMBER.name)
st = QSettings("VirmoDock", "VirmoDock")
for k in ("sesi_terbuka", "proyek_terakhir"):
    st.remove(k)
st.setValue("wizard_selesai", True)

import virmodock.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: None)
hasil = []


def hook():
    from virmodock.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1300, 850)
            s._galat = lambda t: print("GALAT", t, flush=True)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(120000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            pasang = [(j["id"], l["id"]) for j in s.proyek.job for l in j["ligan"] if l["status"] == "selesai"]
            print("hasil", len(pasang), flush=True)
            (j1, l1), (j2, l2) = pasang[0], pasang[1]
            a = s.buka_pose(j1, l1, 1)
            s.aksi_konteks(a.id, "sematkan", None)
            b = s.buka_pose(j1, l1, 2)          # pose lain, grup sama
            c = s.buka_pose(j2, l2, 1)          # ligan lain
            tampil = {o.id for o in s.objek.values() if o.jenis == "pose" and o.tampil}
            print("tersemat tampil:", a.id in tampil, "| pose2 grup sama tampil:", b.id in tampil,
                  "| ligan lain tampil:", c.id in tampil, flush=True)
            s.aksi_konteks(a.id, "sematkan", None)
            s.buka_pose(j2, l2, 2)
            print("lepas sematan -> tersembunyi:", not s.objek[a.id].tampil, flush=True)
            QTimer.singleShot(500, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
