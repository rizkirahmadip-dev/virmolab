"""Pasang bantuan kontekstual pada setiap dialog tanpa menyentuh kelas dialognya satu per satu.

Dialog di VirmoLab tidak punya kelas dasar bersama (52 berkas, masing-masing turunan QDialog langsung),
jadi pintasan bantuan tidak dapat ditambahkan di satu tempat lewat pewarisan.

Pemasangannya digantung pada `QApplication.focusChanged`, bukan pada penyaring kejadian aplikasi. Penyaring
aplikasi menerima SETIAP kejadian dari setiap objek — termasuk kejadian kustom Qt yang `type()`-nya tidak
ada di enum Python dan melempar saat dibaca — dan kegagalan di jalur sepanas itu berbalik menjadi rekursi
tanpa ujung. focusChanged terpanggil beberapa kali per dialog, bukan ribuan kali per detik.

Hanya pintasan yang dipasang, bukan widget: menyisipkan tombol ke tata letak 52 dialog yang berbeda
berisiko menggeser isinya. Jalan yang terlihat mata disediakan lewat menu Bantuan › Panduan fitur.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog


def _dialog_induk(w):
    """QDialog terdekat yang memuat `w`, atau None."""
    while w is not None:
        if isinstance(w, QDialog):
            return w
        w = w.parentWidget()
    return None


def _pasang_pada(d, jw):
    if d is None or d.property("_vm_bantuan"):
        return
    d.setProperty("_vm_bantuan", True)
    s = QShortcut(QKeySequence("F1"), d)
    s.setContext(Qt.WidgetWithChildrenShortcut)
    s.activated.connect(lambda: jw.bantuan_dialog(d))
    judul = d.windowTitle()
    if judul and "F1" not in judul:
        d.setWindowTitle(f"{judul}   ·   F1: panduan")


def pasang(app, jw):
    """Pasang bantuan F1 pada tiap dialog begitu salah satu widget di dalamnya mendapat fokus."""
    def saat_fokus(_lama, baru):
        try:
            _pasang_pada(_dialog_induk(baru), jw)
        except Exception:
            pass          # bantuan tidak boleh menghalangi dialog terbuka

    jw._bantuan_fokus = saat_fokus      # pegang referensinya; sinyal Qt tidak menahan closure
    app.focusChanged.connect(saat_fokus)
