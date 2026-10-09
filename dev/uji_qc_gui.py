"""Uji GUI QC PoseBusters: salinan proyek lama 6M2N (tanpa QC) -> dilengkapi otomatis di latar -> kolom Hasil, dialog pose.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_qc_gui.py
Keluaran: dev/uji/qc/gui/ (gui*.png = grab jendela saja, csv/svg/pdf/png/tif/xlsx).
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", "terang")
st.remove("layout")
st.remove("sesi_terbuka")
SUMBER = Path("dev/uji/kerja_docs/6M2N_20261008_1440.vmd").resolve()
OUT = Path("dev/uji/qc/gui").resolve()
OUT.mkdir(parents=True, exist_ok=True)
PROYEK = OUT / "proyek_uji.vmd"
shutil.rmtree(PROYEK, ignore_errors=True)
shutil.copytree(SUMBER, PROYEK)

import virmodock.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))


def hook():
    from virmodock.ui import mainwindow
    Asli = mainwindow.JendelaUtama
    teks_dialog = []
    QMessageBox.exec = lambda self: teks_dialog.append(self.text()) or 0

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(240000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _galat(s, t):
            print("GALAT:", t, flush=True)

        def l1(s):
            import time
            s.t0 = time.perf_counter()
            s.buka_proyek(str(PROYEK))
            s.tab_tengah.setCurrentWidget(s.hasil)
            QTimer.singleShot(1000, s.tunggu)

        def tunggu(s):
            import time
            sisa = [l for j in s.proyek.job for l in j["ligan"] if l["status"] == "selesai" and not l.get("qc")]
            if sisa and time.perf_counter() - s.t0 < 200:
                QTimer.singleShot(1000, s.tunggu)
                return
            print(f"QC dilengkapi dalam {time.perf_counter() - s.t0:.1f} s; belum: {len(sisa)}", flush=True)
            semua = [l for j in s.proyek.job for l in j["ligan"] if l["status"] == "selesai"]
            print("lulus:", sum(1 for l in semua if l["qc"].get("lulus")), "/", len(semua), flush=True)
            s._muat_hasil()
            from virmodock.ui.panel_hasil import K_QC
            p = s.hasil.pohon
            print("kolom:", p.headerItem().text(K_QC), "| contoh:",
                  [(p.topLevelItem(i).text(1), p.topLevelItem(i).text(K_QC)) for i in range(4)], flush=True)
            s.grab().save(str(OUT / "gui_hasil.png"))
            b = __import__("virmodock.core.ekspor", fromlist=["x"]).baris_hasil(s.proyek)
            gagal = next((x for x in b if x["qc"] and not x["qc"]["lulus"]), b[0])
            s.buka_pose(gagal["job"], gagal["lid"], 1)
            QTimer.singleShot(3000, s.l2)

        def l2(s):
            s.qc_pose_aktif()
            QTimer.singleShot(6000, s.l3)

        def l3(s):
            import re
            print("dialog:", re.sub("<[^>]+>", " ", teks_dialog[-1])[:500] if teks_dialog else "TIDAK ADA", flush=True)
            print("properti:", [s.prop.tabel.item(r, 0).text() + "=" + s.prop.tabel.item(r, 1).text()
                                for r in range(s.prop.tabel.rowCount())][-3:] if hasattr(s.prop, "tabel") else "-")
            s.grab().save(str(OUT / "gui_pose.png"))
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
A.main()
