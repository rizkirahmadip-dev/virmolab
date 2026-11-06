"""Perekaman video dan animasi 3D untuk jendela utama.

Dipisahkan dari `mainwindow.py` supaya alur rekaman (putar kamera, kumpulkan bingkai, rangkai MP4/GIF/WebP)
berdiri sendiri dari kode viewer dan antrean. Metode di sini memakai `self` milik JendelaUtama: `MediaAnimasi`
dipasang sebagai mixin, bukan kelas mandiri.
"""
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QButtonGroup, QFileDialog, QMessageBox

from ..core import molekul
from ..core.proyek import nama_aman
from . import kerja, theme


class MediaAnimasi:
    """Metode animasi dan perekaman video JendelaUtama (mixin; lihat mainwindow.JendelaUtama)."""

    def ekspor_animasi(self):
        if not self.objek:
            self._galat("Viewport 3D kosong.")
            return
        if self.tab_tengah.currentWidget() is not self.w_view:
            self.tab_tengah.setCurrentWidget(self.w_view)
        from .dialog_animasi import DialogAnimasi
        dlg = DialogAnimasi(self, self.viewer.height() / max(1, self.viewer.width()))
        if not dlg.exec():
            return
        d = dlg.data()
        dasar = nama_aman(self.proyek.nama) if self.proyek else "virmolab"
        if d["fmt"] == "png":
            f = QFileDialog.getExistingDirectory(self, "Folder bingkai PNG",
                                                 str(self.proyek.p("ekspor")) if self.proyek else "")
            if f:
                f = str(Path(f, f"{dasar}_animasi_{d['jenis']}"))
        else:
            f = self._path("Simpan animasi", f"{dasar}_{d['jenis']}.{d['fmt']}",
                           {"gif": "GIF (*.gif)", "webp": "WebP (*.webp)"}.get(d["fmt"], "Video MP4 (*.mp4)"))
        if f:
            self.rekam_animasi(d, f)

    def rekam_animasi(self, d, f, selesai=None):
        """Rekam bingkai satu per satu dari viewport (asinkron). MP4: tiap bingkai langsung dialirkan ke encoder
        H.264 (hemat memori, sampai 4K); GIF/WebP/PNG: ditampung lalu disandikan di latar belakang."""
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QProgressDialog
        from ..core import animasi as animod
        import base64
        n = max(2, round(d["durasi"] * d["fps"]))
        video = d["fmt"] == "mp4"
        if video:
            from .perekam_video import RESOLUSI, PerekamVideo
            lebar, tinggi = RESOLUSI.get(d.get("resolusi"), RESOLUSI["fhd"])[:2]
        else:
            lebar = int(d["lebar"]) // 2 * 2
            tinggi = int(round(lebar * self.viewer.height() / max(1, self.viewer.width()))) // 2 * 2
        latar = {"putih": "#ffffff", "hitam": "#000000"}.get(d["latar"], theme.TOKEN[self.mode]["view"])
        # putar & goyang: bingkai terakhir != bingkai pertama agar putaran mulus saat diulang
        langkah = ([i / n for i in range(n)] if d["jenis"] in ("putar", "goyang")
                   else [i / (n - 1) for i in range(n)])
        prog = QProgressDialog(f"Merekam animasi {lebar} × {tinggi}…", "Batal", 0, n + 1, self)
        prog.setWindowTitle("Animasi 3D")
        prog.setMinimumDuration(0)
        prog.setValue(0)
        bingkai = []
        st = {"i": 0, "tunggu": False, "selesai": False}
        rek = PerekamVideo(f, lebar, tinggi, d["fps"], self) if video else None

        def akhiri(pesan=None):
            st["selesai"] = True
            self.viewer.js("animSelesai")
            prog.close()
            if rek:
                rek.batal()
            if pesan:
                self._galat(pesan)

        def berikut(_=None):
            if st["selesai"] or st["tunggu"]:
                return
            if prog.wasCanceled():
                akhiri()
                if video:
                    QTimer.singleShot(1500, lambda: Path(f).unlink(missing_ok=True))
                return
            if st["i"] >= n:
                st["selesai"] = True
                self.viewer.js("animSelesai")
                prog.setLabelText("Menyelesaikan video…" if video else "Menyandikan…")
                prog.setValue(n)
                if video:
                    rek.akhiri()
                else:
                    kerja.jalankan(lambda lapor: animod.simpan(bingkai, f, d["fmt"], d["fps"], lapor, (lebar, tinggi)),
                                   selesai=selesai_sandi, galat=lambda g: akhiri(f"Animasi gagal: {g}"))
                return
            if video and not rek.boleh_lagi():
                return                                  # encoder penuh: lanjut saat siap_lagi
            st["tunggu"] = True
            self.viewer.js("animBingkai", langkah[st["i"]], video, cb=terima)

        def terima(url):
            st["tunggu"] = False
            if st["selesai"]:
                return
            if not url or "," not in url:
                akhiri("Render bingkai gagal (WebGL).")
                return
            data = base64.b64decode(url.split(",", 1)[1])
            if video:
                rek.kirim(QImage.fromData(data))
            else:
                bingkai.append(data)
            st["i"] += 1
            prog.setValue(st["i"])
            QTimer.singleShot(0, berikut)

        def selesai_sandi(hasil):
            prog.close()
            ukuran = Path(hasil).stat().st_size if Path(hasil).is_file() else 0
            self.log.tulis(f"Animasi disimpan: {hasil}" + (f" ({ukuran / 1e6:.1f} MB)" if ukuran else ""))
            self.statusBar().showMessage(f"Animasi disimpan: {hasil}", 6000)
            if selesai:
                selesai(hasil)
            elif d["fmt"] != "png":
                QDesktopServices.openUrl(QUrl.fromLocalFile(hasil))

        if rek:
            rek.siap_lagi.connect(berikut)
            rek.selesai.connect(selesai_sandi)
            rek.galat.connect(lambda t: akhiri(f"Video gagal: {t}"))
        sudut = 30 if d["jenis"] == "goyang" else 360
        self.viewer.js("animMulai", lebar, tinggi, latar, d["jenis"], sudut, cb=lambda _: QTimer.singleShot(150, berikut))

    def gambar_ligan(self, o=None):
        """Editor Ketcher; o = objek ligan untuk diedit (struktur dimuat, hasil jadi ligan baru)."""
        from .dialog_ketcher import DialogKetcher
        awal, nama = None, ""
        if o is not None:
            try:
                from rdkit import Chem
                from ..core import kemiripan
                awal = Chem.MolToSmiles(kemiripan.mol_dari(o.teks, o.fmt))
                nama = f"{o.nama}_edit"
            except Exception:
                awal = None
        d = DialogKetcher(self, awal, nama)
        if d.exec():
            try:
                ob = molekul.dari_smiles(d.hasil_smiles, d.hasil_nama)
            except Exception as e:
                self._galat(f"Struktur tidak dapat dibuat 3D: {e}")
                return
            self.tambah_objek(ob, fokus=True)
            self.log.tulis(f"Ligan digambar (Ketcher): {d.hasil_nama} {d.hasil_smiles}")

    def ganti_bahasa(self, kode):
        """Simpan pilihan bahasa, lalu tawarkan mulai ulang.

        Lapisan terjemahan memasang pembungkus pada kelas Qt saat aplikasi dimulai (lihat i18n.pasang),
        sehingga bahasa tidak dapat ditukar pada jendela yang sudah terbentuk. Alih-alih meminta pengguna
        menutup sendiri, mulai ulang ditawarkan di tempat.
        """
        from .. import i18n
        kini = self.st.value("bahasa", "") or i18n.bahasa_bawaan()
        if kini == kode:
            self._segar_tombol_bahasa(kode)
            return
        self.st.setValue("bahasa", kode)
        self.st.sync()
        self._segar_tombol_bahasa(kode)
        k = QMessageBox(QMessageBox.Question, "Bahasa / Language",
                        "Bahasa antarmuka berganti setelah VirmoLab dibuka ulang.\n"
                        "The interface language changes after VirmoLab is restarted.", parent=self)
        b_ulang = k.addButton("Mulai ulang sekarang / Restart now", QMessageBox.AcceptRole)
        k.addButton("Nanti / Later", QMessageBox.RejectRole)
        k.setDefaultButton(b_ulang)
        k.exec()
        if k.clickedButton() is b_ulang:
            self.mulai_ulang()

    def _segar_tombol_bahasa(self, kode):
        """Samakan keadaan tombol ID | EN dengan setelan (menu dan tombol menyetel nilai yang sama)."""
        for b in getattr(self, "grp_bahasa", QButtonGroup(self)).buttons():
            b.setChecked(b.property("kode") == kode)

    def mulai_ulang(self):
        """Tutup jendela dengan pemeriksaan biasa, lalu jalankan VirmoLab lagi.

        closeEvent tetap dijalankan, sehingga docking atau MD yang sedang berjalan ditanyakan lebih dulu dan
        dijeda dengan rapi; bila pengguna membatalkan penutupan, aplikasi baru tidak jadi dijalankan.
        """
        import sys
        from PySide6.QtCore import QProcess
        from ..core import paths
        if not self.close():
            return
        if getattr(sys, "frozen", False):
            QProcess.startDetached(str(paths.EXE_UTAMA), [])
        else:
            QProcess.startDetached(sys.executable, ["-m", "virmolab"], str(paths.AKAR))
