"""Pusat Ekspor: satu dialog untuk gambar 3D, diagram 2D, struktur, tabel, laporan."""
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from ..core import paths
from ..core.ekspor import mm_ke_px

PRESET_3D = [("Layar ×2", None, None, None), ("Jurnal 1 kolom · 85 mm · 600 dpi", 85, None, 600),
             ("Jurnal 1,5 kolom · 120 mm · 600 dpi", 120, None, 600), ("Jurnal 2 kolom · 180 mm · 600 dpi", 180, None, 600),
             ("Slide 16:9 · 1920×1080", None, (1920, 1080), 150), ("Slide 4K · 3840×2160", None, (3840, 2160), 300),
             ("Poster · 300 mm · 300 dpi", 300, None, 300), ("Kustom", None, None, None)]
MAKS_PX = 16384   # > 4096 px dirender per ubin (mainwindow.UBIN_PX)


def _ket(t):
    l = QLabel(t)
    l.setObjectName("muted")
    l.setWordWrap(True)
    return l


class DialogEkspor(QDialog):
    minta = Signal(dict)

    def __init__(self, ukuran_viewport, ada_pose, parent=None, kategori=0):
        super().__init__(parent)
        self.setWindowTitle("Ekspor")
        self.resize(720, 460)
        self.st = paths.settings()
        self.vw, self.vh = ukuran_viewport
        lay = QVBoxLayout(self)
        tengah = QHBoxLayout()
        self.daftar = QListWidget()
        self.daftar.addItems(["Gambar 3D", "Diagram 2D", "Struktur molekul", "Tabel hasil", "Laporan PDF",
                              "Paket Supplementary"])
        self.daftar.setFixedWidth(170)
        self.stack = QStackedWidget()
        self.daftar.currentRowChanged.connect(self.stack.setCurrentIndex)
        tengah.addWidget(self.daftar)
        tengah.addWidget(self.stack, 1)
        lay.addLayout(tengah, 1)

        # ---- gambar 3D
        w = QWidget()
        f = QFormLayout(w)
        self.g_fmt = QComboBox()
        self.g_fmt.addItems(["PNG", "TIFF (LZW)", "TIFF (tanpa kompresi)", "JPEG", "WebP"])
        self.g_preset = QComboBox()
        for p in PRESET_3D:
            self.g_preset.addItem(p[0])
        self.g_mm = QDoubleSpinBox()
        self.g_mm.setRange(10, 2000)
        self.g_mm.setSuffix(" mm")
        self.g_mm.setValue(180)
        self.g_dpi = QSpinBox()
        self.g_dpi.setRange(72, 2400)
        self.g_dpi.setValue(600)
        self.g_dpi.setSuffix(" dpi")
        self.g_tinggi = QDoubleSpinBox()
        self.g_tinggi.setRange(0.1, 5)
        self.g_tinggi.setSingleStep(0.05)
        self.g_tinggi.setDecimals(3)
        self.g_tinggi.setValue(round(self.vh / max(1, self.vw), 3))
        self.g_tinggi.setToolTip("Tinggi/lebar. Bawaan = rasio viewport saat ini.")
        self.g_latar = QComboBox()
        self.g_latar.addItems(["Putih", "Sesuai tema viewport", "Transparan", "Hitam"])
        self.g_px = QLabel()
        self.g_px.setObjectName("mono")
        f.addRow("Format", self.g_fmt)
        f.addRow("Ukuran", self.g_preset)
        f.addRow("Lebar fisik", self.g_mm)
        f.addRow("Resolusi", self.g_dpi)
        f.addRow("Rasio tinggi/lebar", self.g_tinggi)
        f.addRow("Latar", self.g_latar)
        f.addRow("Hasil", self.g_px)
        f.addRow(_ket("Gambar dirender ulang pada resolusi penuh (bukan diperbesar), garis dan label ikut berskala. "
                      "Metadata DPI ditulis ke berkas agar ukuran fisik terbaca benar di Word/jurnal."))
        for x in (self.g_mm, self.g_dpi, self.g_tinggi):
            x.valueChanged.connect(self._px)
        self.g_preset.currentIndexChanged.connect(self._preset)
        self.stack.addWidget(w)

        # ---- diagram 2D
        w = QWidget()
        f = QFormLayout(w)
        self.d_fmt = QComboBox()
        self.d_fmt.addItems(["SVG (vektor)", "PDF (vektor)", "PNG", "TIFF (LZW)"])
        self.d_mm = QDoubleSpinBox()
        self.d_mm.setRange(20, 1000)
        self.d_mm.setValue(120)
        self.d_mm.setSuffix(" mm")
        self.d_dpi = QSpinBox()
        self.d_dpi.setRange(72, 2400)
        self.d_dpi.setValue(600)
        self.d_dpi.setSuffix(" dpi")
        self.d_vdw = QCheckBox("Sertakan kontak van der Waals")
        self.d_vdw.setChecked(True)
        self.d_trans = QCheckBox("Latar transparan")
        self.d_judul = QCheckBox("Judul (ligan, pose, ΔG)")
        self.d_judul.setChecked(True)
        f.addRow("Format", self.d_fmt)
        f.addRow("Lebar fisik", self.d_mm)
        f.addRow("Resolusi (raster)", self.d_dpi)
        f.addRow(self.d_vdw)
        f.addRow(self.d_trans)
        f.addRow(self.d_judul)
        f.addRow(_ket("SVG dan PDF bisa diedit di Inkscape, Illustrator, atau Word. Diagram dibuat untuk pose/ligan "
                      "yang sedang dipilih."))
        self.stack.addWidget(w)

        # ---- struktur
        w = QWidget()
        f = QFormLayout(w)
        self.s_jenis = QComboBox()
        self.s_jenis.addItem("Kompleks PDB · reseptor + pose aktif", "kompleks")
        self.s_jenis.addItem("Kompleks PDB · pose terbaik setiap ligan (folder)", "kompleks_semua")
        self.s_jenis.addItem("SDF bertag · pose terbaik setiap ligan", "sdf_terbaik")
        self.s_jenis.addItem("SDF bertag · semua pose ligan aktif", "sdf_pose")
        self.s_jenis.addItem("PDBQT · pose aktif", "pdbqt")
        f.addRow("Isi", self.s_jenis)
        f.addRow(_ket("SDF berisi tag ΔG, Ki, LE, klaster, RMSD, jumlah interaksi, SMILES — terbaca di DataWarrior, "
                      "KNIME, PyMOL. Kompleks PDB: ligan di rantai L (HETATM + CONECT) dengan REMARK hasil."))
        if not ada_pose:
            f.addRow(_ket("Pose aktif: pilih pose di panel Objek atau klik dua kali baris di tab Hasil."))
        self.stack.addWidget(w)

        # ---- tabel
        w = QWidget()
        f = QFormLayout(w)
        self.t_fmt = QComboBox()
        self.t_fmt.addItems(["Excel (.xlsx)", "CSV"])
        self.t_sep = QComboBox()
        self.t_sep.addItem("Titik koma ( ; ) — Excel Indonesia", ";")
        self.t_sep.addItem("Koma ( , )", ",")
        self.t_sep.addItem("Tab", "\t")
        self.t_dec = QComboBox()
        self.t_dec.addItem("Koma (12,34)", True)
        self.t_dec.addItem("Titik (12.34)", False)
        self.t_inter = QCheckBox("Sertakan lembar interaksi per ligan (XLSX)")
        self.t_inter.setChecked(True)
        f.addRow("Format", self.t_fmt)
        f.addRow("Pemisah CSV", self.t_sep)
        f.addRow("Desimal CSV", self.t_dec)
        f.addRow(self.t_inter)
        f.addRow(_ket("XLSX: lembar Ringkasan (skala warna ΔG, header beku, filter), Semua pose, Interaksi, "
                      "Parameter, Info. CSV memakai UTF-8 BOM agar Δ, µ, Å terbaca di Excel."))
        self.stack.addWidget(w)

        # ---- laporan
        w = QWidget()
        f = QFormLayout(w)
        self.l_penulis = QLineEdit(self.st.value("penulis", ""))
        self.l_penulis.setPlaceholderText("Nama / institusi (opsional)")
        self.l_gambar = QCheckBox("Sertakan gambar 3D dan diagram 2D ligan terbaik")
        self.l_gambar.setChecked(True)
        self.l_fmt = QComboBox()
        self.l_fmt.addItem("PDF (siap cetak)", "pdf")
        self.l_fmt.addItem("Word .docx (bisa disunting)", "docx")
        self.l_fmt.addItem("HTML interaktif (penjelajah 3D + tabel)", "html")
        i = self.l_fmt.findData(self.st.value("format_laporan", "pdf"))
        self.l_fmt.setCurrentIndex(max(0, i))
        f.addRow("Format", self.l_fmt)
        f.addRow("Penulis", self.l_penulis)
        f.addRow(self.l_gambar)
        f.addRow(_ket("Isi: validasi redocking, reseptor & preparasi, parameter dan perangkat, tabel 15 teratas, "
                      "gambar & interaksi ligan terbaik, metode singkat dengan kriteria interaksi, sitasi software. "
                      "HTML interaktif: satu berkas yang bisa dibuka offline di peramban — pose 3D 30 ligan teratas "
                      "(klik baris tabel), tabel lengkap yang bisa dicari & diurutkan, dan laporan lengkap."))
        self.stack.addWidget(w)

        # ---- paket Supplementary
        w = QWidget()
        f = QFormLayout(w)
        self.p_kompleks = QSpinBox()
        self.p_kompleks.setRange(0, 500)
        self.p_kompleks.setValue(20)
        self.p_kompleks.setSuffix(" ligan teratas")
        f.addRow("Kompleks PDB", self.p_kompleks)
        f.addRow(_ket("Satu berkas .zip untuk lampiran jurnal: README otomatis, reseptor (PDBQT, PDB bersih, laporan "
                      "preparasi, pKa, residu fleksibel), ligan PDBQT, pose terbaik & semua pose (SDF bertag ΔG, Ki, LE, "
                      "interaksi, MM/GBSA), kompleks PDB, tabel CSV, parameter tiap job (JSON), hasil MD & MM/GBSA, "
                      "versi perangkat lunak, dan checksum SHA-256."))
        self.stack.addWidget(w)

        bawah = QHBoxLayout()
        bawah.addStretch(1)
        b = QPushButton("Ekspor…")
        b.setObjectName("primary")
        b.clicked.connect(self._ekspor)
        t = QPushButton("Tutup")
        t.clicked.connect(self.reject)
        bawah.addWidget(b)
        bawah.addWidget(t)
        lay.addLayout(bawah)
        self.daftar.setCurrentRow(kategori)
        self._px()

    def _preset(self, i):
        _n, mm, px, dpi = PRESET_3D[i]
        if dpi:
            self.g_dpi.setValue(dpi)
        if mm:
            self.g_mm.setValue(mm)
        if px:
            self.g_mm.setValue(round(px[0] / dpi * 25.4, 1))
            self.g_tinggi.setValue(round(px[1] / px[0], 4))
        if i == 0:
            self.g_dpi.setValue(144)
            self.g_mm.setValue(round(self.vw * 2 / 144 * 25.4, 1))
            self.g_tinggi.setValue(round(self.vh / max(1, self.vw), 3))
        self._px()

    def ukuran_3d(self):
        w = mm_ke_px(self.g_mm.value(), self.g_dpi.value())
        return w, int(round(w * self.g_tinggi.value()))

    def _px(self, *_):
        w, h = self.ukuran_3d()
        teks = f"{w} × {h} px"
        if max(w, h) > MAKS_PX:
            teks += f"  — melebihi {MAKS_PX} px, akan dibatasi"
        elif max(w, h) > 4096:
            teks += "  — dirender per ubin (lebih lama)"
        self.g_px.setText(teks)

    def _ekspor(self):
        i = self.daftar.currentRow()
        self.st.setValue("penulis", self.l_penulis.text())
        if i == 0:
            fmt = ["png", "tif", "tif", "jpg", "webp"][self.g_fmt.currentIndex()]
            w, h = self.ukuran_3d()
            k = min(1.0, MAKS_PX / max(w, h))
            d = {"jenis": "gambar3d", "fmt": fmt, "lebar": int(w * k), "tinggi": int(h * k), "dpi": self.g_dpi.value(),
                 "kompresi": "raw" if self.g_fmt.currentIndex() == 2 else "tiff_lzw",
                 "latar": ["putih", "tema", "transparan", "hitam"][self.g_latar.currentIndex()]}
        elif i == 1:
            d = {"jenis": "diagram", "fmt": ["svg", "pdf", "png", "tif"][self.d_fmt.currentIndex()],
                 "mm": self.d_mm.value(), "dpi": self.d_dpi.value(), "vdw": self.d_vdw.isChecked(),
                 "transparan": self.d_trans.isChecked(), "judul": self.d_judul.isChecked()}
        elif i == 2:
            d = {"jenis": "struktur", "isi": self.s_jenis.currentData()}
        elif i == 3:
            d = {"jenis": "tabel", "fmt": "xlsx" if self.t_fmt.currentIndex() == 0 else "csv",
                 "sep": self.t_sep.currentData(), "koma": self.t_dec.currentData(), "interaksi": self.t_inter.isChecked()}
        elif i == 5:
            d = {"jenis": "paket", "n_kompleks": self.p_kompleks.value()}
        else:
            self.st.setValue("format_laporan", self.l_fmt.currentData())
            d = {"jenis": "laporan", "penulis": self.l_penulis.text().strip(), "gambar": self.l_gambar.isChecked(),
                 "fmt": self.l_fmt.currentData()}
        self.minta.emit(d)
