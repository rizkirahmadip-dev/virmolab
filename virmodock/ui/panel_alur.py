"""Alur kerja docking untuk pemula: daftar Langkah (kiri) + panel kerja per langkah (kanan).

  1 Protein  ->  2 Ligan  ->  3 Area docking  ->  4 Jalankan  ->  5 Hasil

DaftarLangkah menampilkan status tiap langkah (selesai / aktif / belum) dan memancarkan `dipilih(i)`.
PanelLangkah adalah QStackedWidget berisi satu halaman per langkah; tiap halaman punya judul, penjelasan
satu kalimat, tombol aksi utama, dan tautan "Berikutnya". Halaman 3 dan 4 memakai widget dari PanelDocking.
"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from . import icons, theme

SKEMA_ALUR = {
    "docking": {
        "nama": "Docking Molekuler",
        "langkah": [
            ("protein", "Protein", "rec"),
            ("ligan", "Ligan", "lig"),
            ("area", "Area docking", "box"),
            ("jalankan", "Jalankan", "play"),
            ("hasil", "Hasil", "table"),
        ],
    },
    "md": {
        "nama": "Dinamika Molekul (MD)",
        "langkah": [
            ("struktur", "Protein / Kompleks", "rec"),
            ("solvasi", "Solvasi & Ionisasi", "box"),
            ("parameter", "Parameter MD", "sliders"),
            ("simulasi", "Jalankan Simulasi", "play"),
            ("trajektori", "Analisis Trajektori", "chart"),
        ],
    },
    "screening": {
        "nama": "Penapisan Virtual",
        "langkah": [
            ("target", "Target Reseptor", "rec"),
            ("pustaka", "Pustaka Ligan", "lig"),
            ("filter_box", "Filter & Kotak", "box"),
            ("batch", "Penapisan Batch", "play"),
            ("tophits", "Dashboard Top Hits", "table"),
        ],
    },
    "ppi": {
        "nama": "Protein - Protein (PPI)",
        "langkah": [
            ("reseptor", "Protein Reseptor", "rec"),
            ("mitra", "Protein Mitra", "rec"),
            ("sasa", "Antarmuka (SASA)", "box"),
            ("dock_ppi", "Jalankan PPI", "play"),
            ("evaluasi", "Evaluasi Kompleks", "table"),
        ],
    },
    "fbdd": {
        "nama": "Desain Fragmen (FBDD)",
        "langkah": [
            ("kantong", "Kantong Aktif", "box"),
            ("fragmen", "Fragmen Awal", "lig"),
            ("rekayasa", "Growing / Linking", "plus"),
            ("evaluasi_sifat", "Skor QED / SAScore", "chart"),
            ("impor_analog", "Impor Analog", "table"),
        ],
    },
}

LANGKAH = SKEMA_ALUR["docking"]["langkah"]


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
    alurBerubah = Signal(str)

    def __init__(self):
        super().__init__()
        self.mode = "terang"
        self._alur_aktif = "docking"
        self.baris = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Dropdown Pemilih Alur Kerja (Clean, Native Qt, Konsisten dengan tema)
        self.cb_alur = QComboBox()
        self.cb_alur.setObjectName("pilihAlur")
        self.cb_alur.setFixedHeight(26)
        self.cb_alur.setToolTip("Pilih alur kerja komputasi: Docking, Dinamika Molekul (MD), Penapisan Virtual, PPI, atau Desain Fragmen")
        for k, info in SKEMA_ALUR.items():
            self.cb_alur.addItem(info["nama"], k)
        self.cb_alur.currentIndexChanged.connect(self._pada_alur_diganti)
        lay.addWidget(self.cb_alur)

        # Kontainer baris langkah dinamis
        self.w_baris = QWidget()
        self.lay_baris = QVBoxLayout(self.w_baris)
        self.lay_baris.setContentsMargins(0, 0, 0, 0)
        self.lay_baris.setSpacing(1)
        lay.addWidget(self.w_baris)

        self._bangun_baris()
        lay.addStretch(1)

    def _bangun_baris(self):
        while self.lay_baris.count():
            item = self.lay_baris.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.baris = []

        daftar = SKEMA_ALUR.get(self._alur_aktif, SKEMA_ALUR["docking"])["langkah"]
        for i, (_k, judul, _ik) in enumerate(daftar):
            b = _BarisLangkah(i, judul)
            b.clicked.connect(lambda _=False, i=i: self.pilih(i))
            self.lay_baris.addWidget(b)
            self.baris.append(b)

        if self.baris:
            self.baris[0].setChecked(True)
        self.segarkan()

    def _pada_alur_diganti(self):
        k = self.cb_alur.currentData()
        if k and k != self._alur_aktif:
            self.ganti_alur(k)

    def ganti_alur(self, k, kirim=True):
        if k not in SKEMA_ALUR:
            return
        self._alur_aktif = k
        idx = self.cb_alur.findData(k)
        if idx >= 0 and self.cb_alur.currentIndex() != idx:
            self.cb_alur.blockSignals(True)
            self.cb_alur.setCurrentIndex(idx)
            self.cb_alur.blockSignals(False)
        self._bangun_baris()
        if kirim:
            self.alurBerubah.emit(k)

    def alur_aktif(self):
        return self._alur_aktif

    def pilih(self, i, kirim=True):
        if 0 <= i < len(self.baris):
            self.baris[i].setChecked(True)
            self.segarkan()
            if kirim:
                self.dipilih.emit(i)

    def aktif(self):
        return next((i for i, b in enumerate(self.baris) if b.isChecked()), 0)

    def set_status(self, status):
        """status: list (status, keterangan) per langkah; status = selesai | belum."""
        for i, b in enumerate(self.baris):
            if i < len(status):
                b.status, b.ket = status[i][0], status[i][1]
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.isi)
        lay.addWidget(scroll, 1)
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
    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
    v.setContentsMargins(10, 8, 10, 6)
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
    """Halaman kerja per langkah untuk semua alur. Tombol memancarkan `aksi(kunci)`."""
    aksi = Signal(str)
    berikutnya = Signal(int)          # pindah ke langkah i

    def __init__(self, hal_area, hal_jalan):
        super().__init__()
        A = self._A
        self._alur_kini = "docking"
        self.halaman = {"docking": [], "md": [], "screening": [], "ppi": [], "fbdd": []}

        # ========================================================= 1. ALUR DOCKING
        self.s_protein = _status()
        isi_prot = _kolom(A("rcsb", _tombol("Ambil dari RCSB PDB…", ikon="import", tip="Unduh struktur dengan kode PDB, mis. 1HSG")),
                          A("alphafold", _tombol("Ambil dari AlphaFold DB…", ikon="import",
                                                 tip="Struktur prediksi lewat kode UniProt atau nama protein/gen")),
                          A("buka", _tombol("Buka berkas…", ikon="open", tip="PDB, CIF, PDBQT dari komputer")),
                          8, self.s_protein, 4,
                          A("reseptor", _tombol("Siapkan reseptor…", True, ikon="rec", tip=
                                                "Buang air/ligan, tambah hidrogen & muatan, simpan PDBQT")))
        self.halaman["docking"].append(self._tambah_ke_alur("docking", "Protein (reseptor)",
                                                            "Muat struktur protein target, lalu siapkan untuk docking.",
                                                            isi_prot, "Berikutnya: Ligan ›", 1))

        self.s_ligan = _status()
        isi_lig = _kolom(A("pubchem", _tombol("Ambil dari PubChem…", ikon="search", tip="Nama senyawa atau CID, bisa banyak sekaligus")),
                         A("smiles", _tombol("Dari SMILES…", ikon="smiles")),
                         A("pustaka", _tombol("Pustaka ligan / ChEMBL…", ikon="lig",
                                              tip="Obat disetujui, bahan alam COCONUT, ZINC; aktif dikenal dari ChEMBL")),
                         A("buka", _tombol("Buka berkas / folder…", ikon="open", tip="SDF, MOL2, PDB, PDBQT, SMILES; bisa seret-lepas")),
                         8, self.s_ligan, 4,
                         A("ligan", _tombol("Siapkan ligan…", True, ikon="lig", tip="Hidrogen, protonasi pH, 3D, minimisasi, PDBQT")))
        self.halaman["docking"].append(self._tambah_ke_alur("docking", "Ligan",
                                                            "Tambahkan senyawa yang ingin diuji (satu atau ratusan), lalu siapkan.",
                                                            isi_lig, "Berikutnya: Area docking ›", 2))

        self.halaman["docking"].append(self._tambah_ke_alur("docking", "Area docking",
                                                            "Tentukan bagian protein tempat ligan dicari (kotak biru di viewport).",
                                                            hal_area, "Berikutnya: Jalankan ›", 3))

        self.halaman["docking"].append(self._tambah_ke_alur("docking", "Jalankan docking",
                                                            "Pilih mesin dan ketelitian, lalu mulai. Aplikasi tetap bisa dipakai "
                                                            "selama docking berjalan.",
                                                            hal_jalan, None, 4))

        self.s_hasil = _status()
        isi_hasil = _kolom(self.s_hasil, 4,
                           A("tab_hasil", _tombol("Tabel hasil", ikon="table", tip="Peringkat ΔG semua ligan; klik dua kali untuk melihat pose")),
                           A("tab_diagram", _tombol("Diagram interaksi 2D", ikon="diagram")),
                           A("tab_sifat", _tombol("Sifat ligan && BOILED-Egg", ikon="lig")),
                           A("mpo", _tombol("MPO && Radar Chart…", ikon="chart", tip="Multi-Parameter Optimization dan grafik radar ligan")),
                           A("labplanner", _tombol("Wet-Lab Planner…", ikon="sliders", tip="Kalkulator pengujian in vitro dan denah pelat 96-well")),
                           A("tab_statistik", _tombol("Statistik && grafik", ikon="chart")),
                           A("tab_uji", _tombol("Uji statistik && grafik publikasi", ikon="chart",
                                                tip="Data uji lab → t-test/ANOVA/post-hoc, braket signifikansi, IC₅₀")),
                           8,
                           A("validasi", _tombol("Validasi redocking…", ikon="check", tip="Docking ulang ligan kristal; RMSD ≤ 2 Å = valid")),
                           A("ekspor", _tombol("Ekspor gambar / tabel / struktur…", ikon="dl")),
                           A("laporan", _tombol("Buat laporan…", True, ikon="report")))
        self.halaman["docking"].append(self._tambah_ke_alur("docking", "Hasil",
                                                            "Lihat peringkat, interaksi, dan buat laporan.",
                                                            isi_hasil, None, 0))

        # ========================================================= 2. ALUR MD
        isi_md0 = _kolom(A("buka", _tombol("Buka kompleks protein-ligan…", ikon="open", tip="PDB atau CIF kompleks")),
                         A("reseptor", _tombol("Siapkan struktur reseptor…", ikon="rec")),
                         8, self.s_protein)
        self.halaman["md"].append(self._tambah_ke_alur("md", "Protein / Kompleks",
                                                       "Gunakan kompleks hasil docking atau buka berkas kristal/krio-EM.",
                                                       isi_md0, "Berikutnya: Solvasi ›", 1))

        isi_md1 = _kolom(A("md", _tombol("Buka Pengaturan MD (OpenMM)…", True, ikon="sliders",
                                         tip="Atur kotak pelarut TIP3P eksplisit atau OBC2 implisit")),
                         A("buka", _tombol("Buka berkas pelarut kustom…", ikon="open")))
        self.halaman["md"].append(self._tambah_ke_alur("md", "Solvasi & Ionisasi",
                                                       "Bungkus kompleks dalam kotak air TIP3P atau model implisit OBC2 serta ion Na+/Cl-.",
                                                       isi_md1, "Berikutnya: Parameter MD ›", 2))

        isi_md2 = _kolom(A("md", _tombol("Atur Parameter Simulasi…", True, ikon="sliders",
                                         tip="Force field Amber14/OpenFF, panjang simulasi, dan integrasi")),
                         A("md", _tombol("Ukur kecepatan GPU", ikon="play", tip="Benchmark ns/hari GPU Anda")))
        self.halaman["md"].append(self._tambah_ke_alur("md", "Parameter MD",
                                                       "Pilih force field, termostat Langevin 300 K, dan panjang simulasi dalam nanodetik.",
                                                       isi_md2, "Berikutnya: Jalankan Simulasi ›", 3))

        isi_md3 = _kolom(A("md", _tombol("Buka && Jalankan Simulasi OpenMM…", True, ikon="play",
                                         tip="Mulai ekuilibrasi NVT/NPT dan produksi MD")),
                         A("md", _tombol("Buka folder trajektori", ikon="open")))
        self.halaman["md"].append(self._tambah_ke_alur("md", "Jalankan Simulasi",
                                                       "Simulasi berjalan di latar belakang dengan pencatatan checkpoint otomatis.",
                                                       isi_md3, "Berikutnya: Analisis Trajektori ›", 4))

        isi_md4 = _kolom(A("md", _tombol("Buka Grafik Trajektori && MM/GBSA…", True, ikon="chart",
                                         tip="Fluktuasi RMSD, RMSF residu, dan energi bebas ikatan")),
                         A("ekspor", _tombol("Ekspor data trajektori…", ikon="dl")))
        self.halaman["md"].append(self._tambah_ke_alur("md", "Analisis Trajektori",
                                                       "Tinjau stabilitas pose ligan, persistensi interaksi, dan peringkat MM/GBSA.",
                                                       isi_md4, None, 0))

        # ========================================================= 3. ALUR PENAPISAN VIRTUAL
        self.halaman["screening"].append(self.halaman["docking"][0])

        isi_scr1 = _kolom(A("pustaka", _tombol("Buka Pustaka Ligan / ChEMBL…", True, ikon="lig",
                                               tip="Akses jutaan molekul obat, bahan alam COCONUT, atau ZINC")),
                          A("pubchem", _tombol("Ambil dari PubChem…", ikon="search")),
                          A("buka", _tombol("Buka berkas multi-senyawa (SDF/SMILES)…", ikon="open")),
                          8, self.s_ligan, 4,
                          A("ligan", _tombol("Siapkan semua ligan…", ikon="lig")))
        self.halaman["screening"].append(self._tambah_ke_alur("screening", "Pustaka Senyawa",
                                                              "Kelola koleksi molekul uji untuk penapisan skala besar.",
                                                              isi_scr1, "Berikutnya: Filter & Kotak ›", 2))

        self.halaman["screening"].append(self.halaman["docking"][2])
        self.halaman["screening"].append(self.halaman["docking"][3])

        isi_scr4 = _kolom(A("penapisan", _tombol("Buka Dashboard Penapisan…", True, ikon="table",
                                                tip="Analisis top-hits, filter Lipinski, dan perankingan afinitas")),
                          A("tab_hasil", _tombol("Tabel hasil docking", ikon="table")),
                          A("mpo", _tombol("MPO && Radar Chart…", ikon="chart")),
                          A("laporan", _tombol("Buat laporan penapisan…", ikon="report")))
        self.halaman["screening"].append(self._tambah_ke_alur("screening", "Dashboard Top Hits",
                                                              "Peringkat pose dan identifikasi senyawa teratas (lead molecules).",
                                                              isi_scr4, None, 0))

        # ========================================================= 4. ALUR PPI
        isi_ppi0 = _kolom(A("rcsb", _tombol("Ambil reseptor dari RCSB PDB…", ikon="import")),
                          A("buka", _tombol("Buka berkas protein reseptor…", ikon="open")),
                          8,
                          A("reseptor", _tombol("Siapkan reseptor…", True, ikon="rec")))
        self.halaman["ppi"].append(self._tambah_ke_alur("ppi", "Protein Reseptor",
                                                        "Tentukan makromolekul target utama (reseptor).",
                                                        isi_ppi0, "Berikutnya: Protein Mitra ›", 1))

        isi_ppi1 = _kolom(A("rcsb", _tombol("Ambil mitra dari RCSB PDB…", ikon="import")),
                          A("buka", _tombol("Buka berkas protein mitra…", ikon="open")))
        self.halaman["ppi"].append(self._tambah_ke_alur("ppi", "Protein Mitra",
                                                        "Muat pasangan makromolekul yang akan dipelajari interaksinya.",
                                                        isi_ppi1, "Berikutnya: Antarmuka SASA ›", 2))

        isi_ppi2 = _kolom(A("ppi", _tombol("Analisis Luas Kontak && SASA…", True, ikon="box",
                                           tip="Hitung Solvent Accessible Surface Area dan residu antarmuka")))
        self.halaman["ppi"].append(self._tambah_ke_alur("ppi", "Antarmuka (SASA)",
                                                        "Identifikasi residu permukaan yang terekspos dan kontak intermolekul.",
                                                        isi_ppi2, "Berikutnya: Jalankan PPI ›", 3))

        isi_ppi3 = _kolom(A("ppi", _tombol("Buka Modul Docking PPI…", True, ikon="play",
                                           tip="Simulasi penataan dan docking protein-protein")))
        self.halaman["ppi"].append(self._tambah_ke_alur("ppi", "Jalankan PPI",
                                                        "Jalankan pencarian pose ikatan makromolekul-makromolekul.",
                                                        isi_ppi3, "Berikutnya: Evaluasi Kompleks ›", 4))

        isi_ppi4 = _kolom(A("ppi", _tombol("Evaluasi Kompleks PPI…", True, ikon="table",
                                           tip="Evaluasi energi antarmuka dan residu kunci (hotspots)")))
        self.halaman["ppi"].append(self._tambah_ke_alur("ppi", "Evaluasi Kompleks",
                                                        "Tinjau konformasi kompleks terbaik dan jembatan garam.",
                                                        isi_ppi4, None, 0))

        # ========================================================= 5. ALUR FBDD
        isi_fb0 = _kolom(A("kantong", _tombol("Deteksi Kantong (P2Rank)…", True, ikon="box",
                                             tip="Deteksi otomatis kantong aktif dan sub-pockets")),
                         A("buka", _tombol("Buka berkas reseptor…", ikon="open")))
        self.halaman["fbdd"].append(self._tambah_ke_alur("fbdd", "Kantong Aktif",
                                                         "Prediksi rongga pengikatan target untuk penempatan fragmen awal.",
                                                         isi_fb0, "Berikutnya: Fragmen Awal ›", 1))

        isi_fb1 = _kolom(A("fbdd", _tombol("Buka Rekayasa Fragmen (FBDD)…", True, ikon="lig",
                                           tip="Pilih fragmen awal di sub-pocket")),
                         A("smiles", _tombol("Dari SMILES fragmen…", ikon="smiles")),
                         A("pustaka", _tombol("Pustaka fragmen…", ikon="lig")))
        self.halaman["fbdd"].append(self._tambah_ke_alur("fbdd", "Fragmen Awal",
                                                         "Tentukan fragmen bermassa rendah (MW < 300) yang terikat pada sub-pocket.",
                                                         isi_fb1, "Berikutnya: Growing / Linking ›", 2))

        isi_fb2 = _kolom(A("fbdd", _tombol("Fragment Growing && Linking…", True, ikon="plus",
                                           tip="Kembangkan rantai samping atau tautkan dua fragmen (BRICS)")))
        self.halaman["fbdd"].append(self._tambah_ke_alur("fbdd", "Growing / Linking",
                                                         "Tumbuhkan cabang kimia atau sambungkan fragmen menjadi molekul utuh.",
                                                         isi_fb2, "Berikutnya: Skor Sifat ›", 3))

        isi_fb3 = _kolom(A("fbdd", _tombol("Evaluasi QED && SAScore…", True, ikon="chart",
                                           tip="Druglikeness dan kemudahan sintesis organik")),
                         A("tab_sifat", _tombol("Sifat fisikokimia ligan", ikon="lig")))
        self.halaman["fbdd"].append(self._tambah_ke_alur("fbdd", "Skor QED / SAScore",
                                                         "Saring hasil rekayasa berdasarkan druglikeness (QED) dan sintesis (SAScore).",
                                                         isi_fb3, "Berikutnya: Impor Analog ›", 4))

        isi_fb4 = _kolom(A("fbdd", _tombol("Impor Analog ke Proyek…", True, ikon="table",
                                           tip="Tambahkan calon senyawa baru ke proyek untuk divalidasi")),
                         A("tab_hasil", _tombol("Tabel hasil docking", ikon="table")))
        self.halaman["fbdd"].append(self._tambah_ke_alur("fbdd", "Impor Analog",
                                                         "Simpan senyawa baru langsung ke proyek untuk pengujian docking.",
                                                         isi_fb4, None, 0))

        # Tampilkan langkah awal docking
        self.setCurrentWidget(self.halaman["docking"][0])

    def _A(self, kunci, tombol):
        tombol.clicked.connect(lambda: self.aksi.emit(kunci))
        return tombol

    def _tambah_ke_alur(self, alur, judul, ket, isi, lanjut, target_langkah):
        h = _Halaman(judul, ket, isi, lanjut)
        if lanjut and target_langkah is not None:
            h.berikutnya.connect(lambda t=target_langkah: self.berikutnya.emit(t))
        self.addWidget(h)
        return h

    def pilih_langkah(self, alur, i):
        """Pindah ke langkah i dari alur kerja yang sedang aktif."""
        self._alur_kini = alur
        pages = self.halaman.get(alur, self.halaman["docking"])
        idx = max(0, min(i, len(pages) - 1))
        self.setCurrentWidget(pages[idx])

    def setCurrentIndex(self, i):
        """Kompatibilitas mundur dengan pemanggilan langsung setCurrentIndex."""
        self.pilih_langkah(self._alur_kini, i)

    def currentIndex(self):
        pages = self.halaman.get(self._alur_kini, self.halaman["docking"])
        w = self.currentWidget()
        if w in pages:
            return pages.index(w)
        return 0

    def set_mode(self, mode):
        """Ikon tombol: putih pada tombol utama, netral pada tombol biasa (aksen muncul saat disorot)."""
        t = theme.TOKEN[mode]
        for b, ik, utama in _SEMUA_TOMBOL:
            b.setIcon(icons.ikon(ik, "#ffffff" if utama else t["ink2"], t["acct"]))
            if not utama:
                b.setProperty("ikon_nama", ik)
                b.setProperty("ikon_warna", (t["ink2"], t["acct"]))
                b.installEventFilter(self)

    def eventFilter(self, obj, e):
        """Tukar warna ikon tombol saat tetikus masuk/keluar — aksen hanya pada yang sedang disorot."""
        from PySide6.QtCore import QEvent
        nama = obj.property("ikon_nama") if hasattr(obj, "property") else None
        if nama and e.type() in (QEvent.Enter, QEvent.Leave):
            diam, sorot = obj.property("ikon_warna")
            obj.setIcon(icons.ikon(nama, sorot if e.type() == QEvent.Enter else diam))
        return super().eventFilter(obj, e)

    def set_status(self, protein="", ligan="", hasil=""):
        self.s_protein.setText(protein)
        self.s_ligan.setText(ligan)
        self.s_hasil.setText(hasil)
