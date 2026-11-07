"""Dialog Bantuan › Periksa pembaruan…: versi terpasang vs rilis terbaru di GitHub.

Pembaruan tidak pernah berjalan sendiri. Unduhan dimulai hanya setelah pengguna menekan Unduh dan pasang —
berkasnya ratusan megabita, dan pada koneksi berbayar itu keputusan penggunanya. Sidik jari SHA-256
dicocokkan sebelum installer dijalankan, dan aplikasi ditutup lebih dulu karena pemasangan tidak dapat
menimpa berkas program yang sedang terpakai.
"""
from html import escape

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QDialog, QLabel, QMessageBox, QProgressBar, QTextBrowser,
                               QVBoxLayout)

from .. import __version__ as VERSI
from ..core import paths, pembaruan
from ..core import unduh_pembaruan as unduhmod
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
        self.bar = QProgressBar()
        self.bar.setTextVisible(True)
        self.bar.hide()
        lay.addWidget(self.bar)
        self._unduhan = None            # objek Kerja yang sedang berjalan
        self._bisa_pasang = False
        self._batal = False
        self.b_periksa = kit.tombol("Periksa sekarang", self.periksa)
        self.b_buka = kit.tombol("Buka halaman rilis", self._buka)
        self.b_pasang = kit.tombol("Unduh dan pasang", self._unduh, utama=True,
                                   tip="Unduh installer rilis ini, cocokkan SHA-256-nya, lalu jalankan "
                                       "pemasangannya")
        self.b_pasang.hide()
        lay.addLayout(kit.bar_bawah(self, kiri=(self.b_periksa,), kanan=(self.b_buka, self.b_pasang)))
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
        # Disimpan sebagai nilai tersendiri, bukan ditanyakan ke tombolnya: isVisible() masih False
        # selama dialognya belum tampil di layar, dan teks di bawah ikut salah pilih karenanya.
        self._bisa_pasang = bool(st == "baru" and unduhmod.dapat_dipasang()
                                 and unduhmod.installer_dan_sidik(h)[0])
        self.b_pasang.setVisible(self._bisa_pasang)
        self._hasil = h
        if st == "baru":
            self.k_status.isi("Versi baru tersedia", nada="warn")
            if self._bisa_pasang:
                self.l_info.setText(f"VirmoLab {h['versi']} sudah terbit. Unduh dan pasang mengunduh installernya, "
                                    "mencocokkan sidik jari SHA-256-nya, lalu menjalankan pemasangan. Proyek dan "
                                    "pengaturan tetap terbaca.")
            elif paths.PORTABLE:
                self.l_info.setText(f"VirmoLab {h['versi']} sudah terbit. Versi portable diperbarui dengan "
                                    "mengganti isi foldernya sendiri; unduh zip-nya dari halaman rilis.")
            else:
                self.l_info.setText(f"VirmoLab {h['versi']} sudah terbit. Unduh installer dari halaman rilis, "
                                    "cocokkan SHA-256-nya dengan berkas SHA256SUMS di halaman yang sama, lalu "
                                    "pasang di atas versi ini. Proyek dan pengaturan tetap terbaca.")
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

    def _unduh(self):
        """Unduh installer di thread lain; dialog tetap dapat dipakai dan unduhan dapat dibatalkan."""
        if self._unduhan is not None:           # tombol berubah jadi Batalkan selagi berjalan
            self._batal = True
            return
        self._batal = False
        self.b_pasang.setText("Batalkan unduhan")
        self.b_periksa.setEnabled(False)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFormat("Mengambil sidik jari…")
        self.bar.show()

        TAHAP = {"sidik": "Mengambil sidik jari…", "unduh": "Mengunduh %p% (%v dari %m MB)",
                 "verifikasi": "Memverifikasi berkas…"}

        def kerjakan(lapor):
            def maju(tahap, a, b):
                lapor.progres.emit(a, b, tahap)
            return unduhmod.unduh_terverifikasi(self._hasil, lapor=maju, dibatalkan=lambda: self._batal)

        def progres(a, b, tahap):
            self.bar.setFormat(TAHAP.get(tahap, "%p%"))
            if tahap == "unduh" and b:
                self.bar.setRange(0, max(b // (1 << 20), 1))
                self.bar.setValue(a // (1 << 20))
            elif b:
                self.bar.setRange(0, b)
                self.bar.setValue(a)

        self._unduhan = kerja.jalankan(kerjakan, selesai=self._siap_dipasang, galat=self._gagal_unduh,
                                       progres=progres)

    def _akhiri_unduhan(self):
        self._unduhan = None
        self._batal = False
        self.b_pasang.setText("Unduh dan pasang")
        self.b_periksa.setEnabled(True)
        self.bar.hide()

    def _gagal_unduh(self, pesan):
        self._akhiri_unduhan()
        teks = str(pesan).split("\n")[0]
        self.l_info.setText("Unduhan dibatalkan." if "Dibatalkan" in teks else f"Unduhan gagal: {teks}")

    def _siap_dipasang(self, f):
        self._akhiri_unduhan()
        if not f:
            return
        k = QMessageBox(QMessageBox.Question, "Pasang pembaruan",
                        "Installer sudah diunduh dan sidik jari SHA-256-nya cocok.\n\n"
                        "VirmoLab akan ditutup, pembaruan dipasang sendiri, lalu aplikasi dibuka lagi. "
                        "Tidak ada yang perlu dijawab selama pemasangan. Pekerjaan yang sedang berjalan "
                        "ditanyakan lebih dulu.", parent=self)
        b_ya = k.addButton("Pasang sekarang", QMessageBox.AcceptRole)
        k.addButton("Nanti saja", QMessageBox.RejectRole)
        k.setDefaultButton(b_ya)
        k.exec()
        if k.clickedButton() is not b_ya:
            self.l_info.setText(f"Installer tersimpan di {f.parent}. Jalankan kapan saja untuk memasang.")
            return
        try:
            unduhmod.jalankan_installer(f)
        except Exception as e:
            self.l_info.setText(f"Installer tidak dapat dijalankan: {e}")
            return
        self.accept()
        if self.jw is not None:
            self.jw.close()         # closeEvent biasa: docking/MD yang berjalan ditanyakan lebih dulu

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
