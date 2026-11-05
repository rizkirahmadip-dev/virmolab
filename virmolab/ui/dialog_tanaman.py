"""Dialog pencarian dan impor senyawa dari tanaman obat (F1).

Mengakses LOTUS (Wikidata SPARQL) dan basis data COCONUT 2.0 lokal.
"""
import csv
import threading
from urllib.parse import quote

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter,
    QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget
)

from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D

from ..core import molekul, tanaman
from ..core.sumber_data import Jejak
from . import kit, kerja


def _gambar_mol_pixmap(smiles: str, lebar: int = 280, tinggi: int = 200, tema: str = "terang") -> QPixmap:
    """Buat QPixmap dari SMILES menggunakan RDKit SVG renderer."""
    pix = QPixmap(lebar, tinggi)
    pix.fill(Qt.transparent)
    if not smiles:
        return pix
    try:
        m = Chem.MolFromSmiles(smiles)
        if not m:
            return pix
        d2d = rdMolDraw2D.MolDraw2DSVG(lebar, tinggi)
        opts = d2d.drawOptions()
        opts.clearBackground = False
        if tema == "gelap":
            rdMolDraw2D.SetDarkMode(opts)
        d2d.DrawMolecule(m)
        d2d.FinishDrawing()
        svg_bytes = d2d.GetDrawingText().encode("utf-8")
        renderer = QSvgRenderer(svg_bytes)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
    except Exception:
        pass
    return pix


def _kunci(s: dict) -> str:
    return s.get("inchikey") or s.get("qid") or s.get("smiles", "")


