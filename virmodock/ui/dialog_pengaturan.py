"""Dialog Pengaturan Aplikasi VirmoDock."""

from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout
)

from ..core import paths, sumber_data
from . import kit


class DialogPengaturan(QDialog):
    """Dialog pengaturan umum: folder kerja, software eksternal, dan cache internet."""

    def __init__(self, jw=None):
        super().__init__(jw)
        self.jw = jw
        self.st = jw.st if jw and hasattr(jw, "st") else paths.settings()
        self.setWindowTitle("Pengaturan")
        self.setMinimumWidth(560)
        self.resize(620, 480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        lay.addWidget(kit.judul(
            "Pengaturan aplikasi",
            "Atur folder kerja bawaan, program visualisasi eksternal, dan kelola cache data internet."
        ))

        # 1. Folder kerja
        gb_folder = QGroupBox("Folder kerja")
        v_f = QVBoxLayout(gb_folder)
        h_f = QHBoxLayout()
        folder_awal = self.st.value("folder_kerja", str(paths.folder_kerja_bawaan()))
        self.ed_folder = QLineEdit(folder_awal)
        b_pilih = QPushButton("Pilih…")
        b_pilih.clicked.connect(self._pilih_folder)
        h_f.addWidget(self.ed_folder, 1)
        h_f.addWidget(b_pilih)
        v_f.addLayout(h_f)
        v_f.addWidget(kit.ket("Folder utama tempat berkas proyek baru (.vmd) akan disimpan."))
        lay.addWidget(gb_folder)

        # 2. Program eksternal
        gb_prog = QGroupBox("Program visualisasi eksternal")
        f_p = QFormLayout(gb_prog)
        self.ed_eksternal = {}
        eksternal = self.st.value("eksternal", {}) or {}
        for nama in ("PyMOL", "ChimeraX", "Discovery Studio Visualizer"):
            h = QHBoxLayout()
            ed = QLineEdit(str(eksternal.get(nama, "")))
            b = QPushButton("Cari…")
            b.clicked.connect(lambda _, n=nama, e=ed: self._cari_program(n, e))
            h.addWidget(ed, 1)
            h.addWidget(b)
            self.ed_eksternal[nama] = ed
            f_p.addRow(nama, h)
        lay.addWidget(gb_prog)

        # 3. Cache data internet
        gb_cache = QGroupBox("Penyimpanan & cache internet")
        v_c = QVBoxLayout(gb_cache)
        h_c = QHBoxLayout()
        self.l_ukuran_cache = QLabel(f"Cache data internet: <b>{sumber_data.ukuran_cache()}</b>")
        self.b_hapus_cache = QPushButton("Hapus cache")
        self.b_hapus_cache.clicked.connect(self._hapus_cache)
        h_c.addWidget(self.l_ukuran_cache, 1)
        h_c.addWidget(self.b_hapus_cache)
        v_c.addLayout(h_c)
        v_c.addWidget(kit.ket(
            "Berkas cache HTTP disimpan di folder data aplikasi untuk mempercepat kueri berulang "
            "dan mendukung mode luring saat koneksi internet terputus."
        ))
        lay.addWidget(gb_cache)

        lay.addStretch(1)

        # Baris tombol bawah
        b_simpan = kit.tombol("Simpan", self._simpan, utama=True)
        b_tutup = QPushButton("Batal")
        b_tutup.clicked.connect(self.reject)

        lay_b = QHBoxLayout()
        lay_b.addStretch(1)
        lay_b.addWidget(b_tutup)
        lay_b.addWidget(b_simpan)
        lay.addLayout(lay_b)

    def _pilih_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih folder kerja bawaan", self.ed_folder.text())
        if d:
            self.ed_folder.setText(d)

    def _cari_program(self, nama: str, line_edit: QLineEdit):
        f, _ = QFileDialog.getOpenFileName(self, f"Pilih berkas eksekusi {nama}", "C:/Program Files", "Program (*.exe)")
        if f:
            line_edit.setText(f)

    def _hapus_cache(self):
        n = sumber_data.hapus_cache()
        self.l_ukuran_cache.setText(f"Cache data internet: <b>{sumber_data.ukuran_cache()}</b>")
        QMessageBox.information(self, "Hapus cache", f"Berhasil menghapus {n} berkas cache data internet.")

    def _simpan(self):
        # Simpan folder kerja
        folder = self.ed_folder.text().strip()
        if folder:
            self.st.setValue("folder_kerja", folder)
            if self.jw and hasattr(self.jw, "s_folder"):
                self.jw.s_folder.setText(folder)

        # Simpan program eksternal
        manual = self.st.value("eksternal", {}) or {}
        for nama, ed in self.ed_eksternal.items():
            jalur = ed.text().strip()
            if jalur:
                manual[nama] = jalur
            elif nama in manual:
                manual.pop(nama, None)
        self.st.setValue("eksternal", manual)
        if self.jw and hasattr(self.jw, "deteksi"):
            self.jw.deteksi()

        self.accept()
