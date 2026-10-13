"""Uji dialog ChEMBL (butuh internet): cari target 1HSG, ambil aktivitas, impor 5 teratas, cocokkan dengan docking.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_chembl.py
Keluaran: dev/uji/chembl/
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

SUMBER = Path(str(sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1])).resolve()
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/chembl").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
shutil.copytree(SUMBER, KERJA / SUMBER.name)
st = QSettings("VirmoLab", "VirmoLab")
for k in ("sesi_terbuka", "proyek_terakhir"):
    st.remove(k)
st.setValue("wizard_selesai", True)

import virmolab.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: None)


def hook():
    from virmolab.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1400, 900)
            s._galat = lambda t: print("GALAT", t, flush=True)
            s._path = lambda judul, nama, f: str(KERJA / nama)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(300000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            from virmolab.ui.dialog_chembl import DialogChembl
            d = s.dlg = DialogChembl(s)
            d.show()
            print("kueri awal:", d.e_cari.text(), flush=True)
            d.cari()
            s._tunggu(lambda: d.target, s.l3)

        def _tunggu(s, syarat, lanjut, n=0):
            if syarat() or n > 240:
                lanjut()
            else:
                QTimer.singleShot(500, lambda: s._tunggu(syarat, lanjut, n + 1))

        def l3(s):
            d = s.dlg
            print("target:", [(t["chembl"], t["nama"], t.get("aktivitas")) for t in d.target[:3]], flush=True)
            d.grab().save(str(KERJA / "target.png"))
            d.s_maks.setValue(1000)
            d.ambil()
            s._tunggu(lambda: d.senyawa, s.l4)

        def l4(s):
            d = s.dlg
            print("senyawa:", len(d.senyawa), [x["nama"] for x in d.senyawa[:5]], flush=True)
            d.grab().save(str(KERJA / "senyawa.png"))
            d.s_impor.setValue(5)
            d.impor()
            print("objek ligan:", sum(1 for o in s.objek.values() if o.jenis == "ligan"), flush=True)
            d.korelasi()
            print("cocok:", d.cocok, flush=True)
            print("pchembl di proyek:", [(l["nama"], l.get("pchembl")) for l in s.proyek.ligan], flush=True)
            d.grab().save(str(KERJA / "korelasi.png"))
            d.ekspor_csv()
            QTimer.singleShot(500, s.l5)

        def l5(s):
            s.dlg.close()
            from virmolab.ui.dialog_chembl import DialogChembl
            d2 = DialogChembl(s, 1)       # buka ulang: data tersimpan di proyek
            print("buka ulang, senyawa tersimpan:", len(d2.senyawa), flush=True)
            d2.close()
            for f in sorted(KERJA.iterdir()):
                if f.is_file():
                    print(f"  {f.name}: {f.stat().st_size} B")
            QTimer.singleShot(300, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
