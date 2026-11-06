"""Dialog Batch Virtual Screening Dashboard.

Meringkas hasil penapisan virtual skala besar (>100 ligan):
  - Heatmap ligan x sifat/skor
  - Multi-variabel scatter plot (ΔG vs SAScore dengan gradien QED/MPO)
  - Histogram distribusi afinitas dengan garis rata-rata & median
  - Filter multi-kriteria interaktif
  - Peringkat komposit & auto-flag "Top Hits"
  - Ekspor CSV dan sinkronisasi ke 3D Viewer
"""
import csv
import io
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QSplitter, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from ..core import grafik, penapisan
from .panel_interaksi import KanvasSvg
from ..core.laporan import id_angka
from . import kit, theme


def _sel(t, angka=None, align_right=False):
    it = QTableWidgetItem(str(t) if t is not None else "-")
    if angka is not None:
        it.setData(Qt.UserRole, angka)
    if align_right or angka is not None:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


class DialogPenapisan(QDialog):
    liganDipilih = Signal(str)

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.proyek = jw.proyek
        self.setWindowTitle("Dasbor penapisan virtual")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1260, 780)

        self.semua_data = []
        self.data_terfilter = []
        self.data_top = []

        lay_utama = QVBoxLayout(self)
        lay_utama.setContentsMargins(12, 12, 12, 12)
        lay_utama.setSpacing(8)
        lay_utama.addWidget(kit.judul(
            "Dasbor penapisan virtual",
            "Ringkasan skor, efisiensi ligan, dan sebaran hasil per job untuk memilih kandidat terbaik dari "
            "penapisan besar."))

        # Bilah atas: Pemilihan Job & Ringkasan Cepat
        bar_atas = QHBoxLayout()
        bar_atas.addWidget(QLabel("Job Docking:"))
        self.cb_job = QComboBox()
        self.cb_job.addItem("Semua Job", None)
        if self.proyek and hasattr(self.proyek, "job"):
            for j in self.proyek.job:
                jid = j.get("id", "job")
                mesin = j.get("mesin", "vina")
                n_lig = len(j.get("ligan", []))
                self.cb_job.addItem(f"{jid} ({mesin}, {n_lig} ligan)", jid)
        self.cb_job.currentIndexChanged.connect(self._muat_ulang_data)
        bar_atas.addWidget(self.cb_job)

        bar_atas.addSpacing(16)
        self.l_ringkas = QLabel("Memuat data...")
        self.l_ringkas.setObjectName("subjudul")
        bar_atas.addWidget(self.l_ringkas, 1)

        b_refresh = QPushButton("Segarkan Data")
        b_refresh.clicked.connect(self._muat_ulang_data)
        bar_atas.addWidget(b_refresh)
        lay_utama.addLayout(bar_atas)

        # Splitter Utama: Panel Filter (kiri) vs Tab Visualisasi & Tabel (kanan)
        sp_utama = QSplitter(Qt.Horizontal)

        # === PANEL FILTER (Kiri) ===
        w_filter = QWidget()
        lay_fil = QVBoxLayout(w_filter)
        lay_fil.setContentsMargins(0, 0, 6, 0)
        lay_fil.setSpacing(8)

        gb_filter = QGroupBox("Kriteria Penapisan (Filtering)")
        gb_lay = QVBoxLayout(gb_filter)
        gb_lay.setSpacing(6)

        # Filter Afinitas ΔG
        gb_lay.addWidget(QLabel("ΔG Maksimum (kcal/mol):"))
        self.sp_dg = QDoubleSpinBox()
        self.sp_dg.setRange(-25.0, 0.0)
        self.sp_dg.setValue(0.0)
        self.sp_dg.setSingleStep(0.5)
        self.sp_dg.setSpecialValueText("Tanpa Batas")
        self.sp_dg.setToolTip("Hanya ligan dengan ΔG lebih negatif dari nilai ini yang lolos. Patokan kasar: −7 kcal/mol sudah terhitung mengikat, −9 kuat. Ambang terlalu ketat membuang kandidat yang skornya kurang tepat, bukan yang ikatannya buruk.")
        self.sp_dg.valueChanged.connect(self._terapkan_filter)
        gb_lay.addWidget(self.sp_dg)

        # Filter Drug-Likeness QED
        gb_lay.addWidget(QLabel("QED Minimum (0.0 - 1.0):"))
        self.sp_qed = QDoubleSpinBox()
        self.sp_qed.setRange(0.0, 1.0)
        self.sp_qed.setValue(0.0)
        self.sp_qed.setSingleStep(0.05)
        self.sp_qed.setSpecialValueText("Tanpa Batas")
        self.sp_qed.setToolTip("QED merangkum kemiripan-obat dalam satu angka 0–1. Di atas 0,5 umumnya dianggap mirip-obat; bahan alam sering jatuh di bawahnya tanpa berarti buruk, jadi longgarkan untuk pustaka alam.")
        self.sp_qed.valueChanged.connect(self._terapkan_filter)
        gb_lay.addWidget(self.sp_qed)

        # Filter SAScore (Kemudahan Sintesis)
        gb_lay.addWidget(QLabel("SAScore Maksimum (1 mudah - 10 sulit):"))
        self.sp_sa = QDoubleSpinBox()
        self.sp_sa.setRange(1.0, 10.0)
        self.sp_sa.setValue(10.0)
        self.sp_sa.setSingleStep(0.5)
        self.sp_sa.setSpecialValueText("Tanpa Batas (10)")
        self.sp_sa.setToolTip("SAScore memperkirakan kesulitan sintesis: 1 mudah, 10 sangat sulit. Di bawah 4 biasanya dapat disintesis rutin; di atas 6 perlu jalur khusus. Tidak ada kaitannya dengan afinitas.")
        self.sp_sa.valueChanged.connect(self._terapkan_filter)
        gb_lay.addWidget(self.sp_sa)

        # Filter MPO Skor
        gb_lay.addWidget(QLabel("Oral MPO Minimum (0 - 100):"))
        self.sp_mpo = QDoubleSpinBox()
        self.sp_mpo.setRange(0.0, 100.0)
        self.sp_mpo.setValue(0.0)
        self.sp_mpo.setSingleStep(5.0)
        self.sp_mpo.setSpecialValueText("Tanpa Batas (0)")
        self.sp_mpo.setToolTip("Oral MPO menggabungkan beberapa sifat fisikokimia menjadi skor 0–100 untuk peluang diserap lewat mulut. Di atas 60 dianggap baik. Kosongkan bila target Anda bukan obat oral.")
        self.sp_mpo.valueChanged.connect(self._terapkan_filter)
        gb_lay.addWidget(self.sp_mpo)

        # Checkboxes Aturan
        gb_lay.addSpacing(4)
        self.chk_lipinski = QCheckBox("Hanya lolos Aturan Lipinski")
        self.chk_lipinski.toggled.connect(self._terapkan_filter)
        gb_lay.addWidget(self.chk_lipinski)

        self.chk_veber = QCheckBox("Hanya lolos Aturan Veber")
        self.chk_veber.toggled.connect(self._terapkan_filter)
        gb_lay.addWidget(self.chk_veber)

        self.chk_pains = QCheckBox("Bebas peringatan PAINS")
        self.chk_pains.toggled.connect(self._terapkan_filter)
        gb_lay.addWidget(self.chk_pains)

        self.chk_brenk = QCheckBox("Bebas gugus reaktif (Brenk)")
        self.chk_brenk.toggled.connect(self._terapkan_filter)
        gb_lay.addWidget(self.chk_brenk)

        self.chk_gi = QCheckBox("Absorpsi Gastrointestinal Tinggi")
        self.chk_gi.toggled.connect(self._terapkan_filter)
        gb_lay.addWidget(self.chk_gi)

        # Pengaturan Top Hits
        gb_lay.addSpacing(8)
        gb_top = QGroupBox("Pengaturan Auto-Flag Top Hits")
        top_lay = QVBoxLayout(gb_top)
        top_lay.addWidget(QLabel("Jumlah Top Hits (N):"))
        self.sp_top_n = QSpinBox()
        self.sp_top_n.setToolTip("Berapa banyak ligan teratas yang ditandai sebagai hit setelah semua saringan diterapkan. Angka ini tidak menyaring apa pun, hanya menentukan berapa yang disorot dan diekspor.")
        self.sp_top_n.setRange(1, 200)
        self.sp_top_n.setValue(20)
        self.sp_top_n.valueChanged.connect(self._terapkan_filter)
        top_lay.addWidget(self.sp_top_n)
        gb_lay.addWidget(gb_top)

        b_reset = QPushButton("↺ Reset Filter")
        b_reset.clicked.connect(self._reset_filter)
        gb_lay.addWidget(b_reset)

        gb_lay.addStretch(1)
        lay_fil.addWidget(gb_filter)
        w_filter.setMaximumWidth(280)
        sp_utama.addWidget(w_filter)

        # === PANEL KANAN (Visualisasi & Tabel) ===
        w_kanan = QWidget()
        lay_kanan = QVBoxLayout(w_kanan)
        lay_kanan.setContentsMargins(0, 0, 0, 0)
        lay_kanan.setSpacing(6)

        self.tabs = QTabWidget()

        # Tab 1: Grafik Visualisasi
        tab_grafik = QWidget()
        lay_tg = QVBoxLayout(tab_grafik)
        lay_tg.setContentsMargins(4, 4, 4, 4)
        sp_grafik = QSplitter(Qt.Vertical)

        # Atas: Scatter ΔG vs SAScore (warna = QED/MPO) dan Histogram ΔG berdampingan
        w_graf_atas = QWidget()
        lay_ga = QHBoxLayout(w_graf_atas)
        lay_ga.setContentsMargins(0, 0, 0, 0)
        self.kanvas_scatter = KanvasSvg()
        self.kanvas_hist = KanvasSvg()
        lay_ga.addWidget(self.kanvas_scatter, 3)
        lay_ga.addWidget(self.kanvas_hist, 2)
        sp_grafik.addWidget(w_graf_atas)

        # Bawah: Heatmap Ligan x Variabel
        w_graf_bawah = QWidget()
        lay_gb = QVBoxLayout(w_graf_bawah)
        lay_gb.setContentsMargins(0, 0, 0, 0)
        lay_gb.addWidget(QLabel("Peta Panas Multi-Parameter (50 Ligan Teratas):"))
        self.kanvas_heat = KanvasSvg()
        lay_gb.addWidget(self.kanvas_heat)
        sp_grafik.addWidget(w_graf_bawah)

        lay_tg.addWidget(sp_grafik)
        self.tabs.addTab(tab_grafik, "Visualisasi Distribusi && Peta Panas")

        # Tab 2: Tabel Kandidat
        tab_tabel = QWidget()
        lay_tt = QVBoxLayout(tab_tabel)
        lay_tt.setContentsMargins(4, 4, 4, 4)

        self.tabel_hits = QTableWidget()
        self.tabel_hits.setColumnCount(14)
        self.tabel_hits.setHorizontalHeaderLabels([
            "Flag", "Ligan", "Skor Komposit", "ΔG (kcal/mol)", "MPO", "LE", "QED",
            "SAScore", "MW", "Interaksi", "Lipinski", "PAINS", "Brenk", "GI"
        ])
        self.tabel_hits.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabel_hits.setSelectionMode(QTableWidget.SingleSelection)
        self.tabel_hits.setSortingEnabled(True)
        self.tabel_hits.setAlternatingRowColors(True)
        h = self.tabel_hits.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(14):
            if col != 1:
                h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.tabel_hits.itemSelectionChanged.connect(self._pilih_baris_tabel)
        lay_tt.addWidget(self.tabel_hits)

        # Tombol aksi tabel
        bar_aksi = QHBoxLayout()
        b_salin = QPushButton("Salin Data Top Hits")
        b_salin.clicked.connect(self._salin_top)
        bar_aksi.addWidget(b_salin)

        b_csv = QPushButton("Ekspor CSV…")
        b_csv.clicked.connect(self._ekspor_csv)
        bar_aksi.addWidget(b_csv)

        bar_aksi.addStretch(1)
        b_sorot = QPushButton("Lihat Pose di Viewer 3D")
        b_sorot.setObjectName("primary")
        b_sorot.clicked.connect(self._kirim_ke_viewer)
        bar_aksi.addWidget(b_sorot)

        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.close)
        bar_aksi.addWidget(b_tutup)
        lay_tt.addLayout(bar_aksi)

        self.tabs.addTab(tab_tabel, "Tabel Peringkat && Top Hits")
        lay_kanan.addWidget(self.tabs)

        sp_utama.addWidget(w_kanan)
        sp_utama.setStretchFactor(1, 3)
        lay_utama.addWidget(sp_utama)

        # Muat data pertama kali
        self._muat_ulang_data()

    def _muat_ulang_data(self):
        with kit.sibuk(self.l_ringkas, "Menyiapkan data penapisan…"):
            jid = self.cb_job.currentData()
            jobs = None
            if jid and self.proyek and hasattr(self.proyek, "job"):
                jobs = [j for j in self.proyek.job if j.get("id") == jid]

            self.semua_data = penapisan.gabung_data(self.proyek, jobs=jobs)
            self._terapkan_filter()

    def _terapkan_filter(self):
        with kit.sibuk(self.l_ringkas, "Menerapkan saringan…"):
            if not self.semua_data:
                self.l_ringkas.setText("Tidak ada data ligan/hasil docking.")
                self.kanvas_scatter.set_svg(grafik.scatter_multi_svg([], "energi", "sascore", judul="Scatter ΔG vs SAScore"))
                self.kanvas_hist.set_svg(grafik.histogram_distribusi_svg([], "energi", judul="Distribusi ΔG"))
                self.kanvas_heat.set_svg(grafik.heatmap_svg([], [], [], judul="Peta Panas"))
                self.tabel_hits.setRowCount(0)
                return

            kriteria = {}
            if self.sp_dg.value() < 0.0:
                kriteria["energi_maks"] = self.sp_dg.value()
            if self.sp_qed.value() > 0.0:
                kriteria["qed_min"] = self.sp_qed.value()
            if self.sp_sa.value() < 10.0:
                kriteria["sascore_maks"] = self.sp_sa.value()
            if self.sp_mpo.value() > 0.0:
                kriteria["mpo_min"] = self.sp_mpo.value()

            if self.chk_lipinski.isChecked():
                kriteria["lipinski_lolos"] = True
            if self.chk_veber.isChecked():
                kriteria["veber_lolos"] = True
            if self.chk_pains.isChecked():
                kriteria["pains_bebas"] = True
            if self.chk_brenk.isChecked():
                kriteria["brenk_bebas"] = True
            if self.chk_gi.isChecked():
                kriteria["gi_harus"] = True

            terfilter = penapisan.filter_data(self.semua_data, kriteria)
            top_n = self.sp_top_n.value()
            self.data_terfilter = penapisan.flag_top_hits(terfilter, n=top_n)

            # Hitung statistik
            stat = penapisan.statistik_ringkas(self.semua_data, self.data_terfilter)
            n_tot = stat["total_ligan"]
            n_lolos = stat["jumlah_lolos"]
            pct = stat["persentase_lolos"]
            avg_dg = stat["rata_rata_energi"]
            avg_str = f" · rerata ΔG {id_angka(f'{avg_dg:.2f}')} kcal/mol" if avg_dg is not None else ""
            self.l_ringkas.setText(f"Lolos saringan: {n_lolos} dari {n_tot} ligan ({id_angka(str(pct))}%){avg_str}")

            self._perbarui_grafik()
            self._perbarui_tabel()

    def _reset_filter(self):
        self.sp_dg.setValue(0.0)
        self.sp_qed.setValue(0.0)
        self.sp_sa.setValue(10.0)
        self.sp_mpo.setValue(0.0)
        self.chk_lipinski.setChecked(False)
        self.chk_veber.setChecked(False)
        self.chk_pains.setChecked(False)
        self.chk_brenk.setChecked(False)
        self.chk_gi.setChecked(False)
        self.sp_top_n.setValue(20)

    def _perbarui_grafik(self):
        gelap = theme.is_dark() if hasattr(theme, "is_dark") else False
        data = self.data_terfilter

        # 1. Scatter: X=energi (ΔG), Y=sascore, Warna=mpo_skor
        svg_sc = grafik.scatter_multi_svg(
            data,
            x_kunci="energi",
            y_kunci="sascore",
            warna_kunci="mpo_skor",
            x_label="Afinitas ΔG (kcal/mol)",
            y_label="SAScore (Kemudahan Sintesis)",
            judul="Peta Sebar Afinitas vs Sintesis (Warna: MPO)",
            gelap=gelap,
            sorot_flag="flag_top"
        )
        self.kanvas_scatter.set_svg(svg_sc)

        # 2. Histogram ΔG
        svg_hi = grafik.histogram_distribusi_svg(
            data,
            kunci="energi",
            bins=15,
            x_label="ΔG (kcal/mol)",
            judul="Distribusi Afinitas Docking ΔG",
            gelap=gelap
        )
        self.kanvas_hist.set_svg(svg_hi)

        # 3. Heatmap
        mat, rows, cols = penapisan.matriks_heatmap(data, maks_baris=35)
        svg_hm = grafik.heatmap_svg(
            mat,
            label_baris=rows,
            label_kolom=cols,
            judul="Peta Panas Multi-Parameter Top Ligan",
            gelap=gelap,
            palet="biru_merah"
        )
        self.kanvas_heat.set_svg(svg_hm)

    def _perbarui_tabel(self):
        self.tabel_hits.setSortingEnabled(False)
        self.tabel_hits.setRowCount(len(self.data_terfilter))

        for row, d in enumerate(self.data_terfilter):
            is_top = d.get("flag_top", False)
            flag_teks = "★ Top" if is_top else ""
            it_flag = _sel(flag_teks)
            if is_top:
                it_flag.setForeground(QColor("#d97706"))
                it_flag.setTextAlignment(Qt.AlignCenter)
            self.tabel_hits.setItem(row, 0, it_flag)

            self.tabel_hits.setItem(row, 1, _sel(d.get("nama")))
            self.tabel_hits.setItem(row, 2, _sel(id_angka(f"{d.get('skor_komposit', 0):.1f}"), d.get("skor_komposit")))
            self.tabel_hits.setItem(row, 3, _sel(id_angka(f"{d['energi']:.2f}") if d.get("energi") is not None else "–", d.get("energi")))
            self.tabel_hits.setItem(row, 4, _sel(id_angka(f"{d.get('mpo_skor', 0):.1f}"), d.get("mpo_skor")))
            self.tabel_hits.setItem(row, 5, _sel(id_angka(f"{d['le']:.2f}") if d.get("le") is not None else "–", d.get("le")))
            self.tabel_hits.setItem(row, 6, _sel(id_angka(f"{d['qed']:.2f}") if d.get("qed") is not None else "–", d.get("qed")))
            self.tabel_hits.setItem(row, 7, _sel(id_angka(f"{d['sascore']:.1f}") if d.get("sascore") is not None else "–", d.get("sascore")))
            self.tabel_hits.setItem(row, 8, _sel(id_angka(f"{d['mw']:.1f}") if d.get("mw") is not None else "–", d.get("mw")))
            self.tabel_hits.setItem(row, 9, _sel(d.get("interaksi_total", 0), d.get("interaksi_total")))
            self.tabel_hits.setItem(row, 10, _sel("Ya" if d.get("lipinski_lolos") else "Tidak"))
            self.tabel_hits.setItem(row, 11, _sel("Ada" if d.get("pains") else "Bebas"))
            self.tabel_hits.setItem(row, 12, _sel("Ada" if d.get("brenk") else "Bebas"))
            self.tabel_hits.setItem(row, 13, _sel("Tinggi" if d.get("gi") else "Rendah"))

        self.tabel_hits.setSortingEnabled(True)

    def _pilih_baris_tabel(self):
        pass

    def _kirim_ke_viewer(self):
        sel = self.tabel_hits.selectedItems()
        if not sel:
            QMessageBox.information(self, "Pilih Ligan", "Silakan pilih salah satu ligan pada tabel.")
            return
        row = self.tabel_hits.currentRow()
        if 0 <= row < len(self.data_terfilter):
            d = self.data_terfilter[row]
            nama = d.get("nama")
            if nama:
                self.liganDipilih.emit(nama)

    def _salin_top(self):
        top_list = [d for d in self.data_terfilter if d.get("flag_top")]
        if not top_list:
            top_list = self.data_terfilter[:self.sp_top_n.value()]

        out = io.StringIO()
        writer = csv.writer(out, delimiter="\t")
        writer.writerow(["Nama", "Skor Komposit", "ΔG", "MPO", "LE", "QED", "SAScore", "MW", "SMILES"])
        for d in top_list:
            writer.writerow([
                d.get("nama"), d.get("skor_komposit"), d.get("energi"),
                d.get("mpo_skor"), d.get("le"), d.get("qed"),
                d.get("sascore"), d.get("mw"), d.get("smiles")
            ])
        QGuiApplication.clipboard().setText(out.getvalue())
        QMessageBox.information(self, "Disalin", f"{len(top_list)} data ligan teratas berhasil disalin ke clipboard.")

    def _ekspor_csv(self):
        if not self.data_terfilter:
            QMessageBox.information(self, "Data Kosong", "Tidak ada data ligan terfilter untuk diekspor.")
            return

        jalur, _ = QFileDialog.getSaveFileName(self, "Simpan CSV Penapisan", "hasil_penapisan_virtual.csv", "CSV (*.csv)")
        if not jalur:
            return

        kolom = [
            "flag_top", "nama", "skor_komposit", "energi", "ki", "le", "mmgbsa",
            "mpo_skor", "mpo_kategori", "qed", "sascore", "mw", "wlogp", "tpsa",
            "hbond", "hidrofobik", "pi", "interaksi_total", "lipinski_lolos",
            "veber_lolos", "pains", "brenk", "gi", "bbb", "smiles"
        ]

        try:
            with open(jalur, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=kolom, extrasaction="ignore")
                writer.writeheader()
                for d in self.data_terfilter:
                    writer.writerow(d)
            QMessageBox.information(self, "Sukses", f"Berhasil mengekspor {len(self.data_terfilter)} baris ke {jalur}")
        except Exception as e:
            QMessageBox.critical(self, "Galat Ekspor", f"Gagal mengekspor berkas: {e}")
