"""Jendela asisten: catatan VirmoDock, dan Ollama bila pengguna sudah memasangnya."""
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout

from ..core import asisten


class DialogAsisten(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.setWindowTitle("Asisten")
        self.resize(640, 420)
        v = QVBoxLayout(self)
        lab = QLabel("Tanya dalam Bahasa Indonesia. Jawaban catatan tidak memakai internet. "
                     "Ollama hanya dipakai bila sudah terpasang di komputer ini.")
        lab.setWordWrap(True)
        v.addWidget(lab)
        self.e = QLineEdit()
        self.e.setPlaceholderText("Misalnya: kapan redocking dianggap valid?")
        self.e.returnPressed.connect(self._tanya)
        v.addWidget(self.e)
        b = QPushButton("Tanya")
        b.clicked.connect(self._tanya)
        v.addWidget(b)
        self.keluar = QPlainTextEdit()
        self.keluar.setReadOnly(True)
        v.addWidget(self.keluar, 1)

    def _tanya(self):
        q = self.e.text().strip()
        if not q:
            return
        self.keluar.setPlainText("Sedang menjawab…")
        from . import kerja
        kerja.jalankan(lambda lapor: asisten.jawab(q), selesai=self.keluar.setPlainText, galat=self.keluar.setPlainText)
