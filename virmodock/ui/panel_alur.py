"""Alur kerja docking untuk pemula: daftar Langkah (kiri) + panel kerja per langkah (kanan).

  1 Protein  ->  2 Ligan  ->  3 Area docking  ->  4 Jalankan  ->  5 Hasil

DaftarLangkah menampilkan status tiap langkah (selesai / aktif / belum) dan memancarkan `dipilih(i)`.
PanelLangkah adalah QStackedWidget berisi satu halaman per langkah; tiap halaman punya judul, penjelasan
satu kalimat, tombol aksi utama, dan tautan "Berikutnya". Halaman 3 dan 4 memakai widget dari PanelDocking.
"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from . import icons, theme

LANGKAH = [  # (kunci, judul, ikon)
    ("protein", "Protein", "rec"),
    ("ligan", "Ligan", "lig"),
    ("area", "Area docking", "box"),
    ("jalankan", "Jalankan", "play"),
    ("hasil", "Hasil", "table"),
]


class _BarisLangkah(QToolButton):
    """Satu baris langkah: lingkaran nomor/centang + judul + keterangan status."""

    def __init__(self, i, judul):
        super().__init__()
        self.i, self.judul, self.ket, self.status = i, judul, "", "belum"
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(38)
        self.setIconSize(QSize(18, 18))
        self.setObjectName("langkah")

    def segarkan(self, mode):
        t = theme.TOKEN[mode]
        if self.status == "selesai":
            self.setIcon(icons.ikon("check", t["ok"]))
        else:
            self.setIcon(icons.ikon_nomor(self.i + 1, t["acc"] if self.isChecked() else t["mut"]))
        self.setText(f"{self.judul}\n{self.ket}" if self.ket else self.judul)


class DaftarLangkah(QWidget):
    dipilih = Signal(int)

    def __init__(self):
        super().__init__()
        self.mode = "terang"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(1)
        self.baris = []
        for i, (_k, judul, _ik) in enumerate(LANGKAH):
            b = _BarisLangkah(i, judul)
            b.clicked.connect(lambda _=False, i=i: self.pilih(i))
            lay.addWidget(b)
            self.baris.append(b)
        lay.addStretch(1)
        self.baris[0].setChecked(True)

    def pilih(self, i, kirim=True):
        self.baris[i].setChecked(True)
        self.segarkan()
        if kirim:
            self.dipilih.emit(i)

    def aktif(self):
        return next(i for i, b in enumerate(self.baris) if b.isChecked())

    def set_status(self, status):
        """status: list (status, keterangan) per langkah; status = selesai | belum."""
        for b, (s, ket) in zip(self.baris, status):
            b.status, b.ket = s, ket
        self.segarkan()

    def segarkan(self):
        for b in self.baris:
            b.segarkan(self.mode)


class _Halaman(QWidget):
    """Kerangka halaman: judul, penjelasan, isi, tautan berikutnya."""
    berikutnya = Signal()

    def __init__(self, judul, ket, isi=None, lanjut=None):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        kepala = QWidget()
        kv = QVBoxLayout(kepala)
        kv.setContentsMargins(12, 10, 12, 8)
        kv.setSpacing(3)
        self.l_judul = QLabel(judul)
        self.l_judul.setObjectName("judulHalaman")
        kv.addWidget(self.l_judul)
        self.l_ket = QLabel(ket)
        self.l_ket.setObjectName("muted")
        self.l_ket.setWordWrap(True)
        kv.addWidget(self.l_ket)
        lay.addWidget(kepala)
        garis = QFrame()
        garis.setObjectName("garis")
        garis.setFixedHeight(1)
        lay.addWidget(garis)
        self.isi = isi or QWidget()
        lay.addWidget(self.isi, 1)
        self.b_lanjut = None
        if lanjut:
            kaki = QHBoxLayout()
            kaki.setContentsMargins(12, 6, 12, 10)
            kaki.addStretch(1)
            self.b_lanjut = QPushButton(lanjut)
            self.b_lanjut.setObjectName("tautan")
            self.b_lanjut.setCursor(Qt.PointingHandCursor)
            self.b_lanjut.clicked.connect(self.berikutnya)
            kaki.addWidget(self.b_lanjut)
            lay.addLayout(kaki)


_SEMUA_TOMBOL = []      # (tombol, nama ikon, utama) untuk diwarnai ulang saat tema berganti


def _tombol(teks, utama=False, tip=None, ikon=None):
    b = QPushButton(teks)
    if utama:
        b.setObjectName("primary")
        b.setMinimumHeight(32)
    else:
        b.setObjectName("aksiLangkah")
    if tip:
        b.setToolTip(tip)
    if ikon:
        b.setIconSize(QSize(16, 16))
        _SEMUA_TOMBOL.append((b, ikon, utama))
    return b


def _kolom(*widget, jarak=6):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(12, 10, 12, 6)
    v.setSpacing(jarak)
    for x in widget:
        if isinstance(x, int):
            v.addSpacing(x)
        else:
            v.addWidget(x)
    v.addStretch(1)
    return w


def _status():
    l = QLabel("")
    l.setWordWrap(True)
    l.setObjectName("statusLangkah")
    l.setTextFormat(Qt.RichText)
    return l


class PanelLangkah(QStackedWidget):
    """Halaman kerja per langkah. Tombol memancarkan `aksi(kunci)`; JendelaUtama yang mengerjakan."""
    aksi = Signal(str)
    berikutnya = Signal(int)          # pindah ke langkah i

    def __init__(self, hal_area, hal_jalan):
        super().__init__()
        A = self._A
        # 1 Protein
        self.s_protein = _status()
        isi = _kolom(A("rcsb", _tombol("Ambil dari RCSB PDB…", ikon="import", tip="Unduh struktur dengan kode PDB, mis. 1HSG")),
                     A("buka", _tombol("Buka berkas…", ikon="open", tip="PDB, CIF, PDBQT dari komputer")),
                     8, self.s_protein, 4,
                     A("reseptor", _tombol("Siapkan reseptor…", True, ikon="rec", tip=
                                           "Buang air/ligan, tambah hidrogen & muatan, simpan PDBQT")))
        self._tambah("Protein (reseptor)", "Muat struktur protein target, lalu siapkan untuk docking.", isi,
                     "Berikutnya: Ligan ›")
        # 2 Ligan
        self.s_ligan = _status()
        isi = _kolom(A("pubchem", _tombol("Ambil dari PubChem…", ikon="search", tip="Nama senyawa atau CID, bisa banyak sekaligus")),
                     A("smiles", _tombol("Dari SMILES…", ikon="smiles")),
                     A("buka", _tombol("Buka berkas / folder…", ikon="open", tip="SDF, MOL2, PDB, PDBQT, SMILES; bisa seret-lepas")),
                     8, self.s_ligan, 4,
                     A("ligan", _tombol("Siapkan ligan…", True, ikon="lig", tip="Hidrogen, protonasi pH, 3D, minimisasi, PDBQT")))
        self._tambah("Ligan", "Tambahkan senyawa yang ingin diuji (satu atau ratusan), lalu siapkan.", isi,
                     "Berikutnya: Area docking ›")
        # 3 Area
        self._tambah("Area docking", "Tentukan bagian protein tempat ligan dicari (kotak biru di viewport).",
                     hal_area, "Berikutnya: Jalankan ›")
        # 4 Jalankan
        self._tambah("Jalankan docking", "Pilih mesin dan ketelitian, lalu mulai. Aplikasi tetap bisa dipakai "
                                         "selama docking berjalan.", hal_jalan, None)
        # 5 Hasil
        self.s_hasil = _status()
        isi = _kolom(self.s_hasil, 4,
                     A("tab_hasil", _tombol("Tabel hasil", ikon="table", tip="Peringkat ΔG semua ligan; klik dua kali untuk melihat pose")),
                     A("tab_diagram", _tombol("Diagram interaksi 2D", ikon="diagram")),
                     A("tab_sifat", _tombol("Sifat ligan && BOILED-Egg", ikon="lig")),
                     A("tab_statistik", _tombol("Statistik && grafik", ikon="chart")),
                     A("tab_uji", _tombol("Uji statistik && grafik publikasi", ikon="chart",
                                          tip="Data uji lab → t-test/ANOVA/post-hoc, braket signifikansi, IC₅₀")),
                     8,
                     A("validasi", _tombol("Validasi redocking…", ikon="check", tip="Docking ulang ligan kristal; RMSD ≤ 2 Å = valid")),
                     A("ekspor", _tombol("Ekspor gambar / tabel / struktur…", ikon="dl")),
                     A("laporan", _tombol("Buat laporan PDF…", True, ikon="report")))
        self._tambah("Hasil", "Lihat peringkat, interaksi, dan buat laporan.", isi, None)

    def _A(self, kunci, tombol):
        tombol.clicked.connect(lambda: self.aksi.emit(kunci))
        return tombol

    def _tambah(self, judul, ket, isi, lanjut):
        h = _Halaman(judul, ket, isi, lanjut)
        i = self.count()
        h.berikutnya.connect(lambda: self.berikutnya.emit(i + 1))
        self.addWidget(h)

    def set_mode(self, mode):
        t = theme.TOKEN[mode]
        for b, ik, utama in _SEMUA_TOMBOL:
            b.setIcon(icons.ikon(ik, "#ffffff" if utama else t["acc"]))

    def set_status(self, protein="", ligan="", hasil=""):
        self.s_protein.setText(protein)
        self.s_ligan.setText(ligan)
        self.s_hasil.setText(hasil)
