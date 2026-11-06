"""Dialog Penapisan Berbasis Ligan 3D (F4).

Menapis pustaka senyawa secara cepat menggunakan:
1. Kueri farmakofor 3D (fitur donor, akseptor, aromatik, hidrofobik, ionik + volume eksklusi protein).
2. Keselarasan bentuk dan warna farmakoforik (rdShapeAlign ETKDGv3).
3. Skor terbobot gabungan dan validasi bawaan pengayaan (ROC-AUC, BEDROC, EF1%).
"""
import csv
from pathlib import Path
import threading
from typing import Any, Dict, List

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QProgressBar,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget
)

from rdkit import Chem

from ..core import catat, decoy, farmakofor, molekul, prep_ligan, pustaka
from . import kerja, kit, theme
from .viewer_widget import Viewer


class _UtasPenapisan(QThread):
    progresSignal = Signal(int, int, str)
    selesaiSignal = Signal(list, str)

    def __init__(self, kueri: Dict[str, Any], daftar: List[Any],
                 bobot_farma: float, bobot_bentuk: float, konf_per_mol: int):
        super().__init__()
        self.kueri = kueri
        self.daftar = daftar
        self.bobot_farma = bobot_farma
        self.bobot_bentuk = bobot_bentuk
        self.konf_per_mol = konf_per_mol
        self._batal = threading.Event()

    def batal(self):
        self._batal.set()

    def run(self):
        try:
            def _lapor(selesai, total, pesan):
                self.progresSignal.emit(selesai, total, pesan)

            hasil = farmakofor.saring_pustaka(
                self.kueri,
                self.daftar,
                batal=self._batal,
                progres=_lapor,
                bobot_farma=self.bobot_farma,
                bobot_bentuk=self.bobot_bentuk,
                konf_per_mol=self.konf_per_mol
            )
            pesan = "Penapisan dibatalkan." if self._batal.is_set() else ""
            self.selesaiSignal.emit(hasil, pesan)
        except Exception as e:
            catat.log.error(f"Galat penapisan farmakofor: {e}")
            self.selesaiSignal.emit([], str(e))


