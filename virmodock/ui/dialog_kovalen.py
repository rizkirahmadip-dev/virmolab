"""Dialog docking kovalen: pilih residu nukleofil (Cys/Ser/Lys) di dalam grid box dan lihat gugus reaktif tiap ligan.

Ligan direaksikan otomatis dengan rantai samping residu (lihat core/kovalen.py); ligan tanpa gugus reaktif yang cocok
dilewati saat docking. Hanya AutoDock-GPU.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ..core import kovalen as K
from ..core.laporan import id_angka

MAKS_PRATINJAU = 60


class DialogKovalen(QDialog):
    def __init__(self, teks_pdb, kotak, ligan=(), terpilih=None, parent=None):
        """ligan: [(nama, teks_pdbqt)] ligan siap docking untuk pratinjau gugus reaktif."""
        super().__init__(parent)
        self.setWindowTitle("Docking kovalen")
        self.setMinimumSize(620, 600)
        self.matikan = False
        self._ligan = list(ligan)[:MAKS_PRATINJAU]
        self._lebih = max(0, len(ligan) - MAKS_PRATINJAU)
        self._mol = {}
        v = QVBoxLayout(self)
        ket = QLabel("Ligan dengan gugus reaktif (warhead) diikat ke rantai samping residu yang dipilih, lalu "
                     "di-docking sebagai satu aduk residu + ligan (metode tethered, AutoDock-GPU). Didukung: "
                     "Cys (akseptor Michael, haloasetamida, nitril, aldehida), Ser (nitril, aldehida, sulfonil "
                     "fluorida), Lys (akseptor Michael, sulfonil fluorida, aldehida → basa Schiff). "
                     "Skor yang dilaporkan bukan ΔG ikatan dan tidak sebanding dengan docking non-kovalen.")
        ket.setWordWrap(True)
        ket.setObjectName("muted")
        v.addWidget(ket)
        v.addWidget(QLabel("Residu sasaran (atom nukleofil di dalam grid box)"))
        self.t_res = QTableWidget(0, 3)
        self.t_res.setHorizontalHeaderLabels(["Residu", "Atom nukleofil", "Jarak ke pusat kotak (Å)"])
        self._siapkan(self.t_res)
        self.t_res.setMinimumHeight(170)
        self.t_res.itemSelectionChanged.connect(self._pratinjau)
        v.addWidget(self.t_res, 2)
        self.l_lig = QLabel("Gugus reaktif ligan")
        v.addWidget(self.l_lig)
        self.t_lig = QTableWidget(0, 2)
        self.t_lig.setHorizontalHeaderLabels(["Ligan", "Gugus reaktif terdeteksi"])
        self._siapkan(self.t_lig)
        v.addWidget(self.t_lig, 2)
        self.l_info = QLabel()
        self.l_info.setWordWrap(True)
        v.addWidget(self.l_info)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.b_ok = bb.button(QDialogButtonBox.Ok)
        self.b_ok.setText("✓ Aktifkan docking kovalen")
        self.b_ok.setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText("✕ Batal")
        if terpilih:
            b = QPushButton("✕ Matikan (docking biasa)")
            b.clicked.connect(self._matikan)
            bb.addButton(b, QDialogButtonBox.ResetRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        for c, i, n, d in K.calon_residu(teks_pdb, kotak["pusat"], kotak["ukuran"]):
            r = self.t_res.rowCount()
            self.t_res.insertRow(r)
            it = QTableWidgetItem(f"{n} {i} {c}")
            it.setData(Qt.UserRole, (f"{c}:{i}", n))
            self.t_res.setItem(r, 0, it)
            self.t_res.setItem(r, 1, QTableWidgetItem(K.RESIDU[n][0][-1]))
            self.t_res.setItem(r, 2, QTableWidgetItem(id_angka(f"{d:.1f}")))
            if terpilih and f"{c}:{i}" == terpilih:
                self.t_res.selectRow(r)
        self.t_res.resizeColumnsToContents()
        if self.t_res.rowCount() and not self.t_res.selectedItems():
            self.t_res.selectRow(0)
        self._pratinjau()

    @staticmethod
    def _siapkan(t):
        t.verticalHeader().setVisible(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.horizontalHeader().setStretchLastSection(True)

    def _matikan(self):
        self.matikan = True
        self.accept()

    def pilihan(self):
        """('A:12', 'CYS') atau None."""
        it = self.t_res.selectedItems()
        return self.t_res.item(it[0].row(), 0).data(Qt.UserRole) if it else None

    def _mol_ligan(self, nama, teks):
        if nama not in self._mol:
            from ..core import analisis
            try:
                badan = "\n".join(b for b in teks.splitlines() if not b.startswith("REMARK"))
                self._mol[nama] = analisis.pose_mol(teks, badan)
            except Exception:
                self._mol[nama] = None
        return self._mol[nama]

    def _pratinjau(self):
        p = self.pilihan()
        self.t_lig.setRowCount(0)
        if not self.t_res.rowCount():
            self.l_info.setText("Tidak ada Cys, Ser, atau Lys dengan atom nukleofil di dalam grid box. Pindahkan atau "
                                "perbesar kotak sehingga mencakup residu sasaran.")
            self.l_info.setStyleSheet("color: #c0392b;")
            self.b_ok.setEnabled(False)
            return
        self.b_ok.setEnabled(p is not None)
        if p is None:
            return
        _rid, resn = p
        cocok = 0
        for nama, teks in self._ligan:
            mol = self._mol_ligan(nama, teks)
            wh = K.deteksi(mol, resn) if mol is not None else []
            r = self.t_lig.rowCount()
            self.t_lig.insertRow(r)
            self.t_lig.setItem(r, 0, QTableWidgetItem(nama))
            if mol is None:
                it = QTableWidgetItem("molekul tidak terbaca - akan dilewati")
            elif wh:
                cocok += 1
                it = QTableWidgetItem(wh[0][1] + (f" (+{len(wh) - 1} lain; yang pertama dipakai)" if len(wh) > 1 else ""))
            else:
                it = QTableWidgetItem("tidak ada - akan dilewati")
            if mol is None or not wh:
                it.setForeground(Qt.gray)
            self.t_lig.setItem(r, 1, it)
        self.t_lig.resizeColumnToContents(0)
        n = len(self._ligan)
        self.l_lig.setText(f"Gugus reaktif ligan untuk {resn}" + (f" ({n} pertama dari {n + self._lebih})"
                                                                  if self._lebih else ""))
        if not n:
            teks, warna = "Belum ada ligan siap; gugus reaktif diperiksa saat docking dijalankan.", "#c98a12"
        elif cocok:
            teks, warna = f"{cocok} dari {n} ligan punya gugus reaktif untuk {resn}.", ""
        else:
            teks, warna = (f"Tidak ada ligan yang punya gugus reaktif untuk {resn}; docking kovalen akan melewati "
                           "semua ligan."), "#c98a12"
        self.l_info.setText(teks + " Docking kovalen memakai AutoDock-GPU dan menonaktifkan residu fleksibel.")
        self.l_info.setStyleSheet(f"color: {warna};" if warna else "")
