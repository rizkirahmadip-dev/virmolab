"""Uji kontrol: akurasi geser kotak di viewer, batal, jeda/lanjut. Memakai proyek dari dev/uji_alur.py."""
import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("tema", os.environ.get("VD_TEMA", "gelap"))
st.remove("layout")
st.remove("sesi_terbuka")
PROYEK = sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1].resolve()

import virmolab.app as A
from PySide6.QtWidgets import QApplication
Path("dev/uji/gambar").mkdir(parents=True, exist_ok=True)  # keluaran gambar uji


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(240000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(PROYEK))
            s.d_kerja.raise_()   # dulu d_param; aliasnya dibuang saat F6
            QTimer.singleShot(3000, s.l2)

        def l2(s):
            js = ("(()=>{try{const c=VM.kotak.c, p0=VM.v.modelToScreen({x:c[0],y:c[1],z:c[2]});"
                  "const d=VM.offsetModel(60,-25); const p1=VM.v.modelToScreen({x:c[0]+d[0],y:c[1]+d[1],z:c[2]+d[2]});"
                  "return JSON.stringify([p1.x-p0.x, p1.y-p0.y]);}catch(e){return String(e)}})()")
            s.viewer.page().runJavaScript(js, 0, lambda r: print("geser layar (harus ~60,-25):", r, flush=True))
            # batal: job Vina MK1 (lama), dibatalkan setelah 4 s
            s.param.set_parameter({"mesin": "vina", "perangkat": "cpu", "exhaustiveness": 8})
            s._param_berubah(s.param.parameter())
            s.jalankan_docking()
            s.jb = s.proyek.job[-1]["id"]
            QTimer.singleShot(4000, lambda: s.pelaksana.batal(s.jb))
            QTimer.singleShot(6000, s.l3)

        def l3(s):
            j = s.pelaksana.cari(s.jb)
            print("setelah batal:", j["status"], [(l["id"], l["status"]) for l in j["ligan"]], "sibuk", s.pelaksana.sibuk(), flush=True)
            # jeda lalu lanjut: AD-GPU
            s.param.set_parameter({"mesin": "adgpu", "perangkat": "gpu", "nrun_gpu": 10})
            s._param_berubah(s.param.parameter())
            s.jalankan_docking()
            s.jj = s.proyek.job[-1]["id"]
            s.pelaksana.jeda(s.jj)
            QTimer.singleShot(6000, s.l4)

        def l4(s):
            j = s.pelaksana.cari(s.jj)
            print("setelah jeda:", j["status"], [(l["id"], l["status"]) for l in j["ligan"]], flush=True)
            s.grab().save("dev/uji/gambar/kontrol_gelap.png")
            s.pelaksana.lanjut(s.jj)
            QTimer.singleShot(12000, s.l5)

        def l5(s):
            j = s.pelaksana.cari(s.jj)
            print("setelah lanjut:", j["status"], [(l["id"], l["status"], l["energi"]) for l in j["ligan"]], flush=True)
            print("PESAN:", s.pesan.toPlainText()[-800:], flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
