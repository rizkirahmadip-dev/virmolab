"""Panel Interaksi (daftar per jenis + saklar tampil) dan tab Diagram 2D."""
from PySide6.QtCore import QByteArray, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QHeaderView, QLabel, QPushButton, QToolBar,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core.laporan import id_angka
from ..core.analisis import KRITERIA, NAMA_JENIS, URUT_JENIS
from . import theme
from .panels import judul_seksi


TEKS_KOSONG = ("Belum ada pose yang dipilih. Setelah docking, klik dua kali baris di tab Hasil "
               "(atau pilih ligan/pose di panel Objek) untuk melihat interaksinya di sini.")


class PanelInteraksi(QWidget):
    jenisBerubah = Signal(set)          # jenis yang ditampilkan di viewport
    fokusResidu = Signal(dict)          # interaksi yang diklik
    opsiBerubah = Signal()

    def __init__(self):
        super().__init__()
        self.mode = "terang"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.judul = judul_seksi("Interaksi")
        lay.addWidget(self.judul)
        self.l_info = QLabel(TEKS_KOSONG)
        self.l_info.setObjectName("muted")
        self.l_info.setWordWrap(True)
        self.l_info.setContentsMargins(10, 6, 10, 6)
        lay.addWidget(self.l_info)
        g = QGridLayout()
        g.setContentsMargins(10, 2, 10, 6)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(4)
        self.cek = {}
        for i, j in enumerate(URUT_JENIS):
            cb = QCheckBox(NAMA_JENIS[j])
            cb.setChecked(j != "vdw")
            cb.toggled.connect(lambda *_: self.jenisBerubah.emit(self.jenis_tampil()))
            g.addWidget(cb, i // 2, i % 2)
            self.cek[j] = cb
        self.c_jarak = QCheckBox("Label jarak")
        self.c_jarak.setChecked(True)
        self.c_label = QCheckBox("Label residu")
        self.c_label.setChecked(True)
        self.c_stick = QCheckBox("Residu sebagai stick")
        self.c_stick.setChecked(True)
        n = len(URUT_JENIS)
        baris0 = (n + 1) // 2 + 1                      # satu baris kosong sebagai pemisah
        for i, c in enumerate((self.c_jarak, self.c_label, self.c_stick)):
            c.toggled.connect(lambda *_: self.opsiBerubah.emit())
            g.addWidget(c, baris0 + i // 2, i % 2)       # grid 2 kolom: tidak saling tumpuk di panel sempit
        g.setRowMinimumHeight(baris0 - 1, 4)
        self.w_opsi = QWidget()
        self.w_opsi.setLayout(g)
        lay.addWidget(self.w_opsi)
        self.pohon = QTreeWidget()
        self.pohon.setColumnCount(3)
        self.pohon.setHeaderLabels(["Interaksi", "Jarak (Å)", "Sudut"])
        self.pohon.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.pohon.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pohon.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.pohon.setIndentation(12)
        self.pohon.itemClicked.connect(self._klik)
        self.pohon.itemDoubleClicked.connect(self._klik)
        lay.addWidget(self.pohon, 1)
        k = KRITERIA
        cat = QLabel(f"Kriteria: ikatan H D···A ≤ {k['hbond_da']} Å, H···A ≤ {k['hbond_ha']} Å, sudut ≥ "
                     f"{k['hbond_sudut']:.0f}°; hidrofobik ≤ {k['hidrofobik']} Å; π-π ≤ {k['pi']} Å; π-kation ≤ "
                     f"{k['pikation']} Å; garam ≤ {k['garam']} Å; halogen ≤ {k['halogen']} Å, ≥ "
                     f"{k['halogen_sudut']:.0f}°; logam ≤ {k['logam']} Å; vdW ≤ {k['vdw']} Å.")
        cat.setObjectName("muted")
        cat.setWordWrap(True)
        cat.setContentsMargins(10, 4, 10, 6)
        lay.addWidget(cat)
        self.w_detail = [self.w_opsi, self.pohon, cat]
        self._tampil_detail(False)

    def _tampil_detail(self, on):
        for w in self.w_detail:
            w.setVisible(on)

    def jenis_tampil(self):
        return {j for j, c in self.cek.items() if c.isChecked()}

    def muat(self, judul, daftar):
        t = theme.TOKEN[self.mode]
        warna = theme.INTERAKSI
        self.judul.setText(f"INTERAKSI · {judul}".upper())
        self._tampil_detail(True)
        self.pohon.clear()
        n = {}
        for h in daftar:
            n[h["jenis"]] = n.get(h["jenis"], 0) + 1
        self.l_info.setText(", ".join(f"{NAMA_JENIS[j]} {n[j]}" for j in URUT_JENIS if j in n) or
                            "Tidak ada interaksi dalam kriteria.")
        for j in URUT_JENIS:
            item = [h for h in daftar if h["jenis"] == j]
            if not item:
                continue
            g = QTreeWidgetItem(self.pohon, [f"{NAMA_JENIS[j]} ({len(item)})", "", ""])
            g.setForeground(0, QColor(warna.get(j, t["ink"])))
            f = g.font(0)
            f.setBold(True)
            g.setFont(0, f)
            for h in item:
                teks = h["residu"] + (f" · {h['atom_p']}" if h["atom_p"] and j not in ("pi",) else "")
                c = QTreeWidgetItem(g, [teks, id_angka(f"{h['jarak']:.2f}"), f"{h['sudut']:.0f}°" if h.get("sudut") else ""])
                c.setToolTip(0, teks + (f" · {h['sub']}" if h.get("sub") else ""))
                c.setData(0, Qt.UserRole, h)
                c.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                c.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            g.setExpanded(j != "vdw")

    def kosong(self):
        self.pohon.clear()
        self.judul.setText("INTERAKSI")
        self.l_info.setText(TEKS_KOSONG)
        self._tampil_detail(False)

    def _klik(self, it, _k):
        h = it.data(0, Qt.UserRole)
        if h:
            self.fokusResidu.emit(h)


class KanvasSvg(QWidget):
    """Menampilkan SVG dengan rasio tetap (QSvgRenderer)."""

    def __init__(self):
        super().__init__()
        self.r = QSvgRenderer(self)
        self.latar = QColor("#ffffff")
        self.setMinimumSize(300, 240)

    def set_svg(self, teks):
        self.r.load(QByteArray(teks.encode("utf-8")) if teks else QByteArray())
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), self.latar)
        if not self.r.isValid():
            return
        p.setRenderHint(QPainter.Antialiasing)
        s = self.r.defaultSize()
        k = min(self.width() / max(1, s.width()), self.height() / max(1, s.height()))
        w, h = s.width() * k, s.height() * k
        self.r.render(p, QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h))
        p.end()


