"""Dialog Desain Obat Berbasis Fragmen (Fragment-Based Drug Design / FBDD)."""
import csv
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from ..core import fbdd
from . import kit


def _sel(t, angka=None, align_right=False):
    it = QTableWidgetItem(str(t) if t is not None else "-")
    if angka is not None:
        it.setData(Qt.UserRole, angka)
    if align_right or angka is not None:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


class DialogFBDD(QDialog):
    liganDiimpor = Signal(str, str)   # nama, SMILES

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.proyek = jw.proyek
        self.setWindowTitle("Desain berbasis fragmen (FBDD)")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1180, 720)

        self.hasil_turunan = []

        lay_utama = QVBoxLayout(self)
        lay_utama.setContentsMargins(12, 12, 12, 12)
        lay_utama.setSpacing(8)

        # Bilah mode pemilihan strategi
        self.tabs_strategi = QTabWidget()

        # =====================================================================
        # TAB 1: Fragment Growing
        # =====================================================================
        w_grow = QWidget()
        lay_g = QVBoxLayout(w_grow)
        lay_g.setContentsMargins(8, 8, 8, 8)

        bar_in_g = QHBoxLayout()
        bar_in_g.addWidget(QLabel("Fragmen Awal (SMILES):"))
        self.e_smiles_grow = QLineEdit("c1ccccc1O")
        bar_in_g.addWidget(self.e_smiles_grow, 2)

        # Tombol pilih dari ligan proyek
        self.cb_lig_proyek_g = QComboBox()
        self.cb_lig_proyek_g.addItem("Pilih dari Ligan Proyek…", None)
        for l in kit.ligan_proyek(jw, dengan_mol=False):
            self.cb_lig_proyek_g.addItem(l["nama"], l["smiles"])
        self.cb_lig_proyek_g.currentIndexChanged.connect(self._isi_smiles_dari_proyek_g)
        bar_in_g.addWidget(self.cb_lig_proyek_g, 1)

        b_tumbuh = QPushButton("Kembangkan Fragmen (Growing)")
        b_tumbuh.setObjectName("primary")
        b_tumbuh.clicked.connect(self._jalankan_growing)
        bar_in_g.addWidget(b_tumbuh)
        lay_g.addLayout(bar_in_g)

        self.tabs_strategi.addTab(w_grow, "1. Fragment Growing (Penambahan Substituen)")

        # =====================================================================
        # TAB 2: Fragment Linking
        # =====================================================================
        w_link = QWidget()
        lay_l = QVBoxLayout(w_link)
        lay_l.setContentsMargins(8, 8, 8, 8)

        bar_in_l = QHBoxLayout()
        bar_in_l.addWidget(QLabel("Fragmen 1:"))
        self.e_smiles_l1 = QLineEdit("c1ccccc1")
        bar_in_l.addWidget(self.e_smiles_l1, 1)

        bar_in_l.addWidget(QLabel("Fragmen 2:"))
        self.e_smiles_l2 = QLineEdit("c1ccncc1")
        bar_in_l.addWidget(self.e_smiles_l2, 1)

        b_sambung = QPushButton("Sambungkan Fragmen (Linking)")
        b_sambung.setObjectName("primary")
        b_sambung.clicked.connect(self._jalankan_linking)
        bar_in_l.addWidget(b_sambung)
        lay_l.addLayout(bar_in_l)

        self.tabs_strategi.addTab(w_link, "2. Fragment Linking (Penyambungan Rantai)")

        lay_utama.addWidget(self.tabs_strategi)

        # Bagian Bawah: Tabel Hasil Turunan FBDD
        self.l_info = QLabel("Masukkan fragmen di atas lalu klik tombol proses.")
        self.l_info.setObjectName("subjudul")
        lay_utama.addWidget(self.l_info)

        self.tabel_hasil = QTableWidget()
        self.tabel_hasil.setColumnCount(9)
        self.tabel_hasil.setHorizontalHeaderLabels([
            "Nama Turunan", "Modifikasi", "SMILES", "MW (g/mol)", "WLOGP", "TPSA",
            "QED", "SA Score", "Lipinski"
        ])
        self.tabel_hasil.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabel_hasil.setSortingEnabled(True)
        self.tabel_hasil.setAlternatingRowColors(True)
        h = self.tabel_hasil.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        for c in range(3, 9):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        lay_utama.addWidget(self.tabel_hasil, 1)

        # Bilah Aksi Tombol
        bar_bawah = QHBoxLayout()
        b_impor = QPushButton("Impor Senyawa Terpilih ke Proyek")
        b_impor.setObjectName("primary")
        b_impor.clicked.connect(self._impor_ke_proyek)
        bar_bawah.addWidget(b_impor)

        b_salin = QPushButton("Salin SMILES Terpilih")
        b_salin.clicked.connect(self._salin_smiles)
        bar_bawah.addWidget(b_salin)

        b_csv = QPushButton("Ekspor CSV…")
        b_csv.clicked.connect(self._ekspor_csv)
        bar_bawah.addWidget(b_csv)

        bar_bawah.addStretch(1)
        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.close)
        bar_bawah.addWidget(b_tutup)
        lay_utama.addLayout(bar_bawah)

    def _isi_smiles_dari_proyek_g(self):
        smi = self.cb_lig_proyek_g.currentData()
        if smi:
            self.e_smiles_grow.setText(smi)

    def _jalankan_growing(self):
        with kit.sibuk(self.l_info, "Menumbuhkan fragmen…"):
            smi = self.e_smiles_grow.text().strip()
            if not smi:
                QMessageBox.warning(self, "SMILES Kosong", "Masukkan struktur SMILES fragmen awal.")
                return

            self.hasil_turunan = fbdd.tumbuhkan_fragmen(smi)
            self._perbarui_tabel()
            self.l_info.setText(f"Berhasil menghasilkan {len(self.hasil_turunan)} analog turunan FBDD Growing.")

    def _jalankan_linking(self):
        with kit.sibuk(self.l_info, "Menyambung fragmen…"):
            s1 = self.e_smiles_l1.text().strip()
            s2 = self.e_smiles_l2.text().strip()
            if not s1 or not s2:
                QMessageBox.warning(self, "SMILES Kosong", "Masukkan kedua struktur SMILES fragmen yang akan disambung.")
                return

            self.hasil_turunan = fbdd.sambung_fragmen(s1, s2)
            self._perbarui_tabel()
            self.l_info.setText(f"Berhasil menghasilkan {len(self.hasil_turunan)} molekul hibrida FBDD Linking.")

    def _perbarui_tabel(self):
        self.tabel_hasil.setSortingEnabled(False)
        self.tabel_hasil.setRowCount(len(self.hasil_turunan))

        for r, item in enumerate(self.hasil_turunan):
            self.tabel_hasil.setItem(r, 0, _sel(item["nama"]))
            self.tabel_hasil.setItem(r, 1, _sel(item["modifikasi"]))
            self.tabel_hasil.setItem(r, 2, _sel(item["smiles"]))
            self.tabel_hasil.setItem(r, 3, _sel(f"{item['mw']:.1f}", item["mw"], True))
            self.tabel_hasil.setItem(r, 4, _sel(f"{item['wlogp']:.2f}", item["wlogp"], True))
            self.tabel_hasil.setItem(r, 5, _sel(f"{item['tpsa']:.1f}", item["tpsa"], True))

            it_qed = _sel(f"{item['qed']:.2f}", item["qed"], True)
            if item["qed"] >= 0.7:
                it_qed.setForeground(kit.warna("ok"))
            self.tabel_hasil.setItem(r, 6, it_qed)

            it_sa = _sel(f"{item['sascore']:.2f}", item["sascore"], True)
            if item["sascore"] <= 3.0:
                it_sa.setForeground(kit.warna("ok"))  # Mudah
            elif item["sascore"] > 6.0:
                it_sa.setForeground(kit.warna("bad"))  # Sulit
            self.tabel_hasil.setItem(r, 7, it_sa)

            it_lip = _sel("Lolos" if item["lipinski_lolos"] else f"Gagal ({item['lipinski_pelanggaran']})")
            if item["lipinski_lolos"]:
                it_lip.setForeground(kit.warna("ok"))
            self.tabel_hasil.setItem(r, 8, it_lip)

        self.tabel_hasil.setSortingEnabled(True)

    def _impor_ke_proyek(self):
        rows = sorted({idx.row() for idx in self.tabel_hasil.selectedIndexes()})
        if not rows:
            self.l_info.setText("Pilih dulu baris senyawa yang ingin diimpor.")
            return
        n = 0
        for r in rows:
            if 0 <= r < len(self.hasil_turunan):
                it = self.hasil_turunan[r]
                self.liganDiimpor.emit(it["nama"], it["smiles"])
                n += 1
        self.l_info.setText(f"{n} senyawa dikirim ke daftar objek. Lanjutkan di Siapkan ligan untuk didocking.")

    def _salin_smiles(self):
        rows = sorted(list({idx.row() for idx in self.tabel_hasil.selectedIndexes()}))
        if not rows:
            return
        teks = "\n".join(self.hasil_turunan[r]["smiles"] for r in rows if 0 <= r < len(self.hasil_turunan))
        QGuiApplication.clipboard().setText(teks)
        QMessageBox.information(self, "Disalin", f"{len(rows)} SMILES disalin ke clipboard.")

    def _ekspor_csv(self):
        if not self.hasil_turunan:
            return
        jalur, _ = QFileDialog.getSaveFileName(self, "Simpan CSV FBDD", "turunan_fbdd.csv", "CSV (*.csv)")
        if not jalur:
            return
        try:
            with open(jalur, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["nama", "modifikasi", "smiles", "mw", "wlogp", "tpsa", "qed", "sascore", "lipinski"])
                for it in self.hasil_turunan:
                    writer.writerow([
                        it["nama"], it["modifikasi"], it["smiles"], it["mw"],
                        it["wlogp"], it["tpsa"], it["qed"], it["sascore"],
                        "Lolos" if it["lipinski_lolos"] else "Gagal"
                    ])
            QMessageBox.information(self, "Sukses", f"Berhasil mengekspor {len(self.hasil_turunan)} baris ke {jalur}")
        except Exception as e:
            QMessageBox.critical(self, "Galat", f"Gagal mengekspor CSV: {e}")
