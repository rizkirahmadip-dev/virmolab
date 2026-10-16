"""Dialog Berkas › Impor hasil eksternal › Grafik XVG/CSV…

Plot data keluaran gmx (rmsd, rmsf, gyrate, energy, hbond, sasa), cpptraj, VMD, atau tabel CSV dengan gaya grafik
VirmoLab: beberapa berkas bisa ditumpuk (mis. RMSD tiga replika), satuan dikonversi, rata-rata bergerak, statistik
paruh kedua, lalu disimpan sebagai SVG/PDF/PNG/TIFF atau dikirim ke Komposer Figur.
"""
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLineEdit, QSpinBox, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core import grafik
from ..core import impor_grafik as G
from . import kit
from .panel_interaksi import KanvasSvg

FILTER = "Data grafik (*.xvg *.csv *.tsv *.dat *.txt *.agr);;XVG GROMACS (*.xvg);;CSV/TSV (*.csv *.tsv);;Semua (*.*)"
KOLOM_STAT = ["Seri", "n", "Rerata", "SD", "Min", "Maks", "Rerata paruh kedua"]
LEBAR, TINGGI = 760, 480


class DialogGrafikBerkas(QDialog):
    def __init__(self, jw, berkas=()):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Grafik dari berkas data")
        self.setAcceptDrops(True)
        self.resize(1180, 760)
        self.data = {}                 # jalur -> DataGrafik asli
        self._diubah = set()           # kolom teks yang sudah disunting pengguna (tidak ditimpa otomatis)
        self._svg = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "Grafik dari berkas data MD",
            "XVG keluaran gmx (rmsd, rmsf, gyrate, energy, hbond, sasa), DAT cpptraj/VMD, atau CSV diplot dengan gaya "
            "grafik VirmoLab. Beberapa berkas bisa ditumpuk dalam satu grafik, misalnya RMSD tiga replika."))
        bagi = QSplitter(Qt.Horizontal)
        kiri = QWidget()
        vk = QVBoxLayout(kiri)
        vk.setContentsMargins(0, 0, 0, 0)
        vk.setSpacing(10)

        g = QGroupBox("Berkas dan seri")
        gv = QVBoxLayout(g)
        self.pohon = QTreeWidget()
        self.pohon.setHeaderHidden(True)
        self.pohon.itemChanged.connect(lambda *_: self.gambar())
        gv.addWidget(self.pohon, 1)
        h = QHBoxLayout()
        h.addWidget(kit.tombol("Tambah berkas…", self._pilih))
        h.addStretch(1)
        h.addWidget(kit.tombol("Hapus", self._hapus, tip="Hapus berkas terpilih"))
        gv.addLayout(h)
        vk.addWidget(g, 1)

        g = QGroupBox("Tampilan")
        f = QFormLayout(g)
        self.cb_jenis = QComboBox()
        self.cb_jenis.addItem("Garis", "garis")
        self.cb_jenis.addItem("Distribusi (histogram seri pertama)", "histogram")
        self.cb_jenis.currentIndexChanged.connect(lambda *_: self.gambar())
        f.addRow("Jenis", self.cb_jenis)
        self.e_judul, self.e_x, self.e_y = QLineEdit(), QLineEdit(), QLineEdit()
        for k, e in (("judul", self.e_judul), ("x", self.e_x), ("y", self.e_y)):
            e.textEdited.connect(lambda *_, k=k: (self._diubah.add(k), self.gambar()))
        f.addRow("Judul", self.e_judul)
        f.addRow("Label sumbu X", self.e_x)
        f.addRow("Label sumbu Y", self.e_y)
        self.c_ns = QCheckBox("ps → ns")
        self.c_A = QCheckBox("nm → Å")
        self.c_A2 = QCheckBox("nm² → Å²")
        self.c_kcal = QCheckBox("kJ/mol → kcal/mol")
        h1, h2 = QHBoxLayout(), QHBoxLayout()
        for c in (self.c_ns, self.c_A):
            h1.addWidget(c)
        for c in (self.c_A2, self.c_kcal):
            h2.addWidget(c)
        for c in (self.c_ns, self.c_A, self.c_A2, self.c_kcal):
            c.toggled.connect(lambda *_: (self._diubah.discard("x"), self._diubah.discard("y"), self.gambar()))
        h1.addStretch(1)
        h2.addStretch(1)
        f.addRow("Satuan", h1)
        f.addRow("", h2)
        self.sp_rata = QSpinBox()
        self.sp_rata.setRange(1, 2000)
        self.sp_rata.setSpecialValueText("mati")
        self.sp_rata.setSuffix(" titik")
        self.sp_rata.setToolTip("Rata-rata bergerak terpusat untuk menghaluskan fluktuasi (mis. energi)")
        self.sp_rata.valueChanged.connect(lambda *_: self.gambar())
        f.addRow("Rata-rata bergerak", self.sp_rata)
        self.c_rerata = QCheckBox("Garis rerata tiap seri")
        self.c_rerata.toggled.connect(lambda *_: self.gambar())
        f.addRow("", self.c_rerata)
        vk.addWidget(g)
        bagi.addWidget(kiri)

        kanan = QWidget()
        vn = QVBoxLayout(kanan)
        vn.setContentsMargins(0, 0, 0, 0)
        self.kanvas = KanvasSvg()
        vn.addWidget(self.kanvas, 3)
        self.tabel = kit.tabel(KOLOM_STAT, regang=0)
        self.tabel.setMaximumHeight(170)
        vn.addWidget(self.tabel, 1)
        bagi.addWidget(kanan)
        bagi.setSizes([360, 820])
        lay.addWidget(bagi, 1)

        self.l_status = kit.catatan("")
        lay.addLayout(kit.bar_bawah(self, kiri=[self.l_status], kanan=[
            kit.tombol("Ekspor CSV…", self._csv), kit.tombol("Salin gambar", self._salin),
            kit.tombol("Kirim ke komposer", self._komposer), kit.tombol("Simpan figur…", self._simpan, utama=True)]))
        self._segarkan_konversi()
        self.gambar()
        if berkas:
            self.tambah(berkas)

    # ------------------------------------------------------------ berkas
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.tambah([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def _pilih(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Berkas data grafik",
                                             self.jw.st.value("dir_grafik", self.jw.st.value("dir_terakhir", "")),
                                             FILTER)
        if fs:
            self.jw.st.setValue("dir_grafik", str(Path(fs[0]).parent))
            self.tambah(fs)

    def tambah(self, fs):
        gagal = []
        self.pohon.blockSignals(True)
        for f in fs:
            f = str(Path(f))
            if f in self.data:
                continue
            try:
                d = G.baca(f)
            except Exception as e:
                gagal.append(f"{Path(f).name}: {e}")
                continue
            self.data[f] = d
            it = QTreeWidgetItem(self.pohon, [f"{Path(f).name} · {d.judul}" if d.judul != Path(f).stem
                                              else Path(f).name])
            it.setData(0, Qt.UserRole, f)
            it.setToolTip(0, f)
            it.setFlags(it.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            for i, s in enumerate(d.seri):
                c = QTreeWidgetItem(it, [f"{s.nama} ({len(s.y)} titik)"])
                c.setData(0, Qt.UserRole, (f, i))
                c.setFlags(c.flags() | Qt.ItemIsUserCheckable)
                # gyrate/energy: seri pertama saja dicentang agar grafik awal tidak penuh
                c.setCheckState(0, Qt.Checked if i == 0 or len(d.seri) <= 3 else Qt.Unchecked)
            it.setExpanded(True)
        self.pohon.blockSignals(False)
        self.l_status.setText("Tidak terbaca: " + "; ".join(gagal) if gagal else "")
        self._segarkan_konversi(baru=True)
        self.gambar()

    def _hapus(self):
        for it in self.pohon.selectedItems():
            if it.parent():
                it = it.parent()
            self.data.pop(it.data(0, Qt.UserRole), None)
            self.pohon.takeTopLevelItem(self.pohon.indexOfTopLevelItem(it))
        self._segarkan_konversi()
        self.gambar()

    def _segarkan_konversi(self, baru=False):
        ada = {"x_ns": False, "y_A": False, "y_A2": False, "y_kcal": False}
        for d in self.data.values():
            for k, v in G.konversi_tersedia(d).items():
                ada[k] = ada[k] or v
        for k, c in (("x_ns", self.c_ns), ("y_A", self.c_A), ("y_A2", self.c_A2), ("y_kcal", self.c_kcal)):
            c.blockSignals(True)
            c.setEnabled(ada[k])
            if baru and ada[k]:
                c.setChecked(True)       # saran: ns, Å, Å², kcal/mol seperti grafik VirmoLab lain
            if not ada[k]:
                c.setChecked(False)
            c.blockSignals(False)

    # ------------------------------------------------------------ data terpilih
    def _terpilih(self):
        """[(nama tampil, Seri terolah, DataGrafik terolah)] seri tercentang, satuan & penghalusan diterapkan."""
        olah, out = {}, []
        nama_dipakai = {}
        for i in range(self.pohon.topLevelItemCount()):
            it = self.pohon.topLevelItem(i)
            f = it.data(0, Qt.UserRole)
            for j in range(it.childCount()):
                c = it.child(j)
                if c.checkState(0) != Qt.Checked:
                    continue
                if f not in olah:
                    k = G.konversi_tersedia(self.data[f])
                    olah[f] = G.terapkan(self.data[f], x_ns=self.c_ns.isChecked() and k["x_ns"],
                                         y_A=self.c_A.isChecked() and k["y_A"],
                                         y_A2=self.c_A2.isChecked() and k["y_A2"],
                                         y_kcal=self.c_kcal.isChecked() and k["y_kcal"], jendela=self.sp_rata.value())
                s = olah[f].seri[c.data(0, Qt.UserRole)[1]]
                nama_dipakai[s.nama] = nama_dipakai.get(s.nama, 0) + 1
                out.append([s.nama, s, olah[f]])
        # nama kembar (mis. "RMSD" dari tiga replika): nama berkas lebih informatif
        for x in out:
            if nama_dipakai[x[0]] > 1:
                stem = Path(x[1].berkas).stem
                x[0] = stem if sum(1 for y in out if Path(y[1].berkas).stem == stem) == 1 else f"{x[0]} · {stem}"
        return out

    def _label_otomatis(self, pilih):
        if not pilih:
            return "", "", ""
        d0 = pilih[0][2]
        sama = len({p[2].berkas for p in pilih}) == 1
        judul = d0.judul if sama else re.sub(r"\s+", " ", " / ".join(dict.fromkeys(p[2].judul for p in pilih)))
        return judul, d0.label_x, d0.label_y or (pilih[0][0] if len(pilih) == 1 else "")

    def gambar(self):
        pilih = self._terpilih()
        judul, lx, ly = self._label_otomatis(pilih)
        for k, e, v in (("judul", self.e_judul, judul), ("x", self.e_x, lx), ("y", self.e_y, ly)):
            if k not in self._diubah:
                e.setText(v)
        gelap = getattr(self.jw, "mode", "terang") == "gelap"
        self._svg = self._svg_buat(pilih, gelap)
        self.kanvas.latar = QColor("#14171c" if gelap else "#ffffff")
        self.kanvas.set_svg(self._svg)
        self._isi_statistik(pilih)

    def _svg_buat(self, pilih, gelap):
        judul, lx, ly = self.e_judul.text(), self.e_x.text(), self.e_y.text()
        if not pilih:
            return grafik.garis([], lx, ly, judul or "Tambahkan berkas XVG, CSV, atau DAT", gelap=gelap,
                                lebar=LEBAR, tinggi=TINGGI)
        if self.cb_jenis.currentData() == "histogram":
            nama, s, _ = pilih[0]
            return grafik.histogram(s.y, label_x=ly or nama, judul=judul, gelap=gelap, lebar=LEBAR, tinggi=TINGGI,
                                    label_y="Jumlah frame", catatan=f"{nama}: {len(s.y)} titik")
        acuan = None
        if self.c_rerata.isChecked():
            # satu seri: garis merah berlabel; beberapa seri: garis sewarna seri tanpa teks (nilai ada di tabel)
            acuan = [(G.statistik(s.y)["rerata"], f"rerata {grafik.fmt(G.statistik(s.y)['rerata'])}")
                     for _, s, _ in pilih[:1] if s.y] if len(pilih) == 1 else \
                [(G.statistik(s.y)["rerata"], "", grafik.PALET_GARIS[i % len(grafik.PALET_GARIS)])
                 for i, (_, s, _) in enumerate(pilih) if s.y]
        return grafik.garis([(nama, s.x, s.y) for nama, s, _ in pilih], lx, ly, judul, gelap=gelap, lebar=LEBAR,
                            tinggi=TINGGI, acuan=acuan, x_nol=False,
                            catatan=f"Rata-rata bergerak {self.sp_rata.value()} titik" if self.sp_rata.value() > 1
                            else "")

    def _isi_statistik(self, pilih):
        t = self.tabel
        t.setRowCount(len(pilih))
        for r, (nama, s, _) in enumerate(pilih):
            st = G.statistik(s.y)
            t.setItem(r, 0, kit.sel(nama, rata_kanan=False))
            t.setItem(r, 1, kit.sel_angka(st.get("n"), 0))
            for c, k in ((2, "rerata"), (3, "sd"), (4, "min"), (5, "maks")):
                t.setItem(r, c, kit.sel_angka(st.get(k), 3))
            t.setItem(r, 6, kit.sel(f"{kit.f(st.get('rerata_2'), 3)} ± {kit.f(st.get('sd_2'), 3)}" if st else "–"))
        t.resizeColumnsToContents()

    # ------------------------------------------------------------ keluaran
    def _nama_dasar(self):
        return re.sub(r"[^\w.\-]+", "_", self.e_judul.text().strip() or "grafik").strip("._") or "grafik"

    def _svg_cetak(self):
        return self._svg_buat(self._terpilih(), False)

    def _simpan(self):
        if not self._terpilih():
            self.l_status.setText("Centang minimal satu seri.")
            return
        f = self.jw._path("Simpan grafik", f"{self._nama_dasar()}.svg",
                          "SVG (*.svg);;PDF (*.pdf);;PNG (*.png);;TIFF (*.tif)")
        if f:
            ext = f.lower().rsplit(".", 1)[-1]
            self.jw._simpan_svg(self._svg_cetak(), f, {"pdf": "pdf", "png": "png", "tif": "tif", "tiff": "tif"}
                                .get(ext, "svg"), LEBAR, TINGGI, mm=160, dpi=600)
            self.l_status.setText(f"Disimpan: {Path(f).name}")

    def _salin(self):
        if self._terpilih():
            self.jw._salin_svg(self._svg_cetak(), LEBAR, TINGGI, self.e_judul.text() or "Grafik")
            self.l_status.setText("Gambar grafik disalin ke papan klip.")

    def _komposer(self):
        if not self._terpilih():
            return
        if not getattr(self.jw, "komposer", None):
            self.jw.buka_komposer()
        self.jw.komposer.tambah({"nama": self.e_judul.text() or "Grafik", "jenis": "svg", "isi": self._svg_cetak(),
                                 "w": LEBAR, "h": TINGGI})
        self.l_status.setText("Grafik ditambahkan ke Komposer Figur.")

    def _csv(self):
        pilih = self._terpilih()
        if not pilih:
            return
        f = self.jw._path("Ekspor data grafik", f"{self._nama_dasar()}.csv", "CSV (*.csv)")
        if f:
            from ..core.impor_grafik import Seri
            seri = [Seri(nama, s.x, s.y, s.berkas) for nama, s, _ in pilih]
            Path(f).write_text(G.csv_teks(seri, self.e_x.text() or "x"), encoding="utf-8")
            self.l_status.setText(f"Data diekspor: {Path(f).name}")
