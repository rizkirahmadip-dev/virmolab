"""Uji deteksi kantong P2Rank dari GUI: tombol langkah 3 -> dialog -> grid box di kantong #1.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_p2rank.py
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

CALON = [c for d in ("dev/uji/kerja_docs", "dev/uji/kerja", "dev/uji/md_gui", "dev/uji/proj")
         for c in sorted(Path(d).glob("*.vmd"))]
if not CALON:
    print("LEWAT: belum ada proyek .vmd contoh untuk diuji")
    raise SystemExit(0)
def _punya_reseptor(d):
    """Proyek contoh harus punya entri reseptor DAN berkas objek protein tersimpan (dipulihkan saat dibuka)."""
    try:
        import json
        data = json.loads((d / "proyek.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    if not data.get("reseptor"):
        return False
    return any(o.get("jenis") == "protein" and (d / o.get("berkas", "")).exists()
               for o in data.get("objek", []))


CALON = [c for c in CALON if _punya_reseptor(c)]
if not CALON:
    print("LEWAT: belum ada proyek .vmd contoh yang punya reseptor")
    raise SystemExit(0)
SUMBER = CALON[-1].resolve()
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/p2rank_gui").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
shutil.copytree(SUMBER, KERJA / SUMBER.name)
st = QSettings("VirmoLab", "VirmoLab")
for k in ("sesi_terbuka", "proyek_terakhir"):
    st.remove(k)
st.setValue("wizard_selesai", True)

import virmolab.app as A
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: None)


def hook():
    from virmolab.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1400, 880)
            s._galat = lambda t: print("GALAT", t, flush=True)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(180000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(3000, s.l2)

        def l2(s):
            s.ke_langkah(2)
            s.box["pusat"] = None
            s.cek_dialog = QTimer(s)
            s.cek_dialog.timeout.connect(s.tutup_dialog)
            s.cek_dialog.start(500)
            s.param.btn_kotak["kantong"].click()

        def tutup_dialog(s):
            d = QApplication.activeModalWidget()
            if isinstance(d, QDialog):
                s.cek_dialog.stop()
                d.grab().save(str(KERJA / "dialog.png"))
                s.grab().save(str(KERJA / "jendela.png"))
                d.accept()
                QTimer.singleShot(800, s.l3)

        def l3(s):
            print("KOTAK", s.box["pusat"], s.box["ukuran"], flush=True)
            QTimer.singleShot(300, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
