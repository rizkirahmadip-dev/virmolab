"""Konsol Python di dalam VirmoLab (Alat › Konsol Python) - untuk pengguna mahir dan pembuat plugin.

Variabel siap pakai: vd (jendela utama), proyek, objek, np, dan modul inti VirmoLab (molekul, mesin, analisis, ekspor,
md, prep_ligan, prep_reseptor). Kode berjalan di thread antarmuka: perintah lama membuat jendela tidak merespons
sampai selesai. Riwayat perintah: ↑/↓.
"""
import code
import contextlib
import io

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

SAMBUTAN = ("Konsol Python VirmoLab. Variabel: vd, proyek, objek, np, molekul, mesin, analisis, ekspor, md, prep_ligan, "
            "prep_reseptor.\nContoh:  [o.nama for o in objek.values()]   ·   ekspor.baris_hasil(proyek)[:3]   ·   "
            "help(vd.tambah_objek)\n")


class Konsol(QWidget):
    def __init__(self, jw):
        super().__init__()
        self.jw = jw
        self.riwayat, self.ri = [], 0
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        self.keluar = QPlainTextEdit()
        self.keluar.setReadOnly(True)
        self.keluar.setObjectName("mono")
        f = QFont("Consolas")
        f.setStyleHint(QFont.Monospace)
        self.keluar.setFont(f)
        self.keluar.setPlainText(SAMBUTAN)
        v.addWidget(self.keluar, 1)
        h = QHBoxLayout()
        self.prompt = QLabel(">>>")
        self.prompt.setFont(f)
        self.masuk = QLineEdit()
        self.masuk.setFont(f)
        self.masuk.returnPressed.connect(self.kirim)
        self.masuk.installEventFilter(self)
        b = QPushButton("Bersihkan")
        b.clicked.connect(lambda: self.keluar.setPlainText(SAMBUTAN))
        h.addWidget(self.prompt)
        h.addWidget(self.masuk, 1)
        h.addWidget(b)
        v.addLayout(h)
        self.ns = {}
        self.k = code.InteractiveConsole(self.ns)
        self.segarkan_ns()

    def segarkan_ns(self):
        import numpy as np
        from ..core import analisis, ekspor, mesin, molekul, prep_ligan, prep_reseptor
        self.ns.update(vd=self.jw, proyek=self.jw.proyek, objek=self.jw.objek, np=np, molekul=molekul, mesin=mesin,
                       analisis=analisis, ekspor=ekspor, prep_ligan=prep_ligan, prep_reseptor=prep_reseptor)
        try:
            from ..core import md
            self.ns["md"] = md
        except Exception:
            pass

    def eventFilter(self, obj, e):
        from PySide6.QtCore import QEvent
        if obj is self.masuk and e.type() == QEvent.KeyPress and self.riwayat:
            if e.key() == Qt.Key_Up:
                self.ri = max(0, self.ri - 1)
                self.masuk.setText(self.riwayat[self.ri])
                return True
            if e.key() == Qt.Key_Down:
                self.ri = min(len(self.riwayat), self.ri + 1)
                self.masuk.setText(self.riwayat[self.ri] if self.ri < len(self.riwayat) else "")
                return True
        return super().eventFilter(obj, e)

    def kirim(self):
        baris = self.masuk.text()
        self.masuk.clear()
        if baris.strip():
            self.riwayat.append(baris)
        self.ri = len(self.riwayat)
        self.ns["proyek"] = self.jw.proyek          # proyek bisa berganti sejak konsol dibuka
        self._tulis(f"{self.prompt.text()} {baris}\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            lagi = self.k.push(baris)
        if buf.getvalue():
            self._tulis(buf.getvalue())
        self.prompt.setText("..." if lagi else ">>>")

    def _tulis(self, t):
        self.keluar.moveCursor(QTextCursor.End)
        self.keluar.insertPlainText(t)
        self.keluar.moveCursor(QTextCursor.End)
