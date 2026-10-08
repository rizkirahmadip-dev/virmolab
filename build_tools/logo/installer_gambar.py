"""Gambar wizard Inno Setup dari logo resmi -> installer/wizard_*.bmp (100 % dan 200 %)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtCore import QByteArray, QRectF  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

app = QGuiApplication.instance() or QGuiApplication(sys.argv)
AKAR = Path(__file__).resolve().parents[2]
B, I = AKAR / "branding", AKAR / "installer"
NAVY = "#173b6c"


def gambar(svg_berkas, w, h, latar, lebar_isi, y_rel=0.5):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(latar))
    r = QSvgRenderer(str(svg_berkas))
    s = r.defaultSize()
    rw = w * lebar_isi
    rh = rw * s.height() / s.width()
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p, QRectF((w - rw) / 2, h * y_rel - rh / 2, rw, rh))
    p.end()
    return img


for k in (1, 2):
    # panel kiri halaman sambutan/selesai: logo bertumpuk putih di atas navy
    gambar(B / "virmodock_logo_bertumpuk_putih.svg", 164 * k, 314 * k, NAVY, 0.86, 0.42).save(
        str(I / f"wizard_besar_{k}x.bmp"))
    # pojok kanan atas halaman lain: tanda saja
    gambar(B / "virmodock_tanda.svg", 55 * k, 55 * k, "#ffffff", 0.92).save(str(I / f"wizard_kecil_{k}x.bmp"))
print("ok")
