"""Uji tab 'Uji & Grafik': contoh kolom & XY, isi dari docking, simpan/buka proyek, tangkapan layar.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_tab_uji.py
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

SUMBER = Path(str(sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1])).resolve()
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/tab_uji").resolve()
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
            s.resize(1500, 900)
            s._galat = lambda t: print("GALAT", t, flush=True)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(120000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(3000, s.l2)

        def l2(s):
            s.atur_ruang("analisis")
            s.tab_tengah.setCurrentWidget(s.uji)
            s.uji.isi_contoh()
            h = s.uji.hasil
            print("KOLOM", h["nama_uji"], round(h["p"], 5), [round(x[4], 4) for x in h["posthoc"]], flush=True)
            QTimer.singleShot(800, s.l3)

        def l3(s):
            s.grab().save(str(KERJA / "kolom.png"))
            s.uji.c_data.setCurrentIndex(1)
            s.uji.isi_contoh()
            h = s.uji.hasil
            print("XY", round(h["ic50"], 3), [round(x, 3) for x in h["ic50_ci"]], round(h["r2"], 4), flush=True)
            QTimer.singleShot(800, s.l4)

        def l4(s):
            s.grab().save(str(KERJA / "xy.png"))
            s._uji_dari_docking("job")
            print("DOCKING", s.uji.nama_kolom(), s.uji.hasil.get("nama_uji"), flush=True)
            s.simpan_proyek() if hasattr(s, "simpan_proyek") else s.proyek.simpan()
            import json
            d = json.loads((KERJA / SUMBER.name / "proyek.json").read_text(encoding="utf-8"))
            print("TERSIMPAN", d["uji_grafik"]["jenis"], d["uji_grafik"]["kolom"][:3], flush=True)
            QTimer.singleShot(500, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
