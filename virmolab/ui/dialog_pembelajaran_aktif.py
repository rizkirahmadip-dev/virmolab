"""Dialog Penapisan pustaka besar (pembelajaran aktif): baca pustaka, atur rencana putaran, pantau kampanye.

Kampanyenya dijalankan oleh PengendaliAL milik jendela utama (ui/pengendali_al.py), jadi dialog ini boleh ditutup
selama docking berjalan; membukanya lagi menampilkan keadaan terkini dari proyek.
"""
import csv
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLineEdit, QMessageBox, QProgressBar, QSpinBox, QSplitter, QStackedWidget, QTabWidget,
                               QVBoxLayout, QWidget)

from .. import i18n
from ..core import grafik
from ..core import mesin as M
from ..core import pembelajaran_aktif as PA
from . import kerja, kit

SUMBER = (("berkas", "Berkas SMILES, CSV, atau SDF"), ("coconut", "Bahan alam COCONUT (basis data lokal)"),
          ("obat", "Obat disetujui (ChEMBL, bawaan)"))
KOLOM_PUTARAN = ["Putaran", "Pemilihan", "Ligan", "Kumulatif", "Gagal", "ΔG terbaik", "Rata-rata 100 teratas",
                 "ρ prediksi", "Status"]
KOLOM_PERINGKAT = ["#", "Nama", "ΔG (kkal/mol)", "Prediksi sebelum docking", "Putaran", "SMILES"]
KOLOM_PREDIKSI = ["#", "Nama", "Prediksi ΔG (kkal/mol)", "Ketidakpastian (±)", "SMILES"]
LABEL_STATUS = {"baru": ("Belum dimulai", "info"), "berjalan": ("Berjalan", "ok"), "dijeda": ("Dijeda", "warn"),
                "selesai": ("Selesai", "ok")}
METODE = {"acak": "Acak", "rf+greedy": "RF · greedy", "rf+ucb": "RF · UCB", "mlp+greedy": "JS · greedy",
          "mlp+ucb": "JS · UCB", "rf+acak": "Acak", "mlp+acak": "Acak"}


def _jenis(label, jenis):
    """Ganti gaya label catatan (muted | info | peringatan) setelah label dibuat."""
    label.setObjectName(jenis)
    label.style().unpolish(label)
    label.style().polish(label)


def _n(x):
    """Bilangan bulat dengan pemisah ribuan sesuai bahasa antarmuka."""
    s = f"{int(x):,}"
    return s if i18n.inggris() else s.replace(",", ".")


