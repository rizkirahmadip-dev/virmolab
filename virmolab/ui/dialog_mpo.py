"""Dialog Multi-Parameter Optimization (MPO) & Radar Chart.

Menghitung skor kelayakan terpadu (desirability score 0-100) dari gabungan sifat fisikokimia,
kemudahan sintesis (SAScore), drug-likeness (QED), dan afinitas docking (ΔG).
Dilengkapi visualisasi grafik laba-laba / radar SVG interaktif untuk setiap ligan.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import catat, ekspor as eksmod
from ..core import grafik, mpo, sifat
from ..core.laporan import id_angka
from . import kit, theme
from .panel_interaksi import KanvasSvg


def _sel(t, angka=None, align_right=False):
    it = QTableWidgetItem(str(t) if t is not None else "-")
    if angka is not None:
        it.setData(Qt.UserRole, angka)
    if align_right or angka is not None:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


class DialogMPO(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Optimasi multi-parameter (MPO)")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1180, 720)
        self.data_mpo = []  # [(lid, nama, sifat_dict, dg, hasil_mpo)]
        self.svg_aktif = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Bilah atas: pemilihan preset dan keterangan
        atas = QHBoxLayout()
        atas.addWidget(QLabel("Preset MPO:"))
        self.cb_preset = QComboBox()
        self.cb_preset.addItem("Oral Drug-like MPO (Lipinski, SAScore, QED, ΔG)", "oral")
        self.cb_preset.addItem("CNS-MPO parsial (4 dari 6 suku Wager et al. 2010)", "cns")
        self.cb_preset.setToolTip("CNS-MPO Pfizer memakai MW, ClogP, ClogD, TPSA, HBD, dan pKa. VirmoLab "
                                  "menghitung empat suku pertama (ClogP didekati WLOGP); ClogD dan pKa tidak "
                                  "tersedia, jadi skornya tidak sebanding dengan nilai CNS-MPO 0–6 asli.")
        self.cb_preset.currentIndexChanged.connect(self._hitung_ulang)
        atas.addWidget(self.cb_preset)
        atas.addStretch(1)

        b_hitung = QPushButton("Hitung Ulang")
        b_hitung.clicked.connect(self._hitung_ulang)
        atas.addWidget(b_hitung)
        lay.addLayout(atas)

        # Splitter: tabel ligan (kiri) vs radar chart & rincian (kanan)
        sp = QSplitter(Qt.Horizontal)

        # Bagian kiri: tabel ligan
        kiri = QWidget()
        klay = QVBoxLayout(kiri)
        klay.setContentsMargins(0, 0, 0, 0)
        klay.setSpacing(6)

        self.tabel_ligan = QTableWidget()
        self.tabel_ligan.setColumnCount(9)
        self.tabel_ligan.setHorizontalHeaderLabels([
            "Ligan", "MPO", "Kategori", "ΔG", "SA Score", "QED", "MW", "WLOGP", "TPSA"
        ])
        self.tabel_ligan.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabel_ligan.setSelectionMode(QTableWidget.SingleSelection)
        self.tabel_ligan.setSortingEnabled(True)
        self.tabel_ligan.setAlternatingRowColors(True)
        self.tabel_ligan.verticalHeader().setVisible(False)
        h = self.tabel_ligan.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Interactive)
        h.setMinimumSectionSize(64)
        self.tabel_ligan.setColumnWidth(0, 180)
        for c in range(1, 9):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.tabel_ligan.itemSelectionChanged.connect(self._pilih_ligan)
        klay.addWidget(self.tabel_ligan, 1)

        self.l_info_ligan = QLabel("")
        self.l_info_ligan.setObjectName("muted")
        klay.addWidget(self.l_info_ligan)
        sp.addWidget(kiri)

        # Bagian kanan: Radar Chart dan rincian komponen
        kanan = QWidget()
        rlay = QVBoxLayout(kanan)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(6)

        self.kanvas = KanvasSvg()
        rlay.addWidget(self.kanvas, 3)

        # Tabel komponen
        gb_komp = QGroupBox("Rincian Parameter Ligan Terpilih")
        glay = QVBoxLayout(gb_komp)
        glay.setContentsMargins(6, 6, 6, 6)
        self.tabel_komp = QTableWidget()
        self.tabel_komp.setColumnCount(4)
        self.tabel_komp.setHorizontalHeaderLabels(["Parameter", "Nilai Asli", "Kelayakan (0-100)", "Bobot"])
        kh = self.tabel_komp.horizontalHeader()
        kh.setSectionResizeMode(0, QHeaderView.Stretch)
        kh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        kh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        kh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        glay.addWidget(self.tabel_komp)
        rlay.addWidget(gb_komp, 2)

        sp.addWidget(kanan)
        sp.setStretchFactor(0, 5)
        sp.setStretchFactor(1, 4)
        lay.addWidget(sp, 1)

        # Bilah bawah
        bawah = QHBoxLayout()
        b_salin_svg = QPushButton("Salin Radar SVG")
        b_salin_svg.clicked.connect(self._salin_svg)
        b_simpan_svg = QPushButton("Simpan Radar SVG…")
        b_simpan_svg.clicked.connect(self._simpan_svg)
        b_ekspor_csv = QPushButton("Simpan Tabel CSV…")
        b_ekspor_csv.clicked.connect(self._ekspor_csv)
        bawah.addWidget(b_salin_svg)
        bawah.addWidget(b_simpan_svg)
        bawah.addWidget(b_ekspor_csv)
        bawah.addStretch(1)

        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.accept)
        bawah.addWidget(b_tutup)
        lay.addLayout(bawah)

        self._muat_data()

    def _muat_data(self):
        pr = self.jw.proyek
        if not pr:
            return

        # Dapatkan ΔG terbaik per ligan
        dg_per_lid = {}
        for b in eksmod.baris_hasil(pr):
            lid = b["lid"]
            dg_per_lid[lid] = min(dg_per_lid.get(lid, 0.0), b["energi"])

        preset = self.cb_preset.currentData()
        self.data_mpo = []

        for lid, nama, teks, fmt, l in self.jw._sumber_sifat():
            s = (l or {}).get("sifat")
            if not isinstance(s, dict) or s.get("v") != sifat.VERSI:
                try:
                    s = sifat.dari_teks(teks, fmt)
                except Exception as e:
                    catat.log.warning(f"MPO: gagal membaca sifat ligan '{nama}': {e}")
                    continue
                if l is not None:
                    l["sifat"] = s
            dg = dg_per_lid.get(lid)
            hasil = mpo.hitung_mpo(s, dg=dg, preset=preset)
            self.data_mpo.append((lid, nama, s, dg, hasil))

        self.data_mpo.sort(key=lambda x: x[4]["skor"], reverse=True)
        self._tampilkan_tabel()

    def _hitung_ulang(self):
        with kit.sibuk(self.l_info_ligan, "Menghitung skor MPO…"):
            self._muat_data()

    def _tampilkan_tabel(self):
        t = theme.TOKEN[self.jw.mode if hasattr(self.jw, "mode") else "terang"]
        self.tabel_ligan.setSortingEnabled(False)
        self.tabel_ligan.setRowCount(len(self.data_mpo))

        for row, (lid, nama, s, dg, hasil) in enumerate(self.data_mpo):
            it_nama = _sel(nama)
            it_nama.setData(Qt.UserRole + 1, row)
            self.tabel_ligan.setItem(row, 0, it_nama)

            skor = hasil["skor"]
            it_mpo = _sel(id_angka(f"{skor:.1f}"), angka=skor, align_right=True)
            w_kunci = hasil.get("warna", "ok")
            it_mpo.setForeground(QColor(t.get(w_kunci, t["ok"])))
            self.tabel_ligan.setItem(row, 1, it_mpo)

            it_kat = _sel(hasil["kategori"])
            it_kat.setForeground(QColor(t.get(w_kunci, t["ok"])))
            self.tabel_ligan.setItem(row, 2, it_kat)

            self.tabel_ligan.setItem(row, 3, _sel(id_angka(f"{dg:.2f}") if dg is not None else "–", angka=dg))
            sas = s.get("sascore")
            self.tabel_ligan.setItem(row, 4, _sel(id_angka(f"{sas:.2f}") if sas is not None else "–", angka=sas))
            qed = s.get("qed")
            self.tabel_ligan.setItem(row, 5, _sel(id_angka(f"{qed:.3f}") if qed is not None else "–", angka=qed))
            mw = s.get("mw")
            self.tabel_ligan.setItem(row, 6, _sel(id_angka(f"{mw:.1f}") if mw is not None else "–", angka=mw))
            wlogp = s.get("wlogp")
            self.tabel_ligan.setItem(row, 7, _sel(id_angka(f"{wlogp:.2f}") if wlogp is not None else "–", angka=wlogp))
            tpsa = s.get("tpsa")
            self.tabel_ligan.setItem(row, 8, _sel(id_angka(f"{tpsa:.1f}") if tpsa is not None else "–", angka=tpsa))

        self.tabel_ligan.setSortingEnabled(True)
        self.l_info_ligan.setText(f"Total: {len(self.data_mpo)} ligan. Urut skor kelayakan (desirability).")
        if self.data_mpo:
            self.tabel_ligan.selectRow(0)

    def _pilih_ligan(self):
        sel_items = self.tabel_ligan.selectedItems()
        if not sel_items:
            return
        row = self.tabel_ligan.currentRow()
        it_nama = self.tabel_ligan.item(row, 0)
        if not it_nama:
            return
        idx = it_nama.data(Qt.UserRole + 1)
        if idx is None or idx >= len(self.data_mpo):
            return

        lid, nama, s, dg, hasil = self.data_mpo[idx]
        komponen = hasil["komponen"]

        # Gambar Radar Chart
        labels = [k["label"] for k in komponen.values()]
        values = [k["skor"] for k in komponen.values()]
        gelap = (self.jw.mode == "gelap") if hasattr(self.jw, "mode") else False

        self.svg_aktif = grafik.radar_svg(
            labels, values, maks=100.0,
            lebar=440, tinggi=380, gelap=gelap,
            judul=f"{nama} - Radar MPO",
            subjudul=f"Skor kelayakan {id_angka(f'{hasil['skor']:.1f}')} dari 100 ({hasil['kategori']})"
        )
        self.kanvas.set_svg(self.svg_aktif)

        # Perbarui tabel rincian
        self.tabel_komp.setRowCount(len(komponen))
        for r, (kunci, kdata) in enumerate(komponen.items()):
            self.tabel_komp.setItem(r, 0, _sel(kdata["label"]))
            val = kdata["nilai"]
            val_str = id_angka(f"{val:.2f}") if isinstance(val, float) else str(val) if val is not None else "–"
            self.tabel_komp.setItem(r, 1, _sel(val_str, align_right=True))
            self.tabel_komp.setItem(r, 2, _sel(id_angka(f"{kdata['skor']:.1f}"), angka=kdata["skor"], align_right=True))
            self.tabel_komp.setItem(r, 3, _sel(id_angka(f"{kdata['bobot']:.1f}"), angka=kdata["bobot"], align_right=True))

    def _salin_svg(self):
        if not self.svg_aktif:
            return
        QGuiApplication.clipboard().setText(self.svg_aktif)
        self.jw.status.showMessage("Grafik radar SVG berhasil disalin ke papan klip.", 3000)

    def _simpan_svg(self):
        if not self.svg_aktif:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Radar SVG", "radar_mpo.svg", "Berkas SVG (*.svg)")
        if path:
            from pathlib import Path
            Path(path).write_text(self.svg_aktif, encoding="utf-8")
            self.jw.status.showMessage(f"Radar SVG disimpan ke {path}", 3000)

    def _ekspor_csv(self):
        if not self.data_mpo:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Hasil MPO", "hasil_mpo.csv", "Berkas CSV (*.csv)")
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Ligan", "MPO_Skor", "Kategori", "DeltaG", "SAScore", "QED", "MW", "WLOGP", "TPSA"])
            for lid, nama, s, dg, hasil in self.data_mpo:
                w.writerow([
                    nama, hasil["skor"], hasil["kategori"],
                    dg if dg is not None else "",
                    s.get("sascore", ""), s.get("qed", ""),
                    s.get("mw", ""), s.get("wlogp", ""), s.get("tpsa", "")
                ])
        self.jw.status.showMessage(f"Tabel MPO disimpan ke {path}", 3000)
