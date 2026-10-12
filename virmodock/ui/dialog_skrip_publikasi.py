"""Dialog Skrip figur publikasi (Alat › Skrip figur PyMOL & ChimeraX…).

Menulis berkas .pml dan .cxc yang memuat reseptor + pose aktif, mewarnai kantong, menggambar ikatan hidrogen,
dan merender gambar beresolusi tinggi. Struktur yang dirujuk ikut disalin agar skrip bisa dijalankan apa adanya.
"""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QFileDialog, QFormLayout, QGroupBox, QLineEdit, QPlainTextEdit, QTabWidget,
                               QVBoxLayout)

from ..core import skrip_publikasi
from . import kit


class DialogSkripPublikasi(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Skrip figur publikasi")
        self.resize(880, 680)
        self.rec_teks, self.rec_nama, _ = kit.reseptor_proyek(jw)
        self.pose = kit.pose_aktif(jw)
        self.residu = self._residu_kunci()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "Skrip figur untuk PyMOL dan UCSF ChimeraX",
            "Skrip mengatur kartun protein, stik ligan dan residu kantong, garis putus ikatan hidrogen, serta "
            "render ray-tracing 2400 × 1800 piksel (± 300 dpi pada lebar 8 cm)."))

        g = QGroupBox("Isi figur")
        form = QFormLayout(g)
        form.setHorizontalSpacing(16)
        self.t_nama = QLineEdit(self._nama_dasar())
        self.t_nama.textChanged.connect(self.pratinjau)
        form.addRow("Nama berkas", self.t_nama)
        form.addRow("Reseptor", kit.catatan(self.rec_nama or "– belum ada reseptor di proyek –"))
        form.addRow("Ligan", kit.catatan(self._nama_pose()))
        form.addRow("Residu dilabeli", kit.catatan(", ".join(self.residu) if self.residu
                                                   else "– tidak ada; buka pose untuk melabeli residu interaksi –"))
        lay.addWidget(g)

        self.tab = QTabWidget()
        self.e_pml = self._editor()
        self.e_cxc = self._editor()
        self.tab.addTab(self.e_pml, "PyMOL (.pml)")
        self.tab.addTab(self.e_cxc, "ChimeraX (.cxc)")
        lay.addWidget(self.tab, 1)

        lay.addWidget(kit.catatan(
            "Skrip ditulis bersama salinan struktur (reseptor.pdb dan ligan.pdb) di folder tujuan, jadi jalurnya "
            "relatif dan tetap sahih bila folder dipindahkan."))
        self.l_status = kit.catatan("")
        lay.addLayout(kit.bar_bawah(self, kiri=[kit.tombol("Salin skrip tab ini", self.salin), self.l_status],
                                    kanan=[kit.tombol("Simpan skrip && struktur…", self.simpan, utama=True)]))
        self.pratinjau()

    def _editor(self):
        e = QPlainTextEdit()
        e.setReadOnly(True)
        e.setObjectName("mono")
        e.setLineWrapMode(QPlainTextEdit.NoWrap)
        return e

    def _nama_pose(self):
        if self.pose is None:
            return "– buka satu pose hasil docking agar ikut digambar –"
        return f"{self.pose.info.get('ligan', self.pose.nama)} · {self.pose.nama}"

    def _nama_dasar(self):
        if self.pose is None:
            return "figur_docking"
        from ..core.proyek import nama_aman
        return nama_aman(f"{self.pose.info.get('ligan', 'ligan')}_{self.pose.nama}")

    def _residu_kunci(self):
        """Residu dengan ikatan hidrogen / jembatan garam pada pose aktif (maksimal 6)."""
        a = getattr(self.jw, "_aktif_inter", None) or {}
        urut, lihat = [], set()
        for x in a.get("daftar", []):
            if x.get("jenis") not in ("hbond", "garam"):
                continue
            nama = f"{x['resn']} {x['resi']} ({x['rantai']})"
            if nama not in lihat:
                lihat.add(nama)
                urut.append(nama)
        return urut[:6]

    # ------------------------------------------------------------------ isi
    def _jalur(self):
        """Nama berkas yang dirujuk skrip — sama dengan salinan struktur yang ditulis di folder tujuan."""
        return "reseptor.pdb", "ligan.pdb"

    def pratinjau(self):
        nama = self.t_nama.text().strip() or "figur_docking"
        rec, lig = self._jalur()
        self.e_pml.setPlainText(skrip_publikasi.buat_skrip_pymol(rec, lig, self.residu, nama))
        self.e_cxc.setPlainText(skrip_publikasi.buat_skrip_chimerax(rec, lig, self.residu, nama))

    def salin(self):
        e = self.e_pml if self.tab.currentIndex() == 0 else self.e_cxc
        kit.salin(e.toPlainText(), self.l_status,
                  "Skrip disalin. Di PyMOL: File › Run Script; di ChimeraX: Open berkas .cxc.")

    def simpan(self):
        if not self.rec_teks:
            self.l_status.setText("Belum ada reseptor untuk ditulis.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Folder tujuan skrip figur",
                                                  str(self.jw.proyek.folder if self.jw.proyek else Path.home()))
        if not folder:
            return
        f = Path(folder)
        (f / "reseptor.pdb").write_text(self.rec_teks, encoding="utf-8")
        if self.pose is not None:
            (f / "ligan.pdb").write_text(self.pose.teks, encoding="utf-8")
        nama = self.t_nama.text().strip() or "figur_docking"
        hasil = skrip_publikasi.simpan_skrip_publikasi(folder, nama, "reseptor.pdb", "ligan.pdb", self.residu)
        self.l_status.setText(f"Tersimpan: {Path(hasil['pymol']).name}, {Path(hasil['chimerax']).name} dan salinan "
                              "struktur.")
        self.jw._info(f"Skrip figur publikasi ditulis ke {folder}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
