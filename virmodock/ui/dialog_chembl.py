"""Dialog ChEMBL (Siapkan › Ligan dari ChEMBL… / Analisis › Korelasi dengan data eksperimen ChEMBL…).

1. Cari target (ID PDB reseptor proyek, UniProt, CHEMBL…, atau nama) → tabel target urut jumlah data.
2. Ambil aktivitas ber-pChEMBL (IC50/Ki/Kd/EC50) → tabel senyawa (median pChEMBL per senyawa).
3. Impor senyawa terpilih/teratas sebagai ligan (validasi: aktif dikenal), atau cocokkan dengan hasil docking
   (InChIKey konektivitas) → grafik ΔG vs pChEMBL + Pearson/Spearman; pChEMBL disimpan di proyek.ligan untuk
   tab Statistik.
"""
from datetime import datetime
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QProgressBar, QPushButton, QSpinBox, QSplitter, QTabWidget, QTableWidget,
                               QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

from ..core import chembl as C
from ..core import ekspor as eksmod
from ..core import grafik
from ..core import kemiripan as K
from ..core import statistik as st
from ..core.laporan import id_angka
from . import kerja, theme
from .panel_interaksi import KanvasSvg


def _sel(t, angka=None):
    it = QTableWidgetItem(t)
    if angka is not None:
        it.setData(Qt.UserRole, angka)
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


def _f(v, d=2):
    return id_angka(f"{v:.{d}f}")


