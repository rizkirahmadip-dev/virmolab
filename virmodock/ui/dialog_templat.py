"""Dialog Proyek baru dari templat (Berkas › Proyek baru dari templat…)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QFormLayout, QVBoxLayout)

from ..core import templat as T


class DialogTemplat(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Proyek baru dari templat")
        self.resize(640, 520)
        v = QVBoxLayout(self)
        ket = QLabel("Pilih titik mulai. Templat mengatur ketelitian docking yang sesuai, membuka langkah pertama, "
                     "dan menampilkan daftar langkah di panel Pesan.")
        ket.setWordWrap(True)
        ket.setObjectName("muted")
        v.addWidget(ket)
        self.daftar = QListWidget()
        self.daftar.setWordWrap(True)
        self.daftar.setSpacing(3)
        for t in T.TEMPLAT:
            it = QListWidgetItem(f"{t['judul']}\n{t['ket']}  ·  ketelitian {t['preset']}")
            it.setData(Qt.UserRole, t["kunci"])
            it.setToolTip("\n".join(f"{i + 1}. {s}" for i, s in enumerate(t["langkah"])))
            self.daftar.addItem(it)
        self.daftar.setCurrentRow(0)
        self.daftar.currentItemChanged.connect(self._nama_bawaan)
        self.daftar.itemDoubleClicked.connect(lambda *_: self.accept())
        v.addWidget(self.daftar, 1)
        f = QFormLayout()
        self.nama = QLineEdit()
        f.addRow("Nama proyek", self.nama)
        v.addLayout(f)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Buat proyek")
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText("Batal")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._nama_bawaan()

    def _nama_bawaan(self, *_):
        from datetime import datetime
        t = T.cari(self.kunci())
        if t:
            dasar = "Contoh_HIV_protease" if t["kunci"] == "contoh" else t["judul"].replace(" ", "_")
            self.nama.setText(f"{dasar}_{datetime.now():%Y%m%d_%H%M}")

    def kunci(self):
        it = self.daftar.currentItem()
        return it.data(Qt.UserRole) if it else None
