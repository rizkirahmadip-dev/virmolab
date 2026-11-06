from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QMessageBox
)

from ..core import metabolisme
from . import kit


class DialogMetabolisme(QDialog):
    """Dialog interaktif analisis titik rawan metabolisme sitokrom P450."""

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.proyek = jw.proyek
        self.hasil_saat_ini = {}

        self.setWindowTitle("Titik metabolisme CYP450")
        self.resize(780, 540)
        self._bangun_ui()
        self._analisis()

    def _bangun_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # Header
        lbl_head = QLabel("Prediksi Titik Metabolisme CYP450 (Site of Metabolism)")
        lbl_head.setObjectName("judulDialog")
        root.addWidget(lbl_head)

        lbl_desc = QLabel(
            "Mengidentifikasi posisi atom ligan yang paling rentan terhadap metabolisme oksidatif fase I "
            "(CYP3A4, CYP2D6, CYP2C9), menghitung stabilitas metabolik, dan memberikan saran proteksi bioisosterik."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setObjectName("subjudul")
        root.addWidget(lbl_desc)

        # Pemilihan Ligan
        box_lig = QGroupBox("Ligan yang Dianalisis")
        lyt_l = QHBoxLayout(box_lig)
        lyt_l.addWidget(QLabel("Pilih Ligan:"))
        self.cmb_ligan = QComboBox()
        self.cmb_ligan.setToolTip("Senyawa yang diperiksa titik metabolismenya. Prediksi berlaku untuk strukturnya, bukan untuk pose docking tertentu.")
        for l in kit.ligan_proyek(self.jw, dengan_mol=False):
            self.cmb_ligan.addItem(l["nama"], l["smiles"])
        if not self.cmb_ligan.count():
            self.cmb_ligan.addItem("Contoh: 4-metilanisol", "Cc1ccc(OC)cc1")
        self.cmb_ligan.currentIndexChanged.connect(self._analisis)
        lyt_l.addWidget(self.cmb_ligan)
        root.addWidget(box_lig)

        # Ringkasan Skor
        box_ring = QGroupBox("Stabilitas Metabolik Intrinsik")
        lyt_r = QVBoxLayout(box_ring)
        self.lbl_skor = QLabel("...")
        self.lbl_skor.setObjectName("judulDialog")
        lyt_r.addWidget(self.lbl_skor)

        self.lbl_ringkas = QLabel("...")
        self.lbl_ringkas.setObjectName("subjudul")
        lyt_r.addWidget(self.lbl_ringkas)
        root.addWidget(box_ring)

        # Tabel Titik Rawan Metabolisme
        self.tabel = QTableWidget()
        self.tabel.setColumnCount(4)
        self.tabel.setHorizontalHeaderLabels([
            "Atom Target", "Tipe Reaksi CYP450", "Tingkat Kerentanan", "Rekomendasi Perlindungan Bioisosterik"
        ])
        self.tabel.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabel.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tabel.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabel.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        root.addWidget(self.tabel)
        root.addWidget(kit.catatan(
            "Prediksi memakai pola SMARTS gugus yang lazim dioksidasi CYP450, bukan model terlatih pada data "
            "metabolit atau struktur isoform CYP. Skor stabilitas hanyalah hitungan jumlah dan bobot gugus "
            "rawan — bukan klirens intrinsik; pakai sebagai pengingat titik rawan, bukan sebagai prediksi "
            "metabolisme yang bisa dikutip."))

        # Tombol
        lyt_b = QHBoxLayout()
        btn_salin = QPushButton("Salin Analisis SoM")
        def _salin():
            from PySide6.QtGui import QGuiApplication
            if not self.hasil_saat_ini:
                return
            h = self.hasil_saat_ini
            baris = [f"Analisis SoM: {h['klasifikasi']} (Skor: {h['skor_stabilitas']}/100)"]
            for s in h.get("daftar_som", []):
                baris.append(f"- Atom {s['simbol']}{s['indeks_atom']}: {s['tipe_reaksi']} ({s['tingkat_kerentanan']}) -> {s['rekomendasi_bioisosterik']}")
            QGuiApplication.clipboard().setText("\n".join(baris))
            QMessageBox.information(self, "Tersalin", "Ringkasan titik metabolisme disalin ke papan klip.")
        btn_salin.clicked.connect(_salin)
        lyt_b.addWidget(btn_salin)

        lyt_b.addStretch()
        btn_tutup = QPushButton("✕ Tutup")
        btn_tutup.clicked.connect(self.close)
        lyt_b.addWidget(btn_tutup)
        root.addLayout(lyt_b)

    def _analisis(self):
        with kit.sibuk(self.lbl_ringkas, "Menganalisis titik metabolisme…"):
            smi = self.cmb_ligan.currentData()
            if not smi:
                smi = "Cc1ccc(OC)cc1"

            try:
                h = metabolisme.prediksi_titik_metabolisme(smi)
                self.hasil_saat_ini = h

                self.lbl_skor.setText(f"Skor stabilitas {kit.f(h['skor_stabilitas'], 1)} / 100 · {h['klasifikasi']}")
                self.lbl_ringkas.setText(f"{h['ringkasan']} Terdeteksi {h['jumlah_som']} titik rawan.")

                self.tabel.setRowCount(0)
                for row, s in enumerate(h["daftar_som"]):
                    self.tabel.insertRow(row)
                    self.tabel.setItem(row, 0, QTableWidgetItem(f"{s['simbol']}{s['indeks_atom']}"))
                    self.tabel.setItem(row, 1, QTableWidgetItem(s["tipe_reaksi"]))
                    self.tabel.setItem(row, 2, QTableWidgetItem(s["tingkat_kerentanan"]))
                    self.tabel.setItem(row, 3, QTableWidgetItem(s["rekomendasi_bioisosterik"]))
            except Exception as e:
                QMessageBox.critical(self, "Galat", f"Gagal menganalisis metabolisme: {e}")
