"""Tangkapan halaman pertama laporan PDF untuk tutorial: docs/gambar/t04_laporan.png.

Gambar lama dibuat manual pada Oktober 2026 dan masih memperlihatkan nama lama program serta jalur folder
pengembangan; berkas ini ikut tutorial PDF di dalam installer. Skrip ini membuat laporan sungguhan dari proyek
dokumentasi (dibuat dev/buat_screenshot.py di C:/VirmoLab-dokumentasi), lalu merender halaman pertamanya.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/buat_screenshot_laporan.py
"""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
KERJA = Path("C:/VirmoLab-dokumentasi")
OUT = Path("docs/gambar").resolve()
PDF = KERJA / "laporan_dokumentasi.pdf"
proyek = sorted(KERJA.glob("*.vmd"))
if not proyek:
    raise SystemExit(f"Tidak ada proyek di {KERJA}; jalankan dev/buat_screenshot.py dulu.")

st = QSettings("VirmoLab", "VirmoLab")
MODE_LAMA = st.value("mode_pengguna", "")
for k in ("layout", "layout_v2", "sesi_terbuka", "geometri"):
    st.remove(k)
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")
st.setValue("mode_pengguna", "pemula")

import virmolab.app as A                                              # noqa: E402
from PySide6.QtGui import QDesktopServices                            # noqa: E402
from PySide6.QtWidgets import QApplication                            # noqa: E402

QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)         # jangan membuka PDF di penampil luar


def render_halaman_satu():
    from PySide6.QtPdf import QPdfDocument
    d = QPdfDocument()
    d.load(str(PDF))
    for _ in range(100):                     # pemuatan PDF berjalan asinkron
        if d.status() == QPdfDocument.Status.Ready:
            break
        QApplication.processEvents()
    uk = d.pagePointSize(0)
    lebar = 1400
    img = d.render(0, (uk * (lebar / uk.width())).toSize())
    img.save(str(OUT / "t04_laporan.png"))
    print("gambar t04_laporan", img.width(), img.height(), flush=True)


def hook():
    from virmolab.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1600, 950)
            s._path = lambda *a, **k: str(PDF)          # ganti dialog "Simpan sebagai"
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(300000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(proyek[-1]))
            QTimer.singleShot(6000, s.l2)

        def l2(s):
            PDF.unlink(missing_ok=True)
            s._ekspor_laporan({"jenis": "laporan", "penulis": "", "gambar": True, "fmt": "pdf"})
            s.l3()

        def l3(s, sisa=120):
            if PDF.exists() and PDF.stat().st_size > 50_000:
                QTimer.singleShot(1500, s.l4)           # beri waktu penulisan selesai
                return
            if not sisa:
                print("GAGAL: laporan PDF tidak terbentuk", flush=True)
                QApplication.quit()
                return
            QTimer.singleShot(500, lambda: s.l3(sisa - 1))

        def l4(s):
            render_halaman_satu()
            if MODE_LAMA:
                st.setValue("mode_pengguna", MODE_LAMA)
            else:
                st.remove("mode_pengguna")
            st.sync()
            QApplication.quit()

    mainwindow.JendelaUtama = U
    A.main()


hook()
