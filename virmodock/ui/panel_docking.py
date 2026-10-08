"""Panel Parameter Docking: mesin, perangkat, pencarian, grid box, preset."""
import math

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout,
                               QHBoxLayout, QInputDialog, QLabel, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from ..core import mesin as M
from ..core import paths
from .panels import judul_seksi

PRESET = {
    "Cepat": {"nrun": 10, "heuristik": True, "exhaustiveness": 8, "num_modes": 9, "energy_range": 3.0, "pop": 150,
              "nev": 250000},
    "Standar": {"nrun": 50, "heuristik": True, "exhaustiveness": 16, "num_modes": 9, "energy_range": 3.0, "pop": 150,
                "nev": 2500000},
    "Teliti": {"nrun": 100, "heuristik": True, "exhaustiveness": 32, "num_modes": 20, "energy_range": 4.0,
               "pop": 300, "nev": 2500000},
}


def _spin(lo, hi, nilai, langkah=1, desimal=None, akhiran=""):
    if desimal is None:
        s = QSpinBox()
    else:
        s = QDoubleSpinBox()
        s.setDecimals(desimal)
    s.setRange(lo, hi)
    s.setSingleStep(langkah)
    s.setValue(nilai)
    if akhiran:
        s.setSuffix(akhiran)
    s.setAlignment(Qt.AlignRight)
    s.setKeyboardTracking(False)
    s.setMinimumWidth(56)  # abaikan lebar dari rentang besar agar panel muat di dock sempit
    return s


