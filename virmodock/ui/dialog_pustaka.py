"""Dialog Pustaka ligan (Siapkan › Pustaka ligan…): obat disetujui (offline), bahan alam COCONUT (unduh sekali),
ZINC22 (situs). Saring nama/kelas/sifat, urutkan menurut kemiripan ke SMILES acuan, impor sebagai ligan."""
import threading
from html import escape

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QSpinBox, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import pustaka as P
from ..core.laporan import id_angka
from . import kerja


def _sel(t, angka=None):
    it = QTableWidgetItem(t)
    if angka is not None:
        it.setData(Qt.UserRole, angka)
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


def _f(v, d=2):
    return id_angka(f"{v:.{d}f}") if isinstance(v, (int, float)) else "–"


class DialogPustaka(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Pustaka ligan")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1180, 760)
        self.hasil = []
        self._batal = None
        lay = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("Sumber"))
        self.c_sumber = QComboBox()
        self.c_sumber.addItem("Obat disetujui (ChEMBL fase 4) — offline", "obat")
        self.c_sumber.addItem("Bahan alam (COCONUT 2.0)", "coconut")
        self.c_sumber.addItem("ZINC22 (situs web)", "zinc")
        h.addWidget(self.c_sumber)
        self.l_info = QLabel()
        self.l_info.setObjectName("muted")
        h.addWidget(self.l_info, 1)
        lay.addLayout(h)
        self.stak = QStackedWidget()
        self.stak.addWidget(self._panel_obat())
        self.stak.addWidget(self._panel_coconut())
        self.stak.addWidget(self._panel_zinc())
        lay.addWidget(self.stak)
        # kemiripan (umum)
        hm = QHBoxLayout()
        self.e_mirip = QLineEdit()
        self.e_mirip.setPlaceholderText("Opsional: SMILES acuan → hasil diurutkan menurut kemiripan (Tanimoto ECFP4)")
        b_acuan = QPushButton("Pakai ligan aktif")
        b_acuan.setToolTip("Isi SMILES acuan dari ligan/pose yang sedang dipilih")
        b_acuan.clicked.connect(self._acuan_aktif)
        hm.addWidget(QLabel("Mirip dengan"))
        hm.addWidget(self.e_mirip, 1)
        hm.addWidget(b_acuan)
        self.s_batas = QSpinBox()
        self.s_batas.setRange(10, 5000)
        self.s_batas.setValue(200)
        self.s_batas.setPrefix("maks ")
        hm.addWidget(self.s_batas)
        self.b_cari = QPushButton("Cari")
        self.b_cari.setObjectName("primary")
        self.b_cari.clicked.connect(self.cari)
        hm.addWidget(self.b_cari)
        lay.addLayout(hm)
        self.prog = QProgressBar()
        self.prog.setVisible(False)
        lay.addWidget(self.prog)
        self.tabel = QTableWidget(0, 8)
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabel.setSortingEnabled(True)
        lay.addWidget(self.tabel, 1)
        bawah = QHBoxLayout()
        self.l_status = QLabel()
        self.l_status.setObjectName("muted")
        bawah.addWidget(self.l_status, 1)
        b_semua = QPushButton("Centang semua")
        b_semua.clicked.connect(lambda: self._centang(True))
        b_imp = QPushButton("Impor dicentang sebagai ligan")
        b_imp.setObjectName("primary")
        b_imp.clicked.connect(self.impor)
        b_tutup = QPushButton("Tutup")
        b_tutup.clicked.connect(self.close)
        for b in (b_semua, b_imp, b_tutup):
            bawah.addWidget(b)
        lay.addLayout(bawah)
        self.c_sumber.currentIndexChanged.connect(self._ganti)
        self._ganti()

    # ------------------------------------------------------------------ panel sumber
    def _panel_obat(self):
        w = QWidget()
        f = QHBoxLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self.o_nama = QLineEdit()
        self.o_nama.setPlaceholderText("Nama obat atau CHEMBL ID")
        self.o_nama.returnPressed.connect(self.cari)
        self.o_atc = QComboBox()
        self.o_atc.addItem("Semua golongan ATC", "")
        for k, t in P.ATC.items():
            self.o_atc.addItem(f"{k} · {t}", k)
        self.o_rute = QComboBox()
        for t, k in (("Semua rute", ""), ("Oral", "oral"), ("Topikal", "topikal"), ("Parenteral", "parenteral")):
            self.o_rute.addItem(t, k)
        self.o_alam = QCheckBox("Bahan alam/turunannya")
        for x in (self.o_nama, self.o_atc, self.o_rute, self.o_alam):
            f.addWidget(x)
        f.setStretch(0, 1)
        return w

    def _panel_coconut(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        hb = QHBoxLayout()
        self.l_coco = QLabel()
        self.l_coco.setWordWrap(True)
        hb.addWidget(self.l_coco, 1)
        self.b_unduh = QPushButton("Unduh basis data COCONUT…")
        self.b_unduh.clicked.connect(self.unduh_coconut)
        self.b_batal = QPushButton("Batalkan unduhan")
        self.b_batal.setVisible(False)
        self.b_batal.clicked.connect(lambda: self._batal and self._batal.set())
        hb.addWidget(self.b_unduh)
        hb.addWidget(self.b_batal)
        v.addLayout(hb)
        h = QHBoxLayout()
        self.k_nama = QLineEdit()
        self.k_nama.setPlaceholderText("Nama atau CNP ID (mis. quercetin)")
        self.k_nama.returnPressed.connect(self.cari)
        self.k_kelas = QLineEdit()
        self.k_kelas.setPlaceholderText("Kelas kimia (mis. flavonoid, alkaloid, terpenoid)")
        self.k_kelas.returnPressed.connect(self.cari)
        self.k_mw0, self.k_mw1 = QDoubleSpinBox(), QDoubleSpinBox()
        for s, v_ in ((self.k_mw0, 150), (self.k_mw1, 600)):
            s.setRange(0, 3000)
            s.setDecimals(0)
            s.setValue(v_)
        self.k_lip = QComboBox()
        for t, k in (("Lipinski: bebas", None), ("≤ 1 pelanggaran", 1), ("0 pelanggaran", 0)):
            self.k_lip.addItem(t, k)
        self.k_lip.setCurrentIndex(1)
        self.k_qed = QDoubleSpinBox()
        self.k_qed.setRange(0, 1)
        self.k_qed.setSingleStep(0.1)
        self.k_qed.setPrefix("QED ≥ ")
        self.k_urut = QComboBox()
        for t, k in (("Urut: kualitas anotasi", "anotasi"), ("Urut: QED", "qed"), ("Urut: NP-likeness", "np"),
                     ("Acak (sampel beragam)", "acak")):
            self.k_urut.addItem(t, k)
        for x in (self.k_nama, self.k_kelas, QLabel("MW"), self.k_mw0, QLabel("–"), self.k_mw1, self.k_lip, self.k_qed,
                  self.k_urut):
            h.addWidget(x)
        h.setStretch(0, 1)
        h.setStretch(1, 1)
        v.addLayout(h)
        return w

    def _panel_zinc(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        t = QLabel("ZINC22 (Irwin et al., J Chem Inf Model 2023) memakai verifikasi anti-bot, sehingga VirmoDock tidak "
                   "mengaksesnya otomatis. Buka situs, cari/saring senyawa (mis. tranche 'in-stock' atau mirip SMILES), "
                   "unduh sebagai SDF/SMILES, lalu impor lewat <b>Berkas › Buka</b> atau seret berkas ke jendela.")
        t.setWordWrap(True)
        v.addWidget(t)
        b = QPushButton("Buka ZINC22 (CartBlanche) di browser")
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(P.URL_ZINC)))
        hb = QHBoxLayout()
        hb.addWidget(b)
        hb.addStretch(1)
        v.addLayout(hb)
        return w

    # ------------------------------------------------------------------ logika
    def _ganti(self, *_):
        k = self.c_sumber.currentData()
        self.stak.setCurrentIndex(["obat", "coconut", "zinc"].index(k))
        self.b_cari.setEnabled(k != "zinc")
        self.e_mirip.setEnabled(k != "zinc")
        if k == "obat":
            self.l_info.setText(f"{len(P.obat())} obat · {P.info_obat()}")
        elif k == "coconut":
            self._segarkan_coconut()
        else:
            self.l_info.setText("")

    def _segarkan_coconut(self):
        a = P.coconut_ada()
        if a:
            jml = f"{a['jumlah']:,}".replace(",", ".")
            self.l_coco.setText(f"Basis data lokal: <b>{jml}</b> senyawa (diunduh {a['waktu']}, "
                                f"{a['ukuran'] / 1e6:.0f} MB). Data CC0. {escape(P.SITASI_COCONUT)}")
            self.b_unduh.setText("Perbarui basis data…")
            self.l_info.setText("COCONUT siap (offline)")
        else:
            self.l_coco.setText("Basis data COCONUT belum ada. Unduh sekali (±200 MB, ±700 ribu bahan alam, CC0); "
                                "setelah itu pencarian berjalan offline.")
            self.b_unduh.setText("Unduh basis data COCONUT…")
            self.l_info.setText("")
        self.b_cari.setEnabled(bool(a) or self.c_sumber.currentData() != "coconut")

    def unduh_coconut(self):
        if QMessageBox.question(self, "Unduh COCONUT",
                                "Unduh berkas COCONUT 2.0 (±200 MB) dari server Universitas Jena dan simpan indeks "
                                "(±250 MB) di folder data VirmoDock?\n\nLisensi data: CC0. Proses ±3–10 menit "
                                "tergantung koneksi.") != QMessageBox.Yes:
            return
        self._batal = threading.Event()
        self.b_unduh.setEnabled(False)
        self.b_batal.setVisible(True)
        self.prog.setVisible(True)
        self.prog.setValue(0)

        def selesai(n):
            self._akhiri_unduh()
            self.jw.log.tulis(f"COCONUT: {n} senyawa diindeks")
            self._segarkan_coconut()

        def galat(g):
            self._akhiri_unduh()
            self.l_status.setText("Unduhan gagal/dibatalkan: " + str(g).strip().splitlines()[-1])

        kerja.jalankan(P.unduh_coconut, batal=self._batal, selesai=selesai, galat=galat,
                       log=self.l_status.setText, progres=self._progres)

    def _progres(self, a, b, t):
        self.prog.setMaximum(max(1, b))
        self.prog.setValue(a)
        self.l_status.setText(f"{a / 1e6:.0f} / {b / 1e6:.0f} MB · {t}")

    def _akhiri_unduh(self):
        self.b_unduh.setEnabled(True)
        self.b_batal.setVisible(False)
        self.prog.setVisible(False)
        self._batal = None

    def _acuan_aktif(self):
        a = getattr(self.jw, "_aktif_inter", None)
        if a and a.get("mol") is not None:
            from rdkit import Chem
            self.e_mirip.setText(Chem.MolToSmiles(Chem.RemoveHs(a["mol"])))
        else:
            self.jw.statusBar().showMessage("Pilih ligan atau pose di viewport/Hasil dulu.", 5000)

    def cari(self):
        k = self.c_sumber.currentData()
        smi = self.e_mirip.text().strip()
        batas = self.s_batas.value()
        if k == "obat":
            d = P.saring_obat(self.o_nama.text(), self.o_atc.currentData(), self.o_rute.currentData(),
                              self.o_alam.isChecked())
            fn = (lambda lapor=None: P.urut_mirip(d, smi, batas, lapor)) if smi else (lambda lapor=None: d[:batas])
        elif k == "coconut":
            if not P.coconut_ada():
                return
            saring = dict(nama=self.k_nama.text(), kelas=self.k_kelas.text(), mw=(self.k_mw0.value(), self.k_mw1.value()),
                          lipinski_maks=self.k_lip.currentData(), qed_min=self.k_qed.value(),
                          urut=self.k_urut.currentData(), acak=self.k_urut.currentData() == "acak")
            fn = ((lambda lapor=None: P.cari_coconut_mirip(smi, 100000, batas, lapor, **saring)) if smi else
                  (lambda lapor=None: P.cari_coconut(batas=batas, **saring)))
        else:
            return
        self.b_cari.setEnabled(False)
        self.prog.setVisible(bool(smi))
        self.l_status.setText("Mencari…")
        kerja.jalankan(fn, selesai=self._isi, galat=self._galat_cari,
                       progres=lambda a, b, _t: (self.prog.setMaximum(max(1, b)), self.prog.setValue(a)))

    def _galat_cari(self, g):
        self.b_cari.setEnabled(True)
        self.prog.setVisible(False)
        self.l_status.setText("Gagal: " + str(g).strip().splitlines()[-1])

    def _isi(self, hasil):
        self.b_cari.setEnabled(True)
        self.prog.setVisible(False)
        self.hasil = hasil
        k = self.c_sumber.currentData()
        mirip = any("mirip" in h for h in hasil)
        if k == "obat":
            kol = ["", "Nama", "ID", "Tahun", "ATC", "Rute"]
        else:
            kol = ["", "Nama", "ID", "MW", "ALogP", "QED", "Lipinski", "Kelas"]
        if mirip:
            kol.append("Tanimoto")
        t = self.tabel
        t.setSortingEnabled(False)
        t.clear()
        t.setColumnCount(len(kol))
        t.setHorizontalHeaderLabels(kol)
        t.setRowCount(len(hasil))
        for r, h in enumerate(hasil):
            c = QTableWidgetItem()
            c.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            c.setCheckState(Qt.Unchecked)
            c.setData(Qt.UserRole + 1, r)
            t.setItem(r, 0, c)
            t.setItem(r, 1, _sel(h.get("nama") or h["id"]))
            t.setItem(r, 2, _sel(h["id"]))
            if k == "obat":
                t.setItem(r, 3, _sel(str(h["tahun"] or "–"), h["tahun"] or 0))
                t.setItem(r, 4, _sel(h["atc"]))
                t.setItem(r, 5, _sel(", ".join(x for x in ("oral", "topikal", "parenteral") if h.get(x))))
            else:
                t.setItem(r, 3, _sel(_f(h.get("mw"), 1), h.get("mw") or 0))
                t.setItem(r, 4, _sel(_f(h.get("logp")), h.get("logp") or 0))
                t.setItem(r, 5, _sel(_f(h.get("qed")), h.get("qed") or 0))
                t.setItem(r, 6, _sel(_f(h.get("lipinski"), 0), h.get("lipinski") or 0))
                t.setItem(r, 7, _sel(h.get("kelas") or h.get("superkelas") or ""))
            if mirip:
                t.setItem(r, len(kol) - 1, _sel(_f(h["mirip"], 3), h["mirip"]))
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for c in range(len(kol)):
            if c != 1:
                t.resizeColumnToContents(c)
        t.setSortingEnabled(True)
        self.l_status.setText(f"{len(hasil)} senyawa" + (" (urut kemiripan)" if mirip else ""))

    def _centang(self, on):
        for r in range(self.tabel.rowCount()):
            self.tabel.item(r, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)

    def impor(self):
        from PySide6.QtWidgets import QApplication
        from ..core import molekul
        idx = [self.tabel.item(r, 0).data(Qt.UserRole + 1) for r in range(self.tabel.rowCount())
               if self.tabel.item(r, 0).checkState() == Qt.Checked]
        if not idx:
            self.l_status.setText("Centang senyawa yang akan diimpor.")
            return
        if len(idx) > 300 and QMessageBox.question(self, "Impor", f"Impor {len(idx)} senyawa? (pembuatan 3D bisa "
                                                                  "memakan waktu)") != QMessageBox.Yes:
            return
        ada = {o.nama for o in self.jw.objek.values()}
        ob, gagal = [], 0
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for i in idx:
                h = self.hasil[i]
                nama = (h.get("nama") or h["id"]).strip() or h["id"]
                if len(nama) > 40:
                    nama = h["id"]
                if nama in ada:
                    continue
                try:
                    o = molekul.dari_smiles(h["smiles"], nama)
                    for x in o:
                        x.info["pustaka"] = self.c_sumber.currentData()
                        x.info["id_pustaka"] = h["id"]
                    ob += o
                    ada.add(nama)
                except Exception:
                    gagal += 1
        finally:
            QApplication.restoreOverrideCursor()
        if ob:
            self.jw.tambah_objek(ob, fokus=False)
        self.l_status.setText(f"{len(ob)} ligan diimpor" + (f", {gagal} gagal" if gagal else "")
                              + " — siapkan di langkah 2")
        self.jw.log.tulis(f"Pustaka {self.c_sumber.currentText()}: {len(ob)} ligan diimpor")
