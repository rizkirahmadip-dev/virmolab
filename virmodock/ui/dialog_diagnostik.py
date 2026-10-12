"""Dialog Pemeriksa Kesehatan Sistem (System Health Check & Diagnostic)."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout
)

from ..core import diagnostik
from . import kit


def _sel(t, angka=None, align_right=False):
    it = QTableWidgetItem(str(t) if t is not None else "-")
    if angka is not None:
        it.setData(Qt.UserRole, angka)
    if align_right or angka is not None:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


class DialogDiagnostik(QDialog):
    def __init__(self, jw=None):
        super().__init__(jw)
        self.setWindowTitle("Pemeriksa kesehatan sistem")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1000, 560)

        self.data_diag = []

        lay_utama = QVBoxLayout(self)
        lay_utama.setContentsMargins(12, 12, 12, 12)
        lay_utama.setSpacing(8)

        # Bilah atas
        bar_atas = QHBoxLayout()
        self.l_info = QLabel("Memeriksa seluruh dependensi dan kesiapan lingkungan komputer...")
        self.l_info.setObjectName("subjudul")
        bar_atas.addWidget(self.l_info, 1)

        b_uji_ulang = QPushButton("Uji Ulang Diagnostik")
        b_uji_ulang.clicked.connect(self._jalankan_diagnostik)
        bar_atas.addWidget(b_uji_ulang)
        lay_utama.addLayout(bar_atas)

        # Tabel hasil pemeriksaan
        self.tabel = QTableWidget()
        self.tabel.setColumnCount(5)
        self.tabel.setHorizontalHeaderLabels([
            "Komponen", "Status", "Versi / Detail", "Keterangan", "Saran / Solusi"
        ])
        self.tabel.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabel.setAlternatingRowColors(True)
        h = self.tabel.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        h.setSectionResizeMode(4, QHeaderView.Stretch)
        lay_utama.addWidget(self.tabel, 1)

        # Bilah bawah
        bar_bawah = QHBoxLayout()
        b_salin = QPushButton("Salin Laporan Diagnostik")
        b_salin.clicked.connect(self._salin_laporan)
        bar_bawah.addWidget(b_salin)

        bar_bawah.addStretch(1)
        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.accept)
        bar_bawah.addWidget(b_tutup)
        lay_utama.addLayout(bar_bawah)

        # Jalankan saat buka
        self._jalankan_diagnostik()

    def _jalankan_diagnostik(self):
        with kit.sibuk(self.l_info, "Memeriksa Python, RDKit, mesin docking, GPU, WSL, dan Ollama…"):
            self.data_diag = diagnostik.periksa_semua()
        self.tabel.setRowCount(len(self.data_diag))

        n_ok = sum(1 for d in self.data_diag if d["status"] == "ok")
        n_warn = sum(1 for d in self.data_diag if d["status"] == "warn")
        n_bad = sum(1 for d in self.data_diag if d["status"] == "bad")

        for r, item in enumerate(self.data_diag):
            self.tabel.setItem(r, 0, _sel(item["komponen"]))

            st = item["status"]
            if st == "ok":
                it_st = _sel("✓ Siap")
                it_st.setForeground(QColor("#16a34a"))
            elif st == "warn":
                it_st = _sel("ℹ Opsional")
                it_st.setForeground(QColor("#d97706"))
            else:
                it_st = _sel("✗ Belum Ada")
                it_st.setForeground(QColor("#dc2626"))
            it_st.setTextAlignment(Qt.AlignCenter)
            self.tabel.setItem(r, 1, it_st)

            self.tabel.setItem(r, 2, _sel(item["detail"]))
            self.tabel.setItem(r, 3, _sel(item["keterangan"]))
            self.tabel.setItem(r, 4, _sel(item["solusi"] or "-"))

        self.l_info.setText(
            f"Diagnostik Selesai: {n_ok} Komponen Siap | {n_warn} Komponen Opsional | {n_bad} Memerlukan Tindakan"
        )

    def _salin_laporan(self):
        t = diagnostik.ringkasan_teks_diagnostik()
        QGuiApplication.clipboard().setText(t)
        QMessageBox.information(self, "Disalin", "Laporan diagnostik berhasil disalin ke clipboard.")
