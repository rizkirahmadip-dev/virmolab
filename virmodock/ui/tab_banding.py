"""Perbandingan ligan (viewport 2×2) dan peta panas interaksi residu × ligan."""
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QGridLayout, QHeaderView, QLabel, QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QToolBar, QVBoxLayout, QWidget)

from ..core.analisis import NAMA_JENIS, SINGKAT, URUT_JENIS
from . import theme
from .viewer_widget import Viewer


def _kunci_residu(label):
    m = re.match(r"(\w+) (-?\d+)\s*(\S*)", label)
    return (m.group(3), int(m.group(2))) if m else ("", 0)


class PetaPanas(QTableWidget):
    """Baris = ligan (urut ΔG), kolom = residu (urut rantai, nomor). Sel = jenis interaksi terkuat."""

    def __init__(self):
        super().__init__()
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setShowGrid(True)
        self.verticalHeader().setDefaultSectionSize(22)
        self.horizontalHeader().setDefaultSectionSize(44)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.mode = "terang"

    def muat(self, baris):
        """baris: [(nama ligan, ΔG, {residu: jenis})]"""
        semua = sorted({r for _, _, res in baris for r in res}, key=_kunci_residu)
        self.clear()
        self.setRowCount(len(baris))
        self.setColumnCount(len(semua))
        self.setHorizontalHeaderLabels([r.replace(" ", "\n", 1) for r in semua])
        self.horizontalHeader().setMinimumHeight(52)
        self.setVerticalHeaderLabels([f"{n}  ({e:.2f})" for n, e, _ in baris])
        t = theme.TOKEN[self.mode]
        for i, (_n, _e, res) in enumerate(baris):
            for k, r in enumerate(semua):
                j = res.get(r)
                it = QTableWidgetItem(SINGKAT.get(j, "") if j else "")
                it.setTextAlignment(Qt.AlignCenter)
                if j:
                    w = QColor(theme.INTERAKSI.get(j, t["mut"]))
                    if j in ("vdw", "hidrofobik"):
                        w.setAlpha(110)
                    it.setBackground(w)
                    it.setForeground(QColor("#ffffff") if j not in ("vdw",) else QColor(t["ink"]))
                    it.setToolTip(f"{r}: {NAMA_JENIS.get(j, j)}")
                self.setItem(i, k, it)
        # residu yang sering berinteraksi
        return semua


class TabBanding(QWidget):
    samakan = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QToolBar()
        b = QPushButton("Samakan sudut pandang dengan viewport utama")
        b.clicked.connect(self.samakan)
        bar.addWidget(b)
        self.l_info = QLabel("")
        self.l_info.setObjectName("muted")
        bar.addWidget(self.l_info)
        lay.addWidget(bar)
        sp = QSplitter(Qt.Vertical)
        self.w_grid = QWidget()
        self.grid = QGridLayout(self.w_grid)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(4)
        self.viewer = []
        self.label = []
        sp.addWidget(self.w_grid)
        bawah = QWidget()
        bl = QVBoxLayout(bawah)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        leg = QLabel("  ".join(f"{SINGKAT[j]} = {NAMA_JENIS[j]}" for j in URUT_JENIS))
        leg.setObjectName("muted")
        leg.setContentsMargins(8, 4, 8, 4)
        bl.addWidget(leg)
        self.peta = PetaPanas()
        bl.addWidget(self.peta)
        sp.addWidget(bawah)
        sp.setSizes([600, 220])
        lay.addWidget(sp, 1)

    def siapkan(self, n):
        """Pastikan ada n viewport (dibuat sekali, dipakai ulang)."""
        while len(self.viewer) < n:
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            l = QLabel("")
            l.setObjectName("sech")
            vw = Viewer()
            v.addWidget(l)
            v.addWidget(vw, 1)
            i = len(self.viewer)
            self.grid.addWidget(w, i // 2, i % 2)
            self.viewer.append(vw)
            self.label.append(l)
        for i, vw in enumerate(self.viewer):
            vw.parentWidget().setVisible(i < n)
        return self.viewer[:n]
