"""Uji GUI tab Sifat Ligan: buka salinan proyek 6M2N (26 ligan), hitung sifat, pilih baris, ekspor, tema gelap.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_sifat_gui.py
Keluaran: dev/uji/sifat/ (gui*.png = grab jendela saja, csv/svg/pdf/png/tif/xlsx).
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("tema", "terang")
st.remove("layout")
st.remove("sesi_terbuka")
SUMBER = sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1].resolve()  # proyek docs terbaru
OUT = Path("dev/uji/sifat").resolve()
OUT.mkdir(parents=True, exist_ok=True)
PROYEK = OUT / "proyek_uji.vmd"
shutil.rmtree(PROYEK, ignore_errors=True)
shutil.copytree(SUMBER, PROYEK)

import virmolab.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(120000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _path(s, judul, nama, filter_):
            return str(OUT / nama)

        def _galat(s, t):
            print("GALAT:", t, flush=True)

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            import time
            t = time.perf_counter()
            s.tab_tengah.setCurrentWidget(s.sifat)
            print(f"hitung {len(s.sifat.data)} ligan: {time.perf_counter() - t:.2f} s", flush=True)
            print("ringkas:", s.sifat.l_n.text(), flush=True)
            for n, x, dg in s.sifat.data[:5]:
                print(f"  {n}: MW {x['mw']} WLOGP {x['wlogp']} TPSA {x['tpsa']} GI {x['gi']} BBB {x['bbb']} dG {dg}")
            ada = sum(1 for l in s.proyek.ligan if l.get("sifat"))
            print("tersimpan di proyek:", ada, "/", len(s.proyek.ligan), flush=True)
            s.sifat.pohon.setCurrentItem(s.sifat.pohon.topLevelItem(2))
            QTimer.singleShot(600, s.l3)

        def l3(s):
            s.grab().save(str(OUT / "gui_terang.png"))
            for f in ("csv", "svg", "png"):
                s._ekspor_sifat(f)
            s._simpan_svg(s.sifat.svg(gelap=False), str(OUT / "egg.pdf"), "pdf", 760, 600, 140)
            s._simpan_svg(s.sifat.svg(gelap=False), str(OUT / "egg.tif"), "tif", 760, 600, 140, 300)
            from virmolab.core import ekspor
            ekspor.simpan_xlsx(str(OUT / "uji.xlsx"), s.proyek, ekspor.baris_hasil(s.proyek), {}, {},
                               [x for x in s._data_sifat() if isinstance(x[1], dict)])
            # urut kolom ΔG
            from PySide6.QtCore import Qt
            s.sifat.pohon.sortItems(2, Qt.AscendingOrder)
            print("urut ΔG teratas:", s.sifat.pohon.topLevelItem(0).text(1), s.sifat.pohon.topLevelItem(0).text(2))
            s.atur_tema("gelap") if hasattr(s, "atur_tema") else s.ganti_tema()
            QTimer.singleShot(800, s.l4)

        def l4(s):
            s.grab().save(str(OUT / "gui_gelap.png"))
            s.simpan_proyek() if hasattr(s, "simpan_proyek") else None
            for f in sorted(OUT.iterdir()):
                if f.is_file():
                    print(f"  {f.name}: {f.stat().st_size} B")
            s.ganti_tema()
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
A.main()
