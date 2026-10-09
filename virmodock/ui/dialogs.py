"""Dialog: ambil dari database, wizard pertama kali, pengaturan."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget, QWizard, QWizardPage)


class DialogAmbil(QDialog):
    """Unduh struktur dari RCSB PDB / PubChem, atau buat dari SMILES."""

    def __init__(self, parent=None, tab=0):
        super().__init__(parent)
        self.setWindowTitle("Impor dari database")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        self.tab = QTabWidget()
        # RCSB
        w1 = QWidget()
        f1 = QFormLayout(w1)
        self.pdbid = QLineEdit()
        self.pdbid.setPlaceholderText("mis. 1HSG, 6LU7")
        self.pdbid.setMaxLength(4)
        f1.addRow("ID PDB", self.pdbid)
        f1.addRow(self._ket("Protein, ligan asli, air, dan ion dipisah menjadi objek sendiri."))
        self.tab.addTab(w1, "RCSB PDB")
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
        self.tab.setCurrentIndex(tab)
        lay.addWidget(self.tab)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Impor")
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText("Batal")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _ket(self, t):
        l = QLabel(t)
        l.setObjectName("muted")
        l.setWordWrap(True)
        return l

    def permintaan(self):
        i = self.tab.currentIndex()
        if i == 0:
            return ("rcsb", [self.pdbid.text().strip()]) if self.pdbid.text().strip() else None
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
            baris.append(f"<b>GPU</b>: {g.nama} · {g.vram_gb:g} GB · driver {g.driver or '–'} · "
                         + ("<span style='color:#2e9e5b'>siap untuk AutoDock-GPU (OpenCL)</span>" if g.opencl
                            else "<span style='color:#cf3f3f'>OpenCL tidak tersedia</span>"))
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
