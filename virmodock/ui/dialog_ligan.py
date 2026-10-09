"""Dialog preparasi ligan (batch)."""
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ..core import molekul
from ..core.prep_ligan import OpsiLigan, dimorphite_tersedia, siapkan_banyak
from . import kerja, theme
from .dialogs import DialogAmbil


class DialogLigan(QDialog):
    """Sinyal `siap` membawa [(Objek sumber, HasilLigan)] untuk ligan yang berhasil."""
    siap = Signal(list)
    KOLOM = ["Nama", "Sumber", "Rumus", "MW", "Torsi", "Atom", "Status", "Keterangan"]

    def __init__(self, ligan, mode="terang", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Siapkan ligan")
        self.resize(900, 560)
        self.mode = mode
        self.baris = []          # [Objek]
        self.berjalan = False
        lay = QVBoxLayout(self)

        atas = QHBoxLayout()
        for teks, fn in (("Tambah berkas…", self._berkas), ("Tambah folder…", self._folder),
                         ("PubChem…", lambda: self._ambil(1)), ("SMILES…", lambda: self._ambil(2))):
            b = QPushButton(teks)
            b.clicked.connect(fn)
            atas.addWidget(b)
        atas.addStretch(1)
        self.c_semua = QCheckBox("Pilih semua")
        self.c_semua.setChecked(True)
        self.c_semua.toggled.connect(self._semua)
        atas.addWidget(self.c_semua)
        lay.addLayout(atas)

        self.tabel = QTableWidget(0, len(self.KOLOM))
        self.tabel.setHorizontalHeaderLabels(self.KOLOM)
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabel.setShowGrid(False)
        h = self.tabel.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(7, QHeaderView.Stretch)
        self.tabel.verticalHeader().setDefaultSectionSize(24)
        lay.addWidget(self.tabel, 1)

        g = QGroupBox("Opsi preparasi")
        gh = QHBoxLayout(g)
        self.c_ph = QCheckBox("Protonasi pada pH")
        self.c_ph.setChecked(True)
        self.sp_ph = QDoubleSpinBox()
        self.sp_ph.setRange(0, 14)
        self.sp_ph.setSingleStep(0.1)
        self.sp_ph.setValue(7.4)
        self.sp_ph.setToolTip("pH target protonasi")
        self.cmb_metode = QComboBox()
        self.cmb_metode.addItem("Open Babel", "obabel")
        self.cmb_metode.addItem("Dimorphite-DL", "dimorphite")
        self.cmb_metode.setToolTip("Open Babel: model pH bawaan (fenol tetap netral).\n"
                                   "Dimorphite-DL: aturan pKa per gugus (Ropp dkk. 2019); fenol/katekol bisa "
                                   "dianggap terdeprotonasi.\nKeduanya berbasis aturan: periksa muatan hasil.")
        if not dimorphite_tersedia():
            self.cmb_metode.model().item(1).setEnabled(False)
        self.sp_varian = QSpinBox()
        self.sp_varian.setRange(1, 8)
        self.sp_varian.setValue(1)
        self.sp_varian.setPrefix("varian ≤ ")
        self.sp_varian.setToolTip("Dimorphite-DL: 1 = satu keadaan pada pH tepat. > 1 = semua keadaan protonasi "
                                  "pada pH ± 1, tiap varian jadi ligan terpisah 'nama [vN]'.")
        self.sp_varian.setEnabled(False)
        self.cmb_metode.currentIndexChanged.connect(
            lambda: self.sp_varian.setEnabled(self.cmb_metode.currentData() == "dimorphite"))
        self.c_min = QCheckBox("Minimisasi MMFF94, langkah")
        self.c_min.setChecked(True)
        self.sp_lang = QSpinBox()
        self.sp_lang.setRange(50, 10000)
        self.sp_lang.setSingleStep(100)
        self.sp_lang.setValue(500)
        self.c_makro = QCheckBox("Makrosiklik kaku")
        self.c_makro.setToolTip("Bawaan Meeko: cincin makro (≥7 atom) dibuat fleksibel.")
        for w in (self.c_ph, self.sp_ph, self.cmb_metode, self.sp_varian, self.c_min, self.sp_lang, self.c_makro):
            gh.addWidget(w)
        gh.addStretch(1)
        lay.addWidget(g)

        cat = QLabel("Torsi dan hidrogen polar ditentukan otomatis oleh Meeko. Ligan dengan > 32 torsi atau "
                     "> 256 atom ditandai: tidak bisa di AutoDock-GPU, gunakan Vina.")
        cat.setObjectName("muted")
        cat.setWordWrap(True)
        lay.addWidget(cat)

        bawah = QHBoxLayout()
        self.prog = QProgressBar()
        self.prog.setFixedWidth(220)
        self.prog.hide()
        self.l_stat = QLabel("")
        self.l_stat.setObjectName("muted")
        bawah.addWidget(self.prog)
        bawah.addWidget(self.l_stat, 1)
        self.b_siap = QPushButton("Siapkan")
        self.b_siap.setObjectName("primary")
        self.b_siap.clicked.connect(self.jalankan)
        self.b_tutup = QPushButton("Tutup")
        self.b_tutup.clicked.connect(self.close)
        bawah.addWidget(self.b_siap)
        bawah.addWidget(self.b_tutup)
        lay.addLayout(bawah)

        for o in ligan:
            self.tambah(o)

    # ------------------------------------------------------------ baris
    def tambah(self, o):
        r = self.tabel.rowCount()
        self.tabel.insertRow(r)
        self.baris.append(o)
        it = QTableWidgetItem(o.nama)
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked)
        self.tabel.setItem(r, 0, it)
        sumber = "Ligan asli kristal" if o.info.get("ligan_asli") else (Path(o.sumber).name if o.sumber else "–")
        self._set(r, 1, sumber)
        self._set(r, 2, o.info.get("rumus", ""))
        self._set(r, 3, f"{o.info['mw']:.1f}" if o.info.get("mw") else "", kanan=True)
        self._set(r, 4, str(o.info.get("torsi", "")), kanan=True)
        self._set(r, 5, str(o.info.get("atom", "")), kanan=True)
        self._set(r, 6, "belum")
        self._set(r, 7, "")

    def _set(self, r, k, teks, kanan=False, warna=None):
        it = self.tabel.item(r, k) or QTableWidgetItem()
        it.setText(teks)
        if kanan:
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if warna:
            it.setForeground(QColor(warna))
        self.tabel.setItem(r, k, it)

    def _semua(self, on):
        for r in range(self.tabel.rowCount()):
            self.tabel.item(r, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)

    # ----------------------------------------------------------- tambah
    def _impor(self, berkas):
        def kerjakan(lapor):
            hasil = []
            for f in berkas:
                try:
                    hasil += [o for o in molekul.impor_berkas(f) if o.jenis == "ligan"]
                except Exception as e:
                    lapor.log.emit(f"{Path(f).name}: {e}")
            return hasil
        self.l_stat.setText("Membaca berkas…")
        kerja.jalankan(kerjakan, selesai=self._tambah_banyak, log=self.l_stat.setText)

    def _tambah_banyak(self, daftar):
        for o in daftar:
            self.tambah(o)
        lama = self.l_stat.text()
        self.l_stat.setText(f"{len(daftar)} ligan ditambahkan." + (f" {lama}" if "gagal" in lama else ""))

    def _berkas(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Tambah ligan", "",
                                             "Ligan (*.sdf *.sd *.mol *.mol2 *.pdb *.pdbqt *.smi);;Semua (*.*)")
        if fs:
            self._impor(fs)

    def _folder(self):
        d = QFileDialog.getExistingDirectory(self, "Folder ligan")
        if d:
            fs = [str(p) for p in sorted(Path(d).iterdir()) if p.suffix.lower() in
                  (".sdf", ".sd", ".mol", ".mol2", ".pdb", ".pdbqt", ".smi")]
            self._impor(fs)

    def _ambil(self, tab):
        d = DialogAmbil(self, tab)
        if not d.exec():
            return
        req = d.permintaan()
        if not req:
            return
        jenis, isi = req

        def satu(x):
            try:
                if jenis == "pubchem":
                    return molekul.unduh_pubchem(x), ""
                bag = x.split()
                return molekul.dari_smiles(bag[0], bag[1] if len(bag) > 1 else None), ""
            except Exception as e:
                return [], f"{x} — {e}"

        def kerjakan(lapor):
            from concurrent.futures import ThreadPoolExecutor
            hasil, gagal = [], []
            with ThreadPoolExecutor(max_workers=6 if jenis == "pubchem" else 2) as ex:  # sopan ke server PubChem
                for i, (objs, g) in enumerate(ex.map(satu, isi), 1):
                    hasil += objs
                    if g:
                        gagal.append(g)
                    lapor.log.emit(f"Diambil {i}/{len(isi)}")
            if gagal:
                lapor.log.emit(f"{len(gagal)} gagal: " + "; ".join(gagal)[:300])
            return hasil
        self.l_stat.setText("Mengunduh…")
        kerja.jalankan(kerjakan, selesai=self._tambah_banyak, log=self.l_stat.setText)

    # ------------------------------------------------------------ proses
    def opsi(self):
        return OpsiLigan(ph=self.sp_ph.value(), protonasi=self.c_ph.isChecked(),
                         metode_ph=self.cmb_metode.currentData(), varian=self.sp_varian.value(),
                         minimisasi=self.c_min.isChecked(),
                         langkah=self.sp_lang.value(), makrosiklik_kaku=self.c_makro.isChecked())

    def jalankan(self):
        idx = [r for r in range(self.tabel.rowCount()) if self.tabel.item(r, 0).checkState() == Qt.Checked]
        if not idx:
            self.l_stat.setText("Belum ada ligan yang dicentang.")
            return
        data = []
        for r in idx:
            o = self.baris[r]
            data.append((o.nama, o.teks, "sdf" if o.fmt == "sdf" else ("mol2" if o.fmt == "mol2" else "pdb")))
            self._set(r, 6, "antre")
        self.berjalan = True
        self.b_siap.setEnabled(False)
        self.prog.show()
        self.prog.setRange(0, len(idx))
        self.prog.setValue(0)
        self._idx = idx
        kerja.jalankan(siapkan_banyak, data, self.opsi(), selesai=self._selesai, galat=self._galat,
                       progres=lambda k, n, nama: (self.prog.setMaximum(n), self.prog.setValue(k),
                                                       self.l_stat.setText(f"{k}/{n} · {nama}")))

    def _selesai(self, hasil):
        t = theme.TOKEN[self.mode]
        ok = []
        per_baris = {}
        for h in hasil:   # enumerasi varian: beberapa hasil per baris masukan
            per_baris.setdefault(h.asal, []).append(h)
            if h.status != "gagal":
                ok.append((self.baris[self._idx[h.asal]], h))
        for k, r in enumerate(self._idx):
            hs = per_baris.get(k) or []
            if not hs:
                continue
            h = next((x for x in hs if x.status != "gagal"), hs[0])
            warna = {"siap": t["ok"], "peringatan": t["warn"], "gagal": t["bad"]}[h.status]
            self._set(r, 2, h.rumus or self.tabel.item(r, 2).text())
            self._set(r, 3, f"{h.mw:.1f}" if h.mw else self.tabel.item(r, 3).text(), kanan=True)
            self._set(r, 4, str(h.torsi) if h.status != "gagal" else "", kanan=True)
            self._set(r, 5, str(h.atom) if h.status != "gagal" else "", kanan=True)
            self._set(r, 6, h.status if len(hs) == 1 else f"{h.status} ({len(hs)} varian)", warna=warna)
            alasan = h.alasan if len(hs) == 1 else " | ".join(f"{x.nama}: muatan {x.muatan:+d}" for x in hs)
            self._set(r, 7, alasan)
            self.tabel.item(r, 7).setToolTip("\n".join(f"{x.nama}: {x.status}, muatan {x.muatan:+d}; {x.alasan}"
                                                       for x in hs))
            if h.status != "gagal":
                self.tabel.item(r, 0).setCheckState(Qt.Unchecked)
        gagal = sum(1 for h in hasil if h.status == "gagal")
        self.l_stat.setText(f"Selesai: {len(ok)} siap docking, {gagal} gagal.")
        self.berjalan = False
        self.b_siap.setEnabled(True)
        self.prog.hide()
        if ok:
            self.siap.emit(ok)

    def _galat(self, g):
        self.berjalan = False
        self.b_siap.setEnabled(True)
        self.prog.hide()
        self.l_stat.setText("Galat: " + g.splitlines()[0])

    def closeEvent(self, e):
        if self.berjalan:
            self.l_stat.setText("Tunggu sampai preparasi selesai.")
            e.ignore()
            return
        super().closeEvent(e)

    def reject(self):
        if not self.berjalan:
            super().reject()
