"""Dialog residu fleksibel: pilih rantai samping kantong yang boleh bergerak saat docking (Vina --flex, AD-GPU --flexres).

Calon = residu yang punya atom rantai samping di dalam grid box, diurutkan menurut jarak ke ligan acuan (ligan asli
kristal bila ada) atau ke pusat kotak. Gly/Ala/Pro tidak punya torsi rantai samping yang berarti, jadi tidak ditawarkan.
"""
import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QDoubleSpinBox, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..core.laporan import id_angka
from ..core.prep_reseptor import MAKS_FLEKSIBEL

# perkiraan torsi rantai samping (termasuk CA–CB) per residu, untuk estimasi ruang pencarian
TORSI = {"SER": 2, "THR": 2, "CYS": 2, "VAL": 1, "ILE": 2, "LEU": 2, "ASP": 2, "ASN": 2, "GLU": 3, "GLN": 3,
         "HIS": 2, "HID": 2, "HIE": 2, "HIP": 2, "PHE": 2, "TYR": 3, "TRP": 2, "MET": 3, "LYS": 4, "ARG": 4,
         "ASH": 2, "GLH": 3, "LYN": 4, "CYX": 2}
TULANG = {"N", "CA", "C", "O", "OXT"}


def calon_residu(teks_pdb, pusat, ukuran, acuan=None, radius=None):
    """[(rantai, resi, resn, jarak_min)] residu dengan atom rantai samping di dalam kotak.
    acuan: daftar koordinat ligan (jarak dihitung ke atom ligan terdekat); tanpa acuan: ke pusat kotak."""
    per = {}
    for b in teks_pdb.splitlines():
        if not b.startswith("ATOM"):
            continue
        nama, resn = b[12:16].strip(), b[17:20].strip()
        if nama in TULANG or resn not in TORSI or nama.startswith("H"):
            continue
        try:
            xyz = (float(b[30:38]), float(b[38:46]), float(b[46:54]))
            k = (b[21].strip(), int(b[22:26]), resn)
        except ValueError:
            continue
        if not all(abs(xyz[i] - pusat[i]) <= ukuran[i] / 2 for i in range(3)):
            continue
        titik = acuan or [pusat]
        d = min(math.dist(xyz, t) for t in titik)
        per[k] = min(per.get(k, 1e9), d)
    hasil = [(c, i, n, d) for (c, i, n), d in per.items() if radius is None or d <= radius]
    return sorted(hasil, key=lambda x: x[3])


class DialogFleksibel(QDialog):
    def __init__(self, teks_pdb, kotak, acuan=None, nama_acuan="", terpilih=(), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Residu fleksibel")
        self.setMinimumSize(520, 520)
        self.teks, self.kotak, self.acuan = teks_pdb, kotak, acuan
        self.matikan = False
        v = QVBoxLayout(self)
        ket = QLabel("Rantai samping yang dicentang boleh berotasi selama docking (induced fit terbatas). "
                     "Pilih 2–6 residu kantong yang paling dekat dengan ligan; makin banyak residu, ruang pencarian "
                     "membesar cepat dan hasil makin bergantung pada exhaustiveness/jumlah run. "
                     "Didukung AutoDock-GPU dan Vina (bukan AutoDock4).")
        ket.setWordWrap(True)
        ket.setObjectName("muted")
        v.addWidget(ket)
        h = QHBoxLayout()
        h.addWidget(QLabel(("Jarak ke " + nama_acuan) if acuan else "Jarak ke pusat kotak"))
        self.sp = QDoubleSpinBox()
        self.sp.setRange(2.0, 30.0)
        self.sp.setValue(5.0 if acuan else 10.0)
        self.sp.setSuffix(" Å")
        self.sp.setDecimals(1)
        self.sp.valueChanged.connect(self._isi)
        h.addWidget(self.sp)
        h.addStretch(1)
        v.addLayout(h)
        self.tabel = QTableWidget(0, 3)
        self.tabel.setHorizontalHeaderLabels(["Residu", "Jarak (Å)", "Torsi ± "])
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabel.horizontalHeader().setStretchLastSection(True)
        self.tabel.itemChanged.connect(self._hitung)
        v.addWidget(self.tabel, 1)
        self.l_info = QLabel()
        self.l_info.setWordWrap(True)
        v.addWidget(self.l_info)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Terapkan")
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText("Batal")
        if terpilih:
            b = QPushButton("Kembali ke reseptor kaku")
            b.clicked.connect(self._matikan)
            bb.addButton(b, QDialogButtonBox.ResetRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._pilih = set(terpilih)
        self._isi()

    def _matikan(self):
        self.matikan = True
        self.accept()

    def _isi(self, *_):
        for r in range(self.tabel.rowCount()):    # simpan centang baris yang sedang tampil sebelum diisi ulang
            it = self.tabel.item(r, 0)
            (self._pilih.add if it.checkState() == Qt.Checked else self._pilih.discard)(it.data(Qt.UserRole))
        self.tabel.blockSignals(True)
        self.tabel.setRowCount(0)
        for c, i, n, d in calon_residu(self.teks, self.kotak["pusat"], self.kotak["ukuran"], self.acuan,
                                       self.sp.value()):
            r = self.tabel.rowCount()
            self.tabel.insertRow(r)
            it = QTableWidgetItem(f"{n} {i} {c}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if f"{c}:{i}" in self._pilih else Qt.Unchecked)
            it.setData(Qt.UserRole, f"{c}:{i}")
            it.setData(Qt.UserRole + 1, TORSI.get(n, 2))
            self.tabel.setItem(r, 0, it)
            self.tabel.setItem(r, 1, QTableWidgetItem(id_angka(f"{d:.1f}")))
            self.tabel.setItem(r, 2, QTableWidgetItem(str(TORSI.get(n, 2))))
        self.tabel.blockSignals(False)
        self.tabel.resizeColumnsToContents()
        self._hitung()

    def residu(self):
        out = []
        for r in range(self.tabel.rowCount()):
            it = self.tabel.item(r, 0)
            if it.checkState() == Qt.Checked:
                out.append(it.data(Qt.UserRole))
        return out

    def _hitung(self, *_):
        pilih = [self.tabel.item(r, 0) for r in range(self.tabel.rowCount())
                 if self.tabel.item(r, 0).checkState() == Qt.Checked]
        t = sum(int(it.data(Qt.UserRole + 1)) for it in pilih)
        teks = f"{len(pilih)} residu dipilih · ± {t} torsi tambahan."
        warna = ""
        if len(pilih) > MAKS_FLEKSIBEL:
            teks += f" Maksimal {MAKS_FLEKSIBEL} residu."
            warna = "#c0392b"
        elif len(pilih) > 6 or t > 12:
            teks += " Banyak residu: naikkan exhaustiveness Vina (≥ 32) atau jumlah run AD-GPU (≥ 100)."
            warna = "#c98a12"
        if not self.tabel.rowCount():
            teks = "Tidak ada residu dengan rantai samping fleksibel dalam jarak ini. Perbesar jarak atau periksa grid box."
        self.l_info.setText(teks)
        self.l_info.setStyleSheet(f"color: {warna};" if warna else "")
