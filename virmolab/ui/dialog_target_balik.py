"""Dialog Penargetan Balik & Farmakologi Jaringan (F3 tahap a).

Menghubungkan ligan kueri ke target potensial melalui:
1. Profil kemiripan ligan 2D (ChEMBL, Morgan2/ECFP4)
2. Docking molekuler panel target terkurasi (Vina, z-skor empiris)
3. Konsensus Borda rank dan klasifikasi keyakinan

Peringatan Ilmiah (BCPT 2025):
"Hasil adalah hipotesis. Klaim mekanisme memerlukan uji eksperimen (pedoman BCPT 2025)."
"""
import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QByteArray, QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget
)

try:
    from rdkit import Chem
    from rdkit.Chem import Draw
except ImportError:
    Chem = None
    Draw = None

from ..core import catat, graf, jaringan, pengayaan, target_balik
from . import kit


class _UtasLigan(QThread):
    """Kueri ChEMBL di latar belakang agar jendela tidak membeku."""
    selesai = Signal(list, list, str)

    def __init__(self, smiles, organisme):
        super().__init__()
        self._smiles = smiles
        self._organisme = organisme

    def run(self):
        try:
            hasil, jejak = target_balik.jalur_ligan(self._smiles, k=5, organisme=self._organisme)
            self.selesai.emit(hasil, jejak, "")
        except target_balik.GalatTargetBalik as e:
            self.selesai.emit([], [], str(e))
        except Exception as e:
            self.selesai.emit([], [], f"Galat tak terduga pada jalur ligan: {e}")


