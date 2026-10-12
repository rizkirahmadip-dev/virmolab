"""Dialog Help: lapor masalah/saran, lisensi pihak ketiga, cara mengutip."""
import platform

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTabWidget,
                               QTextBrowser, QVBoxLayout)

from ..core import catat, paths
from ..core.laporan import SITASI
from ..core.qc import SITASI as SITASI_QC
from ..core.sifat import SITASI as SITASI_SIFAT

SITASI_MD = []
try:      # modul MD membutuhkan numpy saja di tingkat impor; daftar sitasi tetap tersedia walau OpenMM tidak ada
    from ..core.md import SITASI as SITASI_MD
except Exception:
    pass


def _ket(t):
    l = QLabel(t)
    l.setObjectName("muted")
    l.setWordWrap(True)
    return l


class DialogLapor(QDialog):
    """E6: pengguna melihat & menyetujui isi laporan; tidak ada pengiriman otomatis."""

    def __init__(self, versi, env, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lapor masalah / kirim saran")
        self.resize(720, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(_ket("Tulis apa yang terjadi atau saran Anda di bagian atas. Info sistem dan log terakhir di "
                           "bawahnya membantu menemukan penyebab - periksa dan hapus bagian yang tidak ingin dibagikan. "
                           "VirmoDock tidak mengirim apa pun secara otomatis: salin teks ini lalu kirim lewat email "
                           "atau halaman Issues proyek."))
        g = env.gpu_utama if env else None
        info = [f"VirmoDock {versi}" + (" (portable)" if paths.PORTABLE else ""),
                f"Windows: {platform.platform()}",
                f"CPU: {env.cpu if env else '-'} · {env.inti if env else '-'} thread · RAM {env.ram_gb if env else '-'} GB",
                f"GPU: {g.nama + ' · ' + str(g.vram_gb) + ' GB · driver ' + g.driver + (' · OpenCL' if g.opencl else ' · tanpa OpenCL') if g else 'tidak ada'}"]
        self.teks = QPlainTextEdit()
        self.teks.setPlainText("Masalah / saran:\n\n\nLangkah untuk mengulang:\n1.\n2.\n\n"
                               "---- Info sistem ----\n" + "\n".join(info) +
                               "\n\n---- Log terakhir ----\n" + catat.ekor(60))
        lay.addWidget(self.teks, 1)
        h = QHBoxLayout()
        b1 = QPushButton("Salin ke clipboard")
        b1.setObjectName("primary")
        b1.clicked.connect(lambda: (QGuiApplication.clipboard().setText(self.teks.toPlainText()),
                                    b1.setText("✓ Tersalin")))
        b2 = QPushButton("Buka folder log")
        b2.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.LOG))))
        b4 = QPushButton("Simpan paket laporan (.zip)…")
        b4.setToolTip("Teks di atas + seluruh berkas log + hasil uji mandiri terakhir (bila ada) dalam satu zip "
                      "untuk dilampirkan sendiri ke email/Issues")
        b4.clicked.connect(self.simpan_zip)
        self.l_zip = _ket("")
        b3 = QPushButton("✕ Tutup")
        b3.clicked.connect(self.accept)
        h.addWidget(b2)
        h.addWidget(b4)
        h.addStretch(1)
        h.addWidget(b1)
        h.addWidget(b3)
        lay.addLayout(h)
        lay.addWidget(self.l_zip)

    def simpan_zip(self):
        import zipfile
        from datetime import datetime
        f, _ = QFileDialog.getSaveFileName(self, "Simpan paket laporan",
                                           str(paths.folder_kerja_bawaan() / f"laporan_VirmoDock_{datetime.now():%Y%m%d_%H%M}.zip"),
                                           "Arsip zip (*.zip)")
        if not f:
            return
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("laporan.txt", self.teks.toPlainText())
            for p in sorted(paths.LOG.glob("*.log*")):
                z.write(p, f"log/{p.name}")
            for p in (paths.APPDATA / "uji_mandiri.json",):
                if p.exists():
                    z.write(p, p.name)
        self.l_zip.setText(f"Tersimpan: {f} - periksa isinya, lalu lampirkan sendiri saat melapor.")


