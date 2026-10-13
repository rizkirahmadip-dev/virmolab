"""Tangkap viewport dengan label residu (pose terbaik) pada resolusi layar -> dev/uji/dpi/label_<nama>.png.
  .venv/Scripts/python.exe dev/diag_label.py NAMA
"""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
NAMA = sys.argv[1] if len(sys.argv) > 1 else "x"
JS = sys.argv[2] if len(sys.argv) > 2 else ""
sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.remove("layout")
st.remove("sesi_terbuka")
PROYEK = sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1].resolve()
OUT = Path("dev/uji/dpi")
OUT.mkdir(parents=True, exist_ok=True)

import virmolab.app as A  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class D(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1500, 900)
            QTimer.singleShot(2500, s.l1)

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(5000, s.l2)

        def l2(s):
            from virmolab.core import ekspor
            b = ekspor.baris_hasil(s.proyek)
            s.buka_pose(b[0]["job"], b[0]["lid"], 1)
            if JS:
                QTimer.singleShot(3000, lambda: s.viewer.page().runJavaScript(JS + ";VM.v.render();"))
            QTimer.singleShot(4500, s.l3)

        def l3(s):
            img = s.viewer.grab()
            img.save(str(OUT / f"label_{NAMA}.png"))
            w, h = img.width(), img.height()
            img.copy(int(w * 0.3), int(h * 0.3), int(w * 0.3), int(h * 0.25)).save(str(OUT / f"label_{NAMA}_crop.png"))
            print("viewer grab", w, h, img.devicePixelRatio(), flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = D
    A.main()


hook()
