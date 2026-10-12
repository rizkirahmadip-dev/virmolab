"""Uji dialog ADMET-AI: salinan proyek docs (3 ligan + kristal), prediksi di proses terpisah, cache, ekspor CSV.
Juga mengukur jeda event loop GUI selama prediksi (harus kecil karena berjalan di proses lain).

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_admet.py
Keluaran: dev/uji/admet/
"""
import shutil
import sys
import time
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

CALON = [c for d in ("dev/uji/kerja_docs", "dev/uji/kerja", "dev/uji/md_gui", "dev/uji/proj")
         for c in sorted(Path(d).glob("*.vmd"))]
if not CALON:
    print("LEWAT: tidak ada proyek .vmd untuk diuji (buat dulu lewat dev/uji_md_gui.py)")
    raise SystemExit(0)
def _n_ligan(d):
    try:
        import json
        return len(json.loads((d / "proyek.json").read_text(encoding="utf-8")).get("ligan", []))
    except Exception:
        return 0
SUMBER = max(CALON, key=_n_ligan).resolve()   # proyek dengan ligan terbanyak
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/admet").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
shutil.copytree(SUMBER, KERJA / SUMBER.name)
st = QSettings("VirmoDock", "VirmoDock")
for k in ("sesi_terbuka", "proyek_terakhir"):
    st.remove(k)
st.setValue("wizard_selesai", True)

import virmodock.app as A
from PySide6.QtWidgets import QApplication


def hook():
    from virmodock.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1400, 900)
            s._galat = lambda t: print("GALAT", t, flush=True)
            s._path = lambda judul, nama, f: str(KERJA / nama)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(180000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            from virmodock.ui.dialog_admet import DialogAdmet
            d = s.dlg = DialogAdmet(s)
            d.resize(1300, 760)
            d.show()
            print("ligan:", [x["nama"] for x in d.lig], flush=True)
            s.jeda, s.t_akhir = 0.0, time.perf_counter()
            s.detak = QTimer()
            s.detak.timeout.connect(s._detak)
            s.detak.start(20)
            s.t0 = time.time()
            d.hitung(False)
            s._tunggu(lambda: all(x["hasil"] for x in d.lig), s.l3)

        def _detak(s):
            t = time.perf_counter()
            s.jeda = max(s.jeda, t - s.t_akhir)
            s.t_akhir = t

        def _tunggu(s, syarat, lanjut, n=0):
            if syarat() or n > 300:
                lanjut()
            else:
                QTimer.singleShot(300, lambda: s._tunggu(syarat, lanjut, n + 1))

        def l3(s):
            s.detak.stop()
            d = s.dlg
            print(f"prediksi {time.time() - s.t0:.1f} s; jeda GUI terbesar {s.jeda * 1000:.0f} ms", flush=True)
            for x in d.lig:
                h = x["hasil"] or {}
                print(f"  {x['nama']}: HIA {h.get('HIA_Hou')} BBB {h.get('BBB_Martins')} hERG {h.get('hERG')}",
                      flush=True)
            d.tabel.selectRow(0)
            d.grab().save(str(KERJA / "admet.png"))
            d.ekspor()
            print("cache proyek:", sum(1 for l in s.proyek.ligan if l.get("admet")), flush=True)
            from virmodock.ui.dialog_admet import DialogAdmet
            d2 = DialogAdmet(s)
            print("buka ulang, belum dihitung:", sum(1 for x in d2.lig if x["hasil"] is None), flush=True)
            d2.close()
            QTimer.singleShot(300, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
