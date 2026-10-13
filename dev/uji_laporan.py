"""Uji laporan PDF / Word / HTML interaktif + Komposer (gambar 3D & grafik) di GUI.

Memakai salinan proyek terakhir dari dev/uji_alur.py. Keluaran ke dev/uji/laporan/.
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/uji_laporan.py
"""
import os
import shutil
import sys
import zipfile
from pathlib import Path
from xml.dom import minidom

from PySide6.QtCore import QSettings, QTimer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("tema", os.environ.get("VD_TEMA", "terang"))
st.remove("layout")
st.remove("sesi_terbuka")
OUT = Path("dev/uji/laporan").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
ASAL = sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1]
PROYEK = OUT / ASAL.name
shutil.copytree(ASAL, PROYEK)

import virmolab.app as A  # noqa: E402
from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))
QDesktopServices.openUrl = staticmethod(lambda *a: True)
gagal = []


def cek(nama, kondisi, detail=""):
    print(("OK   " if kondisi else "GAGAL") + f" {nama} {detail}", flush=True)
    if not kondisi:
        gagal.append(nama)


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(300000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _path(s, judul, nama, filter_):
            return str(OUT / nama)

        def _galat(s, t):
            print("GALAT:", t, flush=True)
            gagal.append("galat: " + str(t)[:80])

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(5000, s.l2)

        def l2(s):
            for fmt in ("pdf", "docx"):
                s._ekspor({"jenis": "laporan", "penulis": "Uji otomatis", "gambar": True, "fmt": fmt})
            QTimer.singleShot(9000, s.l3)

        def l3(s):
            s._ekspor({"jenis": "laporan", "penulis": "Uji otomatis", "gambar": True, "fmt": "html"})
            QTimer.singleShot(15000, s.l4)

        def l4(s):
            nama = s._nama_dasar() if hasattr(s, "_nama_dasar") else ""
            dasar = sorted(OUT.glob("*_laporan.*"))
            print("berkas:", [f"{f.name} {f.stat().st_size:,} B" for f in dasar], nama, flush=True)
            pdf = next((f for f in dasar if f.suffix == ".pdf"), None)
            cek("PDF", pdf and pdf.stat().st_size > 50_000)
            dx = next((f for f in dasar if f.suffix == ".docx"), None)
            ok = False
            if dx:
                with zipfile.ZipFile(dx) as z:
                    nama_isi = z.namelist()
                    for n in nama_isi:
                        if n.endswith((".xml", ".rels")):
                            minidom.parseString(z.read(n))       # XML harus valid
                    dok = z.read("word/document.xml").decode("utf-8")
                    ok = ("word/media/image1.png" in nama_isi and "word/media/image2.png" in nama_isi
                          and dok.count("<w:tbl>") >= 4 and "Validasi metode" in dok)
            cek("DOCX valid (XML, 2 gambar, ≥4 tabel)", ok)
            ht = next((f for f in dasar if f.suffix == ".html"), None)
            teks = ht.read_text(encoding="utf-8") if ht else ""
            cek("HTML interaktif", ht and "$3Dmol" in teks and '"sdf"' in teks and "data:image/png;base64" in teks,
                f"{len(teks):,} karakter")
            # komposer: grafik uji + gambar 3D
            s.uji.isi_contoh()
            s._komposer_tambah("uji")
            s._komposer_tambah("3d")
            QTimer.singleShot(4000, s.l5)

        def l5(s):
            k = s.komposer
            cek("komposer 2 panel", k and len(k.panel) == 2 and k.panel[1]["jenis"] == "png")
            s._ekspor_komposer("png")
            s._ekspor_komposer("svg")
            k.grab().save(str(OUT / "komposer.png"))
            cek("panel 3D tersimpan di proyek", any(PROYEK.joinpath("komposer").glob("*.png")))
            fig = list(OUT.glob("*_figur.*"))
            cek("figur PDF+TIFF", len(fig) == 2, str([f.name for f in fig]))
            print("SEMUA LULUS" if not gagal else f"GAGAL: {gagal}", flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