class DialogLisensi(QDialog):
    def __init__(self, versi, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lisensi dan cara mengutip")
        self.resize(760, 600)
        lay = QVBoxLayout(self)
        tab = QTabWidget()
        kutip = QTextBrowser()
        kutip.setOpenExternalLinks(True)
        kutip.setHtml(
            "<h3>Mengutip VirmoDock dan perangkat lunak di dalamnya</h3>"
            f"<p>VirmoDock {versi}. Aplikasi desktop molecular docking (open-source, GPL-3.0-or-later).</p>"
            "<p>Kutip juga mesin dan pustaka yang Anda pakai (laporan VirmoDock mencantumkannya otomatis):</p><ol>"
            + "".join(f"<li>{v}</li>" for v in SITASI.values()) + "</ol>"
            "<p>Bila memakai kontrol kualitas pose, sifat ligan, atau BOILED-Egg:</p><ol>"
            + "".join(f"<li>{v}</li>" for v in [SITASI_QC] + SITASI_SIFAT) + "</ol>"
            "<p>Bila memakai MD &amp; MM/GBSA (OpenMM, OpenFF):</p><ol>"
            + "".join(f"<li>{v}</li>" for v in SITASI_MD) + "</ol>"
            "<p>Bila memakai docking kovalen:</p><ol><li>"
            "Bianco G, Forli S, Goodsell DS, Olson AJ. Covalent docking using AutoDock: two-point attractor and "
            "flexible side chain methods. Protein Sci. 2016;25(1):295-301. doi:10.1002/pro.2733</li></ol>")
        tab.addTab(kutip, "Cara mengutip")
        lis = QTextBrowser()
        lis.setOpenExternalLinks(True)
        teks = ""
        for f in (paths.AKAR / "LISENSI_PIHAK_KETIGA.txt", paths.AKAR / "docs" / "LISENSI_PIHAK_KETIGA.txt"):
            if f.exists():
                teks = f.read_text(encoding="utf-8", errors="replace")
                break
        lis.setPlainText(teks or "Berkas LISENSI_PIHAK_KETIGA.txt tidak ditemukan.")
        tab.addTab(lis, "Lisensi pihak ketiga")
        lay.addWidget(tab, 1)
        h = QHBoxLayout()
        b = QPushButton("Buka folder lisensi")
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.AKAR / "licenses"
                                                                                   if (paths.AKAR / "licenses").exists()
                                                                                   else paths.AKAR))))
        t = QPushButton("✕ Tutup")
        t.clicked.connect(self.accept)
        h.addWidget(b)
        h.addStretch(1)
        h.addWidget(t)
        lay.addLayout(h)


def catatan_perubahan(sejak=None):
    """Isi CHANGELOG.md; sejak = versi terakhir yang sudah dilihat -> hanya bagian versi yang lebih baru."""
    f = paths.AKAR / "CHANGELOG.md"
    if not f.exists():
        return ""
    teks = f.read_text(encoding="utf-8")
    bagian = teks.split("\n## ")
    versi = ["## " + b for b in bagian[1:]]
    if sejak:
        def v(t):
            return tuple(int(x) for x in t.split("[", 1)[1].split("]", 1)[0].split(".") if x.isdigit())
        try:
            batas = tuple(int(x) for x in sejak.split("."))
            versi = [b for b in versi if v(b) > batas] or versi[:1]
        except (ValueError, IndexError):
            versi = versi[:1]
    import re
    return re.sub(r"(?m)^## \[([^\]]+)\]", r"## Versi \1", "\n\n".join(versi))


class DialogApaBaru(QDialog):
    """Ringkasan perubahan (CHANGELOG.md). Non-modal: muncul sekali setelah pembaruan, juga dari menu Bantuan."""

    def __init__(self, versi, parent=None, sejak=None):
        super().__init__(parent)
        self.setWindowTitle(f"Apa yang baru di VirmoDock {versi}")
        self.resize(720, 620)
        lay = QVBoxLayout(self)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setMarkdown(catatan_perubahan(sejak) or "Catatan perubahan tidak ditemukan.")
        lay.addWidget(tb)
        h = QHBoxLayout()
        h.addWidget(_ket("Panduan lengkap: Bantuan › Panduan pengguna (F1)."), 1)
        b = QPushButton("✕ Tutup")
        b.clicked.connect(self.close)
        h.addWidget(b)
        lay.addLayout(h)
