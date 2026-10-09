"""Jendela Komposer figur: susun beberapa panel (grafik, diagram 2D, BOILED-Egg, statistik, gambar 3D,
berkas gambar) menjadi satu figur berlabel A/B/C. Non-modal: tab lain tetap bisa dipakai sambil menambah panel.
"""
import base64

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QSplitter, QToolButton, QVBoxLayout, QWidget)

from ..core import komposer as K
from .panel_interaksi import KanvasSvg

SUMBER = (("uji", "Grafik Uji & Grafik"), ("statistik", "Grafik Statistik"), ("diagram", "Diagram interaksi 2D"),
          ("sifat", "BOILED-Egg (Sifat ligan)"), ("3d", "Gambar viewport 3D"), ("berkas", "Berkas gambar (PNG/JPG/SVG)…"))
LEBAR_CETAK = ((85, "85 mm (satu kolom jurnal)"), (120, "120 mm (1,5 kolom)"), (174, "174 mm (dua kolom / halaman)"))


def ikon_panel(p, sisi=72):
    img = QImage(sisi, sisi, QImage.Format_ARGB32)
    img.fill(Qt.white)
    q = QPainter(img)
    q.setRenderHint(QPainter.Antialiasing)
    if p["jenis"] == "svg":
        r = QSvgRenderer(QByteArray(p["isi"].encode("utf-8")))
        s = r.defaultSize()
        k = min(sisi / max(1, s.width()), sisi / max(1, s.height()))
        w, h = s.width() * k, s.height() * k
        r.render(q, QRectF((sisi - w) / 2, (sisi - h) / 2, w, h))
    else:
        pm = QPixmap()
        pm.loadFromData(base64.b64decode(p["isi"]))
        pm = pm.scaled(sisi, sisi, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        q.drawPixmap((sisi - pm.width()) // 2, (sisi - pm.height()) // 2, pm)
    q.end()
    return QIcon(QPixmap.fromImage(img))


class DialogKomposer(QDialog):
    minta = Signal(str)          # sumber panel yang ingin ditambahkan (lihat SUMBER)
    ekspor = Signal(str)         # salin | svg | png
    berubah = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Komposer figur")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1180, 760)
        self.panel = []
        self.opsi = K.opsi_lengkap()
        self._diam = False
        lay = QVBoxLayout(self)
        bagi = QSplitter(Qt.Horizontal)
        kiri = QWidget()
        kl = QVBoxLayout(kiri)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.addWidget(QLabel("<b>Panel</b> <span style='color:#7b8698'>(seret untuk mengurutkan)</span>"))
        self.daftar = QListWidget()
        self.daftar.setIconSize(QSize(56, 56))
        self.daftar.setDragDropMode(QAbstractItemView.InternalMove)
        self.daftar.model().rowsMoved.connect(self._urut_diseret)
        self.daftar.currentRowChanged.connect(self._pilih)
        kl.addWidget(self.daftar, 1)
        bar = QHBoxLayout()
        b_tambah = QToolButton()
        b_tambah.setText("＋ Tambah ▾")
        b_tambah.setPopupMode(QToolButton.InstantPopup)
        m = QMenu(self)
        for k, t in SUMBER:
            m.addAction(t, lambda k=k: self.minta.emit(k))
        b_tambah.setMenu(m)
        bar.addWidget(b_tambah)
        for t, fn, tip in (("↑", lambda: self._geser(-1), "Naikkan"), ("↓", lambda: self._geser(1), "Turunkan"),
                           ("Hapus", self._hapus, "Hapus panel terpilih")):
            b = QPushButton(t)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            bar.addWidget(b)
        kl.addLayout(bar)
        f = QFormLayout()
        self.e_nama = QLineEdit()
        self.e_nama.setPlaceholderText("Nama panel")
        self.e_nama.editingFinished.connect(self._ganti_nama)
        f.addRow("Nama", self.e_nama)
        self.c_penuh = QCheckBox("Lebar penuh (satu baris sendiri)")
        self.c_penuh.toggled.connect(self._ganti_penuh)
        f.addRow("", self.c_penuh)
        kl.addLayout(f)
        kl.addSpacing(8)
        kl.addWidget(QLabel("<b>Tata letak</b>"))
        f = QFormLayout()
        self.s_kolom = QDoubleSpinBox()
        self.s_kolom.setRange(1, 4)
        self.s_kolom.setDecimals(0)
        self.s_jarak = QDoubleSpinBox()
        self.s_jarak.setRange(0, 120)
        self.s_jarak.setDecimals(0)
        self.s_jarak.setSingleStep(4)
        self.c_label = QComboBox()
        for k, t in K.LABEL.items():
            self.c_label.addItem(t, k)
        self.s_label = QDoubleSpinBox()
        self.s_label.setRange(10, 60)
        self.s_label.setDecimals(0)
        self.c_judul = QCheckBox("Tampilkan nama panel")
        self.c_seragam = QCheckBox("Samakan skala huruf antar grafik")
        self.c_seragam.setToolTip("Semua grafik diperkecil dengan faktor yang sama agar ukuran huruf seragam")
        self.c_lebar = QComboBox()
        for v, t in LEBAR_CETAK:
            self.c_lebar.addItem(t, v)
        f.addRow("Kolom", self.s_kolom)
        f.addRow("Jarak antar panel", self.s_jarak)
        f.addRow("Label", self.c_label)
        f.addRow("Ukuran label", self.s_label)
        f.addRow("", self.c_judul)
        f.addRow("", self.c_seragam)
        f.addRow("Lebar cetak", self.c_lebar)
        kl.addLayout(f)
        for w, k in ((self.s_kolom, "kolom"), (self.s_jarak, "jarak"), (self.s_label, "ukuran_label")):
            w.valueChanged.connect(lambda v, k=k: self._set(k, int(v)))
        self.c_label.currentIndexChanged.connect(lambda _i: self._set("label", self.c_label.currentData()))
        self.c_lebar.currentIndexChanged.connect(lambda _i: self._set("lebar_mm", self.c_lebar.currentData()))
        self.c_judul.toggled.connect(lambda v: self._set("judul_panel", v))
        self.c_seragam.toggled.connect(lambda v: self._set("seragam", v))
        bagi.addWidget(kiri)
        self.kanvas = KanvasSvg()
        bagi.addWidget(self.kanvas)
        bagi.setSizes([330, 850])
        lay.addWidget(bagi, 1)
        bawah = QHBoxLayout()
        self.l_info = QLabel()
        self.l_info.setObjectName("muted")
        bawah.addWidget(self.l_info, 1)
        for k, t in (("salin", "Salin"), ("svg", "Simpan SVG/PDF…"), ("png", "Simpan PNG/TIFF…")):
            b = QPushButton(t)
            b.clicked.connect(lambda _=False, k=k: self.ekspor.emit(k))
            bawah.addWidget(b)
        b = QPushButton("Tutup")
        b.clicked.connect(self.close)
        bawah.addWidget(b)
        lay.addLayout(bawah)
        self._isi_opsi()
        self.segarkan()

    # ------------------------------------------------------------ data
    def muat(self, d):
        d = d or {}
        self.panel = [dict(p) for p in d.get("panel") or [] if p.get("isi")]
        self.opsi = K.opsi_lengkap(d.get("opsi"))
        self._isi_opsi()
        self.segarkan()

    def ke_dict(self):
        return {"panel": self.panel, "opsi": self.opsi}

    def tambah(self, p):
        self.panel.append(p)
        self.segarkan(len(self.panel) - 1)
        self.berubah.emit()
        self.show()
        self.raise_()
        self.activateWindow()

    def svg(self):
        return K.susun(self.panel, self.opsi) if self.panel else ("", (0, 0))

    # ------------------------------------------------------------ tampilan
    def _isi_opsi(self):
        self._diam = True
        o = self.opsi
        self.s_kolom.setValue(o["kolom"])
        self.s_jarak.setValue(o["jarak"])
        self.s_label.setValue(o["ukuran_label"])
        self.c_label.setCurrentIndex(max(0, self.c_label.findData(o["label"])))
        self.c_judul.setChecked(bool(o["judul_panel"]))
        self.c_seragam.setChecked(bool(o["seragam"]))
        i = self.c_lebar.findData(o["lebar_mm"])
        self.c_lebar.setCurrentIndex(i if i >= 0 else 2)
        self._diam = False

    def segarkan(self, pilih=None):
        self._diam = True
        baris = self.daftar.currentRow() if pilih is None else pilih
        self.daftar.clear()
        for i, p in enumerate(self.panel):
            label = K.teks_label(self.opsi["label"], i)
            it = QListWidgetItem(ikon_panel(p), f"{label + '  ' if label else ''}{p.get('nama', 'Panel')}"
                                 + ("  · penuh" if p.get("penuh") else ""))
            it.setData(Qt.UserRole, i)
            self.daftar.addItem(it)
        self.daftar.setCurrentRow(min(baris, len(self.panel) - 1) if self.panel else -1)
        self._diam = False
        self._pilih(self.daftar.currentRow())
        s, (w, h) = self.svg()
        self.kanvas.set_svg(s)
        if self.panel:
            mm = self.opsi["lebar_mm"]
            self.l_info.setText(f"{len(self.panel)} panel · ukuran cetak {mm} × {mm * h / w:.0f} mm")
        else:
            self.l_info.setText("Belum ada panel. Klik ＋ Tambah, atau tombol ＋ Komposer di tab Uji & Grafik.")

    def _pilih(self, i):
        ada = 0 <= i < len(self.panel)
        self.e_nama.setEnabled(ada)
        self.c_penuh.setEnabled(ada)
        self.e_nama.blockSignals(True)
        self.c_penuh.blockSignals(True)
        self.e_nama.setText(self.panel[i].get("nama", "") if ada else "")
        self.c_penuh.setChecked(bool(self.panel[i].get("penuh")) if ada else False)
        self.e_nama.blockSignals(False)
        self.c_penuh.blockSignals(False)

    def _set(self, k, v):
        if self._diam:
            return
        self.opsi[k] = v
        self.segarkan()
        self.berubah.emit()

    def _ganti_nama(self):
        i = self.daftar.currentRow()
        if 0 <= i < len(self.panel) and self.e_nama.text().strip() != self.panel[i].get("nama"):
            self.panel[i]["nama"] = self.e_nama.text().strip()
            self.segarkan()
            self.berubah.emit()

    def _ganti_penuh(self, v):
        i = self.daftar.currentRow()
        if 0 <= i < len(self.panel):
            self.panel[i]["penuh"] = v
            self.segarkan()
            self.berubah.emit()

    def _geser(self, d):
        i = self.daftar.currentRow()
        j = i + d
        if 0 <= i < len(self.panel) and 0 <= j < len(self.panel):
            self.panel[i], self.panel[j] = self.panel[j], self.panel[i]
            self.segarkan(j)
            self.berubah.emit()

    def _urut_diseret(self, *_):
        if self._diam:
            return
        urut = [self.daftar.item(r).data(Qt.UserRole) for r in range(self.daftar.count())]
        self.panel = [self.panel[i] for i in urut]
        self.segarkan(self.daftar.currentRow())
        self.berubah.emit()

    def _hapus(self):
        i = self.daftar.currentRow()
        if 0 <= i < len(self.panel):
            del self.panel[i]
            self.segarkan(i)
            self.berubah.emit()
