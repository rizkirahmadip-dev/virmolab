"""Tampilan jaringan interaktif: geser, perbesar, klik simpul, sorot tetangga.

Melengkapi core.graf yang hanya menghasilkan SVG statis. Di sini graf digambar dengan QGraphicsScene
sehingga bisa ditelusuri: roda tetikus memperbesar, seret menggeser, klik memilih simpul dan memancarkan
`simpulDipilih`, dan simpul terpilih beserta tetangganya disorot sementara sisanya diredupkan.

Tata letak tetap dihitung core.graf.tata_letak (NetworkX) agar gambar di layar, SVG ekspor, dan GraphML
memakai koordinat yang sama.
"""
from typing import Any, Dict, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsScene, QGraphicsSimpleTextItem,
                               QGraphicsView)

from ..core import graf as M_graf

# Warna per lapisan jaringan farmakologi. Dipilih dari palet aman buta warna (Okabe-Ito) dan
# bermakna sama di tema terang maupun gelap, seperti theme.INTERAKSI.
WARNA_JENIS = {
    "senyawa": "#e69f00",      # oranye — bahan uji
    "target": "#0072b2",       # biru — protein target
    "jalur": "#009e73",        # hijau — jalur biologis
    "penyakit": "#d55e00",     # merah bata — penyakit
    "": "#7b8698",
}
LABEL_JENIS = {"senyawa": "Senyawa", "target": "Target", "jalur": "Jalur", "penyakit": "Penyakit"}
MAKS_LABEL = 26          # huruf; lebih panjang dipotong agar tata letak tidak melar (nama utuh di tooltip)


class _Simpul(QGraphicsEllipseItem):
    """Lingkaran satu simpul. Menyimpan id simpul dan atributnya untuk tooltip dan pemilihan."""

    def __init__(self, nid: str, data: Dict[str, Any], r: float, warna: QColor):
        super().__init__(-r, -r, 2 * r, 2 * r)
        self.nid = nid
        self.data = data
        self.r = r
        self.warna = warna
        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        self.setCursor(Qt.PointingHandCursor)

    def hoverEnterEvent(self, e):
        self.setScale(1.18)
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self.setScale(1.0)
        super().hoverLeaveEvent(e)


