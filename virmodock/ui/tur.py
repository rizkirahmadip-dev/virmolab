"""Tur aplikasi interaktif (Bantuan › Tur aplikasi): sorot bagian jendela satu per satu dengan penjelasan singkat.

Overlay transparan di atas jendela utama menggelapkan semuanya kecuali bagian yang dijelaskan; balon keterangan
punya tombol Kembali / Lanjut / Selesai. Tidak mengubah apa pun di proyek.
"""
from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


def langkah_tur(jw):
    """[(fungsi -> widget sasaran atau None, judul, teks)] — widget dicari saat langkah tampil."""
    def ruang():
        return jw.grp_ruang.buttons()[0].parentWidget() if getattr(jw, "grp_ruang", None) else None

    return [
        (lambda: None, "Selamat datang di VirmoDock",
         "Tur singkat ini menunjukkan bagian utama jendela (± 1 menit). Tekan Lanjut, atau Esc untuk berhenti."),
        (lambda: jw.d_langkah, "Langkah",
         "Alur docking dari 1 sampai 5: Protein → Ligan → Area docking → Jalankan → Hasil. Centang hijau = selesai. "
         "Klik langkah mana pun untuk membuka panduannya."),
        (lambda: jw.d_kerja, "Panel kerja",
         "Tombol untuk langkah yang sedang aktif: ambil protein (RCSB / AlphaFold), siapkan reseptor dan ligan, atur "
         "grid box, pilih mesin dan ketelitian, lalu jalankan docking."),
        (lambda: jw.tab_tengah, "Viewport 3D & tab analisis",
         "Struktur 3D (putar: seret kiri, geser: seret kanan, zoom: gulir). Tab Hasil, Diagram 2D, Sifat Ligan, "
         "Statistik, dan Uji & Grafik muncul di sini."),
        (lambda: jw.d_hier, "Objek",
         "Semua protein, ligan, pose, air, dan ion. Centang untuk tampil/sembunyi; klik untuk melihat properti; "
         "ketik di kotak filter untuk mencari residu."),
        (ruang, "Ruang kerja",
         "Siapkan, Docking, dan Analisis mengatur tata letak panel untuk setiap tahap (juga Ctrl+1/2/3)."),
        (lambda: jw.tb, "Bilah alat",
         "Buka/simpan, impor, pengukuran, foto, laporan, dan buka di PyMOL/ChimeraX. Ctrl+K membuka palet perintah "
         "untuk mencari perintah apa pun dengan mengetik."),
        (lambda: jw.d_antre if jw.d_antre.isVisible() else jw.d_pesan if jw.d_pesan.isVisible() else None,
         "Antrean, Log, dan Pesan",
         "Progres docking (jeda/lanjut), catatan proses, dan pesan penting. Ditampilkan otomatis saat diperlukan."),
        (lambda: None, "Siap memulai",
         "Coba Berkas › Proyek baru dari templat › Contoh: HIV-1 protease (offline) untuk latihan lengkap tanpa "
         "internet. Panduan lengkap: F1. Tur ini bisa dibuka lagi dari menu Bantuan."),
    ]


