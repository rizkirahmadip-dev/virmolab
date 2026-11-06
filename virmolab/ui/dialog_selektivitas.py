"""Dialog Selektivitas Multi-Target & Ensemble Docking.

Membandingkan afinitas ligan terhadap beberapa target protein sekaligus
untuk mengidentifikasi senyawa selektif vs promiskuitas obat.
"""
import csv
import io
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from ..core import grafik, selektivitas
from ..core.proyek import Proyek
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


class DialogSelektivitas(QDialog):
    def __init__(self, jw):
        parent = jw if isinstance(jw, QWidget) else None
        super().__init__(parent)
        self.jw = jw
        proyek_awal = jw.proyek
        self.setWindowTitle("Selektivitas multi-target")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1240, 760)

        self.daftar_proyek = []  # list of (nama_target, Proyek)
        if proyek_awal:
            nama_t = ""
            if hasattr(proyek_awal, "reseptor") and isinstance(proyek_awal.reseptor, dict):
                nama_t = proyek_awal.reseptor.get("nama") or ""
            if not nama_t:
                nama_t = proyek_awal.nama or "Target Utama"
            self.daftar_proyek.append((nama_t, proyek_awal))

        self.label_ligan = []
        self.label_target = []
        self.matriks = []
        self.matriks_z = []
        self.klasifikasi = []

        lay_utama = QVBoxLayout(self)
        lay_utama.setContentsMargins(12, 12, 12, 12)
        lay_utama.setSpacing(8)
        lay_utama.addWidget(kit.judul(
            "Selektivitas multi-target",
            "Bandingkan skor ligan yang sama di beberapa proyek target untuk menilai selektivitas dan risiko efek samping. Perbedaan ΔG di bawah 1 kcal/mol antar-target berada dalam galat fungsi skor, jadi jangan dibaca sebagai selektivitas."))

        # Bilah atas
        bar_atas = QHBoxLayout()
        b_tambah = QPushButton("Tambah Proyek Target…")
        b_tambah.clicked.connect(self._tambah_proyek)
        bar_atas.addWidget(b_tambah)

        bar_atas.addWidget(QLabel("Metrik Tampilan:"))
        self.cb_metrik = QComboBox()
        self.cb_metrik.setToolTip("ΔG membandingkan afinitas mentah antar-target; efisiensi ligan (LE) menormalkan terhadap ukuran molekul, sehingga ligan besar tidak otomatis tampak lebih selektif.")
        self.cb_metrik.addItem("Afinitas Docking ΔG (kcal/mol)", "energi")
        self.cb_metrik.addItem("Ligand Efficiency (LE)", "le")
        self.cb_metrik.addItem("Z-Score Relatif Per Target", "zscore")
        self.cb_metrik.currentIndexChanged.connect(self._hitung_dan_tampilkan)
        bar_atas.addWidget(self.cb_metrik)

        bar_atas.addSpacing(16)
        self.l_status = QLabel("")
        self.l_status.setObjectName("subjudul")
        bar_atas.addWidget(self.l_status, 1)

        b_analisis = QPushButton("Hitung Matriks")
        b_analisis.setObjectName("primary")
        b_analisis.clicked.connect(self._hitung_dan_tampilkan)
        bar_atas.addWidget(b_analisis)
        lay_utama.addLayout(bar_atas)

        # Splitter: Kiri (Daftar Target + Statistik) vs Kanan (Heatmap + Tabel)
        sp = QSplitter(Qt.Horizontal)

        # Panel Kiri
        w_kiri = QWidget()
        lay_kiri = QVBoxLayout(w_kiri)
        lay_kiri.setContentsMargins(0, 0, 0, 0)
        lay_kiri.setSpacing(8)

        gb_target = QGroupBox("Daftar Target Protein")
        lay_gt = QVBoxLayout(gb_target)
        self.list_target = QListWidget()
        lay_gt.addWidget(self.list_target)

        b_hapus_tgt = QPushButton("Hapus Target Terpilih")
        b_hapus_tgt.clicked.connect(self._hapus_target)
        lay_gt.addWidget(b_hapus_tgt)
        lay_kiri.addWidget(gb_target, 2)

        gb_stat = QGroupBox("Ringkasan Profil Selektivitas")
        lay_stat = QVBoxLayout(gb_stat)
        self.l_stat_selektif = QLabel("Selektif: -")
        self.l_stat_semi = QLabel("Semi-selektif: -")
        self.l_stat_promis = QLabel("Promiskuitas: -")
        lay_stat.addWidget(self.l_stat_selektif)
        lay_stat.addWidget(self.l_stat_semi)
        lay_stat.addWidget(self.l_stat_promis)
        lay_kiri.addWidget(gb_stat, 1)

        w_kiri.setMaximumWidth(280)
        sp.addWidget(w_kiri)

        # Panel Kanan
        w_kanan = QWidget()
        lay_kanan = QVBoxLayout(w_kanan)
        lay_kanan.setContentsMargins(0, 0, 0, 0)
        lay_kanan.setSpacing(6)

        sp_kanan = QSplitter(Qt.Vertical)

        # Atas: Heatmap Ligan x Target
        w_heat = QWidget()
        lay_h = QVBoxLayout(w_heat)
        lay_h.setContentsMargins(0, 0, 0, 0)
        lay_h.addWidget(QLabel("Peta Panas Selektivitas Ligan × Target:"))
        self.kanvas_heat = KanvasSvg()
        lay_h.addWidget(self.kanvas_heat)
        sp_kanan.addWidget(w_heat)

        # Bawah: Tabel Lengkap
        w_tab = QWidget()
        lay_t = QVBoxLayout(w_tab)
        lay_t.setContentsMargins(0, 0, 0, 0)
        self.tabel_selektivitas = QTableWidget()
        self.tabel_selektivitas.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabel_selektivitas.setSelectionMode(QTableWidget.SingleSelection)
        self.tabel_selektivitas.setSortingEnabled(True)
        self.tabel_selektivitas.setAlternatingRowColors(True)
        lay_t.addWidget(self.tabel_selektivitas)

        bar_aksi = QHBoxLayout()
        b_salin = QPushButton("Salin Matriks ke Clipboard")
        b_salin.clicked.connect(self._salin_matriks)
        bar_aksi.addWidget(b_salin)

        b_csv = QPushButton("Ekspor CSV Matriks…")
        b_csv.clicked.connect(self._ekspor_csv)
        bar_aksi.addWidget(b_csv)
        bar_aksi.addStretch(1)

        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.close)
        bar_aksi.addWidget(b_tutup)
        lay_t.addLayout(bar_aksi)

        sp_kanan.addWidget(w_tab)
        lay_kanan.addWidget(sp_kanan)
        sp.addWidget(w_kanan)
        sp.setStretchFactor(1, 3)

        lay_utama.addWidget(sp)

        self._perbarui_daftar_target_ui()
        self._hitung_dan_tampilkan()

    def _perbarui_daftar_target_ui(self):
        self.list_target.clear()
        for idx, (nama, pr) in enumerate(self.daftar_proyek):
            n_lig = len(pr.ligan) if hasattr(pr, "ligan") else 0
            n_job = len(pr.job) if hasattr(pr, "job") else 0
            it = QListWidgetItem(f"[{idx+1}] {nama} ({n_lig} ligan, {n_job} job)")
            self.list_target.addItem(it)

    def _tambah_proyek(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Proyek VirmoLab (*.vmd)")
        if not folder:
            return

        p = Path(folder)
        if not (p / "proyek.json").exists():
            QMessageBox.warning(self, "Bukan Proyek VirmoLab", "Folder yang dipilih tidak mengandung berkas 'proyek.json'.")
            return

        try:
            pr = Proyek.buka(p)
            nama_t = ""
            if pr.reseptor and isinstance(pr.reseptor, dict):
                nama_t = pr.reseptor.get("nama") or ""
            if not nama_t:
                nama_t = pr.nama or f"Target {len(self.daftar_proyek) + 1}"
            self.daftar_proyek.append((nama_t, pr))
            self._perbarui_daftar_target_ui()
            self._hitung_dan_tampilkan()
        except Exception as e:
            QMessageBox.critical(self, "Gagal Membuka Proyek", f"Terjadi galat: {e}")

    def _hapus_target(self):
        row = self.list_target.currentRow()
        if 0 <= row < len(self.daftar_proyek):
            if len(self.daftar_proyek) <= 1:
                QMessageBox.information(self, "Minimal 1", "Harus ada minimal 1 proyek di dalam daftar.")
                return
            del self.daftar_proyek[row]
            self._perbarui_daftar_target_ui()
            self._hitung_dan_tampilkan()

    def _hitung_dan_tampilkan(self):
        with kit.sibuk(self.l_status, "Menghitung matriks selektivitas…"):
            if not self.daftar_proyek:
                self.l_status.setText("Belum ada proyek target.")
                return

            metrik_pilih = self.cb_metrik.currentData()
            var_hitung = "energi" if metrik_pilih == "zscore" else metrik_pilih

            self.label_ligan, self.label_target, self.matriks, _ = selektivitas.matriks_selektivitas(
                self.daftar_proyek, variabel=var_hitung
            )

            if not self.label_ligan:
                self.l_status.setText("Tidak ada hasil docking yang cocok pada target terpilih.")
                self.kanvas_heat.set_svg(grafik.heatmap_svg([], [], [], judul="Peta Panas Kosong"))
                self.tabel_selektivitas.setRowCount(0)
                return

            self.matriks_z = selektivitas.zscore_normalisasi(self.matriks)
            self.klasifikasi = selektivitas.klasifikasi_selektivitas(self.matriks, self.label_target)

            # Hitung statistik
            n_sel = sum(1 for k in self.klasifikasi if "Selektif" in k["kelas"] and "Semi" not in k["kelas"])
            n_semi = sum(1 for k in self.klasifikasi if "Semi-selektif" in k["kelas"])
            n_prom = sum(1 for k in self.klasifikasi if k["kelas"] == "Promiskuitas")
            self.l_stat_selektif.setText(f"Selektif Kuat: {n_sel} ligan")
            self.l_stat_semi.setText(f"Semi-selektif: {n_semi} ligan")
            self.l_stat_promis.setText(f"Promiskuitas: {n_prom} ligan")

            self.l_status.setText(f"{len(self.label_ligan)} ligan dianalisis lintas {len(self.label_target)} target protein.")

            # Gambar Heatmap
            gelap = theme.is_dark() if hasattr(theme, "is_dark") else False
            mat_tampil = self.matriks_z if metrik_pilih == "zscore" else self.matriks

            judul_hm = "Peta Panas Z-Score Relatif" if metrik_pilih == "zscore" else f"Peta Panas Afinitas ({metrik_pilih.upper()})"
            svg = grafik.heatmap_svg(
                mat_tampil[:40],
                label_baris=self.label_ligan[:40],
                label_kolom=self.label_target,
                judul=judul_hm,
                gelap=gelap,
                palet="biru_merah"
            )
            self.kanvas_heat.set_svg(svg)

            # Isi Tabel
            self._isi_tabel(mat_tampil, metrik_pilih)

    def _isi_tabel(self, mat_tampil, metrik_pilih):
        n_col_target = len(self.label_target)
        header = ["Ligan"] + self.label_target + ["Klasifikasi", "Gap ΔΔG (kcal/mol)", "Cakupan Target"]
        self.tabel_selektivitas.setSortingEnabled(False)
        self.tabel_selektivitas.setColumnCount(len(header))
        self.tabel_selektivitas.setHorizontalHeaderLabels(header)
        self.tabel_selektivitas.setRowCount(len(self.label_ligan))

        h = self.tabel_selektivitas.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, len(header)):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        for row in range(len(self.label_ligan)):
            self.tabel_selektivitas.setItem(row, 0, _sel(self.label_ligan[row]))

            # Kolom nilai per target
            for c in range(n_col_target):
                v = mat_tampil[row][c]
                fmt_v = id_angka(f"{v:.2f}") if v is not None else "–"
                self.tabel_selektivitas.setItem(row, c + 1, _sel(fmt_v, v, True))

            # Kolom klasifikasi & gap
            info_k = self.klasifikasi[row] if row < len(self.klasifikasi) else {}
            kelas_str = info_k.get("kelas", "-")
            it_kelas = _sel(kelas_str)
            if "Selektif" in kelas_str and "Semi" not in kelas_str:
                it_kelas.setForeground(QColor("#16a34a"))  # Hijau
            elif "Promiskuitas" in kelas_str:
                it_kelas.setForeground(QColor("#ea580c"))  # Jingga
            self.tabel_selektivitas.setItem(row, n_col_target + 1, it_kelas)

            ddg_val = info_k.get("ddg", 0.0)
            self.tabel_selektivitas.setItem(row, n_col_target + 2, _sel(id_angka(f"{ddg_val:.2f}"), ddg_val, True))
            self.tabel_selektivitas.setItem(row, n_col_target + 3, _sel(str(info_k.get("cakupan", 0)), info_k.get("cakupan", 0), True))

        self.tabel_selektivitas.setSortingEnabled(True)

    def _salin_matriks(self):
        if not self.label_ligan:
            return
        out = io.StringIO()
        writer = csv.writer(out, delimiter="\t")
        header = ["Ligan"] + self.label_target + ["Klasifikasi", "Gap_ddG"]
        writer.writerow(header)
        for r, lig in enumerate(self.label_ligan):
            row_vals = [lig] + [self.matriks[r][c] for c in range(len(self.label_target))]
            info_k = self.klasifikasi[r] if r < len(self.klasifikasi) else {}
            row_vals += [info_k.get("kelas", ""), info_k.get("ddg", 0.0)]
            writer.writerow(row_vals)
        QGuiApplication.clipboard().setText(out.getvalue())
        QMessageBox.information(self, "Disalin", f"Matriks {len(self.label_ligan)} ligan berhasil disalin ke clipboard.")

    def _ekspor_csv(self):
        if not self.label_ligan:
            QMessageBox.information(self, "Kosong", "Tidak ada data selektivitas untuk diekspor.")
            return
        jalur, _ = QFileDialog.getSaveFileName(self, "Simpan Matriks Selektivitas", "matriks_selektivitas.csv", "CSV (*.csv)")
        if not jalur:
            return
        try:
            with open(jalur, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                header = ["ligan"] + [f"dg_{t}" for t in self.label_target] + ["klasifikasi", "gap_ddg", "cakupan"]
                writer.writerow(header)
                for r, lig in enumerate(self.label_ligan):
                    vals = [self.matriks[r][c] for c in range(len(self.label_target))]
                    info_k = self.klasifikasi[r] if r < len(self.klasifikasi) else {}
                    writer.writerow([lig] + vals + [info_k.get("kelas", ""), info_k.get("ddg", 0.0), info_k.get("cakupan", 0)])
            QMessageBox.information(self, "Sukses", f"Berhasil mengekspor matriks ke {jalur}")
        except Exception as e:
            QMessageBox.critical(self, "Galat", f"Gagal mengekspor berkas: {e}")
