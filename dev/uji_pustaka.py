"""Uji dialog Pustaka ligan: obat (saring + kemiripan), COCONUT (unduhan parsial 3 MB bila belum ada), impor.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_pustaka.py
Keluaran: dev/uji/pustaka/. Basis data COCONUT uji (parsial) dihapus di akhir bila dibuat oleh uji ini.
"""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/pustaka").resolve()
KERJA.mkdir(parents=True, exist_ok=True)
st = QSettings("VirmoLab", "VirmoLab")
for k in ("sesi_terbuka", "proyek_terakhir"):
    st.remove(k)
st.setValue("wizard_selesai", True)

import virmolab.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

from virmolab.core import pustaka as P

QMessageBox.information = staticmethod(lambda *a, **k: None)
BUAT_DB = P.coconut_ada() is None
if BUAT_DB:
    print("membuat COCONUT parsial:", P.unduh_coconut(maks_byte=3_000_000), flush=True)


def hook():
    from virmolab.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1300, 850)
            s._galat = lambda t: print("GALAT", t, flush=True)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(120000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _tunggu(s, syarat, lanjut, n=0):
            if syarat() or n > 120:
                lanjut()
            else:
                QTimer.singleShot(300, lambda: s._tunggu(syarat, lanjut, n + 1))

        def l1(s):
            from virmolab.ui.dialog_pustaka import DialogPustaka
            d = s.dlg = DialogPustaka(s)
            d.show()
            d.o_atc.setCurrentIndex(d.o_atc.findData("N"))
            d.e_mirip.setText("CC(=O)Nc1ccc(O)cc1")
            d.hasil = None
            d.cari()
            s._tunggu(lambda: d.hasil is not None, s.l2)

        def l2(s):
            d = s.dlg
            print("obat N mirip parasetamol:", [(h["nama"], h["mirip"]) for h in d.hasil[:5]], flush=True)
            d.grab().save(str(KERJA / "obat.png"))
            for r in range(3):
                d.tabel.item(r, 0).setCheckState(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Checked)
            d.impor()
            print(d.l_status.text(), flush=True)
            d.c_sumber.setCurrentIndex(1)
            d.e_mirip.setText("")
            d.k_kelas.setText("flavon")
            d.hasil = None
            d.cari()
            s._tunggu(lambda: d.hasil is not None, s.l3)

        def l3(s):
            d = s.dlg
            print("coconut flavon:", len(d.hasil), [h["nama"][:25] for h in d.hasil[:4]], flush=True)
            d.grab().save(str(KERJA / "coconut.png"))
            d.c_sumber.setCurrentIndex(2)
            d.grab().save(str(KERJA / "zinc.png"))
            print("ligan di viewer:", [o.nama for o in s.objek.values() if o.jenis == "ligan"], flush=True)
            if BUAT_DB:
                P.hapus_coconut()
            QTimer.singleShot(300, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
