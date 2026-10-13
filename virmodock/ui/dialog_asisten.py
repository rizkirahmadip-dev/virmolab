from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget
)

from ..core import asisten
from . import kerja, kit


class DialogAsisten(QDialog):
    def __init__(self, jw, tab_awal: int = 0):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Asisten & interpretasi hasil")
        self.resize(750, 520)

        lay_utama = QVBoxLayout(self)
        lay_utama.setContentsMargins(10, 10, 10, 10)
        lay_utama.setSpacing(6)
        lay_utama.addWidget(kit.judul(
            "Asisten interpretasi hasil",
            "Tanya jawab dan ringkasan otomatis dari hasil docking proyek; periksa ulang setiap kesimpulan "
            "sebelum dipakai."))

        self.tabs = QTabWidget()

        # =====================================================================
        # TAB 1: Tanya Bebas & Panduan
        # =====================================================================
        w_tanya = QWidget()
        lay_tanya = QVBoxLayout(w_tanya)
        lay_tanya.setContentsMargins(8, 8, 8, 8)
        lay_tanya.setSpacing(6)

        lab = QLabel("Tanya dalam Bahasa Indonesia. Jawaban panduan bersumber langsung dari basis pengetahuan VirmoDock. "
                     "Bila Ollama aktif di komputer ini, jawaban diperluas secara otomatis oleh LLM lokal.")
        lab.setWordWrap(True)
        lay_tanya.addWidget(lab)

        self.e_tanya = QLineEdit()
        self.e_tanya.setPlaceholderText("Misalnya: kapan redocking dianggap valid? atau apa itu CNS-MPO?")
        self.e_tanya.returnPressed.connect(self._tanya)
        lay_tanya.addWidget(self.e_tanya)

        b_tanya = QPushButton("Tanya Asisten")
        b_tanya.clicked.connect(self._tanya)
        lay_tanya.addWidget(b_tanya)

        self.keluar_tanya = QPlainTextEdit()
        self.keluar_tanya.setReadOnly(True)
        lay_tanya.addWidget(self.keluar_tanya, 1)

        self.tabs.addTab(w_tanya, "Tanya Bebas && Panduan")

        # =====================================================================
        # TAB 2: Interpretasi Hasil Docking AI
        # =====================================================================
        w_interp = QWidget()
        lay_interp = QVBoxLayout(w_interp)
        lay_interp.setContentsMargins(8, 8, 8, 8)
        lay_interp.setSpacing(6)

        bar_opsi = QHBoxLayout()
        bar_opsi.addWidget(QLabel("Mode Narasi:"))
        self.cb_mode = QComboBox()
        self.cb_mode.addItem("Ringkasan Eksekutif (1-2 Paragraf)", "ringkasan")
        self.cb_mode.addItem("Draf Hasil & Pembahasan Skripsi/Jurnal (2-3 Paragraf)", "hasil_pembahasan")
        bar_opsi.addWidget(self.cb_mode)

        bar_opsi.addSpacing(10)
        self.b_generate = QPushButton("Generate Interpretasi")
        self.b_generate.setObjectName("primary")
        self.b_generate.clicked.connect(self._jalankan_interpretasi)
        bar_opsi.addWidget(self.b_generate)
        lay_interp.addLayout(bar_opsi)

        self.l_status_ai = kit.lencana("Deteksi Ollama…", "info")
        self.l_status_ai.setObjectName("muted")
        lay_interp.addWidget(self.l_status_ai)

        self.keluar_interp = QTextEdit()
        self.keluar_interp.setReadOnly(True)
        lay_interp.addWidget(self.keluar_interp, 1)

        bar_bawah = QHBoxLayout()
        b_salin = QPushButton("Salin Teks ke Clipboard")
        b_salin.clicked.connect(self._salin_interp)
        bar_bawah.addWidget(b_salin)

        bar_bawah.addStretch(1)
        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.close)
        bar_bawah.addWidget(b_tutup)
        lay_interp.addLayout(bar_bawah)

        self.tabs.addTab(w_interp, "Interpretasi Hasil Docking (AI)")

        lay_utama.addWidget(self.tabs)

        # Cek status Ollama saat buka
        self._cek_status_ollama()

        # Set tab awal
        if 0 <= tab_awal < self.tabs.count():
            self.tabs.setCurrentIndex(tab_awal)

    def _cek_status_ollama(self):
        m = asisten.model_ollama(timeout=1)
        if m:
            self.l_status_ai.setText(f"✓ Ollama aktif (Model: {m}). Narasi akan diperkaya oleh AI lokal.")
            kit.atur_nada(self.l_status_ai, "ok")
        else:
            self.l_status_ai.setText("ℹ Ollama tidak aktif di 127.0.0.1:11434. Narasi akan disusun otomatis oleh Mesin Pakar VirmoDock.")
            kit.atur_nada(self.l_status_ai, "info")

    def _tanya(self):
        q = self.e_tanya.text().strip()
        if not q:
            return
        self.keluar_tanya.setPlainText("Sedang berpikir…")
        kerja.jalankan(lambda lapor: asisten.jawab(q), selesai=self.keluar_tanya.setPlainText, galat=self.keluar_tanya.setPlainText)

    def _jalankan_interpretasi(self):
        proyek = getattr(self.jw, "proyek", None)
        if not proyek:
            QMessageBox.warning(self, "Proyek Kosong", "Belum ada proyek atau hasil docking yang terbuka.")
            return

        mode = self.cb_mode.currentData()
        self.keluar_interp.setPlainText("Sedang menyusun interpretasi hasil docking… Mohon tunggu beberapa saat.")
        self.b_generate.setEnabled(False)

        def _selesai(teks):
            self.b_generate.setEnabled(True)
            self.keluar_interp.setMarkdown(str(teks))

        def _galat(err):
            self.b_generate.setEnabled(True)
            self.keluar_interp.setPlainText(f"Galat saat interpretasi: {err}")

        kerja.jalankan(
            lambda lapor: asisten.interpretasi(proyek, mode=mode),
            selesai=_selesai,
            galat=_galat
        )

    def _salin_interp(self):
        teks = self.keluar_interp.toPlainText().strip()
        if not teks:
            return
        QGuiApplication.clipboard().setText(teks)
        QMessageBox.information(self, "Disalin", "Teks interpretasi berhasil disalin ke clipboard.")
