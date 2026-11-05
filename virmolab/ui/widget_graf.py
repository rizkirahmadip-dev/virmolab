"""Tampilan jaringan interaktif: geser, perbesar, klik simpul, sorot tetangga.

Melengkapi core.graf yang hanya menghasilkan SVG statis. Di sini graf digambar dengan QGraphicsScene
sehingga bisa ditelusuri: roda tetikus memperbesar, seret menggeser, klik memilih simpul dan memancarkan
`simpulDipilih`, dan simpul terpilih beserta tetangganya disorot sementara sisanya diredupkan.

Tiga hal yang menentukan keterbacaannya, semuanya hasil kesalahan yang pernah terlihat di layar:

1. Label berukuran tetap di layar (ItemIgnoresTransformations). Sebelumnya ukuran label ikut
   diperbesar fitInView, sehingga jaringan kecil menghasilkan tulisan raksasa yang menutupi grafnya.
2. Label dipilih, bukan diborong. Melabeli semua simpul membuat tulisan saling tumpuk sampai tidak
   satu pun terbaca; label kini diberikan menurut prioritas (simpul terpilih dan tetangganya, lalu
   derajat tertinggi) dan yang bertabrakan disembunyikan. Nama lengkap selalu ada di tooltip.
3. Label memakai lingkar warna latar supaya tetap terbaca saat melintasi tepi, sesuai aturan
   "surface ring" pada panduan visualisasi data.

Tata letak tetap dihitung core.graf.tata_letak (NetworkX) agar gambar di layar, SVG ekspor, dan GraphML
memakai koordinat yang sama.
"""
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPen, QTransform
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout, QLabel, QWidget)

from ..core import graf as M_graf

# Warna per lapisan jaringan farmakologi, dari palet aman buta warna Okabe-Ito. Diperiksa dengan
# validator palet: pita terang, lantai kroma, pemisahan CVD, dan lantai penglihatan normal semuanya lulus.
WARNA_JENIS = {
    "senyawa": "#e69f00",      # oranye — bahan uji
    "target": "#0072b2",       # biru — protein target
    "jalur": "#009e73",        # hijau — jalur biologis
    "penyakit": "#d55e00",     # merah bata — penyakit
    "": "#7b8698",
}
LABEL_JENIS = {"senyawa": "Senyawa", "target": "Target", "jalur": "Jalur", "penyakit": "Penyakit"}

MAKS_HURUF = 22          # nama lebih panjang dipotong; nama utuh tetap di tooltip
JARAK_LABEL = 3.0        # piksel layar antara tepi simpul dan tulisan
SELA_LABEL = 3.0         # piksel layar: dua label dianggap bertabrakan bila lebih dekat dari ini


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


