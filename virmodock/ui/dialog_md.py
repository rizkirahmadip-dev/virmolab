"""Dialog MD & MM/GBSA (Analisis › MD & MM/GBSA…) - rencana A8a: aplikasi menilai kemampuan laptop dan menyarankan.

Tiga tingkat: Ringan (minimisasi + MM/GBSA), Sedang (MD pelarut implisit OBC2), Lengkap (MD air eksplisit TIP3P).
Kecepatan diukur otomatis pada kompleks pengguna sendiri (per perangkat & reseptor, disimpan) -> perkiraan waktu dan
status Disarankan / Bisa (lama) / Tidak disarankan. Perhitungan berjalan di proses terpisah (VirmoDock.exe --md),
bisa dijeda (checkpoint) dan dilanjutkan, juga setelah aplikasi dibuka ulang.
"""
import ctypes
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QRadioButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

from ..core import grafik, paths
from ..core.analisis import NAMA_JENIS
from ..core.laporan import id_angka
from . import kit
from .panel_interaksi import KanvasSvg

TINGKAT = [("ringan", "Ringan", "Minimisasi kompleks + MM/GBSA satu titik (menit; semua laptop)"),
           ("sedang", "Sedang", "MD pelarut implisit (OBC2) + RMSD/RMSF + MM/GBSA rata-rata (puluhan menit-jam)"),
           ("lengkap", "Lengkap", "MD air eksplisit (TIP3P, PME) + MM/GBSA banyak frame (butuh GPU; standar publikasi)")]
# (label, token tema) — warnanya diambil saat dipakai supaya ikut mode gelap
STATUS = {"disarankan": ("Disarankan", "ok"), "bisa": ("Bisa (lama)", "warn"),
          "tidak": ("Tidak disarankan", "bad"), "": ("", "mut")}


def pakai_baterai():
    """True bila laptop berjalan dengan baterai (Windows GetSystemPowerStatus)."""
    if sys.platform != "win32":
        return False

    class SPS(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
    s = SPS()
    try:
        return bool(ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))) and s.ACLineStatus == 0
    except Exception:
        return False


def _jam(j):
    if j < 1 / 60:
        return "< 1 mnt"
    if j < 1:
        return f"± {max(1, round(j * 60))} mnt"
    return f"± {int(j)} j {round((j - int(j)) * 60)} mnt"


