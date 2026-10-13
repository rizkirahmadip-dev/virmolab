"""Uji UI/UX baru (panel Langkah, ruang kerja, antrean ringkas, kolom Hasil) di GUI.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_ux.py
  env VD_UKURAN=1366x768 untuk layar kecil. Tangkapan JENDELA saja (widget.grab) -> dev/uji/ux/.
"""
import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("tema", "terang")
st.setValue("wizard_selesai", True)
for k in ("layout", "layout_v2", "sesi_terbuka", "kolom_hasil"):
    st.remove(k)
UKURAN = [int(x) for x in os.environ.get("VD_UKURAN", "1700x1000").split("x")]
SUMBER = sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1].resolve()
OUT = Path("dev/uji/ux").resolve()
OUT.mkdir(parents=True, exist_ok=True)
PROYEK = OUT / "proyek_ux.vmd"
shutil.rmtree(PROYEK, ignore_errors=True)
shutil.copytree(SUMBER, PROYEK)
akhiran = "" if UKURAN[0] >= 1600 else f"_{UKURAN[0]}"

import virmolab.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: 0)


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(*UKURAN)
            s.move(10, 10)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(240000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def foto(s, n):
            s.grab().save(str(OUT / f"{n}{akhiran}.png"))

        def status_langkah(s):
            return [(b.status, b.ket) for b in s.langkah.baris]

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            js = ("(function(){const v=VM.v, r=v.renderer||{};const c=document.querySelector('#gl canvas');"
                  "return JSON.stringify({dpr:devicePixelRatio, rdpr:r.devicePixelRatio, vp:[r._viewportWidth,"
                  "r._viewportHeight], buf:[c.width,c.height], css:[c.clientWidth,c.clientHeight], W:[v.WIDTH,v.HEIGHT]});})()")
            s.viewer.page().runJavaScript(js, 0, lambda r: print("KANVAS:", r, flush=True))
            print("status langkah:", s.status_langkah(), flush=True)
            print("ruang:", s._ruang_aktif, "| tab terlihat:",
                  [s.tab_tengah.tabText(i) for i in range(s.tab_tengah.count()) if s.tab_tengah.isTabVisible(i)])
            print("panel bawah terlihat:", s.d_antre.isVisible(), "| tombol:", s.b_antre.text(), flush=True)
            s.ke_langkah(0)
            QTimer.singleShot(500, lambda: (s.foto("1_protein"), s.ke_langkah(2),
                                            QTimer.singleShot(500, s.l3)))

        def l3(s):
            s.foto("3_area")
            s.ke_langkah(3)
            QTimer.singleShot(500, s.l4)

        def l4(s):
            s.foto("4_jalankan")
            s.param.b_lanjutan.setChecked(True)
            QTimer.singleShot(300, s.l5)

        def l5(s):
            s.foto("4_jalankan_lanjutan")
            s.param.b_lanjutan.setChecked(False)
            s.param.cmb_preset.setCurrentText("Cepat")
            s.param.terapkan_preset("Cepat")
            print("tombol jalan:", s.param.b_run.text(), "| ruang:", s._ruang_aktif, flush=True)
            s.param.b_run.click()          # docking sungguhan dari langkah 4
            QTimer.singleShot(1500, s.l6)

        def l6(s):
            print("setelah jalankan: bawah terlihat", s.d_antre.isVisible(), "|", s.b_antre.text(), flush=True)
            s.foto("4_berjalan")
            s.tunggu = 0
            QTimer.singleShot(1000, s.l7)

        def l7(s):
            jalan = any(j["status"] in ("berjalan", "menunggu") for j in s.proyek.job)
            s.tunggu += 1
            if jalan and s.tunggu < 120:
                QTimer.singleShot(1000, s.l7)
                return
            QTimer.singleShot(1500, s.l8)

        def l8(s):
            print("setelah selesai: langkah aktif", s.langkah.aktif(), "ruang", s._ruang_aktif,
                  "| tab:", s.tab_tengah.tabText(s.tab_tengah.currentIndex()), flush=True)
            print("kolom Hasil terlihat:", [s.hasil.pohon.headerItem().text(k) for k in range(s.hasil.pohon.columnCount())
                                           if not s.hasil.pohon.isColumnHidden(k)], flush=True)
            print("status langkah:", s.status_langkah(), flush=True)
            s.foto("5_hasil")
            b = __import__("virmolab.core.ekspor", fromlist=["x"]).baris_hasil(s.proyek)
            s.buka_pose(b[0]["job"], b[0]["lid"], 1)
            s.atur_ruang("analisis")
            QTimer.singleShot(3000, s.l9)

        def l9(s):
            s.d_inter.raise_()
            s.foto("5_interaksi")
            s.atur_ruang("siapkan")
            print("kembali ke Siapkan: langkah", s.langkah.aktif(), "| interaksi terlihat", s.d_inter.isVisible())
            s.ganti_tema()
            QTimer.singleShot(1200, s.l10)

        def l10(s):
            s.foto("gelap")
            s.ganti_tema()
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
A.main()