class _Legenda(QWidget):
    """Keterangan warna yang mengambang di pojok tampilan; hanya jenis yang benar-benar ada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(8, 4, 8, 4)
        self._lay.setSpacing(12)

    def atur(self, jenis_jumlah: Dict[str, int], mode: str):
        while self._lay.count():
            w = self._lay.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        t = M_graf.TEMA_GRAF[mode]
        # Urutan tetap, bukan urutan kemunculan: warna mengikuti jenis, bukan peringkatnya.
        for jenis in ("senyawa", "target", "jalur", "penyakit", ""):
            n = jenis_jumlah.get(jenis, 0)
            if not n:
                continue
            # Bulatannya memakai warna seri, teksnya memakai warna tinta — identitas dibawa penanda,
            # bukan tulisan berwarna.
            baris = QLabel(f"<span style='color:{WARNA_JENIS.get(jenis, WARNA_JENIS[''])}'>●</span> "
                           f"<span style='color:{t['teks']}'>"
                           f"{LABEL_JENIS.get(jenis, jenis or 'lainnya')} {n}</span>")
            baris.setTextFormat(Qt.RichText)
            self._lay.addWidget(baris)
        self.setStyleSheet(f"background: {t['latar']}; border: 1px solid {t['tepi']}; border-radius: 4px;")
        self.adjustSize()
        self.setVisible(bool(self._lay.count()))


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
        self._halo: Dict[str, QGraphicsSimpleTextItem] = {}   # lapis bawah tiap label
        self._prioritas: List[str] = []   # urutan simpul yang paling pantas dapat label
        self._terpilih: Optional[str] = None
        self._tampilkan_label = True
        self._zoom = 1.0

        self.legenda = _Legenda(self)
        self.legenda.move(8, 8)
        self.legenda.hide()

        # Menata ulang label tiap piksel geseran terlalu mahal; ditunda sampai gerakan berhenti.
        self._tunda = QTimer(self)
        self._tunda.setSingleShot(True)
        self._tunda.setInterval(90)
        self._tunda.timeout.connect(self._tata_label)

    # ---------------------------------------------------------------- isi
    def set_graf(self, G, metode: str = "", mode: str = "terang", tampilkan_label: bool = True):
        """Gambar ulang seluruh jaringan. `G` boleh None atau kosong.

        metode kosong = pilih sendiri: Kamada-Kawai untuk graf kecil (persilangan tepi lebih sedikit,
        jarak antarsimpul lebih merata), spring untuk graf besar karena KK berbiaya O(n²).
        """
        self._G = G
        self._mode = mode if mode in ("terang", "gelap") else "terang"
        self._tampilkan_label = tampilkan_label
        s = self.scene()
        s.clear()
        self._simpul, self._tepi, self._label, self._halo = {}, [], {}, {}
        self._prioritas, self._terpilih = [], None
        t = M_graf.TEMA_GRAF[self._mode]
        self.setBackgroundBrush(QBrush(QColor(t["latar"])))
        if G is None or G.number_of_nodes() == 0:
            self.legenda.hide()
            kosong = s.addSimpleText("Jaringan belum dibangun.")
            kosong.setBrush(QBrush(QColor(t["teks"])))
            s.setSceneRect(kosong.boundingRect().adjusted(-40, -40, 40, 40))
            return

        if not metode:
            metode = "kk" if G.number_of_nodes() <= 60 else "spring"
        posisi = M_graf.tata_letak(G, metode=metode, benih=1)
        # Skala dinaikkan seiring jumlah simpul supaya kerapatannya tetap, bukan makin padat.
        skala = 30.0 * max(1.0, G.number_of_nodes() ** 0.5)
        titik = {n: QPointF(float(p[0]) * skala, -float(p[1]) * skala) for n, p in posisi.items()}

        pena_tepi = QPen(QColor(t["tepi"]))
        pena_tepi.setWidthF(1.1)
        pena_tepi.setCosmetic(True)       # tebal tepi tetap 1,1 px berapa pun perbesarannya
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
        font_label.setPointSizeF(max(7.5, font_label.pointSizeF() - 0.5))
        jumlah_jenis: Dict[str, int] = {}
        for n, d in G.nodes(data=True):
            if n not in titik:
                continue
            derajat = G.degree(n)
            jenis = d.get("jenis", "")
            jumlah_jenis[jenis] = jumlah_jenis.get(jenis, 0) + 1
            r = max(7.0, min(26.0, 7.0 + (derajat ** 0.5) * 3.2))
            warna = QColor(WARNA_JENIS.get(jenis, WARNA_JENIS[""]))
            item = _Simpul(n, dict(d), r, warna)
            item.setBrush(QBrush(warna))
            # Cincin warna latar, bukan garis tepi gelap: yang memisahkan simpul bertumpuk adalah
            # celah, bukan tinta tambahan.
            pena = QPen(QColor(t["stroke_simpul"]))
            pena.setWidthF(2.0)
            item.setPen(pena)
            item.setPos(titik[n])
            item.setToolTip(f"{d.get('label', n)}\n{LABEL_JENIS.get(jenis, jenis or 'simpul')} · "
                            f"{derajat} koneksi")
            s.addItem(item)
            self._simpul[n] = item

            penuh = str(d.get("label", n))
            potong = penuh if len(penuh) <= MAKS_HURUF else penuh[:MAKS_HURUF - 1] + "…"
            # Dua lapis: bayangan tebal berwarna latar di belakang, tulisan bersih di depan. Satu item
            # ber-pen tebal akan menggerus bentuk hurufnya sendiri karena goresan Qt berada di atas isian.
            lapis = []
            for halo in (True, False):
                it = QGraphicsSimpleTextItem(potong)
                it.setFont(font_label)
                # Ukuran tetap di layar: tanpa ini jaringan kecil menghasilkan tulisan raksasa setelah
                # dipaskan, dan jaringan besar menghasilkan tulisan yang tak terbaca.
                it.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
                if halo:
                    it.setBrush(QBrush(QColor(t["latar"])))
                    pena_halo = QPen(QColor(t["latar"]))
                    pena_halo.setWidthF(3.0)
                    pena_halo.setCosmetic(True)
                    it.setPen(pena_halo)
                    it.setZValue(2.9)
                else:
                    it.setBrush(QBrush(QColor(t["teks"])))
                    it.setPen(Qt.NoPen)
                    it.setZValue(3.0)
                it.setPos(titik[n])
                it.setVisible(False)      # ditentukan _tata_label()
                s.addItem(it)
                lapis.append(it)
            self._halo[n], self._label[n] = lapis[0], lapis[1]

        # Prioritas label: derajat tertinggi lebih dulu — simpul hub itulah yang dicari pembaca.
        self._prioritas = sorted(self._simpul, key=lambda n: (-G.degree(n), str(G.nodes[n].get("label", n))))
        # Legenda selalu ada bila lebih dari satu jenis simpul: identitas tidak boleh bergantung
        # pada pencocokan warna saja. Satu jenis saja tidak perlu kotak legenda.
        self.legenda.atur(jumlah_jenis if len(jumlah_jenis) > 1 else {}, self._mode)
        self.legenda.raise_()

        s.setSceneRect(s.itemsBoundingRect().adjusted(-30, -30, 30, 30))
        self.muat_penuh()

    def set_label(self, tampil: bool):
        self._tampilkan_label = tampil
        self._tata_label()

    # ---------------------------------------------------------------- penataan label
    def _tata_label(self):
        """Pilih label mana yang muncul: prioritas tinggi lebih dulu, yang bertabrakan disembunyikan.

        Perhitungan dilakukan di ruang layar karena label berukuran tetap di layar, sehingga apa yang
        bertabrakan bergantung pada perbesaran saat ini, bukan pada koordinat graf.
        """
        if self._G is None or not self._label:
            return
        if not self._tampilkan_label:
            for n in self._label:
                self._tampilkan(n, False)
            return

        skala = self.transform().m11() or 1.0
        fm = QFontMetricsF(next(iter(self._label.values())).font())
        tinggi = fm.height()
        terpakai: List[QRectF] = []
        area = QRectF(self.viewport().rect()).adjusted(-20, -20, 20, 20)

        # Simpul terpilih dan tetangganya selalu didahulukan: itu yang sedang dibaca pengguna.
        urut = list(self._prioritas)
        if self._terpilih and self._terpilih in self._simpul:
            dekat = [self._terpilih] + [n for n in self._G.neighbors(self._terpilih) if n in self._simpul]
            urut = dekat + [n for n in urut if n not in set(dekat)]

        for n in urut:
            teks, simpul = self._label.get(n), self._simpul.get(n)
            if teks is None or simpul is None:
                continue
            lebar = fm.horizontalAdvance(teks.text())
            pusat = self.mapFromScene(simpul.pos())
            atas = pusat.y() + simpul.r * skala + JARAK_LABEL
            kotak = QRectF(pusat.x() - lebar / 2.0, atas, lebar, tinggi)
            if not area.intersects(kotak):
                self._tampilkan(n, False)
                continue
            uji = kotak.adjusted(-SELA_LABEL, -SELA_LABEL, SELA_LABEL, SELA_LABEL)
            if any(uji.intersects(k) for k in terpakai):
                self._tampilkan(n, False)
                continue
            terpakai.append(kotak)
            # Transformasi item tetap berlaku walau transformasi tampilan diabaikan, jadi geseran ini
            # bersatuan piksel layar: label menggantung tepat di bawah lingkaran pada perbesaran apa pun.
            geser = QTransform.fromTranslate(-lebar / 2.0, simpul.r * skala + JARAK_LABEL)
            for it in (self._halo.get(n), teks):
                if it is not None:
                    it.setTransform(geser)
            self._tampilkan(n, True)

    def _tampilkan(self, nid: str, tampil: bool):
        """Nyalakan/matikan kedua lapis label (bayangan dan tulisan) sekaligus."""
        for it in (self._halo.get(nid), self._label.get(nid)):
            if it is not None:
                it.setVisible(tampil)

    def _jadwalkan_label(self):
        self._tunda.start()

    # ---------------------------------------------------------------- tampilan
    def muat_penuh(self):
        """Paskan seluruh jaringan ke dalam area tampilan."""
        if not self.scene() or self.scene().sceneRect().isEmpty():
            return
        self.resetTransform()
        self._zoom = 1.0
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        self._tata_label()

    def perbesar(self, faktor: float):
        baru = self._zoom * faktor
        if baru < self.ZOOM_MIN or baru > self.ZOOM_MAKS:
            return
        self._zoom = baru
        self.scale(faktor, faktor)
        self._jadwalkan_label()

    def wheelEvent(self, e):
        self.perbesar(1.18 if e.angleDelta().y() > 0 else 1 / 1.18)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._jadwalkan_label()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self._jadwalkan_label()

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
            for item in self._simpul.values():
                item.setOpacity(1.0)
                pena = QPen(QColor(t["stroke_simpul"]))
                pena.setWidthF(2.0)
                item.setPen(pena)
            for garis, _a, _b in self._tepi:
                garis.setOpacity(1.0)
                pena = QPen(QColor(t["tepi"]))
                pena.setWidthF(1.1)
                pena.setCosmetic(True)
                garis.setPen(pena)
            for n in self._label:
                for it in (self._halo.get(n), self._label.get(n)):
                    if it is not None:
                        it.setOpacity(1.0)
            self._tata_label()
            return

        tetangga = set(self._G.neighbors(nid)) | {nid}
        for n, item in self._simpul.items():
            dekat = n in tetangga
            item.setOpacity(1.0 if dekat else 0.15)
            pena = QPen(QColor(t["tepi_aktif"] if n == nid else t["stroke_simpul"]))
            pena.setWidthF(3.0 if n == nid else 2.0)
            item.setPen(pena)
        for garis, a, b in self._tepi:
            aktif = a in tetangga and b in tetangga and (a == nid or b == nid)
            garis.setOpacity(1.0 if aktif else 0.10)
            pena = QPen(QColor(t["tepi_aktif"] if aktif else t["tepi"]))
            pena.setWidthF(2.0 if aktif else 1.1)
            pena.setCosmetic(True)
            garis.setPen(pena)
        for n in self._label:
            buram = 1.0 if n in tetangga else 0.15
            for it in (self._halo.get(n), self._label.get(n)):
                if it is not None:
                    it.setOpacity(buram)
        self._tata_label()

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
