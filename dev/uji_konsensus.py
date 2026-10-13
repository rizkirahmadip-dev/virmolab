"""Uji Konsensus skor di GUI: rescoring Vina/Vinardo pose terbaik + kolom AD-GPU -> peringkat konsensus, Kendall W,
CSV, tersimpan di proyek. Keluaran dev/uji/konsensus/.
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/uji_konsensus.py
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.remove("layout")
st.remove("sesi_terbuka")
OUT = Path("dev/uji/konsensus").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
ASAL = sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1]
def _cukup_ligan(folder, minimal=3):
    """Jumlah ligan berstatus selesai pada proyek contoh (uji ini perlu beberapa ligan untuk dibandingkan)."""
    import json
    try:
        data = json.loads((folder / "proyek.json").read_text(encoding="utf-8"))
    except Exception:
        return 0
    nama = {l["nama"] for j in data.get("job", []) for l in j.get("ligan", []) if l.get("status") == "selesai"}
    return len(nama)


if _cukup_ligan(ASAL) < 3:
    print(f"LEWAT: proyek contoh {ASAL.name} hanya punya {_cukup_ligan(ASAL)} ligan selesai; "
          "uji ini butuh minimal 3. Jalankan docking beberapa ligan lalu salin proyeknya ke dev/uji/kerja_docs/.")
    raise SystemExit(0)

PROYEK = OUT / ASAL.name
shutil.copytree(ASAL, PROYEK)

import virmolab.app as A  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(OUT / "konsensus.csv"), ""))
gagal = []


def cek(nama, kondisi, detail=""):
    print(("OK   " if kondisi else "GAGAL") + f" {nama} {detail}", flush=True)
    if not kondisi:
        gagal.append(nama)


def hook():
    from virmolab.ui import mainwindow
    from virmolab.ui.dialog_konsensus import DialogKonsensus
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1500, 900)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(180000, lambda: (print("TIMEOUT", flush=True), QApplication.quit()))

        def _galat(s, t):
            print("GALAT:", t, flush=True)
            gagal.append(str(t)[:80])

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            s.d = DialogKonsensus(s)
            s.d.show()
            s.d.hitung()
            QTimer.singleShot(15000, s.l3)

        def l3(s):
            h = s.d.hasil
            cek("hasil konsensus", h and not h.get("galat") and h["n"] >= 3,
                f"kolom={h and h['kolom']} n={h and h['n']} galat={h and h.get('galat')}")
            if h and not h.get("galat"):
                print([(b["ligan"], [round(x, 2) for x in b["skor"]], b["rata_rank"], b["konsisten"]) for b in h["baris"]])
                cek("Kendall W", h["W"] is not None, str(h["W"]))
            s.d.grab().save(str(OUT / "dialog.png"))
            s.d.ekspor()
            cek("CSV", (OUT / "konsensus.csv").exists())
            j = [x for x in s.proyek.job if any((l.get("rescore") or {}) for l in x["ligan"])]
            cek("rescoring tersimpan di job", bool(j))
            print("SEMUA LULUS" if not gagal else f"GAGAL: {gagal}", flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