class DialogMD(QDialog):
    selesai = Signal(dict, dict)          # (hasil.json, catatan proses)

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.proyek_awal = jw.proyek
        self.setWindowTitle("MD & MM/GBSA - OpenMM")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1180, 820)
        self.proses = None
        self.run = None              # {id, folder, mode, tugas, ligan}
        self.kecepatan = None        # {platform, implisit, eksplisit, atom_i, atom_e}
        self._buf = ""
        lay = QVBoxLayout(self)
        lay.addWidget(kit.judul(
            "Dinamika molekul dan MM/GBSA",
            "Penyempurnaan pasca-docking: kompleks diminimisasi atau disimulasikan dengan OpenMM (protein "
            "Amber ff14SB, ligan OpenFF Sage 2.3 dengan muatan NAGL setara AM1-BCC). ΔG MM/GBSA berguna untuk "
            "membandingkan ligan secara relatif (entropi tidak dihitung), bukan sebagai afinitas absolut."))
        bagi = QSplitter(Qt.Horizontal)
        # ---- kiri: ligan + tingkat + opsi
        kiri = QWidget()
        vk = QVBoxLayout(kiri)
        vk.setContentsMargins(0, 0, 0, 0)
        vk.addWidget(QLabel("<b>Ligan (pose terbaik tiap ligan)</b>"))
        self.tabel = QTableWidget(0, 4)
        self.tabel.setHorizontalHeaderLabels(["Ligan", "ΔG docking", "MM/GBSA", "Job"])
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabel.itemChanged.connect(lambda *_: self._perkiraan())
        vk.addWidget(self.tabel, 1)
        hp = QHBoxLayout()
        for t, n in (("Pilih 5 teratas", 5), ("Pilih semua", -1), ("Kosongkan", 0)):
            b = QToolButton()
            b.setText(t)
            b.clicked.connect(lambda _=False, n=n: self._pilih(n))
            hp.addWidget(b)
        hp.addStretch(1)
        vk.addLayout(hp)
        vk.addWidget(QLabel("<b>Tingkat</b>"))
        g = QGridLayout()
        self.grp = QButtonGroup(self)
        self.l_est, self.l_stat = {}, {}
        for i, (k, nama, des) in enumerate(TINGKAT):
            r = QRadioButton(nama)
            r.setToolTip(des)
            self.grp.addButton(r, i)
            g.addWidget(r, i * 2, 0)
            self.l_stat[k] = QLabel()
            g.addWidget(self.l_stat[k], i * 2, 1)
            self.l_est[k] = QLabel()
            self.l_est[k].setObjectName("mono")
            g.addWidget(self.l_est[k], i * 2, 2)
            d = QLabel(des)
            d.setObjectName("muted")
            d.setWordWrap(True)
            g.addWidget(d, i * 2 + 1, 0, 1, 3)
        g.setColumnStretch(2, 1)
        self.grp.idToggled.connect(lambda *_: self._perkiraan())
        vk.addLayout(g)
        f = QFormLayout()
        self.sp_ns_i = QDoubleSpinBox()
        self.sp_ns_i.setRange(0.1, 100)
        self.sp_ns_i.setValue(2.0)
        self.sp_ns_i.setSuffix(" ns")
        self.sp_ns_e = QDoubleSpinBox()
        self.sp_ns_e.setRange(0.1, 1000)
        self.sp_ns_e.setValue(10.0)
        self.sp_ns_e.setSuffix(" ns")
        self.sp_interval = QDoubleSpinBox()
        self.sp_interval.setRange(1, 1000)
        self.sp_interval.setValue(10)
        self.sp_interval.setSuffix(" ps")
        self.sp_frame = QSpinBox()
        self.sp_frame.setRange(5, 500)
        self.sp_frame.setValue(25)
        self.sp_replika = QSpinBox()
        self.sp_replika.setRange(1, 5)
        self.sp_replika.setValue(1)
        self.sp_replika.setToolTip("Jumlah replika MD independen dengan benih berbeda (1-5, bawaan 1, saran 3)")
        self.cb_plat = QComboBox()
        for t, v in (("Otomatis (GPU bila ada)", "auto"), ("CPU", "CPU")):
            self.cb_plat.addItem(t, v)
        for w in (self.sp_ns_i, self.sp_ns_e, self.sp_replika):
            w.valueChanged.connect(lambda *_: self._perkiraan())
        f.addRow("Lama MD (Sedang)", self.sp_ns_i)
        f.addRow("Lama MD (Lengkap)", self.sp_ns_e)
        f.addRow("Simpan frame tiap", self.sp_interval)
        f.addRow("Frame MM/GBSA", self.sp_frame)
        f.addRow("Jumlah replika", self.sp_replika)
        f.addRow("Perangkat", self.cb_plat)
        self.cb_plat.currentIndexChanged.connect(lambda *_: self._muat_kecepatan(ukur=True))
        vk.addLayout(f)
        hk = QHBoxLayout()
        self.l_kec = QLabel()
        self.l_kec.setWordWrap(True)
        self.l_kec.setObjectName("muted")
        hk.addWidget(self.l_kec, 1)
        self.b_ukur = QPushButton("Ukur kecepatan")
        self.b_ukur.setToolTip("Uji 10-30 detik pada kompleks ligan terpilih pertama (implisit & eksplisit)")
        self.b_ukur.clicked.connect(lambda: self._mulai("uji"))
        hk.addWidget(self.b_ukur)
        vk.addLayout(hk)
        self.l_baterai = QLabel()
        self.l_baterai.setWordWrap(True)
        self.l_baterai.setStyleSheet(f"color:{kit.hx('warn')};")
        vk.addWidget(self.l_baterai)
        bagi.addWidget(kiri)

        # ---- kanan: hasil (UI F2: Ringkasan, Stabilitas, Interaksi, PCA & FEL, Klaster, Replika, Log)
        self.tab = QTabWidget()
        self.k = {}

        # 1. Tab Ringkasan
        w_ringkas = QWidget()
        vr = QVBoxLayout(w_ringkas)
        self.t_hasil = QTableWidget(0, 8)
        self.t_hasil.setHorizontalHeaderLabels(["Ligan", "ΔG docking", "MM/GBSA min", "MM/GBSA MD", "SD", "ΔE vdW",
                                                "Elek + GB", "RMSD ligan"])
        for c, tip in ((2, "ΔG MM/GBSA setelah minimisasi kompleks (kcal/mol)"),
                       (3, "Rerata ΔG MM/GBSA atas frame MD (kcal/mol)"), (4, "Simpangan baku antar-frame"),
                       (5, "Komponen van der Waals"), (6, "ΔE elektrostatik + ΔG solvasi polar (GB) - sering saling "
                                                         "mengimbangi"),
                       (7, "Rerata RMSD atom berat ligan selama MD (Å); > 3 Å = pose tidak stabil")):
            self.t_hasil.horizontalHeaderItem(c).setToolTip(tip)
        self.t_hasil.horizontalHeader().setMinimumSectionSize(70)
        self.t_hasil.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.t_hasil.verticalHeader().setVisible(False)
        self.t_hasil.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t_hasil.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t_hasil.currentCellChanged.connect(lambda r, *_: self._grafik_ligan(r))
        vr.addWidget(self.t_hasil, 1)

        # Baris kartu paruh kedua
        self.k_rmsd_lig = kit.Kartu("RMSD Ligan", "–", "paruh kedua")
        self.k_rmsd_ca = kit.Kartu("RMSD Cα", "–", "paruh kedua")
        self.k_rg = kit.Kartu("Radius Girasi", "–", "paruh kedua")
        self.k_hb = kit.Kartu("Ikatan-H", "–", "blok rata-rata")
        self.k_dg = kit.Kartu("ΔG MM/GBSA", "–", "paruh kedua")
        vr.addLayout(kit.baris_kartu(self.k_rmsd_lig, self.k_rmsd_ca, self.k_rg, self.k_hb, self.k_dg))

        # Baris lencana dan tombol analisis lanjutan
        h_konv = QHBoxLayout()
        self.l_lencana_konv = kit.lencana("Siap", "info")
        self.b_analisis_lanjut = QPushButton("Hitung analisis lanjutan")
        self.b_analisis_lanjut.setToolTip("Hitung Rg, SASA, Barcode, PCA, FEL, dan Klaster dari DCD tersimpan")
        self.b_analisis_lanjut.clicked.connect(self._hitung_analisis_lanjut_klik)
        self.b_analisis_lanjut.setEnabled(False)
        h_konv.addWidget(self.l_lencana_konv)
        h_konv.addWidget(self.b_analisis_lanjut)
        h_konv.addStretch(1)
        vr.addLayout(h_konv)
        self.l_catatan_md = kit.catatan("MD singkat satu replika menunjukkan kestabilan lokal pose, bukan afinitas.", "info")
        vr.addWidget(self.l_catatan_md)
        self.tab.addTab(w_ringkas, "Ringkasan")

        # 2. Tab Stabilitas
        w_stab = QWidget()
        vs = QVBoxLayout(w_stab)
        hs_top = QHBoxLayout()
        hs_top.addWidget(QLabel("Metrik stabilitas:"))
        self.cb_metrik_stab = QComboBox()
        self.cb_metrik_stab.addItem("RMSD (Ligan & Protein Cα)", "rmsd")
        self.cb_metrik_stab.addItem("RMSF Cα per Residu", "rmsf")
        self.cb_metrik_stab.addItem("Radius Girasi Protein (Rg)", "rg")
        self.cb_metrik_stab.addItem("Luas Akses Pelarut (SASA)", "sasa")
        self.cb_metrik_stab.currentIndexChanged.connect(lambda *_: self._segarkan_stabilitas())
        hs_top.addWidget(self.cb_metrik_stab)
        hs_top.addStretch(1)
        vs.addLayout(hs_top)
        self.k["stabilitas"] = KanvasSvg()
        vs.addWidget(self.k["stabilitas"], 1)
        self.tab.addTab(w_stab, "Stabilitas")

        # 3. Tab Interaksi
        w_inter = QWidget()
        vi = QHBoxLayout(w_inter)
        split_inter = QSplitter(Qt.Horizontal)
        w_inter_tabel = QWidget()
        vit = QVBoxLayout(w_inter_tabel)
        vit.setContentsMargins(0, 0, 0, 0)
        vit.addWidget(QLabel("<b>Okupansi Interaksi (≥ 10%)</b>"))
        self.t_inter = QTableWidget(0, 3)
        self.t_inter.setHorizontalHeaderLabels(["Residu", "Jenis", "Okupansi"])
        self.t_inter.verticalHeader().setVisible(False)
        self.t_inter.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t_inter.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t_inter.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.t_inter.itemSelectionChanged.connect(self._sorot_residu_interaksi)
        vit.addWidget(self.t_inter, 1)
        split_inter.addWidget(w_inter_tabel)
        self.k["barcode"] = KanvasSvg()
        split_inter.addWidget(self.k["barcode"])
        split_inter.setSizes([280, 520])
        vi.addWidget(split_inter)
        self.tab.addTab(w_inter, "Interaksi")

        # 4. Tab PCA & FEL
        w_pca_fel = QWidget()
        vp = QHBoxLayout(w_pca_fel)
        split_pf = QSplitter(Qt.Horizontal)
        self.k["pca"] = KanvasSvg()
        self.k["fel"] = KanvasSvg()
        split_pf.addWidget(self.k["pca"])
        split_pf.addWidget(self.k["fel"])
        split_pf.setSizes([400, 400])
        vp.addWidget(split_pf)
        self.tab.addTab(w_pca_fel, kit.amp("PCA & FEL"))

        # 5. Tab Klaster
        w_klas = QWidget()
        vk_layout = QVBoxLayout(w_klas)
        vk_layout.addWidget(QLabel("<b>Klaster Konformasi Ligan (Ambang 2,0 Å)</b>"))
        self.t_klaster = QTableWidget(0, 4)
        self.t_klaster.setHorizontalHeaderLabels(["Klaster", "Ukuran (%)", "Jumlah Frame", "Medoid (Frame)"])
        self.t_klaster.verticalHeader().setVisible(False)
        self.t_klaster.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t_klaster.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t_klaster.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        vk_layout.addWidget(self.t_klaster, 1)
        hk_btn = QHBoxLayout()
        self.b_lihat_medoid = QPushButton("Tampilkan medoid")
        self.b_lihat_medoid.setToolTip("Buka struktur PDB medoid di viewer 3D")
        self.b_lihat_medoid.clicked.connect(self._tampilkan_medoid)
        self.b_pakai_ensemble = QPushButton("Pakai sebagai reseptor ensemble")
        self.b_pakai_ensemble.setToolTip("Simpan dan muat medoid ini sebagai varian konformasi reseptor ke proyek")
        self.b_pakai_ensemble.clicked.connect(self._pakai_sebagai_ensemble)
        hk_btn.addWidget(self.b_lihat_medoid)
        hk_btn.addWidget(self.b_pakai_ensemble)
        hk_btn.addStretch(1)
        vk_layout.addLayout(hk_btn)
        self.tab.addTab(w_klas, "Klaster")

        # 6. Tab Replika
        w_rep = QWidget()
        vr_layout = QVBoxLayout(w_rep)
        vr_layout.addWidget(QLabel("<b>Simulasi Multi-Replika Independen</b>"))
        self.t_replika = QTableWidget(0, 6)
        self.t_replika.setHorizontalHeaderLabels(["Replika", "Seed", "RMSD Ligan (Å)", "RMSD Cα (Å)", "Rg (Å)", "ΔG MM/GBSA (kcal/mol)"])
        self.t_replika.verticalHeader().setVisible(False)
        self.t_replika.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t_replika.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t_replika.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        vr_layout.addWidget(self.t_replika, 1)
        self.l_rep_agregat = QLabel()
        self.l_rep_agregat.setWordWrap(True)
        vr_layout.addWidget(self.l_rep_agregat)
        self.k["replika"] = KanvasSvg()
        vr_layout.addWidget(self.k["replika"], 1)
        self.tab.addTab(w_rep, "Replika")

        # 7. Tab Log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("mono")
        self.tab.addTab(self.log, "Log")

        bagi.addWidget(self.tab)
        bagi.setSizes([430, 750])
        lay.addWidget(bagi, 1)
        self.prog = QProgressBar()
        self.prog.setRange(0, 1000)
        self.prog.setTextVisible(False)
        lay.addWidget(self.prog)
        hb = QHBoxLayout()
        self.l_status = QLabel()
        self.l_status.setObjectName("muted")
        hb.addWidget(self.l_status, 1)
        self.b_jalan = QPushButton("Jalankan")
        self.b_jalan.setObjectName("primary")
        self.b_jalan.clicked.connect(lambda: self._mulai(None))
        self.b_jeda = QPushButton("⏸ Jeda")
        self.b_jeda.setToolTip("Simpan checkpoint lalu berhenti; bisa dilanjutkan kapan saja")
        self.b_jeda.clicked.connect(self.jeda)
        self.b_lanjut = QPushButton("Lanjutkan")
        self.b_lanjut.clicked.connect(self.lanjutkan)

        self.b_komposer = QPushButton("Kirim ke komposer")
        self.b_komposer.setToolTip("Kirim grafik aktif saat ini ke Komposer Figur")
        self.b_komposer.clicked.connect(self._kirim_ke_komposer)

        self.b_grafik = QPushButton("Simpan figur…")
        self.b_grafik.clicked.connect(self._simpan_grafik)

        self.b_ekspor_csv = QPushButton("Ekspor CSV…")
        self.b_ekspor_csv.setToolTip("Ekspor data numerik analisis (RMSD, Rg, SASA, MM/GBSA) ke berkas CSV")
        self.b_ekspor_csv.clicked.connect(self._ekspor_csv)

        self.b_folder = QPushButton("Buka folder")
        self.b_folder.clicked.connect(self._buka_folder)
        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.close)
        for b in (self.b_jalan, self.b_jeda, self.b_lanjut, self.b_komposer, self.b_grafik, self.b_ekspor_csv, self.b_folder, b_tutup):
            hb.addWidget(b)
        lay.addLayout(hb)
        self.hasil = None
        self.muat()

    # ------------------------------------------------------------- data
    def muat(self):
        from ..core import ekspor as eksmod
        pr = self.jw.proyek
        self.baris = eksmod.baris_hasil(pr) if pr else []
        self.tabel.blockSignals(True)
        self.tabel.setRowCount(0)
        for b in self.baris:
            r = self.tabel.rowCount()
            self.tabel.insertRow(r)
            it = QTableWidgetItem(b["ligan"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if r < 5 else Qt.Unchecked)
            it.setData(Qt.UserRole, (b["job"], b["lid"]))
            self.tabel.setItem(r, 0, it)
            self.tabel.setItem(r, 1, QTableWidgetItem(id_angka(f"{b['energi']:.2f}")))
            self.tabel.setItem(r, 2, QTableWidgetItem(id_angka(f"{b['mmgbsa']:.2f}") if b.get("mmgbsa") is not None
                                                      else ""))
            self.tabel.setItem(r, 3, QTableWidgetItem(b["job"]))
        self.tabel.blockSignals(False)
        self.tabel.resizeColumnsToContents()
        if self.grp.checkedId() < 0:
            self.grp.button(0).setChecked(True)
        self.l_baterai.setText("Laptop memakai baterai - colok ke listrik untuk MD (simulasi panjang menguras baterai "
                               "dan bisa diperlambat mode hemat daya)." if pakai_baterai() else "")
        dijeda = next((r for r in reversed(pr.md) if r.get("status") == "dijeda"), None) if pr else None
        if dijeda and not self.proses:
            self.run = dict(dijeda)
            self.l_status.setText(f"MD {dijeda['id']} dijeda - klik Lanjutkan untuk meneruskan dari checkpoint.")
        terakhir = next((r for r in reversed(pr.md) if r.get("status") == "selesai"), None) if pr else None
        if terakhir and not self.hasil:
            f = pr.p(terakhir["folder"], "hasil.json")
            if f.exists():
                self.run = self.run or dict(terakhir)
                self._tampil_hasil(json.loads(f.read_text(encoding="utf-8")), pr.p(terakhir["folder"]))
        self._muat_kecepatan()
        self._tombol()

    def _segarkan_mmgbsa(self):
        """Perbarui kolom MM/GBSA tabel ligan setelah hasil diterapkan ke proyek (centang tidak berubah)."""
        from ..core import ekspor as eksmod
        nilai = {(b["job"], b["lid"]): b.get("mmgbsa") for b in eksmod.baris_hasil(self.jw.proyek)}
        for r in range(self.tabel.rowCount()):
            v = nilai.get(self.tabel.item(r, 0).data(Qt.UserRole))
            self.tabel.item(r, 2).setText(id_angka(f"{v:.2f}") if v is not None else "")
            self.baris[r]["mmgbsa"] = v

    def _pilih(self, n):
        for r in range(self.tabel.rowCount()):
            self.tabel.item(r, 0).setCheckState(Qt.Checked if n < 0 or r < n else Qt.Unchecked)

    def terpilih(self):
        out = []
        for r in range(self.tabel.rowCount()):
            it = self.tabel.item(r, 0)
            if it.checkState() == Qt.Checked:
                out.append(self.baris[r])
        return out

    def tingkat(self):
        return TINGKAT[max(0, self.grp.checkedId())][0]

    # ------------------------------------------------------------- kecepatan & saran
    def _kunci_kecepatan(self):
        pr = self.jw.proyek
        gpu = ""
        try:
            g = self.jw.env.gpu_utama
            gpu = g.nama if g else "CPU"
        except Exception:
            pass
        return f"{gpu}|{self.cb_plat.currentData()}|{(pr.reseptor or {}).get('pdbqt', '') if pr else ''}|{pr.folder if pr else ''}"

    def _muat_kecepatan(self, ukur=False):
        try:
            semua = json.loads(paths.settings().value("md/kecepatan", "{}") or "{}")
        except (TypeError, ValueError):
            semua = {}
        self.kecepatan = semua.get(self._kunci_kecepatan())
        if self.kecepatan:
            k = self.kecepatan
            atom = f"{k.get('atom_e', 0):,}".replace(",", ".")
            imp, eks = id_angka(f"{k['implisit']:.1f}"), id_angka(f"{k['eksplisit']:.1f}")
            self.l_kec.setText(f"Kecepatan terukur ({k['platform']}, kompleks ini): implisit {imp} ns/hari, "
                               f"eksplisit {eks} ns/hari ({atom} atom dengan air).")
        else:
            self.l_kec.setText("Kecepatan laptop belum diukur untuk perangkat & reseptor ini. Pengukuran otomatis "
                               "(±30 detik) saat dialog dibuka.")
            if (ukur or not getattr(self, "_sudah_ukur", False)) and self.terpilih() and not self.proses:
                self._sudah_ukur = True
                QTimer.singleShot(300, lambda: self._mulai("uji"))
        self._perkiraan()

    def _perkiraan(self):
        from ..core.md import saran
        n = max(1, len(self.terpilih()))
        n_rep = max(1, self.sp_replika.value())
        k = self.kecepatan
        gpu = bool(k and k.get("platform") in ("CUDA", "OpenCL"))
        est = {"ringan": (n * (25 if gpu or not k else 60)) / 3600.0}
        st = {"ringan": "disarankan"}
        if k:
            for kunci, ns, kec in (("sedang", self.sp_ns_i.value(), k["implisit"]),
                                   ("lengkap", self.sp_ns_e.value(), k["eksplisit"])):
                s, jam = saran(kec, ns, n * n_rep)
                est[kunci] = jam + (n * n_rep) * (40 if kunci == "lengkap" else 25) / 3600.0
                st[kunci] = "disarankan" if est[kunci] < 2 else "bisa" if est[kunci] <= 12 else "tidak"
        for kunci, *_ in TINGKAT:
            t, tok = STATUS[st.get(kunci, "")]
            w = kit.hx(tok)
            self.l_stat[kunci].setText(f"<span style='color:{w}; font-weight:600'>{t}</span>" if t else "")
            self.l_est[kunci].setText(_jam(est[kunci]) if kunci in est else "belum diukur")
        if k and st.get("lengkap") == "tidak" and self.tingkat() == "lengkap":
            self.l_status.setText("Tingkat Lengkap diperkirakan > 12 jam di laptop ini - pilih Sedang, kurangi ns/ligan, "
                                  "atau jalankan di komputer ber-GPU.")

    # ------------------------------------------------------------- proses
    def _tombol(self):
        jalan = self.proses is not None
        self.b_jalan.setEnabled(not jalan)
        self.b_ukur.setEnabled(not jalan)
        self.b_jeda.setEnabled(jalan and bool(self.run) and self.run.get("mode") == "md")
        self.b_lanjut.setEnabled(not jalan and bool(self.run) and self.run.get("status") == "dijeda")
        self.b_folder.setEnabled(bool(self.run))

    def _item_ligan(self, b):
        from ..core import mesin as M
        pr = self.jw.proyek
        j = self.jw.pelaksana.cari(b["job"])
        l = next(x for x in j["ligan"] if x["id"] == b["lid"])
        pose = M.baca_hasil(j["mesin"], pr.p(l["keluaran"]))[0]
        return {"nama": b["ligan"], "lid": b["lid"], "job": b["job"], "peringkat": 1, "energi_docking": b["energi"],
                "pdbqt_masukan": str(pr.p(l["pdbqt"])), "pose_pdbqt": pose.pdbqt, "flex": pose.flex}

    def _mulai(self, mode):
        pr = self.jw.proyek
        if self.proses:
            return
        pilih = self.terpilih()
        if not pr or not pilih:
            self.l_status.setText("Pilih minimal satu ligan hasil docking.")
            return
        rec = pr.reseptor or {}
        sumber = rec.get("meeko") or rec.get("bersih")
        if not sumber or not pr.p(sumber).exists():
            QMessageBox.warning(self, "MD & MM/GBSA", "Berkas reseptor bersih tidak ditemukan. Siapkan ulang reseptor.")
            return
        mode = mode or ("mmgbsa" if self.tingkat() == "ringan" else "md")
        if mode != "uji" and self.jw.pelaksana.sibuk():
            if QMessageBox.question(self, "MD & MM/GBSA", "Docking sedang berjalan dan memakai GPU/CPU yang sama. "
                                    "Tetap jalankan bersamaan (keduanya melambat)?") != QMessageBox.Yes:
                return
        try:
            ligan = [self._item_ligan(b) for b in (pilih[:1] if mode == "uji" else pilih)]
        except Exception as e:
            QMessageBox.warning(self, "MD & MM/GBSA", f"Pose docking tidak terbaca: {e}")
            return
        if mode == "uji":
            rid = "uji_kecepatan"
            import shutil
            shutil.rmtree(pr.p("md", rid), ignore_errors=True)     # hasil ukur lama tidak boleh terbaca ulang
        else:
            # ID unik (dua proses dalam detik yang sama tidak boleh berbagi folder/hasil)
            dasar = datetime.now().strftime("MD%Y%m%d_%H%M%S")
            rid, k = dasar, 2
            while pr.p("md", rid).exists() or any(r.get("id") == rid for r in pr.md):
                rid, k = f"{dasar}_{k}", k + 1
        folder = pr.p("md", rid)
        folder.mkdir(parents=True, exist_ok=True)
        pelarut = "eksplisit" if self.tingkat() == "lengkap" else "implisit"
        opsi = {"pelarut": pelarut, "ns": self.sp_ns_e.value() if pelarut == "eksplisit" else self.sp_ns_i.value(),
                "interval_ps": self.sp_interval.value(), "frame_mmgbsa": self.sp_frame.value(),
                "platform": self.cb_plat.currentData(), "replika": self.sp_replika.value()}
        tugas = {"mode": mode, "folder": str(folder), "ligan": ligan, "opsi": opsi,
                 "reseptor": {"pdb": str(pr.p(sumber)), "pdbqt": str(pr.p(rec["pdbqt"]))}}
        (folder / "tugas.json").write_text(json.dumps(tugas, ensure_ascii=False, indent=1), encoding="utf-8")
        self.run = {"id": rid, "folder": pr.rel(folder), "mode": mode, "tingkat": self.tingkat() if mode != "uji" else "",
                    "tanggal": datetime.now().isoformat(timespec="seconds"), "status": "berjalan", "opsi": opsi,
                    "ligan": [{"nama": x["nama"], "lid": x["lid"], "job": x["job"]} for x in ligan]}
        if mode != "uji":
            pr.md = [r for r in pr.md if r.get("id") != rid] + [dict(self.run)]
            self.jw.minta_simpan()
        self._proses(folder / "tugas.json")

    def lanjutkan(self):
        if not self.run or self.proses:
            return
        f = self.jw.proyek.p(self.run["folder"], "tugas.json")
        if not f.exists():
            self.l_status.setText("Berkas tugas MD tidak ditemukan.")
            return
        self.run["status"] = "berjalan"
        self._simpan_run()
        self._proses(f)

    def jeda(self):
        if self.proses and self.run:
            self.jw.proyek.p(self.run["folder"], "BERHENTI").write_text("1", encoding="utf-8")
            self.l_status.setText("Menyimpan checkpoint lalu menjeda…")
            self.b_jeda.setEnabled(False)

    def _proses(self, f_tugas):
        self.log.clear()
        self.prog.setValue(0)
        self.proses = QProcess(self)
        self.proses.setProcessChannelMode(QProcess.MergedChannels)
        self.proses.readyReadStandardOutput.connect(self._baca)
        self.proses.finished.connect(self._akhir)
        from PySide6.QtCore import QProcessEnvironment
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self.proses.setProcessEnvironment(env)
        if getattr(sys, "frozen", False):
            prog, arg = str(paths.EXE_UTAMA), ["--md", str(f_tugas)]
        else:
            prog, arg = sys.executable, ["-m", "virmodock", "--md", str(f_tugas)]
            self.proses.setWorkingDirectory(str(paths.AKAR))
        self.t0 = time.time()
        self.proses.start(prog, arg)
        self.l_status.setText("Menyiapkan OpenMM…" if self.run["mode"] != "uji" else "Mengukur kecepatan laptop…")
        self.jw.log.tulis(f"MD/MM-GBSA dimulai: {self.run['id']} ({self.run['mode']})")
        self._tombol()

    def _baca(self):
        self._buf += bytes(self.proses.readAllStandardOutput()).decode("utf-8", "replace")
        *baris, self._buf = self._buf.split("\n")
        for b in baris:
            b = b.rstrip("\r")
            if b.startswith("PROGRES "):
                _, p, *t = b.split(" ", 2)
                try:
                    self.prog.setValue(int(float(p) * 10))
                except ValueError:
                    pass
                self.l_status.setText(t[0] if t else "")
            elif b.startswith("LOG "):
                self.log.appendPlainText(b[4:])
            elif b.strip() and "Warning" not in b and "warn(" not in b:
                self.log.appendPlainText(b)

    def _akhir(self, kode, _status):
        self.proses = None
        pr = self.jw.proyek
        folder = pr.p(self.run["folder"])
        f = folder / "hasil.json"
        h = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        if self.run["mode"] == "uji":
            L = (h.get("ligan") or [{}])[0]
            if L.get("uji_implisit") and L.get("uji_eksplisit"):
                try:
                    semua = json.loads(paths.settings().value("md/kecepatan", "{}") or "{}")
                except (TypeError, ValueError):
                    semua = {}
                semua[self._kunci_kecepatan()] = {
                    "platform": L["uji_implisit"]["platform"], "implisit": L["uji_implisit"]["ns_hari"],
                    "eksplisit": L["uji_eksplisit"]["ns_hari"], "atom_i": L["uji_implisit"]["atom"],
                    "atom_e": L["uji_eksplisit"]["atom"], "tanggal": datetime.now().isoformat(timespec="seconds")}
                paths.settings().setValue("md/kecepatan", json.dumps(semua))
                self.l_status.setText("Kecepatan laptop terukur.")
            else:
                self.l_status.setText(f"Uji kecepatan gagal: {L.get('galat') or f'kode {kode}'} - lihat tab Log.")
            self.run = next((r for r in reversed(pr.md) if r.get("status") in ("dijeda", "selesai")), None)
            self._muat_kecepatan()
            self._tombol()
            return
        if kode == 3 or h.get("dijeda"):
            self.run["status"] = "dijeda"
            self.l_status.setText("Dijeda - checkpoint tersimpan. Klik Lanjutkan kapan saja (juga setelah aplikasi "
                                  "dibuka ulang).")
        elif any(x.get("selesai") for x in h.get("ligan", [])):
            self.run["status"] = "selesai"
            gagal = [x for x in h["ligan"] if x.get("galat")]
            self.l_status.setText(f"Selesai dalam {(time.time() - self.t0) / 60:.1f} menit"
                                  + (f"; {len(gagal)} ligan gagal (lihat Log)" if gagal else "") + ".")
            self.selesai.emit(h, dict(self.run))
            self._tampil_hasil(h, folder)
            self._segarkan_mmgbsa()
        else:
            self.run["status"] = "gagal"
            g = next((x.get("galat") for x in h.get("ligan", []) if x.get("galat")), None)
            self.l_status.setText(f"Gagal: {g or f'proses berakhir dengan kode {kode}'} - lihat tab Log.")
            self.tab.setCurrentWidget(self.log)
        self._simpan_run()
        self.jw.log.tulis(f"MD/MM-GBSA {self.run['id']}: {self.run['status']}")
        self._tombol()

    def _simpan_run(self):
        pr = self.jw.proyek
        if not pr or not self.run or self.run.get("mode") == "uji":
            return
        pr.md = [r for r in pr.md if r.get("id") != self.run["id"]] + [dict(self.run)]
        self.jw.minta_simpan()

    def proses_berjalan(self):
        return self.proses is not None

    def hentikan_untuk_keluar(self, tunggu_ms=20000):
        """Dipanggil saat aplikasi ditutup: jeda dengan checkpoint (MD) atau hentikan (lainnya)."""
        if not self.proses:
            return
        if self.run and self.run.get("mode") == "md":
            self.jeda()
            if self.proses.waitForFinished(tunggu_ms):
                return
        self.proses.kill()
        self.proses.waitForFinished(3000)

    # ------------------------------------------------------------- hasil
    def _tampil_hasil(self, h, folder):
        self.hasil, self.folder_hasil = h, Path(folder)
        L = [x for x in h.get("ligan", []) if x.get("selesai")]
        self.t_hasil.setRowCount(0)
        for x in L:
            r = self.t_hasil.rowCount()
            self.t_hasil.insertRow(r)
            mn, md_ = x.get("mmgbsa_min") or {}, x.get("mmgbsa") or {}
            tr = x.get("trajektori") or {}
            rm = tr.get("rmsd_ligan") or []
            nilai = [x["nama"], x.get("energi_docking"), mn.get("dG"), md_.get("dG"), md_.get("sd"),
                     (md_ or mn).get("vdw"), ((md_ or mn).get("elek") or 0) + ((md_ or mn).get("gb") or 0) if (md_ or mn) else None,
                     sum(rm) / len(rm) if rm else None]
            for c, v in enumerate(nilai):
                t = v if isinstance(v, str) else ("" if v is None else id_angka(f"{v:.2f}"))
                it = QTableWidgetItem(t)
                if c:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    it.setData(Qt.UserRole, v)
                self.t_hasil.setItem(r, c, it)
            if rm and sum(rm) / len(rm) > 3.0:
                self.t_hasil.item(r, 7).setForeground(kit.warna("bad"))
                self.t_hasil.item(r, 7).setToolTip("RMSD rerata > 3 Å: pose tidak stabil selama MD")
        self.t_hasil.resizeColumnsToContents()
        if L:
            self.t_hasil.setCurrentCell(0, 0)
            self._grafik_ligan(0)
        self._tombol()

    def _ligan_hasil(self, r=None):
        L = [x for x in (self.hasil or {}).get("ligan", []) if x.get("selesai")]
        r = self.t_hasil.currentRow() if r is None else r
        return L[r] if 0 <= r < len(L) else None

    def _segarkan_stabilitas(self):
        x = self._ligan_hasil()
        if not x:
            return
        g = getattr(self.jw, "mode", "terang") == "gelap"
        kunci = self.cb_metrik_stab.currentData() or "rmsd"
        svg = self._svg(kunci, x, g)
        self.k["stabilitas"].latar = QColor("#14171c" if g else "#ffffff")
        self.k["stabilitas"].set_svg(svg)

    def _svg(self, kunci, x, gelap=False):
        tr = x.get("trajektori") or {}
        an = x.get("analisis") or {}

        dt = (self.hasil.get("opsi") or {}).get("interval_ps", 10) / 1000.0

        if kunci == "rmsd":
            n = len(tr.get("rmsd_ligan") or [])
            t = [(i + 1) * dt for i in range(n)]
            seri = [("Ligan (berat)", t, tr.get("rmsd_ligan") or []),
                    ("Protein Cα", t, tr.get("rmsd_ca") or [])]
            return grafik.garis(seri, "Waktu (ns)", "RMSD (Å)", f"RMSD - {x['nama']}", gelap=gelap, y_nol=True,
                                catatan="Superposisi pada Cα protein frame pertama produksi; RMSD > 3 Å = pose bergeser")
        if kunci == "rmsf":
            v = tr.get("rmsf") or []
            return grafik.garis([("Cα", list(range(1, len(v) + 1)), v)], "Residu (urutan)", "RMSF (Å)",
                                f"RMSF Cα - {x['nama']}", gelap=gelap, y_nol=True,
                                catatan=(f"Residu 1 = {tr['residu'][0]}, terakhir = {tr['residu'][-1]}" if tr.get("residu") else ""))
        if kunci == "rg":
            rg_list = an.get("rg") or []
            t = [(i + 1) * dt for i in range(len(rg_list))]
            return grafik.garis([("Radius Girasi (Rg)", t, rg_list)], "Waktu (ns)", "Rg (Å)",
                                f"Radius Girasi Protein - {x['nama']}", gelap=gelap, y_nol=False,
                                catatan="Ukuran kekompakan lipatan protein selama simulasi")
        if kunci == "sasa":
            sasa_info = an.get("sasa") or {}
            prot = sasa_info.get("protein") or []
            terkubur = sasa_info.get("terkubur") or []
            n_pt = max(len(prot), len(terkubur))
            step_stride = (len(tr.get("rmsd_ligan") or [0]) / float(n_pt)) if n_pt else 1.0
            t = [(i + 1) * step_stride * dt for i in range(n_pt)]
            seri = []
            if prot:
                seri.append(("SASA Protein", t[:len(prot)], prot))
            if terkubur:
                seri.append(("ΔSASA Terkubur", t[:len(terkubur)], terkubur))
            return grafik.garis(seri, "Waktu (ns)", "SASA (Å²)", f"SASA - {x['nama']}", gelap=gelap, y_nol=False,
                                catatan="Luas permukaan terakses pelarut (rdFreeSASA / Shrake–Rupley)")
        if kunci == "energi":
            e = x.get("mmgbsa_frame") or []
            acuan = [(x["mmgbsa"]["dG"], f"rerata {grafik.fmt(x['mmgbsa']['dG'])}")] if x.get("mmgbsa") else None
            return grafik.garis([("ΔG MM/GBSA", [f["t_ns"] for f in e], [f["dG"] for f in e])], "Waktu (ns)",
                                "ΔG MM/GBSA (kcal/mol)", f"MM/GBSA per frame - {x['nama']}", gelap=gelap, acuan=acuan,
                                catatan="OBC2 (igb 5), satu-trajektori, tanpa entropi")
        return ""

    def _grafik_ligan(self, r):
        import numpy as np
        from ..core import md_analisis
        x = self._ligan_hasil(r)
        if not x:
            return
        g = getattr(self.jw, "mode", "terang") == "gelap"
        dt = (self.hasil.get("opsi") or {}).get("interval_ps", 10) / 1000.0

        tr = x.get("trajektori") or {}
        an = x.get("analisis") or {}
        rm_lig = tr.get("rmsd_ligan") or []
        rm_ca = tr.get("rmsd_ca") or []

        # 1. Baris Kartu & Lencana Konvergensi
        if rm_lig:
            rm_lig_2 = rm_lig[len(rm_lig) // 2:] if len(rm_lig) > 1 else rm_lig
            m_lig, s_lig = float(np.mean(rm_lig_2)), float(np.std(rm_lig_2))
            self.k_rmsd_lig.isi(f"{kit.f(m_lig)} ± {kit.f(s_lig, satuan='Å')}", "paruh kedua")
        else:
            self.k_rmsd_lig.isi("–", "paruh kedua")

        if rm_ca:
            rm_ca_2 = rm_ca[len(rm_ca) // 2:] if len(rm_ca) > 1 else rm_ca
            m_ca, s_ca = float(np.mean(rm_ca_2)), float(np.std(rm_ca_2))
            self.k_rmsd_ca.isi(f"{kit.f(m_ca)} ± {kit.f(s_ca, satuan='Å')}", "paruh kedua")
        else:
            self.k_rmsd_ca.isi("–", "paruh kedua")

        rg_list = an.get("rg") or []
        if rg_list:
            rg_2 = rg_list[len(rg_list) // 2:] if len(rg_list) > 1 else rg_list
            m_rg, s_rg = float(np.mean(rg_2)), float(np.std(rg_2))
            self.k_rg.isi(f"{kit.f(m_rg)} ± {kit.f(s_rg, satuan='Å')}", "paruh kedua")
        else:
            self.k_rg.isi("–", "paruh kedua")

        konv = an.get("konvergensi") or {}
        hb_list = an.get("hb") or []
        if hb_list:
            m_hb = konv.get("hb_rerata", float(np.mean(hb_list)))
            s_hb = konv.get("hb_gs", float(np.std(hb_list)))
            self.k_hb.isi(f"{kit.f(m_hb, 1)} ± {kit.f(s_hb, 1)}", "blok rata-rata")
        else:
            self.k_hb.isi("–", "blok rata-rata")

        mm = x.get("mmgbsa") or {}
        if mm.get("dG") is not None:
            self.k_dg.isi(f"{kit.f(mm['dG'])} ± {kit.f(mm.get('sd', 0.0))}", "kcal/mol")
        else:
            self.k_dg.isi("–", "kcal/mol")

        n_rep = len(x.get("replika") or []) or 1
        ns = (x.get("md") or {}).get("ns") or len(rm_lig) * dt
        teks = (f"{n_rep} replika × {kit.f(ns, 1)} ns: kestabilan lokal pose, bukan afinitas."
                + (" Saran: ≥ 3 replika untuk publikasi." if n_rep < 3 else ""))
        for p in an.get("peringatan") or []:
            teks += f"\n• {p}"
        self.l_catatan_md.setText(teks)

        # Lencana status stabilitas
        if rm_lig:
            m_total = float(np.mean(rm_lig))
            if m_total > 3.0:
                kit.atur_nada(self.l_lencana_konv, "bad")
                self.l_lencana_konv.setText("Bergeser (> 3 Å)")
            elif len(rm_lig) > 10 and float(np.std(rm_lig_2)) < 0.6:
                kit.atur_nada(self.l_lencana_konv, "ok")
                self.l_lencana_konv.setText("Stabil")
            else:
                kit.atur_nada(self.l_lencana_konv, "warn")
                self.l_lencana_konv.setText("Belum konvergen")
        else:
            kit.atur_nada(self.l_lencana_konv, "info")
            self.l_lencana_konv.setText("Siap")

        # Tombol Analisis Lanjutan
        ada_v2 = an.get("versi") == 2
        self.b_analisis_lanjut.setEnabled(not ada_v2 and bool(x.get("trajektori")))
        self.b_analisis_lanjut.setText("Analisis v2 lengkap" if ada_v2 else "Hitung analisis lanjutan")

        # 2. Tab Stabilitas
        self._segarkan_stabilitas()

        # 3. Tab Interaksi
        self.t_inter.setRowCount(0)
        for k_, v in list((x.get("interaksi_frek") or {}).items())[:60]:
            r_ = self.t_inter.rowCount()
            self.t_inter.insertRow(r_)
            p_res, p_jenis = (k_.split("|", 1) + [""])[:2]
            self.t_inter.setItem(r_, 0, QTableWidgetItem(p_res.strip()))
            jenis_it = QTableWidgetItem(NAMA_JENIS.get(p_jenis.strip(), p_jenis.strip()))
            jenis_it.setData(Qt.UserRole, p_jenis.strip())
            self.t_inter.setItem(r_, 1, jenis_it)
            it = QTableWidgetItem(f"{v * 100:.0f} %")
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.t_inter.setItem(r_, 2, it)

        # Barcode interaksi
        barcode_svg = md_analisis.svg_barcode_interaksi(an.get("barcode") or {},
                                                        dt_ps=(self.hasil.get("opsi") or {}).get("interval_ps", 10),
                                                        gelap=g)
        self.k["barcode"].latar = QColor("#14171c" if g else "#ffffff")
        self.k["barcode"].set_svg(barcode_svg)

        # 4. Tab PCA & FEL
        pca_d = an.get("pca") or {}
        var_rasio = pca_d.get("varians_rasio", [0.0, 0.0])
        pca_svg = md_analisis.svg_pca_sebar(pca_d,
                                            dt_ps=(self.hasil.get("opsi") or {}).get("interval_ps", 10),
                                            gelap=g)
        self.k["pca"].latar = QColor("#14171c" if g else "#ffffff")
        self.k["pca"].set_svg(pca_svg)

        fel_d = an.get("fel") or {}
        fel_svg = md_analisis.svg_fel_2d(fel_d,
                                         var_pc1=var_rasio[0] if len(var_rasio) > 0 else None,
                                         var_pc2=var_rasio[1] if len(var_rasio) > 1 else None,
                                         gelap=g)
        self.k["fel"].latar = QColor("#14171c" if g else "#ffffff")
        self.k["fel"].set_svg(fel_svg)

        # 5. Tab Klaster
        self.t_klaster.setRowCount(0)
        klaster_list = an.get("klaster") or []
        for c_idx, c_info in enumerate(klaster_list):
            r_c = self.t_klaster.rowCount()
            self.t_klaster.insertRow(r_c)
            self.t_klaster.setItem(r_c, 0, QTableWidgetItem(f"Klaster {c_idx + 1}"))
            self.t_klaster.setItem(r_c, 1, QTableWidgetItem(f"{c_info.get('ukuran_persen', 0.0):.1f} %"))
            self.t_klaster.setItem(r_c, 2, QTableWidgetItem(str(c_info.get("ukuran", 0))))
            self.t_klaster.setItem(r_c, 3, QTableWidgetItem(f"Frame {c_info.get('medoid', 0) + 1}"))
        if klaster_list:
            self.t_klaster.selectRow(0)

        # 6. Tab Replika
        self.t_replika.setRowCount(0)
        daftar_rep = x.get("replika") or (self.hasil.get("replika") if self.hasil else None) or [x]
        seri_rep = []
        for rep in daftar_rep:
            r_idx_row = self.t_replika.rowCount()
            self.t_replika.insertRow(r_idx_row)
            rep_no = rep.get("replika", r_idx_row + 1)
            self.t_replika.setItem(r_idx_row, 0, QTableWidgetItem(f"Replika {rep_no}"))
            self.t_replika.setItem(r_idx_row, 1, QTableWidgetItem(str(rep.get("seed", "-"))))
            r_tr = rep.get("trajektori") or {}
            r_an = rep.get("analisis") or {}
            r_rm = r_tr.get("rmsd_ligan") or []
            r_ca = r_tr.get("rmsd_ca") or []
            r_rg = r_an.get("rg") or []
            r_dg = (rep.get("mmgbsa") or {}).get("dG")

            self.t_replika.setItem(r_idx_row, 2, QTableWidgetItem(f"{np.mean(r_rm):.2f}" if r_rm else "-"))
            self.t_replika.setItem(r_idx_row, 3, QTableWidgetItem(f"{np.mean(r_ca):.2f}" if r_ca else "-"))
            self.t_replika.setItem(r_idx_row, 4, QTableWidgetItem(f"{np.mean(r_rg):.2f}" if r_rg else "-"))
            self.t_replika.setItem(r_idx_row, 5, QTableWidgetItem(f"{r_dg:.2f}" if r_dg is not None else "-"))

            if r_rm:
                t_rep = [(j + 1) * dt for j in range(len(r_rm))]
                seri_rep.append((f"Replika {rep_no}", t_rep, r_rm))

        agregat = self.hasil.get("replika_agregat") or x.get("replika_agregat") or {}
        if agregat:
            m_l, s_l = agregat.get("rmsd_ligan", [0, 0])
            m_c, s_c = agregat.get("rmsd_ca", [0, 0])
            m_g, s_g = agregat.get("rg", [0, 0])
            m_d, s_d = agregat.get("mmgbsa_dG", [0, 0])
            self.l_rep_agregat.setText(f"<b>Rata-rata ± SD:</b> RMSD ligan {kit.f(m_l)} ± {kit.f(s_l)} Å · "
                                      f"RMSD Cα {kit.f(m_c)} ± {kit.f(s_c)} Å · Rg {kit.f(m_g)} ± {kit.f(s_g)} Å · "
                                      f"ΔG MM/GBSA {kit.f(m_d)} ± {kit.f(s_d)} kcal/mol")
        else:
            self.l_rep_agregat.setText("")

        svg_rep = grafik.garis(seri_rep, "Waktu (ns)", "RMSD Ligan (Å)", "RMSD Multi-Replika", gelap=g, y_nol=True)
        self.k["replika"].latar = QColor("#14171c" if g else "#ffffff")
        self.k["replika"].set_svg(svg_rep)

    def _sorot_residu_interaksi(self):
        r = self.t_inter.currentRow()
        if r < 0:
            return
        it = self.t_inter.item(r, 0)
        if not it:
            return
        teks_res = it.text().strip()
        # Sorot residu di 3D viewer jika tersedia
        try:
            tokens = teks_res.split()
            if len(tokens) >= 2:
                resi = int("".join(c for c in tokens[1] if c.isdigit()))
                self.jw.viewer.js("pilihResidu", resi)
        except Exception:
            pass

    def _tampilkan_medoid(self):
        x = self._ligan_hasil()
        if not x:
            return
        kl_idx = self.t_klaster.currentRow()
        an = x.get("analisis") or {}
        kl_list = an.get("klaster") or []
        if kl_idx < 0 or kl_idx >= len(kl_list):
            QMessageBox.information(self, "Klaster Medoid", "Pilih salah satu klaster dari tabel terlebih dahulu.")
            return

        kl = kl_list[kl_idx]
        pdb_path = kl.get("pdb_medoid")
        if not pdb_path or not Path(pdb_path).exists():
            # Ekspor terlebih dahulu
            sub = self.folder_hasil / f"{self._ligan_folder_nama(x)}"
            from ..core import md_analisis
            top_f = sub / "topologi.pdb"
            dcd_f = sub / "trajektori_terlarut.dcd"
            if top_f.exists() and dcd_f.exists():
                from openmm import app
                top = app.PDBFile(str(top_f)).topology
                frames, _ = md_analisis.baca_dcd(dcd_f)
                hasil_pdb = md_analisis.ekspor_pdb_medoid(top, frames, kl_list, sub)
                pdb_path = hasil_pdb[kl_idx] if kl_idx < len(hasil_pdb) else None

        if pdb_path and Path(pdb_path).exists():
            self.jw.impor([str(pdb_path)])
            self.l_status.setText(f"Medoid klaster {kl_idx + 1} dimuat ke viewer 3D.")
        else:
            QMessageBox.warning(self, "Klaster Medoid", "Berkas PDB medoid belum tersedia. Jalankan atau hitung ulang analisis.")

    def _pakai_sebagai_ensemble(self):
        x = self._ligan_hasil()
        if not x:
            return
        kl_idx = self.t_klaster.currentRow()
        an = x.get("analisis") or {}
        kl_list = an.get("klaster") or []
        if kl_idx < 0 or kl_idx >= len(kl_list):
            QMessageBox.information(self, "Reseptor Ensemble", "Pilih salah satu klaster dari tabel terlebih dahulu.")
            return

        kl = kl_list[kl_idx]
        pdb_path = kl.get("pdb_medoid")
        if not pdb_path or not Path(pdb_path).exists():
            self._tampilkan_medoid()
            pdb_path = kl.get("pdb_medoid")

        if pdb_path and Path(pdb_path).exists():
            # Tambahkan sebagai reseptor ensemble di proyek
            pr = self.jw.proyek
            if pr:
                if not hasattr(pr, "ensemble_reseptor"):
                    pr.ensemble_reseptor = []
                entri = {
                    "nama": f"Ensemble_{x['nama']}_Klaster_{kl_idx + 1}",
                    "pdb": str(pr.rel(Path(pdb_path))),
                    "ligan_sumber": x["nama"],
                    "klaster": kl_idx + 1,
                    "ukuran_persen": kl.get("ukuran_persen", 0.0),
                }
                pr.ensemble_reseptor.append(entri)
                self.jw.impor([str(pdb_path)])
                self.jw.minta_simpan()
                QMessageBox.information(self, "Reseptor Ensemble",
                                        f"Struktur medoid klaster {kl_idx + 1} ({Path(pdb_path).name}) "
                                        f"berhasil didaftarkan sebagai reseptor ensemble dalam proyek.")
        else:
            QMessageBox.warning(self, "Reseptor Ensemble", "Gagal memuat berkas PDB medoid.")

    def _ligan_folder_nama(self, x):
        from ..core.md import _aman
        return f"{_aman(x['nama'])}_{x.get('peringkat', 1)}"


    def _mol_ligan_md(self, x):
        """Pose ligan ber-ikatan untuk analisis ulang: dibangun dari tugas.json persis seperti saat MD berjalan.

        Tanpa molekul ini ligan hanya berupa atom lepas tanpa ikatan, sehingga donor/akseptor ikatan hidrogen
        tidak dikenali dan yang terdeteksi tinggal kontak hidrofobik.
        """
        from ..core import md as mdmod
        try:
            tugas = json.loads((self.folder_hasil / "tugas.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        it = next((i for i in tugas.get("ligan", []) if i.get("lid") == x.get("lid") and i.get("job") == x.get("job")
                   and i.get("peringkat", 1) == x.get("peringkat", 1)), None)
        if not it:
            return None
        it = dict(it)
        asal = Path(it.get("pdbqt_masukan") or "")
        pr = self.jw.proyek
        if asal.name and not asal.exists() and pr:  # proyek dipindah: cari ulang relatif terhadap folder proyek
            calon = pr.p(f"ligan/pdbqt/{asal.name}")
            if calon.exists():
                it["pdbqt_masukan"] = str(calon)
        try:
            return mdmod._mol_pose(it)
        except Exception:  # berkas pose hilang/rusak: analisis tetap jalan, ikatan H ditandai tidak dinilai
            return None

    def _hitung_analisis_lanjut_klik(self):
        x = self._ligan_hasil()
        if not x:
            return
        sub = self.folder_hasil / f"{x['nama']}_{x.get('peringkat', 1)}"
        if not sub.exists():
            QMessageBox.warning(self, "Analisis Lanjutan", f"Folder simulasi tidak ditemukan: {sub}")
            return

        try:
            from ..core import md_analisis
            self.l_status.setText(f"Menghitung analisis lanjutan untuk {x['nama']}…")
            dt_ps = (self.hasil.get("opsi") or {}).get("interval_ps", 10.0)
            mol = self._mol_ligan_md(x)
            hasil_v2 = md_analisis.hitung_analisis_lanjutan(sub, dt_ps=dt_ps, mol_rdkit=mol)
            if mol is None:
                hasil_v2.setdefault("peringatan", []).append(
                    "Struktur ligan dari tugas MD tidak ditemukan: ikatan hidrogen dan interaksi polar tidak dinilai; "
                    "hanya kontak hidrofobik yang dapat dihitung.")
            x["analisis"] = hasil_v2
            x["interaksi_frek"] = hasil_v2.get("interaksi_frek", x.get("interaksi_frek", {}))

            # Simpan perubahan ke hasil.json & proyek.md
            f_hasil = self.folder_hasil / "hasil.json"
            f_hasil.write_text(json.dumps(self.hasil, indent=1, ensure_ascii=False), encoding="utf-8")
            self._simpan_run()
            self._grafik_ligan(self.t_hasil.currentRow())
            self.l_status.setText(f"Analisis lanjutan selesai untuk {x['nama']}.")
        except Exception as e:
            QMessageBox.warning(self, "Analisis Lanjutan Gagal", f"Gagal menghitung: {e}")

    def _svg_aktif(self):
        """Ambil teks SVG dari tab grafik yang sedang aktif."""
        w_tab = self.tab.currentWidget()
        x = self._ligan_hasil()
        if not x:
            return "", "Grafik"
        g = getattr(self.jw, "mode", "terang") == "gelap"

        if w_tab == self.tab.widget(1):  # Stabilitas
            kunci = self.cb_metrik_stab.currentData() or "rmsd"
            return self._svg(kunci, x, g), f"{kunci.upper()}_{x['nama']}"
        elif w_tab == self.tab.widget(2):  # Interaksi
            an = x.get("analisis") or {}
            from ..core import md_analisis
            return md_analisis.svg_barcode_interaksi(an.get("barcode") or {}, gelap=g), f"Barcode_{x['nama']}"
        elif w_tab == self.tab.widget(3):  # PCA & FEL
            an = x.get("analisis") or {}
            from ..core import md_analisis
            return md_analisis.svg_fel_2d(an.get("fel") or {}, gelap=g), f"FEL_{x['nama']}"
        elif w_tab == self.tab.widget(5):  # Replika
            return self.k["replika"]._svg if hasattr(self.k["replika"], "_svg") else "", f"Replika_{x['nama']}"
        else:
            return self._svg("rmsd", x, g), f"RMSD_{x['nama']}"

    def _kirim_ke_komposer(self):
        svg_teks, judul = self._svg_aktif()
        if not svg_teks:
            self.l_status.setText("Tidak ada grafik aktif untuk dikirim ke komposer.")
            return
        if not getattr(self.jw, "komposer", None):
            self.jw.buka_komposer()
        self.jw.komposer.tambah({"nama": judul, "jenis": "svg", "isi": svg_teks, "w": 760, "h": 480})
        self.l_status.setText(f"“{judul}” ditambahkan ke Komposer Figur.")

    def _simpan_grafik(self):
        svg_teks, judul = self._svg_aktif()
        if not svg_teks:
            self.l_status.setText("Pilih grafik di tab Stabilitas, Interaksi, PCA & FEL, atau Replika.")
            return
        f = self.jw._path("Simpan grafik", f"{judul}.svg", "SVG (*.svg);;PDF (*.pdf);;PNG (*.png);;TIFF (*.tif)")
        if f:
            ext = f.lower().rsplit(".", 1)[-1]
            self.jw._simpan_svg(svg_teks, f, {"pdf": "pdf", "png": "png", "tif": "tif", "tiff": "tif"}.get(ext, "svg"),
                                760, 480, mm=160, dpi=600)

    def _ekspor_csv(self):
        x = self._ligan_hasil()
        if not x:
            return
        f = self.jw._path("Ekspor CSV", f"md_{x['nama']}_data.csv", "CSV (*.csv)")
        if not f:
            return
        tr = x.get("trajektori") or {}
        an = x.get("analisis") or {}
        dt = (self.hasil.get("opsi") or {}).get("interval_ps", 10) / 1000.0
        rm_l = tr.get("rmsd_ligan") or []
        rm_c = tr.get("rmsd_ca") or []
        rg = an.get("rg") or []
        hb = an.get("hb") or []
        n = max(len(rm_l), len(rm_c), len(rg), len(hb))

        lines = ["frame,waktu_ns,rmsd_ligan_A,rmsd_ca_A,rg_A,ikatan_h"]
        for i in range(n):
            t_ns = (i + 1) * dt
            v_rl = f"{rm_l[i]:.3f}" if i < len(rm_l) else ""
            v_rc = f"{rm_c[i]:.3f}" if i < len(rm_c) else ""
            v_rg = f"{rg[i]:.3f}" if i < len(rg) else ""
            v_hb = f"{hb[i]}" if i < len(hb) else ""
            lines.append(f"{i + 1},{t_ns:.3f},{v_rl},{v_rc},{v_rg},{v_hb}")
        Path(f).write_text("\n".join(lines), encoding="utf-8")
        self.l_status.setText(f"Data diekspor ke {Path(f).name}.")

    def _buka_folder(self):
        if self.run:
            os.startfile(str(self.jw.proyek.p(self.run["folder"])))

    def closeEvent(self, e):
        e.accept()

