"""Uji GUI dialog lanjut 0.9.7–1.1.0 pada proyek nyata (bukan mock): buka tiap Analisis/Alat baru dari
jendela utama, tangkap galat, simpan grab terang & gelap.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_dialog_lanjut_gui.py [nama ...]
Butuh dev/uji/md_gui/proyek_md.vmd (dibuat dev/uji_md_gui.py). Keluaran: dev/uji/lanjut/<nama>_<tema>.png
"""
import shutil
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

PILIH = sys.argv[1:]
sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", "terang")
st.remove("layout")
st.remove("sesi_terbuka")
st.setValue("mode_pengguna", "ahli")
OUT = Path("dev/uji/lanjut").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
CALON = [c for d in ("dev/uji/md_gui", "dev/uji/kerja", "dev/uji/proj") for c in sorted(Path(d).glob("*.vmd"))]


def _n_job(d):
    try:
        import json
        return len(json.loads((d / "proyek.json").read_text(encoding="utf-8")).get("job", []))
    except Exception:
        return 0


CALON = [c for c in CALON if _n_job(c)]
if not CALON:
    print("LEWAT: belum ada proyek .vmd berisi hasil docking (buat lewat dev/uji_md_gui.py)")
    raise SystemExit(0)
SUMBER = max(CALON, key=_n_job).resolve()
PROYEK = OUT / SUMBER.name
shutil.copytree(SUMBER, PROYEK)
st.setValue("folder_kerja", str(OUT))

import virmodock.app as A
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
gagal = []
_hook_lama = sys.excepthook


def _tangkap(t, v, tb):
    teks = "".join(traceback.format_exception(t, v, tb))
    print("Traceback (galat GUI):\n" + teks, flush=True)
    gagal.append(f"{t.__name__}: {v}")


sys.excepthook = _tangkap

DIALOG = ["admet", "mpo", "labplanner", "penapisan", "mmp", "selektivitas", "interpretasi", "ppi", "kantong", "fbdd",
          "skrip_publikasi", "diagnostik", "terowongan", "kinetika", "protac", "metabolisme", "rescore_ml"]
if PILIH:
    DIALOG = [d for d in DIALOG if d in PILIH]


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def hook():
    from virmodock.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(300000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _galat(s, t):
            print("GALAT:", t, flush=True)
            gagal.append(t)

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            cek(bool(s.proyek and s.proyek.job), f"proyek dibuka: {s.proyek and s.proyek.nama}")
            j = s.proyek.job[0]
            s.buka_pose(j["id"], j["ligan"][0]["id"], 1)
            QTimer.singleShot(3500, lambda: s.l3("terang"))

        def l3(s, tema):
            cek(bool(s._aktif_inter), f"pose aktif ({tema})")
            for nama in DIALOG:
                sebelum = set(QApplication.topLevelWidgets())
                n = len(gagal)
                try:
                    getattr(s, "buka_" + nama)()
                except Exception:
                    _tangkap(*sys.exc_info())
                for _ in range(15):
                    QApplication.processEvents()
                baru = [w for w in QApplication.topLevelWidgets() if w not in sebelum and isinstance(w, QDialog)
                        and w.isVisible()]
                if baru:
                    d = baru[0]
                    d.grab().save(str(OUT / f"{nama}_{tema}.png"))
                    cek(len(gagal) == n, f"{nama} ({tema}): {d.windowTitle()} {d.width()}×{d.height()}")
                    d.close()
                else:
                    cek(False, f"{nama} ({tema}): dialog tidak muncul")
                QApplication.processEvents()
            if tema == "terang":
                s.terapkan_tema("gelap")
                QTimer.singleShot(800, lambda: s.l3("gelap"))
            else:
                s.terapkan_tema("terang")
                print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
                QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
try:
    A.main()
except SystemExit:
    pass
