"""Dialog preparasi reseptor."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from ..core.prep_reseptor import OpsiReseptor


class DialogReseptor(QDialog):
    def __init__(self, protein, ada_logam, parent=None, aktif=None):
        """protein: daftar Objek protein; ada_logam: {id protein: [nama ion logam]}."""
        super().__init__(parent)
        self.setWindowTitle("Siapkan reseptor")
        self.setMinimumWidth(480)
        self.protein = protein
        self.ada_logam = ada_logam
        lay = QVBoxLayout(self)

        f = QFormLayout()
        self.cmb = QComboBox()
        for o in protein:
            self.cmb.addItem(f"{o.nama}  ·  {o.info.get('atom', '')} atom", o.id)
        if aktif:
            self.cmb.setCurrentIndex(max(0, self.cmb.findData(aktif)))
        self.cmb.currentIndexChanged.connect(self._isi_rantai)
        f.addRow("Protein", self.cmb)
        self.w_rantai = QWidget()
        self.l_rantai = QHBoxLayout(self.w_rantai)
        self.l_rantai.setContentsMargins(0, 0, 0, 0)
        f.addRow("Rantai", self.w_rantai)
        lay.addLayout(f)

        g = QGroupBox("Pembersihan")
        v = QVBoxLayout(g)
        self.c_air = QCheckBox("Hapus molekul air")
        self.c_air.setChecked(True)
        self.c_lig = QCheckBox("Hapus ligan asli, aditif, dan ion non-logam")
        self.c_lig.setChecked(True)
        h = QHBoxLayout()
        self.c_logam = QCheckBox("Pertahankan ion logam (Zn, Mg, Ca, Mn, Fe, Cu, Co, Ni) dalam radius")
        self.c_logam.setChecked(True)
        self.sp_rad = QDoubleSpinBox()
        self.sp_rad.setRange(0, 50)
        self.sp_rad.setValue(8.0)
        self.sp_rad.setSuffix(" Å")
        self.sp_rad.setToolTip("Jarak dari ligan asli. 0 = semua ion logam dipertahankan.")
        h.addWidget(self.c_logam)
        h.addWidget(self.sp_rad)
        h.addStretch(1)
        v.addWidget(self.c_air)
        v.addWidget(self.c_lig)
        v.addLayout(h)
        self.l_logam = QLabel()
        self.l_logam.setObjectName("muted")
        v.addWidget(self.l_logam)
        f2 = QFormLayout()
        self.cmb_alt = QComboBox()
        self.cmb_alt.addItem("Okupansi tertinggi", "tertinggi")
        self.cmb_alt.addItem("Selalu altloc A", "A")
        f2.addRow("Konformasi alternatif", self.cmb_alt)
        v.addLayout(f2)
        lay.addWidget(g)

        g2 = QGroupBox("Hidrogen dan muatan")
        f3 = QFormLayout(g2)
        self.cmb_q = QComboBox()
        self.cmb_q.addItem("Gasteiger (dihitung Meeko)", "gasteiger")
        self.cmb_q.addItem("Muatan templat residu Meeko", "templat")
        self.cmb_q.addItem("Kollman (tidak tersedia)", "kollman")
        item = self.cmb_q.model().item(2)
        item.setEnabled(False)
        item.setToolTip("Muatan Kollman hanya ada di MGLTools (Python 2, tidak dibundel). "
                        "Gasteiger adalah standar Meeko untuk AutoDock-GPU dan Vina.")
        f3.addRow("Muatan parsial", self.cmb_q)
        lh = QLabel("Hidrogen polar ditambahkan sesuai templat residu (format PDBQT AutoDock).")
        lh.setObjectName("muted")
        lh.setWordWrap(True)
        f3.addRow(lh)
        lay.addWidget(g2)

        cat = QLabel("Residu yang atomnya tidak lengkap dibuang otomatis dan dilaporkan di panel Pesan. "
                     "Cadangan: Open Babel bila Meeko gagal.")
        cat.setObjectName("muted")
        cat.setWordWrap(True)
        lay.addWidget(cat)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Siapkan")
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText("Batal")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.cek_rantai = {}
        self._isi_rantai()

    def _isi_rantai(self):
        while self.l_rantai.count():
            w = self.l_rantai.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.cek_rantai = {}
        o = self.objek()
        for c, rs in (o.rantai if o else {}).items():
            cb = QCheckBox(f"{c} ({len(rs)})")
            cb.setChecked(True)
            self.l_rantai.addWidget(cb)
            self.cek_rantai[c] = cb
        self.l_rantai.addStretch(1)
        logam = self.ada_logam.get(o.id, []) if o else []
        self.l_logam.setText("Ion logam di struktur: " + (", ".join(logam) if logam else "tidak ada"))

    def objek(self):
        oid = self.cmb.currentData()
        return next((o for o in self.protein if o.id == oid), None)

    def opsi(self):
        rantai = [c for c, cb in self.cek_rantai.items() if cb.isChecked()]
        return OpsiReseptor(rantai=rantai if len(rantai) < len(self.cek_rantai) else None,
                            hapus_air=self.c_air.isChecked(), hapus_ligan=self.c_lig.isChecked(),
                            pertahankan_logam=self.c_logam.isChecked(), radius_logam=self.sp_rad.value(),
                            altloc=self.cmb_alt.currentData(), muatan=self.cmb_q.currentData())

    def accept(self):
        if not any(cb.isChecked() for cb in self.cek_rantai.values()):
            self.l_logam.setText("Pilih minimal satu rantai.")
            return
        super().accept()
