"""Tab Hasil: satu baris per ligan per job (pose terbaik), dapat diperluas ke semua pose."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import theme

KOLOM = ["#", "Ligan", "ΔG (kcal/mol)", "Ki perkiraan", "LE", "Klaster", "RMSD kristal (Å)", "RMSD ref (Å)",
         "H", "HF", "π", "Lain", "Mesin", "Job"]
NUM = {0, 2, 4, 5, 6, 7, 8, 9, 10, 11}


class ItemAngka(QTreeWidgetItem):
    """Sortir numerik untuk kolom angka (sel kosong di akhir)."""

    def __lt__(self, lain):
        k = self.treeWidget().sortColumn() if self.treeWidget() else 0
        if k in NUM:
            a, b = self.data(k, Qt.UserRole), lain.data(k, Qt.UserRole)
            a = 1e9 if a is None else a
            b = 1e9 if b is None else b
            return a < b
        return self.text(k).lower() < lain.text(k).lower()


class PanelHasil(QWidget):
    bukaPose = Signal(str, str, int)        # id job, id ligan, peringkat pose (1 = terbaik)
    bandingkan = Signal(list)               # [(id job, id ligan)]
    petaInteraksi = Signal()
    ekspor = Signal()

    def __init__(self):
        super().__init__()
        self.mode = "terang"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 6, 8, 6)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Cari ligan / job")
        self.filter.setClearButtonEnabled(True)
        self.filter.setMaximumWidth(260)
        self.filter.textChanged.connect(self._saring)
        self.sp_dg = QLineEdit()
        self.sp_dg.setPlaceholderText("ΔG ≤ (mis. -8)")
        self.sp_dg.setToolTip("Tampilkan hanya ligan dengan ΔG ≤ nilai ini (kosong = semua)")
        self.sp_dg.setMaximumWidth(130)
        self.sp_dg.textChanged.connect(self._saring)
        self.l_n = QLabel("")
        self.l_n.setObjectName("muted")
        self.b_banding = QPushButton("Bandingkan")
        self.b_banding.setToolTip("Centang 2–4 ligan di kolom pertama")
        self.b_banding.clicked.connect(self._banding)
        b_peta = QPushButton("Peta interaksi")
        b_peta.setToolTip("Peta panas residu × ligan untuk semua hasil")
        b_peta.clicked.connect(self.petaInteraksi)
        b_eks = QPushButton("Ekspor…")
        b_eks.clicked.connect(self.ekspor)
        for w in (self.filter, self.sp_dg, self.l_n):
            bl.addWidget(w)
        bl.addStretch(1)
        for w in (self.b_banding, b_peta, b_eks):
            bl.addWidget(w)
        lay.addWidget(bar)
        self.pohon = QTreeWidget()
        self.pohon.setColumnCount(len(KOLOM))
        self.pohon.setHeaderLabels(KOLOM)
        self.pohon.setSortingEnabled(True)
        self.pohon.setUniformRowHeights(True)
        self.pohon.setIndentation(14)
        self.pohon.setAlternatingRowColors(False)
        h = self.pohon.header()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setStretchLastSection(False)
        self.pohon.itemDoubleClicked.connect(self._klik)
        self.pohon.itemActivated.connect(self._klik)
        self.pohon.itemChanged.connect(lambda *_: self._hitung_centang())
        lay.addWidget(self.pohon, 1)
        cat = QLabel("Hasil docking adalah prediksi komputasi, bukan bukti aktivitas biologis; konfirmasi dengan "
                     "uji eksperimen. Ki dihitung dari ΔG (perkiraan, 298 K). LE = −ΔG / atom berat. "
                     "H = ikatan hidrogen, HF = hidrofobik, π = π–π, Lain = π–kation, garam, halogen, logam. "
                     "Klik dua kali baris untuk memuat pose.")
        cat.setObjectName("muted")
        cat.setWordWrap(True)
        cat.setContentsMargins(8, 4, 8, 4)
        lay.addWidget(cat)

    def _sel(self, it, k, v, fmt="{:.2f}"):
        it.setData(k, Qt.UserRole, v)
        it.setText(k, "" if v is None else (fmt.format(v) if isinstance(v, float) else str(v)))
        if k in NUM:
            it.setTextAlignment(k, Qt.AlignRight | Qt.AlignVCenter)

    def muat(self, baris):
        """baris: dari core.ekspor.baris_hasil."""
        t = theme.TOKEN[self.mode]
        self.pohon.blockSignals(True)
        self.pohon.setSortingEnabled(False)
        self.pohon.clear()
        for b in baris:
            it = ItemAngka(self.pohon)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(0, Qt.Unchecked)
            it.setData(1, Qt.UserRole + 1, (b["job"], b["lid"]))
            self._sel(it, 0, b["peringkat"])
            it.setText(1, b["ligan"])
            self._sel(it, 2, b["energi"])
            it.setText(3, b["ki"] or "")
            self._sel(it, 4, b["le"], "{:.3f}")
            self._sel(it, 5, b["klaster"])
            self._sel(it, 6, b["rmsd_kristal"])
            if b["rmsd_kristal"] is not None:
                it.setForeground(6, QColor(t["ok"] if b["rmsd_kristal"] <= 2.0 else t["bad"]))
                it.setToolTip(6, "≤ 2,0 Å: redocking valid" if b["rmsd_kristal"] <= 2.0 else "> 2,0 Å: tidak valid")
            self._sel(it, 7, b["rmsd"])
            self._sel(it, 8, b["hbond"])
            self._sel(it, 9, b["hidrofobik"])
            self._sel(it, 10, b["pi"])
            self._sel(it, 11, b["pikation"] + b["garam"] + b["halogen"] + b["logam"])
            it.setText(12, b["mesin"])
            it.setText(13, b["job"])
            for p in b["pose"]:
                c = ItemAngka(it)
                c.setData(1, Qt.UserRole + 1, (b["job"], b["lid"], p["peringkat"]))
                c.setText(1, f"Pose {p['peringkat']}")
                self._sel(c, 2, p["energi"])
                self._sel(c, 5, p.get("klaster") or None)
                self._sel(c, 6, p.get("rmsd_kristal"))
                self._sel(c, 7, p["rmsd_ref"] if p.get("rmsd_ref", -1) >= 0 else
                          (p.get("rmsd_lb") if p.get("peringkat", 1) > 1 else None))
                for k in range(len(KOLOM)):
                    c.setForeground(k, QColor(t["ink2"]))
        self.pohon.setSortingEnabled(True)
        self.pohon.sortItems(2, Qt.AscendingOrder)
        self.pohon.blockSignals(False)
        self._saring()
        self._hitung_centang()

    def _saring(self, *_):
        teks = self.filter.text().lower().strip()
        try:
            batas = float(self.sp_dg.text().replace(",", ".").strip())
        except ValueError:
            batas = None
        n = 0
        for i in range(self.pohon.topLevelItemCount()):
            it = self.pohon.topLevelItem(i)
            e = it.data(2, Qt.UserRole)
            tampil = (not teks or teks in it.text(1).lower() or teks in it.text(13).lower()) and \
                     (batas is None or (e is not None and e <= batas))
            it.setHidden(not tampil)
            n += tampil
        self.l_n.setText(f"{n} ligan")

    def _hitung_centang(self):
        n = len(self.dicentang())
        self.b_banding.setText(f"Bandingkan ({n})" if n else "Bandingkan")
        self.b_banding.setEnabled(2 <= n <= 4)

    def dicentang(self):
        hasil = []
        for i in range(self.pohon.topLevelItemCount()):
            it = self.pohon.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                hasil.append(it.data(1, Qt.UserRole + 1))
        return hasil

    def _banding(self):
        self.bandingkan.emit(self.dicentang())

    def _klik(self, it, _k=0):
        d = it.data(1, Qt.UserRole + 1)
        if d:
            self.bukaPose.emit(d[0], d[1], d[2] if len(d) > 2 else 1)

    def terpilih(self):
        """(job, lid, peringkat) baris aktif."""
        it = self.pohon.currentItem()
        d = it.data(1, Qt.UserRole + 1) if it else None
        if not d:
            return None
        return (d[0], d[1], d[2] if len(d) > 2 else 1)
