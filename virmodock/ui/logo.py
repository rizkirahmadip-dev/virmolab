"""Logo VirmoDock (SVG vektor dari branding/) sebagai widget, menyesuaikan tema terang/gelap."""
from PySide6.QtCore import QRectF, QSize
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from ..core import paths


def berkas(gelap=False):
    return paths.PAKET / "aset" / ("logo_horizontal_putih.svg" if gelap else "logo_horizontal.svg")


class Logo(QWidget):
    """Logo horizontal; tinggi tetap, lebar mengikuti rasio SVG. gelap=None -> ikut palet aplikasi."""

    def __init__(self, tinggi=56, gelap=None, parent=None):
        super().__init__(parent)
        if gelap is None:
            gelap = self.palette().window().color().lightness() < 128
        self.r = QSvgRenderer(str(berkas(gelap)), self)
        s = self.r.defaultSize()
        self.rasio = s.width() / max(1, s.height())
        self.setFixedSize(QSize(int(tinggi * self.rasio), tinggi))

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.r.render(p, QRectF(0, 0, self.width(), self.height()))
        p.end()
