"""Uji editor Ketcher: dimuat offline, setMolecule (kurkumin), baca Molfile -> ligan 3D baru.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_ketcher.py
Keluaran: dev/uji/ketcher/ketcher.png
"""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/ketcher").resolve()
KERJA.mkdir(parents=True, exist_ok=True)
st = QSettings("VirmoLab", "VirmoLab")
for k in ("sesi_terbuka", "proyek_terakhir"):
    st.remove(k)
st.setValue("wizard_selesai", True)

import virmolab.app as A
from PySide6.QtWidgets import QApplication


def hook():
    from virmolab.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1300, 850)
            s._galat = lambda t: print("GALAT", t, flush=True)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(90000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            import time
            from virmolab.ui.dialog_ketcher import DialogKetcher
            d = s.dlg = DialogKetcher(s, "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O", "kurkumin")
            d.show()
            s.t0 = time.time()
            s._tunggu(lambda: d.siap, s.l2)

        def _tunggu(s, syarat, lanjut, n=0):
            if syarat() or n > 200:
                lanjut()
            else:
                QTimer.singleShot(250, lambda: s._tunggu(syarat, lanjut, n + 1))

        def l2(s):
            import time
            d = s.dlg
            print("ketcher siap:", d.siap, f"{time.time() - s.t0:.1f} s", flush=True)
            QTimer.singleShot(2500, s.l3)

        def l3(s):
            d = s.dlg
            d.grab().save(str(KERJA / "ketcher.png"))
            d.finished.connect(lambda r: s.l4(r))
            d._ambil("getMolfile", d._jadi)

        def l4(s, r):
            d = s.dlg
            print("hasil:", r, getattr(d, "hasil_smiles", None), d.l_status.text(), flush=True)
            QTimer.singleShot(300, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
