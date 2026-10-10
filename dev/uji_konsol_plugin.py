"""Uji konsol Python + plugin (0.9.5): konsol menjalankan perintah & multi-baris; plugin contoh, plugin baru,
plugin rusak (galat tertangkap), perintah plugin yang melempar galat. Folder plugin dialihkan ke folder uji.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_konsol_plugin.py
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", "terang")
st.remove("layout")
st.remove("sesi_terbuka")
OUT = Path("dev/uji/v095/plugin").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
from virmodock.core import plugin as P

P.FOLDER = OUT
(OUT / "halo.py").write_text('PLUGIN = {"nama": "Halo", "versi": "0.1", "keterangan": "uji"}\n'
                             'def pasang(vd):\n'
                             '    return [("Sapa", lambda: vd.pesan.tulis("Halo dari plugin")),\n'
                             '            ("Galat", lambda: 1 / 0)]\n', encoding="utf-8")
(OUT / "rusak.py").write_text("def pasang(vd):\n    return [\n", encoding="utf-8")

import virmodock.app as A
from PySide6.QtWidgets import QApplication

gagal = []


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
            s.resize(1500, 900)
            QTimer.singleShot(3500, s.l1)
            QTimer.singleShot(120000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            nama = {p.nama: p for p in s._plugin}
            cek("Halo" in nama and len(nama["Halo"].aksi) == 2, f"plugin dimuat: {list(nama)}")
            cek(bool(nama.get("rusak") and nama["rusak"].galat), "plugin rusak tertangkap: "
                + (nama.get("rusak").galat[:60] if nama.get("rusak") else "-"))
            cek((OUT / "_contoh_plugin.py").exists(), "contoh plugin dibuat")
            judul = [a.text() for a in s.m_plugin.actions()]
            cek(any("Halo" in t for t in judul) and "Muat ulang plugin" in judul, f"menu plugin: {judul}")
            p = nama["Halo"]
            P.jalankan(p, "Sapa", p.aksi[0][1], s.log.tulis)
            cek("Halo dari plugin" in s.pesan.toPlainText(), "perintah plugin berjalan")
            P.jalankan(p, "Galat", p.aksi[1][1], s.log.tulis)
            cek("ZeroDivisionError" in s.log.toPlainText(), "galat perintah plugin tertangkap (aplikasi tetap jalan)")
            # contoh plugin aktif setelah disalin tanpa awalan "_"
            shutil.copy(OUT / "_contoh_plugin.py", OUT / "ringkas.py")
            s.muat_plugin()
            cek(any(p.nama == "Ringkasan ΔG" and not p.galat for p in s._plugin), "plugin contoh dimuat ulang")
            # konsol
            s.buka_konsol()
            k = s.konsol
            for b in ("x = 6 * 7", "print(x)", "def f(a):", "    return a + 1", "", "print(f(x))",
                      "len(objek)", "1/0"):
                k.masuk.setText(b)
                k.kirim()
            t = k.keluar.toPlainText()
            cek("42" in t and "43" in t, "konsol: perintah & fungsi multi-baris")
            cek("ZeroDivisionError" in t, "konsol: galat ditampilkan, konsol tetap jalan")
            QApplication.processEvents()
            s.grab().save(str(OUT.parent / "gui_konsol.png"))
            print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
try:
    A.main()
except SystemExit:
    pass
