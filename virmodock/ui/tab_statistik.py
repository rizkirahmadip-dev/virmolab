"""Tab Statistik: histogram, sebar + regresi, batang ΔG teratas, matriks korelasi; ringkasan deskriptif."""
from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QLabel, QPushButton, QSpinBox, QSplitter, QTextBrowser,
                               QToolBar, QVBoxLayout, QWidget)

from ..core import grafik, statistik as st
from . import theme
from .panel_interaksi import KanvasSvg

JENIS = [("hist", "Histogram"), ("sebar", "Sebar + regresi"), ("batang", "Batang ΔG teratas"),
         ("matriks", "Matriks korelasi"), ("ifp", "Kemiripan interaksi (IFP)")]
MATRIKS_BAWAAN = ["energi", "le", "mw", "wlogp", "tpsa", "hbd", "hba", "rotb", "atom_berat", "qed", "hbond",
                  "hidrofobik", "interaksi"]
SEMUA = "__semua__"


class TabStatistik(QWidget):
    ekspor = Signal(str)        # salin | svg | png | csv

    def __init__(self):
        super().__init__()
        self.mode = "terang"
        self.baris = []          # dataset penuh (semua job)
        self.data = []           # dataset terpilih
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QToolBar()
        self.c_job = QComboBox()
        self.c_job.setMinimumWidth(220)
        self.c_job.setToolTip("Satu job = satu mesin & parameter. 'Semua job' memakai ΔG terbaik tiap ligan.")
        self.c_jenis = QComboBox()
        for k, t in JENIS:
            self.c_jenis.addItem(t, k)
        self.c_x, self.c_y = QComboBox(), QComboBox()
        for k, label, _p, _d in st.VARIABEL:
            self.c_x.addItem(label, k)
            self.c_y.addItem(label, k)
        self.c_x.setCurrentIndex(self.c_x.findData("energi"))
        self.c_y.setCurrentIndex(self.c_y.findData("energi"))
        self.l_x, self.l_y = QLabel(" X "), QLabel(" Y ")
        self.s_n = QSpinBox()
        self.s_n.setRange(0, 200)
        self.s_n.setSpecialValueText("otomatis")
        self.l_n = QLabel(" Kelas ")
        self.c_metode = QComboBox()
        self.c_metode.addItem("Pearson", "pearson")
        self.c_metode.addItem("Spearman", "spearman")
        self.c_label = QCheckBox("Label")
        self.c_label.setToolTip("Nama ligan di titik (nomor bila > 25 titik)")
        self._aksi = {}         # widget di QToolBar disembunyikan lewat QAction-nya
        for w in (QLabel("Job "), self.c_job, QLabel("   Grafik "), self.c_jenis, self.l_x, self.c_x, self.l_y,
                  self.c_y, self.l_n, self.s_n, self.c_metode, self.c_label):
            self._aksi[w] = bar.addWidget(w)
        self.c_x.setMaximumWidth(180)
        self.c_y.setMaximumWidth(180)
        self.c_job.setMaximumWidth(260)
        sp = QWidget()
        sp.setSizePolicy(sp.sizePolicy().horizontalPolicy().Expanding, sp.sizePolicy().verticalPolicy().Preferred)
        bar.addWidget(sp)
        for k, t in (("salin", "Salin"), ("csv", "Data CSV…"), ("svg", "SVG/PDF…"), ("png", "PNG/TIFF…")):
            b = QPushButton(t)
            b.clicked.connect(lambda _=False, k=k: self.ekspor.emit(k))
            bar.addWidget(b)
        lay.addWidget(bar)
        bagi = QSplitter(Qt.Horizontal)
        self.kanvas = KanvasSvg()
        bagi.addWidget(self.kanvas)
        self.info = QTextBrowser()
        self.info.setOpenLinks(False)
        self.info.setMinimumWidth(400)
        bagi.addWidget(self.info)
        bagi.setStretchFactor(0, 3)
        bagi.setStretchFactor(1, 2)
        lay.addWidget(bagi, 1)
        cat = QLabel("Korelasi menunjukkan hubungan, bukan sebab-akibat. ΔG docking adalah skor perkiraan; "
                     "bandingkan hanya hasil dari mesin & parameter yang sama (pilih satu job). "
                     "Pita biru = selang kepercayaan 95 % garis regresi. * = p < 0,05 (tanpa koreksi uji berganda).")
        cat.setObjectName("muted")
        cat.setWordWrap(True)
        cat.setContentsMargins(8, 4, 8, 4)
        lay.addWidget(cat)
        self.c_job.currentIndexChanged.connect(self._pilih_job)
        for w in (self.c_jenis, self.c_x, self.c_y, self.c_metode):
            w.currentIndexChanged.connect(self._gambar)
        self.s_n.valueChanged.connect(self._gambar)
        self.c_label.toggled.connect(self._gambar)
        self._atur_kontrol()

    # ------------------------------------------------------------- data
    def muat(self, baris, jobs):
        """baris: statistik.dataset (semua job). jobs: [(id, teks)] urut lama → baru."""
        self.baris = baris
        lama = self.c_job.currentData()
        self.c_job.blockSignals(True)
        self.c_job.clear()
        for jid, t in jobs:
            n = sum(1 for d in baris if d["job"] == jid)
            if n:
                self.c_job.addItem(f"{t} · {n} ligan", jid)
        if self.c_job.count() > 1:
            self.c_job.addItem("Semua job · ΔG terbaik per ligan", SEMUA)
        i = self.c_job.findData(lama)
        # bawaan: job terbaru yang punya hasil
        self.c_job.setCurrentIndex(i if i >= 0 else max(0, self.c_job.count() - (2 if self.c_job.count() > 1 else 1)))
        self.c_job.blockSignals(False)
        self._pilih_job()

    def _pilih_job(self, *_):
        jid = self.c_job.currentData()
        if jid == SEMUA:
            terbaik = {}
            for d in self.baris:
                if d["lid"] not in terbaik or d["energi"] < terbaik[d["lid"]]["energi"]:
                    terbaik[d["lid"]] = d
            self.data = sorted(terbaik.values(), key=lambda d: d["energi"])
        else:
            self.data = [d for d in self.baris if d["job"] == jid]
        self._gambar()

    def _atur_kontrol(self):
        j = self.c_jenis.currentData()
        tampil = {self.l_x: j in ("hist", "sebar"), self.c_x: j in ("hist", "sebar"),
                  self.l_y: j == "sebar", self.c_y: j == "sebar",
                  self.l_n: j in ("hist", "batang", "ifp"), self.s_n: j in ("hist", "batang", "ifp"),
                  self.c_metode: j == "matriks", self.c_label: j == "sebar"}
        for w, on in tampil.items():
            self._aksi[w].setVisible(on)
        self.l_x.setText(" Variabel " if j == "hist" else " X ")
        self.l_n.setText(" Kelas " if j == "hist" else " Jumlah ")
        self.s_n.setSpecialValueText("otomatis" if j == "hist" else "20")

    # ------------------------------------------------------------- gambar
    def svg(self, gelap=None, transparan=False, judul=True):
        """SVG grafik aktif + (lebar, tinggi) piksel."""
        g = (self.mode == "gelap") if gelap is None else gelap
        j = self.c_jenis.currentData()
        d = self.data
        if not d:
            return "", (0, 0)
        kx, ky = self.c_x.currentData(), self.c_y.currentData()
        if j == "hist":
            v = st.kolom(d, kx)
            if len(v) < 2:
                return "", (0, 0)
            s = grafik.histogram(v, st.LABEL[kx], f"Sebaran {st.PENDEK[kx]}" if judul else "",
                                 self.s_n.value() or None, g, transparan, catatan=f"n = {len(v)}")
            return s, (760, 520)
        if j == "sebar":
            pr = st.pasangan(d, kx, ky)
            if len(pr) < 2:
                return "", (0, 0)
            x, y = [p[1] for p in pr], [p[2] for p in pr]
            k = st.korelasi(x, y)
            s = grafik.sebar(x, y, [p[0] for p in pr], st.LABEL[kx], st.LABEL[ky],
                             f"{st.PENDEK[ky]} vs {st.PENDEK[kx]}" if judul else "", k, g, transparan,
                             label=self.c_label.isChecked())
            return s, (760, 560)
        if j == "batang":
            n = self.s_n.value() or 20
            top = sorted(d, key=lambda r: r["energi"])[:n]
            s = grafik.batang([r["ligan"] for r in top], [r["energi"] for r in top], "ΔG (kcal/mol)",
                              f"{len(top)} ligan dengan ΔG terendah" if judul else "", g, transparan)
            return s, (760, max(260, 70 + 22 * len(top) + (44 if judul else 20)))
        if j == "ifp":
            n = self.s_n.value() or 20
            top = sorted(d, key=lambda r: r["energi"])[:n]
            label, m = st.matriks_ifp(top)
            if len(label) < 2:
                return "", (0, 0)
            s = grafik.peta_korelasi(label, m, "Kemiripan sidik jari interaksi (Tanimoto)" if judul else "", g,
                                     transparan, skala01=True,
                                     catatan=f"{len(label)} ligan ΔG terendah; bit = residu × jenis interaksi "
                                             "(tanpa vdW)")
            import re
            mm = re.search(r'width="(\d+)" height="(\d+)"', s)
            return s, (int(mm.group(1)), int(mm.group(2)))
        kun = [k for k in MATRIKS_BAWAAN if len(st.kolom(d, k)) > 2 and len(set(st.kolom(d, k))) > 1]
        if len(kun) < 2:
            return "", (0, 0)
        r, p = st.matriks(d, kun, self.c_metode.currentData())
        s = grafik.peta_korelasi([st.PENDEK[k] for k in kun], r,
                                 f"Korelasi {self.c_metode.currentText()}" if judul else "", g, transparan, p=p,
                                 catatan=f"n = {len(d)}; * p < 0,05")
        import re
        m = re.search(r'width="(\d+)" height="(\d+)"', s)
        return s, (int(m.group(1)), int(m.group(2)))

    def _gambar(self, *_):
        self._atur_kontrol()
        if self.c_jenis.currentData() == "sebar" and self.c_x.currentData() == self.c_y.currentData():
            self.c_x.blockSignals(True)       # X = Y tidak berguna: bawaan MW vs ΔG
            self.c_x.setCurrentIndex(self.c_x.findData("mw" if self.c_y.currentData() != "mw" else "energi"))
            self.c_x.blockSignals(False)
        self.kanvas.latar = QColor(theme.TOKEN[self.mode]["surf"])
        s, _ = self.svg()
        self.kanvas.set_svg(s)
        self._info()

    def _info(self):
        d = self.data
        t = theme.TOKEN[self.mode]
        o = [f"<style>td,th{{padding:2px 6px;}} th{{text-align:left;color:{t['ink2']};font-weight:600;}} "
             f"td.n{{text-align:right;font-family:Consolas,monospace;}} .m{{color:{t['mut']};}}</style>"]
        if not d:
            self.info.setHtml("".join(o) + "<p class='m'>Belum ada hasil docking. Jalankan docking dulu.</p>")
            return
        j = self.c_jenis.currentData()
        if j == "sebar":
            kx, ky = self.c_x.currentData(), self.c_y.currentData()
            pr = st.pasangan(d, kx, ky)
            k = st.korelasi([p[1] for p in pr], [p[2] for p in pr], pita=False)
            o.append(f"<p><b>{escape(st.LABEL[ky])}</b> vs <b>{escape(st.LABEL[kx])}</b></p>")
            if k["r"] is None:
                o.append("<p class='m'>Data kurang (n &lt; 3) atau variansi nol.</p>")
            else:
                F = grafik.fmt
                o.append("<table>"
                         f"<tr><th>n</th><td class='n'>{k['n']}</td></tr>"
                         f"<tr><th nowrap>Pearson r</th><td class='n'>{F(k['r'], 3)}</td><td nowrap>p {escape(grafik.p_teks(k['p']))}</td></tr>"
                         f"<tr><th>R²</th><td class='n'>{F(k['r2'], 3)}</td></tr>"
                         f"<tr><th nowrap>Spearman ρ</th><td class='n'>{F(k['rho'], 3)}</td>"
                         f"<td nowrap>p {escape(grafik.p_teks(k['p_rho']))}</td></tr>"
                         f"<tr><th>Kemiringan</th><td class='n'>{F(k['kemiringan'], 4)}</td>"
                         f"<td>SE {F(k['se_kemiringan'], 4)}</td></tr>"
                         f"<tr><th nowrap>Perpotongan</th><td class='n'>{F(k['potong'], 3)}</td></tr></table>")
                arah = "negatif" if k["r"] < 0 else "positif"
                sig = "bermakna (p &lt; 0,05)" if k["p"] < 0.05 else "tidak bermakna (p ≥ 0,05)"
                o.append(f"<p>Korelasi {arah} {st.kekuatan(k['r'])}, {sig}.</p>")
        o.append("<p><b>Statistik deskriptif</b></p><table><tr><th>Variabel</th><th>n</th><th>Rerata ± SD</th>"
                 "<th>Median</th><th>Min – Maks</th></tr>")
        F = grafik.fmt
        for k, label, pendek, des in st.VARIABEL:
            s = st.deskriptif(st.kolom(d, k))
            if not s["n"]:
                continue
            dd = max(des, 1)
            sd = f" ± {F(s['sd'], dd)}" if s["sd"] is not None else ""
            o.append(f"<tr><td nowrap>{escape(pendek)}</td><td class='n'>{s['n']}</td>"
                     f"<td class='n' nowrap>{F(s['rerata'], dd)}{sd}</td><td class='n' nowrap>{F(s['median'], dd)}</td>"
                     f"<td class='n' nowrap>{F(s['min'], dd)} – {F(s['maks'], dd)}</td></tr>")
        o.append("</table>")
        self.info.setHtml("".join(o))

    def set_mode(self, mode):
        self.mode = mode
        self._gambar()
