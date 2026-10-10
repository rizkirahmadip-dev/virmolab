"""Halaman sambutan di viewport saat belum ada struktur dimuat: pintu masuk yang jelas untuk pemula."""
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import icons, theme
from .logo import Logo


class _Ubin(QFrame):
    """Kartu aksi yang bisa diklik: ikon, judul, keterangan."""
    diklik = Signal()

    def __init__(self, ikon, judul, ket):
        super().__init__()
        self.setObjectName("ubin")
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.nama_ikon = ikon
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(12)
        self.l_ikon = QLabel()
        self.l_ikon.setFixedSize(24, 24)
        h.addWidget(self.l_ikon, 0, Qt.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(2)
        self.l_judul = QLabel(judul)
        self.l_judul.setObjectName("ubinJudul")
        self.l_ket = QLabel(ket)
        self.l_ket.setObjectName("muted")
        self.l_ket.setWordWrap(True)
        v.addWidget(self.l_judul)
        v.addWidget(self.l_ket)
        h.addLayout(v, 1)

    def warnai(self, mode):
        self.l_ikon.setPixmap(icons.pixmap(self.nama_ikon, theme.TOKEN[mode]["acc"], 22))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.diklik.emit()


class HalamanAwal(QWidget):
    aksi = Signal(str)        # rcsb | buka | proyek | terakhir | tutorial | panduan

    def __init__(self):
        super().__init__()
        self.setObjectName("halamanAwal")
        self.setAttribute(Qt.WA_StyledBackground)
        self.mode = "terang"
        luar = QVBoxLayout(self)
        luar.addStretch(2)
        kol = QWidget()
        kol.setMaximumWidth(620)
        v = QVBoxLayout(kol)
        v.setContentsMargins(24, 0, 24, 0)
        v.setSpacing(0)
        self.w_logo = QHBoxLayout()
        self.logo = Logo(46, gelap=False)
        self.w_logo.addWidget(self.logo)
        self.w_logo.addStretch(1)
        v.addLayout(self.w_logo)
        v.addSpacing(14)
        t = QLabel("Mulai docking")
        t.setObjectName("judulAwal")
        v.addWidget(t)
        k = QLabel("Muat protein target, tambahkan ligan, lalu ikuti langkah 1–5 di panel kiri. "
                   "Setiap langkah dijelaskan di panel kanan.")
        k.setObjectName("muted")
        k.setWordWrap(True)
        v.addWidget(k)
        v.addSpacing(18)
        g = QGridLayout()
        g.setSpacing(10)
        self.ubin = {}
        for i, (kunci, ikon, judul, ket) in enumerate((
                ("rcsb", "import", "Ambil protein dari RCSB", "Ketik kode PDB, mis. 1HSG atau 6LU7"),
                ("buka", "open", "Buka berkas", "PDB, CIF, PDBQT, SDF, MOL2, SMILES — atau seret ke jendela ini"),
                ("proyek", "folder", "Buka proyek", "Lanjutkan pekerjaan tersimpan (.vmd)"),
                ("terakhir", "rotate", "Proyek terakhir", ""))):
            u = _Ubin(ikon, judul, ket)
            u.diklik.connect(lambda k=kunci: self.aksi.emit(k))
            g.addWidget(u, i // 2, i % 2)
            self.ubin[kunci] = u
        g.setColumnStretch(0, 1)
        g.setColumnStretch(1, 1)
        v.addLayout(g)
        v.addSpacing(16)
        h = QHBoxLayout()
        h.setSpacing(16)
        for kunci, teks in (("templat", "Mulai dari templat / proyek contoh"), ("tur", "Tur aplikasi"),
                            ("tutorial", "Tutorial docking (PDF)"), ("panduan", "Panduan pengguna (F1)")):
            b = QPushButton(teks)
            b.setObjectName("tautan")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=kunci: self.aksi.emit(k))
            h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)
        baris = QHBoxLayout()
        baris.addStretch(1)
        baris.addWidget(kol, 10)
        baris.addStretch(1)
        luar.addLayout(baris)
        luar.addStretch(3)

    def set_terakhir(self, folder):
        u = self.ubin["terakhir"]
        ada = bool(folder) and Path(folder).exists()
        u.setVisible(ada)
        if ada:
            u.l_ket.setText(Path(folder).stem)
            u.setToolTip(str(folder))

    def set_mode(self, mode):
        self.mode = mode
        gelap = mode == "gelap"
        baru = Logo(46, gelap=gelap)
        self.w_logo.replaceWidget(self.logo, baru)
        self.logo.deleteLater()
        self.logo = baru
        for u in self.ubin.values():
            u.warnai(mode)
