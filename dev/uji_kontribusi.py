"""Uji kontribusi energi per atom: buka pose terbaik, aktifkan toggle, simpan tangkapan viewport.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_kontribusi.py
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

SUMBER = Path(str(sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1])).resolve()
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/kontribusi").resolve()
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
            QTimer.singleShot(120000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            j = s.proyek.job[0]
            l = next(x for x in j["ligan"] if x["status"] == "selesai")
            s.buka_pose(j["id"], l["id"], 1)
            s.a_kontrib.setChecked(True)
            s._tampilkan_kontribusi()
            print("STATUS", s.statusBar().currentMessage(), flush=True)
            prot = next(o for o in s.objek.values() if o.jenis == "protein" and o.tampil)
            s.viewer.js("sorot", prot.id, {"resi": [25, 50]})   # uji halo seleksi
            QTimer.singleShot(2500, s.l3)

        def l3(s):
            s.viewer.grab().save(str(KERJA / "kontribusi.png"))
            QTimer.singleShot(300, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