class DialogTanaman(QDialog):
    """Dialog pencarian senyawa bahan alam dari tanaman obat Indonesia.

    Dua mode. `mode="docking"` (bawaan) mengimpor senyawa terpilih ke proyek sebagai ligan: struktur 3D
    dibuat, objek viewer ditambahkan, dan senyawanya siap disiapkan untuk docking. `mode="senyawa"`
    hanya memulangkan nama dan SMILES lewat sinyal `senyawaDipilih` — dipakai alur farmakologi jaringan,
    yang bekerja atas daftar senyawa dan belum memerlukan struktur 3D sama sekali. Satu takson bisa
    memberi ratusan senyawa; membuat konformasi 3D untuk semuanya memakan waktu lama dan memenuhi
    panel Objek dengan ligan yang belum tentu akan didocking.
    """

    senyawaDipilih = Signal(list)      # [{nama, smiles, sumber}] pada mode "senyawa"

    def __init__(self, jw=None, mode: str = "docking"):
        super().__init__(jw)
        self.jw = jw
        self.mode = mode if mode in ("docking", "senyawa") else "docking"
        self.setWindowTitle("Senyawa dari tanaman obat")
        self.setMinimumSize(1000, 650)
        self.resize(1180, 720)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)

        self.semua_senyawa = []
        self._dipilih = set()  # kunci senyawa yang dicentang; bertahan saat saringan diubah
        self.senyawa_tersaring = []
        self.jejak_aktif = None
        self._batal = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        # 1. Kepala
        lay.addWidget(kit.judul(
            "Senyawa dari tanaman obat",
            "Senyawa yang dilaporkan dari suatu tanaman menurut LOTUS (Wikidata), lengkap dengan rujukan. "
            "Kehadiran senyawa di basis data belum tentu berarti kadarnya bermakna."
        ))

        # 2. Baris pencarian takson
        gb_cari = QGroupBox("Pencarian takson tanaman")
        v_cari = QVBoxLayout(gb_cari)
        v_cari.setContentsMargins(10, 8, 10, 8)
        v_cari.setSpacing(6)

        h_input = QHBoxLayout()
        h_input.addWidget(QLabel("Tanaman:"))
        self.ed_nama = QLineEdit()
        self.ed_nama.setPlaceholderText("Nama lokal atau ilmiah (mis. sambiloto, kunyit, Curcuma longa, Zingiber…)")
        self.ed_nama.returnPressed.connect(self.cari_takson)
        h_input.addWidget(self.ed_nama, 1)

        self.c_genus = QCheckBox("Sertakan seluruh genus")
        self.c_genus.setToolTip("Cari senyawa dari takson spesies ini beserta seluruh takson turunannya")
        h_input.addWidget(self.c_genus)

        self.b_cari = QPushButton("Cari takson")
        self.b_cari.setObjectName("primary")
        self.b_cari.clicked.connect(self.cari_takson)
        h_input.addWidget(self.b_cari)

        self.b_batal = QPushButton("✕ Batal")
        self.b_batal.setVisible(False)
        self.b_batal.clicked.connect(self._batalkan)
        h_input.addWidget(self.b_batal)

        v_cari.addLayout(h_input)

        h_takson = QHBoxLayout()
        h_takson.addWidget(QLabel("Pilih takson:"))
        self.c_takson = QComboBox()
        self.c_takson.currentIndexChanged.connect(self._takson_terpilih)
        h_takson.addWidget(self.c_takson, 1)

        self.b_ambil = QPushButton("Ambil senyawa")
        self.b_ambil.clicked.connect(self.ambil_senyawa)
        h_takson.addWidget(self.b_ambil)
        v_cari.addLayout(h_takson)

        lay.addWidget(gb_cari)

        # 3. Konten tengah: Splitter (Tabel Kiri, Pratinjau Kanan)
        spl = QSplitter(Qt.Horizontal)

        # Panel Kiri (Saringan + Tabel)
        w_kiri = QWidget()
        v_kiri = QVBoxLayout(w_kiri)
        v_kiri.setContentsMargins(0, 0, 0, 0)
        v_kiri.setSpacing(6)

        # Saringan
        f_saring = QHBoxLayout()
        f_saring.addWidget(QLabel("MW:"))
        self.s_mw0 = QDoubleSpinBox()
        self.s_mw0.setRange(0, 3000)
        self.s_mw0.setValue(0)
        self.s_mw0.setDecimals(0)
        self.s_mw0.valueChanged.connect(self._terapkan_saringan)
        f_saring.addWidget(self.s_mw0)
        f_saring.addWidget(QLabel("–"))
        self.s_mw1 = QDoubleSpinBox()
        self.s_mw1.setRange(0, 3000)
        self.s_mw1.setValue(900)
        self.s_mw1.setDecimals(0)
        self.s_mw1.valueChanged.connect(self._terapkan_saringan)
        f_saring.addWidget(self.s_mw1)

        self.c_lipinski = QCheckBox("Lipinski ≤ 1")
        self.c_lipinski.setChecked(False)
        self.c_lipinski.toggled.connect(self._terapkan_saringan)
        f_saring.addWidget(self.c_lipinski)

        self.s_qed = QDoubleSpinBox()
        self.s_qed.setRange(0.0, 1.0)
        self.s_qed.setValue(0.0)
        self.s_qed.setSingleStep(0.1)
        self.s_qed.setPrefix("QED ≥ ")
        self.s_qed.valueChanged.connect(self._terapkan_saringan)
        f_saring.addWidget(self.s_qed)

        self.c_rujukan = QCheckBox("Ada rujukan")
        self.c_rujukan.setChecked(False)
        self.c_rujukan.toggled.connect(self._terapkan_saringan)
        f_saring.addWidget(self.c_rujukan)

        self.c_stereo = QCheckBox("Stereo lengkap")
        self.c_stereo.setChecked(False)
        self.c_stereo.toggled.connect(self._terapkan_saringan)
        f_saring.addWidget(self.c_stereo)

        self.ed_saring_nama = QLineEdit()
        self.ed_saring_nama.setPlaceholderText("Saring nama senyawa…")
        self.ed_saring_nama.textChanged.connect(self._terapkan_saringan)
        f_saring.addWidget(self.ed_saring_nama)

        v_kiri.addLayout(f_saring)

        # Tabel Senyawa
        kolom_tabel = ["Pilih", "Nama", "MW", "QED", "Rujukan", "Tahun", "Asal"]
        self.tabel = kit.tabel(kolom_tabel, regang=1, urut=True)
        self.tabel.itemSelectionChanged.connect(self._tabel_dipilih)
        self.tabel.itemChanged.connect(self._centang_berubah)
        v_kiri.addWidget(self.tabel, 1)

        self.l_info_tabel = QLabel("Belum ada data senyawa.")
        self.l_info_tabel.setObjectName("muted")
        v_kiri.addWidget(self.l_info_tabel)

        spl.addWidget(w_kiri)

        # Panel Kanan (Pratinjau Molekul 2D & Rujukan)
        w_kanan = QWidget()
        w_kanan.setMinimumWidth(320)
        v_kanan = QVBoxLayout(w_kanan)
        v_kanan.setContentsMargins(8, 0, 0, 0)
        v_kanan.setSpacing(6)

        self.lbl_gambar = QLabel()
        self.lbl_gambar.setFixedSize(300, 210)
        self.lbl_gambar.setAlignment(Qt.AlignCenter)
        self.lbl_gambar.setStyleSheet(f"border: 1px solid {kit.hx('line')}; border-radius: 4px;")
        v_kanan.addWidget(self.lbl_gambar, 0, Qt.AlignCenter)

        self.txt_detail = QTextBrowser()
        self.txt_detail.setOpenExternalLinks(True)
        v_kanan.addWidget(self.txt_detail, 1)

        # Tombol pranala luar
        h_tautan = QHBoxLayout()
        self.b_wikidata = QPushButton("Buka di Wikidata")
        self.b_wikidata.clicked.connect(self._buka_wikidata)
        self.b_knapsack = QPushButton("Buka di KNApSAcK")
        self.b_knapsack.clicked.connect(self._buka_knapsack)
        h_tautan.addWidget(self.b_wikidata)
        h_tautan.addWidget(self.b_knapsack)
        v_kanan.addLayout(h_tautan)

        spl.addWidget(w_kanan)
        spl.setStretchFactor(0, 3)
        spl.setStretchFactor(1, 1)

        lay.addWidget(spl, 1)

        # 4. Baris Tombol Aksi Bawah
        b_semua = QPushButton("Centang semua")
        b_semua.clicked.connect(lambda: self._centang_semua(True))
        b_kosong = QPushButton("Kosongkan")
        b_kosong.clicked.connect(lambda: self._centang_semua(False))
        b_ekspor = QPushButton("Ekspor CSV…")
        b_ekspor.clicked.connect(self.ekspor_csv)

        if self.mode == "senyawa":
            self.b_impor = kit.tombol("Pakai untuk farmakologi jaringan", self.kirim_senyawa, utama=True,
                                      tip="Ambil nama dan SMILES-nya saja; struktur 3D baru dibuat nanti "
                                          "bila senyawanya dibawa ke docking")
        else:
            self.b_impor = kit.tombol("Impor ke proyek", self.impor_ke_proyek, utama=True)
        lay.addLayout(kit.bar_bawah(
            self,
            kiri=[b_semua, b_kosong, b_ekspor],
            kanan=[self.b_impor]
        ))

        # Pemuatan awal jika ada teks
        self._segarkan_tampilan_detail(None)

    def _batalkan(self):
        if self._batal:
            self._batal.set()
        self.b_batal.setVisible(False)
        self.b_cari.setEnabled(True)
        self.b_ambil.setEnabled(True)

    def cari_takson(self):
        q = self.ed_nama.text().strip()
        if not q:
            return
        self.c_takson.clear()
        self.b_cari.setEnabled(False)
        self.b_batal.setVisible(True)
        self._batal = threading.Event()
        self.l_info_tabel.setText("Mencari takson tanaman di Wikidata…")

        def kerja_cari(lapor):
            return tanaman.cari_takson(q)

        def selesai(hasil):
            self.b_cari.setEnabled(True)
            self.b_batal.setVisible(False)
            if not hasil:
                self.l_info_tabel.setText(f"Takson '{q}' tidak ditemukan. Coba nama latin atau sinonim lain.")
                return
            for h in hasil:
                label = f"{h['nama_ilmiah']} — {h['peringkat']} — {h['qid']}"
                if h.get("nama_lokal"):
                    label = f"{h['nama_lokal'].title()} ({h['nama_ilmiah']}) — {h['qid']}"
                self.c_takson.addItem(label, h)
            self.l_info_tabel.setText(f"{len(hasil)} takson ditemukan. Klik 'Ambil senyawa'.")
            self.ambil_senyawa()

        def galat(g):
            self.b_cari.setEnabled(True)
            self.b_batal.setVisible(False)
            self.l_info_tabel.setText(f"Pencarian takson gagal: {g}")

        kerja.jalankan(kerja_cari, selesai=selesai, galat=galat)

    def _takson_terpilih(self):
        # Bersihkan tabel jika takson diganti
        pass

    def ambil_senyawa(self):
        idx = self.c_takson.currentIndex()
        if idx < 0:
            return
        takson = self.c_takson.currentData()
        if not takson:
            return

        qid = takson["qid"]
        nama_ilmiah = takson["nama_ilmiah"]
        turunan = self.c_genus.isChecked()

        self.b_ambil.setEnabled(False)
        self.b_batal.setVisible(True)
        self._batal = threading.Event()
        self.l_info_tabel.setText(f"Mengambil senyawa untuk {nama_ilmiah} dari LOTUS…")

        def kerja_ambil(lapor):
            lotus_list, jejak = tanaman.senyawa_takson(qid, turunan=turunan, batas=5000, batal=self._batal)
            coco_list = tanaman.senyawa_coconut_organisme(nama_ilmiah, batas=5000)
            gabung = tanaman.gabung_senyawa(lotus_list, coco_list)
            std = tanaman.standarisasi(gabung)
            return std, jejak

        def selesai(res):
            self.b_ambil.setEnabled(True)
            self.b_batal.setVisible(False)
            self.semua_senyawa, self.jejak_aktif = res
            self._dipilih.clear()
            self._terapkan_saringan()

        def galat(g):
            self.b_ambil.setEnabled(True)
            self.b_batal.setVisible(False)
            self.l_info_tabel.setText(f"Pengambilan senyawa gagal: {g}")

        kerja.jalankan(kerja_ambil, selesai=selesai, galat=galat)

    def _terapkan_saringan(self):
        if not self.semua_senyawa:
            self.tabel.setRowCount(0)
            self.l_info_tabel.setText("Belum ada data senyawa.")
            return

        mw_min = self.s_mw0.value()
        mw_max = self.s_mw1.value()
        hanya_lip = self.c_lipinski.isChecked()
        qed_min = self.s_qed.value()
        hanya_ruj = self.c_rujukan.isChecked()
        hanya_stereo = self.c_stereo.isChecked()
        nama_q = self.ed_saring_nama.text().strip().lower()

        tersaring = []
        for s in self.semua_senyawa:
            if s.get("galat"):
                continue
            mw = s.get("mw", 0.0)
            if not (mw_min <= mw <= mw_max):
                continue
            if hanya_lip and s.get("lipinski", 0) > 1:
                continue
            if s.get("qed", 0.0) < qed_min:
                continue
            if hanya_ruj and len(s.get("rujukan", [])) == 0:
                continue
            if hanya_stereo and not s.get("stereo_lengkap", False):
                continue
            if nama_q and nama_q not in s.get("nama", "").lower() and nama_q not in s.get("qid", "").lower():
                continue
            tersaring.append(s)

        self.senyawa_tersaring = tersaring
        self._isi_tabel()

    def _isi_tabel(self):
        t = self.tabel
        t.setSortingEnabled(False)
        t.blockSignals(True)
        t.setRowCount(len(self.senyawa_tersaring))

        for r, s in enumerate(self.senyawa_tersaring):
            # 0. Centang
            it_cek = QTableWidgetItem()
            it_cek.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            it_cek.setCheckState(Qt.Checked if _kunci(s) in self._dipilih else Qt.Unchecked)
            it_cek.setData(Qt.UserRole, r)
            t.setItem(r, 0, it_cek)

            # 1. Nama
            t.setItem(r, 1, QTableWidgetItem(s.get("nama") or s.get("qid", "")))

            # 2. MW
            mw_val = s.get("mw", 0.0)
            it_mw = QTableWidgetItem(kit.f(mw_val, 1))
            it_mw.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t.setItem(r, 2, it_mw)

            # 3. QED
            qed_val = s.get("qed", 0.0)
            it_qed = QTableWidgetItem(kit.f(qed_val, 2))
            it_qed.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t.setItem(r, 3, it_qed)

            # 4. Rujukan
            n_ruj = len(s.get("rujukan", []))
            it_ruj = QTableWidgetItem(str(n_ruj) if n_ruj else "-")
            it_ruj.setTextAlignment(Qt.AlignCenter)
            t.setItem(r, 4, it_ruj)

            # 5. Tahun
            th = s.get("tahun")
            it_th = QTableWidgetItem(str(th) if th else "-")
            it_th.setTextAlignment(Qt.AlignCenter)
            t.setItem(r, 5, it_th)

            # 6. Asal
            t.setItem(r, 6, QTableWidgetItem(s.get("asal", "LOTUS")))

        t.resizeColumnToContents(0)
        t.resizeColumnToContents(2)
        t.resizeColumnToContents(3)
        t.resizeColumnToContents(4)
        t.resizeColumnToContents(5)
        t.resizeColumnToContents(6)
        t.setSortingEnabled(True)
        t.blockSignals(False)

        self._hitung_pilihan()

    def _centang_semua(self, on: bool):
        self.tabel.blockSignals(True)
        for r in range(self.tabel.rowCount()):
            it = self.tabel.item(r, 0)
            if it:
                it.setCheckState(Qt.Checked if on else Qt.Unchecked)
                self._catat_centang(it)
        self.tabel.blockSignals(False)
        self._hitung_pilihan()

    def _catat_centang(self, it):
        idx = it.data(Qt.UserRole)
        if idx is None or idx >= len(self.senyawa_tersaring):
            return
        k = _kunci(self.senyawa_tersaring[idx])
        if it.checkState() == Qt.Checked:
            self._dipilih.add(k)
        else:
            self._dipilih.discard(k)

    def _centang_berubah(self, it):
        if it.column() == 0:
            self._catat_centang(it)
            self._hitung_pilihan()

    def _hitung_pilihan(self):
        dipilih = 0
        for r in range(self.tabel.rowCount()):
            it = self.tabel.item(r, 0)
            if it and it.checkState() == Qt.Checked:
                dipilih += 1
        total = len(self.senyawa_tersaring)
        self.l_info_tabel.setText(f"{total} senyawa · {dipilih} dipilih")
        if self.mode == "senyawa":
            self.b_impor.setText(f"Pakai {dipilih} senyawa" if dipilih else "Pakai untuk farmakologi jaringan")
        else:
            self.b_impor.setText(f"Impor {dipilih} ke proyek" if dipilih else "Impor ke proyek")

    def _tabel_dipilih(self):
        r = self.tabel.currentRow()
        if r < 0 or r >= len(self.senyawa_tersaring):
            self._segarkan_tampilan_detail(None)
            return
        it_cek = self.tabel.item(r, 0)
        idx = it_cek.data(Qt.UserRole) if it_cek else r
        if idx is not None and idx < len(self.senyawa_tersaring):
            self._segarkan_tampilan_detail(self.senyawa_tersaring[idx])

    def _segarkan_tampilan_detail(self, s: dict | None):
        if not s:
            self.lbl_gambar.setPixmap(QPixmap())
            self.txt_detail.setHtml("<p class='muted'>Pilih senyawa di tabel untuk melihat struktur dan rujukan.</p>")
            self.b_wikidata.setEnabled(False)
            self.b_knapsack.setEnabled(False)
            return

        smi = s.get("smiles_std") or s.get("smiles", "")
        pix = _gambar_mol_pixmap(smi, 280, 200, kit.mode())
        self.lbl_gambar.setPixmap(pix)

        qid = s.get("qid", "")
        self.b_wikidata.setEnabled(bool(qid and qid.startswith("Q")))
        self.b_knapsack.setEnabled(True)

        sifat_d = s.get("sifat") or {}
        rumus = sifat_d.get("rumus", "-")
        mw = kit.f(s.get("mw", 0.0), 1)
        logp = kit.f(s.get("logp", 0.0), 2)
        qed = kit.f(s.get("qed", 0.0), 2)
        tpsa = kit.f(s.get("tpsa", 0.0), 1)

        # Lencana peringatan
        lencana_html = []
        if s.get("pains"):
            lencana_html.append(f"<span style='color:{kit.hx('bad')}; font-weight:600;'>[Peringatan PAINS]</span>")
        if s.get("lipinski", 0) > 1:
            lencana_html.append(f"<span style='color:{kit.hx('warn')}; font-weight:600;'>[Melanggar Lipinski]</span>")
        if not s.get("stereo_lengkap", False):
            lencana_html.append(f"<span style='color:{kit.hx('mut')};'>[Stereokimia parsial]</span>")

        # Rujukan DOI
        ruj_html = []
        for doi in s.get("rujukan", []):
            if doi.startswith("10."):
                ruj_html.append(f"<li><a href='https://doi.org/{quote(doi)}'>{doi}</a></li>")
            elif doi.startswith("Wikidata Q"):
                q = doi.split()[-1]
                ruj_html.append(f"<li><a href='https://www.wikidata.org/wiki/{q}'>{doi}</a> (tanpa DOI)</li>")
            else:
                ruj_html.append(f"<li>{doi}</li>")
        if not ruj_html:
            ruj_html.append("<li><i>Tidak ada DOI langsung</i></li>")

        html = f"""
        <div style='font-family: Segoe UI, sans-serif; font-size: 9.5pt;'>
          <h3 style='margin: 0 0 4px 0; color: {kit.hx("ink")};'>{s.get("nama") or qid}</h3>
          <p style='margin: 0 0 6px 0; color: {kit.hx("mut")};'>ID: {qid} · Asal: {s.get("asal", "LOTUS")}</p>
          <p style='margin: 0 0 6px 0;'>{' '.join(lencana_html)}</p>
          <table cellpadding='3' style='width: 100%; border-collapse: collapse; margin-bottom: 8px;'>
            <tr><td><b>Rumus:</b></td><td>{rumus}</td><td><b>MW:</b></td><td>{mw} Da</td></tr>
            <tr><td><b>LogP:</b></td><td>{logp}</td><td><b>TPSA:</b></td><td>{tpsa} Å²</td></tr>
            <tr><td><b>QED:</b></td><td>{qed}</td><td><b>SAScore:</b></td><td>{kit.f(s.get("sascore", 0.0), 2)}</td></tr>
          </table>
          <b>Rujukan pustaka:</b>
          <ul style='margin-top: 4px; padding-left: 18px;'>
            {''.join(ruj_html)}
          </ul>
        </div>
        """
        self.txt_detail.setHtml(html)

    def _buka_wikidata(self):
        r = self.tabel.currentRow()
        if r < 0 or r >= len(self.senyawa_tersaring):
            return
        s = self.senyawa_tersaring[r]
        qid = s.get("qid", "")
        if qid.startswith("Q"):
            QDesktopServices.openUrl(QUrl(f"https://www.wikidata.org/wiki/{qid}"))

    def _buka_knapsack(self):
        QDesktopServices.openUrl(QUrl("http://www.knapsackfamily.com/knapsack_core/top.html"))

    def ekspor_csv(self):
        if not self.senyawa_tersaring:
            QMessageBox.information(self, "Ekspor CSV", "Belum ada senyawa yang bisa diekspor.")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Ekspor daftar senyawa", "senyawa_tanaman.csv", "CSV (*.csv)")
        if not f:
            return
        with open(f, "w", encoding="utf-8", newline="") as fp:
            w = csv.writer(fp)
            w.writerow(["QID", "Nama", "SMILES", "InChIKey", "MW", "LogP", "TPSA", "QED", "Lipinski", "Asal", "Rujukan"])
            for s in self.senyawa_tersaring:
                w.writerow([
                    s.get("qid", ""), s.get("nama", ""), s.get("smiles_std", s.get("smiles", "")),
                    s.get("inchikey", ""), s.get("mw", ""), s.get("logp", ""), s.get("tpsa", ""),
                    s.get("qed", ""), s.get("lipinski", ""), s.get("asal", ""),
                    "; ".join(s.get("rujukan", []))
                ])
        QMessageBox.information(self, "Ekspor CSV", f"Berhasil mengekspor {len(self.senyawa_tersaring)} senyawa.")

    def _senyawa_dicentang(self) -> list:
        dipilih = []
        for r in range(self.tabel.rowCount()):
            it = self.tabel.item(r, 0)
            if it and it.checkState() == Qt.Checked:
                idx = it.data(Qt.UserRole)
                if idx is not None and idx < len(self.senyawa_tersaring):
                    dipilih.append(self.senyawa_tersaring[idx])
        return dipilih

    def kirim_senyawa(self):
        """Mode "senyawa": pulangkan nama dan SMILES terpilih tanpa menyentuh proyek maupun viewer."""
        dipilih = self._senyawa_dicentang()
        if not dipilih:
            QMessageBox.information(self, "Senyawa", "Centang minimal satu senyawa.")
            return
        takson = (self.c_takson.currentData() or {}).get("nama_ilmiah", "")
        hasil = []
        for s in dipilih:
            smi = s.get("smiles_std") or s.get("smiles") or ""
            if not smi:
                continue
            hasil.append({"nama": s.get("nama") or s.get("qid") or "Senyawa", "smiles": smi,
                          "sumber": takson or "LOTUS"})
        self.senyawaDipilih.emit(hasil)
        self.accept()

    def impor_ke_proyek(self):
        dipilih = self._senyawa_dicentang()

        if not dipilih:
            QMessageBox.information(self, "Impor ligan", "Centang minimal satu senyawa untuk diimpor.")
            return

        if len(dipilih) > 200:
            if QMessageBox.question(
                self, "Impor ligan",
                f"Impor {len(dipilih)} senyawa? Pembuatan konformasi 3D dapat memakan waktu beberapa saat."
            ) != QMessageBox.Yes:
                return

        takson_info = self.c_takson.currentData() or {}
        nama_takson = takson_info.get("nama_ilmiah", "Tanaman Obat")

        # Cek duplikasi InChIKey terhadap objek proyek yang sudah ada
        inchikey_ada = set()
        if self.jw and hasattr(self.jw, "objek"):
            for o in self.jw.objek.values():
                if hasattr(o, "inchikey") and o.inchikey:
                    inchikey_ada.add(o.inchikey[:14])
        if self.jw and hasattr(self.jw, "proyek") and self.jw.proyek:
            for l in self.jw.proyek.ligan:
                ik = l.get("inchikey", "")
                if ik:
                    inchikey_ada.add(ik[:14])

        ob_baru = []
        duplikat = 0
        gagal = 0
        ada_nama = {o.nama for o in self.jw.objek.values()} if self.jw else set()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for s in dipilih:
                ik = s.get("inchikey", "")
                if ik and ik[:14] in inchikey_ada:
                    duplikat += 1
                    continue

                nama = s.get("nama") or s.get("qid") or "Senyawa"
                nama_bersih = nama.strip()
                if len(nama_bersih) > 40:
                    nama_bersih = s.get("qid") or nama_bersih[:40]

                smi = s.get("smiles_std") or s.get("smiles", "")
                try:
                    obj_list = molekul.dari_smiles(smi, nama_bersih)
                    for x in obj_list:
                        x.info["asal"] = {
                            "sumber": s.get("asal", "LOTUS (Wikidata)"),
                            "takson": nama_takson,
                            "qid": s.get("qid", ""),
                            "rujukan": s.get("rujukan", [])
                        }
                        if ik:
                            x.inchikey = ik
                    ob_baru.extend(obj_list)
                    if ik:
                        inchikey_ada.add(ik[:14])
                    ada_nama.add(nama_bersih)
                except Exception:
                    gagal += 1
        finally:
            QApplication.restoreOverrideCursor()

        # Masukkan ke objek aplikasi / proyek
        if ob_baru and self.jw:
            self.jw.tambah_objek(ob_baru, fokus=False)

        # Catat jejak ke proyek
        if self.jw and hasattr(self.jw, "proyek") and self.jw.proyek:
            pr = self.jw.proyek
            if self.jejak_aktif:
                pr.catat_jejak(self.jejak_aktif)
            # Jika ada COCONUT yang dipakai
            if any("COCONUT" in s.get("asal", "") for s in dipilih):
                jejak_coco = Jejak(
                    sumber="COCONUT 2.0",
                    versi="2.0",
                    diambil=tanaman.sumber_data.datetime.now().isoformat(timespec="seconds"),
                    kueri=nama_takson,
                    lisensi="CC BY 4.0"
                )
                pr.catat_jejak(jejak_coco)
            if hasattr(self.jw, "minta_simpan"):
                self.jw.minta_simpan()

        pesan = f"Berhasil mengimpor {len(ob_baru)} senyawa ke proyek."
        if duplikat > 0:
            pesan += f"\n({duplikat} senyawa duplikat dilewati)."
        if gagal > 0:
            pesan += f"\n({gagal} senyawa gagal diproses)."

        QMessageBox.information(self, "Impor selesai", pesan)
        if self.jw and hasattr(self.jw, "log"):
            self.jw.log.tulis(f"Tanaman ({nama_takson}): {len(ob_baru)} ligan diimpor ({duplikat} duplikat)")
        self.accept()
