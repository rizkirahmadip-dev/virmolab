"""Tab Sifat Ligan: deskriptor, aturan drug-likeness, peringatan PAINS/Brenk, dan BOILED-Egg."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QHeaderView, QLabel, QPushButton, QSplitter, QToolBar, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core import sifat
from ..core.laporan import id_angka
from . import theme
from .panel_interaksi import KanvasSvg

KOLOM = ["#", "Ligan", "ΔG terbaik", "MW", "WLOGP", "TPSA", "Donor H", "Akseptor H", "Rotasi", "QED",
         "SA Score", "Lipinski", "Ghose", "Veber", "Egan", "Muegge", "GI", "BBB", "PAINS", "Brenk"]
KUNCI = [None, "nama", "dg", "mw", "wlogp", "tpsa", "hbd", "hba", "rotb", "qed",
         "sascore", "lipinski", "ghose", "veber", "egan", "muegge", "gi", "bbb", "pains", "brenk"]
NUM = {0, 2, 3, 4, 5, 6, 7, 8, 9, 10}
ATURAN = {"lipinski", "ghose", "veber", "egan", "muegge", "gi", "bbb"}


class _Item(QTreeWidgetItem):
    def __lt__(self, lain):
        k = self.treeWidget().sortColumn() if self.treeWidget() else 0
        a, b = self.data(k, Qt.UserRole), lain.data(k, Qt.UserRole)
        if k in NUM:
            a = 1e9 if a is None else a
            b = 1e9 if b is None else b
            return a < b
        return str(a if a is not None else self.text(k)).lower() < str(b if b is not None else lain.text(k)).lower()


class TabSifat(QWidget):
    minta = Signal()            # hitung/muat ulang
    ekspor = Signal(str)        # salin | svg | png | csv

    def __init__(self):
        super().__init__()
        self.mode = "terang"
        self.data = []          # [(nama, sifat dict, dg)]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QToolBar()
        self.l_n = QLabel("")
        self.l_n.setObjectName("muted")
        bar.addWidget(self.l_n)
        self.c_label = QCheckBox("Nomor titik")
        self.c_label.setChecked(True)
        self.c_label.toggled.connect(self._gambar)
        bar.addWidget(QLabel("   "))
        bar.addWidget(self.c_label)
        sp = QWidget()
        sp.setSizePolicy(sp.sizePolicy().horizontalPolicy().Expanding, sp.sizePolicy().verticalPolicy().Preferred)
        bar.addWidget(sp)
        b = QPushButton("Hitung ulang")
        b.setToolTip("Hitung ulang sifat semua ligan")
        b.clicked.connect(self.minta)
        bar.addWidget(b)
        for k, t in (("salin", "Salin grafik"), ("csv", "Simpan tabel CSV…"), ("svg", "Simpan grafik SVG/PDF…"),
                     ("png", "Simpan grafik PNG/TIFF…")):
            b = QPushButton(t)
            b.clicked.connect(lambda _=False, k=k: self.ekspor.emit(k))
            bar.addWidget(b)
        lay.addWidget(bar)

        bagi = QSplitter(Qt.Horizontal)
        kiri = QWidget()
        kl = QVBoxLayout(kiri)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.setSpacing(0)
        self.pohon = QTreeWidget()
        self.pohon.setColumnCount(len(KOLOM))
        self.pohon.setHeaderLabels(KOLOM)
        self.pohon.setRootIsDecorated(False)
        self.pohon.setSortingEnabled(True)
        self.pohon.setUniformRowHeights(True)
        h = self.pohon.header()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Interactive)
        h.setStretchLastSection(False)
        for i, t in enumerate(("Nomor titik di grafik", "", "ΔG pose terbaik dari semua job (kcal/mol)",
                               "Massa molekul (g/mol)", "Lipofilisitas Wildman-Crippen", "Luas permukaan polar (Å²)",
                               "", "", "Ikatan rotasi", "Kemiripan obat (0-1)",
                               "Skor kemudahan sintesis (1 mudah - 10 sulit, Ertl 2009; ≤ 3 hijau, 3-6 kuning, > 6 merah)",
                               "Ya = ≤ 1 pelanggaran (angka = jumlah pelanggaran)", "", "", "", "",
                               "Absorpsi saluran cerna (BOILED-Egg)", "Menembus sawar darah otak (BOILED-Egg)",
                               "Substruktur pengganggu uji", "Gugus kimia tak diinginkan")):
            if t:
                self.pohon.headerItem().setToolTip(i, t)
        self.pohon.currentItemChanged.connect(lambda *_: self._pilih())
        kl.addWidget(self.pohon, 1)
        self.l_detail = QLabel("")
        self.l_detail.setWordWrap(True)
        self.l_detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.l_detail.setContentsMargins(8, 6, 8, 6)
        kl.addWidget(self.l_detail)
        bagi.addWidget(kiri)
        self.kanvas = KanvasSvg()
        bagi.addWidget(self.kanvas)
        bagi.setStretchFactor(0, 3)
        bagi.setStretchFactor(1, 2)
        lay.addWidget(bagi, 1)
        cat = QLabel("Sifat dihitung RDKit dari struktur netral (fragmen terbesar). WLOGP dipakai untuk semua aturan "
                     "(SwissADME memakai MLOGP untuk Lipinski & XLOGP3 untuk Muegge - nilai bisa sedikit berbeda). "
                     "Prediksi in silico; bukan pengganti uji farmakokinetik. Kriteria lengkap: arahkan kursor ke judul "
                     "kolom atau lihat Bantuan › Dokumentasi › Metode dan kriteria.")
        cat.setObjectName("muted")
        cat.setWordWrap(True)
        cat.setContentsMargins(8, 4, 8, 4)
        lay.addWidget(cat)
        self.l_kosong = QLabel("Belum ada ligan. Tambahkan ligan di langkah 2 (Ambil dari PubChem, SMILES, atau berkas).")
        self.l_kosong.setObjectName("muted")
        self.l_kosong.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.l_kosong)

    # ------------------------------------------------------------- isi
    def muat(self, data):
        """data: [(nama, sifat dict | str galat, dg | None)]."""
        t = theme.TOKEN[self.mode]
        self.data = [d for d in data if isinstance(d[1], dict)]
        gagal = [d for d in data if not isinstance(d[1], dict)]
        self.pohon.setSortingEnabled(False)
        self.pohon.clear()
        for i, (nama, s, dg) in enumerate(self.data):
            it = _Item(self.pohon)
            it.setData(0, Qt.UserRole + 1, i)
            for k, kunci in enumerate(KUNCI):
                if kunci is None:
                    v, teks = i + 1, str(i + 1)
                elif kunci == "nama":
                    v, teks = nama, nama
                elif kunci == "dg":
                    v, teks = dg, "" if dg is None else id_angka(f"{dg:.2f}")
                elif kunci in ATURAN or kunci in ("pains", "brenk"):
                    teks = sifat.sel(s, kunci)
                    v = teks
                else:
                    v = s.get(kunci)
                    teks = "" if v is None else (id_angka(f"{v:.3f}") if kunci == "qed" else
                                                 id_angka(f"{v:.2f}") if isinstance(v, float) else str(v))
                it.setData(k, Qt.UserRole, v)
                it.setText(k, teks)
                if k in NUM:
                    it.setTextAlignment(k, Qt.AlignRight | Qt.AlignVCenter)
                if kunci == "sascore" and isinstance(v, (int, float)):
                    if v <= 3.0:
                        it.setForeground(k, QColor(t["ok"]))
                    elif v <= 6.0:
                        it.setForeground(k, QColor(t["warn"]))
                    else:
                        it.setForeground(k, QColor(t["bad"]))
                    from ..core import sascore
                    it.setToolTip(k, sascore.keterangan(v))
                if kunci in ATURAN:
                    baik = s["gi"] if kunci == "gi" else s["bbb"] if kunci == "bbb" else s[f"{kunci}_ok"]
                    if kunci != "bbb":   # BBB bukan "baik/buruk", tergantung target
                        it.setForeground(k, QColor(t["ok"] if baik else t["bad"]))
                    alasan = s.get(f"{kunci}_alasan")
                    if alasan:
                        it.setToolTip(k, "; ".join(alasan))
                if kunci in ("pains", "brenk") and s[kunci]:
                    it.setForeground(k, QColor(t["warn"]))
                    it.setToolTip(k, "\n".join(s[kunci]))
            it.setToolTip(1, s.get("smiles", ""))
        for nama, galat, _dg in gagal:
            it = _Item(self.pohon)
            it.setText(1, nama)
            it.setText(3, f"gagal: {galat}")
            it.setForeground(3, QColor(t["bad"]))
        self.pohon.setSortingEnabled(True)
        self.pohon.sortItems(0, Qt.AscendingOrder)
        self.pohon.resizeColumnToContents(1)
        self.pohon.setColumnWidth(1, min(self.pohon.columnWidth(1), 220))
        n_gi = sum(1 for _, s, _ in self.data if s["gi"])
        n_lip = sum(1 for _, s, _ in self.data if s["lipinski_ok"])
        self.l_n.setText(f"{len(self.data)} ligan · Lipinski {n_lip}/{len(self.data)} · GI tinggi {n_gi}/{len(self.data)}"
                         + (f" · {len(gagal)} gagal" if gagal else ""))
        self.l_kosong.setVisible(not data)
        self.l_detail.setText("")
        self._gambar()

    def indeks_terpilih(self):
        it = self.pohon.currentItem()
        return it.data(0, Qt.UserRole + 1) if it else None

    def svg(self, gelap=None, judul="", transparan=False):
        titik = [(n, s["tpsa"], s["wlogp"]) for n, s, _ in self.data]
        g = (self.mode == "gelap") if gelap is None else gelap
        return sifat.boiled_egg_svg(titik, gelap=g, label=self.c_label.isChecked(), pilih=self.indeks_terpilih(),
                                    judul=judul, transparan=transparan) if titik else ""

    def _gambar(self, *_):
        self.kanvas.latar = QColor(theme.TOKEN[self.mode]["surf"])
        self.kanvas.set_svg(self.svg())

    def _pilih(self):
        i = self.indeks_terpilih()
        if i is None or i >= len(self.data):
            self.l_detail.setText("")
        else:
            nama, s, _ = self.data[i]
            baris = sifat.ringkas_alasan(s) or ["Tidak ada pelanggaran aturan dan tidak ada peringatan struktur."]
            self.l_detail.setText(f"<b>{nama}</b> · {s['rumus']} · SMILES netral: {s['smiles']}<br>"
                                  + "<br>".join(baris))
        self._gambar()

    def set_mode(self, mode):
        self.mode = mode
        if self.data:
            self.muat([(n, s, d) for n, s, d in self.data])
        else:
            self._gambar()
