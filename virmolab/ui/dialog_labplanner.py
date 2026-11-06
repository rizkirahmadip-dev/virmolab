"""Dialog Kalkulator Pengujian Laboratorium Basah (Wet-Lab Planner).

Menjembatani penambatan molekuler ke protokol uji in vitro di laboratorium basah:
- Perkiraan Ki & IC50 dari skor energi docking.
- Seri pengenceran bertingkat (serial dilution) 1:3, 1:2, semi-log.
- Toleransi pelarut DMSO (≤ 0.5%) dan volume pemipetan mikro.
- Denah visual pelat mikro (96-well / 384-well) dengan triplo/duplo dan kontrol.
- Ekspor protokol kerja siap cetak dan lembar kerja CSV/Excel.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QSpinBox, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
                               QTextEdit, QVBoxLayout, QWidget)
from PySide6.QtSvgWidgets import QSvgWidget

from ..core import ekspor as eksmod
from ..core import hipotesis
from ..core import labplanner
from ..core.laporan import id_angka
from . import kit


class DialogLabPlanner(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Rencana uji lab basah")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1200, 750)

        self.ligan_data = []  # [(lid, nama, dg)]
        self.protokol_aktif = {}
        self.denah_aktif = {}
        self.teks_protokol_aktif = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(kit.judul(
            "Rencana uji laboratorium basah",
            "Susun denah pelat, seri pengenceran, dan protokol uji untuk ligan terpilih dari hasil docking."))

        # Splitter: Parameter & Kontrol (Kiri) vs Visualisasi Denah & Protokol (Kanan)
        sp = QSplitter(Qt.Horizontal)

        # Panel Kiri: Input Parameter
        kiri = QWidget()
        klay = QVBoxLayout(kiri)
        klay.setContentsMargins(0, 0, 0, 0)
        klay.setSpacing(8)

        # 1. Pemilihan Ligan
        gb_ligan = QGroupBox("1. Pemilihan Ligan Docking")
        glay1 = QVBoxLayout(gb_ligan)
        self.cb_ligan = QComboBox()
        self.cb_ligan.currentIndexChanged.connect(self._pilih_ligan_berubah)
        glay1.addWidget(self.cb_ligan)

        self.l_afinitas = QLabel("ΔG: - kcal/mol | Ki: - | IC50: -")
        self.l_afinitas.setObjectName("muted")
        glay1.addWidget(self.l_afinitas)
        klay.addWidget(gb_ligan)

        # 2. Parameter Pengenceran & Pelat
        gb_param = QGroupBox("2. Parameter larutan && pelat")
        glay2 = QVBoxLayout(gb_param)

        hl_stok = QHBoxLayout()
        hl_stok.addWidget(QLabel("Konsentrasi stok (mM):"))
        self.sp_stok = QDoubleSpinBox()
        self.sp_stok.setToolTip("Konsentrasi larutan induk senyawa. 10 mM dalam DMSO adalah praktik umum; menaikkannya mengurangi volume DMSO yang masuk ke sumur.")
        self.sp_stok.setRange(0.1, 1000.0)
        self.sp_stok.setValue(10.0)
        self.sp_stok.setSuffix(" mM")
        self.sp_stok.valueChanged.connect(self._hitung_ulang)
        hl_stok.addWidget(self.sp_stok)
        glay2.addLayout(hl_stok)

        hl_vol = QHBoxLayout()
        hl_vol.addWidget(QLabel("Volume akhir sumur (μL):"))
        self.sp_vol = QDoubleSpinBox()
        self.sp_vol.setToolTip("Volume akhir tiap sumur. 100 µL lazim untuk pelat 96-sumur; pelat 384-sumur memakai volume jauh lebih kecil.")
        self.sp_vol.setRange(10.0, 1000.0)
        self.sp_vol.setValue(100.0)
        self.sp_vol.setSuffix(" μL")
        self.sp_vol.valueChanged.connect(self._hitung_ulang)
        hl_vol.addWidget(self.sp_vol)
        glay2.addLayout(hl_vol)

        hl_dmso = QHBoxLayout()
        hl_dmso.addWidget(QLabel("Batas DMSO maks (%):"))
        self.sp_dmso = QDoubleSpinBox()
        self.sp_dmso.setToolTip("Batas DMSO yang masih ditoleransi sel. Di atas 0,5 % banyak lini sel mulai terpengaruh, sehingga efek yang terukur bisa berasal dari pelarutnya, bukan senyawanya.")
        self.sp_dmso.setRange(0.05, 5.0)
        self.sp_dmso.setValue(0.5)
        self.sp_dmso.setSingleStep(0.1)
        self.sp_dmso.setSuffix(" %")
        self.sp_dmso.valueChanged.connect(self._hitung_ulang)
        hl_dmso.addWidget(self.sp_dmso)
        glay2.addLayout(hl_dmso)

        hl_pelat = QHBoxLayout()
        hl_pelat.addWidget(QLabel("Format pelat mikro:"))
        self.cb_pelat = QComboBox()
        self.cb_pelat.setToolTip("Format pelat menentukan berapa banyak senyawa dan konsentrasi yang muat dalam satu kali uji.")
        self.cb_pelat.addItem("96-well (8 × 12)", "96")
        self.cb_pelat.addItem("384-well (16 × 24)", "384")
        self.cb_pelat.addItem("48-well (6 × 8)", "48")
        self.cb_pelat.addItem("24-well (4 × 6)", "24")
        self.cb_pelat.currentIndexChanged.connect(self._hitung_ulang)
        hl_pelat.addWidget(self.cb_pelat)
        glay2.addLayout(hl_pelat)

        hl_rep = QHBoxLayout()
        hl_rep.addWidget(QLabel("Replikasi uji:"))
        self.cb_rep = QComboBox()
        self.cb_rep.setToolTip("Jumlah sumur per konsentrasi. Triplo memungkinkan perhitungan simpangan baku dan uji statistik; duplo hanya memperlihatkan selisih tanpa ukuran sebarannya.")
        self.cb_rep.addItem("Triplo (3 sumur / konsentrasi)", 3)
        self.cb_rep.addItem("Duplo (2 sumur / konsentrasi)", 2)
        self.cb_rep.addItem("Singlet (1 sumur)", 1)
        self.cb_rep.currentIndexChanged.connect(self._hitung_ulang)
        hl_rep.addWidget(self.cb_rep)
        glay2.addLayout(hl_rep)

        klay.addWidget(gb_param)

        # 3. Seri Pengenceran
        gb_seri = QGroupBox("3. Skema Rentang Dosis")
        glay3 = QVBoxLayout(gb_seri)

        hl_cmax = QHBoxLayout()
        hl_cmax.addWidget(QLabel("Konsentrasi tertinggi (μM):"))
        self.sp_cmax = QDoubleSpinBox()
        self.sp_cmax.setToolTip("Konsentrasi tertinggi dalam seri pengenceran. Pilih agar perkiraan IC50 jatuh di tengah seri, bukan di ujungnya — IC50 di tepi tidak dapat dipasang kurvanya dengan andal.")
        self.sp_cmax.setRange(0.001, 10000.0)
        self.sp_cmax.setValue(100.0)
        self.sp_cmax.setSuffix(" μM")
        self.sp_cmax.valueChanged.connect(self._hitung_ulang)
        hl_cmax.addWidget(self.sp_cmax)
        glay3.addLayout(hl_cmax)

        hl_pola = QHBoxLayout()
        hl_pola.addWidget(QLabel("Pola seri pengenceran:"))
        self.cb_pola = QComboBox()
        self.cb_pola.setToolTip("Faktor pengenceran antar-titik. Faktor 3 mencakup rentang lebar dengan sedikit titik; faktor 2 memberi kurva lebih rapat tetapi rentangnya lebih sempit.")
        self.cb_pola.addItem("Faktor 3 (1:3 serial)", (3.0, "faktor"))
        self.cb_pola.addItem("Faktor 2 (1:2 serial)", (2.0, "faktor"))
        self.cb_pola.addItem("Semi-logaritmik (1000, 300, 100…)", (3.16, "semi_log"))
        self.cb_pola.addItem("Faktor 10 (1:10 serial)", (10.0, "faktor"))
        self.cb_pola.currentIndexChanged.connect(self._hitung_ulang)
        hl_pola.addWidget(self.cb_pola)
        glay3.addLayout(hl_pola)

        hl_titik = QHBoxLayout()
        hl_titik.addWidget(QLabel("Jumlah titik konsentrasi:"))
        self.sp_titik = QSpinBox()
        self.sp_titik.setToolTip("Jumlah titik konsentrasi. Delapan titik sudah cukup untuk memasang kurva sigmoid empat parameter; kurang dari enam membuat pemasangan kurva tidak stabil.")
        self.sp_titik.setRange(4, 16)
        self.sp_titik.setValue(8)
        self.sp_titik.valueChanged.connect(self._hitung_ulang)
        hl_titik.addWidget(self.sp_titik)
        glay3.addLayout(hl_titik)

        klay.addWidget(gb_seri)
        klay.addStretch(1)

        sp.addWidget(kiri)

        # Panel Kanan: Tab Denah & Protokol
        kanan = QWidget()
        rlay = QVBoxLayout(kanan)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(6)

        self.tab = QTabWidget()

        # Tab 1: Denah Pelat Visual
        t1 = QWidget()
        t1lay = QVBoxLayout(t1)
        t1lay.setContentsMargins(6, 6, 6, 6)
        self.tabel_pelat = QTableWidget()
        self.tabel_pelat.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabel_pelat.setSelectionMode(QTableWidget.SingleSelection)
        self.tabel_pelat.itemClicked.connect(self._klik_sumur)
        t1lay.addWidget(self.tabel_pelat, 1)

        self.l_detail_sumur = QLabel("Klik salah satu sumur untuk melihat rincian isi.")
        self.l_detail_sumur.setObjectName("muted")
        t1lay.addWidget(self.l_detail_sumur)

        # Legenda warna
        leg = QHBoxLayout()
        leg.addWidget(QLabel("<b>Legenda:</b>"))
        for t_label, warna_hex in [
            ("Sampel uji", "#bcd4f5"),
            ("Kendali pelarut (DMSO)", "#c4e7f7"),
            ("Kontrol positif", "#f6c6c6"),
            ("Blanko", "#d6dbe3"),
        ]:
            lbl = QLabel(f" {t_label} ")
            lbl.setStyleSheet(f"background: {warna_hex}; color: #1b2430; border-radius: 3px; padding: 2px 8px;")
            leg.addWidget(lbl)
        leg.addStretch(1)
        t1lay.addLayout(leg)
        self.tab.addTab(t1, "Denah Pelat Mikro (Plate Map)")

        # Tab 2: Panduan Pemipetan
        t2 = QWidget()
        t2lay = QVBoxLayout(t2)
        t2lay.setContentsMargins(6, 6, 6, 6)
        self.tabel_langkah = QTableWidget()
        self.tabel_langkah.setColumnCount(6)
        self.tabel_langkah.setHorizontalHeaderLabels([
            "Titik", "Kons. Sumur (μM)", "Kons. Kerja (μM)", "Vol. Buffer (μL)", "Vol. Senyawa (μL)", "DMSO Akhir (%)"
        ])
        th = self.tabel_langkah.horizontalHeader()
        th.setSectionResizeMode(QHeaderView.Stretch)
        t2lay.addWidget(self.tabel_langkah)
        self.tab.addTab(t2, "Tabel Pemipetan Seri")

        # Tab 3: Draf Protokol Teks
        t3 = QWidget()
        t3lay = QVBoxLayout(t3)
        t3lay.setContentsMargins(6, 6, 6, 6)
        self.txt_protokol = QTextEdit()
        self.txt_protokol.setReadOnly(True)
        self.txt_protokol.setFont(QFont("Consolas, Courier New, monospace", 10))
        t3lay.addWidget(self.txt_protokol)
        self.tab.addTab(t3, "Draf Protokol Siap Cetak")

        # Tab 4: Pelacak Hipotesis -> Uji Lab (F12)
        t4 = self._buat_tab_hipotesis()
        self.tab.addTab(t4, "Hipotesis")

        rlay.addWidget(self.tab, 1)
        sp.addWidget(kanan)
        sp.setStretchFactor(0, 3)
        sp.setStretchFactor(1, 5)
        lay.addWidget(sp, 1)

        # Bilah Bawah
        bawah = QHBoxLayout()
        b_salin = QPushButton("Salin Protokol")
        b_salin.clicked.connect(self._salin_protokol)
        b_simpan_txt = QPushButton("Simpan Protokol Teks…")
        b_simpan_txt.clicked.connect(self._simpan_protokol_teks)
        b_ekspor_csv = QPushButton("Simpan Denah CSV…")
        b_ekspor_csv.clicked.connect(self._ekspor_denah_csv)
        bawah.addWidget(b_salin)
        bawah.addWidget(b_simpan_txt)
        bawah.addWidget(b_ekspor_csv)
        bawah.addStretch(1)

        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.accept)
        bawah.addWidget(b_tutup)
        lay.addLayout(bawah)

        self._muat_ligan_proyek()

    def _muat_ligan_proyek(self):
        pr = self.jw.proyek
        if not pr:
            return
        dg_per_lid = {}
        for b in eksmod.baris_hasil(pr):
            lid = b["lid"]
            dg_per_lid[lid] = min(dg_per_lid.get(lid, 0.0), b["energi"])

        self.ligan_data = []
        self.cb_ligan.blockSignals(True)
        self.cb_ligan.clear()

        for l in pr.ligan:
            lid = l["id"]
            nama = l["nama"]
            dg = dg_per_lid.get(lid)
            self.ligan_data.append((lid, nama, dg))
            teks = f"{nama} (ΔG: {dg:.2f} kcal/mol)" if dg is not None else nama
            self.cb_ligan.addItem(teks, lid)

        self.cb_ligan.blockSignals(False)
        if self.ligan_data:
            self._pilih_ligan_berubah()
        self._muat_data_hipotesis()

    def _pilih_ligan_berubah(self):
        idx = self.cb_ligan.currentIndex()
        if idx < 0 or idx >= len(self.ligan_data):
            return
        lid, nama, dg = self.ligan_data[idx]
        ki_info = labplanner.prediksi_ki_ic50(dg)
        self.l_afinitas.setText(
            f"ΔG {kit.f(dg, 2, 'kcal/mol')} · perkiraan Ki {id_angka(ki_info['ki_teks'])} · "
            f"perkiraan IC₅₀ {id_angka(ki_info['ic50_teks'])}"
            if dg is not None else "ΔG belum ada (belum di-docking)"
        )

        # Sarankan Cmax berdasarkan IC50 perkiraan
        if ki_info["ic50_uM"] is not None:
            c_saran = max(1.0, min(1000.0, ki_info["ic50_uM"] * 50.0))
            # Bulatkan ke angka cantik (10, 30, 100, 300, dsb.)
            if c_saran <= 10.0:
                saran_bulat = 10.0
            elif c_saran <= 30.0:
                saran_bulat = 30.0
            elif c_saran <= 100.0:
                saran_bulat = 100.0
            elif c_saran <= 300.0:
                saran_bulat = 300.0
            else:
                saran_bulat = 1000.0
            self.sp_cmax.setValue(saran_bulat)

        self._hitung_ulang()

    def _hitung_ulang(self):
        idx = self.cb_ligan.currentIndex()
        if idx < 0 or idx >= len(self.ligan_data):
            return
        lid, nama, dg = self.ligan_data[idx]
        ki_info = labplanner.prediksi_ki_ic50(dg)

        cmax = self.sp_cmax.value()
        faktor, mode = self.cb_pola.currentData()
        n_titik = self.sp_titik.value()
        seri = labplanner.hitung_seri_konsentrasi(cmax, faktor_pengenceran=faktor, jumlah_titik=n_titik, mode=mode)

        stok_mM = self.sp_stok.value()
        vol_sumur = self.sp_vol.value()
        dmso_maks = self.sp_dmso.value()
        prot = labplanner.buat_protokol_pipet(stok_mM, seri, volume_sumur_uL=vol_sumur, dmso_maks_persen=dmso_maks)
        self.protokol_aktif = prot

        format_pelat = self.cb_pelat.currentData()
        replikasi = self.cb_rep.currentData()
        denah = labplanner.rancang_denah_pelat(
            format_pelat=format_pelat,
            daftar_sampel=[{"nama": nama, "konsentrasi": seri}],
            replikasi=replikasi
        )
        self.denah_aktif = denah

        self.teks_protokol_aktif = labplanner.buat_teks_protokol(nama, dg or 0.0, ki_info, prot)
        self.txt_protokol.setText(self.teks_protokol_aktif)

        self._gambar_denah(denah)
        self._tampilkan_langkah(prot)

    def _gambar_denah(self, denah):
        n_baris, n_kolom = denah["n_baris"], denah["n_kolom"]
        label_baris, label_kolom = denah["label_baris"], denah["label_kolom"]
        grid = denah["grid"]

        self.tabel_pelat.setRowCount(n_baris)
        self.tabel_pelat.setColumnCount(n_kolom)
        self.tabel_pelat.setVerticalHeaderLabels(label_baris)
        self.tabel_pelat.setHorizontalHeaderLabels(label_kolom)

        vh = self.tabel_pelat.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Stretch)
        hh = self.tabel_pelat.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)

        for r_idx, r in enumerate(label_baris):
            for c_idx, c in enumerate(label_kolom):
                pos = f"{r}{c}"
                data_sumur = grid.get(pos, {})
                jenis = data_sumur.get("jenis", "kosong")
                lbl = data_sumur.get("label", "")
                kons = data_sumur.get("kons_uM")

                if jenis == "sampel":
                    teks_sel = f"{kit.f(kons, 3 if kons < 0.1 else 2)} μM"
                elif jenis == "blanko":
                    teks_sel = "BLK"
                elif jenis == "pelarut":
                    teks_sel = "VC"
                elif jenis == "kontrol_pos":
                    teks_sel = "PC"
                else:
                    teks_sel = ""

                it = QTableWidgetItem(teks_sel)
                it.setTextAlignment(Qt.AlignCenter)
                w_hex = data_sumur.get("warna", "#f2f4f7")
                it.setBackground(QColor(w_hex))
                it.setForeground(QColor("#1b2430"))   # latar sumur selalu pastel terang
                it.setData(Qt.UserRole, data_sumur)
                if lbl:
                    it.setToolTip(lbl)
                self.tabel_pelat.setItem(r_idx, c_idx, it)

    def _klik_sumur(self, it):
        data = it.data(Qt.UserRole)
        if not data:
            return
        pos = f"{data.get('baris')}{data.get('kolom')}"
        jenis = data.get("jenis", "kosong")
        if jenis == "sampel":
            self.l_detail_sumur.setText(
                f"Sumur {pos} · {data.get('sampel')} · {kit.f(data.get('kons_uM'), 3)} μM · "
                f"Volume {self.sp_vol.value():.0f} μL | DMSO ≤ {self.sp_dmso.value():.1f}%"
            )
        elif jenis == "blanko":
            self.l_detail_sumur.setText(f"Sumur [{pos}] : Blanko (Buffer saja tanpa enzim/senyawa)")
        elif jenis == "pelarut":
            self.l_detail_sumur.setText(f"Sumur [{pos}] : Kendali Pelarut (Buffer + DMSO {self.sp_dmso.value():.1f}% + Enzim)")
        elif jenis == "kontrol_pos":
            self.l_detail_sumur.setText(f"Sumur [{pos}] : Kontrol Positif (Inhibitor referensi)")
        else:
            self.l_detail_sumur.setText(f"Sumur [{pos}] : Kosong")

    def _tampilkan_langkah(self, prot):
        langkah = prot.get("langkah", [])
        self.tabel_langkah.setRowCount(len(langkah))
        for r, lk in enumerate(langkah):
            self.tabel_langkah.setItem(r, 0, QTableWidgetItem(f"#{lk['titik']}"))
            self.tabel_langkah.setItem(r, 1, kit.sel_angka(lk["kons_sumur_uM"], 3))
            self.tabel_langkah.setItem(r, 2, kit.sel_angka(lk["kons_kerja_uM"], 3))
            self.tabel_langkah.setItem(r, 3, QTableWidgetItem(f"{lk['vol_buffer_sumur_uL']:.1f}"))
            self.tabel_langkah.setItem(r, 4, QTableWidgetItem(f"{lk['vol_ke_sumur_uL']:.1f}"))
            self.tabel_langkah.setItem(r, 5, QTableWidgetItem(f"{lk['dmso_akhir_persen']:.1f}%"))

    def _salin_protokol(self):
        if not self.teks_protokol_aktif:
            return
        QGuiApplication.clipboard().setText(self.teks_protokol_aktif)
        self.jw.status.showMessage("Draf protokol laboratorium berhasil disalin ke papan klip.", 3000)

    def _simpan_protokol_teks(self):
        if not self.teks_protokol_aktif:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Protokol Pengujian", "protokol_in_vitro.txt", "Berkas Teks (*.txt)")
        if path:
            from pathlib import Path
            Path(path).write_text(self.teks_protokol_aktif, encoding="utf-8")
            self.jw.status.showMessage(f"Protokol disimpan ke {path}", 3000)

    def _ekspor_denah_csv(self):
        if not self.denah_aktif:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Denah Pelat", "denah_pelat.csv", "Berkas CSV (*.csv)")
        if not path:
            return
        import csv
        denah = self.denah_aktif
        label_baris, label_kolom = denah["label_baris"], denah["label_kolom"]
        grid = denah["grid"]

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([""] + label_kolom)
            for r in label_baris:
                baris_csv = [r]
                for c in label_kolom:
                    pos = f"{r}{c}"
                    d = grid.get(pos, {})
                    jenis = d.get("jenis")
                    if jenis == "sampel":
                        baris_csv.append(f"{d.get('sampel')}:{d.get('kons_uM'):g}uM")
                    elif jenis in ("blanko", "pelarut", "kontrol_pos"):
                        baris_csv.append(d.get("label", ""))
                    else:
                        baris_csv.append("")
                w.writerow(baris_csv)
        self.jw.status.showMessage(f"Denah pelat mikro disimpan ke {path}", 3000)

    # ------------------------------------------------------------------ Tab Hipotesis (F12)
    def _buat_tab_hipotesis(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # Bilah kontrol atas
        top = QHBoxLayout()
        top.addWidget(QLabel("Prediksi pembanding:"))
        self.cb_jenis_pred = QComboBox()
        self.cb_jenis_pred.setToolTip("Nilai prediksi yang akan dibandingkan dengan hasil uji lab. Pastikan satuannya sepadan sebelum menarik kesimpulan tentang korelasi.")
        self.cb_jenis_pred.addItem("ΔG Docking (kcal/mol)", "dg")
        self.cb_jenis_pred.addItem("MM/GBSA (kcal/mol)", "mmgbsa")
        self.cb_jenis_pred.addItem("pIC50 estimasi dari ΔG", "pic50_pred")
        self.cb_jenis_pred.setItemData(2, "Transformasi monoton ΔG (Ki → IC50); korelasi peringkatnya sama dengan ΔG.",
                                       Qt.ToolTipRole)
        self.cb_jenis_pred.currentIndexChanged.connect(self._muat_data_hipotesis)
        top.addWidget(self.cb_jenis_pred)

        top.addSpacing(8)
        b_impor = QPushButton("Impor CSV plate reader…")
        b_impor.clicked.connect(self._impor_csv_plate_reader)
        top.addWidget(b_impor)

        b_tambah = QPushButton("+ Tambah entri")
        b_tambah.clicked.connect(self._tambah_baris_hipotesis)
        top.addWidget(b_tambah)

        b_simpan = QPushButton("Simpan entri ke proyek")
        b_simpan.clicked.connect(self._simpan_hipotesis_ke_proyek)
        top.addWidget(b_simpan)

        top.addStretch(1)

        b_qsar = QPushButton("Latih ulang QSAR dengan data baru")
        b_qsar.setToolTip("Gunakan data aktivitas eksperimen yang terukur untuk melatih model QSAR (P8)")
        b_qsar.clicked.connect(self._latih_ulang_qsar)
        top.addWidget(b_qsar)

        lay.addLayout(top)

        # Splitter horizontal: Kiri (Tabel) vs Kanan (Statistik & Plot)
        sp_h = QSplitter(Qt.Horizontal)

        # Kiri: Tabel Ligan x Hipotesis
        kiri_w = QWidget()
        klay = QVBoxLayout(kiri_w)
        klay.setContentsMargins(0, 0, 0, 0)
        klay.setSpacing(4)

        self.tabel_hipotesis = QTableWidget()
        self.tabel_hipotesis.setColumnCount(9)
        self.tabel_hipotesis.setHorizontalHeaderLabels([
            "ID Ligan", "Nama", "Prediksi", "Nilai Terukur", "Satuan", "pIC50 Terukur",
            "Status Hipotesis", "Assay", "Catatan"
        ])
        th = self.tabel_hipotesis.horizontalHeader()
        th.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(8, QHeaderView.Stretch)
        th.setMinimumSectionSize(60)
        # ID ligan hampir selalu sama dengan nama; disimpan di kolom tersembunyi untuk kunci entri
        self.tabel_hipotesis.setColumnHidden(0, True)
        self.tabel_hipotesis.verticalHeader().setVisible(False)
        self.tabel_hipotesis.cellChanged.connect(self._sel_hipotesis_berubah)
        klay.addWidget(self.tabel_hipotesis, 1)

        sp_h.addWidget(kiri_w)

        # Kanan: Evaluasi Statistik & Plot SVG
        kanan_w = QWidget()
        rlay = QVBoxLayout(kanan_w)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(6)

        # Kartu Evaluasi Korelasi
        gb_eval = QGroupBox("Evaluasi korelasi prediksi vs terukur")
        glay = QVBoxLayout(gb_eval)
        glay.setContentsMargins(8, 8, 8, 8)
        glay.setSpacing(4)

        self.l_n_sampel = QLabel("Sampel terpasang: - | Dilewati: -")
        self.l_spearman = QLabel("Spearman ρ: - | 95% CI: -")
        self.l_kendall = QLabel("Kendall τ: - | 95% CI: -")
        self.l_arah = QLabel("")
        self.l_arah.setWordWrap(True)
        self.l_arah.setObjectName("muted")
        self.l_peringatan_sampel = QLabel("")
        self.l_peringatan_sampel.setWordWrap(True)
        self.l_peringatan_sampel.setVisible(False)

        glay.addWidget(self.l_n_sampel)
        glay.addWidget(self.l_spearman)
        glay.addWidget(self.l_kendall)
        glay.addWidget(self.l_arah)
        glay.addWidget(self.l_peringatan_sampel)
        rlay.addWidget(gb_eval)

        # Plot SVG
        self.svg_plot = QSvgWidget()
        self.svg_plot.setMinimumSize(340, 300)
        rlay.addWidget(self.svg_plot, 1)

        # Tombol aksi grafik
        gb_aksi = QHBoxLayout()
        b_salin_svg = QPushButton("Salin SVG")
        b_salin_svg.clicked.connect(self._salin_grafik_svg)
        b_simpan_svg = QPushButton("Simpan SVG…")
        b_simpan_svg.clicked.connect(self._simpan_grafik_svg)
        gb_aksi.addWidget(b_salin_svg)
        gb_aksi.addWidget(b_simpan_svg)
        gb_aksi.addStretch(1)
        rlay.addLayout(gb_aksi)

        sp_h.addWidget(kanan_w)
        # Tabel butuh ruang untuk 7 kolom isian; grafik tetap terbaca di ~40 %
        sp_h.setStretchFactor(0, 3)
        sp_h.setStretchFactor(1, 2)
        sp_h.setSizes([600, 400])

        lay.addWidget(sp_h, 1)
        return w

    def _muat_data_hipotesis(self):
        pr = self.jw.proyek
        if not pr:
            return
        jenis_pred = self.cb_jenis_pred.currentData() or "dg"
        baris_tabel, stats_hasil = hipotesis.kumpulkan_data_tabel(pr, jenis_pred)

        self.tabel_hipotesis.blockSignals(True)
        self.tabel_hipotesis.setRowCount(len(baris_tabel))

        for r, b in enumerate(baris_tabel):
            # 0: ID Ligan
            it_id = QTableWidgetItem(str(b["ligan_id"]))
            it_id.setFlags(it_id.flags() & ~Qt.ItemIsEditable)
            self.tabel_hipotesis.setItem(r, 0, it_id)

            # 1: Nama Ligan
            it_nama = QTableWidgetItem(str(b["nama"]))
            it_nama.setFlags(it_nama.flags() & ~Qt.ItemIsEditable)
            it_nama.setToolTip(f"ID ligan: {b['ligan_id']}")
            self.tabel_hipotesis.setItem(r, 1, it_nama)

            # 2: Prediksi
            pred_v = b.get("prediksi_tampil")
            pred_teks = kit.f(pred_v, 2)
            it_pred = QTableWidgetItem(pred_teks)
            it_pred.setFlags(it_pred.flags() & ~Qt.ItemIsEditable)
            it_pred.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tabel_hipotesis.setItem(r, 2, it_pred)

            # 3: Nilai Terukur
            val_t = b.get("nilai_terukur")
            it_val = QTableWidgetItem(id_angka(f"{val_t:g}") if val_t is not None else "")
            it_val.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tabel_hipotesis.setItem(r, 3, it_val)

            # 4: Satuan
            it_sat = QTableWidgetItem(str(b.get("satuan_terukur") or "uM"))
            it_sat.setTextAlignment(Qt.AlignCenter)
            self.tabel_hipotesis.setItem(r, 4, it_sat)

            # 5: pIC50 Terukur
            p_val = b.get("pic50_terukur")
            p_teks = kit.f(p_val, 2)
            it_p = QTableWidgetItem(p_teks)
            it_p.setFlags(it_p.flags() & ~Qt.ItemIsEditable)
            it_p.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tabel_hipotesis.setItem(r, 5, it_p)

            # 6: Status Hipotesis (Combobox)
            cb_status = QComboBox()
            for st in hipotesis.STATUS_HIPOTESIS:
                cb_status.addItem(st.capitalize(), st)
            st_aktif = str(b.get("status_hipotesis") or "diajukan").lower()
            idx_st = hipotesis.STATUS_HIPOTESIS.index(st_aktif) if st_aktif in hipotesis.STATUS_HIPOTESIS else 0
            cb_status.setCurrentIndex(idx_st)
            cb_status.currentIndexChanged.connect(lambda _i, row=r: self._status_berubah(row))
            self.tabel_hipotesis.setCellWidget(r, 6, cb_status)

            # 7: Assay
            self.tabel_hipotesis.setItem(r, 7, QTableWidgetItem(str(b.get("assay") or "Inhibisi")))

            # 8: Catatan
            self.tabel_hipotesis.setItem(r, 8, QTableWidgetItem(str(b.get("catatan") or "")))

        self.tabel_hipotesis.blockSignals(False)

        # Perbarui Kartu Statistik
        n_pasang = stats_hasil.get("n", 0)
        n_skip = stats_hasil.get("n_dilewati", 0)
        self.l_n_sampel.setText(f"Sampel terpasang: {n_pasang} | Dilewati / tidak lengkap: {n_skip}")

        sp_val = stats_hasil.get("spearman")
        p_sp = stats_hasil.get("p_spearman")
        ci_sp = stats_hasil.get("ci_spearman")
        if sp_val is not None:
            ci_sp_teks = f"[{kit.f(ci_sp[0], 2)}; {kit.f(ci_sp[1], 2)}]" if ci_sp else "–"
            self.l_spearman.setText(f"Spearman ρ = {kit.f(sp_val, 3)} (p {_teks_p(p_sp)}; CI 95 % {ci_sp_teks})")
        else:
            self.l_spearman.setText("Spearman ρ = –")

        kd_val = stats_hasil.get("kendall")
        p_kd = stats_hasil.get("p_kendall")
        ci_kd = stats_hasil.get("ci_kendall")
        if kd_val is not None:
            ci_kd_teks = f"[{kit.f(ci_kd[0], 2)}; {kit.f(ci_kd[1], 2)}]" if ci_kd else "–"
            self.l_kendall.setText(f"Kendall τ = {kit.f(kd_val, 3)} (p {_teks_p(p_kd)}; CI 95 % {ci_kd_teks})")
        else:
            self.l_kendall.setText("Kendall τ = –")

        if jenis_pred in ("dg", "mmgbsa"):
            self.l_arah.setText("Energi dibalik tanda (−ΔG) sehingga ρ dan τ positif berarti peringkat prediksi "
                                "sejalan dengan pIC50 terukur.")
        else:
            self.l_arah.setText("ρ dan τ positif berarti peringkat prediksi sejalan dengan pIC50 terukur.")

        per = stats_hasil.get("peringatan")
        if n_pasang == 0:
            # Belum ada data lab: keadaan awal, bukan galat
            per = "Belum ada pIC50 terukur yang berpasangan dengan prediksi. Isi kolom Nilai terukur atau impor CSV."
            self.l_peringatan_sampel.setStyleSheet(f"color: {kit.warna('mut').name()};")
        else:
            self.l_peringatan_sampel.setStyleSheet(f"color: {kit.warna('warn').name()};")
        self.l_peringatan_sampel.setText(per or "")
        self.l_peringatan_sampel.setVisible(bool(per))

        # Pilihan prediksi tanpa satu nilai pun di proyek dinonaktifkan
        model = self.cb_jenis_pred.model()
        for i in range(self.cb_jenis_pred.count()):
            kunci = self.cb_jenis_pred.itemData(i)
            ada = kunci == jenis_pred or hipotesis.ada_prediksi(pr, kunci)
            model.item(i).setEnabled(ada)

        # Render Grafik SVG
        gelap = kit.mode() == "gelap"
        svg_teks = hipotesis.buat_grafik_prediksi_vs_terukur(baris_tabel, jenis_pred, gelap=gelap)
        self.svg_plot_teks = svg_teks
        self.svg_plot.load(bytearray(svg_teks, "utf-8"))

    def _status_berubah(self, _row):
        self._simpan_hipotesis_ke_proyek()

    def _sel_hipotesis_berubah(self, row, col):
        if col in (3, 4):  # Nilai atau Satuan diubah
            it_val = self.tabel_hipotesis.item(row, 3)
            it_sat = self.tabel_hipotesis.item(row, 4)
            val_s = _ke_float_teks(it_val.text()) if it_val else ""
            sat_s = it_sat.text().strip() if it_sat else "uM"
            try:
                val_f = float(val_s) if val_s else None
            except ValueError:
                val_f = None
            pic_f = hipotesis.ke_pic50(val_f, sat_s) if val_f is not None else None

            self.tabel_hipotesis.blockSignals(True)
            it_p = QTableWidgetItem(kit.f(pic_f, 2))
            it_p.setFlags(it_p.flags() & ~Qt.ItemIsEditable)
            it_p.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tabel_hipotesis.setItem(row, 5, it_p)
            self.tabel_hipotesis.blockSignals(False)

            self._simpan_hipotesis_ke_proyek()

    def _tambah_baris_hipotesis(self):
        r = self.tabel_hipotesis.rowCount()
        self.tabel_hipotesis.blockSignals(True)
        self.tabel_hipotesis.insertRow(r)
        self.tabel_hipotesis.setItem(r, 0, QTableWidgetItem(""))
        it_nama = QTableWidgetItem(f"Senyawa {r + 1}")
        it_nama.setToolTip("Ketik nama ligan persis seperti di proyek agar terpasang dengan prediksinya")
        self.tabel_hipotesis.setItem(r, 1, it_nama)
        self.tabel_hipotesis.setItem(r, 2, QTableWidgetItem("–"))
        self.tabel_hipotesis.setItem(r, 3, QTableWidgetItem(""))
        self.tabel_hipotesis.setItem(r, 4, QTableWidgetItem("uM"))
        self.tabel_hipotesis.setItem(r, 5, QTableWidgetItem("–"))

        cb_status = QComboBox()
        for st in hipotesis.STATUS_HIPOTESIS:
            cb_status.addItem(st.capitalize(), st)
        cb_status.setCurrentIndex(0)
        cb_status.currentIndexChanged.connect(lambda _i, row=r: self._status_berubah(row))
        self.tabel_hipotesis.setCellWidget(r, 6, cb_status)

        self.tabel_hipotesis.setItem(r, 7, QTableWidgetItem("Inhibisi Enzim"))
        self.tabel_hipotesis.setItem(r, 8, QTableWidgetItem(""))
        self.tabel_hipotesis.blockSignals(False)
        self.tabel_hipotesis.scrollToBottom()
        self.tabel_hipotesis.editItem(it_nama)

    def _simpan_hipotesis_ke_proyek(self):
        pr = self.jw.proyek
        if not pr:
            return
        daftar_entri = []
        for r in range(self.tabel_hipotesis.rowCount()):
            it_id = self.tabel_hipotesis.item(r, 0)
            it_val = self.tabel_hipotesis.item(r, 3)
            it_sat = self.tabel_hipotesis.item(r, 4)
            it_pic = self.tabel_hipotesis.item(r, 5)
            w_st = self.tabel_hipotesis.cellWidget(r, 6)
            it_asy = self.tabel_hipotesis.item(r, 7)
            it_cat = self.tabel_hipotesis.item(r, 8)

            it_nama = self.tabel_hipotesis.item(r, 1)
            lid = (it_id.text().strip() if it_id else "") or (it_nama.text().strip() if it_nama else "")
            if not lid:
                continue
            val_s = _ke_float_teks(it_val.text()) if it_val else ""
            sat_s = it_sat.text().strip() if it_sat else "uM"
            pic_s = _ke_float_teks(it_pic.text()) if it_pic else ""
            st_s = w_st.currentData() if isinstance(w_st, QComboBox) else "diajukan"
            asy_s = it_asy.text().strip() if it_asy else "Inhibisi"
            cat_s = it_cat.text().strip() if it_cat else ""

            try:
                val_f = float(val_s) if val_s else None
            except ValueError:
                val_f = None
            try:
                pic_f = float(pic_s) if pic_s else None
            except ValueError:
                pic_f = None

            daftar_entri.append({
                "id": f"EXP{r+1:03d}",
                "ligan_id": lid,
                "assay": asy_s,
                "nilai": val_f,
                "satuan": sat_s,
                "pIC50": pic_f,
                "catatan": cat_s,
                "status_hipotesis": st_s,
            })

        hipotesis.simpan_entri_proyek(pr, daftar_entri)
        self.jw.minta_simpan()

    def _impor_csv_plate_reader(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih berkas CSV hasil uji / plate reader", "",
            "Berkas CSV (*.csv *.tsv *.txt)"
        )
        if not path:
            return
        try:
            entri_baru = hipotesis.impor_csv_hasil(path, self.denah_aktif)
        except Exception as e:
            kit.pesan_peringatan(self, f"Gagal mengimpor CSV: {e}")
            return

        if not entri_baru:
            self.jw.status.showMessage("Tidak ada data valid yang ditemukan pada berkas CSV.", 4000)
            return

        pr = self.jw.proyek
        if pr:
            lama = hipotesis.ambil_entri_proyek(pr)
            peta_lama = {e["ligan_id"]: e for e in lama}
            for eb in entri_baru:
                peta_lama[eb["ligan_id"]] = eb
            hipotesis.simpan_entri_proyek(pr, list(peta_lama.values()))
            self.jw.minta_simpan()
            self._muat_data_hipotesis()
            self.jw.status.showMessage(f"Berhasil mengimpor {len(entri_baru)} entri hasil uji.", 3000)

    def _latih_ulang_qsar(self):
        self._simpan_hipotesis_ke_proyek()
        pr = self.jw.proyek
        if not pr:
            return
        eks = getattr(pr, "eksperimen", None) or {}
        entri = eks.get("entri") or []
        ada_pic = [e for e in entri if e.get("pIC50") is not None]
        if len(ada_pic) < 3:
            kit.pesan_peringatan(
                self, "Data eksperimen belum mencukupi untuk melatih model QSAR (minimal 3 entri ber-pIC50 terukur)."
            )
            return
        if hasattr(self.jw, "buka_qsar"):
            d = self.jw.buka_qsar()
            if d is not None and hasattr(d, "_muat_eksperimen_lab"):
                d._muat_eksperimen_lab()
            self.jw.status.showMessage("Modul QSAR dibuka dengan data aktivitas uji lab proyek.", 3000)

    def _salin_grafik_svg(self):
        teks = getattr(self, "svg_plot_teks", "")
        if teks:
            QGuiApplication.clipboard().setText(teks)
            self.jw.status.showMessage("Grafik SVG berhasil disalin ke papan klip.", 3000)

    def _simpan_grafik_svg(self):
        teks = getattr(self, "svg_plot_teks", "")
        if not teks:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Grafik Hipotesis", "prediksi_vs_terukur.svg", "Berkas SVG (*.svg)")
        if path:
            from pathlib import Path
            Path(path).write_text(teks, encoding="utf-8")
            self.jw.status.showMessage(f"Grafik SVG disimpan ke {path}", 3000)


def _ke_float_teks(teks: str) -> str:
    """Teks angka gaya Indonesia ('1,5', '−6,30', '–') menjadi teks yang bisa di-float ('' bila kosong)."""
    t = (teks or "").strip().replace("−", "-").replace(",", ".")
    return "" if t in ("", "-", "–") else t


def _teks_p(p) -> str:
    if p is None:
        return "= –"
    return "< 0,0001" if p < 1e-4 else f"= {kit.f(p, 4)}"
