"""Uji Tahap 3 di GUI: analisis, diagram 2D, validasi redocking, bandingkan, peta, semua ekspor, laporan PDF.

Memakai proyek terakhir dari dev/uji_alur.py. Berkas keluaran ke dev/uji/ekspor/.
  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_tahap3.py
"""
import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", os.environ.get("VD_TEMA", "terang"))
st.remove("layout")
st.remove("sesi_terbuka")
PROYEK = sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1].resolve()
OUT = Path("dev/uji/ekspor").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)

import virmodock.app as A
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(OUT / "kompleks"))
from PySide6.QtGui import QDesktopServices
QDesktopServices.openUrl = staticmethod(lambda *a: True)


def hook():
    from virmodock.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            s._jalur = None
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(420000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _path(s, judul, nama, filter_):
            return str(OUT / nama)

        def p(s, *a):
            print(*a, flush=True)

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(5000, s.l2)

        def l2(s):
            from virmodock.core import ekspor
            b = ekspor.baris_hasil(s.proyek)
            s.p("baris hasil:", [(x["ligan"], x["energi"], x["le"], x["hbond"], x["hidrofobik"], x["rmsd_kristal"]) for x in b])
            s.buka_pose(b[0]["job"], b[0]["lid"], 1)
            s.d_inter.raise_()
            QTimer.singleShot(3500, s.l3)

        def l3(s):
            s.p("interaksi aktif:", s._aktif_inter["judul"], len(s._aktif_inter["daftar"]))
            s.grab().save("dev/t3_interaksi.png")
            s.tab_tengah.setCurrentWidget(s.diagram)
            QTimer.singleShot(800, s.l4)

        def l4(s):
            s.grab().save("dev/t3_diagram.png")
            s.tab_tengah.setCurrentWidget(s.hasil)
            QTimer.singleShot(500, s.l4b)

        def l4b(s):
            s.grab().save("dev/t3_hasil.png")
            # ekspor
            for d in ({"jenis": "gambar3d", "fmt": "tif", "lebar": 4252, "tinggi": 2835, "dpi": 600, "kompresi": "tiff_lzw",
                       "latar": "putih"},
                      {"jenis": "gambar3d", "fmt": "png", "lebar": 2000, "tinggi": 1400, "dpi": 300, "latar": "transparan"},
                      {"jenis": "diagram", "fmt": "svg", "mm": 120, "dpi": 600, "vdw": True, "transparan": False, "judul": True},
                      {"jenis": "diagram", "fmt": "pdf", "mm": 120, "dpi": 600, "vdw": True, "transparan": False, "judul": True},
                      {"jenis": "diagram", "fmt": "tif", "mm": 85, "dpi": 600, "vdw": False, "transparan": False, "judul": True},
                      {"jenis": "struktur", "isi": "kompleks"}, {"jenis": "struktur", "isi": "pdbqt"},
                      {"jenis": "struktur", "isi": "sdf_pose"}, {"jenis": "struktur", "isi": "sdf_terbaik"},
                      {"jenis": "struktur", "isi": "kompleks_semua"},
                      {"jenis": "tabel", "fmt": "csv", "sep": ";", "koma": True, "interaksi": True},
                      {"jenis": "tabel", "fmt": "xlsx", "sep": ";", "koma": True, "interaksi": True}):
                if d["jenis"] == "struktur" and d["isi"] == "kompleks_semua":
                    (OUT / "kompleks").mkdir(exist_ok=True)
                s._ekspor(d)
            QTimer.singleShot(8000, s.l5)

        def l5(s):
            # validasi redocking dengan AD-GPU 10 run
            s.param.set_parameter({"mesin": "adgpu", "perangkat": "gpu", "nrun_gpu": 20})
            s._param_berubah(s.param.parameter())
            s.pelaksana.jobSelesai.connect(lambda jid: QTimer.singleShot(3000, s.l6))
            s.validasi_redocking()

        def l6(s):
            s.p("validasi:", s.proyek.validasi)
            s.grab().save("dev/t3_validasi.png")
            from virmodock.core import ekspor
            b = ekspor.baris_hasil(s.proyek)
            pilih = [(x["job"], x["lid"]) for x in b[:3]]
            s.bandingkan(pilih)
            QTimer.singleShot(7000, s.l7)

        def l7(s):
            s.grab().save("dev/t3_banding.png")
            s.peta_interaksi()
            QTimer.singleShot(1000, s.l8)

        def l8(s):
            s.grab().save("dev/t3_peta.png")
            s._ekspor({"jenis": "laporan", "penulis": "Uji otomatis", "gambar": True})
            QTimer.singleShot(6000, s.l9)

        def l9(s):
            for f in sorted(OUT.rglob("*")):
                if f.is_file():
                    s.p(f"  {f.relative_to(OUT)}  {f.stat().st_size:,} B")
            s.p("PESAN:", s.pesan.toPlainText()[-1200:])
            s.p("LOG:", "\n".join(s.log.toPlainText().splitlines()[-25:]))
            QApplication.quit()

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
