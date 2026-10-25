"""Dialog Pasang alat lanjutan (WSL): periksa prasyarat, pasang paket alat Linux, pantau kemajuannya.

Paket "Docking GPU & RBFE" (Uni-Dock + OpenFE) dan "Co-folding & skor CNN" (Boltz-2 + GNINA) dipasang dengan skrip
yang ikut installer (core/alat_wsl.py). Pemeriksaan prasyarat dan status berjalan di latar; pemasangan berjalan
sebagai QProcess sehingga jendela tetap responsif, bisa dihentikan, dan bisa dilanjutkan bila unduhan putus.
"""
import time

from PySide6.QtCore import QProcess, Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QFrame, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .. import i18n
from ..core import alat_wsl as A
from ..core import paths
from ..core.lanjutan import teks_wsl
from . import icons, kerja, kit

TANDA = {True: "✓", False: "✗"}
# keadaan langkah pemasangan -> ikon tema (nomor untuk yang belum dimulai, seperti langkah alur kerja)
_IKON_LANGKAH = {"jalan": ("clock", "acc"), "selesai": ("check", "ok"), "gagal": ("x", "bad")}


class DialogAlatWsl(QDialog):
    alatBerubah = Signal()          # sesudah pemasangan sukses: jendela utama memperbarui ketersediaan fitur

    def __init__(self, jw, paket_awal=None):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Pasang alat lanjutan (WSL)")
        self.setMinimumSize(880, 540)
        layar = (jw.screen() if jw is not None else QApplication.primaryScreen()).availableGeometry()
        self.resize(min(1120, layar.width() - 60), min(780, layar.height() - 60))    # muat sembilan langkah
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._pr = None                  # Prasyarat terakhir
        self._status = {}
        self._proc = None
        self._paket = None               # paket yang sedang dipasang
        self._mulai = 0.0
        self._sisa = ""                  # potongan baris keluaran yang belum lengkap
        self._log = None
        self._pid = None                 # PID bash pemasang di dalam WSL
        self._dihentikan = False
        self._paket_awal = paket_awal
        self._bungkus = []               # label terbungkus yang tingginya disesuaikan dengan lebarnya
        self._pesan_syarat = []
        self._rincian = None             # None: ikut hasil pemeriksaan; True/False: pilihan pengguna
        self._pesan_akhir = None         # pesan hasil pemasangan yang tidak ditimpa pemeriksaan ulang
        self._bangun()
        self._t_waktu = QTimer(self)
        self._t_waktu.setInterval(1000)
        self._t_waktu.timeout.connect(self._detak)
        self._periksa()

    # ================================================================== tata letak
    def _bangun(self):
        luar = QVBoxLayout(self)
        luar.setContentsMargins(14, 12, 14, 12)
        luar.setSpacing(8)
        isi = QWidget()
        lay = QVBoxLayout(isi)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Pasang alat lanjutan (WSL)",
                                "Uni-Dock, OpenFE, GNINA, dan Boltz-2 hanya tersedia untuk Linux, jadi dipasang di WSL "
                                "(Windows Subsystem for Linux), bukan di dalam installer."))
        k = kit.catatan("Paket diunduh dari conda-forge, GitHub, PyPI, PyTorch, dan Hugging Face, lalu disimpan di folder "
                        "rumah Linux (~/virmolab-alat). Tidak ada data proyek yang dikirim. Fitur inti VirmoLab tidak "
                        "membutuhkan paket ini.", "muted")
        self._bungkus.append(k)
        lay.addWidget(k)

        g = QGroupBox("Prasyarat")
        vg = QVBoxLayout(g)
        h = QHBoxLayout()
        self.l_distro = QLabel("Distro Linux")
        self.cb_distro = QComboBox()
        self.cb_distro.setMinimumWidth(200)
        self.cb_distro.activated.connect(self._ganti_distro)
        h.addWidget(self.l_distro)
        h.addWidget(self.cb_distro)
        self.l_ringkas = QLabel("")
        self.l_ringkas.setWordWrap(True)
        self._bungkus.append(self.l_ringkas)
        h.addWidget(self.l_ringkas, 1)
        self.b_rincian = QPushButton("Tampilkan rincian")
        self.b_rincian.setObjectName("tautan")
        self.b_rincian.clicked.connect(self._alih_rincian)
        self.b_rincian.setVisible(False)
        h.addWidget(self.b_rincian)
        self.b_periksa = kit.tombol("Periksa ulang", self._periksa)
        h.addWidget(self.b_periksa)
        vg.addLayout(h)
        self.w_syarat = QWidget()
        self.grid = QGridLayout(self.w_syarat)
        self.grid.setContentsMargins(0, 4, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(6)
        self.grid.setColumnStretch(2, 1)
        vg.addWidget(self.w_syarat)
        lay.addWidget(g)

        h = QHBoxLayout()
        h.setSpacing(10)
        self.kartu = {}
        for kunci in A.PAKET:
            h.addWidget(self._kartu_paket(kunci), 1)
        lay.addLayout(h)

        g = QGroupBox("Kemajuan")
        self._g_kemajuan = g
        vk = QVBoxLayout(g)
        self.l_langkah = QLabel("Belum ada pemasangan yang berjalan.")
        self.l_langkah.setWordWrap(True)
        self._bungkus.append(self.l_langkah)
        vk.addWidget(self.l_langkah)
        h = QHBoxLayout()
        self.pb = QProgressBar()
        self.pb.setTextVisible(False)
        self.pb.setMaximumHeight(8)
        h.addWidget(self.pb, 1)
        self.l_waktu = QLabel("")
        self.l_waktu.setObjectName("mono")
        h.addWidget(self.l_waktu)
        self.b_log = kit.tombol("Tampilkan log", self._alih_log)
        self.b_henti = kit.tombol("Hentikan", self._hentikan)
        self.b_henti.setEnabled(False)
        h.addWidget(self.b_log)
        h.addWidget(self.b_henti)
        vk.addLayout(h)
        self.daftar_langkah = QListWidget()
        self.daftar_langkah.setSelectionMode(QAbstractItemView.NoSelection)
        self.daftar_langkah.setFocusPolicy(Qt.NoFocus)
        self.daftar_langkah.setVisible(False)
        vk.addWidget(self.daftar_langkah)
        self.t_log = QPlainTextEdit()
        self.t_log.setReadOnly(True)
        self.t_log.setMaximumBlockCount(4000)
        self.t_log.setMinimumHeight(180)
        self.t_log.setVisible(False)
        vk.addWidget(self.t_log, 1)
        self._lay = lay
        lay.addWidget(g)
        lay.addStretch(1)              # ruang sisa di bawah; pindah ke log saat log dibuka

        gulir = QScrollArea()
        gulir.setWidgetResizable(True)
        gulir.setFrameShape(QFrame.NoFrame)
        gulir.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        gulir.setWidget(isi)                 # layar laptop 1080p dengan skala 150% hanya ±680 px tingginya
        luar.addWidget(gulir, 1)
        self.l_status = kit.catatan("", "muted")
        self._bungkus.append(self.l_status)
        luar.addWidget(self.l_status)
        luar.addLayout(kit.bar_bawah(self))

    def _kartu_paket(self, kunci):
        p = A.PAKET[kunci]
        f = QFrame()
        f.setObjectName("kartu")
        v = QVBoxLayout(f)
        v.setContentsMargins(14, 10, 14, 12)
        v.setSpacing(4)
        judul = QLabel(p["nama"])
        judul.setObjectName("ubinJudul")
        v.addWidget(judul)
        alat = kit.catatan(p["alat"], "muted")
        self._bungkus.append(alat)
        v.addWidget(alat)
        rinci = kit.catatan(i18n.t(f"±{p['ukuran_gb']} GB di WSL · ") + i18n.t(p["lisensi"]), "muted")
        v.addWidget(rinci)
        st = QLabel("Memeriksa status…")
        st.setWordWrap(True)
        v.addWidget(st)
        catatan = kit.catatan("", "peringatan")
        catatan.setVisible(False)
        self._bungkus += [st, catatan]
        v.addWidget(catatan)
        v.addStretch(1)
        b = kit.tombol("Pasang", lambda _=False, k=kunci: self._pasang(k), utama=True)
        b.setEnabled(False)
        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(b)
        v.addLayout(h)
        self.kartu[kunci] = {"status": st, "catatan": catatan, "tombol": b, "bingkai": f}
        return f

    def _pas_tinggi(self):
        """QLabel terbungkus di dalam grid/kartu tidak menaikkan tinggi minimum tata letak, sehingga baris terakhir
        terpotong saat dialog sempit. Tinggi minimumnya ditetapkan dari lebar yang sedang dipakai."""
        for l in self._bungkus + self._pesan_syarat:
            if l.width() > 20:
                l.setMinimumHeight(l.heightForWidth(l.width()))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._pas_tinggi)

    def _pas_daftar(self):
        """Daftar langkah setinggi isinya (paling banyak sembilan baris), tanpa batang gulir."""
        d = self.daftar_langkah
        n = d.count()
        d.setFixedHeight(n * max(d.sizeHintForRow(0), d.fontMetrics().height() + 4) + 2 * d.frameWidth() + 4)
        d.setVisible(n > 0)

    def _atur_log(self, tampil):
        self.t_log.setVisible(tampil)
        self.b_log.setText(i18n.t("Sembunyikan log") if tampil else i18n.t("Tampilkan log"))
        self._lay.setStretchFactor(self._g_kemajuan, 1 if tampil else 0)
        self._lay.setStretch(self._lay.indexOf(self._g_kemajuan) + 1, 0 if tampil else 1)

    def _status_teks(self, teks, jenis="muted"):
        self.l_status.setText(teks)
        kit.ganti_jenis(self.l_status, jenis if teks else "muted")
        QTimer.singleShot(0, self._pas_tinggi)

    # ================================================================== prasyarat & status
    def _periksa(self):
        if self._proc is not None:
            return
        self.b_periksa.setEnabled(False)
        for k in self.kartu.values():
            k["tombol"].setEnabled(False)
        self._status_teks("Memeriksa WSL, GPU, disk, dan koneksi…")
        distro = self.cb_distro.currentData() or None

        def kerjakan(lapor=None):
            pr = A.periksa_prasyarat(distro=distro)
            st = A.status_paket() if pr.wsl_siap and pr.distro else {}
            return pr, st

        kerja.jalankan(kerjakan, selesai=self._hasil_periksa,
                       galat=lambda g: (self.b_periksa.setEnabled(True),
                                        self._status_teks(i18n.t("Pemeriksaan gagal: ") + str(g).splitlines()[0],
                                                          "peringatan")))

    def _hasil_periksa(self, hasil):
        self._pr, self._status = hasil
        self.b_periksa.setEnabled(True)
        pr = self._pr
        self.cb_distro.blockSignals(True)
        self.cb_distro.clear()
        for d in pr.daftar_distro:
            self.cb_distro.addItem(f"{d['nama']} (WSL {d['versi']})" + (i18n.t(" · bawaan") if d["bawaan"] else ""),
                                   d["nama"])
        i = self.cb_distro.findData(pr.distro)
        if i >= 0:
            self.cb_distro.setCurrentIndex(i)
        self.cb_distro.blockSignals(False)
        tampak = len(pr.daftar_distro) > 1
        self.cb_distro.setVisible(tampak)
        self.l_distro.setVisible(tampak)
        self._isi_syarat(pr)
        self._isi_kartu()
        if self._pesan_akhir:
            self._status_teks(*self._pesan_akhir)
            self._pesan_akhir = None
        elif not pr.wsl_siap:
            self._status_teks("WSL belum siap. Ikuti tombol perbaikan pada daftar prasyarat.", "peringatan")
        elif any(v[0] for v in pr.bisa.values()):
            self._status_teks("Prasyarat terpenuhi. Pilih paket yang ingin dipasang.")
        else:
            self._status_teks("Paket belum dapat dipasang; lihat prasyarat yang bertanda ✗.", "peringatan")
        if self._paket_awal and pr.bisa.get(self._paket_awal, (False,))[0]:
            self.kartu[self._paket_awal]["bingkai"].setFocus()
            self._paket_awal = None

    def _isi_syarat(self, pr):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self._pesan_syarat = []
        semua_ok = bool(pr.syarat) and all(s.ok for s in pr.syarat)
        if semua_ok:
            disk = i18n.t(f"{pr.disk_gb} GB bebas") if pr.disk_gb is not None else ""
            self.l_ringkas.setText("✓  " + i18n.t("Semua prasyarat terpenuhi") + " · " + " · ".join(
                x for x in (f"{pr.distro} (WSL 2)", pr.gpu.split(",")[0].strip(), disk) if x))
        else:
            n = sum(1 for s in pr.syarat if not s.ok)
            self.l_ringkas.setText(i18n.t(f"{n} prasyarat perlu perhatian; lihat baris bertanda ✗ atau !."))
        self.l_ringkas.setStyleSheet(f"color: {kit.hx('ok' if semua_ok else 'warn')};")
        self.b_rincian.setVisible(semua_ok)
        self._atur_rincian(self._rincian if (semua_ok and self._rincian is not None) else not semua_ok)
        for r, s in enumerate(pr.syarat):
            tanda = QLabel(TANDA[s.ok] if (s.ok or s.wajib) else "!")
            tanda.setStyleSheet(f"color: {kit.hx('ok' if s.ok else ('bad' if s.wajib else 'warn'))};"
                                "font-weight: 600;")
            judul = QLabel(i18n.t(s.judul))
            pesan = kit.catatan(i18n.t(s.pesan), "muted")
            self._pesan_syarat.append(pesan)
            self.grid.addWidget(tanda, r, 0, Qt.AlignTop)
            self.grid.addWidget(judul, r, 1, Qt.AlignTop)
            self.grid.addWidget(pesan, r, 2, Qt.AlignTop)
            b = self._tombol_aksi(s)
            if b is not None:
                self.grid.addWidget(b, r, 3, Qt.AlignTop)
        QTimer.singleShot(0, self._pas_tinggi)

    def _atur_rincian(self, tampil):
        self.w_syarat.setVisible(tampil)
        self.b_rincian.setText(i18n.t("Sembunyikan rincian") if tampil else i18n.t("Tampilkan rincian"))

    def _alih_rincian(self):
        self._rincian = not self.w_syarat.isVisible()
        self._atur_rincian(self._rincian)
        QTimer.singleShot(0, self._pas_tinggi)

    def _tombol_aksi(self, s):
        if s.ok or not s.aksi:
            return None
        if s.aksi == "pasang_wsl":
            return kit.tombol("Pasang WSL…", self._pasang_wsl,
                              tip="Membuka jendela persetujuan administrator Windows, lalu perlu restart")
        if s.aksi == "terminal":
            return kit.tombol("Buka terminal Ubuntu", lambda _=False, p=s.perintah: self._buka_terminal(p))
        if s.aksi == "salin":
            return kit.tombol("Salin perintah", lambda _=False, p=s.perintah: self._salin(p))
        return None

    def _isi_kartu(self):
        pr = self._pr
        for kunci, k in self.kartu.items():
            boleh, alasan, lewati = pr.bisa.get(kunci, (False, "", []))
            st = self._status.get(kunci, {})
            baris = []
            for nama, s in st.items():
                if s.get("ada"):
                    baris.append(f"✓ {nama}")
                elif nama.replace("-", "").lower().startswith(tuple(lewati)):
                    baris.append(i18n.t(f"– {nama} dilewati (butuh GPU NVIDIA)"))
                else:
                    baris.append(i18n.t(f"✗ {nama} belum terpasang"))
            k["status"].setText("   ".join(baris) if baris else i18n.t("Status belum dapat dibaca."))
            terpasang = bool(st) and all(s.get("ada") or nama.replace("-", "").lower().startswith(tuple(lewati))
                                         for nama, s in st.items())
            k["tombol"].setText(i18n.t("Pasang ulang") if terpasang else i18n.t("Pasang"))
            k["tombol"].setEnabled(boleh and self._proc is None)
            k["tombol"].setToolTip("" if boleh else i18n.t(alasan))
            teks_catatan = alasan if boleh and alasan else ("" if boleh else alasan)
            k["catatan"].setText(i18n.t(teks_catatan))
            k["catatan"].setVisible(bool(teks_catatan))
        QTimer.singleShot(0, self._pas_tinggi)

    def _ganti_distro(self, *_):
        d = self.cb_distro.currentData()
        if not d:
            return
        paths.settings().setValue("wsl_distro", d)
        A.segarkan_semua()
        self._periksa()

    # ================================================================== aksi perbaikan
    def _pasang_wsl(self):
        QProcess.startDetached(A.argv_pasang_wsl()[0], A.argv_pasang_wsl()[1:])
        self._status_teks("Setujui jendela administrator Windows dan tunggu sampai pemasangan WSL selesai. Sesudah itu "
                          "restart komputer, buka Ubuntu sekali dari menu Start untuk membuat nama pengguna dan kata "
                          "sandi, lalu buka dialog ini lagi.", "info")

    def _buka_terminal(self, perintah):
        if perintah:
            kit.salin(perintah)
        argv = A.argv_terminal(self._pr.distro if self._pr else "")
        QProcess.startDetached(argv[0], argv[1:])
        self._status_teks(("Perintah sudah disalin. Tempel di terminal Ubuntu (klik kanan), masukkan kata sandi "
                           "Ubuntu, lalu klik Periksa ulang.") if perintah else
                          "Terminal Ubuntu dibuka. Selesaikan pesan yang muncul di sana, lalu klik Periksa ulang.",
                          "info")

    def _salin(self, perintah):
        kit.salin(perintah)
        self._status_teks(i18n.t("Perintah disalin: ") + perintah + i18n.t(". Jalankan di PowerShell, lalu klik "
                                                                             "Periksa ulang."), "info")

    # ================================================================== pemasangan
    def _pasang(self, kunci):
        if self._proc is not None or not self._pr:
            return
        boleh, _alasan, lewati = self._pr.bisa.get(kunci, (False, "", []))
        if not boleh:
            return
        self._paket = kunci
        self._mulai = time.time()
        self._sisa = ""
        self._pid = None
        self._log = A.berkas_log(kunci).open("w", encoding="utf-8")
        self.t_log.clear()
        self.daftar_langkah.clear()
        for _penanda, label in A.PAKET[kunci]["langkah"]:
            self.daftar_langkah.addItem(QListWidgetItem(i18n.t(label)))
            self._tandai(self.daftar_langkah.count() - 1, "tunggu")
        self._pas_daftar()
        self.pb.setRange(0, len(A.PAKET[kunci]["langkah"]))
        self.pb.setValue(0)
        self.l_langkah.setText(i18n.t(f"Memasang {A.PAKET[kunci]['nama']}… Biarkan dialog terbuka; unduhan bisa "
                                      "makan waktu lama di koneksi lambat."))
        for k in self.kartu.values():
            k["tombol"].setEnabled(False)
        self.b_periksa.setEnabled(False)
        self.cb_distro.setEnabled(False)
        self.b_henti.setEnabled(True)
        argv = A.argv_pasang(self._pr.distro)
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(self._baca)
        p.finished.connect(self._selesai)
        p.errorOccurred.connect(self._galat_proses)
        self._proc = p
        p.start(argv[0], argv[1:])
        p.write(A.skrip_paket(kunci, lewati))
        p.closeWriteChannel()
        self._t_waktu.start()
        self._status_teks("")

    def _baca(self):
        teks = self._sisa + teks_wsl(bytes(self._proc.readAllStandardOutput()))
        baris = teks.replace("\r", "\n").split("\n")
        self._sisa = baris.pop()
        for b in baris:
            pid = A.pid_dari(b)
            if pid is not None:
                self._pid = pid
                continue
            self._tulis_log(b)
            k = A.urai_kemajuan(b, self._paket)
            if k is None:
                continue
            i, total, label = k
            if i >= 0:
                for j in range(min(i, total)):
                    self._tandai(j, "selesai")
                if i < total:
                    self._tandai(i, "jalan")
                self.pb.setValue(i)
            self.l_langkah.setText(i18n.t(label))

    def _tandai(self, j, keadaan):
        it = self.daftar_langkah.item(j)
        it.setData(Qt.UserRole, keadaan)
        if keadaan in _IKON_LANGKAH:
            nama, warna = _IKON_LANGKAH[keadaan]
            it.setIcon(icons.ikon(nama, kit.hx(warna)))
        else:
            it.setIcon(icons.ikon_nomor(j + 1, kit.hx("mut"), 16))

    def _tandai_berjalan(self, keadaan):
        for j in range(self.daftar_langkah.count()):
            if self.daftar_langkah.item(j).data(Qt.UserRole) == "jalan":
                self._tandai(j, keadaan)

    def _tulis_log(self, b):
        if not b.strip():
            return
        self.t_log.appendPlainText(b)
        if self._log:
            self._log.write(b + "\n")
            self._log.flush()

    def _detak(self):
        s = int(time.time() - self._mulai)
        self.l_waktu.setText(f"{s // 3600:d}:{s // 60 % 60:02d}:{s % 60:02d}")

    def _galat_proses(self, e):
        if e == QProcess.FailedToStart:
            self._tulis_log("wsl.exe tidak dapat dijalankan.")

    def _selesai(self, kode, _status):
        if self._sisa:
            self._tulis_log(self._sisa)
            self._sisa = ""
        self._t_waktu.stop()
        if self._log:
            self._log.close()
            self._log = None
        log = self.t_log.toPlainText()
        sukses = kode == 0 and "PAKET_SELESAI" in log
        nama = A.PAKET[self._paket]["nama"]
        self._proc = None
        self.b_henti.setEnabled(False)
        self.cb_distro.setEnabled(True)
        if sukses:
            self.pb.setValue(self.pb.maximum())
            for j in range(self.daftar_langkah.count()):
                self._tandai(j, "selesai")
            self.l_langkah.setText(i18n.t(f"{nama} terpasang dalam {self.l_waktu.text()}."))
            self._pesan_akhir = ("Status fitur diperbarui; tidak perlu membuka ulang VirmoLab.", "info")
            A.segarkan_semua()
            self.alatBerubah.emit()
        elif self._dihentikan:
            self._tandai_berjalan("tunggu")
            self.l_langkah.setText(i18n.t("Pemasangan dihentikan. Klik Pasang lagi untuk melanjutkan; unduhan yang "
                                          "sudah selesai tidak diulang."))
        else:
            self._tandai_berjalan("gagal")
            self.l_langkah.setText(i18n.t(A.pesan_gagal(kode, log)))
            self._atur_log(True)
            self._pesan_akhir = (i18n.t("Log lengkap: ") + str(A.berkas_log(self._paket)), "peringatan")
        self._dihentikan = False
        self._periksa()

    def _hentikan(self):
        if self._proc is None:
            return
        self._dihentikan = True
        if self._pid:          # mematikan wsl.exe saja tidak menghentikan unduhan yang berjalan di dalam Linux
            argv = A.argv_hentikan(self._pr.distro, self._pid)
            QProcess.startDetached(argv[0], argv[1:])      # tidak menahan jendela selama WSL menjawab
        self._proc.kill()

    def _alih_log(self):
        self._atur_log(not self.t_log.isVisible())

    def closeEvent(self, e):
        if self._proc is not None:
            if QMessageBox.question(self, i18n.t("Pemasangan berjalan"),
                                    i18n.t("Pemasangan masih berjalan. Hentikan dan tutup? Unduhan yang sudah selesai "
                                           "tidak hilang.")) != QMessageBox.Yes:
                e.ignore()
                return
            self._hentikan()
        super().closeEvent(e)
