"""Uji GUI tab Statistik: salinan proyek 6M2N, semua jenis grafik, ekspor, ganti job, tema gelap.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_statistik_gui.py
Keluaran: dev/uji/statistik/gui/ (gui*.png = grab jendela saja, csv/svg/pdf/png/tif/xlsx).
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", "terang")
st.remove("layout")
st.remove("sesi_terbuka")
SUMBER = sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1].resolve()  # proyek docs terbaru
def _cukup_ligan(folder, minimal=3):
    """Jumlah ligan berstatus selesai pada proyek contoh (uji ini perlu beberapa ligan untuk dibandingkan)."""
    import json
    try:
        data = json.loads((folder / "proyek.json").read_text(encoding="utf-8"))
    except Exception:
        return 0
    nama = {l["nama"] for j in data.get("job", []) for l in j.get("ligan", []) if l.get("status") == "selesai"}
    return len(nama)


if _cukup_ligan(SUMBER) < 3:
    print(f"LEWAT: proyek contoh {SUMBER.name} hanya punya {_cukup_ligan(SUMBER)} ligan selesai; "
          "uji ini butuh minimal 3. Jalankan docking beberapa ligan lalu salin proyeknya ke dev/uji/kerja_docs/.")
    raise SystemExit(0)

OUT = Path("dev/uji/statistik/gui").resolve()
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
            s.tab_tengah.setCurrentWidget(s.statistik)
            st_ = s.statistik
            print(f"muat: {time.perf_counter() - t:.2f} s; job: {[st_.c_job.itemText(i) for i in range(st_.c_job.count())]}")
            print("data job terpilih:", len(st_.data), flush=True)
            for i, (k, _t) in enumerate(__import__("virmodock.ui.tab_statistik", fromlist=["JENIS"]).JENIS):
                st_.c_jenis.setCurrentIndex(i)
                svg, ukuran = st_.svg()
                if k == "ifp" and not any(d.get("ifp") for d in st_.data):
                    print("  ifp: dilewati (proyek lama tanpa sidik jari interaksi)", flush=True)
                    continue
                print(f"  {k}: svg {len(svg)} B ukuran {ukuran}", flush=True)
                s.grab().save(str(OUT / f"gui_{k}.png"))
                for f in ("svg", "png"):
                    s._ekspor_statistik(f)
            st_.c_jenis.setCurrentIndex(1)
            st_.c_label.setChecked(True)
            s.grab().save(str(OUT / "gui_sebar_label.png"))
            s._ekspor_statistik("csv")
            st_.c_job.setCurrentIndex(st_.c_job.count() - 1)
            print("semua job (terbaik per ligan):", len(st_.data))
            s.ganti_tema()
            QTimer.singleShot(800, s.l3)

        def l3(s):
            s.grab().save(str(OUT / "gui_gelap.png"))
            s.ganti_tema()
            for f in sorted(OUT.iterdir()):
                if f.is_file():
                    print(f"  {f.name}: {f.stat().st_size} B")
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
A.main()