class DialogPembelajaranAktif(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.al = jw.pengendali_al
        self.setWindowTitle("Penapisan pustaka besar (pembelajaran aktif)")
        self.setMinimumSize(1120, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._pustaka = None          # PA.Pustaka hasil "Baca pustaka" (belum menjadi kampanye)
        self._sumber_teks = ""
        self._prediksi = {}           # id kampanye -> [(indeks, rata, sb)]
        self._dimuat = set()          # kampanye yang pustakanya sudah diminta dimuat untuk tampilan
        self._bangun()
        self.al.berubah.connect(self._berubah)
        self.al.kemajuan.connect(self._kemajuan)
        self.al.galat.connect(self._galat)
        self._ganti_sumber()
        self._perbarui_rencana()
        self._isi_daftar_kampanye()

    # ================================================================== tata letak
    def _bangun(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Penapisan pustaka besar",
                                "Docking sebagian kecil pustaka, latih model dari skornya, lalu docking senyawa "
                                "berikutnya yang diprediksi paling kuat. Mengikuti MolPAL (Graff dkk., 2021)."))
        split = QSplitter(Qt.Horizontal, self)
        split.setChildrenCollapsible(False)
        split.addWidget(self._bangun_kiri())
        split.addWidget(self._bangun_kanan())
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([370, 760])
        lay.addWidget(split, 1)
        self.l_status = kit.catatan("", "muted")
        lay.addWidget(self.l_status)
        self.b_metode = kit.tombol("Salin metode", self._salin_metode,
                                   tip="Paragraf metode untuk naskah, dengan angka kampanye yang dipilih")
        self.b_csv = kit.tombol("Ekspor CSV…", self._ekspor_csv, tip="Semua senyawa yang sudah didocking beserta "
                                                                       "prediksi model sebelum docking")
        lay.addLayout(kit.bar_bawah(self, kiri=(self.b_metode, self.b_csv)))

    def _bangun_kiri(self):
        w = QWidget()
        w.setMaximumWidth(430)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 8, 0)
        v.setSpacing(8)

        g = QGroupBox("1 · Pustaka senyawa")
        vg = QVBoxLayout(g)
        self.cb_sumber = QComboBox()
        for k, t in SUMBER:
            self.cb_sumber.addItem(t, k)
        self.cb_sumber.currentIndexChanged.connect(self._ganti_sumber)
        vg.addWidget(self.cb_sumber)
        self.tumpuk = QStackedWidget()
        # berkas
        hal = QWidget()
        h = QHBoxLayout(hal)
        h.setContentsMargins(0, 0, 0, 0)
        self.e_berkas = QLineEdit()
        self.e_berkas.setReadOnly(True)
        self.e_berkas.setPlaceholderText("Belum ada berkas")
        h.addWidget(self.e_berkas, 1)
        h.addWidget(kit.tombol("Pilih…", self._pilih_berkas))
        self.tumpuk.addWidget(hal)
        # COCONUT
        hal = QWidget()
        f = QFormLayout(hal)
        f.setContentsMargins(0, 0, 0, 0)
        self.sp_coconut = QSpinBox()
        self.sp_coconut.setRange(1000, 1_000_000)
        self.sp_coconut.setSingleStep(10000)
        self.sp_coconut.setValue(50000)
        self.sp_coconut.setGroupSeparatorShown(True)
        f.addRow("Maks. senyawa", self.sp_coconut)
        self.chk_lipinski = QCheckBox("Hanya ≤ 1 pelanggaran Lipinski")
        self.chk_lipinski.setChecked(True)
        f.addRow("", self.chk_lipinski)
        self.l_coconut = kit.catatan("", "muted")
        f.addRow(self.l_coconut)
        self.tumpuk.addWidget(hal)
        # obat
        hal = QWidget()
        vo = QVBoxLayout(hal)
        vo.setContentsMargins(0, 0, 0, 0)
        vo.addWidget(kit.catatan("Molekul kecil yang disetujui (ChEMBL max_phase 4), ikut terpasang. Cocok untuk "
                                 "mencoba alur atau repurposing obat.", "muted"))
        self.tumpuk.addWidget(hal)
        vg.addWidget(self.tumpuk)
        h = QHBoxLayout()
        self.b_baca = kit.tombol("Baca pustaka", self._baca_pustaka)
        h.addWidget(self.b_baca)
        h.addStretch(1)
        vg.addLayout(h)
        self.l_pustaka = kit.catatan("Belum ada pustaka yang dibaca.", "muted")
        vg.addWidget(self.l_pustaka)
        v.addWidget(g)

        g = QGroupBox("2 · Rencana putaran")
        f = QFormLayout(g)
        self.cb_model = QComboBox()
        self.cb_model.addItem("Jaringan saraf (ensemble 3)", "mlp")
        self.cb_model.addItem("Random forest", "rf")
        self.cb_model.setToolTip("Model pengganti yang memprediksi skor docking dari sidik jari pasangan atom")
        f.addRow("Model", self.cb_model)
        self.cb_akuisisi = QComboBox()
        self.cb_akuisisi.addItem("UCB: prediksi + ketidakpastian", "ucb")
        self.cb_akuisisi.addItem("Greedy: prediksi terbaik saja", "greedy")
        self.cb_akuisisi.addItem("Acak (pembanding tanpa model)", "acak")
        f.addRow("Pemilihan", self.cb_akuisisi)
        self.sp_awal = QSpinBox()
        self.sp_batch = QSpinBox()
        for sp in (self.sp_awal, self.sp_batch):
            sp.setRange(20, 1_000_000)
            sp.setGroupSeparatorShown(True)
            sp.valueChanged.connect(self._perbarui_rencana)
        f.addRow("Batch awal (acak)", self.sp_awal)
        f.addRow("Batch per putaran", self.sp_batch)
        self.sp_putaran = QSpinBox()
        self.sp_putaran.setRange(1, 50)
        self.sp_putaran.setValue(5)
        self.sp_putaran.valueChanged.connect(self._perbarui_rencana)
        f.addRow("Putaran sesudah batch awal", self.sp_putaran)
        self.l_rencana = kit.catatan("", "muted")
        f.addRow(self.l_rencana)
        v.addWidget(g)

        g = QGroupBox("3 · Docking")
        vd = QVBoxLayout(g)
        self.l_docking = kit.catatan("", "muted")
        vd.addWidget(self.l_docking)
        v.addWidget(g)

        self.b_mulai = kit.tombol("Mulai penapisan", self._mulai, utama=True)
        v.addWidget(self.b_mulai)
        v.addStretch(1)
        return w

    def _bangun_kanan(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 0, 0, 0)
        v.setSpacing(8)
        h = QHBoxLayout()
        self.cb_kampanye = QComboBox()
        self.cb_kampanye.setMinimumWidth(260)
        self.cb_kampanye.currentIndexChanged.connect(lambda *_: self._tampilkan())
        h.addWidget(self.cb_kampanye, 1)
        self.lc_status = kit.lencana("", "info")
        h.addWidget(self.lc_status)
        self.b_lanjut = kit.tombol("Lanjutkan", self._lanjutkan, tip="Lanjutkan job putaran yang dijeda, atau pilih "
                                                                   "putaran berikutnya")
        self.b_berhenti = kit.tombol("Berhenti setelah putaran ini", self._berhenti,
                                     tip="Docking putaran yang berjalan diselesaikan; putaran baru tidak dimulai")
        self.b_henti = kit.tombol("Hentikan sekarang", self._hentikan,
                                  tip="Batalkan job putaran; ligan yang belum didocking kembali menjadi kandidat")
        self.b_hapus = kit.tombol("Hapus", self._hapus, tip="Hapus catatan kampanye; hasil docking tetap di proyek")
        for b in (self.b_lanjut, self.b_berhenti, self.b_henti, self.b_hapus):
            h.addWidget(b)
        v.addLayout(h)

        self.pb = QProgressBar()
        self.pb.setTextVisible(False)
        self.pb.setMaximumHeight(6)
        self.pb.setVisible(False)
        v.addWidget(self.pb)
        self.l_tahap = kit.catatan("", "muted")
        v.addWidget(self.l_tahap)

        self.k_dock = kit.Kartu("Didocking", "–")
        self.k_terbaik = kit.Kartu("ΔG terbaik", "–")
        self.k_top = kit.Kartu("Rata-rata 100 teratas", "–")
        self.k_model = kit.Kartu("Akurasi model", "–")
        v.addLayout(kit.baris_kartu(self.k_dock, self.k_terbaik, self.k_top, self.k_model))

        self.tab = QTabWidget()
        # putaran: tabel + grafik
        hal = QSplitter(Qt.Vertical)
        hal.setChildrenCollapsible(False)
        self.t_putaran = kit.tabel(KOLOM_PUTARAN, regang=len(KOLOM_PUTARAN) - 1)
        hal.addWidget(self.t_putaran)
        self.grafik = kit.GambarSvg()
        hal.addWidget(self.grafik)
        hal.setSizes([200, 260])
        self.tab.addTab(hal, "Putaran")
        # peringkat
        self.t_peringkat = kit.tabel(KOLOM_PERINGKAT, regang=len(KOLOM_PERINGKAT) - 1, urut=True)
        self.t_peringkat.setToolTip("Klik dua kali untuk membuka pose di viewer")
        self.t_peringkat.itemDoubleClicked.connect(self._buka_pose)
        self.tab.addTab(self.t_peringkat, "Peringkat")
        # prediksi
        hal = QWidget()
        vp = QVBoxLayout(hal)
        vp.setContentsMargins(0, 6, 0, 0)
        h = QHBoxLayout()
        self.b_prediksi = kit.tombol("Hitung prediksi", self._hitung_prediksi,
                                     tip="Latih model pada semua skor yang ada, lalu peringkatkan senyawa yang belum "
                                         "didocking")
        h.addWidget(self.b_prediksi)
        h.addWidget(kit.catatan("Kandidat yang belum didocking tetapi diprediksi kuat. Prediksi bukan hasil docking: "
                                "docking-kan dulu sebelum dipakai.", "muted"), 1)
        vp.addLayout(h)
        self.t_prediksi = kit.tabel(KOLOM_PREDIKSI, regang=len(KOLOM_PREDIKSI) - 1, urut=True)
        vp.addWidget(self.t_prediksi, 1)
        self.tab.addTab(hal, "Prediksi belum didocking")
        v.addWidget(self.tab, 1)
        self.l_kosong = kit.catatan("Belum ada kampanye di proyek ini. Baca pustaka di kiri, atur rencana, lalu klik "
                                    "Mulai penapisan.", "muted")
        v.addWidget(self.l_kosong)
        return w

    def changeEvent(self, e):
        # setelan docking bisa diubah di jendela utama selama dialog terbuka: segarkan saat dialog kembali aktif
        if e.type() == QEvent.ActivationChange and self.isActiveWindow():
            self._perbarui_rencana()
        super().changeEvent(e)

    # ================================================================== pustaka & rencana
    def _ganti_sumber(self, *_):
        k = self.cb_sumber.currentData()
        self.tumpuk.setCurrentIndex([s for s, _ in SUMBER].index(k))
        if k == "coconut":
            from ..core import pustaka
            info = pustaka.coconut_ada()
            if info:
                self.l_coconut.setText(f"Basis data lokal: {_n(info['jumlah'])} senyawa ({info['waktu'][:10]}).")
                self.b_baca.setEnabled(True)
            else:
                self.l_coconut.setText("COCONUT belum diunduh. Unduh sekali lewat Siapkan › Pustaka ligan.")
                self.b_baca.setEnabled(False)
        else:
            self.b_baca.setEnabled(True)

    def _pilih_berkas(self):
        f, _ = QFileDialog.getOpenFileName(self, "Pilih pustaka senyawa", "",
                                           "Pustaka senyawa (*.smi *.smiles *.txt *.csv *.tsv *.sdf *.gz);;"
                                           "Semua berkas (*)")
        if f:
            self.e_berkas.setText(f)

    def _baca_pustaka(self):
        k = self.cb_sumber.currentData()
        if k == "berkas":
            f = self.e_berkas.text().strip()
            if not f:
                self._pilih_berkas()
                f = self.e_berkas.text().strip()
                if not f:
                    return
            self._sumber_teks = Path(f).name

            def ambil(lapor):
                return PA.siapkan_pustaka(PA.baca_entri(f), lapor)
        elif k == "coconut":
            from ..core import pustaka
            batas, lip = self.sp_coconut.value(), self.chk_lipinski.isChecked()
            self._sumber_teks = f"COCONUT (≤ {_n(batas)} senyawa{', Lipinski ≤ 1' if lip else ''})"

            def ambil(lapor):
                baris = pustaka.cari_coconut(lipinski_maks=1 if lip else None, batas=batas, atom_min=6)
                return PA.siapkan_pustaka([(b["smiles"], b.get("id") or "") for b in baris if b.get("smiles")], lapor)
        else:
            from ..core import pustaka
            self._sumber_teks = "Obat disetujui (ChEMBL)"

            def ambil(lapor):
                return PA.siapkan_pustaka([(o["smiles"], o["nama"]) for o in pustaka.obat() if o.get("smiles")], lapor)
        self.b_baca.setEnabled(False)
        self.l_pustaka.setText("Membaca pustaka dan menghitung sidik jari…")
        self.pb.setVisible(True)
        self.pb.setRange(0, 0)
        kerja.jalankan(ambil, selesai=self._pustaka_siap, galat=self._pustaka_gagal, progres=self._progres_baca)

    def _progres_baca(self, i, n, _t):
        self.pb.setRange(0, max(1, n))
        self.pb.setValue(i)

    def _pustaka_siap(self, pus):
        self.b_baca.setEnabled(True)
        self.pb.setVisible(False)
        self._pustaka = pus
        r = pus.ringkasan
        if not len(pus):
            self.l_pustaka.setText("Tidak ada SMILES valid di pustaka ini.")
            _jenis(self.l_pustaka, "peringatan")
            self._perbarui_rencana()
            return
        bagian = [f"{_n(r['valid'])} senyawa unik siap"]
        if r.get("ganda"):
            bagian.append(f"{_n(r['ganda'])} duplikat dibuang")
        if r.get("tidak_valid"):
            bagian.append(f"{_n(r['tidak_valid'])} SMILES tidak valid")
        if r.get("garam"):
            bagian.append(f"{_n(r['garam'])} garam/pelarut dilepas")
        self.l_pustaka.setText("; ".join(bagian) + ".")
        _jenis(self.l_pustaka, "muted")
        kp = PA.Kampanye(len(pus))
        self.sp_awal.blockSignals(True)
        self.sp_batch.blockSignals(True)
        self.sp_awal.setValue(kp.ukuran_awal())
        self.sp_batch.setValue(kp.ukuran_batch())
        self.sp_awal.blockSignals(False)
        self.sp_batch.blockSignals(False)
        self._perbarui_rencana()

    def _pustaka_gagal(self, g):
        self.b_baca.setEnabled(True)
        self.pb.setVisible(False)
        self.l_pustaka.setText("Pustaka gagal dibaca: " + g.split("\n")[0])
        _jenis(self.l_pustaka, "peringatan")

    def _pengaturan(self):
        return {"model": self.cb_model.currentData(), "akuisisi": self.cb_akuisisi.currentData(),
                "awal": self.sp_awal.value(), "batch": self.sp_batch.value(), "putaran": self.sp_putaran.value()}

    def _detik_per_ligan(self, mesin):
        """Median detik per ligan dari job proyek dengan mesin yang sama (None bila belum ada riwayat)."""
        pr = self.jw.proyek
        d = sorted(l["detik"] for j in (pr.job if pr else []) if j.get("mesin") == mesin
                   for l in j.get("ligan", []) if l.get("status") == "selesai" and l.get("detik"))
        return d[len(d) // 2] if len(d) >= 5 else None

    def _perbarui_rencana(self, *_):
        pr, jw = self.jw.proyek, self.jw
        p = jw.param.parameter()
        mesin = p["mesin"]
        if mesin == "adgpu" and (p["perangkat"] != "gpu" or not (jw.env and jw.env.opencl_ok)):
            mesin = "vina"
        bagian = [M.MESIN.get(mesin, mesin)]
        if mesin == "unidock":
            bagian.append({"fast": "mode Cepat", "balance": "mode Seimbang", "detail": "mode Detail"}
                          .get(p.get("unidock_mode"), ""))
        elif mesin == "vina":
            bagian.append(f"exhaustiveness {p.get('exhaustiveness', 8)}")
        kotak = jw.box or {}
        if kotak.get("pusat"):
            bagian.append("kotak " + " × ".join(kit.f(x, 1) for x in kotak["ukuran"]) + " Å")
        rec = (pr.reseptor or {}).get("nama") if pr else None
        masalah = []
        if not pr or not pr.reseptor or not pr.p(pr.reseptor.get("pdbqt", "")).exists():
            masalah.append("reseptor belum disiapkan (langkah 1)")
        if not kotak.get("pusat"):
            masalah.append("area docking belum diatur (langkah 3)")
        if pr and (pr.reseptor or {}).get("kovalen", {}).get("aktif"):
            masalah.append("docking kovalen aktif (tidak didukung untuk penapisan bertahap)")
        teks = " · ".join(b for b in bagian if b) + (f" · reseptor {rec}" if rec else "")
        teks += ". Setelan diambil dari langkah 3–4 dan dikunci saat kampanye dimulai."
        if mesin == "vina":
            teks += " Untuk ribuan ligan, Uni-Dock (GPU, WSL) jauh lebih cepat."
        self.l_docking.setText(teks)
        if self._pustaka is not None and len(self._pustaka):
            kp = PA.Kampanye(len(self._pustaka), self._pengaturan())
            total = kp.total_rencana()
            r = (f"Didocking ± {_n(total)} dari {_n(len(self._pustaka))} senyawa "
                 f"({kit.f(100 * total / len(self._pustaka), 1)} %) dalam {self.sp_putaran.value() + 1} putaran.")
            dt = self._detik_per_ligan(mesin)
            if dt:
                jam = total * dt / 3600
                r += f" Perkiraan waktu docking ± {kit.f(jam, 1)} jam (median {kit.f(dt, 1)} s/ligan di proyek ini)."
            self.l_rencana.setText(r)
        else:
            self.l_rencana.setText("Ukuran batch bawaan: 1 % pustaka (minimal 50), seperti uji MolPAL.")
        self.b_mulai.setEnabled(self._pustaka is not None and len(self._pustaka) >= 100 and not masalah)
        self.b_mulai.setToolTip("Perlu: " + "; ".join(masalah) if masalah else
                                ("Baca pustaka (≥ 100 senyawa) lebih dulu" if self._pustaka is None
                                 or len(self._pustaka) < 100 else ""))

    def _mulai(self):
        if self._pustaka is None:
            return
        pg = self._pengaturan()
        nama = f"{self._sumber_teks or 'Pustaka'} · {_n(len(self._pustaka))}"
        cid = self.al.buat(nama, self._pustaka, pg, self._sumber_teks)
        self._pustaka = None
        self.l_pustaka.setText("Pustaka dipakai untuk kampanye baru. Baca lagi untuk kampanye berikutnya.")
        self.b_mulai.setEnabled(False)
        self._isi_daftar_kampanye(pilih=cid)
        self.al.jalankan(cid)
        self.jw._tampil_bawah(True)

    # ================================================================== kampanye
    def _cid(self):
        return self.cb_kampanye.currentData()

    def _isi_daftar_kampanye(self, pilih=None):
        pilih = pilih or self._cid()
        self.cb_kampanye.blockSignals(True)
        self.cb_kampanye.clear()
        for e in reversed(self.al.daftar()):
            self.cb_kampanye.addItem(f"{e['nama']} · {e['dibuat'][:16].replace('T', ' ')}", e["id"])
        i = self.cb_kampanye.findData(pilih)
        self.cb_kampanye.setCurrentIndex(i if i >= 0 else 0)
        self.cb_kampanye.blockSignals(False)
        self._tampilkan()

    def _berubah(self, cid):
        if self.cb_kampanye.findData(cid) < 0 or self.al.cari(cid) is None:
            self._isi_daftar_kampanye()
        elif cid == self._cid():
            self._tampilkan()

    def _kemajuan(self, cid, i, n, teks):
        if cid != self._cid():
            return
        self.pb.setVisible(True)
        self.pb.setRange(0, max(1, n))
        self.pb.setValue(i)

    def _galat(self, cid, pesan):
        if cid == self._cid():
            self._status(pesan, "peringatan")
        self._tampilkan()

    def _status(self, teks, jenis="muted"):
        self.l_status.setText(teks)
        _jenis(self.l_status, jenis if teks else "muted")

    def _tampilkan(self):
        cid = self._cid()
        ada = cid is not None and self.al.cari(cid) is not None
        self.l_kosong.setVisible(not ada)
        for x in (self.tab, self.cb_kampanye, self.b_lanjut, self.b_berhenti, self.b_henti, self.b_hapus):
            x.setEnabled(ada)
        self.lc_status.setVisible(ada)
        self.b_metode.setEnabled(ada)
        self.b_csv.setEnabled(ada)
        if not ada:
            self.lc_status.setText("")
            for t in (self.t_putaran, self.t_peringkat, self.t_prediksi):
                t.setRowCount(0)
            self.grafik.atur_pembuat(None)
            for k in (self.k_dock, self.k_terbaik, self.k_top, self.k_model):
                k.isi("–", "")
            return
        e, kp = self.al.cari(cid), self.al.kampanye(cid)
        st = self.al.status(cid)
        teks, nada = LABEL_STATUS.get(st, (st, "info"))
        if st == "berjalan" and self.al.akan_berhenti(cid):
            teks, nada = "Berhenti setelah putaran ini", "warn"
        self.lc_status.setText(teks)
        kit.atur_nada(self.lc_status, nada)
        tahap = self.al.tahap(cid)
        j = self.al.job_aktif(cid)
        if tahap:
            self.l_tahap.setText(tahap)
        elif j is not None:
            n_sel = sum(1 for l in j["ligan"] if l["status"] in ("selesai", "gagal", "dilewati"))
            self.l_tahap.setText(f"Docking putaran {j['al']['putaran']}: {_n(n_sel)}/{_n(len(j['ligan']))} ligan "
                                 f"({M.MESIN.get(j['mesin'], j['mesin'])}). Kemajuan rinci ada di panel Antrean.")
        else:
            self.l_tahap.setText("")
        self.pb.setVisible(bool(tahap))
        if not tahap:
            self.pb.setRange(0, 1)
        self.b_lanjut.setEnabled(st in ("baru", "dijeda") and not tahap)
        self.b_berhenti.setEnabled(st == "berjalan" and not self.al.akan_berhenti(cid))
        self.b_henti.setEnabled(j is not None)
        self.b_hapus.setEnabled(st != "berjalan")
        self.b_lanjut.setText("Mulai" if st == "baru" else "Lanjutkan")

        rp = kp.ringkasan_putaran(100)
        ok = [s for s in kp.skor.values() if s is not None]
        self.k_dock.isi(f"{_n(len(kp.skor))} / {_n(kp.total_rencana())}",
                        f"{kit.f(100 * len(kp.skor) / max(1, kp.n), 1)} % dari {_n(kp.n)} senyawa")
        self.k_terbaik.isi(kit.f(min(ok)) if ok else "–", "kkal/mol" if ok else "")
        akhir = next((r for r in reversed(rp) if r["rata_top"] is not None), None)
        self.k_top.isi(kit.f(akhir["rata_top"]) if akhir else "–",
                       f"kkal/mol, {akhir['k_top']} senyawa terbaik" if akhir else "")
        mutu = next((r["mutu"] for r in reversed(rp) if r["mutu"].get("rho") is not None), None)
        if mutu:
            nada = "ok" if mutu["rho"] >= 0.4 else ("warn" if mutu["rho"] >= 0.2 else "bad")
            self.k_model.isi(f"ρ {kit.f(mutu['rho'])}", f"Spearman, prediksi vs docking batch terakhir "
                                                       f"(n = {_n(mutu['n'])})", nada)
        else:
            self.k_model.isi("–", "Diukur setelah putaran pertama yang dipilih model")
        self._isi_putaran(rp)
        self._isi_peringkat(cid, e, kp)
        self._isi_prediksi(cid)
        self._gambar(rp)

    def _isi_putaran(self, rp):
        t = self.t_putaran
        t.setRowCount(len(rp))
        for r, x in enumerate(rp):
            mutu = x["mutu"]
            sel = [kit.sel(str(x["ke"]), x["ke"]), kit.sel(METODE.get(x["metode"], x["metode"])),
                   kit.sel(_n(x["n_batch"]), x["n_batch"]), kit.sel(_n(x["n_kumulatif"]), x["n_kumulatif"]),
                   kit.sel(_n(x["gagal"]), x["gagal"]), kit.sel_angka(x["terbaik"]), kit.sel_angka(x["rata_top"]),
                   kit.sel_angka(mutu.get("rho")) if mutu else kit.sel("–"),
                   kit.sel("Selesai" if x["selesai"] else "Didocking…")]
            for c, it in enumerate(sel):
                t.setItem(r, c, it)

    def _isi_peringkat(self, cid, e, kp):
        pus = self.al.pustaka(cid)
        prediksi = {}
        ke = {}
        for p in kp.putaran:
            for i in p["indeks"]:
                ke[i] = p["ke"]
            prediksi.update(p.get("prediksi") or {})
        baris = kp.peringkat(500)
        t = self.t_peringkat
        t.setSortingEnabled(False)
        t.setRowCount(len(baris))
        nama_lig = {l.get("al_idx"): l["nama"] for l in (self.jw.proyek.ligan if self.jw.proyek else [])
                    if l.get("al") == cid}
        for r, (i, s) in enumerate(baris):
            nama = pus.nama[i] if pus else nama_lig.get(i, f"#{i}")
            smi = pus.smiles[i] if pus else ""
            sel = [kit.sel(str(r + 1), r + 1), kit.sel(nama), kit.sel_angka(s), kit.sel_angka(prediksi.get(i)),
                   kit.sel(str(ke.get(i, "")), ke.get(i)), kit.sel(smi)]
            sel[1].setData(Qt.UserRole + 1, (e.get("pose") or {}).get(str(i)))
            for c, it in enumerate(sel):
                t.setItem(r, c, it)
        t.setSortingEnabled(True)
        if not pus and cid not in self._dimuat and not self.al.tahap(cid):
            self._dimuat.add(cid)        # nama & SMILES lengkap: muat salinan pustaka kampanye di latar, sekali
            self.al.dengan_pustaka(cid, lambda c: self._berubah(c))

    def _isi_prediksi(self, cid):
        daftar = self._prediksi.get(cid) or []
        pus = self.al.pustaka(cid)
        t = self.t_prediksi
        t.setSortingEnabled(False)
        t.setRowCount(len(daftar) if pus else 0)
        if not pus:
            return
        for r, (i, mu, sd) in enumerate(daftar):
            sel = [kit.sel(str(r + 1), r + 1), kit.sel(pus.nama[i]), kit.sel_angka(mu), kit.sel_angka(sd),
                   kit.sel(pus.smiles[i])]
            for c, it in enumerate(sel):
                t.setItem(r, c, it)
        t.setSortingEnabled(True)

    def _gambar(self, rp):
        xs = [r["n_kumulatif"] for r in rp if r["terbaik"] is not None]
        if len(xs) < 2:
            self.grafik.atur_pembuat(None)
            return
        terbaik = [r["terbaik"] for r in rp if r["terbaik"] is not None]
        top = [r["rata_top"] for r in rp if r["terbaik"] is not None]
        k = rp[-1]["k_top"]
        seri = [("ΔG terbaik", xs, terbaik), (f"Rata-rata {k} teratas", xs, top)]
        self.grafik.atur_pembuat(lambda l, t: grafik.garis(
            seri, label_x="Senyawa didocking (kumulatif)", label_y="ΔG (kkal/mol)",
            judul="Kemajuan penapisan per putaran", gelap=kit.mode() == "gelap", lebar=l, tinggi=t, x_nol=False))

    # ================================================================== aksi
    def _lanjutkan(self):
        cid = self._cid()
        if cid:
            self._status("")
            self.al.jalankan(cid)

    def _berhenti(self):
        if self._cid():
            self.al.berhenti_setelah_putaran(self._cid())

    def _hentikan(self):
        cid = self._cid()
        if cid and QMessageBox.question(self, "Hentikan putaran", "Batalkan docking putaran yang sedang berjalan? "
                                        "Skor ligan yang sudah selesai tetap disimpan; sisanya kembali menjadi "
                                        "kandidat dan bisa dipilih lagi saat dilanjutkan.") == QMessageBox.Yes:
            self.al.hentikan(cid)

    def _hapus(self):
        cid = self._cid()
        if not cid:
            return
        if QMessageBox.question(self, "Hapus kampanye", "Hapus catatan kampanye ini dan salinan pustakanya? Job dan "
                                "hasil docking yang sudah ada tetap tersimpan di proyek.") != QMessageBox.Yes:
            return
        if not self.al.hapus(cid):
            self._status("Kampanye yang sedang berjalan tidak bisa dihapus. Hentikan dulu.")
            return
        self._prediksi.pop(cid, None)
        self._isi_daftar_kampanye()

    def _hitung_prediksi(self):
        cid = self._cid()
        if not cid:
            return
        kp = self.al.kampanye(cid)
        self.b_prediksi.setEnabled(False)
        self._status("Melatih model dan memprediksi seluruh pustaka…")

        def hitung(_cid):
            pus = self.al.pustaka(_cid)
            kerja.jalankan(lambda lapor: kp.prediksi_kandidat(pus, 200, lapor),
                           selesai=lambda h: self._prediksi_siap(_cid, h), galat=self._prediksi_gagal,
                           progres=lambda i, n, t: self._kemajuan(_cid, i, n, t))
        self.al.dengan_pustaka(cid, hitung)

    def _prediksi_siap(self, cid, hasil):
        self._prediksi[cid] = hasil
        self.b_prediksi.setEnabled(True)
        self.pb.setVisible(False)
        self._status(f"{_n(len(hasil))} kandidat teratas dari model yang dilatih pada "
                              f"{_n(len(self.al.kampanye(cid).latih_data()[0]))} skor docking.")
        self._tampilkan()
        self.tab.setCurrentIndex(2)

    def _prediksi_gagal(self, g):
        self.b_prediksi.setEnabled(True)
        self.pb.setVisible(False)
        self._status(g.split("\n")[0])

    def _buka_pose(self, it):
        d = self.t_peringkat.item(it.row(), 1).data(Qt.UserRole + 1)
        if d:
            self.jw.buka_pose(d[0], d[1])
        else:
            self._status("Pose senyawa ini tidak ditemukan (job-nya mungkin sudah dihapus dari antrean).")

    def _salin_metode(self):
        cid = self._cid()
        if not cid:
            return
        e, kp = self.al.cari(cid), self.al.kampanye(cid)
        mesin = M.MESIN.get(e["docking"]["mesin"], e["docking"]["mesin"])
        teks = PA.teks_metode(kp, mesin, e.get("ringkasan_pustaka"), en=i18n.inggris())
        kit.salin(teks + "\n\n" + PA.SITASI)
        self._status("Paragraf metode dan sitasi MolPAL disalin.")

    def _ekspor_csv(self):
        cid = self._cid()
        if not cid:
            return
        f, _ = QFileDialog.getSaveFileName(self, "Ekspor hasil penapisan", f"{cid}.csv", "CSV (*.csv)")
        if f:
            self.al.dengan_pustaka(cid, lambda c: self._tulis_csv(c, f))   # nama & SMILES dari salinan pustaka

    def _tulis_csv(self, cid, f):
        kp, pus = self.al.kampanye(cid), self.al.pustaka(cid)
        prediksi, ke = {}, {}
        for p in kp.putaran:
            prediksi.update(p.get("prediksi") or {})
            for i in p["indeks"]:
                ke[i] = p["ke"]
        with open(f, "w", encoding="utf-8", newline="") as fo:
            w = csv.writer(fo)
            w.writerow(["indeks", "nama", "smiles", "putaran", "dG_kkal_mol", "prediksi_sebelum_docking", "status"])
            for i, s in sorted(kp.skor.items(), key=lambda x: (x[1] is None, x[1] if x[1] is not None else 0)):
                w.writerow([i, pus.nama[i] if pus else "", pus.smiles[i] if pus else "", ke.get(i, ""),
                            "" if s is None else f"{s:.3f}", prediksi.get(i, ""), "gagal" if s is None else "ok"])
        self._status(f"{_n(len(kp.skor))} baris diekspor ke {f}")