class DialogChembl(QDialog):
    def __init__(self, jw, tab_awal=0):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("ChEMBL - data aktivitas eksperimen")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1240, 800)
        self.target = []
        self.senyawa = []
        self.cocok = []
        pr = jw.proyek
        lama = (pr.eksperimen if pr else {}) or {}
        lay = QVBoxLayout(self)
        ket = QLabel("Data bioaktivitas ChEMBL (EMBL-EBI, CC BY-SA 3.0) diambil lewat internet. pChEMBL = −log₁₀ "
                     "(IC₅₀/Ki/Kd/EC₅₀ molar): makin besar makin poten (6 = 1 µM, 9 = 1 nM).")
        ket.setWordWrap(True)
        ket.setObjectName("muted")
        lay.addWidget(ket)
        # --- 1. target
        h = QHBoxLayout()
        h.addWidget(QLabel("<b>1</b>  Target"))
        self.e_cari = QLineEdit()
        self.e_cari.setPlaceholderText("ID PDB (mis. 1HSG), UniProt (P00918), CHEMBL205, atau nama protein")
        self.e_cari.setText((lama.get("target") or {}).get("chembl") or self._pdb_proyek())
        self.e_cari.returnPressed.connect(self.cari)
        h.addWidget(self.e_cari, 1)
        b = QPushButton("Cari target")
        b.setObjectName("primary")
        b.clicked.connect(self.cari)
        h.addWidget(b)
        lay.addLayout(h)
        bagi = QSplitter(Qt.Vertical)
        self.t_target = QTableWidget(0, 6)
        self.t_target.setHorizontalHeaderLabels(["ChEMBL ID", "Nama target", "Organisme", "Jenis", "UniProt",
                                                 "Data pChEMBL"])
        self.t_target.verticalHeader().setVisible(False)
        self.t_target.setSelectionBehavior(QTableWidget.SelectRows)
        self.t_target.setSelectionMode(QTableWidget.SingleSelection)
        self.t_target.setEditTriggers(QTableWidget.NoEditTriggers)
        self.t_target.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.t_target.doubleClicked.connect(lambda *_: self.ambil())
        bagi.addWidget(self.t_target)
        # --- 2. aktivitas
        w2 = QWidget()
        v2 = QVBoxLayout(w2)
        v2.setContentsMargins(0, 0, 0, 0)
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("<b>2</b>  Aktivitas"))
        self.c_jenis = {}
        for j in C.JENIS_AKTIVITAS:
            c = QCheckBox(j)
            c.setChecked(j != "EC50")
            self.c_jenis[j] = c
            h2.addWidget(c)
        h2.addWidget(QLabel("  maks"))
        self.s_maks = QSpinBox()
        self.s_maks.setRange(100, 20000)
        self.s_maks.setSingleStep(500)
        self.s_maks.setValue(3000)
        self.s_maks.setSuffix(" data")
        h2.addWidget(self.s_maks)
        self.b_ambil = QPushButton("Ambil aktivitas target terpilih")
        self.b_ambil.clicked.connect(self.ambil)
        h2.addWidget(self.b_ambil)
        self.prog = QProgressBar()
        self.prog.setMaximumWidth(160)
        self.prog.setVisible(False)
        h2.addWidget(self.prog)
        h2.addStretch(1)
        h2.addWidget(QLabel("pChEMBL ≥"))
        self.s_min = QDoubleSpinBox()
        self.s_min.setRange(0, 12)
        self.s_min.setDecimals(1)
        self.s_min.setValue(0)
        self.s_min.valueChanged.connect(self.isi_senyawa)
        h2.addWidget(self.s_min)
        self.e_filter = QLineEdit()
        self.e_filter.setPlaceholderText("Saring nama/ID…")
        self.e_filter.setMaximumWidth(180)
        self.e_filter.textChanged.connect(self.isi_senyawa)
        h2.addWidget(self.e_filter)
        v2.addLayout(h2)
        self.tab = QTabWidget()
        self.t_sen = QTableWidget(0, 7)
        self.t_sen.setHorizontalHeaderLabels(["", "Nama", "ChEMBL ID", "pChEMBL", "n", "Jenis", "MW"])
        self.t_sen.verticalHeader().setVisible(False)
        self.t_sen.setEditTriggers(QTableWidget.NoEditTriggers)
        self.t_sen.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tab.addTab(self.t_sen, "Senyawa")
        wk = QWidget()
        hk = QHBoxLayout(wk)
        hk.setContentsMargins(0, 0, 0, 0)
        self.k_kor = KanvasSvg()
        hk.addWidget(self.k_kor, 3)
        self.i_kor = QTextBrowser()
        self.i_kor.setMinimumWidth(320)
        hk.addWidget(self.i_kor, 2)
        self.tab.addTab(wk, "Korelasi dengan docking")
        v2.addWidget(self.tab, 1)
        bagi.addWidget(w2)
        bagi.setSizes([200, 560])
        lay.addWidget(bagi, 1)
        # --- 3. aksi
        h3 = QHBoxLayout()
        h3.addWidget(QLabel("<b>3</b>"))
        self.s_impor = QSpinBox()
        self.s_impor.setRange(1, 500)
        self.s_impor.setValue(20)
        self.s_impor.setPrefix("Impor ")
        self.s_impor.setSuffix(" teratas")
        self.s_impor.setToolTip("Bila tidak ada yang dicentang, impor N senyawa pChEMBL tertinggi (setelah saringan)")
        h3.addWidget(self.s_impor)
        b_imp = QPushButton("Impor sebagai ligan")
        b_imp.setToolTip("Senyawa dicentang (atau N teratas) ditambahkan sebagai ligan SMILES → siapkan di langkah 2")
        b_imp.clicked.connect(self.impor)
        h3.addWidget(b_imp)
        b_kor = QPushButton("Cocokkan dengan hasil docking")
        b_kor.setObjectName("primary")
        b_kor.clicked.connect(self.korelasi)
        h3.addWidget(b_kor)
        h3.addStretch(1)
        self.l_status = QLabel()
        self.l_status.setObjectName("muted")
        h3.addWidget(self.l_status)
        for t, fn in (("Simpan grafik…", self.simpan_grafik), ("Ekspor CSV…", self.ekspor_csv), ("✕ Tutup", self.close)):
            x = QPushButton(t)
            x.clicked.connect(fn)
            h3.addWidget(x)
        lay.addLayout(h3)
        if lama.get("senyawa"):
            self.target = [lama["target"]]
            self._isi_target()
            self.senyawa = lama["senyawa"]
            self.isi_senyawa()
            self.l_status.setText(f"Data tersimpan di proyek: {lama['target'].get('nama', '')} · "
                                  f"{len(self.senyawa)} senyawa · {lama.get('waktu', '')}")
        self.tab.setCurrentIndex(tab_awal if self.senyawa else 0)
        if tab_awal == 1 and self.senyawa:
            self.korelasi()

    def _pdb_proyek(self):
        pr = self.jw.proyek
        nama = ((pr.reseptor or {}).get("nama") if pr else "") or ""
        if not nama:
            nama = next((o.nama for o in self.jw.objek.values() if o.jenis == "protein"), "")
        kode = nama.split()[0][:4] if nama else ""
        return kode if len(kode) == 4 and kode[0].isdigit() else ""

    # ------------------------------------------------------------------ jaringan
    def cari(self):
        q = self.e_cari.text().strip()
        if not q:
            return
        self.l_status.setText("Mencari target…")
        self.t_target.setRowCount(0)
        kerja.jalankan(C.cari_target, q, selesai=self._target_ok, galat=self._galat,
                       log=lambda s: self.l_status.setText(s))

    def _galat(self, t):
        self.prog.setVisible(False)
        self.l_status.setText("")
        pesan = str(t).strip().splitlines()[-1] if str(t).strip() else str(t)
        self.jw._galat("ChEMBL tidak dapat dihubungi atau permintaan gagal. Periksa koneksi internet.\n" + pesan)

    def _target_ok(self, hasil):
        self.target = hasil
        self._isi_target()
        self.l_status.setText(f"{len(hasil)} target ditemukan" if hasil else "Target tidak ditemukan")

    def _isi_target(self):
        t = self.t_target
        t.setRowCount(len(self.target))
        for r, x in enumerate(self.target):
            for c, v in enumerate((x["chembl"], x["nama"], x["organisme"], x["jenis"], x["uniprot"])):
                t.setItem(r, c, _sel(v))
            n = x.get("aktivitas")
            t.setItem(r, 5, _sel("-" if n is None else f"{n:,}".replace(",", "."), n or 0))
        for c in (0, 2, 3, 4):
            t.resizeColumnToContents(c)
        if self.target:
            t.selectRow(0)

    def ambil(self):
        r = self.t_target.currentRow()
        if r < 0 or r >= len(self.target):
            self.jw._galat("Pilih satu target dulu.")
            return
        tg = self.target[r]
        jenis = [j for j, c in self.c_jenis.items() if c.isChecked()] or C.JENIS_AKTIVITAS
        self.prog.setValue(0)
        self.prog.setVisible(True)
        self.b_ambil.setEnabled(False)
        self.l_status.setText(f"Mengambil aktivitas {tg['chembl']}…")

        def kerjakan(lapor):
            return C.ringkas_senyawa(C.aktivitas(tg["chembl"], jenis, self.s_maks.value(), lapor=lapor))

        def selesai(sen):
            self.prog.setVisible(False)
            self.b_ambil.setEnabled(True)
            self.senyawa = sen
            pr = self.jw.proyek
            if pr is not None:
                pr.eksperimen = {"target": tg, "jenis": jenis, "senyawa": sen,
                                 "waktu": datetime.now().strftime("%d-%m-%Y %H:%M"), "sumber": "ChEMBL"}
                self.jw.minta_simpan()
            self.isi_senyawa()
            self.l_status.setText(f"{tg['nama']}: {len(sen)} senyawa unik")
            self.jw.log.tulis(f"ChEMBL {tg['chembl']} ({tg['nama']}): {len(sen)} senyawa dengan pChEMBL")

        kerja.jalankan(kerjakan, selesai=selesai, galat=lambda g: (self.b_ambil.setEnabled(True), self._galat(g)),
                       log=lambda s: self.l_status.setText(s),
                       progres=lambda a, b, _t: (self.prog.setMaximum(max(1, b)), self.prog.setValue(a)))

    # ------------------------------------------------------------------ tabel senyawa
    def _tersaring(self):
        q = self.e_filter.text().strip().lower()
        m = self.s_min.value()
        return [s for s in self.senyawa if s["pchembl"] >= m
                and (not q or q in s["nama"].lower() or q in s["chembl"].lower())]

    def isi_senyawa(self, *_):
        d = self._tersaring()[:2000]
        t = self.t_sen
        t.setRowCount(len(d))
        for r, s in enumerate(d):
            c = QTableWidgetItem()
            c.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            c.setCheckState(Qt.Unchecked)
            c.setData(Qt.UserRole + 1, s["chembl"])
            t.setItem(r, 0, c)
            t.setItem(r, 1, _sel(s["nama"]))
            t.setItem(r, 2, _sel(s["chembl"]))
            t.setItem(r, 3, _sel(_f(s["pchembl"]) + (f" ± {_f(s['sd'])}" if s.get("sd") else ""), s["pchembl"]))
            t.setItem(r, 4, _sel(str(s["n"]), s["n"]))
            t.setItem(r, 5, _sel(s["jenis"]))
            t.setItem(r, 6, _sel(_f(s["berat"], 1) if s.get("berat") else "-", s.get("berat") or 0))
        for c in (0, 2, 3):
            t.resizeColumnToContents(c)

    def _terpilih(self):
        ids = {self.t_sen.item(r, 0).data(Qt.UserRole + 1) for r in range(self.t_sen.rowCount())
               if self.t_sen.item(r, 0).checkState() == Qt.Checked}
        d = self._tersaring()
        return [s for s in d if s["chembl"] in ids] if ids else d[:self.s_impor.value()]

    def impor(self):
        from ..core import molekul
        pilih = self._terpilih()
        if not pilih:
            return
        ada = {o.nama for o in self.jw.objek.values()}
        ob, gagal = [], 0
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for s in pilih:
                nama = s["nama"] if s["nama"] != s["chembl"] else s["chembl"]
                nama = nama.title() if nama.isupper() and not nama.startswith("CHEMBL") else nama
                if nama in ada:
                    continue
                try:
                    o = molekul.dari_smiles(s["smiles"], nama)
                    for x in o:
                        x.info["chembl"] = s["chembl"]
                        x.info["pchembl"] = s["pchembl"]
                    ob += o
                except Exception:
                    gagal += 1
        finally:
            QApplication.restoreOverrideCursor()
        if ob:
            self.jw.tambah_objek(ob, fokus=False)
        self.l_status.setText(f"{len(ob)} ligan diimpor" + (f", {gagal} gagal" if gagal else "")
                              + " - siapkan di langkah 2 (Siapkan ligan)")
        self.jw.log.tulis(f"ChEMBL: {len(ob)} ligan diimpor dari {len(pilih)} senyawa")

    # ------------------------------------------------------------------ korelasi
    def korelasi(self):
        jw = self.jw
        pr = jw.proyek
        if not self.senyawa:
            jw._galat("Ambil aktivitas target dulu (langkah 2).")
            return
        if not pr or not pr.job:
            jw._galat("Belum ada hasil docking untuk dicocokkan.")
            return
        dg = {}
        for b in eksmod.baris_hasil(pr):
            dg[b["lid"]] = min(dg.get(b["lid"], 0.0), b["energi"])
        lig = []
        for l in pr.ligan:
            f = pr.p(l["sdf"]) if l.get("sdf") else None
            try:
                mol = K.mol_dari(f.read_text(encoding="utf-8"), "sdf") if f and f.exists() else None
            except Exception:
                mol = None
            lig.append((l, mol))
        cocok = C.cocokkan(self.senyawa, [(l["id"], m, dg.get(l["id"])) for l, m in lig])
        per_id = {c[0]: c for c in cocok}
        for l, _m in lig:          # simpan untuk tab Statistik (variabel pChEMBL)
            l["pchembl"] = per_id[l["id"]][2] if l["id"] in per_id else None
            if l["id"] in per_id:
                l["chembl"] = per_id[l["id"]][3]
        jw.minta_simpan()
        jw._stat_kotor = True
        nama = {l["id"]: l["nama"] for l, _ in lig}
        self.cocok = [(nama[c[0]], c[1], c[2], c[3]) for c in cocok]
        self.tab.setCurrentIndex(1)
        self._gambar_kor()

    def _svg_kor(self, gelap=False, transparan=False):
        c = self.cocok
        if len(c) < 2:
            return ""
        x, y = [v[2] for v in c], [v[1] for v in c]
        k = st.korelasi(x, y)
        return grafik.sebar(x, y, [v[0] for v in c], "pChEMBL eksperimen", "ΔG docking (kcal/mol)",
                            "Docking vs aktivitas eksperimen (ChEMBL)", k, gelap, transparan, label=len(c) <= 25,
                            catatan=f"n = {len(c)} ligan cocok (InChIKey konektivitas)")

    def _gambar_kor(self):
        g = self.jw.st.value("tema", "terang") == "gelap"
        self.k_kor.latar = QColor(theme.TOKEN["gelap" if g else "terang"]["surf"])
        self.k_kor.set_svg(self._svg_kor(g))
        c = self.cocok
        o = ["<style>td{padding:2px 6px} td.n{text-align:right;font-family:Consolas,monospace}</style>"]
        if not c:
            o.append("<p>Tidak ada ligan hasil docking yang strukturnya cocok dengan senyawa ChEMBL target ini. "
                     "Impor senyawa ChEMBL sebagai ligan (langkah 3), siapkan, lalu docking.</p>")
        else:
            k = st.korelasi([v[2] for v in c], [v[1] for v in c], pita=False) if len(c) >= 3 else None
            if k and k.get("r") is not None:
                o.append(f"<p><b>n = {k['n']}</b> · Pearson r = {_f(k['r'], 3)} (p {escape(grafik.p_teks(k['p']))}) · "
                         f"Spearman ρ = {_f(k['rho'], 3)} (p {escape(grafik.p_teks(k['p_rho']))})</p>"
                         "<p style='color:#5b6b82'>Korelasi negatif = ΔG makin negatif untuk senyawa makin poten "
                         "(yang diharapkan). Skor docking umumnya berkorelasi lemah dengan afinitas; gunakan "
                         "untuk validasi kemampuan membedakan aktif, bukan prediksi nilai.</p>")
            elif len(c) < 3:
                o.append("<p>Butuh ≥ 3 ligan cocok untuk korelasi.</p>")
            o.append("<table><tr><th>Ligan</th><th>ΔG</th><th>pChEMBL</th><th>ΔG eksp.*</th></tr>")
            for n, d, p, cid in sorted(c, key=lambda v: -v[2]):
                o.append(f"<tr><td>{escape(n)}</td><td class=n>{_f(d)}</td><td class=n>{_f(p)}</td>"
                         f"<td class=n>{_f(C.pchembl_ke_dg(p))}</td></tr>")
            o.append("</table><p style='color:#5b6b82'>* ΔG = −RT ln 10 · pChEMBL (298 K), perkiraan kasar.</p>")
        o.append(f"<p style='color:#5b6b82;font-size:9pt'>Sitasi: {escape(C.SITASI)}</p>")
        self.i_kor.setHtml("".join(o))

    # ------------------------------------------------------------------ ekspor
    def simpan_grafik(self):
        s = self._svg_kor()
        if not s:
            self.jw.statusBar().showMessage("Belum ada grafik korelasi.", 4000)
            return
        f = self.jw._path("Simpan grafik", "docking_vs_chembl.svg", "SVG (*.svg);;PDF (*.pdf);;PNG (*.png);;TIFF (*.tif)")
        if f:
            ext = f.lower().rsplit(".", 1)[-1]
            self.jw._simpan_svg(s, f, {"pdf": "pdf", "png": "png", "tif": "tif"}.get(ext, "svg"), 760, 560, mm=140,
                                dpi=600)
            self.jw.log.tulis(f"Grafik disimpan: {f}")

    def ekspor_csv(self):
        if not self.senyawa:
            return
        f = self.jw._path("Ekspor ChEMBL", "chembl_aktivitas.csv", "CSV (*.csv)")
        if not f:
            return
        import csv
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["ChEMBL ID", "Nama", "pChEMBL median", "SD", "n", "Jenis", "MW", "SMILES", "InChIKey"])
            for s in self._tersaring():
                w.writerow([s["chembl"], s["nama"], _f(s["pchembl"]), _f(s["sd"]) if s.get("sd") else "", s["n"],
                            s["jenis"], _f(s["berat"], 1) if s.get("berat") else "", s["smiles"], s["inchikey"]])
        self.jw.log.tulis(f"ChEMBL diekspor: {f}")