class TampilanGraf(QGraphicsView):
    """Tampilan jaringan yang bisa ditelusuri.

    Sinyal:
      simpulDipilih(str, dict) — id simpul dan atributnya; dipancarkan juga dengan ("", {}) saat
      pengguna mengklik latar (pembatalan pilihan).
    """
    simpulDipilih = Signal(str, dict)

    ZOOM_MIN, ZOOM_MAKS = 0.15, 8.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumHeight(240)
        self.setObjectName("kanvas")

        self._G = None
        self._mode = "terang"
        self._simpul: Dict[str, _Simpul] = {}
        self._tepi = []                 # (item, a, b)
        self._label: Dict[str, QGraphicsSimpleTextItem] = {}
        self._terpilih: Optional[str] = None
        self._tampilkan_label = True
        self._zoom = 1.0

    # ---------------------------------------------------------------- isi
    def set_graf(self, G, metode: str = "spring", mode: str = "terang", tampilkan_label: bool = True):
        """Gambar ulang seluruh jaringan. `G` boleh None atau kosong."""
        self._G = G
        self._mode = mode if mode in ("terang", "gelap") else "terang"
        self._tampilkan_label = tampilkan_label
        s = self.scene()
        s.clear()
        self._simpul, self._tepi, self._label, self._terpilih = {}, [], {}, None
        t = M_graf.TEMA_GRAF[self._mode]
        self.setBackgroundBrush(QBrush(QColor(t["latar"])))
        if G is None or G.number_of_nodes() == 0:
            kosong = s.addSimpleText("Jaringan belum dibangun.")
            kosong.setBrush(QBrush(QColor(t["teks"])))
            f = kosong.font()
            f.setPointSizeF(f.pointSizeF() + 1)
            kosong.setFont(f)
            s.setSceneRect(kosong.boundingRect().adjusted(-40, -40, 40, 40))
            return

        posisi = M_graf.tata_letak(G, metode=metode, benih=1)
        skala = 26.0 * max(1.0, G.number_of_nodes() ** 0.5)
        titik = {n: QPointF(float(p[0]) * skala, -float(p[1]) * skala) for n, p in posisi.items()}

        pena_tepi = QPen(QColor(t["tepi"]))
        pena_tepi.setWidthF(1.1)
        pena_tepi.setCosmetic(True)
        for a, b, d in G.edges(data=True):
            if a not in titik or b not in titik:
                continue
            garis = QGraphicsLineItem(titik[a].x(), titik[a].y(), titik[b].x(), titik[b].y())
            garis.setPen(pena_tepi)
            garis.setZValue(1)
            skor = d.get("skor")
            if skor is not None:
                garis.setToolTip(f"{G.nodes[a].get('label', a)} – {G.nodes[b].get('label', b)}\n"
                                 f"skor: {str(skor).replace('.', ',')}")
            s.addItem(garis)
            self._tepi.append((garis, a, b))

        font_label = QFont()
        font_label.setPointSizeF(max(7.0, font_label.pointSizeF() - 1.0))
        for n, d in G.nodes(data=True):
            if n not in titik:
                continue
            derajat = G.degree(n)
            r = max(7.0, min(26.0, 7.0 + (derajat ** 0.5) * 3.2))
            warna = QColor(WARNA_JENIS.get(d.get("jenis", ""), WARNA_JENIS[""]))
            item = _Simpul(n, dict(d), r, warna)
            item.setBrush(QBrush(warna))
            pena = QPen(QColor(t["stroke_simpul"]))
            pena.setWidthF(1.4)
            item.setPen(pena)
            item.setPos(titik[n])
            jenis = LABEL_JENIS.get(d.get("jenis", ""), d.get("jenis", "") or "simpul")
            item.setToolTip(f"{d.get('label', n)}\n{jenis} · {derajat} koneksi")
            s.addItem(item)
            self._simpul[n] = item

            # Label dipotong: satu nama panjang (nama IUPAC senyawa bahan alam bisa 70 huruf) melebarkan
            # sceneRect sehingga seluruh jaringan ikut mengecil saat dipaskan. Nama utuh tetap di tooltip.
            penuh = str(d.get("label", n))
            teks = QGraphicsSimpleTextItem(penuh if len(penuh) <= MAKS_LABEL else penuh[:MAKS_LABEL - 1] + "…")
            teks.setFont(font_label)
            teks.setBrush(QBrush(QColor(t["teks"])))
            lebar = teks.boundingRect().width()
            teks.setPos(titik[n].x() - lebar / 2, titik[n].y() + r + 2)
            teks.setZValue(3)
            teks.setVisible(tampilkan_label)
            s.addItem(teks)
            self._label[n] = teks

        s.setSceneRect(s.itemsBoundingRect().adjusted(-40, -40, 40, 40))
        self.muat_penuh()

    def set_label(self, tampil: bool):
        self._tampilkan_label = tampil
        for t in self._label.values():
            t.setVisible(tampil)

    # ---------------------------------------------------------------- tampilan
    def muat_penuh(self):
        """Pas-kan seluruh jaringan ke dalam area tampilan."""
        if not self.scene() or self.scene().sceneRect().isEmpty():
            return
        self.resetTransform()
        self._zoom = 1.0
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

    def perbesar(self, faktor: float):
        baru = self._zoom * faktor
        if baru < self.ZOOM_MIN or baru > self.ZOOM_MAKS:
            return
        self._zoom = baru
        self.scale(faktor, faktor)

    def wheelEvent(self, e):
        self.perbesar(1.18 if e.angleDelta().y() > 0 else 1 / 1.18)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            item = self.itemAt(e.position().toPoint())
            while item is not None and not isinstance(item, _Simpul):
                item = item.parentItem()
            if isinstance(item, _Simpul):
                self.pilih(item.nid)
                self.simpulDipilih.emit(item.nid, item.data)
                return          # jangan mulai geser saat mengklik simpul
            self.pilih(None)
            self.simpulDipilih.emit("", {})
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.muat_penuh()
        super().mouseDoubleClickEvent(e)

    # ---------------------------------------------------------------- pemilihan
    def pilih(self, nid: Optional[str]):
        """Sorot satu simpul beserta tetangganya; None mengembalikan semua ke tampilan penuh."""
        self._terpilih = nid
        if self._G is None:
            return
        t = M_graf.TEMA_GRAF[self._mode]
        if nid is None or nid not in self._simpul:
            for n, item in self._simpul.items():
                item.setOpacity(1.0)
                pena = QPen(QColor(t["stroke_simpul"]))
                pena.setWidthF(1.4)
                item.setPen(pena)
            for garis, _a, _b in self._tepi:
                garis.setOpacity(1.0)
                pena = QPen(QColor(t["tepi"]))
                pena.setWidthF(1.1)
                pena.setCosmetic(True)
                garis.setPen(pena)
            for n, teks in self._label.items():
                teks.setOpacity(1.0)
                teks.setVisible(self._tampilkan_label)
            return

        tetangga = set(self._G.neighbors(nid)) | {nid}
        for n, item in self._simpul.items():
            dekat = n in tetangga
            item.setOpacity(1.0 if dekat else 0.18)
            pena = QPen(QColor(t["tepi_aktif"] if n == nid else t["stroke_simpul"]))
            pena.setWidthF(3.0 if n == nid else 1.4)
            item.setPen(pena)
        for garis, a, b in self._tepi:
            aktif = a in tetangga and b in tetangga and (a == nid or b == nid)
            garis.setOpacity(1.0 if aktif else 0.12)
            pena = QPen(QColor(t["tepi_aktif"] if aktif else t["tepi"]))
            pena.setWidthF(2.0 if aktif else 1.1)
            pena.setCosmetic(True)
            garis.setPen(pena)
        for n, teks in self._label.items():
            dekat = n in tetangga
            teks.setVisible(self._tampilkan_label or dekat)
            teks.setOpacity(1.0 if dekat else 0.18)

    def simpul_terpilih(self) -> Optional[str]:
        return self._terpilih

    def gambar_png(self, lebar: int = 1600) -> QImage:
        """Render tampilan saat ini ke QImage beresolusi tinggi (untuk ekspor gambar)."""
        s = self.scene()
        r = s.sceneRect()
        if r.isEmpty():
            r = QRectF(0, 0, 100, 100)
        tinggi = max(1, int(lebar * r.height() / max(r.width(), 1e-6)))
        img = QImage(lebar, tinggi, QImage.Format_ARGB32)
        img.fill(QColor(M_graf.TEMA_GRAF[self._mode]["latar"]))
        p = QPainter(img)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        s.render(p, QRectF(0, 0, lebar, tinggi), r)
        p.end()
        return img
