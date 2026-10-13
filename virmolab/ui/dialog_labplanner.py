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

from ..core import ekspor as eksmod
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
        self.sp_stok.setRange(0.1, 1000.0)
        self.sp_stok.setValue(10.0)
        self.sp_stok.setSuffix(" mM")
        self.sp_stok.valueChanged.connect(self._hitung_ulang)
        hl_stok.addWidget(self.sp_stok)
        glay2.addLayout(hl_stok)

        hl_vol = QHBoxLayout()
        hl_vol.addWidget(QLabel("Volume akhir sumur (μL):"))
        self.sp_vol = QDoubleSpinBox()
        self.sp_vol.setRange(10.0, 1000.0)
        self.sp_vol.setValue(100.0)
        self.sp_vol.setSuffix(" μL")
        self.sp_vol.valueChanged.connect(self._hitung_ulang)
        hl_vol.addWidget(self.sp_vol)
        glay2.addLayout(hl_vol)

        hl_dmso = QHBoxLayout()
        hl_dmso.addWidget(QLabel("Batas DMSO maks (%):"))
        self.sp_dmso = QDoubleSpinBox()
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
        self.sp_cmax.setRange(0.001, 10000.0)
        self.sp_cmax.setValue(100.0)
        self.sp_cmax.setSuffix(" μM")
        self.sp_cmax.valueChanged.connect(self._hitung_ulang)
        hl_cmax.addWidget(self.sp_cmax)
        glay3.addLayout(hl_cmax)

        hl_pola = QHBoxLayout()
        hl_pola.addWidget(QLabel("Pola seri pengenceran:"))
        self.cb_pola = QComboBox()
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
