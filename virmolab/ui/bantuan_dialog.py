"""Pasang bantuan kontekstual pada setiap dialog tanpa menyentuh kelas dialognya satu per satu.

Dialog di VirmoLab tidak punya kelas dasar bersama (52 berkas, masing-masing turunan QDialog langsung),
jadi tombol bantuan tidak dapat ditambahkan di satu tempat lewat pewarisan. Penyaring kejadian pada
QApplication menangkap tiap dialog saat pertama kali ditampilkan dan memasang pintasan F1 di sana.

Hanya pintasan yang dipasang, bukan widget: menyisipkan tombol ke tata letak 52 dialog yang berbeda
berisiko menggeser isinya, sedangkan pintasan tidak menyentuh tata letak sama sekali. Jalan yang terlihat
mata disediakan lewat menu Bantuan › Panduan fitur.
"""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog


class _Penyaring(QObject):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw

    def eventFilter(self, obj, e):
        if e.type() == QEvent.Show and isinstance(obj, QDialog) and not obj.property("_vm_bantuan"):
            obj.setProperty("_vm_bantuan", True)
            try:
                s = QShortcut(QKeySequence("F1"), obj)
                s.setContext(Qt.WidgetWithChildrenShortcut)
                s.activated.connect(lambda d=obj: self.jw.bantuan_dialog(d))
                judul = obj.windowTitle()
                if judul and "F1" not in judul:
                    obj.setWindowTitle(f"{judul}   ·   F1: panduan")
            except Exception:
                pass          # bantuan tidak boleh menghalangi dialog terbuka
        return False


def pasang(app, jw):
    """Pasang penyaring; disimpan pada jendela utama supaya tidak dibuang pengumpul sampah."""
    jw._penyaring_bantuan = _Penyaring(jw)
    app.installEventFilter(jw._penyaring_bantuan)
