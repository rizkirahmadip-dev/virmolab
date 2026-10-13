"""Dialog Kemiripan & ruang kimia (Analisis › Kemiripan, ruang kimia, farmakofor…).

Tab: Peta ruang kimia (MDS Tanimoto / PCA deskriptor, warna klaster atau ΔG), Matriks kemiripan, Cari mirip
(acuan = ligan proyek atau SMILES), Klaster Butina, Farmakofor bersama (fitur 3D pose terbaik N ligan teratas).
"""
import csv

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..core import analisis, grafik, kemiripan as K
from ..core import ekspor as eksmod
from ..core import mesin as mesinmod
from ..core.laporan import id_angka
from . import kerja, theme
from . import kit
from .panel_interaksi import KanvasSvg


def _f(v, d=2):
    return id_angka(f"{v:.{d}f}")


def _sel(t, angka=None):
    it = QTableWidgetItem(t)
    if angka is not None:
        it.setData(Qt.UserRole, angka)
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


class DialogKemiripan(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Kemiripan, ruang kimia, dan farmakofor")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1220, 780)
        self.lig = []         # [{nama, kunci, mol, dg}]
        self.fps, self.m, self.klaster = [], None, []
        self.farma = []
        lay = QVBoxLayout(self)
        lay.addWidget(kit.judul(
            "Kemiripan, ruang kimia, dan farmakofor",
            "Bandingkan ligan proyek dengan sidik jari Tanimoto, klaster Butina, peta ruang kimia, dan fitur "
            "farmakofor."))
        bar = QHBoxLayout()
        self.c_fp = QComboBox()
        for k, t in K.SIDIK:
            self.c_fp.addItem(t, k)
        self.c_fp.setToolTip("Sidik jari struktur untuk Tanimoto. FCFP4/Gobbi = berbasis fitur farmakofor "
                             "(mendeteksi kemiripan fungsi walau kerangka berbeda)")
        self.s_amb = QDoubleSpinBox()
        self.s_amb.setRange(0.2, 0.95)
        self.s_amb.setSingleStep(0.05)
        self.s_amb.setValue(0.45)
        self.s_amb.setToolTip("Klaster Butina: ligan dalam satu klaster punya Tanimoto ≥ nilai ini ke pusat klaster")
        bar.addWidget(QLabel("Sidik jari"))
        bar.addWidget(self.c_fp)
        bar.addSpacing(12)
        bar.addWidget(QLabel("Ambang klaster"))
        bar.addWidget(self.s_amb)
        bar.addStretch(1)
        self.l_info = QLabel()
        self.l_info.setObjectName("muted")
        bar.addWidget(self.l_info)
        lay.addLayout(bar)
        self.tab = QTabWidget()
        lay.addWidget(self.tab, 1)
        self._tab_peta()
        self._tab_matriks()
        self._tab_mirip()
        self._tab_klaster()
        self._tab_farma()
        bawah = QHBoxLayout()
        cat = QLabel("Kemiripan struktur tidak menjamin kemiripan aktivitas (activity cliff). Tanimoto ≥ 0,85 (ECFP4) "
                     "biasanya dianggap sangat mirip; ambang bergantung jenis sidik jari.")
        cat.setObjectName("muted")
        cat.setWordWrap(True)
        bawah.addWidget(cat, 1)
        for t, fn in (("Salin grafik", lambda: self._grafik("salin")), ("Simpan grafik…", lambda: self._grafik("svg")),
                      ("Ekspor CSV…", self.ekspor_csv), ("Tutup", self.close)):
            b = QPushButton(t)
            b.clicked.connect(fn)
            bawah.addWidget(b)
        lay.addLayout(bawah)
        self.c_fp.currentIndexChanged.connect(self.hitung)
        self.s_amb.valueChanged.connect(self.hitung)
        self.muat()

    # ------------------------------------------------------------------ tab
    def _tab_peta(self):
        w = QWidget()
        v = QVBoxLayout(w)
        h = QHBoxLayout()
        self.c_peta = QComboBox()
        self.c_peta.addItem("MDS dari kemiripan sidik jari", "mds")
        self.c_peta.addItem("PCA deskriptor fisikokimia", "pca")
        self.c_warna = QComboBox()
        self.c_warna.addItem("Warna = klaster", "klaster")
        self.c_warna.addItem("Warna = ΔG terbaik", "dg")
        self.c_lbl = QCheckBox("Label")
        h.addWidget(self.c_peta)
        h.addWidget(self.c_warna)
        h.addWidget(self.c_lbl)
        h.addStretch(1)
        v.addLayout(h)
        self.k_peta = KanvasSvg()
        v.addWidget(self.k_peta, 1)
        for x in (self.c_peta, self.c_warna):
            x.currentIndexChanged.connect(self.gambar_peta)
        self.c_lbl.toggled.connect(self.gambar_peta)
        self.tab.addTab(w, "Peta ruang kimia")

    def _tab_matriks(self):
        w = QWidget()
        v = QVBoxLayout(w)
        h = QHBoxLayout()
        h.addWidget(QLabel("Tampilkan"))
        self.s_mat = QSpinBox()
        self.s_mat.setRange(2, 80)
        self.s_mat.setValue(30)
        self.s_mat.setSuffix(" ligan ΔG terbaik")
        h.addWidget(self.s_mat)
        h.addStretch(1)
        v.addLayout(h)
        self.k_mat = KanvasSvg()
        v.addWidget(self.k_mat, 1)
        self.s_mat.valueChanged.connect(self.gambar_matriks)
        self.tab.addTab(w, "Matriks kemiripan")

    def _tab_mirip(self):
        w = QWidget()
        v = QVBoxLayout(w)
        h = QHBoxLayout()
        h.addWidget(QLabel("Acuan"))
        self.c_acuan = QComboBox()
        self.c_acuan.setMinimumWidth(240)
        self.e_smiles = QLineEdit()
        self.e_smiles.setPlaceholderText("…atau tempel SMILES acuan (mis. obat pembanding), lalu Enter")
        h.addWidget(self.c_acuan)
        h.addWidget(self.e_smiles, 1)
        v.addLayout(h)
        self.t_mirip = QTableWidget(0, 5)
        self.t_mirip.setHorizontalHeaderLabels(["#", "Ligan", "Tanimoto", "ΔG terbaik", "Klaster"])
        self.t_mirip.verticalHeader().setVisible(False)
        self.t_mirip.horizontalHeader().setStretchLastSection(True)
        self.t_mirip.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self.t_mirip, 1)
        self.c_acuan.currentIndexChanged.connect(self.isi_mirip)
        self.e_smiles.returnPressed.connect(self.isi_mirip)
        self.tab.addTab(w, "Cari mirip")

    def _tab_klaster(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_kl = QTableWidget(0, 5)
        self.t_kl.setHorizontalHeaderLabels(["Klaster", "Jumlah", "Pusat klaster", "ΔG terbaik (ligan)", "Anggota"])
        self.t_kl.verticalHeader().setVisible(False)
        self.t_kl.horizontalHeader().setStretchLastSection(True)
        self.t_kl.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self.t_kl, 1)
        self.tab.addTab(w, "Klaster")

    def _tab_farma(self):
        w = QWidget()
        v = QVBoxLayout(w)
        ket = QLabel("Farmakofor bersama: fitur kimia (donor/akseptor ikatan H, aromatik, hidrofobik, muatan) dari pose "
                     "terbaik N ligan dengan ΔG terendah, dikelompokkan bila berdekatan. Fitur yang muncul di banyak "
                     "pose = titik pengikatan penting untuk merancang/menyaring ligan baru.")
        ket.setWordWrap(True)
        ket.setObjectName("muted")
        v.addWidget(ket)
        h = QHBoxLayout()
        self.c_job = QComboBox()
        self.s_top = QSpinBox()
        self.s_top.setRange(2, 100)
        self.s_top.setValue(10)
        self.s_top.setSuffix(" ligan teratas")
        self.s_rad = QDoubleSpinBox()
        self.s_rad.setRange(0.5, 3.0)
        self.s_rad.setSingleStep(0.25)
        self.s_rad.setValue(1.5)
        self.s_rad.setSuffix(" Å")
        self.s_rad.setToolTip("Fitur sejenis dalam jarak ini dianggap satu titik farmakofor")
        self.s_frek = QSpinBox()
        self.s_frek.setRange(10, 100)
        self.s_frek.setValue(50)
        self.s_frek.setSuffix(" % pose")
        self.s_frek.setToolTip("Hanya fitur yang muncul di minimal persentase pose ini")
        for t, x in (("Job", self.c_job), ("", self.s_top), ("Radius", self.s_rad), ("Minimal", self.s_frek)):
            if t:
                h.addWidget(QLabel(t))
            h.addWidget(x)
        b = QPushButton("Hitung farmakofor")
        b.setObjectName("primary")
        b.clicked.connect(self.hitung_farma)
        h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)
        self.t_farma = QTableWidget(0, 5)
        self.t_farma.setHorizontalHeaderLabels(["Fitur", "Frekuensi", "Pose", "Sebaran (Å)", "Pusat x, y, z"])
        self.t_farma.verticalHeader().setVisible(False)
        self.t_farma.horizontalHeader().setStretchLastSection(True)
        self.t_farma.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self.t_farma, 1)
        h2 = QHBoxLayout()
        self.b_tampil = QPushButton("Tampilkan di viewport")
        self.b_tampil.clicked.connect(self.tampil_farma)
        self.b_pml = QPushButton("Simpan skrip PyMOL…")
        self.b_pml.clicked.connect(self.simpan_pml)
        for x in (self.b_tampil, self.b_pml):
            x.setEnabled(False)
            h2.addWidget(x)
        h2.addStretch(1)
        v.addLayout(h2)
        self.tab.addTab(w, "Farmakofor bersama")

    # ------------------------------------------------------------------ data
    def muat(self):
        with kit.sibuk(self.l_info, "Membaca ligan proyek…"):
            jw = self.jw
            dg = {}
            if jw.proyek:
                for b in eksmod.baris_hasil(jw.proyek):
                    dg[b["lid"]] = min(dg.get(b["lid"], 0.0), b["energi"])
            self.lig, gagal = [], []
            for kunci, nama, teks, fmt, _l in jw._sumber_sifat():
                try:
                    self.lig.append({"nama": nama, "kunci": kunci, "mol": K.mol_dari(teks, fmt), "dg": dg.get(kunci)})
                except Exception:
                    gagal.append(nama)
            self.c_acuan.blockSignals(True)
            self.c_acuan.clear()
            for i, l in enumerate(self.lig):
                self.c_acuan.addItem(l["nama"], i)
            kr = next((i for i, l in enumerate(self.lig) if "kristal" in l["nama"].lower()), 0)
            self.c_acuan.setCurrentIndex(kr)
            self.c_acuan.blockSignals(False)
            self.c_job.clear()
            if jw.proyek:
                terbaik, n_maks = 0, 0
                for j in reversed(jw.proyek.job):
                    n = sum(1 for l in j["ligan"] if l["status"] == "selesai" and "kristal" not in l["nama"].lower())
                    if n:
                        self.c_job.addItem(f"{mesinmod.MESIN.get(j['mesin'], j['mesin'])} · {j['id']} · {n} ligan", j["id"])
                        if n > n_maks:      # bawaan: job dengan ligan terbanyak (bukan job validasi kristal)
                            terbaik, n_maks = self.c_job.count() - 1, n
                self.c_job.setCurrentIndex(terbaik)
            self.l_info.setText(f"{len(self.lig)} ligan" + (f" ({len(gagal)} tak terbaca)" if gagal else ""))
            self.hitung()

    def hitung(self, *_):
        with kit.sibuk(self.l_info, "Menghitung kemiripan dan klaster…"):
            if len(self.lig) < 2:
                self.k_peta.set_svg("")
                self.l_info.setText("Butuh ≥ 2 ligan (impor atau siapkan ligan dulu).")
                return
            jenis = self.c_fp.currentData()
            self.fps = [K.sidik_jari(l["mol"], jenis) for l in self.lig]
            self.m = K.matriks(self.fps)
            self.klaster, _ = K.butina(self.m, self.s_amb.value())
            self.gambar_peta()
            self.gambar_matriks()
            self.isi_mirip()
            self.isi_klaster()

        # ------------------------------------------------------------------ peta & matriks
    def _svg_peta(self, gelap=False, transparan=False):
        if self.m is None:
            return ""
        if self.c_peta.currentData() == "mds":
            xy, var = K.mds(self.m)
            lx, ly = "Dimensi 1", "Dimensi 2"
            ket = f"MDS klasik, jarak = 1 − Tanimoto ({K.NAMA_SIDIK[self.c_fp.currentData()]})"
        else:
            xy, var = K.pca([K.deskriptor(l["mol"]) for l in self.lig])
            lx, ly = "PC1", "PC2"
            ket = "PCA terstandar: " + ", ".join(K.DESKRIPTOR)
        lx += f" ({var[0] * 100:.0f} %)".replace(".", ",")
        ly += f" ({var[1] * 100:.0f} %)".replace(".", ",")
        nama = [l["nama"] for l in self.lig]
        kel = self.klaster if self.c_warna.currentData() == "klaster" else None
        nil = [l["dg"] for l in self.lig] if self.c_warna.currentData() == "dg" else None
        acu = self.c_acuan.currentData() if not self.e_smiles.text().strip() else None
        return grafik.sebar_kelompok(list(xy[:, 0]), list(xy[:, 1]), nama, kel, nil, lx, ly, "Peta ruang kimia",
                                     gelap, transparan, label=self.c_lbl.isChecked(), acuan=acu,
                                     label_nilai="ΔG (kcal/mol)", catatan=f"n = {len(nama)} · {ket}", tanpa_tik=True)

    def _svg_matriks(self, gelap=False, transparan=False):
        if self.m is None:
            return ""
        idx = sorted(range(len(self.lig)), key=lambda i: (self.lig[i]["dg"] is None, self.lig[i]["dg"] or 0))
        idx = idx[:self.s_mat.value()]
        lab = [self.lig[i]["nama"][:28] for i in idx]
        mm = [[float(self.m[i][j]) for j in idx] for i in idx]
        return grafik.peta_korelasi(lab, mm, f"Kemiripan Tanimoto · {K.NAMA_SIDIK[self.c_fp.currentData()]}", gelap,
                                    transparan, skala01=True, catatan=f"{len(idx)} ligan (urut ΔG terbaik)")

    def _mode(self):
        return self.jw.st.value("tema", "terang") == "gelap"

    def gambar_peta(self, *_):
        g = self._mode()
        self.k_peta.latar = QColor(theme.TOKEN["gelap" if g else "terang"]["surf"])
        self.k_peta.set_svg(self._svg_peta(g))

    def gambar_matriks(self, *_):
        g = self._mode()
        self.k_mat.latar = QColor(theme.TOKEN["gelap" if g else "terang"]["surf"])
        self.k_mat.set_svg(self._svg_matriks(g))

    # ------------------------------------------------------------------ tabel
    def isi_mirip(self, *_):
        if not self.fps:
            return
        smi = self.e_smiles.text().strip()
        if smi:
            try:
                acuan = K.sidik_jari(K.mol_dari(smi, "smi"), self.c_fp.currentData())
            except Exception:
                self.jw.statusBar().showMessage("SMILES acuan tidak valid.", 5000)
                return
            ia = None
        else:
            ia = self.c_acuan.currentData()
            if ia is None:
                return
            acuan = self.fps[ia]
        sk = K.peringkat(acuan, self.fps)
        urut = sorted(range(len(sk)), key=lambda i: -sk[i])
        t = self.t_mirip
        t.setSortingEnabled(False)
        t.setRowCount(len(urut))
        for r, i in enumerate(urut):
            l = self.lig[i]
            t.setItem(r, 0, _sel(str(r + 1), r + 1))
            t.setItem(r, 1, _sel(l["nama"] + ("  (acuan)" if i == ia else "")))
            t.setItem(r, 2, _sel(_f(sk[i], 3), sk[i]))
            t.setItem(r, 3, _sel(_f(l["dg"], 2) if l["dg"] is not None else "-", l["dg"] or 0))
            t.setItem(r, 4, _sel(str(self.klaster[i]), self.klaster[i]))
        t.resizeColumnsToContents()
        if self.tab.currentIndex() == 0:
            self.gambar_peta()

    def isi_klaster(self):
        with kit.sibuk(self.l_info, "Mengelompokkan ligan…"):
            grup = {}
            for i, k in enumerate(self.klaster):
                grup.setdefault(k, []).append(i)
            t = self.t_kl
            t.setRowCount(len(grup))
            for r, k in enumerate(sorted(grup)):
                ang = grup[k]
                pusat = max(ang, key=lambda i: sum(self.m[i][j] for j in ang))
                dgs = [(self.lig[i]["dg"], self.lig[i]["nama"]) for i in ang if self.lig[i]["dg"] is not None]
                terbaik = min(dgs) if dgs else None
                t.setItem(r, 0, _sel(str(k), k))
                t.setItem(r, 1, _sel(str(len(ang)), len(ang)))
                t.setItem(r, 2, _sel(self.lig[pusat]["nama"]))
                t.setItem(r, 3, _sel(f"{_f(terbaik[0], 2)} ({terbaik[1]})" if terbaik else "-"))
                t.setItem(r, 4, _sel(", ".join(self.lig[i]["nama"] for i in ang)))
            t.resizeColumnsToContents()

        # ------------------------------------------------------------------ farmakofor bersama
    def hitung_farma(self):
        jw = self.jw
        jid = self.c_job.currentData()
        j = jw.pelaksana.cari(jid) if jid else None
        if not j:
            jw._galat("Belum ada job docking yang selesai.")
            return
        pr = jw.proyek
        lig = sorted([l for l in j["ligan"] if l["status"] == "selesai"], key=lambda l: l["energi"])
        lig = [l for l in lig if "kristal" not in l["nama"].lower()][:self.s_top.value()]
        if len(lig) < 2:
            jw._galat("Farmakofor bersama butuh ≥ 2 ligan hasil docking pada job ini.")
            return
        rad, frek = self.s_rad.value(), self.s_frek.value() / 100

        def kerjakan(lapor):
            semua, nama = [], []
            for l in lig:
                try:
                    p = mesinmod.baca_hasil(j["mesin"], pr.p(l["keluaran"]))[0]
                    m = analisis.pose_mol(pr.p(l["pdbqt"]).read_text(), p.pdbqt)
                    semua.append(K.fitur(m))
                    nama.append(l["nama"])
                except Exception as e:
                    lapor.log.emit(f"Farmakofor: pose {l['nama']} dilewati ({e})")
            return K.farmakofor_bersama(semua, rad, frek), nama

        self.b_tampil.setEnabled(False)
        self.jw.statusBar().showMessage("Menghitung farmakofor bersama…")
        kerja.jalankan(kerjakan, selesai=self._farma_selesai, galat=jw._galat, log=jw.log.tulis)

    def _farma_selesai(self, hasil):
        fs, nama = hasil
        self.farma = fs
        t = self.t_farma
        t.setRowCount(len(fs))
        for r, f in enumerate(fs):
            it = _sel(f["nama"])
            it.setForeground(QColor(f["warna"]))
            t.setItem(r, 0, it)
            t.setItem(r, 1, _sel(f"{round(f['frek'] * 100)} %", f["frek"]))
            t.setItem(r, 2, _sel(f"{f['n']}/{len(nama)}", f["n"]))
            t.setItem(r, 3, _sel(_f(f["sebar"], 2), f["sebar"]))
            t.setItem(r, 4, _sel("; ".join(_f(v, 2) for v in f["xyz"])))
        t.resizeColumnsToContents()
        for b in (self.b_tampil, self.b_pml):
            b.setEnabled(bool(fs))
        saran = "" if fs else " - tidak ada fitur yang cukup sering; turunkan 'Minimal' atau naikkan radius."
        self.jw.statusBar().showMessage(f"Farmakofor bersama dari {len(nama)} pose: {K.ringkas_fitur(fs)}{saran}", 10000)
        if fs:
            self.tampil_farma()

    def tampil_farma(self):
        if not self.farma:
            return
        d = [dict(f, label=f"{f['nama']} {round(f['frek'] * 100)} %") for f in self.farma]
        self.jw.a_farma.setChecked(False)
        self.jw.viewer.js("farmakofor", d, {"label": True})
        self.jw.statusBar().showMessage("Farmakofor bersama ditampilkan di viewport (matikan: Analisis › "
                                        "Farmakofor pose aktif dua kali).", 8000)

    def simpan_pml(self):
        f = self.jw._path("Simpan farmakofor (PyMOL)", "farmakofor.pml", "Skrip PyMOL (*.pml)")
        if f:
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(K.pml_farmakofor(self.farma))
            self.jw.log.tulis(f"Farmakofor disimpan: {f}")

    # ------------------------------------------------------------------ ekspor
    def _grafik(self, mode):
        i = self.tab.currentIndex()
        if i not in (0, 1):
            self.jw.statusBar().showMessage("Pilih tab Peta ruang kimia atau Matriks kemiripan dulu.", 5000)
            return
        s = self._svg_peta() if i == 0 else self._svg_matriks()
        if not s:
            return
        import re
        mm = re.search(r'width="(\d+)" height="(\d+)"', s)
        w, h = int(mm.group(1)), int(mm.group(2))
        nama = "ruang_kimia" if i == 0 else "matriks_kemiripan"
        if mode == "salin":
            self.jw._salin_svg(s, w, h, nama)
            return
        f = self.jw._path("Simpan grafik", f"{nama}.svg", "SVG (*.svg);;PDF (*.pdf);;PNG (*.png);;TIFF (*.tif)")
        if f:
            ext = f.lower().rsplit(".", 1)[-1]
            jenis = {"pdf": "pdf", "png": "png", "tif": "tif", "tiff": "tif"}.get(ext, "svg")
            self.jw._simpan_svg(s, f, jenis, w, h, mm=160, dpi=600)
            self.jw.log.tulis(f"Grafik disimpan: {f}")

    def ekspor_csv(self):
        if not self.lig:
            return
        f = self.jw._path("Ekspor kemiripan", "kemiripan_ligan.csv", "CSV (*.csv)")
        if not f:
            return
        acuan = self.c_acuan.currentData()
        sk = K.peringkat(self.fps[acuan], self.fps) if acuan is not None and self.fps else [None] * len(self.lig)
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Ligan", "dG terbaik (kcal/mol)", "Klaster",
                        f"Tanimoto ke {self.lig[acuan]['nama'] if acuan is not None else '-'}", "SMILES"])
            from rdkit import Chem
            for i, l in enumerate(self.lig):
                w.writerow([l["nama"], _f(l["dg"], 2) if l["dg"] is not None else "", self.klaster[i]
                            if self.klaster else "", _f(sk[i], 3) if sk[i] is not None else "",
                            Chem.MolToSmiles(l["mol"])])
        self.jw.log.tulis(f"Kemiripan diekspor: {f}")
        self.jw.statusBar().showMessage(f"Disimpan: {f}", 5000)
