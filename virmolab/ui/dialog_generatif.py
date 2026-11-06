"""Desain generatif terpandu docking (F8): bangun analog dari satu induk, saring, lalu peringkat.

Docking dijalankan lewat antrean proyek seperti job biasa, jadi hasilnya tercatat dan dapat diulang.
Dialog ini sengaja memperlihatkan jumlah yang ditolak beserta alasannya: tanpa itu pengguna tidak
tahu bahwa saringannya terlalu ketat untuk seri senyawanya.
"""
import csv

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QSpinBox, QSplitter, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..core import catat, generatif, molekul
from . import kerja, kit

KOLOM = ["SMILES", "Generasi", "Operasi", "QED", "SAScore", "MPO", "Mirip induk", "ΔG (kkal/mol)"]


class DialogGeneratif(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.jw = parent
        self.proyek = getattr(parent, "proyek", None)
        self.setWindowTitle("Desain generatif")
        self.setMinimumSize(1120, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._hasil = None
        self._kerja = None
        self._bangun()
        self._isi_induk()

    def _bangun(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Desain generatif",
                                "Bangun analog yang masuk akal untuk disintesis dari satu senyawa induk"))

        info = generatif.tersedia()
        lay.addWidget(kit.catatan(info["pesan"], "muted" if info["ada"] else "peringatan"))

        split = QSplitter(Qt.Horizontal, self)
        split.setChildrenCollapsible(False)

        kiri = QWidget()
        vk = QVBoxLayout(kiri)
        vk.setContentsMargins(0, 0, 8, 0)
        vk.setSpacing(8)

        g_induk = QGroupBox("Senyawa induk")
        v_induk = QVBoxLayout(g_induk)
        self.cb_induk = QComboBox()
        self.cb_induk.currentIndexChanged.connect(self._ganti_induk)
        v_induk.addWidget(self.cb_induk)
        self.t_smiles = QLineEdit()
        self.t_smiles.setPlaceholderText("SMILES induk")
        v_induk.addWidget(self.t_smiles)
        vk.addWidget(g_induk)

        g_par = QGroupBox("Parameter")
        v_par = QVBoxLayout(g_par)
        h_op = QHBoxLayout()
        h_op.addWidget(QLabel("Operasi:"))
        self.cb_operasi = QComboBox()
        self.cb_operasi.setToolTip("Menumbuhkan menambah gugus pada rangka yang ada; menukar mengganti bagian molekul dengan padanan yang masuk akal secara kimia. Menumbuhkan memperbesar molekul, menukar menjaga ukurannya.")
        for teks, kunci in (("Ganti fragmen (mutate)", "mutate"), ("Tambah fragmen (grow)", "grow")):
            self.cb_operasi.addItem(teks, kunci)
        h_op.addWidget(self.cb_operasi, 1)
        v_par.addLayout(h_op)

        h_rad = QHBoxLayout()
        h_rad.addWidget(QLabel("Radius konteks:"))
        self.s_radius = QSpinBox()
        self.s_radius.setRange(1, 3)
        self.s_radius.setValue(2)
        self.s_radius.setToolTip("Makin besar makin konservatif: lingkungan kimia yang harus sama makin luas")
        h_rad.addWidget(self.s_radius)
        h_rad.addStretch(1)
        v_par.addLayout(h_rad)

        h_gen = QHBoxLayout()
        h_gen.addWidget(QLabel("Generasi:"))
        self.s_generasi = QSpinBox()
        self.s_generasi.setToolTip("Berapa kali operasi diulang berantai. Satu generasi menghasilkan analog yang dekat dengan induknya; lebih banyak generasi menjauh dari induk dan makin sulit disintesis.")
        self.s_generasi.setRange(1, 5)
        self.s_generasi.setValue(1)
        h_gen.addWidget(self.s_generasi)
        h_gen.addWidget(QLabel("Maks analog:"))
        self.s_maks = QSpinBox()
        self.s_maks.setToolTip("Batas jumlah analog yang dihasilkan. Angka besar memperlambat penyaringan dan docking lanjutan, bukan tahap pembangkitannya.")
        self.s_maks.setRange(50, 2000)
        self.s_maks.setSingleStep(50)
        self.s_maks.setValue(300)
        h_gen.addWidget(self.s_maks)
        v_par.addLayout(h_gen)
        vk.addWidget(g_par)

        g_saring = QGroupBox("Saringan")
        v_saring = QVBoxLayout(g_saring)
        h_sa = QHBoxLayout()
        h_sa.addWidget(QLabel("SAScore maks:"))
        self.s_sa = QDoubleSpinBox()
        self.s_sa.setToolTip("SAScore maksimum yang diterima: 1 mudah disintesis, 10 sangat sulit. Di atas 6 biasanya memerlukan jalur sintesis khusus.")
        self.s_sa.setRange(1.0, 10.0)
        self.s_sa.setSingleStep(0.5)
        self.s_sa.setValue(generatif.SA_MAKS)
        h_sa.addWidget(self.s_sa)
        h_sa.addWidget(QLabel("QED min:"))
        self.s_qed = QDoubleSpinBox()
        self.s_qed.setToolTip("QED minimum (0–1) untuk kemiripan-obat. Di atas 0,5 umumnya dianggap mirip-obat; longgarkan bila induknya sendiri berada di bawah ambang itu.")
        self.s_qed.setRange(0.0, 1.0)
        self.s_qed.setSingleStep(0.05)
        self.s_qed.setValue(generatif.QED_MIN)
        h_sa.addWidget(self.s_qed)
        v_saring.addLayout(h_sa)
        self.c_relatif = QCheckBox("Longgarkan ambang bila induk sendiri di luar ambang")
        self.c_relatif.setChecked(True)
        self.c_relatif.setToolTip("Tanpa ini, induk ber-QED rendah seperti inhibitor peptidomimetik "
                                  "membuat seluruh turunannya tertolak")
        v_saring.addWidget(self.c_relatif)
        self.c_pains = QCheckBox("Buang PAINS dan Brenk")
        self.c_pains.setChecked(True)
        v_saring.addWidget(self.c_pains)
        vk.addWidget(g_saring)

        h_aksi = QHBoxLayout()
        self.b_jalan = kit.tombol("Bangun analog", self._mulai, utama=True)
        self.b_batal = kit.tombol("Batal", self._batalkan)
        self.b_batal.setEnabled(False)
        h_aksi.addWidget(self.b_jalan)
        h_aksi.addWidget(self.b_batal)
        vk.addLayout(h_aksi)
        self.l_status = QLabel("")
        self.l_status.setWordWrap(True)
        self.l_status.setObjectName("muted")
        vk.addWidget(self.l_status)
        vk.addStretch(1)
        kiri.setFixedWidth(340)
        split.addWidget(kiri)

        kanan = QWidget()
        vn = QVBoxLayout(kanan)
        vn.setContentsMargins(8, 0, 0, 0)
        vn.setSpacing(8)
        self.tabel = kit.tabel(KOLOM, regang=0, urut=True)
        vn.addWidget(self.tabel, 1)
        self.l_ringkas = QLabel("")
        self.l_ringkas.setWordWrap(True)
        self.l_ringkas.setObjectName("muted")
        vn.addWidget(self.l_ringkas)
        split.addWidget(kanan)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)

        lay.addWidget(kit.catatan(
            "Analog adalah usulan komputasi. Nilai ΔG baru terisi setelah kandidat di-docking, dan "
            "kelayakan sintesisnya tetap perlu dinilai ahli kimia.", "peringatan"))

        self.b_impor = kit.tombol("Impor terpilih sebagai ligan", self._impor)
        self.b_csv = kit.tombol("Ekspor CSV…", self._ekspor)
        self.b_metode = kit.tombol("Salin paragraf metode", self._salin_metode)
        lay.addLayout(kit.bar_bawah(self, kiri=[self.b_impor, self.b_csv, self.b_metode], tutup=True))

        if not info["ada"]:
            self.b_jalan.setEnabled(False)

    def _isi_induk(self):
        self.cb_induk.clear()
        for item in (kit.ligan_proyek(self.jw, dengan_mol=False) if self.jw else []):
            smi = item.get("smiles") if isinstance(item, dict) else ""
            nama = item.get("nama") if isinstance(item, dict) else str(item)
            if smi:
                self.cb_induk.addItem(nama, smi)
        if self.cb_induk.count() == 0:
            self.cb_induk.addItem("Ketik SMILES sendiri", "")
        self._ganti_induk()

    def _ganti_induk(self):
        smi = self.cb_induk.currentData()
        if smi:
            self.t_smiles.setText(smi)

    # ------------------------------------------------------------------ jalankan
    def _mulai(self):
        induk = self.t_smiles.text().strip()
        if not induk:
            self.l_status.setText("Isi SMILES senyawa induk.")
            return
        from rdkit import Chem
        if Chem.MolFromSmiles(induk) is None:
            self.l_status.setText("SMILES induk tidak valid.")
            return

        opsi = dict(operasi=self.cb_operasi.currentData(), radius=self.s_radius.value(),
                    maks=self.s_maks.value(), n_generasi=self.s_generasi.value())
        saringan = dict(sa_maks=self.s_sa.value(), qed_min=self.s_qed.value(),
                        relatif_induk=self.c_relatif.isChecked(),
                        buang_pains=self.c_pains.isChecked(), buang_brenk=self.c_pains.isChecked())
        self._batal = False
        self.b_jalan.setEnabled(False)
        self.b_batal.setEnabled(True)
        self.l_status.setText("Membangun analog…")

        def kerjakan(lapor=None):
            def progres(i, n, pesan):
                if lapor:
                    lapor.log.emit(pesan)
            return generatif.siklus(induk, dock=None, batal=lambda: self._batal,
                                    progres=progres, **opsi, **saringan)

        self._kerja = kerja.jalankan(kerjakan, selesai=self._selesai, galat=self._galat,
                                     log=self.l_status.setText)

    def _batalkan(self):
        self._batal = True
        self.b_batal.setEnabled(False)
        self.l_status.setText("Membatalkan setelah generasi berjalan selesai…")

    def _galat(self, teks):
        self.b_jalan.setEnabled(True)
        self.b_batal.setEnabled(False)
        self.l_status.setText(f"Gagal: {teks.splitlines()[0]}")

    def _selesai(self, hasil):
        self.b_jalan.setEnabled(True)
        self.b_batal.setEnabled(False)
        self._hasil = hasil
        kandidat = hasil.get("kandidat") or []
        ditolak = hasil.get("ditolak") or []
        self._isi_tabel(kandidat)

        if not kandidat:
            sebab = {}
            for k in ditolak:
                for b in (k.alasan_tolak or "").split("; "):
                    kunci = b.split(" ")[0] if b else ""
                    sebab[kunci] = sebab.get(kunci, 0) + 1
            rinci = ", ".join(f"{v}× {k}" for k, v in sorted(sebab.items(), key=lambda x: -x[1])[:4])
            self.l_ringkas.setText(f"Seluruh {len(ditolak)} analog tertolak saringan ({rinci}). "
                                   "Longgarkan ambang di panel kiri bila perlu.")
            return
        self.l_ringkas.setText(
            f"{len(kandidat)} analog lolos saringan, {len(ditolak)} ditolak. "
            "ΔG masih kosong sampai kandidat di-docking lewat tombol impor dan antrean docking.")

    def _isi_tabel(self, kandidat):
        self.tabel.setSortingEnabled(False)
        self.tabel.setRowCount(len(kandidat))
        for r, k in enumerate(kandidat):
            self.tabel.setItem(r, 0, QTableWidgetItem(k.smiles))
            self.tabel.setItem(r, 1, kit.sel_angka(k.generasi, d=0))
            self.tabel.setItem(r, 2, QTableWidgetItem(k.operasi))
            self.tabel.setItem(r, 3, kit.sel_angka(k.qed, d=3))
            self.tabel.setItem(r, 4, kit.sel_angka(k.sascore, d=2))
            self.tabel.setItem(r, 5, kit.sel_angka(k.mpo, d=1))
            self.tabel.setItem(r, 6, kit.sel_angka(k.kemiripan_induk, d=3))
            self.tabel.setItem(r, 7, kit.sel_angka(k.dg, d=2))
        self.tabel.setSortingEnabled(True)

    # ------------------------------------------------------------------ keluaran
    def _terpilih(self):
        baris = {i.row() for i in self.tabel.selectedIndexes()}
        return [self.tabel.item(r, 0).text() for r in sorted(baris) if self.tabel.item(r, 0)]

    def _impor(self):
        smiles = self._terpilih()
        if not smiles:
            self.l_status.setText("Pilih baris kandidat yang akan diimpor.")
            return
        if not self.jw or not hasattr(self.jw, "tambah_objek"):
            self.l_status.setText("Buka dialog ini dari jendela utama untuk mengimpor kandidat.")
            return
        objs, gagal = [], 0
        for i, smi in enumerate(smiles, 1):
            try:
                for o in molekul.dari_smiles(smi, f"Generatif_{i}"):
                    o.tampil = False
                    o.info["asal"] = {"sumber": "generatif", "induk": self.t_smiles.text().strip(),
                                      "operasi": self.cb_operasi.currentData()}
                    objs.append(o)
            except Exception as e:
                catat.log.debug(f"Kandidat generatif gagal dibangun: {e}")
                gagal += 1
        if objs:
            self.jw.tambah_objek(objs, fokus=False)
        pesan = f"{len(objs)} kandidat ditambahkan sebagai ligan."
        if gagal:
            pesan += f" {gagal} gagal dibangun strukturnya."
        self.l_status.setText(pesan)
        if objs and hasattr(self.jw, "siapkan_ligan"):
            self.jw.siapkan_ligan()

    def _ekspor(self):
        if not self._hasil or not self._hasil.get("kandidat"):
            self.l_status.setText("Belum ada kandidat untuk diekspor.")
            return
        p, _ = QFileDialog.getSaveFileName(self, "Simpan CSV kandidat", "kandidat_generatif.csv",
                                           "CSV (*.csv)")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["# sumber fragmen", self._hasil.get("catatan_db", "")])
            w.writerow(["smiles", "induk", "generasi", "operasi", "qed", "sascore", "mpo",
                        "kemiripan_induk", "dg"])
            for k in self._hasil["kandidat"]:
                w.writerow([k.smiles, k.induk, k.generasi, k.operasi, k.qed, k.sascore, k.mpo,
                            k.kemiripan_induk, k.dg])
        self.l_status.setText(f"CSV disimpan ke {p}")

    def _salin_metode(self):
        if not self._hasil:
            self.l_status.setText("Jalankan pembangunan analog terlebih dahulu.")
            return
        teks = generatif.paragraf_metode(self._hasil, operasi=self.cb_operasi.currentData(),
                                         radius=self.s_radius.value(), sa_maks=self.s_sa.value(),
                                         qed_min=self.s_qed.value())
        if not teks:
            self.l_status.setText("Belum ada kandidat yang lolos untuk ditulis di paragraf metode.")
            return
        kit.salin(teks)
        self.l_status.setText("Paragraf metode disalin ke papan klip.")