class PanelDocking(QWidget):
    parameterBerubah = Signal(dict)
    kotakBerubah = Signal(dict)
    aksiKotak = Signal(str)          # ligan_asli | residu | blind | sesuai
    tampilKotak = Signal(bool)
    jalankan = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._diam = False
        self.warna_warn = "#c98a12"
        self.st = paths.settings()
        luar = QVBoxLayout(self)
        luar.setContentsMargins(0, 0, 0, 0)
        luar.setSpacing(0)
        isi = QWidget()
        lay = QVBoxLayout(isi)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(0)

        # ---------------- ringkasan
        lay.addWidget(judul_seksi("Masukan"))
        f0 = QFormLayout()
        f0.setContentsMargins(10, 6, 10, 6)
        f0.setHorizontalSpacing(12)
        self.l_rec = QLabel("belum disiapkan")
        self.l_rec.setObjectName("mono")
        self.l_lig = QLabel("0")
        self.l_lig.setObjectName("mono")
        f0.addRow(self._m("Reseptor"), self.l_rec)
        f0.addRow(self._m("Ligan siap"), self.l_lig)
        lay.addLayout(f0)

        # ---------------- mesin & perangkat
        lay.addWidget(judul_seksi("Mesin"))
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 6, 10, 6)
        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.grp_mesin = QButtonGroup(self)
        self.btn_mesin = {}
        for i, (k, t) in enumerate((("adgpu", "AD-GPU"), ("vina", "Vina"), ("ad4", "AD4"))):
            b = QPushButton(t)
            b.setMinimumWidth(40)
            b.setToolTip(M.MESIN[k])
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            if not M.tersedia(k):
                b.setEnabled(False)
                b.setToolTip(f"{M.PROGRAM[k]} tidak ditemukan di folder bin")
            self.grp_mesin.addButton(b, i)
            self.btn_mesin[k] = b
            seg.addWidget(b)
        self.grp_mesin.idToggled.connect(lambda i, on: on and self._mesin_ganti())
        v.addLayout(seg)
        fp = QFormLayout()
        self.cmb_alat = QComboBox()
        self.cmb_alat.currentIndexChanged.connect(self._ubah)
        fp.addRow(self._m("Perangkat"), self.cmb_alat)
        hp = QHBoxLayout()
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems(list(PRESET) + list((self.st.value("preset_kustom", {}) or {}).keys()))
        self.cmb_preset.setCurrentText("Standar")
        self.cmb_preset.setMinimumWidth(60)
        b_terap = QToolButton()
        b_terap.setText("Terapkan")
        b_terap.clicked.connect(lambda: self.terapkan_preset(self.cmb_preset.currentText()))
        b_simpan = QToolButton()
        b_simpan.setText("Simpan…")
        b_simpan.setToolTip("Simpan parameter saat ini sebagai preset kustom")
        b_simpan.clicked.connect(self._simpan_preset)
        hp.addWidget(self.cmb_preset, 1)
        hp.addWidget(b_terap)
        hp.addWidget(b_simpan)
        fp.addRow(self._m("Preset"), hp)
        v.addLayout(fp)
        self.l_mesin = QLabel()
        self.l_mesin.setObjectName("muted")
        self.l_mesin.setWordWrap(True)
        v.addWidget(self.l_mesin)
        lay.addWidget(w)

        # ---------------- pencarian
        lay.addWidget(judul_seksi("Pencarian"))
        self.stack = QStackedWidget()
        # AD-GPU
        a = QWidget()
        fa = QFormLayout(a)
        fa.setContentsMargins(10, 6, 10, 6)
        self.sp_nrun = _spin(1, 1000, 50)
        self.c_heur = QCheckBox("Heuristik jumlah evaluasi (disarankan)")
        self.c_heur.setChecked(True)
        self.sp_nev = _spin(10000, 100000000, 2500000, 250000)
        self.c_heur.toggled.connect(lambda on: self.sp_nev.setEnabled(not on))
        self.sp_nev.setEnabled(False)
        fa.addRow(self._m("Jumlah run"), self.sp_nrun)
        fa.addRow(self.c_heur)
        fa.addRow(self._m("Maks. evaluasi"), self.sp_nev)
        self.stack.addWidget(a)
        # Vina
        b = QWidget()
        fb = QFormLayout(b)
        fb.setContentsMargins(10, 6, 10, 6)
        self.sp_exh = _spin(1, 128, 8)
        self.sp_modes = _spin(1, 50, 9)
        self.sp_erange = _spin(0.5, 20, 3.0, 0.5, 1, " kcal/mol")
        self.sp_cpu = _spin(0, 256, 0)
        self.sp_cpu.setSpecialValueText("otomatis")
        fb.addRow(self._m("Exhaustiveness"), self.sp_exh)
        fb.addRow(self._m("Jumlah pose"), self.sp_modes)
        fb.addRow(self._m("Rentang energi"), self.sp_erange)
        fb.addRow(self._m("Thread CPU"), self.sp_cpu)
        self.stack.addWidget(b)
        # AD4
        c = QWidget()
        fc = QFormLayout(c)
        fc.setContentsMargins(10, 6, 10, 6)
        self.sp_garun = _spin(1, 1000, 50)
        self.sp_pop = _spin(50, 1000, 150, 10)
        self.sp_evals = _spin(10000, 100000000, 2500000, 250000)
        fc.addRow(self._m("ga_run"), self.sp_garun)
        fc.addRow(self._m("ga_pop_size"), self.sp_pop)
        fc.addRow(self._m("ga_num_evals"), self.sp_evals)
        self.stack.addWidget(c)
        lay.addWidget(self.stack)
        fs = QFormLayout()
        fs.setContentsMargins(10, 0, 10, 6)
        self.sp_seed = _spin(0, 2147483647, 42)
        self.sp_seed.setSpecialValueText("acak")
        self.sp_seed.setToolTip("Seed tetap = hasil dapat diulang. 0 = acak.")
        fs.addRow(self._m("Seed"), self.sp_seed)
        lay.addLayout(fs)
        for s in (self.sp_nrun, self.sp_nev, self.sp_exh, self.sp_modes, self.sp_erange, self.sp_cpu, self.sp_garun,
                  self.sp_pop, self.sp_evals, self.sp_seed):
            s.valueChanged.connect(self._ubah)
        self.c_heur.toggled.connect(self._ubah)

        # ---------------- grid box
        lay.addWidget(judul_seksi("Grid box"))
        gb = QWidget()
        g = QGridLayout(gb)
        g.setContentsMargins(10, 6, 10, 6)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(4)
        for j, t in enumerate(("", "X", "Y", "Z")):
            l = self._m(t)
            l.setAlignment(Qt.AlignCenter)
            g.addWidget(l, 0, j)
        self.sp_pusat, self.sp_ukuran = [], []
        g.addWidget(self._m("Pusat (Å)"), 1, 0)
        g.addWidget(self._m("Ukuran (Å)"), 2, 0)
        for j in range(3):
            p = _spin(-9999, 9999, 0.0, 0.5, 3)
            u = _spin(1.0, 200.0, 22.5, 1.0, 2)
            p.valueChanged.connect(self._kotak_ubah)
            u.valueChanged.connect(self._kotak_ubah)
            g.addWidget(p, 1, j + 1)
            g.addWidget(u, 2, j + 1)
            self.sp_pusat.append(p)
            self.sp_ukuran.append(u)
        g.addWidget(self._m("Spasi (Å)"), 3, 0)
        self.sp_spasi = _spin(0.2, 1.0, 0.375, 0.025, 3)
        self.sp_spasi.valueChanged.connect(self._kotak_ubah)
        g.addWidget(self.sp_spasi, 3, 1)
        self.l_npts = QLabel("")
        self.l_npts.setObjectName("mono")
        g.addWidget(self.l_npts, 3, 2, 1, 2)
        lay.addWidget(gb)
        self.l_kotak = QLabel("")
        self.l_kotak.setWordWrap(True)
        self.l_kotak.setContentsMargins(10, 0, 10, 4)
        lay.addWidget(self.l_kotak)
        bk = QGridLayout()
        bk.setContentsMargins(10, 2, 10, 6)
        bk.setSpacing(4)
        for i, (k, t, tip) in enumerate((
                ("ligan_asli", "Pusat ke ligan asli", "Pusatkan pada ligan kristal (ukuran = ligan + 10 Å, min 20 Å)"),
                ("residu", "Pusat ke residu terpilih", "Pilih residu di Hierarki atau klik atom di viewport"),
                ("sesuai", "Sesuaikan ke ligan +8 Å", "Ukuran = rentang ligan terpilih + 8 Å tiap sisi"),
                ("blind", "Seluruh protein (blind)", "Kotak menutupi seluruh protein"))):
            b = QPushButton(t)
            b.setToolTip(tip)
            b.setMinimumWidth(40)
            b.setStyleSheet("padding:4px 6px")
            b.clicked.connect(lambda _=False, k=k: self.aksiKotak.emit(k))
            bk.addWidget(b, i // 2, i % 2)
        lay.addLayout(bk)
        self.c_tampil = QCheckBox("Tampilkan grid box di viewport")
        self.c_tampil.setChecked(True)
        self.c_tampil.setContentsMargins(10, 0, 10, 0)
        self.c_tampil.toggled.connect(self.tampilKotak)
        h = QHBoxLayout()
        h.setContentsMargins(10, 0, 10, 0)
        h.addWidget(self.c_tampil)
        lay.addLayout(h)
        tip = QLabel("Di viewport: Shift + seret = geser kotak, Shift + gulir = ubah ukuran, "
                     "Alt + gulir = ubah satu sumbu (X/Y/Z dipilih dengan tombol X, Y, Z).")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        tip.setContentsMargins(10, 4, 10, 4)
        lay.addWidget(tip)

        lay.addSpacing(8)
        hr = QHBoxLayout()
        hr.setContentsMargins(10, 0, 10, 0)
        self.b_run = QPushButton("Jalankan docking")
        self.b_run.setObjectName("primary")
        self.b_run.clicked.connect(self.jalankan)
        hr.addWidget(self.b_run)
        lay.addLayout(hr)
        lay.addStretch(1)

        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QScrollArea.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setWidget(isi)
        luar.addWidget(sc)
        self.cmb_alat.setMinimumWidth(60)
        self.cmb_alat.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._t_kotak = QTimer(self)
        self._t_kotak.setSingleShot(True)
        self._t_kotak.setInterval(100)
        self._t_kotak.timeout.connect(lambda: self.kotakBerubah.emit(self.kotak()))
        self.btn_mesin["adgpu" if M.tersedia("adgpu") else "vina"].setChecked(True)
        self._info_kotak()

    def _m(self, t):
        l = QLabel(t)
        l.setObjectName("muted")
        return l

    # --------------------------------------------------------- parameter
    def mesin(self):
        return ["adgpu", "vina", "ad4"][max(0, self.grp_mesin.checkedId())]

    def _mesin_ganti(self):
        m = self.mesin()
        self._halaman(m)
        self.l_mesin.setText({
            "adgpu": "AutoDock-GPU (OpenCL): algoritma LGA + ADADELTA, sangat cepat di GPU. Butuh grid map (AutoGrid4).",
            "vina": "AutoDock Vina 1.2.7: CPU, tanpa grid map, cocok untuk ligan besar (> 32 torsi).",
            "ad4": "AutoDock4 klasik (LGA, CPU): lambat, untuk perbandingan dengan penelitian lama."}[m])
        self._ubah()

    def _halaman(self, m):
        self.stack.setCurrentIndex(["adgpu", "vina", "ad4"].index(m))
        for i in range(self.stack.count()):  # tinggi stack = halaman aktif saja
            self.stack.widget(i).setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred
                                               if i == self.stack.currentIndex() else QSizePolicy.Ignored)
        self.stack.adjustSize()

    def parameter(self):
        return {"mesin": self.mesin(), "perangkat": self.cmb_alat.currentData() or "cpu",
                "nrun": self.sp_nrun.value() if self.mesin() == "adgpu" else self.sp_garun.value(),
                "nev": self.sp_nev.value() if self.mesin() == "adgpu" else self.sp_evals.value(),
                "heuristik": self.c_heur.isChecked(), "exhaustiveness": self.sp_exh.value(),
                "num_modes": self.sp_modes.value(), "energy_range": self.sp_erange.value(),
                "cpu": self.sp_cpu.value(), "pop": self.sp_pop.value(), "seed": self.sp_seed.value(),
                "nrun_gpu": self.sp_nrun.value(), "nrun_ad4": self.sp_garun.value(),
                "nev_gpu": self.sp_nev.value(), "nev_ad4": self.sp_evals.value()}

    def set_parameter(self, d):
        if not d:
            return
        self._diam = True
        m = d.get("mesin")
        if m in self.btn_mesin and self.btn_mesin[m].isEnabled():
            self.btn_mesin[m].setChecked(True)
            self._halaman(m)
        for s, k in ((self.sp_nrun, "nrun_gpu"), (self.sp_garun, "nrun_ad4"), (self.sp_nev, "nev_gpu"),
                     (self.sp_evals, "nev_ad4"), (self.sp_exh, "exhaustiveness"), (self.sp_modes, "num_modes"),
                     (self.sp_erange, "energy_range"), (self.sp_cpu, "cpu"), (self.sp_pop, "pop"),
                     (self.sp_seed, "seed")):
            if k in d:
                s.setValue(d[k])
        if "heuristik" in d:
            self.c_heur.setChecked(bool(d["heuristik"]))
        i = self.cmb_alat.findData(d.get("perangkat"))
        if i >= 0:
            self.cmb_alat.setCurrentIndex(i)
        self._diam = False

    def terapkan_preset(self, nama):
        p = PRESET.get(nama) or (self.st.value("preset_kustom", {}) or {}).get(nama)
        if not p:
            return
        d = dict(p)
        d.setdefault("nrun_gpu", d.get("nrun"))
        d.setdefault("nrun_ad4", d.get("nrun"))
        d.setdefault("nev_ad4", d.get("nev"))
        d.pop("mesin", None)
        d.pop("perangkat", None)
        self.set_parameter(d)
        self._ubah()

    def _simpan_preset(self):
        nama, ok = QInputDialog.getText(self, "Simpan preset", "Nama preset:")
        if not ok or not nama.strip():
            return
        kustom = dict(self.st.value("preset_kustom", {}) or {})
        kustom[nama.strip()] = self.parameter()
        self.st.setValue("preset_kustom", kustom)
        if self.cmb_preset.findText(nama.strip()) < 0:
            self.cmb_preset.addItem(nama.strip())
        self.cmb_preset.setCurrentText(nama.strip())

    def set_perangkat(self, daftar, pilih=None):
        """daftar: [(teks, data, ikon)]"""
        self._diam = True
        self.cmb_alat.clear()
        for t, d, ik in daftar:
            self.cmb_alat.addItem(ik, t, d) if ik else self.cmb_alat.addItem(t, d)
        if pilih is not None:
            i = self.cmb_alat.findData(pilih)
            if i >= 0:
                self.cmb_alat.setCurrentIndex(i)
        self._diam = False

    def _ubah(self, *_):
        if not self._diam:
            self.parameterBerubah.emit(self.parameter())

    def set_ringkasan(self, reseptor, n_lig, n_peringatan=0):
        self.l_rec.setText(reseptor or "belum disiapkan")
        self.l_lig.setText(f"{n_lig}" + (f"  ({n_peringatan} dengan peringatan)" if n_peringatan else ""))

    # ------------------------------------------------------------- kotak
    def kotak(self):
        return {"pusat": [round(s.value(), 3) for s in self.sp_pusat],
                "ukuran": [round(s.value(), 2) for s in self.sp_ukuran], "spasi": round(self.sp_spasi.value(), 3)}

    def set_kotak(self, k):
        if not k or not k.get("pusat"):
            return
        self._diam = True
        for s, v in zip(self.sp_pusat, k["pusat"]):
            s.setValue(v)
        for s, v in zip(self.sp_ukuran, k["ukuran"]):
            s.setValue(v)
        self.sp_spasi.setValue(k.get("spasi", 0.375))
        self._diam = False
        self._info_kotak()

    def _kotak_ubah(self, *_):
        self._info_kotak()
        if not self._diam:
            self._t_kotak.start()

    def _info_kotak(self):
        k = M.Kotak(**self.kotak())
        n = k.npts()
        self.l_npts.setText(f"{n[0]}×{n[1]}×{n[2]} titik")
        pesan = []
        if k.terpotong():
            sp = max(u / 126 for u in k.ukuran)
            pesan.append(f"Melebihi 126 titik grid per sumbu: AutoGrid memotong kotak. "
                         f"Naikkan spasi ke ≥ {math.ceil(sp * 1000) / 1000:.3f} Å atau perkecil kotak.")
        if any(u > 30 for u in k.ukuran):
            pesan.append("Ukuran > 30 Å: pencarian Vina kurang efisien; tambah exhaustiveness.")
        self.l_kotak.setText("\n".join(pesan))
        self.l_kotak.setStyleSheet(f"color:{self.warna_warn}" if pesan else "")
        self.l_kotak.setVisible(bool(pesan))
