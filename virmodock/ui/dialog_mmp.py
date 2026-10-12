"""Dialog Molecular Matched Pair (MMP) Analysis.

Menganalisis pasangan molekul dengan satu variasi substituen (R-group),
mengidentifikasi SAR Activity Cliffs, dan memberikan saran modifikasi struktur.
"""
import csv
import io
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from ..core import ekspor as eksmod
from ..core import grafik, mmp, penapisan
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


class DialogMMP(QDialog):
    liganDipilih = Signal(str)

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.proyek = jw.proyek
        self.setWindowTitle("Pasangan molekul berpadanan (MMP)")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1220, 750)

        self.pasangan = []
        self.tabel_data = []
        self.cliffs = []
        self.saran = []

        lay_utama = QVBoxLayout(self)
        lay_utama.setContentsMargins(12, 12, 12, 12)
        lay_utama.setSpacing(8)

        # Bilah atas
        bar_atas = QHBoxLayout()
        self.l_info = QLabel("Memuat data ligan dan pasangan MMP...")
        self.l_info.setObjectName("subjudul")
        bar_atas.addWidget(self.l_info, 1)

        bar_atas.addWidget(QLabel("Ambang SAR Cliff: |ΔΔG| ≥"))
        self.sp_ddg = QDoubleSpinBox()
        self.sp_ddg.setRange(0.5, 8.0)
        self.sp_ddg.setValue(1.5)
        self.sp_ddg.setSingleStep(0.2)
        self.sp_ddg.valueChanged.connect(self._hitung_ulang_cliff)
        bar_atas.addWidget(self.sp_ddg)

        bar_atas.addWidget(QLabel("kcal/mol, Tanimoto ≥"))
        self.sp_sim = QDoubleSpinBox()
        self.sp_sim.setRange(0.3, 0.99)
        self.sp_sim.setValue(0.65)
        self.sp_sim.setSingleStep(0.05)
        self.sp_sim.valueChanged.connect(self._hitung_ulang_cliff)
        bar_atas.addWidget(self.sp_sim)

        b_refresh = QPushButton("Analisis Ulang")
        b_refresh.clicked.connect(self._muat_dan_analisis)
        bar_atas.addWidget(b_refresh)
        lay_utama.addLayout(bar_atas)

        # Splitter: Kiri (Tabel Pasangan) vs Kanan (Grafik SAR Cliff + Panel Saran)
        sp = QSplitter(Qt.Horizontal)

        # Bagian Kiri: Tabel Pasangan MMP
        w_kiri = QWidget()
        lay_kiri = QVBoxLayout(w_kiri)
        lay_kiri.setContentsMargins(0, 0, 0, 0)
        lay_kiri.setSpacing(6)

        lay_kiri.addWidget(QLabel("Daftar Pasangan Molecular Matched Pair (MMP):"))
        self.tabel_mmp = QTableWidget()
        self.tabel_mmp.setColumnCount(9)
        self.tabel_mmp.setHorizontalHeaderLabels([
            "Ligan A", "Ligan B", "Substitusi (A → B)", "ΔG A", "ΔG B", "ΔΔG",
            "ΔQED", "Kemiripan", "Efek"
        ])
        self.tabel_mmp.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabel_mmp.setSelectionMode(QTableWidget.SingleSelection)
        self.tabel_mmp.setSortingEnabled(True)
        self.tabel_mmp.setAlternatingRowColors(True)
        h = self.tabel_mmp.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        for col in range(3, 9):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.tabel_mmp.itemSelectionChanged.connect(self._pilih_pasangan)
        lay_kiri.addWidget(self.tabel_mmp)

        # Tombol aksi tabel
        bar_tombol_tabel = QHBoxLayout()
        b_salin = QPushButton("Salin Tabel Pasangan")
        b_salin.clicked.connect(self._salin_tabel)
        bar_tombol_tabel.addWidget(b_salin)

        b_csv = QPushButton("Ekspor CSV…")
        b_csv.clicked.connect(self._ekspor_csv)
        bar_tombol_tabel.addWidget(b_csv)

        bar_tombol_tabel.addStretch(1)
        b_sorot = QPushButton("Lihat di 3D Viewer")
        b_sorot.setObjectName("primary")
        b_sorot.clicked.connect(self._kirim_ke_viewer)
        bar_tombol_tabel.addWidget(b_sorot)

        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.close)
        bar_tombol_tabel.addWidget(b_tutup)
        lay_kiri.addLayout(bar_tombol_tabel)

        sp.addWidget(w_kiri)

        # Bagian Kanan: Grafik SAR Cliff & Rekomendasi
        w_kanan = QWidget()
        lay_kanan = QVBoxLayout(w_kanan)
        lay_kanan.setContentsMargins(0, 0, 0, 0)
        lay_kanan.setSpacing(6)

        # Kanvas Scatter Plot SAR Cliff
        self.kanvas_cliff = KanvasSvg()
        lay_kanan.addWidget(self.kanvas_cliff, 3)

        # Panel Rekomendasi Modifikasi R-Group
        gb_saran = QGroupBox("Rekomendasi Substitusi R-Group Paling Menguntungkan")
        lay_saran = QVBoxLayout(gb_saran)
        lay_saran.setContentsMargins(8, 8, 8, 8)
        self.tabel_saran = QTableWidget()
        self.tabel_saran.setColumnCount(4)
        self.tabel_saran.setHorizontalHeaderLabels([
            "Substitusi R-Group", "Rerata ΔΔG (kcal/mol)", "Pasangan Cocok", "Tingkat Sukses"
        ])
        hs = self.tabel_saran.horizontalHeader()
        hs.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 4):
            hs.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        lay_saran.addWidget(self.tabel_saran)
        lay_kanan.addWidget(gb_saran, 2)

        sp.addWidget(w_kanan)
        sp.setStretchFactor(0, 3)
        sp.setStretchFactor(1, 2)
        lay_utama.addWidget(sp)

        # Muat data pertama kali
        self._muat_dan_analisis()

    def _muat_dan_analisis(self):
        with kit.sibuk(self.l_info, "Mencari pasangan MMP…"):
            if not self.proyek:
                self.l_info.setText("Proyek belum dibuka.")
                return

            # 1. Kumpulkan molekul / SMILES
            lig_list = [(l["nama"], l["smiles"]) for l in kit.ligan_proyek(self.jw, dengan_mol=False)]

            if len(lig_list) < 2:
                self.l_info.setText("Perlu minimal 2 ligan dengan struktur valid untuk analisis MMP.")
                return

            # 2. Kumpulkan data docking
            data_vs = penapisan.gabung_data(self.proyek)
            data_docking = {d["nama"]: d for d in data_vs}

            # 3. Cari pasangan MMP
            self.pasangan = mmp.cari_pasangan(lig_list)
            self.tabel_data = mmp.tabel_rgroup(self.pasangan, data_docking)
            self._hitung_ulang_cliff()

    def _hitung_ulang_cliff(self):
        with kit.sibuk(self.l_info, "Menghitung jurang aktivitas…"):
            ambang_ddg = self.sp_ddg.value()
            ambang_sim = self.sp_sim.value()

            self.cliffs = mmp.sar_cliff(self.tabel_data, ambang_ddg=ambang_ddg, ambang_sim=ambang_sim)
            self.saran = mmp.saran_modifikasi(self.tabel_data, n=6)

            n_pasang = len(self.tabel_data)
            n_cliff = len(self.cliffs)
            self.l_info.setText(
                f"Ditemukan {n_pasang} pasangan MMP | {n_cliff} SAR Cliffs (|ΔΔG| ≥ {ambang_ddg}, Sim ≥ {ambang_sim})"
            )

            self._perbarui_tabel_mmp()
            self._perbarui_grafik_cliff()
            self._perbarui_tabel_saran()

    def _perbarui_tabel_mmp(self):
        self.tabel_mmp.setSortingEnabled(False)
        self.tabel_mmp.setRowCount(len(self.tabel_data))

        cliff_keys = {(c["id_a"], c["id_b"]) for c in self.cliffs}

        for row, it in enumerate(self.tabel_data):
            is_cliff = (it["id_a"], it["id_b"]) in cliff_keys or (it["id_b"], it["id_a"]) in cliff_keys

            item_a = _sel(it["id_a"])
            item_b = _sel(it["id_b"])
            if is_cliff:
                item_a.setForeground(QColor("#dc2626"))
                item_b.setForeground(QColor("#dc2626"))

            self.tabel_mmp.setItem(row, 0, item_a)
            self.tabel_mmp.setItem(row, 1, item_b)

            subst = f"{it['r_a']}  →  {it['r_b']}"
            self.tabel_mmp.setItem(row, 2, _sel(subst))

            self.tabel_mmp.setItem(row, 3, _sel(id_angka(f"{it['dg_a']:.2f}") if it.get("dg_a") is not None else "–", it.get("dg_a"), True))
            self.tabel_mmp.setItem(row, 4, _sel(id_angka(f"{it['dg_b']:.2f}") if it.get("dg_b") is not None else "–", it.get("dg_b"), True))

            ddg_str = id_angka(f"{it['ddg']:+.2f}").replace("+", "+") if it.get("ddg") is not None else "–"
            it_ddg = _sel(ddg_str, it.get("abs_ddg"), True)
            if it.get("ddg") is not None and it["ddg"] < -0.5:
                it_ddg.setForeground(QColor("#16a34a"))  # Lebih kuat (hijau)
            elif it.get("ddg") is not None and it["ddg"] > 0.5:
                it_ddg.setForeground(QColor("#dc2626"))  # Lebih lemah (merah)
            self.tabel_mmp.setItem(row, 5, it_ddg)

            dqed_str = id_angka(f"{it['dqed']:+.2f}") if it.get("dqed") is not None else "–"
            self.tabel_mmp.setItem(row, 6, _sel(dqed_str, it.get("dqed"), True))

            self.tabel_mmp.setItem(row, 7, _sel(id_angka(f"{it['tanimoto']:.2f}"), it.get("tanimoto"), True))
            self.tabel_mmp.setItem(row, 8, _sel(it.get("efek", "-")))

        self.tabel_mmp.setSortingEnabled(True)

    def _perbarui_grafik_cliff(self):
        gelap = theme.is_dark() if hasattr(theme, "is_dark") else False
        cliff_keys = {(c["id_a"], c["id_b"]) for c in self.cliffs}

        plot_data = []
        for it in self.tabel_data:
            is_c = (it["id_a"], it["id_b"]) in cliff_keys or (it["id_b"], it["id_a"]) in cliff_keys
            item_p = {
                "nama": f"{it['id_a']} vs {it['id_b']}",
                "tanimoto": it["tanimoto"],
                "abs_ddg": it["abs_ddg"],
                "is_cliff": is_c,
            }
            plot_data.append(item_p)

        svg = grafik.scatter_multi_svg(
            plot_data,
            x_kunci="tanimoto",
            y_kunci="abs_ddg",
            x_label="Kemiripan Struktur (Tanimoto)",
            y_label="|ΔΔG| Perubahan Afinitas (kcal/mol)",
            judul="SAR Activity Cliff Plot (Titik Berbintang: Cliff)",
            gelap=gelap,
            sorot_flag="is_cliff"
        )
        self.kanvas_cliff.set_svg(svg)

    def _perbarui_tabel_saran(self):
        self.tabel_saran.setRowCount(len(self.saran))
        for r, s in enumerate(self.saran):
            self.tabel_saran.setItem(r, 0, _sel(s["transformasi"]))
            it_ddg = _sel(id_angka(f"{s['rata_rata_ddg']:+.2f}"), s["rata_rata_ddg"], True)
            it_ddg.setForeground(QColor("#16a34a"))
            self.tabel_saran.setItem(r, 1, it_ddg)
            self.tabel_saran.setItem(r, 2, _sel(str(s["jumlah_pasangan"]), s["jumlah_pasangan"], True))
            self.tabel_saran.setItem(r, 3, _sel(f"{s['persen_sukses']:.0f}%", s["persen_sukses"], True))

    def _pilih_pasangan(self):
        pass

    def _kirim_ke_viewer(self):
        sel = self.tabel_mmp.selectedItems()
        if not sel:
            QMessageBox.information(self, "Pilih Pasangan", "Silakan pilih salah satu pasangan pada tabel.")
            return
        row = self.tabel_mmp.currentRow()
        if 0 <= row < len(self.tabel_data):
            it = self.tabel_data[row]
            # Kirim ligan B (atau A) ke viewer
            self.liganDipilih.emit(it["id_b"])

    def _salin_tabel(self):
        if not self.tabel_data:
            return
        out = io.StringIO()
        writer = csv.writer(out, delimiter="\t")
        writer.writerow(["Ligan A", "Ligan B", "Substitusi", "ΔG A", "ΔG B", "ΔΔG", "ΔQED", "Kemiripan", "Efek"])
        for it in self.tabel_data:
            writer.writerow([
                it["id_a"], it["id_b"], f"{it['r_a']} -> {it['r_b']}",
                it.get("dg_a"), it.get("dg_b"), it.get("ddg"),
                it.get("dqed"), it.get("tanimoto"), it.get("efek")
            ])
        QGuiApplication.clipboard().setText(out.getvalue())
        QMessageBox.information(self, "Disalin", f"{len(self.tabel_data)} pasangan MMP berhasil disalin.")

    def _ekspor_csv(self):
        if not self.tabel_data:
            QMessageBox.information(self, "Kosong", "Tidak ada pasangan MMP untuk diekspor.")
            return
        jalur, _ = QFileDialog.getSaveFileName(self, "Simpan Pasangan MMP", "analisis_mmp.csv", "CSV (*.csv)")
        if not jalur:
            return
        try:
            with open(jalur, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ligan_a", "ligan_b", "inti_core", "r_a", "r_b", "dg_a", "dg_b", "ddg", "abs_ddg", "dqed", "dsa", "tanimoto", "efek"])
                for it in self.tabel_data:
                    writer.writerow([
                        it["id_a"], it["id_b"], it["inti"], it["r_a"], it["r_b"],
                        it.get("dg_a"), it.get("dg_b"), it.get("ddg"), it.get("abs_ddg"),
                        it.get("dqed"), it.get("dsa"), it.get("tanimoto"), it.get("efek")
                    ])
            QMessageBox.information(self, "Sukses", f"Berhasil mengekspor pasangan MMP ke {jalur}")
        except Exception as e:
            QMessageBox.critical(self, "Galat", f"Gagal menyimpan berkas: {e}")
