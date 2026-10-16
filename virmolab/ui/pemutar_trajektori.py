"""Bilah pemutar trajektori MD di bawah viewport 3D.

Trajektori (PDB multi-MODEL) dimuat ke viewer sekali; bilah ini memilih bingkai lewat VM.filmKe() sehingga
pengguna bisa memutar, menjeda, menggeser ke waktu tertentu, dan mengatur kecepatan. Objek lain disembunyikan
selama film tampil dan dikembalikan saat film ditutup.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QSlider, QToolButton

from ..core.laporan import id_angka

ID_FILM = "film-trajektori"
KECEPATAN = (("0,5×", 200), ("1×", 100), ("2×", 50), ("4×", 25))


class PemutarTrajektori(QFrame):
    def __init__(self, jw):
        super().__init__()
        self.jw = jw
        self.setObjectName("bilahPemutar")
        self.waktu = []
        self.i = 0
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(8)
        self.l_judul = QLabel()
        self.l_judul.setObjectName("muted")
        self.b_putar = QToolButton()
        self.b_putar.setText("▶")
        self.b_putar.setToolTip("Putar / jeda (Spasi)")
        self.b_putar.setFixedWidth(30)
        self.b_putar.clicked.connect(self.putar_jeda)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self.ke)
        self.l_waktu = QLabel()
        self.l_waktu.setObjectName("mono")
        self.l_waktu.setMinimumWidth(150)
        self.cb_cepat = QComboBox()
        for t, ms in KECEPATAN:
            self.cb_cepat.addItem(t, ms)
        self.cb_cepat.setCurrentIndex(1)
        self.cb_cepat.setToolTip("Kecepatan putar")
        self.cb_cepat.currentIndexChanged.connect(lambda *_: self.timer.setInterval(self.cb_cepat.currentData()))
        b_tutup = QToolButton()
        b_tutup.setText("✕")
        b_tutup.setToolTip("Tutup trajektori dan tampilkan kembali objek lain")
        b_tutup.clicked.connect(self.tutup)
        for w in (self.l_judul, self.b_putar):
            h.addWidget(w)
        h.addWidget(self.slider, 1)
        for w in (self.l_waktu, self.cb_cepat, b_tutup):
            h.addWidget(w)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._maju)
        self.setVisible(False)

    def muat(self, teks_pdb, waktu_ns, judul=""):
        """teks_pdb: PDB multi-MODEL; waktu_ns: waktu tiap bingkai (panjang sama dengan jumlah MODEL)."""
        self.timer.stop()
        self.waktu = list(waktu_ns)
        self.l_judul.setText(judul)
        self.jw.tab_tengah.setCurrentWidget(self.jw.w_view)
        # garis & label interaksi pose aktif berada di kerangka koordinat lain: jangan melayang di atas film
        self.jw.viewer.js("interaksi", [], {})
        a = getattr(self.jw, "_aktif_inter", None)
        if a:
            self.jw.viewer.js("residuKontak", a["rec"], None)
        self.jw.viewer.js("filmMuat", ID_FILM, teks_pdb, cb=self._siap)

    def _siap(self, n):
        n = int(n or 1)
        if len(self.waktu) != n:
            self.waktu = self.waktu[:n] + [None] * max(0, n - len(self.waktu))
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, n - 1))
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.i = 0
        self._label()
        self.setVisible(True)
        self.putar_jeda(True)

    def _label(self):
        n = self.slider.maximum() + 1
        t = self.waktu[self.i] if self.i < len(self.waktu) else None
        self.l_waktu.setText((f"t = {id_angka(f'{t:.2f}')} ns · " if t is not None else "") + f"{self.i + 1}/{n}")

    def ke(self, i):
        self.i = int(i)
        self.jw.viewer.js("filmKe", self.i)
        self._label()

    def _maju(self):
        n = self.slider.maximum() + 1
        self.slider.setValue((self.i + 1) % n)

    def putar_jeda(self, putar=None):
        jalan = self.timer.isActive() if putar is None else not putar
        if jalan:
            self.timer.stop()
            self.b_putar.setText("▶")
        else:
            self.timer.start(self.cb_cepat.currentData())
            self.b_putar.setText("⏸")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space:
            self.putar_jeda()
            return
        super().keyPressEvent(e)

    def tutup(self):
        self.timer.stop()
        self.jw.viewer.js("filmHapus", ID_FILM)
        self.setVisible(False)
        if getattr(self.jw, "_aktif_inter", None):
            self.jw._tampilkan_interaksi()
