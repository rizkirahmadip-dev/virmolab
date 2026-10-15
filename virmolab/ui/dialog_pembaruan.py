"""Dialog Bantuan › Periksa pembaruan…: versi terpasang vs rilis terbaru di GitHub.

Tidak ada unduhan atau pemasangan otomatis. Tombol membuka halaman rilis di peramban; pengguna mengunduh
installer sendiri dan mencocokkannya dengan SHA256SUMS yang ada di halaman yang sama.
"""
from html import escape

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QTextBrowser, QVBoxLayout

from .. import __version__ as VERSI
from ..core import paths, pembaruan
from . import kerja, kit


class DialogPembaruan(QDialog):
    def __init__(self, jw=None, hasil=None):
        super().__init__(jw)
        self.jw = jw
        self.st = jw.st if jw is not None and hasattr(jw, "st") else paths.settings()
        self._url = pembaruan.HALAMAN_RILIS
        self.setWindowTitle("Periksa pembaruan")
        self.resize(640, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "Pembaruan VirmoLab",
            "Membandingkan versi terpasang dengan rilis terbaru di GitHub. Hanya nomor versi yang dibaca; "
            "tidak ada data proyek yang dikirim dan tidak ada yang dipasang otomatis."))
        self.k_pasang = kit.Kartu("Versi terpasang", VERSI)
        self.k_rilis = kit.Kartu("Rilis terbaru", "–")
        self.k_status = kit.Kartu("Status", "–")
        lay.addLayout(kit.baris_kartu(self.k_pasang, self.k_rilis, self.k_status))
        self.l_info = QLabel()
        self.l_info.setWordWrap(True)
        self.l_info.setObjectName("subjudul")
        lay.addWidget(self.l_info)
        self.catatan = QTextBrowser()
        self.catatan.setOpenExternalLinks(True)
        lay.addWidget(self.catatan, 1)
        self.c_otomatis = QCheckBox("Periksa otomatis sekali sehari saat aplikasi dibuka")
        self.c_otomatis.setChecked(pembaruan.otomatis_aktif(self.st))
        self.c_otomatis.toggled.connect(lambda v: self.st.setValue("cek_pembaruan", bool(v)))
        lay.addWidget(self.c_otomatis)
        self.b_periksa = kit.tombol("Periksa sekarang", self.periksa)
        self.b_buka = kit.tombol("Buka halaman rilis", self._buka, utama=True)
        lay.addLayout(kit.bar_bawah(self, kiri=(self.b_periksa,), kanan=(self.b_buka,)))
        if hasil:
            self._tampilkan(hasil)
        else:
            self.periksa()

    def periksa(self):
        self.b_periksa.setEnabled(False)
        self.k_status.isi("Memeriksa…")
        self.l_info.setText("Menghubungi GitHub…")
        kerja.jalankan(lambda lapor: pembaruan.periksa(), selesai=self._tampilkan,
                       galat=lambda g: self._tampilkan({"status": "galat", "pesan": str(g).split("\n")[0]}))

    def _tampilkan(self, h):
        self.b_periksa.setEnabled(True)
        st = h.get("status")
        if st in ("baru", "terkini"):
            pembaruan.catat_diperiksa(self.st)
        self._url = h.get("url") or pembaruan.HALAMAN_RILIS
        self.k_rilis.isi(h.get("versi") or "–", h.get("tanggal") or None)
        if st == "baru":
            self.k_status.isi("Versi baru tersedia", nada="warn")
            self.l_info.setText(f"VirmoLab {h['versi']} sudah terbit. Unduh installer dari halaman rilis, cocokkan "
                                "SHA-256-nya dengan berkas SHA256SUMS di halaman yang sama, lalu pasang di atas "
                                "versi ini. Proyek dan pengaturan tetap terbaca.")
        elif st == "terkini":
            self.k_status.isi("Sudah terbaru", nada="ok")
            self.l_info.setText("Versi terpasang sama dengan atau lebih baru dari rilis terbaru di GitHub.")
        elif st == "belum_ada_rilis":
            self.k_status.isi("Belum ada rilis")
            self.l_info.setText(h.get("pesan", ""))
        else:
            self.k_status.isi("Tidak terhubung", nada="bad")
            self.l_info.setText("Pemeriksaan gagal: " + (h.get("pesan") or "sebab tidak diketahui") +
                                " Aplikasi tetap bisa dipakai seperti biasa.")
        self._isi_catatan(h)

    def _isi_catatan(self, h):
        bagian = []
        aset = h.get("aset") or []
        if aset:
            baris = "".join(
                f"<li><a href='{escape(a['url'], quote=True)}'>{escape(a['nama'])}</a> · "
                f"{pembaruan.ukuran_teks(a['ukuran'])}</li>" for a in aset)
            bagian.append(f"<p><b>Berkas rilis</b></p><ul>{baris}</ul>")
        if h.get("catatan"):
            bagian.append("<p><b>Catatan rilis</b></p>")
        from PySide6.QtGui import QTextCursor
        self.catatan.setHtml("".join(bagian))
        if h.get("catatan"):
            # Markdown dari GitHub ditambahkan sebagai Markdown, bukan HTML mentah dari internet.
            c = self.catatan.textCursor()
            c.movePosition(QTextCursor.MoveOperation.End)
            c.insertBlock()
            c.insertMarkdown(h["catatan"])
        self.catatan.moveCursor(QTextCursor.MoveOperation.Start)
        # Tanpa berkas dan catatan (belum ada rilis, gagal terhubung) kotak kosong hanya memakan tempat.
        self.catatan.setVisible(bool(bagian))
        if not bagian:
            self.adjustSize()

    def _buka(self):
        QDesktopServices.openUrl(QUrl(self._url))
