"""Dialog Gambar ligan (Ketcher 3, EPAM, Apache-2.0; versi standalone offline dengan Indigo WASM).

Siapkan › Gambar ligan… (kosong) atau klik kanan ligan › Edit struktur (Ketcher) (memuat SMILES/Molfile ligan).
Hasil: SMILES + Molfile -> ligan 3D baru (RDKit ETKDG + MMFF, sama seperti 'Ligan dari SMILES').
Ketcher berjalan di QWebEngineView; API JS window.ketcher (getSmiles/getMolfile/setMolecule mengembalikan Promise),
hasil Promise disimpan di window._vm lalu dibaca dengan runJavaScript berulang.
"""
import json

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from ..core import paths


class DialogKetcher(QDialog):
    def __init__(self, jw, awal=None, nama=""):
        """awal: SMILES atau Molfile yang dimuat saat editor siap."""
        super().__init__(jw)
        self.jw = jw
        self.awal = awal
        self.siap = False
        self.setWindowTitle("Gambar ligan — Ketcher")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1180, 780)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.web = QWebEngineView()
        s = self.web.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        lay.addWidget(self.web, 1)
        h = QHBoxLayout()
        h.addWidget(QLabel("Nama"))
        self.e_nama = QLineEdit(nama or "ligan_gambar")
        self.e_nama.setMaximumWidth(260)
        h.addWidget(self.e_nama)
        self.l_status = QLabel("Memuat editor…")
        self.l_status.setObjectName("muted")
        h.addWidget(self.l_status, 1)
        self.b_smiles = QPushButton("Salin SMILES")
        self.b_smiles.clicked.connect(lambda: self._ambil("getSmiles", self._salin))
        self.b_ok = QPushButton("Tambahkan sebagai ligan")
        self.b_ok.setObjectName("primary")
        self.b_ok.clicked.connect(lambda: self._ambil("getMolfile", self._jadi))
        b_batal = QPushButton("Batal")
        b_batal.clicked.connect(self.reject)
        for b in (self.b_smiles, self.b_ok, b_batal):
            h.addWidget(b)
            b.setEnabled(b is b_batal)
        lay.addLayout(h)
        indeks = paths.KETCHER / "index.html"
        if not indeks.exists():
            self.l_status.setText("Ketcher tidak ditemukan di instalasi (folder 'ketcher').")
            return
        self.web.load(QUrl.fromLocalFile(str(indeks)))
        self._cek = 0
        QTimer.singleShot(800, self._tunggu_siap)

    def _tunggu_siap(self):
        self._cek += 1
        self.web.page().runJavaScript("!!(window.ketcher && window.ketcher.editor)", 0, self._status_siap)

    def _status_siap(self, ok):
        if ok:
            self.siap = True
            self.l_status.setText("Gambar struktur, lalu Tambahkan sebagai ligan. Tip: tempel SMILES dengan "
                                  "Ctrl+V atau buka berkas MOL/SDF.")
            for b in (self.b_smiles, self.b_ok):
                b.setEnabled(True)
            if self.awal:
                self.web.page().runJavaScript(f"window.ketcher.setMolecule({json.dumps(self.awal)})")
            return
        if self._cek > 120:
            self.l_status.setText("Editor gagal dimuat.")
            return
        QTimer.singleShot(250, self._tunggu_siap)

    def _ambil(self, fungsi, lanjut):
        """Panggil ketcher.<fungsi>() (Promise) lalu teruskan hasilnya ke lanjut(teks)."""
        js = (f"window._vm = undefined; window.ketcher.{fungsi}().then(r => window._vm = {{ok: r}})"
              ".catch(e => window._vm = {galat: String(e)}); 1")
        self.web.page().runJavaScript(js, 0, lambda _: self._poll(lanjut, 0))

    def _poll(self, lanjut, n):
        def terima(v):
            v = json.loads(v) if v else None
            if v is None and n < 80:
                QTimer.singleShot(100, lambda: self._poll(lanjut, n + 1))
            elif not v or "galat" in v:
                self.l_status.setText("Tidak dapat membaca struktur: " + (v or {}).get("galat", "batas waktu"))
            else:
                lanjut(v["ok"])
        self.web.page().runJavaScript("window._vm ? JSON.stringify(window._vm) : ''", 0, terima)

    def _salin(self, smi):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(smi)
        self.l_status.setText(f"SMILES disalin: {smi[:80]}")

    def _jadi(self, molfile):
        from rdkit import Chem
        mol = Chem.MolFromMolBlock(molfile)
        if mol is None or mol.GetNumAtoms() == 0:
            self.l_status.setText("Struktur kosong atau tidak valid.")
            return
        self.hasil_smiles = Chem.MolToSmiles(mol)
        self.hasil_nama = self.e_nama.text().strip() or "ligan_gambar"
        self.accept()
