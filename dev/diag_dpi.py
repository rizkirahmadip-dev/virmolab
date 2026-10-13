"""Diagnostik ketajaman: DPR Qt vs WebEngine, ukuran kanvas WebGL vs CSS, rasio piksel grafik SVG.
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/diag_dpi.py
"""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.remove("layout")
st.remove("sesi_terbuka")
PROYEK = sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1].resolve()
OUT = Path("dev/uji/dpi")
OUT.mkdir(parents=True, exist_ok=True)

import virmolab.app as A  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

JS = ("(() => { window._n = 0; const asli = VM.v.render.bind(VM.v); VM.v.render = function () { window._n++; return asli(...arguments); }; "
      "VM.v.render(); return 'pasang'; })()")
JS2 = "JSON.stringify({render_2_detik: window._n})"


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
            QTimer.singleShot(6000, s.l1b)

        def l1b(s):
            from virmolab.core import ekspor
            b = ekspor.baris_hasil(s.proyek)
            s.buka_pose(b[0]["job"], b[0]["lid"], 1)
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            scr = s.screen()
            print("Qt: DPR jendela", s.devicePixelRatioF(), "| layar", scr.name(), scr.devicePixelRatio(),
                  "logical DPI", scr.logicalDotsPerInch(), "| ukuran layar", scr.size().toTuple(), flush=True)
            print("viewer widget", s.viewer.width(), s.viewer.height(), "DPR", s.viewer.devicePixelRatioF(), flush=True)
            s.viewer.page().runJavaScript(JS, 0, lambda r: QTimer.singleShot(2000, lambda: s.viewer.page().runJavaScript(
                JS2, 0, lambda r2: (print("WebGL:", r2, flush=True), s.l3()))))

        def l3(s):
            s.tab_tengah.setCurrentWidget(s.uji)
            s.uji.isi_contoh()
            QTimer.singleShot(800, s.l4)

        def l4(s):
            k = s.uji.kanvas
            print("Kanvas grafik", k.width(), k.height(), "DPR", k.devicePixelRatioF(), flush=True)
            img = k.grab()
            print("grab grafik px", img.width(), img.height(), "dpr", img.devicePixelRatio(), flush=True)
            img.save(str(OUT / "grafik_grab.png"))
            QApplication.quit()

    mainwindow.JendelaUtama = D
    A.main()


hook()