class Tur(QWidget):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.langkah = langkah_tur(jw)
        self.i = 0
        self.lubang = QRect()
        self.balon = QFrame(self)
        self.balon.setObjectName("turBalon")
        self.balon.setStyleSheet("#turBalon { background: palette(window); border: 1px solid #2b6fd6; border-radius: 4px; }")
        v = QVBoxLayout(self.balon)
        v.setContentsMargins(14, 12, 14, 10)
        self.l_judul = QLabel()
        self.l_judul.setStyleSheet("font-weight: 600; font-size: 11pt;")
        self.l_teks = QLabel()
        self.l_teks.setWordWrap(True)
        self.l_teks.setMinimumWidth(320)
        self.l_teks.setMaximumWidth(380)
        h = QHBoxLayout()
        self.l_hal = QLabel()
        self.l_hal.setObjectName("muted")
        self.b_kembali = QPushButton("Kembali")
        self.b_lanjut = QPushButton("Lanjut")
        self.b_lanjut.setObjectName("primary")
        b_tutup = QPushButton("Selesai")
        self.b_kembali.clicked.connect(lambda: self.ke(self.i - 1))
        self.b_lanjut.clicked.connect(lambda: self.ke(self.i + 1))
        b_tutup.clicked.connect(self.tutup)
        h.addWidget(self.l_hal)
        h.addStretch(1)
        for b in (self.b_kembali, self.b_lanjut, b_tutup):
            h.addWidget(b)
        v.addWidget(self.l_judul)
        v.addWidget(self.l_teks)
        v.addLayout(h)
        jw.installEventFilter(self)
        self.setGeometry(jw.rect())
        self.show()
        self.raise_()
        self.ke(0)
        self.setFocus()

    def eventFilter(self, obj, e):
        if obj is self.jw and e.type() in (QEvent.Resize, QEvent.Move):
            self.setGeometry(self.jw.rect())
            self.ke(self.i)
        return False

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.tutup()
        elif e.key() in (Qt.Key_Right, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.ke(self.i + 1)
        elif e.key() == Qt.Key_Left:
            self.ke(self.i - 1)

    def ke(self, i):
        if i >= len(self.langkah):
            self.tutup()
            return
        self.i = max(0, i)
        cari, judul, teks = self.langkah[self.i]
        w = None
        try:
            w = cari()
        except Exception:
            w = None
        if w is not None and w.isVisible():
            p = w.mapTo(self.jw, w.rect().topLeft())
            self.lubang = QRect(p, w.size()).adjusted(-4, -4, 4, 4)
        else:
            self.lubang = QRect()
        self.l_judul.setText(judul)
        self.l_teks.setText(teks)
        self.l_hal.setText(f"{self.i + 1}/{len(self.langkah)}")
        self.b_kembali.setEnabled(self.i > 0)
        self.b_lanjut.setText("Selesai" if self.i == len(self.langkah) - 1 else "Lanjut")
        self.balon.adjustSize()
        self._posisi_balon()
        self.update()

    def _posisi_balon(self):
        b = self.balon.sizeHint()
        r = self.rect()
        L = self.lubang
        if L.isNull():
            x, y = (r.width() - b.width()) // 2, (r.height() - b.height()) // 2
        else:
            # kanan lubang, lalu kiri, bawah, atas — yang muat lebih dulu
            calon = [(L.right() + 16, L.top()), (L.left() - b.width() - 16, L.top()),
                     (L.left(), L.bottom() + 16), (L.left(), L.top() - b.height() - 16)]
            x, y = next(((cx, cy) for cx, cy in calon
                         if 0 <= cx and cx + b.width() <= r.width() and 0 <= cy and cy + b.height() <= r.height()),
                        (L.center().x() - b.width() // 2, L.center().y() - b.height() // 2))
            x = max(8, min(x, r.width() - b.width() - 8))
            y = max(8, min(y, r.height() - b.height() - 8))
        self.balon.setGeometry(x, y, b.width(), b.height())

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        jalur = QPainterPath()
        jalur.addRect(self.rect())
        if not self.lubang.isNull():
            lubang = QPainterPath()
            lubang.addRoundedRect(self.lubang, 4, 4)
            jalur = jalur.subtracted(lubang)
        p.fillPath(jalur, QColor(10, 16, 28, 150))
        if not self.lubang.isNull():
            p.setPen(QPen(QColor("#2b6fd6"), 2))
            p.drawRoundedRect(self.lubang, 4, 4)

    def mousePressEvent(self, e):
        e.accept()          # klik di luar balon tidak menembus ke aplikasi selama tur

    def tutup(self):
        self.jw.removeEventFilter(self)
        self.jw.st.setValue("tur_selesai", 1)
        self.close()
        self.deleteLater()