class DialogFarmakofor(QDialog):
    """Dialog Penapisan Berbasis Ligan 3D (Farmakofor & Bentuk)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Penapisan berbasis ligan 3D")
        self.resize(1260, 750)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)

        self.jw = parent
        self.proyek = getattr(parent, "proyek", None)
        self._ref_mol = None
        self._kueri = None
        self._hasil_terakhir = []
        self._val_terakhir = None
        self._val_sibuk = False
        self._aktif_val = []
        self._versi_kueri = 0
        self._utas = None

        self._bangun_ui()
        self._inisialisasi_sumber()

    def _bangun_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header dan catatan ilmiah
        layout.addWidget(kit.judul(
            "Penapisan berbasis ligan 3D",
            "Penyaringan pustaka senyawa berdasarkan farmakofor 3D dan keselarasan bentuk"
        ))
        layout.addWidget(kit.catatan(
            "Penapisan berbasis ligan 3D mempercepat penemuan kandidat sebelum docking komprehensif. "
            "Hasil penapisan merupakan hipotesis dan tetap memerlukan konfirmasi energi bebas pengikatan.",
            "peringatan"
        ))

        # Splitter 3 panel
        split = QSplitter(Qt.Horizontal, self)
        split.setChildrenCollapsible(False)

        # Panel Kiri (30%): Parameter dan Kueri
        w_kiri = QWidget()
        v_kiri = QVBoxLayout(w_kiri)
        v_kiri.setContentsMargins(0, 0, 8, 0)
        v_kiri.setSpacing(8)

        # Sumber kueri
        g_sumber = QGroupBox("Sumber kueri")
        v_sumber = QVBoxLayout(g_sumber)
        v_sumber.setSpacing(6)
        self.cb_sumber = QComboBox()
        self.cb_sumber.currentIndexChanged.connect(self._ganti_sumber)
        v_sumber.addWidget(self.cb_sumber)

        self.chk_eksklusi = QCheckBox("Volume eksklusi protein (4 Å)")
        self.chk_eksklusi.setChecked(True)
        self.chk_eksklusi.toggled.connect(self._ekstrak_kueri)
        v_sumber.addWidget(self.chk_eksklusi)
        v_kiri.addWidget(g_sumber)

        # Daftar Fitur Farmakofor
        g_fitur = QGroupBox("Fitur farmakofor 3D")
        v_fitur = QVBoxLayout(g_fitur)
        v_fitur.setSpacing(6)

        self.tabel_fitur = QTableWidget()
        # Koordinat pusat ditaruh di tooltip: panel kiri terlalu sempit untuk kolom X, Y, Z
        self.tabel_fitur.setColumnCount(3)
        self.tabel_fitur.setHorizontalHeaderLabels(["Aktif", "Fitur", "Tol (Å)"])
        self.tabel_fitur.setColumnWidth(0, 52)
        self.tabel_fitur.setColumnWidth(2, 84)
        self.tabel_fitur.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tabel_fitur.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabel_fitur.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tabel_fitur.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tabel_fitur.verticalHeader().setVisible(False)
        self.tabel_fitur.verticalHeader().setDefaultSectionSize(28)
        self.tabel_fitur.setSelectionBehavior(QAbstractItemView.SelectRows)
        v_fitur.addWidget(self.tabel_fitur)

        h_btn_fitur = QHBoxLayout()
        b_pilih_semua = kit.tombol("Pilih semua", self._pilih_semua_fitur)
        b_kosongkan = kit.tombol("Kosongkan", self._kosongkan_fitur)
        h_btn_fitur.addWidget(b_pilih_semua)
        h_btn_fitur.addWidget(b_kosongkan)
        v_fitur.addLayout(h_btn_fitur)
        v_kiri.addWidget(g_fitur)

        # Bobot Skor
        g_bobot = QGroupBox("Bobot komponen skor")
        v_bobot = QVBoxLayout(g_bobot)
        self.lbl_bobot = QLabel("50 % Farmakofor : 50 % Bentuk-Warna")
        v_bobot.addWidget(self.lbl_bobot)
        self.sl_bobot = QSlider(Qt.Horizontal)
        self.sl_bobot.setToolTip("Bobot antara kecocokan fitur farmakofor dan kemiripan bentuk-warna. Geser ke farmakofor bila yang penting adalah pola donor/akseptor; ke bentuk bila yang dicari adalah rangka dengan volume serupa.")
        self.sl_bobot.setRange(0, 100)
        self.sl_bobot.setValue(50)
        self.sl_bobot.valueChanged.connect(self._update_label_bobot)
        v_bobot.addWidget(self.sl_bobot)
        v_kiri.addWidget(g_bobot)

        # Pustaka & Konformer
        g_pus = QGroupBox("Pustaka senyawa")
        v_pus = QVBoxLayout(g_pus)
        self.cb_pustaka = QComboBox()
        self.cb_pustaka.setToolTip("Pustaka yang ditapis. Obat yang sudah disetujui berguna untuk penggunaan ulang (repurposing); COCONUT untuk bahan alam.")
        self.cb_pustaka.addItem("Obat disetujui (ChEMBL)", "obat")
        if pustaka.coconut_ada():
            self.cb_pustaka.addItem("COCONUT lokal (Bahan alam)", "coconut")
        self.cb_pustaka.addItem("Ligan proyek saat ini", "proyek")
        self.cb_pustaka.addItem("Impor berkas SDF / SMILES…", "berkas")
        v_pus.addWidget(self.cb_pustaka)

        h_konf = QHBoxLayout()
        h_konf.addWidget(QLabel("Konformer / senyawa:"))
        self.sp_konf = QSpinBox()
        self.sp_konf.setToolTip("Konformer 3D per senyawa. 30 cukup untuk molekul berukuran obat; molekul sangat lentur (lebih dari 10 ikatan berputar) butuh lebih banyak agar bentuk yang relevan ikut terwakili.")
        self.sp_konf.setRange(1, 100)
        self.sp_konf.setValue(30)
        h_konf.addWidget(self.sp_konf)
        v_pus.addLayout(h_konf)

        # Tombol aksi penapisan
        h_aksi = QHBoxLayout()
        self.btn_saring = kit.tombol("Saring pustaka", self._mulai_saring, utama=True)
        self.btn_batal = kit.tombol("Batal", self._batal_saring)
        self.btn_batal.setEnabled(False)
        h_aksi.addWidget(self.btn_saring)
        h_aksi.addWidget(self.btn_batal)
        v_pus.addLayout(h_aksi)

        self.prog_bar = QProgressBar()
        self.prog_bar.setVisible(False)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #666; font-size: 11px;")
        v_pus.addWidget(self.prog_bar)
        v_pus.addWidget(self.lbl_status)
        v_kiri.addWidget(g_pus)

        split.addWidget(w_kiri)

        # Panel Tengah (35%): Viewer 3D
        w_tengah = QWidget()
        v_tengah = QVBoxLayout(w_tengah)
        v_tengah.setContentsMargins(4, 0, 4, 0)
        v_tengah.setSpacing(6)

        h_bar_viewer = QHBoxLayout()
        h_bar_viewer.addWidget(QLabel("Pratinjau kueri & bentuk 3D:"))
        h_bar_viewer.addStretch()
        self.chk_tampil_farma = QCheckBox("Bola farmakofor")
        self.chk_tampil_farma.setChecked(True)
        self.chk_tampil_farma.toggled.connect(self._perbarui_viewer_kueri)
        self.chk_tampil_eksklusi = QCheckBox("Bola eksklusi")
        self.chk_tampil_eksklusi.setChecked(True)
        self.chk_tampil_eksklusi.toggled.connect(self._perbarui_viewer_kueri)
        h_bar_viewer.addWidget(self.chk_tampil_farma)
        h_bar_viewer.addWidget(self.chk_tampil_eksklusi)
        v_tengah.addLayout(h_bar_viewer)

        self.viewer = Viewer(self)
        # Penampil mengikuti tema aplikasi seperti penampil utama
        latar = theme.TOKEN[kit.mode()]["view"]
        self.viewer.page().setBackgroundColor(latar)
        self.viewer.js("tema", kit.mode() == "gelap", latar)
        self.viewer.jembatan.siapSignal.connect(self._saat_viewer_siap)
        v_tengah.addWidget(self.viewer, 1)

        split.addWidget(w_tengah)

        # Panel Kanan (35%): Hasil dan Validasi
        w_kanan = QWidget()
        v_kanan = QVBoxLayout(w_kanan)
        v_kanan.setContentsMargins(8, 0, 0, 0)
        v_kanan.setSpacing(8)

        # Tabel Hasil
        g_hasil = QGroupBox("Peringkat kandidat penapisan")
        v_hasil = QVBoxLayout(g_hasil)
        self.tabel_hasil = kit.tabel(["#", "Senyawa", "Cocok", "RMSD (Å)", "Bentuk", "Warna", "Skor"], urut=True)
        self.tabel_hasil.itemSelectionChanged.connect(self._pilih_hasil_tabel)
        v_hasil.addWidget(self.tabel_hasil)
        v_kanan.addWidget(g_hasil, 1)

        # Kartu Validasi Kueri
        g_val = QGroupBox("Validasi diskriminasi kueri (Aktif vs Decoy)")
        v_val = QVBoxLayout(g_val)
        self.k_auc = kit.Kartu("ROC-AUC", "–", "daya pembeda")
        self.k_bedroc = kit.Kartu("BEDROC (α=20)", "–", "pengayaan awal")
        self.k_ef1 = kit.Kartu("EF 1%", "–", "faktor 1%")
        v_val.addLayout(kit.baris_kartu(self.k_auc, self.k_bedroc, self.k_ef1))
        h_val = QHBoxLayout()
        self.lbl_info_val = QLabel("")
        self.lbl_info_val.setWordWrap(True)
        self.lbl_info_val.setStyleSheet("color: #777; font-size: 11px;")
        h_val.addWidget(self.lbl_info_val, 1)
        v_val.addLayout(h_val)
        h_val_btn = QHBoxLayout()
        self.btn_val_chembl = kit.tombol("Aktif dari ChEMBL…", self._aktif_dari_chembl,
                                         tip="Aktif pChEMBL ≥ 7, beragam kerangka (Butina 0,6), maks. 30")
        self.btn_val_csv = kit.tombol("Aktif dari CSV…", self._aktif_dari_csv, tip="Kolom: smiles[,nama]")
        h_val_btn.addWidget(self.btn_val_chembl)
        h_val_btn.addWidget(self.btn_val_csv)
        h_val_btn.addStretch()
        v_val.addLayout(h_val_btn)
        v_kanan.addWidget(g_val)

        split.addWidget(w_kanan)

        split.setStretchFactor(0, 30)
        split.setStretchFactor(1, 35)
        split.setStretchFactor(2, 35)
        layout.addWidget(split, 1)

        # Bar tombol bawah
        b_ekspor = kit.tombol("Ekspor SDF terselaraskan…", self._ekspor_sdf)
        b_metode = kit.tombol("Salin paragraf metode", self._salin_metode)
        b_docking = kit.tombol("Kirim teratas ke docking", self._kirim_ke_docking, utama=True)

        layout.addLayout(kit.bar_bawah(
            self,
            kiri=[b_ekspor, b_metode],
            kanan=[b_docking],
            tutup=True
        ))

    def _inisialisasi_sumber(self):
        """Isi opsi pose kueri dari konteks proyek."""
        # Tahan sinyal: tanpa ini addItem pertama memicu _ganti_sumber sehingga kueri
        # diekstrak dua kali (dan tabel fitur diisi ulang dua kali).
        self.cb_sumber.blockSignals(True)
        self.cb_sumber.clear()

        # Opsi 1: Pose aktif di jendela utama
        pose_aktif = kit.pose_aktif(self.jw) if self.jw else None
        if pose_aktif:
            self.cb_sumber.addItem("Pose aktif di penampil", ("aktif", pose_aktif))

        # Opsi 2: ligan ko-kristal (pose eksperimental). Ligan proyek lain tidak ditawarkan:
        # koordinatnya hanya konformer hasil embedding, bukan pose terikat, sehingga farmakofor
        # darinya tidak bermakna. Pose docking dipakai lewat "Pose aktif di penampil".
        if self.proyek:
            for lig in getattr(self.proyek, "ligan", []):
                if lig.get("ligan_asli") or lig.get("kristal") or lig.get("ko_kristal"):
                    self.cb_sumber.addItem(f"Ligan ko-kristal: {lig.get('nama')}", ("proyek_lig", lig))

        # Opsi bawaan fallback contoh bila proyek kosong
        p_contoh = Path("dev/uji/cli/vina/pose/MK1_902_B_terbaik.sdf")
        if p_contoh.exists():
            self.cb_sumber.addItem("Contoh MK1 (1HSG)", ("berkas", str(p_contoh)))

        if self.cb_sumber.count() == 0:
            self.cb_sumber.addItem("Belum ada ligan 3D", None)

        self.cb_sumber.blockSignals(False)
        self._ganti_sumber(0)
        self._cek_validasi_proyek()

    def _ganti_sumber(self, idx):
        data = self.cb_sumber.currentData()
        mol = None
        if data:
            jenis, obj = data
            try:
                if jenis == "aktif":
                    mol = prep_ligan.mol_dari(obj.teks, obj.fmt)
                elif jenis == "proyek_lig":
                    berkas = obj.get("sdf") or obj.get("pdbqt")
                    p = Path(self.proyek.folder) / berkas if berkas else None
                    if p and p.exists():
                        mol = prep_ligan.mol_dari(p.read_text(encoding="utf-8", errors="replace"),
                                                  "pdbqt" if p.suffix.lower() == ".pdbqt" else "sdf")
                elif jenis == "berkas":
                    mol = next(iter(Chem.SDMolSupplier(obj, removeHs=False)), None)
            except Exception as e:
                catat.log.debug(f"Ligan acuan tak terbaca: {e}")

        if mol is not None and mol.GetNumConformers() > 0:
            self._ref_mol = mol
            self.lbl_status.setText("")
            self._ekstrak_kueri()
            return
        # Jangan biarkan kueri ligan sebelumnya tampil seolah milik ligan yang baru dipilih
        self._ref_mol = None
        self._kueri = None
        self._isi_tabel_fitur()
        if hasattr(self.viewer, "js"):
            self.viewer.js("hapusFarmakofor")
            self.viewer.hapus("kueri_ref")
            self.viewer.hapus("kandidat_terpilih")
        self._versi_kueri += 1
        self._cek_validasi_proyek()
        self.lbl_status.setText("Ligan terpilih tidak dapat dibaca sebagai struktur 3D.")

    def _ekstrak_kueri(self):
        if self._ref_mol is None:
            return

        protein = None
        if self.chk_eksklusi.isChecked() and self.jw is not None and hasattr(self.jw, "_reseptor_objek"):
            protein = kit.reseptor_proyek(self.jw)[0] or None

        try:
            self._kueri = farmakofor.kueri_dari_pose(
                self._ref_mol,
                protein=protein,
                toleransi=1.0,
                eksklusi=self.chk_eksklusi.isChecked()
            )
            self._isi_tabel_fitur()
            self._perbarui_viewer_kueri()
            self._versi_kueri += 1
            self._cek_validasi_proyek()
            n_eks = len(self._kueri["eksklusi"])
            if self.chk_eksklusi.isChecked() and not protein:
                ket = "tanpa bola eksklusi (proyek belum memiliki reseptor)"
            else:
                ket = f"{n_eks} bola eksklusi"
            self.lbl_status.setText(f"Kueri: {len(self._kueri['fitur'])} fitur, {ket}.")
        except Exception as e:
            catat.log.error(f"Gagal ekstrak kueri: {e}")
            self.lbl_status.setText(f"Kueri gagal dibuat: {e}")

    def _isi_tabel_fitur(self):
        fitur = self._kueri.get("fitur", []) if self._kueri else []
        self.tabel_fitur.blockSignals(True)
        # Widget sel lama baru dihapus Qt lewat deleteLater; sembunyikan dulu agar tidak
        # tertinggal tergambar di atas baris baru.
        for r in range(self.tabel_fitur.rowCount()):
            for c in (0, 2):
                w = self.tabel_fitur.cellWidget(r, c)
                if w:
                    w.hide()
        self.tabel_fitur.setRowCount(0)
        self.tabel_fitur.setRowCount(len(fitur))

        for row, f in enumerate(fitur):
            # Kolom 0: Centang aktif
            w_chk = QWidget()
            l_chk = QHBoxLayout(w_chk)
            l_chk.setContentsMargins(0, 0, 0, 0)
            l_chk.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(f.get("aktif", True))
            chk.toggled.connect(lambda val, r=row: self._toggle_fitur(r, val))
            l_chk.addWidget(chk)
            self.tabel_fitur.setCellWidget(row, 0, w_chk)

            # Kolom 1: Fitur (pusat X, Y, Z di tooltip)
            xyz = f.get("xyz", [0, 0, 0])
            it_fam = QTableWidgetItem(f.get("nama") or f.get("famili"))
            it_fam.setForeground(kit.QColor(f.get("warna", "#333333")))
            it_fam.setFlags(it_fam.flags() & ~Qt.ItemIsEditable)
            it_fam.setToolTip(f"Pusat: {kit.f(xyz[0], 2)}; {kit.f(xyz[1], 2)}; {kit.f(xyz[2], 2)} Å")
            self.tabel_fitur.setItem(row, 1, it_fam)

            # Kolom 2: Spin Toleransi
            sp = QDoubleSpinBox()
            sp.setToolTip("Jari-jari bola toleransi fitur ini, dalam ångström. Makin kecil makin ketat: 1,0 Å menuntut penempatan yang rapat, 2,0 Å memberi kelonggaran untuk fleksibilitas konformasi. Melonggarkan semua fitur sekaligus membuat hampir semua senyawa lolos.")
            sp.setRange(0.5, 3.0)
            sp.setSingleStep(0.1)
            sp.setValue(f.get("toleransi", 1.0))
            sp.valueChanged.connect(lambda val, r=row: self._ubah_toleransi(r, val))
            self.tabel_fitur.setCellWidget(row, 2, sp)

        self.tabel_fitur.blockSignals(False)

    def _toggle_fitur(self, idx: int, aktif: bool):
        if self._kueri and idx < len(self._kueri.get("fitur", [])):
            self._kueri["fitur"][idx]["aktif"] = aktif
            self._kueri["n_fitur_aktif"] = sum(1 for f in self._kueri["fitur"] if f.get("aktif", True))
            self._perbarui_viewer_kueri()
            self._versi_kueri += 1
            self._cek_validasi_proyek()

    def _ubah_toleransi(self, idx: int, tol: float):
        if self._kueri and idx < len(self._kueri.get("fitur", [])):
            self._kueri["fitur"][idx]["toleransi"] = tol
            self._perbarui_viewer_kueri()
            self._versi_kueri += 1
            self._cek_validasi_proyek()

    def _pilih_semua_fitur(self):
        for r in range(self.tabel_fitur.rowCount()):
            w = self.tabel_fitur.cellWidget(r, 0)
            chk = w.findChild(QCheckBox) if w else None
            if chk:
                chk.setChecked(True)

    def _kosongkan_fitur(self):
        for r in range(self.tabel_fitur.rowCount()):
            w = self.tabel_fitur.cellWidget(r, 0)
            chk = w.findChild(QCheckBox) if w else None
            if chk:
                chk.setChecked(False)

    def _update_label_bobot(self, val):
        farma_pct = val
        bentuk_pct = 100 - val
        self.lbl_bobot.setText(f"{farma_pct} % Farmakofor : {bentuk_pct} % Bentuk-Warna")

    def _saat_viewer_siap(self):
        self._perbarui_viewer_kueri()

    def _perbarui_viewer_kueri(self):
        if not self._kueri or not hasattr(self.viewer, "js"):
            return
        self.viewer.js("hapusFarmakofor")

        # Muat molekul acuan
        ref_mol = self._kueri.get("ref_mol")
        if ref_mol is not None:
            self._tampil_ligan("kueri_ref", "Ligan acuan", ref_mol, "#3a9bb5")

        daftar_kirim = []
        if self.chk_tampil_farma.isChecked():
            for f in self._kueri.get("fitur", []):
                if f.get("aktif", True):
                    daftar_kirim.append(f)

        if self.chk_tampil_eksklusi.isChecked():
            for e in self._kueri.get("eksklusi", []):
                daftar_kirim.append(e)

        if daftar_kirim:
            self.viewer.js("tampilFarmakofor", daftar_kirim, {"label": True})

    def _tampil_ligan(self, oid: str, nama: str, mol_atau_sdf, karbon: str):
        """Muat ligan (Mol atau blok SDF) ke penampil sebagai batang berwarna unsur."""
        try:
            sdf = mol_atau_sdf if isinstance(mol_atau_sdf, str) else Chem.MolToMolBlock(mol_atau_sdf)
        except Exception as e:
            catat.log.debug(f"Ligan {nama} tak dapat ditulis sebagai SDF: {e}")
            return
        obj = molekul.Objek(id=oid, nama=nama, jenis="ligan", teks=sdf, fmt="sdf")
        self.viewer.muat(obj)
        self.viewer.tampil(obj, {"layers": [{"rep": "sticks", "radius": 0.18,
                                             "color": {"mode": "element", "carbon": karbon}}]})

    def _cek_validasi_proyek(self):
        """Kosongkan kartu validasi; dipanggil tiap kali kueri berubah karena angka lama tak berlaku lagi.

        Skor enrichment docking dari Validasi protokol sengaja tidak ditampilkan di sini:
        angka itu menilai fungsi skor docking, bukan kueri farmakofor ini."""
        self._val_terakhir = None
        for k, sub in ((self.k_auc, "daya pembeda"), (self.k_bedroc, "pengayaan awal"), (self.k_ef1, "faktor 1%")):
            k.isi("–", sub)
        siap = self._kueri is not None and not self._val_sibuk
        self.btn_val_chembl.setEnabled(siap)
        self.btn_val_csv.setEnabled(siap)
        if self._aktif_val:
            self.lbl_info_val.setText(f"{len(self._aktif_val)} aktif termuat; kueri berubah, muat ulang aktif "
                                      "untuk menilai kueri saat ini.")
        else:
            self.lbl_info_val.setText("Muat senyawa aktif target (ChEMBL atau CSV); decoy sepadan gaya DUD-E "
                                      "dibangkitkan otomatis lalu kueri dinilai.")

    def _aktif_dari_chembl(self):
        target, ok = QInputDialog.getText(self, "Aktif dari ChEMBL",
                                          "ID atau nama target ChEMBL (mis. CHEMBL243):")
        if not ok or not target.strip():
            return
        self._mulai_validasi(f"Mengambil aktif {target.strip()} dari ChEMBL…",
                             lambda lapor: decoy.pilih_aktif(target.strip(), pchembl_min=7.0, maks=30, lapor=lapor))

    def _aktif_dari_csv(self):
        f, _ = QFileDialog.getOpenFileName(self, "Aktif dari CSV", "", "CSV (*.csv *.txt)")
        if not f:
            return
        daftar = []
        try:
            with open(f, newline="", encoding="utf-8-sig") as fh:
                for baris in csv.reader(fh):
                    if not baris or not baris[0].strip() or baris[0].strip().lower() == "smiles":
                        continue
                    if Chem.MolFromSmiles(baris[0].strip()) is None:
                        continue
                    daftar.append({"smiles": baris[0].strip(),
                                   "nama": baris[1].strip() if len(baris) > 1 else f"aktif_{len(daftar) + 1}"})
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            self.lbl_info_val.setText(f"CSV tidak terbaca: {e}")
            return
        if len(daftar) < 3:
            self.lbl_info_val.setText("CSV berisi kurang dari 3 SMILES valid (kolom: smiles[,nama]).")
            return
        self._mulai_validasi(f"{len(daftar)} aktif dari CSV…", lambda lapor: daftar)

    def _mulai_validasi(self, pesan, ambil_aktif):
        """Latar: ambil aktif -> decoy DUD-E dari pustaka lokal -> nilai kueri saat ini."""
        kueri = dict(self._kueri)
        kueri["fitur"] = [dict(f) for f in self._kueri.get("fitur", [])]
        bobot = self.sl_bobot.value() / 100.0
        versi = self._versi_kueri

        def _kerja(lapor=None):
            aktif = ambil_aktif(lapor)
            if len(aktif) < 3:
                raise ValueError(f"Hanya {len(aktif)} senyawa aktif; butuh minimal 3.")
            if lapor:
                lapor.log.emit(f"Membangkitkan decoy untuk {len(aktif)} aktif…")
            hd = decoy.buat_decoy(aktif, per_aktif=30, lapor=lapor)
            if len(hd["decoy"]) < 2:
                raise ValueError("Pustaka lokal tidak menghasilkan decoy sepadan.")
            if lapor:
                lapor.log.emit(f"Menilai {len(aktif)} aktif dan {len(hd['decoy'])} decoy terhadap kueri…")
            res = farmakofor.validasi_kueri(kueri, aktif, hd["decoy"], bobot_farma=bobot,
                                            bobot_bentuk=1.0 - bobot, konf_per_mol=10)
            res["aktif"] = aktif
            res["peringatan_decoy"] = hd.get("peringatan", [])
            res["versi"] = versi
            return res

        self._val_sibuk = True
        self.btn_val_chembl.setEnabled(False)
        self.btn_val_csv.setEnabled(False)
        self.lbl_info_val.setText(pesan)
        self._kerja_val = kerja.jalankan(_kerja, selesai=self._saat_validasi, galat=self._saat_validasi_galat,
                                         log=self.lbl_info_val.setText)

    def _saat_validasi(self, res):
        self._val_sibuk = False
        self._aktif_val = res.get("aktif") or []
        self._cek_validasi_proyek()
        if res.get("versi") != self._versi_kueri:
            return  # kueri diubah selama validasi berjalan; petunjuk muat ulang sudah ditampilkan
        if res.get("auc") is None:
            self.lbl_info_val.setText(res.get("pesan", "Validasi gagal."))
            return
        self._val_terakhir = res
        self.k_auc.isi(kit.f(res["auc"], 3), "daya pembeda")
        self.k_bedroc.isi(kit.f(res["bedroc"], 3), "pengayaan awal")
        if res.get("ef1") is not None:
            self.k_ef1.isi(f"{kit.f(res['ef1'], 1)}×", "faktor 1%")
        else:
            self.k_ef1.isi("–", "butuh ≥ 100 senyawa")
        pesan = res["pesan"]
        if res.get("peringatan_decoy"):
            pesan += " " + " ".join(res["peringatan_decoy"][:1])
        self.lbl_info_val.setText(pesan)

    def _saat_validasi_galat(self, teks):
        self._val_sibuk = False
        self._cek_validasi_proyek()
        self.lbl_info_val.setText(f"Validasi gagal: {teks.splitlines()[0]}")

    def _kumpulkan_pustaka(self) -> List[Dict[str, Any]]:
        mode = self.cb_pustaka.currentData()
        daftar = []

        if mode == "obat":
            daftar = pustaka.obat()
        elif mode == "coconut":
            daftar = pustaka.cari_coconut(batas=2000)
        elif mode == "proyek" and self.proyek:
            for lig in getattr(self.proyek, "ligan", []):
                smi = self.proyek.smiles_ligan(lig) if hasattr(self.proyek, "smiles_ligan") else lig.get("smiles")
                if smi:
                    daftar.append({"nama": lig.get("nama", "Ligan"), "smiles": smi})
        elif mode == "berkas":
            p, _ = QFileDialog.getOpenFileName(
                self, "Pilih berkas pustaka", "", "Struktur Kimia (*.sdf *.mol *.smi *.txt)"
            )
            if p:
                if p.endswith((".sdf", ".mol")):
                    suppl = Chem.SDMolSupplier(p)
                    for i, m in enumerate(suppl):
                        if m:
                            nm = m.GetProp("_Name") if m.HasProp("_Name") else f"Senyawa_{i+1}"
                            daftar.append({"nama": nm, "mol": m})
                else:
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f):
                            parts = line.strip().split()
                            if parts:
                                s = parts[0]
                                nm = parts[1] if len(parts) > 1 else f"Senyawa_{i+1}"
                                daftar.append({"nama": nm, "smiles": s})

        return daftar

    def _mulai_saring(self):
        if not self._kueri:
            self.lbl_status.setText("Silakan siapkan kueri farmakofor terlebih dahulu.")
            return

        daftar = self._kumpulkan_pustaka()
        if not daftar:
            self.lbl_status.setText("Pustaka senyawa kosong atau tidak dapat dimuat.")
            return

        bobot_farma = self.sl_bobot.value() / 100.0
        bobot_bentuk = 1.0 - bobot_farma
        konf = self.sp_konf.value()

        self.btn_saring.setEnabled(False)
        self.btn_batal.setEnabled(True)
        self.prog_bar.setVisible(True)
        self.prog_bar.setRange(0, len(daftar))
        self.prog_bar.setValue(0)
        self.lbl_status.setText(f"Menapis {len(daftar):,} senyawa...")

        self._utas = _UtasPenapisan(self._kueri, daftar, bobot_farma, bobot_bentuk, konf)
        self._utas.progresSignal.connect(self._saat_progres)
        self._utas.selesaiSignal.connect(self._saat_selesai)
        self._utas.start()

    def _batal_saring(self):
        if self._utas and self._utas.isRunning():
            self._utas.batal()
            self.lbl_status.setText("Membatalkan penapisan...")
            self.btn_batal.setEnabled(False)

    def _saat_progres(self, selesai, total, pesan):
        self.prog_bar.setValue(selesai)
        self.lbl_status.setText(pesan)

    def _saat_selesai(self, hasil, pesan):
        self.btn_saring.setEnabled(True)
        self.btn_batal.setEnabled(False)
        self.prog_bar.setVisible(False)
        self._hasil_terakhir = hasil

        if pesan:
            self.lbl_status.setText(pesan)
        else:
            self.lbl_status.setText(f"Penapisan tuntas: {len(hasil):,} kandidat berhasil diperingkat.")

        self._isi_tabel_hasil()

    def _isi_tabel_hasil(self):
        self.tabel_hasil.setRowCount(len(self._hasil_terakhir))
        self.tabel_hasil.blockSignals(True)

        for row, h in enumerate(self._hasil_terakhir):
            # 0: Rank
            self.tabel_hasil.setItem(row, 0, kit.sel_angka(h.get("rank", row + 1), d=0))

            # 1: Nama Senyawa
            it_nama = QTableWidgetItem(str(h.get("nama", "Senyawa")))
            it_nama.setFlags(it_nama.flags() & ~Qt.ItemIsEditable)
            self.tabel_hasil.setItem(row, 1, it_nama)

            # 2: Fitur Cocok
            n_c = h.get("n_cocok", 0)
            n_a = h.get("n_aktif", 0)
            it_cocok = QTableWidgetItem(f"{n_c} / {n_a}")
            it_cocok.setTextAlignment(Qt.AlignCenter)
            it_cocok.setFlags(it_cocok.flags() & ~Qt.ItemIsEditable)
            self.tabel_hasil.setItem(row, 2, it_cocok)

            # 3: RMSD Fitur
            rmsd = h.get("rmsd_fitur")
            self.tabel_hasil.setItem(row, 3, kit.sel_angka(rmsd, d=2) if rmsd is not None else QTableWidgetItem("–"))

            # 4: Tanimoto Bentuk
            self.tabel_hasil.setItem(row, 4, kit.sel_angka(h.get("tanimoto_bentuk"), d=3))

            # 5: Tanimoto Warna
            self.tabel_hasil.setItem(row, 5, kit.sel_angka(h.get("tanimoto_warna"), d=3))

            # 6: Skor Akhir
            self.tabel_hasil.setItem(row, 6, kit.sel_angka(h.get("skor_akhir"), d=3))

        self.tabel_hasil.blockSignals(False)

    def _pilih_hasil_tabel(self):
        rows = self.tabel_hasil.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        if row >= len(self._hasil_terakhir):
            return

        h = self._hasil_terakhir[row]
        sdf_teks = h.get("sdf")
        if sdf_teks:
            self._tampil_ligan("kandidat_terpilih", h.get("nama", "Kandidat"), sdf_teks, "#2e9d5b")

    def _ekspor_sdf(self):
        if not self._hasil_terakhir:
            self.lbl_status.setText("Belum ada hasil penapisan untuk diekspor.")
            return

        p, _ = QFileDialog.getSaveFileName(self, "Simpan SDF terselaraskan", "kandidat_terselaraskan.sdf", "SDF (*.sdf)")
        if not p:
            return

        n_tulis = 0
        with open(p, "w", encoding="utf-8") as f:
            for h in self._hasil_terakhir:
                sdf = h.get("sdf")
                if sdf:
                    f.write(sdf.strip() + "\n$$$$\n")
                    n_tulis += 1

        self.lbl_status.setText(f"Berhasil mengekspor {n_tulis} molekul terselaraskan ke {Path(p).name}.")

    def _salin_metode(self):
        if not self._kueri:
            self.lbl_status.setText("Siapkan kueri farmakofor terlebih dahulu.")
            return
        fitur = self._kueri.get("fitur", [])
        aktif = [f for f in fitur if f.get("aktif", True)]
        tol = sorted({round(float(f.get("toleransi", 1.0)), 2) for f in aktif}) or [1.0]
        tol_teks = (f"{kit.f(tol[0], 1)} Å" if len(tol) == 1 else f"{kit.f(tol[0], 1)}–{kit.f(tol[-1], 1)} Å")
        n_eks = len(self._kueri.get("eksklusi", []))
        bf = self.sl_bobot.value() / 100.0
        from .. import i18n
        if i18n.inggris():
            teks = self._metode_en(aktif, fitur, tol, n_eks, bf)
            kit.salin(teks)
            self.lbl_status.setText("Paragraf metode disalin ke papan klip.")
            return
        eksklusi_teks = (f", ditambah {n_eks} bola volume eksklusi dari atom berat protein dalam radius 4,0 Å"
                         if n_eks else "")

        teks = (
            "Penapisan virtual berbasis ligan 3D dilakukan dengan modul farmakofor dan bentuk VirmoLab (RDKit). "
            f"Kueri farmakofor diekstraksi dari pose acuan dengan definisi fitur BaseFeatures.fdef; "
            f"{len(aktif)} dari {len(fitur)} fitur dipakai dengan toleransi spasial {tol_teks}{eksklusi_teks}. "
            f"Tiap senyawa pustaka dibangkitkan hingga {self.sp_konf.value()} konformer ETKDGv3 (pemangkasan "
            "RMSD 0,5 Å), lalu tiap konformer diselaraskan rigid ke ligan acuan dengan rdShapeAlign "
            "(Tanimoto bentuk dan warna). Skor akhir adalah rata-rata berbobot "
            f"{kit.f(bf, 2)} skor farmakofor (fraksi fitur cocok × presisi jarak, dikurangi penalti bentrok "
            f"eksklusi) dan {kit.f(1.0 - bf, 2)} skor bentuk-warna; konformer dengan skor tertinggi dilaporkan."
        )
        v = self._val_terakhir
        if v and v.get("auc") is not None:
            teks += (f" Daya pembeda kueri diuji pada {v['n_aktif']} senyawa aktif dan {v['n_decoy']} decoy: "
                     f"ROC-AUC {kit.f(v['auc'], 3)}, BEDROC (α = 20) {kit.f(v['bedroc'], 3)}")
            if v.get("ef1") is not None:
                teks += f", EF1% {kit.f(v['ef1'], 1)}"
            teks += "."
        teks += " Peringkat penapisan adalah hipotesis yang perlu dikonfirmasi dengan docking dan uji eksperimen."

        kit.salin(teks)
        self.lbl_status.setText("Paragraf metode disalin ke papan klip.")

    def _metode_en(self, aktif, fitur, tol, n_eks, bf):
        """Versi Inggris paragraf metode di atas, dengan angka dan syarat kalimat yang sama."""
        tol_teks = f"{tol[0]:.1f} Å" if len(tol) == 1 else f"{tol[0]:.1f}–{tol[-1]:.1f} Å"
        teks = (
            "Ligand-based 3D virtual screening was performed with the VirmoLab pharmacophore and shape module "
            "(RDKit). The pharmacophore query was extracted from the reference pose using the BaseFeatures.fdef "
            f"feature definitions; {len(aktif)} of {len(fitur)} features were used with a spatial tolerance of "
            f"{tol_teks}"
            + (f", plus {n_eks} excluded-volume spheres from protein heavy atoms within 4.0 Å" if n_eks else "")
            + f". Up to {self.sp_konf.value()} ETKDGv3 conformers (RMSD pruning 0.5 Å) were generated for each "
            "library compound, and each conformer was rigidly aligned to the reference ligand with rdShapeAlign "
            f"(shape and colour Tanimoto). The final score is the weighted mean of {bf:.2f} pharmacophore score "
            "(fraction of matched features × distance precision, minus an excluded-volume clash penalty) and "
            f"{1.0 - bf:.2f} shape–colour score; the highest-scoring conformer is reported."
        )
        v = self._val_terakhir
        if v and v.get("auc") is not None:
            teks += (f" Query discrimination was tested on {v['n_aktif']} actives and {v['n_decoy']} decoys: "
                     f"ROC-AUC {v['auc']:.3f}, BEDROC (α = 20) {v['bedroc']:.3f}")
            if v.get("ef1") is not None:
                teks += f", EF1% {v['ef1']:.1f}"
            teks += "."
        return teks + " Screening ranks are hypotheses that must be confirmed by docking and experimental assays."

    def _kirim_ke_docking(self):
        """Tambahkan senyawa teratas sebagai ligan di jendela utama lalu buka Siapkan ligan.

        Jalur ini sama dengan impor ligan biasa: protonasi dan PDBQT dibuat di dialog Siapkan
        ligan, sehingga docking tidak berjalan dengan ligan setengah jadi."""
        if not self._hasil_terakhir:
            self.lbl_status.setText("Belum ada kandidat untuk dikirim ke docking.")
            return
        if self.jw is None or not hasattr(self.jw, "tambah_objek"):
            self.lbl_status.setText("Buka dialog ini dari jendela utama untuk mengirim kandidat ke docking.")
            return
        bisa = [h for h in self._hasil_terakhir if h.get("smiles")]
        if not bisa:
            self.lbl_status.setText("Kandidat tidak memiliki SMILES sehingga tidak dapat dikirim.")
            return
        n, ok = QInputDialog.getInt(
            self, "Kirim ke docking",
            "Jumlah senyawa teratas yang ditambahkan sebagai ligan:",
            min(20, len(bisa)), 1, min(100, len(bisa)), 1
        )
        if not ok:
            return
        terpilih = bisa[:n]
        self.lbl_status.setText(f"Membangun struktur 3D {n} senyawa…")

        def _bangun(lapor=None):
            objs, gagal = [], []
            for h in terpilih:
                try:
                    for o in molekul.dari_smiles(h["smiles"], h.get("nama") or "Hit_F4"):
                        o.tampil = False
                        o.info["skor_f4"] = h.get("skor_akhir")
                        objs.append(o)
                except Exception:
                    gagal.append(h.get("nama") or h["smiles"])
            return objs, gagal

        def _selesai(hasil):
            objs, gagal = hasil
            if objs:
                self.jw.tambah_objek(objs, fokus=False)
            pesan = f"{len(objs)} senyawa ditambahkan sebagai ligan."
            if gagal:
                pesan += f" {len(gagal)} gagal dibangun: {', '.join(gagal[:5])}."
            self.lbl_status.setText(pesan)
            if objs and hasattr(self.jw, "siapkan_ligan"):
                self.jw.siapkan_ligan()

        self._kerja_kirim = kerja.jalankan(
            _bangun, selesai=_selesai,
            galat=lambda t: self.lbl_status.setText(f"Gagal menyiapkan kandidat: {t.splitlines()[0]}"))
