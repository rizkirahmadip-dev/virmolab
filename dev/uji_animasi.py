"""Uji ekspor animasi 3D (putar GIF, goyang WebP, zoom folder PNG) di GUI. Keluaran -> dev/uji/animasi/.
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/uji_animasi.py
"""
import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", os.environ.get("VD_TEMA", "terang"))
st.remove("layout")
st.remove("sesi_terbuka")
OUT = Path("dev/uji/animasi").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
ASAL = sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1]
PROYEK = OUT / ASAL.name
shutil.copytree(ASAL, PROYEK)

import virmodock.app as A  # noqa: E402
from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QDesktopServices.openUrl = staticmethod(lambda *a: True)
gagal = []


def cek(nama, kondisi, detail=""):
    print(("OK   " if kondisi else "GAGAL") + f" {nama} {detail}", flush=True)
    if not kondisi:
        gagal.append(nama)


def hook():
    from virmodock.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1500, 900)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(480000, lambda: (print("TIMEOUT", flush=True), QApplication.quit()))

        def _galat(s, t):
            print("GALAT:", t, flush=True)
            gagal.append(str(t)[:80])

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(5000, s.l2)

        def l2(s):
            from virmodock.core import ekspor
            b = ekspor.baris_hasil(s.proyek)
            s.buka_pose(b[0]["job"], b[0]["lid"], 1)
            QTimer.singleShot(3500, s.l3)

        def l3(s):
            import time
            s.t0 = time.time()
            s.rekam_animasi({"jenis": "putar", "fmt": "gif", "durasi": 3, "fps": 15, "lebar": 640, "latar": "putih"},
                            str(OUT / "putar.gif"), selesai=s.l4)

        def l4(s, hasil):
            import time
            from PIL import Image
            im = Image.open(hasil)
            cek("GIF putar", im.n_frames == 45 and im.size[0] == 640,
                f"{im.n_frames} bingkai {im.size} {Path(hasil).stat().st_size / 1e6:.1f} MB {time.time() - s.t0:.0f} s")
            im.seek(0)
            a = im.convert("RGB").copy()
            im.seek(11)
            b = im.convert("RGB").copy()
            from PIL import ImageChops
            cek("bingkai berbeda (berputar)", ImageChops.difference(a, b).getbbox() is not None)
            a.save(OUT / "bingkai_0.png")
            b.save(OUT / "bingkai_11.png")
            s.rekam_animasi({"jenis": "goyang", "fmt": "webp", "durasi": 2, "fps": 10, "lebar": 480, "latar": "tema"},
                            str(OUT / "goyang.webp"), selesai=s.l5)

        def l5(s, hasil):
            from PIL import Image
            im = Image.open(hasil)
            cek("WebP goyang", getattr(im, "n_frames", 1) == 20, f"{im.n_frames} bingkai")
            s.rekam_animasi({"jenis": "zoom", "fmt": "png", "durasi": 1, "fps": 10, "lebar": 480, "latar": "putih"},
                            str(OUT / "zoom"), selesai=s.l6)

        def l6(s, hasil):
            f = sorted(Path(hasil).glob("*.png"))
            cek("PNG zoom", len(f) == 10, str(len(f)))
            s.grab().save(str(OUT / "jendela_sesudah.png"))   # viewport harus kembali normal
            import time
            s.t0 = time.time()
            s.rekam_animasi({"jenis": "sinema", "fmt": "png", "durasi": 12, "fps": 5, "latar": "putih", "lebar": 640},
                            str(OUT / "sinema"), selesai=s.l6b)

        def l6b(s, hasil):
            f = sorted(Path(hasil).glob("*.png"))
            cek("PNG sinema", len(f) == 60, str(len(f)))
            from PIL import Image
            pilih = [f[k] for k in (0, 10, 22, 40, 47, 53, 59)]
            ims = [Image.open(x).resize((320, 240)) for x in pilih]
            lembar = Image.new("RGB", (320 * 4 + 30, 240 * 2 + 10), "black")
            for k, im in enumerate(ims):
                lembar.paste(im, ((k % 4) * 330, (k // 4) * 250))
            lembar.save(str(OUT / "sinema_lembar.png"))
            import time
            s.t0 = time.time()
            s.rekam_animasi({"jenis": "sinema", "fmt": "mp4", "durasi": 10, "fps": 30, "resolusi": "fhd",
                             "latar": "putih", "lebar": 800}, str(OUT / "sinema_fhd.mp4"), selesai=s.l6c)

        def l6c(s, hasil):
            import time
            print(f"MP4 sinema FHD {Path(hasil).stat().st_size / 1e6:.1f} MB rekam {time.time() - s.t0:.0f} s", flush=True)
            s.t0 = time.time()
            s.rekam_animasi({"jenis": "putar", "fmt": "mp4", "durasi": 4, "fps": 30, "resolusi": "uhd",
                             "latar": "putih", "lebar": 800}, str(OUT / "putar_4k.mp4"), selesai=s.l7)

        def l7(s, hasil):
            import time
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QMediaMetaData, QMediaPlayer, QVideoSink
            s.dt = time.time() - s.t0
            s.pl, s.sink = QMediaPlayer(), QVideoSink()
            s.pl.setVideoSink(s.sink)
            s.frame = []

            def fr(v):
                if v.isValid() and not s.frame:
                    s.frame.append(v.toImage())
            s.sink.videoFrameChanged.connect(fr)
            s.pl.setSource(QUrl.fromLocalFile(hasil))
            s.pl.play()

            def lapor():
                md = s.pl.metaData()
                res = md.value(QMediaMetaData.Key.Resolution)
                mb = Path(hasil).stat().st_size / 1e6
                cek("MP4 4K", res is not None and (res.width(), res.height()) == (3840, 2160)
                    and abs(s.pl.duration() - 4000) < 200,
                    f"{res} {s.pl.duration()} ms {mb:.1f} MB rekam {s.dt:.0f} s")
                if s.frame:
                    s.frame[0].save(str(OUT / "bingkai_4k.png"))
                s.pl.stop()
                print("SEMUA LULUS" if not gagal else f"GAGAL: {gagal}", flush=True)
                QApplication.quit()
            QTimer.singleShot(3000, lapor)

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
