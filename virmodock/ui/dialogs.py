"""Dialog: ambil dari database, wizard pertama kali, pengaturan."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QProgressBar, QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget, QWizard, QWizardPage)

from . import kit

ORGANISME = [("Semua organisme", None), ("Homo sapiens (manusia)", 9606), ("Mus musculus (mencit)", 10090),
             ("Rattus norvegicus (tikus)", 10116), ("SARS-CoV-2", 2697049), ("Escherichia coli K-12", 83333),
             ("Mycobacterium tuberculosis H37Rv", 83332), ("Plasmodium falciparum 3D7", 36329),
             ("Staphylococcus aureus NCTC 8325", 93061), ("Candida albicans SC5314", 237561)]


class DialogAmbil(QDialog):
    """Unduh struktur dari RCSB PDB / PubChem, atau buat dari SMILES."""

    def __init__(self, parent=None, tab=0):
        super().__init__(parent)
        self.setWindowTitle("Impor dari database")
        self.setMinimumWidth(460)
        self.resize(860, 600)
        lay = QVBoxLayout(self)
        self.tab = QTabWidget()
        # RCSB
        self.tab.addTab(self._tab_rcsb(), "RCSB PDB")
        # PubChem
        w2 = QWidget()
        v2 = QVBoxLayout(w2)
        v2.addWidget(self._ket("Satu senyawa per baris: nama (quercetin) atau CID (5280343)."))
        self.pubchem = QPlainTextEdit()
        self.pubchem.setPlaceholderText("quercetin\nkaempferol\n5280343")
        v2.addWidget(self.pubchem)
        self.tab.addTab(w2, "PubChem")
        # SMILES
        w3 = QWidget()
        v3 = QVBoxLayout(w3)
        v3.addWidget(self._ket("Satu per baris: SMILES lalu nama (opsional). Struktur 3D dibuat dan diminimisasi (MMFF)."))
        self.smiles = QPlainTextEdit()
        self.smiles.setPlaceholderText("CC(=O)Oc1ccccc1C(=O)O aspirin")
        v3.addWidget(self.smiles)
        self.tab.addTab(w3, "SMILES")
        self.tab.addTab(self._tab_alphafold(), "AlphaFold DB")
        self.tab.setCurrentIndex(tab)
        lay.addWidget(self.tab)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Impor")
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText("Batal")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _tab_rcsb(self):
        w = QWidget()
        v = QVBoxLayout(w)
        f1 = QFormLayout()
        self.pdbid = QLineEdit()
        self.pdbid.setPlaceholderText("mis. 1HSG, 6LU7")
        self.pdbid.setMaxLength(4)
        f1.addRow("ID PDB", self.pdbid)
        v.addLayout(f1)
        v.addWidget(self._ket("Belum tahu kodenya? Cari dengan nama protein, gen, ligan, atau penyakit - VirmoDock "
                              "menyarankan struktur terbaik untuk docking (sinar-X, ada ligan kristal, resolusi terkecil)."))
        h = QHBoxLayout()
        self.rc_kueri = QLineEdit()
        self.rc_kueri.setPlaceholderText("HIV-1 protease, EGFR erlotinib, acetylcholinesterase")
        self.rc_org = QComboBox()
        for t, nama in (("Semua organisme", None), ("Homo sapiens (manusia)", "Homo sapiens"),
                        ("Mus musculus (mencit)", "Mus musculus"), ("Rattus norvegicus (tikus)", "Rattus norvegicus"),
                        ("SARS-CoV-2", "Severe acute respiratory syndrome coronavirus 2"),
                        ("HIV-1", "Human immunodeficiency virus 1"), ("Escherichia coli", "Escherichia coli"),
                        ("Mycobacterium tuberculosis", "Mycobacterium tuberculosis"),
                        ("Plasmodium falciparum", "Plasmodium falciparum"),
                        ("Staphylococcus aureus", "Staphylococcus aureus")):
            self.rc_org.addItem(t, nama)
        b = QPushButton("Cari")
        b.clicked.connect(self._rc_cari)
        h.addWidget(self.rc_kueri, 1)
        h.addWidget(self.rc_org)
        h.addWidget(b)
        v.addLayout(h)
        h2 = QHBoxLayout()
        self.rc_ligan = QCheckBox("Hanya yang punya ligan")
        self.rc_ligan.setChecked(True)
        self.rc_res = QComboBox()
        for t, x in (("Resolusi apa saja", None), ("≤ 2,0 Å", 2.0), ("≤ 2,5 Å", 2.5), ("≤ 3,0 Å", 3.0)):
            self.rc_res.addItem(t, x)
        self.rc_res.setCurrentIndex(2)
        self.rc_urut = QComboBox()
        self.rc_urut.addItem("Urut relevansi", "skor")
        self.rc_urut.addItem("Urut resolusi", "resolusi")
        for x in (self.rc_ligan, self.rc_res, self.rc_urut):
            h2.addWidget(x)
        h2.addStretch(1)
        v.addLayout(h2)
        self.rc_daftar = QTreeWidget()
        self.rc_daftar.setHeaderLabels(["Kode", "Resolusi (Å)", "Ligan kristal", "Judul", "Organisme"])
        self.rc_daftar.setRootIsDecorated(False)
        self.rc_daftar.setMinimumHeight(220)
        self.rc_daftar.setSelectionMode(QAbstractItemView.SingleSelection)
        self.rc_daftar.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.rc_daftar.currentItemChanged.connect(
            lambda it, *_: it is not None and self.pdbid.setText(it.data(0, Qt.UserRole) or ""))
        self.rc_daftar.itemDoubleClicked.connect(lambda *_: self.accept())
        v.addWidget(self.rc_daftar, 1)
        self.rc_status = self._ket("Protein, ligan asli, air, dan ion dipisah menjadi objek sendiri.")
        v.addWidget(self.rc_status)
        return w

    def _rc_cari(self):
        from ..core import rcsb
        from . import kerja, kit
        q = self.rc_kueri.text().strip()
        if not q:
            return
        self.rc_daftar.clear()
        self.rc_status.setText("Mencari di RCSB PDB…")
        arg = dict(organisme=self.rc_org.currentData(), hanya_ligan=self.rc_ligan.isChecked(),
                   resolusi_maks=self.rc_res.currentData(), urut=self.rc_urut.currentData())

        def selesai(h):
            total, entri = h
            kode_saran, alasan = rcsb.saran(entri)
            self.rc_daftar.clear()
            for e in sorted(entri, key=lambda e: e["kode"] != kode_saran):
                it = QTreeWidgetItem([e["kode"] + ("  ★" if e["kode"] == kode_saran else ""),
                                      f"{e['resolusi']:.2f}".replace(".", ",") if e["resolusi"] else "-",
                                      ", ".join(c for c, _n in e["ligan"][:4]) or "-", e["judul"], e["organisme"]])
                it.setData(0, Qt.UserRole, e["kode"])
                it.setToolTip(2, "\n".join(f"{c}: {n}" for c, n in e["ligan"]) or "Tidak ada ligan kristal (selain "
                                                                                   "aditif/ion)")
                it.setToolTip(3, f"{e['judul']}\n{e['protein']}\n{e['metode']} · rilis {e['tanggal']}")
                it.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                if e["kode"] == kode_saran:
                    for c in range(5):
                        f = it.font(c)
                        f.setBold(True)
                        it.setFont(c, f)
                self.rc_daftar.addTopLevelItem(it)
            for c in (0, 1, 2):
                self.rc_daftar.resizeColumnToContents(c)
            if entri:
                self.rc_daftar.setCurrentItem(self.rc_daftar.topLevelItem(0))
                self.rc_status.setText(f"{len(entri)} dari {total} entri. ★ Disarankan: {kode_saran} ({alasan}). "
                                       "Klik dua kali untuk mengimpor.")
            else:
                self.rc_status.setText("Tidak ditemukan. Coba kata kunci lain, longgarkan resolusi, atau matikan "
                                       "'Hanya yang punya ligan'.")
        kerja.jalankan(lambda lapor: rcsb.cari(q, **arg), selesai=selesai,
                       galat=lambda g: self.rc_status.setText("Pencarian gagal: " + g.splitlines()[0]))

    def _tab_alphafold(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(self._ket("Struktur prediksi AlphaFold untuk protein yang belum punya struktur kristal. "
                              "Ketik kode UniProt (mis. P00918) atau nama protein/gen (mis. ACE2), lalu Cari."))
        h = QHBoxLayout()
        self.af_kueri = QLineEdit()
        self.af_kueri.setPlaceholderText("P00918, ACE2, carbonic anhydrase 2")
        self.af_org = QComboBox()
        for t, tx in ORGANISME:
            self.af_org.addItem(t, tx)
        self.af_org.setCurrentIndex(1)
        b = QPushButton("Cari")
        b.clicked.connect(self._af_cari)
        h.addWidget(self.af_kueri, 1)
        h.addWidget(self.af_org)
        h.addWidget(b)
        v.addLayout(h)
        self.af_daftar = QListWidget()
        self.af_daftar.setMinimumHeight(150)
        self.af_daftar.itemDoubleClicked.connect(lambda *_: self.accept())
        v.addWidget(self.af_daftar)
        self.af_status = self._ket("")
        v.addWidget(self.af_status)
        h2 = QHBoxLayout()
        self.af_pangkas = QCheckBox("Pangkas residu pLDDT <")
        self.af_pangkas.setChecked(True)
        self.af_ambang = QDoubleSpinBox()
        self.af_ambang.setRange(30, 90)
        self.af_ambang.setValue(50)
        self.af_ambang.setDecimals(0)
        self.af_ujung = QComboBox()
        self.af_ujung.addItem("hanya di ujung N/C", True)
        self.af_ujung.addItem("di mana saja", False)
        self.af_pangkas.toggled.connect(self.af_ambang.setEnabled)
        self.af_pangkas.toggled.connect(self.af_ujung.setEnabled)
        h2.addWidget(self.af_pangkas)
        h2.addWidget(self.af_ambang)
        h2.addWidget(self.af_ujung)
        h2.addStretch(1)
        v.addLayout(h2)
        v.addWidget(self._ket("Ujung N/C yang tak beraturan (pLDDT rendah) bisa menutupi kantong dan mengganggu "
                              "deteksi kantong. Protein diwarnai menurut pLDDT: biru tua > 90, biru muda 70-90, "
                              "kuning 50-70, jingga < 50. Lisensi data CC BY 4.0 - kutip Jumper dkk. 2021 dan "
                              "Varadi dkk. 2024."))
        return w

    def accept(self):
        # tab RCSB: Enter di kolom cari = cari (bukan impor)
        if self.tab.currentIndex() == 0 and self.rc_kueri.hasFocus():
            self._rc_cari()
            return
        # tab AlphaFold: Enter di kolom cari / Impor tanpa pilihan = jalankan pencarian dulu
        if self.tab.currentIndex() == 3:
            from ..core import alphafold
            it = self.af_daftar.currentItem()
            if self.af_kueri.hasFocus() or not (it or alphafold.aksesi_sah(self.af_kueri.text())):
                self._af_cari()
                return
        super().accept()

    def _af_cari(self):
        from ..core import alphafold
        from . import kerja
        q = self.af_kueri.text().strip()
        if not q:
            return
        self.af_daftar.clear()
        self.af_status.setText("Mencari di UniProt…")
        org = None if alphafold.aksesi_sah(q) else self.af_org.currentData()

        def selesai(hasil):
            self.af_daftar.clear()
            for r in hasil:
                it = QListWidgetItem(f"{r['aksesi']}  ·  {r['nama'] or '-'}" + (f"  ({r['gen']})" if r['gen'] else "")
                                     + f"  ·  {r['organisme']}" + (f"  ·  {r['panjang']} aa" if r['panjang'] else ""))
                it.setData(Qt.UserRole, r["aksesi"])
                self.af_daftar.addItem(it)
            if hasil:
                self.af_daftar.setCurrentRow(0)
            self.af_status.setText(f"{len(hasil)} hasil. Pilih satu lalu Impor (atau klik dua kali)." if hasil else
                                   "Tidak ditemukan. Coba nama lain, kode UniProt, atau 'Semua organisme'.")
        kerja.jalankan(lambda lapor: alphafold.cari(q, org), selesai=selesai,
                       galat=lambda g: self.af_status.setText("Pencarian gagal: " + g.splitlines()[0]))

    def _ket(self, t):
        l = QLabel(t)
        l.setObjectName("muted")
        l.setWordWrap(True)
        return l

    def permintaan(self):
        i = self.tab.currentIndex()
        if i == 0:
            return ("rcsb", [self.pdbid.text().strip()]) if self.pdbid.text().strip() else None
        if i == 3:
            it = self.af_daftar.currentItem()
            aksesi = it.data(Qt.UserRole) if it else self.af_kueri.text().strip().upper()
            from ..core import alphafold
            if not alphafold.aksesi_sah(aksesi or ""):
                return None
            return ("alphafold", [aksesi], {"pangkas_aktif": self.af_pangkas.isChecked(),
                                            "ambang": self.af_ambang.value(), "hanya_ujung": self.af_ujung.currentData()})
        teks = (self.pubchem if i == 1 else self.smiles).toPlainText()
        baris = [b.strip() for b in teks.splitlines() if b.strip() and not b.startswith("#")]
        return (("pubchem" if i == 1 else "smiles"), baris) if baris else None


class Wizard(QWizard):
    """Wizard pertama kali: cek sistem, GPU, software terkait, folder kerja."""

    def __init__(self, env, folder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selamat datang di VirmoDock")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(620, 460)
        self.setButtonText(QWizard.NextButton, "Lanjut")
        self.setButtonText(QWizard.BackButton, "Kembali")
        self.setButtonText(QWizard.FinishButton, "Selesai")
        self.setButtonText(QWizard.CancelButton, "Lewati")
        self.env = env
        self.folder = folder

        p1 = QWizardPage()
        p1.setTitle("Pemeriksaan sistem")
        p1.setSubTitle("VirmoDock memeriksa perangkat keras dan program pendukung di laptop ini.")
        v = QVBoxLayout(p1)
        from .logo import Logo
        v.addWidget(Logo(52))
        v.addSpacing(10)
        v.addWidget(QLabel(self._ringkas()))
        self.panduan = QLabel()
        self.panduan.setWordWrap(True)
        self.panduan.setOpenExternalLinks(True)
        v.addWidget(self.panduan)
        self._isi_panduan()
        v.addStretch(1)
        self.addPage(p1)

        p2 = QWizardPage()
        p2.setTitle("Software pendukung")
        p2.setSubTitle("Untuk tombol 'Buka di…'. Bisa diubah kapan saja di Alat › Atur lokasi program lain.")
        f = QFormLayout(p2)
        for nama in ("PyMOL", "ChimeraX", "Discovery Studio Visualizer"):
            jalur = env.eksternal.get(nama)
            l = QLabel(("✓  " + jalur) if jalur else "Tidak ditemukan (opsional)")
            l.setWordWrap(True)
            l.setObjectName("" if jalur else "muted")
            f.addRow(nama, l)
        self.addPage(p2)

        p3 = QWizardPage()
        p3.setTitle("Folder kerja")
        p3.setSubTitle("Proyek baru disimpan di folder ini.")
        h = QHBoxLayout(p3)
        self.ed_folder = QLineEdit(str(folder))
        b = QPushButton("Pilih…")
        b.clicked.connect(self._pilih_folder)
        h.addWidget(self.ed_folder, 1)
        h.addWidget(b)
        self.addPage(p3)

    def _ringkas(self):
        e = self.env
        g = e.gpu_utama
        baris = []
        if g:
            baris.append(f"<b>GPU</b>: {g.nama} · {g.vram_gb:g} GB · driver {g.driver or '-'} · "
                         + (f"<span style='color:{kit.hx('ok')}'>siap untuk AutoDock-GPU (OpenCL)</span>" if g.opencl
                            else f"<span style='color:{kit.hx('bad')}'>OpenCL tidak tersedia</span>"))
        else:
            baris.append("<b>GPU</b>: tidak ada GPU yang mendukung OpenCL")
        baris.append(f"<b>CPU</b>: {e.cpu} · {e.inti} thread · RAM {e.ram_gb:g} GB")
        mode = "GPU (AutoDock-GPU)" if e.mode_bawaan == "gpu" else "CPU (AutoDock Vina)"
        baris.append(f"<b>Mode docking bawaan</b>: {mode}")
        prog = ", ".join(k.replace(".exe", "") for k, v in e.program.items() if v)
        baris.append(f"<b>Program bawaan</b>: {prog}")
        return "<br><br>".join(baris)

    def _isi_panduan(self):
        from ..core.env import panduan_untuk
        e = self.env
        if e.mode_bawaan == "gpu":
            self.panduan.setText("")
            return
        p = panduan_untuk(e)
        if p:
            judul, url, langkah = p
            self.panduan.setText(f"<b>{judul}</b> agar docking bisa memakai GPU:<ol>"
                                 + "".join(f"<li>{s}</li>" for s in langkah)
                                 + f"</ol><a href='{url}'>{url}</a><br><br>Sementara itu VirmoDock tetap bisa "
                                   "dipakai dengan mode CPU.")
        else:
            self.panduan.setText("Tidak ada GPU yang bisa dipakai. VirmoDock akan memakai AutoDock Vina di CPU.")

    def _pilih_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih folder kerja", self.ed_folder.text())
        if d:
            self.ed_folder.setText(d)


class DialogProgresUnduh(QDialog):
    """Dialog progres saat mengunduh molekul atau protein dari basis data online."""

    def __init__(self, judul, total, parent=None):
        super().__init__(parent)
        self.setWindowTitle(judul)
        self.setMinimumWidth(440)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.dibatalkan = False

        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 18, 20, 18)

        self.lbl_judul = QLabel(f"Mengunduh {total} item…")
        self.lbl_judul.setStyleSheet("font-weight: 600; font-size: 10.5pt;")
        lay.addWidget(self.lbl_judul)

        self.prog = QProgressBar()
        self.prog.setRange(0, total)
        self.prog.setValue(0)
        self.prog.setFixedHeight(22)
        self.prog.setTextVisible(True)
        self.prog.setStyleSheet("QProgressBar { text-align: center; font-weight: 600; height: 22px; border-radius: 3px; }")
        lay.addWidget(self.prog)

        self.lbl_item = QLabel("Menghubungi server…")
        self.lbl_item.setObjectName("muted")
        lay.addWidget(self.lbl_item)

        lay_b = QHBoxLayout()
        lay_b.addStretch()
        self.btn_batal = QPushButton("✕ Batal")
        self.btn_batal.clicked.connect(self._batal)
        lay_b.addWidget(self.btn_batal)
        lay.addLayout(lay_b)

    def set_progres(self, saat_ini, total, teks_item):
        self.prog.setValue(saat_ini)
        self.lbl_item.setText(teks_item)
        self.lbl_judul.setText(f"Mengunduh ({saat_ini}/{total})…")

    def _batal(self):
        self.dibatalkan = True
        self.lbl_item.setText("Membatalkan proses…")
        self.btn_batal.setEnabled(False)
        self.reject()

