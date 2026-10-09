"""Uji PerekamVideo tanpa GUI utama: 90 bingkai sintetis 4K @30 fps -> MP4, lalu dibaca balik (QMediaPlayer):
durasi, resolusi, codec. Keluaran dev/uji/video/.
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/uji_video.py [fhd|qhd|uhd]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PySide6.QtMultimedia import QMediaMetaData, QMediaPlayer, QVideoSink  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from virmodock.ui.perekam_video import RESOLUSI, PerekamVideo  # noqa: E402

KUNCI = sys.argv[1] if len(sys.argv) > 1 else "uhd"
W, H, _ = RESOLUSI[KUNCI]
OUT = Path("dev/uji/video").resolve()
OUT.mkdir(parents=True, exist_ok=True)
F = str(OUT / f"uji_{KUNCI}.mp4")
Path(F).unlink(missing_ok=True)
app = QApplication([])
N, FPS = 90, 30
rek = PerekamVideo(F, W, H, FPS)
t0 = time.time()
i = 0


def bingkai(n):
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    import random
    rnd = random.Random(n)
    for _ in range(400):      # konten rumit agar encoder benar-benar butuh bitrate
        p.setBrush(QColor.fromHsv(rnd.randrange(360), 160, 220))
        p.drawEllipse(rnd.randrange(W), rnd.randrange(H), 20 + rnd.randrange(H // 8), 20 + rnd.randrange(H // 8))
    p.setBrush(QColor("#2b6fd6"))
    p.drawEllipse(int(W * n / N), H // 3, H // 4, H // 4)
    p.setFont(QFont("Segoe UI", H // 30))
    p.drawText(40, H - 60, f"VirmoDock uji video {W}x{H} bingkai {n + 1}/{N}")
    p.end()
    return img


def lanjut():
    global i
    while i < N and rek.boleh_lagi():
        rek.kirim(bingkai(i))
        i += 1
    if i >= N:
        rek.akhiri()


def periksa(f):
    print(f"tulis {time.time() - t0:.1f} s, {Path(f).stat().st_size / 1e6:.1f} MB", flush=True)
    pl = QMediaPlayer()
    sink = QVideoSink()
    pl.setVideoSink(sink)
    ukuran = []
    sink.videoFrameChanged.connect(lambda fr: ukuran.append((fr.width(), fr.height())))
    pl.setSource(QUrl.fromLocalFile(f))
    pl.play()

    def lapor():
        md = pl.metaData()
        print("durasi ms", pl.duration(), "| bingkai", ukuran[:1], "| codec", md.stringValue(QMediaMetaData.Key.VideoCodec),
              "| bitrate", md.value(QMediaMetaData.Key.VideoBitRate), flush=True)
        res = md.value(QMediaMetaData.Key.Resolution)
        print("resolusi", res, flush=True)
        ok = res is not None and (res.width(), res.height()) == (W, H) and abs(pl.duration() - N * 1000 / FPS) < 200
        print("LULUS" if ok else "GAGAL", flush=True)
        app.quit()
    QTimer.singleShot(2500, lapor)


rek.siap_lagi.connect(lanjut)
rek.selesai.connect(periksa)
rek.galat.connect(lambda t: (print("GALAT", t, flush=True), app.quit()))
QTimer.singleShot(300, lanjut)
QTimer.singleShot(120000, lambda: (print("TIMEOUT"), app.quit()))
app.exec()