class TabDiagram(QWidget):
    minta = Signal()           # gambar ulang (opsi berubah)
    ekspor = Signal(str)       # salin | svg | png

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QToolBar()
        self.c_vdw = QCheckBox("Kontak van der Waals")
        self.c_vdw.setChecked(True)
        self.c_vdw.toggled.connect(self.minta)
        self.c_jarak = QCheckBox("Label jarak")
        self.c_jarak.setChecked(True)
        self.c_jarak.toggled.connect(self.minta)
        bar.addWidget(self.c_vdw)
        bar.addWidget(QLabel("   "))
        bar.addWidget(self.c_jarak)
        sp = QWidget()
        sp.setSizePolicy(sp.sizePolicy().horizontalPolicy().Expanding, sp.sizePolicy().verticalPolicy().Preferred)
        bar.addWidget(sp)
        for k, t in (("salin", "Salin"), ("svg", "Simpan SVG…"), ("png", "Simpan PNG/TIFF…")):
            b = QPushButton(t)
            b.clicked.connect(lambda _=False, k=k: self.ekspor.emit(k))
            bar.addWidget(b)
        lay.addWidget(bar)
        self.kanvas = KanvasSvg()
        lay.addWidget(self.kanvas, 1)
        self.l_kosong = QLabel("Belum ada diagram. Pilih pose atau ligan, lalu buka tab ini.")
        self.l_kosong.setObjectName("muted")
        self.l_kosong.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.l_kosong)
        self.svg = ""

    def tampil(self, svg, latar):
        self.svg = svg
        self.kanvas.latar = QColor(latar)
        self.kanvas.set_svg(svg)
        self.l_kosong.setVisible(not svg)