class _KanvasGraf(QScrollArea):
    """Kanvas SVG graf: gulir untuk memperbesar, seret untuk menggeser."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignCenter)
        self._svg = QSvgWidget()
        self._dasar = (900, 620)
        self._zoom = 1.0
        self._seret = None
        self.setWidget(self._svg)
        self._svg.resize(*self._dasar)

    def tampilkan(self, svg: str, lebar: int, tinggi: int):
        self._dasar = (lebar, tinggi)
        self._svg.load(QByteArray(svg.encode("utf-8")))
        tersedia = self.viewport().size()
        self._zoom = max(0.3, min(1.0, min((tersedia.width() - 4) / lebar, (tersedia.height() - 4) / tinggi)))
        self._terapkan_zoom()

    def _terapkan_zoom(self):
        self._svg.resize(int(self._dasar[0] * self._zoom), int(self._dasar[1] * self._zoom))

    def wheelEvent(self, e):
        if self._svg.size().isEmpty():
            return
        self._zoom = max(0.3, min(4.0, self._zoom * (1.15 if e.angleDelta().y() > 0 else 1 / 1.15)))
        self._terapkan_zoom()
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._seret = e.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._seret is not None:
            d = e.position().toPoint() - self._seret
            self._seret = e.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._seret = None
        self.unsetCursor()
        super().mouseReleaseEvent(e)


class _UtasJaringan(QThread):
    """Ambil tepi STRING, asosiasi penyakit, dan versi basis data di latar belakang."""
    selesai = Signal(object, str)
    kabar = Signal(str)

    def __init__(self, gen, ambang_string, ambang_penyakit, pakai_ppi, pakai_penyakit, ambang_sensitivitas):
        super().__init__()
        self._a = (gen, ambang_string, ambang_penyakit, pakai_ppi, pakai_penyakit, ambang_sensitivitas)

    def run(self):
        gen, a_str, a_pen, pakai_ppi, pakai_pen, a_sens = self._a
        hasil = {"tepi": [], "penyakit": [], "jejak": [], "versi_string": "", "versi_ot": "", "tepi_per_ambang": {}}
        try:
            if pakai_ppi:
                self.kabar.emit("STRING: mengambil interaksi protein…")
                hasil["versi_string"], j = jaringan.versi_string()
                hasil["jejak"].append(j)
                for a in sorted({a_str} | set(a_sens or ())):
                    tepi, jk = jaringan.tepi_string(gen, a)
                    hasil["tepi_per_ambang"][a] = tepi
                    hasil["jejak"] += jk
                hasil["tepi"] = hasil["tepi_per_ambang"][a_str]
            if pakai_pen:
                self.kabar.emit("Open Targets: mengambil asosiasi penyakit…")
                hasil["versi_ot"], j = jaringan.versi_opentargets()
                hasil["jejak"].append(j)
                pen, jk = jaringan.tepi_penyakit(gen, a_pen, maks_per_target=5)
                hasil["penyakit"], hasil["jejak"] = pen, hasil["jejak"] + jk
            self.selesai.emit(hasil, "")
        except jaringan.GalatJaringan as e:
            self.selesai.emit(None, str(e))
        except Exception as e:
            self.selesai.emit(None, f"Galat tak terduga saat membangun jaringan: {e}")


class DialogTargetBalik(QDialog):
    """Dialog analisis penargetan balik dan farmakologi jaringan."""

    def __init__(self, parent=None, proyek=None):
        super().__init__(parent)
        self.jw = parent
        self.proyek = proyek if proyek is not None else getattr(parent, "proyek", None)

        self.setWindowTitle("Penargetan balik & jaringan")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1150, 740)

        self.kelas_aktif = (target_balik.daftar_kelas_panel() or [""])[0]
        self.hasil_gabungan: List[Dict[str, Any]] = []
        self.target_terpilih: Optional[Dict[str, Any]] = None
        self._sedang_berjalan = False
        self._analisis_aktif = False          # True setelah "Mulai" pada sesi dialog ini (hasil bisa dihitung ulang)
        self._hasil_ligan: List[Dict[str, Any]] = []
        self._jejak: List[Dict[str, Any]] = []
        self._lig_data: Dict[str, Any] = {}
        self._gen_terpilih: List[str] = []
        self._graf = None
        self._pengayaan: List[Dict[str, Any]] = []
        self._sens: Dict[str, Any] = {}
        self._info_jaringan: Dict[str, Any] = {}
        if getattr(parent, "pelaksana", None) is not None:
            parent.pelaksana.jobSelesai.connect(self._job_selesai)

        self._bangun_ui()
        self._muat_pilihan_senyawa()
        self._perbarui_estimasi()

        # Otomatis muat hasil bila ada data tersimpan di proyek
        if self.proyek and getattr(self.proyek, "target_balik", None):
            self._muat_riwayat_proyek()
        else:
            # Muat pratinjau panel awal
            self._isi_tabel_panel_awal()

    def _bangun_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        # Header judul & subjudul
        lay.addWidget(kit.judul(
            "Penargetan balik & jaringan",
            "Mencari target protein untuk senyawa melalui kemiripan ligan dan penambatan panel target"
        ))

        # Banner Peringatan Wajib BCPT 2025
        self.banner_peringatan = kit.catatan(
            "Hasil adalah hipotesis. Klaim mekanisme memerlukan uji eksperimen (pedoman BCPT 2025).",
            jenis="peringatan"
        )
        lay.addWidget(self.banner_peringatan)

        # Tab Widget
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # Tab 1: Penargetan balik
        w_tab1 = QWidget()
        self._bangun_tab_target_balik(w_tab1)
        self.tabs.addTab(w_tab1, "Penargetan balik")

        # Tab 2: Jaringan & jalur (Placeholder / persiapan P7)
        w_tab2 = QWidget()
        self._bangun_tab_jaringan(w_tab2)
        self.tabs.addTab(w_tab2, kit.amp("Jaringan & jalur"))

        # Bar bawah
        self.l_status = QLabel("")
        self.l_status.setObjectName("subjudul")

        btn_csv = kit.tombol("Ekspor CSV…", self._ekspor_csv, tip="Simpan tabel peringkat target ke berkas CSV")
        btn_metode = kit.tombol("Salin paragraf metode", self._salin_metode, tip="Salin deskripsi metode ilmiah ke papan klip")
        btn_ke_jaringan = kit.tombol("Kirim target terpilih ke Jaringan ›", self._ke_tab_jaringan,
                                     tip="Buka target berkeyakinan tinggi di tab Jaringan & jalur")

        lay_bawah = kit.bar_bawah(
            self,
            kiri=[btn_csv, btn_metode, self.l_status],
            kanan=[btn_ke_jaringan],
            tutup=True
        )
        lay.addLayout(lay_bawah)

    def _bangun_tab_target_balik(self, parent: QWidget):
        vlay = QVBoxLayout(parent)
        vlay.setContentsMargins(8, 8, 8, 8)
        vlay.setSpacing(10)

        # Panel Kontrol Atas
        g_kontrol = QGroupBox("Pengaturan Penargetan Balik")
        h_ctrl = QHBoxLayout(g_kontrol)
        h_ctrl.setContentsMargins(10, 8, 10, 8)
        h_ctrl.setSpacing(14)

        # 1. Pilihan Senyawa
        v_senyawa = QVBoxLayout()
        v_senyawa.setSpacing(4)
        l_sen = QLabel("Senyawa kueri:")
        l_sen.setObjectName("subjudul")
        v_senyawa.addWidget(l_sen)

        self.cb_senyawa = QComboBox()
        self.cb_senyawa.setMinimumWidth(180)
        self.cb_senyawa.currentIndexChanged.connect(self._perbarui_estimasi)
        v_senyawa.addWidget(self.cb_senyawa)
        h_ctrl.addLayout(v_senyawa)

        # 2. Pilihan Kelas Panel
        v_kelas = QVBoxLayout()
        v_kelas.setSpacing(4)
        l_kls = QLabel("Kelas panel target:")
        l_kls.setObjectName("subjudul")
        v_kelas.addWidget(l_kls)

        self.cb_kelas = QComboBox()
        kelas_ada = target_balik.daftar_kelas_panel()
        for k in kelas_ada:
            n = len(target_balik.muat_panel_sah(k)[0])
            self.cb_kelas.addItem(f"{k.capitalize()} ({n} target)", k)
        if not kelas_ada:
            self.cb_kelas.addItem("(panel target belum dibangun)", "")
            self.cb_kelas.setEnabled(False)
        self.cb_kelas.currentIndexChanged.connect(self._on_kelas_berubah)
        v_kelas.addWidget(self.cb_kelas)
        h_ctrl.addLayout(v_kelas)

        # 3. Pilihan Jalur
        v_jalur = QVBoxLayout()
        v_jalur.setSpacing(4)
        l_jlr = QLabel("Jalur analisis:")
        l_jlr.setObjectName("subjudul")
        v_jalur.addWidget(l_jlr)

        h_chk = QHBoxLayout()
        self.chk_ligan = QCheckBox("Berbasis ligan (ChEMBL)")
        self.chk_ligan.setChecked(True)
        self.chk_ligan.toggled.connect(self._perbarui_estimasi)
        self.chk_struktur = QCheckBox("Berbasis struktur (docking panel)")
        self.chk_struktur.setChecked(bool(kelas_ada))
        self.chk_struktur.setEnabled(bool(kelas_ada))
        self.chk_struktur.toggled.connect(self._perbarui_estimasi)
        h_chk.addWidget(self.chk_ligan)
        h_chk.addWidget(self.chk_struktur)
        v_jalur.addLayout(h_chk)
        h_ctrl.addLayout(v_jalur)

        # 4. Estimasi & Tombol Aksi
        v_aksi = QVBoxLayout()
        v_aksi.setSpacing(4)
        self.l_estimasi = QLabel("")
        self.l_estimasi.setWordWrap(True)
        self.l_estimasi.setObjectName("subjudul")
        v_aksi.addStretch(1)

        h_btn = QHBoxLayout()
        self.btn_mulai = kit.tombol("Mulai", self._mulai_analisis, utama=True, tip="Jalankan penargetan balik")
        h_btn.addWidget(self.btn_mulai)
        v_aksi.addLayout(h_btn)
        h_ctrl.addLayout(v_aksi)

        vlay.addWidget(g_kontrol)
        vlay.addWidget(self.l_estimasi)

        # Progress bar
        self.pbar = QProgressBar()
        self.pbar.setVisible(False)
        self.pbar.setFixedHeight(6)
        vlay.addWidget(self.pbar)

        # Area Tengah: Splitter Tabel Hasil & Pratinjau
        split = QSplitter(Qt.Horizontal)
        vlay.addWidget(split, 1)

        # Kiri: Tabel Hasil
        w_tabel = QWidget()
        v_tbl = QVBoxLayout(w_tabel)
        v_tbl.setContentsMargins(0, 0, 0, 0)
        v_tbl.setSpacing(4)

        kolom = ["#", "Target", "Gen", "Ligan (Tan.)", "Struktur z", "Borda", "Keyakinan"]
        self.tabel_hasil = kit.tabel(kolom, regang=1, urut=True)
        self.tabel_hasil.itemSelectionChanged.connect(self._on_tabel_diklik)
        v_tbl.addWidget(self.tabel_hasil)

        l_instruksi = QLabel("Klik baris target untuk melihat detail interaksi dan ligan kristal/ChEMBL 2D.")
        l_instruksi.setObjectName("subjudul")
        v_tbl.addWidget(l_instruksi)

        split.addWidget(w_tabel)

        # Kanan: Detail & Visualisasi 2D
        w_detail = QWidget()
        w_detail.setMinimumWidth(320)
        v_det = QVBoxLayout(w_detail)
        v_det.setContentsMargins(8, 0, 0, 0)
        v_det.setSpacing(8)

        # Kartu Ringkasan Target
        self.g_target = QGroupBox("Detail Target Terpilih")
        v_tgt_info = QVBoxLayout(self.g_target)
        v_tgt_info.setSpacing(4)

        self.l_det_nama = QLabel("Pilih target pada tabel")
        self.l_det_nama.setWordWrap(True)
        self.l_det_nama.setStyleSheet("font-weight: bold;")
        v_tgt_info.addWidget(self.l_det_nama)

        self.l_det_pdb = QLabel("PDB ID: –")
        self.l_det_pdb.setObjectName("subjudul")
        v_tgt_info.addWidget(self.l_det_pdb)

        self.l_det_uniprot = QLabel("UniProt: –")
        self.l_det_uniprot.setObjectName("subjudul")
        v_tgt_info.addWidget(self.l_det_uniprot)

        self.l_det_skor = QLabel("Kemiripan ligan: –  |  Struktur z: –")
        self.l_det_skor.setObjectName("subjudul")
        v_tgt_info.addWidget(self.l_det_skor)

        self.l_det_keyakinan = QLabel("Keyakinan: –")
        self.l_det_keyakinan.setObjectName("subjudul")
        v_tgt_info.addWidget(self.l_det_keyakinan)

        v_det.addWidget(self.g_target)

        # Panel Gambar 2D Ligan Mirip ChEMBL
        self.g_2d = QGroupBox("Ligan ChEMBL Paling Mirip (2D)")
        v_2d = QVBoxLayout(self.g_2d)
        v_2d.setAlignment(Qt.AlignCenter)

        self.l_gambar_2d = QLabel("Belum ada ligan")
        self.l_gambar_2d.setAlignment(Qt.AlignCenter)
        self.l_gambar_2d.setFixedSize(260, 200)
        self.l_gambar_2d.setStyleSheet("border: 1px dashed #888; border-radius: 4px; background: transparent;")
        v_2d.addWidget(self.l_gambar_2d)

        self.l_info_ligan_2d = QLabel("–")
        self.l_info_ligan_2d.setObjectName("subjudul")
        self.l_info_ligan_2d.setAlignment(Qt.AlignCenter)
        self.l_info_ligan_2d.setWordWrap(True)
        v_2d.addWidget(self.l_info_ligan_2d)

        v_det.addWidget(self.g_2d)

        # Tombol aksi target
        self.btn_tampil_viewer = kit.tombol("Buka target di viewer 3D", self._buka_viewer_target,
                                            tip="Muat struktur reseptor dan pose docking ke viewer 3D")
        v_det.addWidget(self.btn_tampil_viewer)

        v_det.addStretch(1)
        split.addWidget(w_detail)

        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

    def _bangun_tab_jaringan(self, parent: QWidget):
        """Tab farmakologi jaringan: pengayaan jalur, STRING, Open Targets, dan uji sensitivitas (F3b)."""
        vlay = QVBoxLayout(parent)
        vlay.setContentsMargins(8, 8, 8, 8)
        vlay.setSpacing(10)

        g_kontrol = QGroupBox("Pengaturan Jaringan")
        h = QHBoxLayout(g_kontrol)
        h.setSpacing(18)

        v1 = QVBoxLayout()
        v1.setSpacing(4)
        l1 = QLabel("Ambang skor STRING:")
        l1.setObjectName("subjudul")
        v1.addWidget(l1)
        self.cb_string = QComboBox()
        for teks, nilai in (("0,4 (rendah)", 0.4), ("0,7 (tinggi)", 0.7), ("0,9 (sangat tinggi)", 0.9)):
            self.cb_string.addItem(teks, nilai)
        self.cb_string.setCurrentIndex(1)
        v1.addWidget(self.cb_string)
        h.addLayout(v1)

        v2 = QVBoxLayout()
        v2.setSpacing(4)
        l2 = QLabel("Skor penyakit minimum:")
        l2.setObjectName("subjudul")
        v2.addWidget(l2)
        self.sp_penyakit = QDoubleSpinBox()
        self.sp_penyakit.setRange(0.0, 1.0)
        self.sp_penyakit.setSingleStep(0.05)
        self.sp_penyakit.setValue(0.5)
        v2.addWidget(self.sp_penyakit)
        h.addLayout(v2)

        v3 = QVBoxLayout()
        v3.setSpacing(4)
        l3 = QLabel("Lapisan:")
        l3.setObjectName("subjudul")
        v3.addWidget(l3)
        hl = QHBoxLayout()
        self.chk_jalur = QCheckBox("Jalur")
        self.chk_ppi = QCheckBox("Target–target (STRING)")
        self.chk_penyakit = QCheckBox("Penyakit (Open Targets)")
        for c in (self.chk_jalur, self.chk_ppi, self.chk_penyakit):
            c.setChecked(True)
            hl.addWidget(c)
        v3.addLayout(hl)
        h.addLayout(v3)

        v3b = QVBoxLayout()
        v3b.setSpacing(4)
        l3b = QLabel("Sumber jalur:")
        l3b.setObjectName("subjudul")
        v3b.addWidget(l3b)
        self.cb_gmt = QComboBox()
        self.cb_gmt.addItem("Reactome", "reactome")
        self.cb_gmt.addItem("GO: proses biologis", "go_bp")
        v3b.addWidget(self.cb_gmt)
        h.addLayout(v3b)

        h.addStretch(1)
        v4 = QVBoxLayout()
        v4.setSpacing(6)
        self.btn_jaringan = kit.tombol("Bangun jaringan", self._bangun_jaringan, utama=True,
                                       tip="Pengayaan jalur + STRING + Open Targets untuk target terpilih")
        self.chk_sens = QCheckBox("Sertakan uji sensitivitas")
        self.chk_sens.setChecked(True)
        self.chk_sens.setToolTip("Ulangi pada ambang STRING 0,4/0,7/0,9 dan 5/10/20 target teratas, "
                                 "lalu cari simpul inti yang stabil")
        v4.addWidget(self.btn_jaringan)
        v4.addWidget(self.chk_sens)
        h.addLayout(v4)
        vlay.addWidget(g_kontrol)

        self.l_jaringan_target = QLabel("")
        self.l_jaringan_target.setWordWrap(True)
        self.l_jaringan_target.setObjectName("subjudul")
        vlay.addWidget(self.l_jaringan_target)

        split = QSplitter(Qt.Horizontal)
        vlay.addWidget(split, 1)

        w_kiri = QWidget()
        v_kiri = QVBoxLayout(w_kiri)
        v_kiri.setContentsMargins(0, 0, 0, 0)
        v_kiri.setSpacing(4)
        self.kanvas = _KanvasGraf()
        self.kanvas.setMinimumWidth(420)
        v_kiri.addWidget(self.kanvas, 1)
        self.l_legenda = QLabel("")
        self.l_legenda.setObjectName("subjudul")
        self.l_legenda.setWordWrap(True)
        v_kiri.addWidget(self.l_legenda)
        w_kiri.setMinimumWidth(420)
        split.addWidget(w_kiri)

        self.tab_kanan = QTabWidget()
        self.tabel_jalur = kit.tabel(["Jalur", "Overlap", "q", "Gen"], regang=0, urut=True)
        self.tabel_jalur.itemSelectionChanged.connect(self._sorot_jalur)
        self.tab_kanan.addTab(self.tabel_jalur, "Jalur")
        self.tabel_simpul = kit.tabel(["Simpul", "Jenis", "Derajat", "Betweenness", "Closeness"], regang=0, urut=True)
        self.tabel_simpul.itemSelectionChanged.connect(self._pilih_simpul)
        self.tab_kanan.addTab(self.tabel_simpul, "Simpul")
        self.tabel_sens = kit.tabel(["Gen", "Muncul", "Kombinasi", "%"], regang=0, urut=True)
        self.tab_kanan.addTab(self.tabel_sens, "Sensitivitas")
        self.tab_kanan.setMinimumWidth(320)
        split.addWidget(self.tab_kanan)
        split.setSizes([700, 380])

        h_bawah = QHBoxLayout()
        h_bawah.addWidget(kit.tombol("Ekspor GraphML…", self._ekspor_graphml, tip="Berkas untuk Cytoscape atau Gephi"))
        h_bawah.addWidget(kit.tombol("Ekspor CSV tepi…", self._ekspor_tepi))
        h_bawah.addWidget(kit.tombol("Kirim ke komposer", self._kirim_komposer))
        h_bawah.addWidget(kit.tombol("Salin paragraf metode", self._salin_metode_jaringan))
        h_bawah.addStretch(1)
        self.l_status_jaringan = QLabel("")
        h_bawah.addWidget(self.l_status_jaringan)
        vlay.addLayout(h_bawah)

        self._perbarui_ringkasan_jaringan()

    # ------------------------------------------------------------------ jaringan (F3b)
    def _gen_jaringan(self) -> List[str]:
        """Gen target untuk jaringan: dari pilihan pengguna di tabel, bila kosong dari hasil penargetan balik."""
        if self._gen_terpilih:
            return list(self._gen_terpilih)
        return [h["gen"] for h in self.hasil_gabungan if h.get("gen")][:20]

    def _perbarui_ringkasan_jaringan(self):
        gen = self._gen_jaringan()
        if not gen:
            self.l_jaringan_target.setText(
                "Belum ada target. Jalankan penargetan balik di tab sebelah, lalu tekan "
                "\u201cKirim target terpilih ke Jaringan\u201d.")
        else:
            asal = "dipilih di tabel" if self._gen_terpilih else "20 teratas penargetan balik"
            self.l_jaringan_target.setText(f"{len(gen)} target ({asal}): " + ", ".join(gen))
        self.btn_jaringan.setEnabled(bool(gen))

    def _bangun_jaringan(self):
        gen = self._gen_jaringan()
        if not gen:
            return
        self.btn_jaringan.setEnabled(False)
        self.l_status_jaringan.setText("Menyiapkan…")
        a_sens = (0.4, 0.7, 0.9) if self.chk_sens.isChecked() else ()
        self._utas_jaringan = _UtasJaringan(gen, self.cb_string.currentData(), self.sp_penyakit.value(),
                                            self.chk_ppi.isChecked(), self.chk_penyakit.isChecked(), a_sens)
        self._utas_jaringan.kabar.connect(self.l_status_jaringan.setText)
        self._utas_jaringan.selesai.connect(self._jaringan_siap)
        self._utas_jaringan.start()

    def _jaringan_siap(self, hasil, galat):
        self.btn_jaringan.setEnabled(True)
        if galat:
            self.l_status_jaringan.setText(galat)
            return
        gen = self._gen_jaringan()
        nama_gmt = self.cb_gmt.currentData()
        self._pengayaan = []
        if self.chk_jalur.isChecked():
            try:
                self._pengayaan = pengayaan.hipergeometrik(gen, pengayaan.gmt_bawaan(nama_gmt), min_overlap=2)
            except FileNotFoundError as e:
                self.l_status_jaringan.setText(str(e))
        for j in hasil["jejak"]:
            if self.proyek:
                self.proyek.catat_jejak(j)

        senyawa = {self._lig_data.get("nama") or "Senyawa": gen}
        self._graf = jaringan.bangun(senyawa, self._pengayaan, hasil["tepi"], hasil["penyakit"])
        self._sens = {}
        if self.chk_sens.isChecked() and hasil["tepi_per_ambang"]:
            self._sens = jaringan.sensitivitas(senyawa, hasil["tepi_per_ambang"])
        self._info_jaringan = {"nama_gmt": nama_gmt, "ambang_string": self.cb_string.currentData(),
                               "ambang_penyakit": self.sp_penyakit.value(), "n_ppi": len(hasil["tepi"]),
                               "n_penyakit": len(hasil["penyakit"]), "versi_string": hasil["versi_string"],
                               "versi_ot": hasil["versi_ot"], "n_gen": len(gen)}
        self._gambar_graf()
        self._isi_tabel_jaringan()
        sig = sum(1 for b in self._pengayaan if b["q"] < 0.05)
        self.l_status_jaringan.setText(
            f"{self._graf.number_of_nodes()} simpul, {self._graf.number_of_edges()} tepi; "
            f"{sig} jalur q < 0,05; {len(hasil['penyakit'])} tepi penyakit.")

    def _gambar_graf(self, sorot_gen=()):
        if self._graf is None or self._graf.number_of_nodes() == 0:
            return
        t = kit.mode()
        warna_lapisan = {"senyawa": kit.hx("warn"), "target": kit.hx("acc2"), "jalur": kit.hx("ok"),
                         "penyakit": kit.hx("bad")}
        warna = {n: warna_lapisan.get(d.get("jenis"), kit.hx("mut")) for n, d in self._graf.nodes(data=True)}
        inti = {f"T:{g}" for g in (self._sens or {}).get("inti_stabil", [])}
        inti |= {f"T:{g}" for g in sorot_gen}
        lebar, tinggi = 1400, 980
        posisi = graf.tata_letak(self._graf, benih=1, renggang=2.2)
        svg = graf.svg_graf(self._graf, posisi=posisi, warna_simpul=warna, label=self._label_graf(),
                            lebar=lebar, tinggi=tinggi, tema=t, sorot=inti)
        self.kanvas.tampilkan(svg, lebar, tinggi)
        petak = "".join(f'<span style="color:{warna_lapisan[k]}">●</span> {k}&nbsp;&nbsp; '
                        for k in ("senyawa", "target", "jalur", "penyakit"))
        self.l_legenda.setText(
            petak + "&nbsp;· ukuran ∝ derajat · tepi tebal = inti stabil · "
            "gulir = perbesar, seret = geser · label hanya pada simpul ≥ 3 target")

    def _label_graf(self) -> Dict[str, str]:
        """Label hanya untuk senyawa, target, dan jalur/penyakit yang menghubungkan >= 3 target.

        Tanpa penyaringan ini puluhan nama saling menimpa dan graf tidak terbaca; nama lengkap tetap ada di tabel kanan.
        """
        label = {}
        for n, d in self._graf.nodes(data=True):
            if d.get("jenis") in ("senyawa", "target") or self._graf.degree(n) >= 3:
                teks = d.get("label", n)
                label[n] = teks if len(teks) <= 28 else teks[:27] + "…"
        return label

    def _isi_tabel_jaringan(self):
        self.tabel_jalur.setSortingEnabled(False)
        self.tabel_jalur.setRowCount(len(self._pengayaan))
        for r, b in enumerate(self._pengayaan):
            self.tabel_jalur.setItem(r, 0, kit.sel(b["nama"]))
            self.tabel_jalur.setItem(r, 1, kit.sel_angka(b["n_overlap"], d=0))
            self.tabel_jalur.setItem(r, 2, kit.sel_angka(b["q"], d=4))
            self.tabel_jalur.setItem(r, 3, kit.sel(", ".join(b["gen"])))
            self.tabel_jalur.item(r, 0).setData(Qt.UserRole, b)
        self.tabel_jalur.setSortingEnabled(True)

        m = jaringan.metrik(self._graf)
        self.tabel_simpul.setSortingEnabled(False)
        self.tabel_simpul.setRowCount(len(m))
        for r, b in enumerate(m):
            self.tabel_simpul.setItem(r, 0, kit.sel(b["label"]))
            self.tabel_simpul.setItem(r, 1, kit.sel(b["jenis"]))
            self.tabel_simpul.setItem(r, 2, kit.sel_angka(b["derajat"], d=0))
            self.tabel_simpul.setItem(r, 3, kit.sel_angka(b["betweenness"], d=4))
            self.tabel_simpul.setItem(r, 4, kit.sel_angka(b["closeness"], d=4))
        self.tabel_simpul.setSortingEnabled(True)

        baris = (self._sens or {}).get("simpul", [])
        self.tabel_sens.setSortingEnabled(False)
        self.tabel_sens.setRowCount(len(baris))
        for r, b in enumerate(baris):
            self.tabel_sens.setItem(r, 0, kit.sel(b["gen"]))
            self.tabel_sens.setItem(r, 1, kit.sel_angka(b["muncul"], d=0))
            self.tabel_sens.setItem(r, 2, kit.sel_angka(b["kombinasi"], d=0))
            self.tabel_sens.setItem(r, 3, kit.sel_angka(b["persen"], d=1))
        self.tabel_sens.setSortingEnabled(True)

    def _pilih_simpul(self):
        """Pilih baris target: sorot simpulnya pada graf dan muat reseptor panelnya ke viewer 3D bila ada."""
        baris = self.tabel_simpul.currentRow()
        if baris < 0 or self._graf is None:
            return
        jenis = self.tabel_simpul.item(baris, 1)
        gen = self.tabel_simpul.item(baris, 0)
        if not jenis or not gen or jenis.text() != "target":
            return
        self._gambar_graf(sorot_gen=[gen.text()])
        hasil = next((h for h in self.hasil_gabungan if h.get("gen") == gen.text()), None)
        if hasil and hasil.get("pdb"):
            self.target_terpilih = hasil
            self._buka_viewer_target()

    def _sorot_jalur(self):
        baris = self.tabel_jalur.currentRow()
        if baris < 0 or self._graf is None:
            return
        item = self.tabel_jalur.item(baris, 0)
        data = item.data(Qt.UserRole) if item else None
        if data:
            self._gambar_graf(sorot_gen=data["gen"])

    def _ekspor_graphml(self):
        if self._graf is None:
            self.l_status_jaringan.setText("Bangun jaringan dulu.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan GraphML", "jaringan.graphml", "GraphML (*.graphml)")
        if path:
            graf.ekspor_graphml(self._graf, path)
            self.l_status_jaringan.setText(f"Jaringan disimpan: {Path(path).name}")

    def _ekspor_tepi(self):
        if self._graf is None:
            self.l_status_jaringan.setText("Bangun jaringan dulu.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan daftar tepi", "jaringan_tepi.csv", "CSV (*.csv)")
        if path:
            graf.ekspor_csv_tepi(self._graf, path)
            self.l_status_jaringan.setText(f"Daftar tepi disimpan: {Path(path).name}")

    def _kirim_komposer(self):
        if self._graf is None:
            self.l_status_jaringan.setText("Bangun jaringan dulu.")
            return
        warna_lapisan = {"senyawa": kit.hx("warn"), "target": kit.hx("acc2"), "jalur": kit.hx("ok"),
                         "penyakit": kit.hx("bad")}
        warna = {n: warna_lapisan.get(d.get("jenis"), kit.hx("mut")) for n, d in self._graf.nodes(data=True)}
        svg = graf.svg_graf(self._graf, warna_simpul=warna, lebar=900, tinggi=620, tema=kit.mode(),
                            sorot={f"T:{g}" for g in (self._sens or {}).get("inti_stabil", [])})
        if not getattr(self.jw, "komposer", None):
            self.jw.buka_komposer()
        self.jw.komposer.tambah({"nama": "Jaringan farmakologi", "jenis": "svg", "isi": svg, "w": 900, "h": 620})
        self.l_status_jaringan.setText("Graf ditambahkan ke Komposer Figur.")

    def _salin_metode_jaringan(self):
        if self._graf is None:
            self.l_status_jaringan.setText("Bangun jaringan dulu.")
            return
        i = self._info_jaringan
        teks = jaringan.susun_paragraf_metode(
            "hasil penargetan balik", i["n_gen"], i["nama_gmt"], self._pengayaan, i["ambang_string"], i["n_ppi"],
            i["ambang_penyakit"], i["n_penyakit"], self._sens, versi_ot=i["versi_ot"], versi_string=i["versi_string"])
        kit.salin(teks, status=self.l_status_jaringan, pesan="Paragraf metode jaringan disalin ke papan klip.")

    # ---------------------------------------------------------------- Data & Logika
    def _muat_pilihan_senyawa(self):
        self.cb_senyawa.clear()
        if self.proyek and getattr(self.proyek, "ligan", None):
            for lig in self.proyek.ligan:
                nama = lig.get("nama") or lig.get("id") or "Ligan"
                self.cb_senyawa.addItem(nama, userData=lig)

        # Bila proyek belum memiliki ligan, berikan contoh bawaan (Kurkumin, Ibuprofen)
        if self.cb_senyawa.count() == 0:
            contoh = [
                {"id": "kurkumin", "nama": "Kurkumin", "smiles": "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O"},
                {"id": "ibuprofen", "nama": "Ibuprofen", "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O"},
                {"id": "aspirin", "nama": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
            ]
            for c in contoh:
                self.cb_senyawa.addItem(c["nama"], userData=c)

    def _on_kelas_berubah(self):
        self.kelas_aktif = self.cb_kelas.currentData() or ""
        self._perbarui_estimasi()
        self._isi_tabel_panel_awal()

    def _perbarui_estimasi(self):
        sah, lewat = target_balik.muat_panel_sah(self.kelas_aktif) if self.kelas_aktif else ([], [])
        bagian = []
        if self.chk_ligan.isChecked():
            bagian.append("Jalur ligan: kueri ChEMBL daring, perlu internet.")
        if self.chk_struktur.isChecked():
            bagian.append(f"Jalur struktur: {len(sah)} job Vina (CPU) masuk antrean.")
        if lewat:
            bagian.append(f"{len(lewat)} entri panel dilewati (tak memenuhi syarat).")
        if not self.kelas_aktif:
            bagian.append("Panel target belum tersedia di paket ini.")
        self.l_estimasi.setText("\n".join(bagian))

    def _isi_tabel_panel_awal(self):
        panel = target_balik.muat_panel_sah(self.kelas_aktif)[0] if self.kelas_aktif else []
        self.tabel_hasil.setSortingEnabled(False)
        self.tabel_hasil.setRowCount(len(panel))

        for row, tgt in enumerate(panel):
            self.tabel_hasil.setItem(row, 0, kit.sel_angka(row + 1, d=0))
            self.tabel_hasil.setItem(row, 1, kit.sel(f"{tgt.get('nama', '')} · {tgt['pdb']}"))
            self.tabel_hasil.setItem(row, 2, kit.sel(tgt.get("gen", tgt.get("pdb", ""))))
            self.tabel_hasil.setItem(row, 3, kit.sel_angka(None))
            self.tabel_hasil.setItem(row, 4, kit.sel_angka(None))
            self.tabel_hasil.setItem(row, 5, kit.sel_angka(None))
            self.tabel_hasil.setItem(row, 6, kit.sel("–"))

            # Simpan metadata target di baris
            self.tabel_hasil.item(row, 1).setData(Qt.UserRole, tgt)

        self.tabel_hasil.setSortingEnabled(True)
        self.tabel_hasil.sortByColumn(0, Qt.AscendingOrder)

    def _mulai_analisis(self):
        lig_data = self.cb_senyawa.currentData()
        if not lig_data:
            return

        smiles = lig_data.get("smiles") or ""
        self._sedang_berjalan = True
        self.btn_mulai.setEnabled(False)
        self.pbar.setVisible(True)
        self.pbar.setValue(10)
        self.l_status.setText("Menjalankan penargetan balik...")

        self._eksekusi_analisis(lig_data, smiles)

    def _eksekusi_analisis(self, lig_data: Dict[str, Any], smiles: str):
        self._lig_data = lig_data
        if self.chk_ligan.isChecked() and smiles:
            self.l_status.setText("Mengambil data ChEMBL…")
            self._utas = _UtasLigan(smiles, target_balik.organisme_kelas(self.kelas_aktif))
            self._utas.selesai.connect(self._lanjut_analisis)
            self._utas.start()
        else:
            self._lanjut_analisis([], [], "")

    def _lanjut_analisis(self, hasil_ligan, jejak, galat):
        lig_data = self._lig_data
        if galat:
            self._sedang_berjalan = False
            self.btn_mulai.setEnabled(True)
            self.pbar.setVisible(False)
            self.l_status.setText(galat)
            return
        self.pbar.setValue(40)
        self._hasil_ligan, self._jejak = hasil_ligan, list(jejak)
        self._analisis_aktif = True
        if self.proyek:
            for j in jejak:
                self.proyek.catat_jejak(j)

        catatan = ""
        if self.chk_struktur.isChecked() and self.kelas_aktif:
            catatan = self._antre_struktur(lig_data)
        self._gabung_dan_tampil(catatan)
        self._sedang_berjalan = False
        self.btn_mulai.setEnabled(True)
        self.pbar.setVisible(False)

    def _antre_struktur(self, lig_data: Dict[str, Any]) -> str:
        """Daftarkan job docking panel (satu per target yang belum punya job untuk ligan ini). Kembalikan catatan status."""
        if not self.proyek or not getattr(self.jw, "pelaksana", None):
            return "Jalur struktur membutuhkan proyek yang terbuka."
        lig = self.proyek.cari_ligan(lig_data.get("id")) if lig_data.get("id") else None
        if not lig or not lig.get("pdbqt"):
            return "Jalur struktur dilewati: ligan belum disiapkan di proyek (tidak ada PDBQT)."
        ada = {h["pdb"] for h in target_balik.kumpulkan(self.proyek, self.kelas_aktif, ligan_id=lig["id"])
               if h["status"] != "belum_dijalankan"}
        try:
            baru = target_balik.jalur_struktur(self.proyek, lig, self.kelas_aktif, lewati=ada,
                                               daftarkan=self.jw.pelaksana.tambah)
        except target_balik.GalatTargetBalik as e:
            return str(e)
        return f"{len(baru)} job docking panel dimasukkan ke antrean." if baru else "Hasil docking panel sudah ada di proyek."

    def _hasil_struktur(self) -> List[Dict[str, Any]]:
        if self.chk_struktur.isChecked() and self.proyek and self.kelas_aktif:
            return target_balik.kumpulkan(self.proyek, self.kelas_aktif, ligan_id=self._lig_data.get("id"))
        return []

    def _gabung_dan_tampil(self, catatan: str = ""):
        hasil_struktur = self._hasil_struktur()
        self.hasil_gabungan = target_balik.gabung(self._hasil_ligan, hasil_struktur)
        self._tampilkan_hasil(self.hasil_gabungan)

        n_sel = sum(1 for h in hasil_struktur if h["z_skor"] is not None)
        n_gagal = sum(1 for h in hasil_struktur if h["status"] in ("gagal", "dibatalkan"))
        n_tunggu = len(hasil_struktur) - n_sel - n_gagal
        bagian = [f"{len(self.hasil_gabungan)} target diperingkat"]
        if hasil_struktur:
            bagian.append(f"docking panel: {n_sel} selesai, {n_gagal} gagal, {n_tunggu} menunggu")
        if catatan:
            bagian.append(catatan)
        self.l_status.setText("; ".join(bagian) + ".")

        if self.proyek:
            entri = {"ligan_id": self._lig_data.get("id", ""), "nama_ligan": self._lig_data.get("nama", ""),
                     "kelas": self.kelas_aktif, "hasil": self.hasil_gabungan,
                     "parameter": {"jalur_ligan": self.chk_ligan.isChecked(), "jalur_struktur": self.chk_struktur.isChecked(),
                                   "exhaustiveness": 8},
                     "jejak": list(self._jejak)}
            tb = self.proyek.target_balik
            for i, e in enumerate(tb):
                if e.get("ligan_id") == entri["ligan_id"] and e.get("kelas") == entri["kelas"]:
                    tb[i] = entri
                    break
            else:
                tb.append(entri)

    def _job_selesai(self, jid: str):
        """Perbarui peringkat saat job panel untuk ligan dan kelas yang sedang ditampilkan selesai."""
        if not self.proyek or not self._analisis_aktif:
            return
        j = next((x for x in self.proyek.job if x["id"] == jid), None)
        tb = (j or {}).get("target_balik")
        if tb and tb.get("kelas") == self.kelas_aktif and self._lig_data:
            if any(l.get("id") == self._lig_data.get("id") for l in j.get("ligan", [])):
                self._gabung_dan_tampil()

    def _tampilkan_hasil(self, hasil_list: List[Dict[str, Any]]):
        self.tabel_hasil.setSortingEnabled(False)
        self.tabel_hasil.setRowCount(len(hasil_list))

        for row, h in enumerate(hasil_list):
            self.tabel_hasil.setItem(row, 0, kit.sel_angka(row + 1, d=0))
            self.tabel_hasil.setItem(row, 1, kit.sel(h.get("nama") or h.get("target", "")))
            self.tabel_hasil.setItem(row, 2, kit.sel(h.get("gen", "")))

            # Ligan skor Tanimoto
            skor_l = h.get("skor_ligan")
            self.tabel_hasil.setItem(row, 3, kit.sel_angka(skor_l, d=2))

            # Struktur z-skor
            z_s = h.get("struktur_z")
            self.tabel_hasil.setItem(row, 4, kit.sel_angka(z_s, d=1))

            # Borda
            borda = h.get("borda")
            self.tabel_hasil.setItem(row, 5, kit.sel_angka(borda, d=0))

            # Keyakinan
            keyak = h.get("keyakinan", "rendah")
            it_keyak = kit.sel(f"[{keyak}]")
            if keyak == "tinggi":
                it_keyak.setForeground(kit.warna("ok"))
            elif keyak == "sedang":
                it_keyak.setForeground(kit.warna("warn"))
            else:
                it_keyak.setForeground(kit.warna("mut"))
            self.tabel_hasil.setItem(row, 6, it_keyak)

            # Metadata di baris
            self.tabel_hasil.item(row, 1).setData(Qt.UserRole, h)

        self.tabel_hasil.setSortingEnabled(True)
        self.tabel_hasil.sortByColumn(0, Qt.AscendingOrder)

        if len(hasil_list) > 0:
            self.tabel_hasil.selectRow(0)

    def _on_tabel_diklik(self):
        baris = self.tabel_hasil.currentRow()
        if baris < 0:
            return

        it = self.tabel_hasil.item(baris, 1)
        if not it:
            return

        data = it.data(Qt.UserRole)
        if not data:
            return

        self.target_terpilih = data

        # Perbarui panel detail
        nama = data.get("nama", "Target")
        gen = data.get("gen", "–")
        pdb = data.get("pdb", "–")
        uniprot = data.get("uniprot", "–")

        self.l_det_nama.setText(f"{nama} ({gen})")
        self.l_det_pdb.setText(f"PDB ID: {pdb}")
        self.l_det_uniprot.setText(f"UniProt: {uniprot}")

        skor_l = kit.f(data.get("skor_ligan"), 2)
        skor_z = kit.f(data.get("struktur_z"), 1)
        self.l_det_skor.setText(f"Kemiripan ligan: {skor_l}  |  Struktur z: {skor_z}")

        keyak = data.get("keyakinan", "–")
        self.l_det_keyakinan.setText(f"Keyakinan konsensus: [{keyak}]")

        # Gambar 2D ligan mirip ChEMBL
        contoh = data.get("contoh_ligan")
        if contoh and contoh.get("smiles"):
            smi = contoh["smiles"]
            nm_lig = contoh.get("nama") or contoh.get("chembl_id") or "Ligan ChEMBL"
            kem = kit.f(contoh.get("kemiripan"), 2)
            self.l_info_ligan_2d.setText(f"{nm_lig} (Tanimoto: {kem})")
            self._gambar_molekul_2d(smi)
        else:
            self.l_gambar_2d.setText("Struktur 2D tidak tersedia")
            self.l_info_ligan_2d.setText("–")

    def _gambar_molekul_2d(self, smiles: str):
        """Gambar 2D molekul ligan acuan ChEMBL dan tampilkan di QLabel."""
        if not Chem or not Draw or not smiles:
            self.l_gambar_2d.setText("RDKit tidak tersedia")
            return

        try:
            mol = Chem.MolFromSmiles(smiles)
            if not mol:
                self.l_gambar_2d.setText("SMILES tidak valid")
                return

            img = Draw.MolToImage(mol, size=(260, 200))
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            qimg = QImage.fromData(buffer.getvalue())
            self.l_gambar_2d.setPixmap(QPixmap.fromImage(qimg))
        except Exception as e:
            catat.log.debug(f"Gagal merender molekul 2D: {e}")
            self.l_gambar_2d.setText("Gagal merender 2D")

    def _buka_viewer_target(self):
        """Buka struktur reseptor dan pose docking ke viewer 3D jendela utama bila tersedia."""
        if not self.target_terpilih:
            return

        pdb = self.target_terpilih.get("pdb")
        if not pdb or not self.jw:
            return

        berkas_rec = target_balik.DIR_DATA_PANEL / self.kelas_aktif / f"{pdb}.pdbqt"
        if not berkas_rec.exists():
            self.l_status.setText(f"Reseptor panel {pdb} tidak ada di paket ini.")
            return
        if not getattr(self.jw, "viewer", None):
            self.l_status.setText("Viewer 3D tidak tersedia.")
            return
        try:
            from ..core import molekul, prep_reseptor
            teks_pdb = prep_reseptor.pdbqt_ke_pdb(berkas_rec.read_text(encoding="utf-8"))
            o = molekul.Objek(nama=f"Panel {pdb}", jenis="protein", teks=teks_pdb, fmt="pdb")
            self.jw.viewer.muat(o)
            self.jw.viewer.tampil(o, molekul.spek_viewer(o))
            self.l_status.setText(f"Reseptor panel {pdb} dimuat ke viewer 3D.")
        except Exception as e:
            self.l_status.setText(f"Gagal memuat reseptor ke viewer: {e}")

    def _muat_riwayat_proyek(self):
        if not self.proyek or not getattr(self.proyek, "target_balik", None):
            return
        terakhir = self.proyek.target_balik[-1]
        self.kelas_aktif = terakhir.get("kelas", self.kelas_aktif)
        self.hasil_gabungan = terakhir.get("hasil", [])
        if self.hasil_gabungan:
            self._tampilkan_hasil(self.hasil_gabungan)

    def _salin_metode(self):
        n_suk = sum(1 for h in self.hasil_gabungan if h.get("struktur_z") is not None)
        n_gag = len(self.hasil_gabungan) - n_suk
        teks = target_balik.susun_paragraf_metode(
            kelas=self.kelas_aktif,
            parameter=(self.proyek.target_balik[-1].get("parameter") if self.proyek and self.proyek.target_balik else {}),
            n_sukses=n_suk,
            n_gagal=n_gag,
            jejak=(self.proyek.target_balik[-1].get("jejak") if self.proyek and self.proyek.target_balik else None)
        )
        kit.salin(teks, status=self.l_status, pesan="Paragraf metode disalin ke papan klip.")

    def _ekspor_csv(self):
        if not self.hasil_gabungan:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Peringkat Target Balik", "target_balik.csv", "CSV (*.csv)")
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            penulis = csv.writer(f)
            penulis.writerow(["Peringkat", "Target", "Gen", "UniProt", "PDB", "Kemiripan_Ligan", "Struktur_z", "Skor_Borda", "Keyakinan"])
            for idx, h in enumerate(self.hasil_gabungan, start=1):
                penulis.writerow([
                    idx,
                    h.get("nama", ""),
                    h.get("gen", ""),
                    h.get("uniprot", ""),
                    h.get("pdb", ""),
                    h.get("skor_ligan", ""),
                    h.get("struktur_z", ""),
                    h.get("borda", ""),
                    h.get("keyakinan", "")
                ])
        self.l_status.setText(f"Peringkat target diekspor ke {Path(path).name}.")

    def _ke_tab_jaringan(self):
        """Kirim target berkeyakinan tinggi (atau baris terpilih) ke tab Jaringan & jalur."""
        baris = {i.row() for i in self.tabel_hasil.selectedIndexes()}
        if baris:
            pilih = [self.hasil_gabungan[r] for r in sorted(baris) if r < len(self.hasil_gabungan)]
        else:
            pilih = [h for h in self.hasil_gabungan if h.get("keyakinan") == "tinggi"] or self.hasil_gabungan[:10]
        self._gen_terpilih = [h.get("gen") or h.get("target") for h in pilih if h.get("gen") or h.get("target")]
        self._perbarui_ringkasan_jaringan()
        self.tabs.setCurrentIndex(1)
