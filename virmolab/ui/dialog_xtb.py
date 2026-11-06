"""Sifat elektronik semi-empiris (F7): jalankan xtb untuk ligan proyek dan lihat hasilnya di penampil.

Deskriptor berasal dari `core/xtb.py` (GFN2-xTB). Peringatan metodenya ikut di dialog, di paragraf
metode, dan di ekspor, karena angka semi-empiris mudah disalahpahami sebagai nilai setara DFT.
"""
import csv

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QProgressBar, QSplitter,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import catat, molekul, xtb
from . import kerja, kit, theme
from .viewer_widget import Viewer

MODE_TAMPIL = (
    ("Fukui f(-) · serangan elektrofil", "fukui_minus"),
    ("Fukui f(+) · serangan nukleofil", "fukui_plus"),
    ("Muatan parsial Mulliken", "muatan"),
    ("Potensial elektrostatik (ESP)", "esp"),
)

KOLOM = ["Ligan", "HOMO (eV)", "LUMO (eV)", "Celah (eV)", "η (eV)", "ω (eV)", "Dipol (D)"]


class DialogXtb(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.jw = parent
        self.proyek = getattr(parent, "proyek", None)
        self.setWindowTitle("Sifat elektronik (xTB)")
        self.setMinimumSize(1180, 720)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._ligan = []            # [(nama, mol)]
        self._hasil = {}            # nama -> dict hasil
        self._mol = {}              # nama -> Chem.Mol
        self._kerja = None
        self._bangun()
        self._muat_ligan()

    # ------------------------------------------------------------------ tata letak
    def _bangun(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Sifat elektronik (xTB)",
                                "Deskriptor kuantum semi-empiris GFN2-xTB untuk ligan proyek"))

        info = xtb.tersedia()
        self.l_status_xtb = kit.catatan(info["pesan"], "muted" if info["ada"] else "peringatan")
        lay.addWidget(self.l_status_xtb)

        split = QSplitter(Qt.Horizontal, self)
        split.setChildrenCollapsible(False)

        # Kiri: pilihan ligan dan parameter
        kiri = QWidget()
        vk = QVBoxLayout(kiri)
        vk.setContentsMargins(0, 0, 8, 0)
        vk.setSpacing(8)

        g_lig = QGroupBox("Ligan")
        v_lig = QVBoxLayout(g_lig)
        self.daftar = QListWidget()
        self.daftar.setSelectionMode(QListWidget.NoSelection)
        v_lig.addWidget(self.daftar)
        h_pilih = QHBoxLayout()
        h_pilih.addWidget(kit.tombol("Pilih semua", lambda: self._centang_semua(True)))
        h_pilih.addWidget(kit.tombol("Kosongkan", lambda: self._centang_semua(False)))
        v_lig.addLayout(h_pilih)
        vk.addWidget(g_lig, 1)

        g_par = QGroupBox("Parameter")
        v_par = QVBoxLayout(g_par)
        h_pel = QHBoxLayout()
        h_pel.addWidget(QLabel("Pelarut:"))
        self.cb_pelarut = QComboBox()
        self.cb_pelarut.setToolTip("Model pelarut implisit. Fase gas paling cepat tetapi melebih-lebihkan interaksi bermuatan; pilih air bila hasilnya akan dibandingkan dengan data larutan.")
        for p in xtb.PELARUT:
            self.cb_pelarut.addItem("Vakum (fase gas)" if p == "none" else p, p)
        self.cb_pelarut.setCurrentIndex(0)
        h_pel.addWidget(self.cb_pelarut, 1)
        v_par.addLayout(h_pel)
        self.c_fukui = QCheckBox("Indeks Fukui (reaktivitas per atom)")
        self.c_fukui.setChecked(True)
        v_par.addWidget(self.c_fukui)
        self.c_esp = QCheckBox("Potensial elektrostatik (ESP)")
        self.c_esp.setChecked(True)
        v_par.addWidget(self.c_esp)
        vk.addWidget(g_par)

        h_aksi = QHBoxLayout()
        self.b_hitung = kit.tombol("Hitung", self._mulai, utama=True)
        self.b_batal = kit.tombol("Batal", self._batalkan)
        self.b_batal.setEnabled(False)
        h_aksi.addWidget(self.b_hitung)
        h_aksi.addWidget(self.b_batal)
        vk.addLayout(h_aksi)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        vk.addWidget(self.bar)
        self.l_status = QLabel("")
        self.l_status.setWordWrap(True)
        self.l_status.setObjectName("muted")
        vk.addWidget(self.l_status)
        kiri.setFixedWidth(330)
        split.addWidget(kiri)

        # Tengah: tabel deskriptor
        tengah = QWidget()
        vt = QVBoxLayout(tengah)
        vt.setContentsMargins(0, 0, 0, 0)
        vt.setSpacing(8)
        self.tabel = kit.tabel(KOLOM, urut=True)
        self.tabel.itemSelectionChanged.connect(self._pilih_baris)
        vt.addWidget(self.tabel, 1)
        self.l_som = QLabel("")
        self.l_som.setWordWrap(True)
        self.l_som.setObjectName("muted")
        vt.addWidget(self.l_som)
        split.addWidget(tengah)

        # Kanan: penampil
        kanan = QWidget()
        vn = QVBoxLayout(kanan)
        vn.setContentsMargins(8, 0, 0, 0)
        vn.setSpacing(6)
        h_mode = QHBoxLayout()
        h_mode.addWidget(QLabel("Pewarnaan:"))
        self.cb_mode = QComboBox()
        self.cb_mode.setToolTip("Besaran yang diwarnakan pada permukaan molekul. Muatan parsial memperlihatkan daerah kaya dan miskin elektron; potensial elektrostatik memperlihatkan bagaimana molekul lain 'melihat' molekul ini.")
        for teks, kunci in MODE_TAMPIL:
            self.cb_mode.addItem(teks, kunci)
        self.cb_mode.currentIndexChanged.connect(self._perbarui_viewer)
        h_mode.addWidget(self.cb_mode, 1)
        vn.addLayout(h_mode)
        self.viewer = Viewer(self)
        latar = theme.TOKEN[kit.mode()]["view"]
        self.viewer.page().setBackgroundColor(latar)
        self.viewer.js("tema", kit.mode() == "gelap", latar)
        vn.addWidget(self.viewer, 1)
        self.l_legenda = QLabel("")
        self.l_legenda.setObjectName("muted")
        vn.addWidget(self.l_legenda)
        split.addWidget(kanan)

        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 3)
        split.setStretchFactor(2, 3)
        lay.addWidget(split, 1)

        lay.addWidget(kit.catatan(xtb.CATATAN_METODE, "peringatan"))
        self.b_csv = kit.tombol("Ekspor CSV…", self._ekspor)
        self.b_metode = kit.tombol("Salin paragraf metode", self._salin_metode)
        lay.addLayout(kit.bar_bawah(self, kiri=[self.b_csv, self.b_metode], tutup=True))

        if not info["ada"]:
            self.b_hitung.setEnabled(False)

    # ------------------------------------------------------------------ data
    def _muat_ligan(self):
        self.daftar.clear()
        self._ligan = []
        for item in (kit.ligan_proyek(self.jw) if self.jw else []):
            mol = item.get("mol") if isinstance(item, dict) else None
            nama = item.get("nama") if isinstance(item, dict) else str(item)
            if mol is None or mol.GetNumConformers() == 0:
                continue
            self._ligan.append((nama, mol))
            self._mol[nama] = mol
            li = QListWidgetItem(nama)
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Checked if len(self._ligan) <= 5 else Qt.Unchecked)
            self.daftar.addItem(li)
        if not self._ligan:
            self.l_status.setText("Belum ada ligan proyek berkoordinat 3D. Siapkan ligan pada langkah 2.")
            self.b_hitung.setEnabled(False)

    def _centang_semua(self, nyala):
        for i in range(self.daftar.count()):
            self.daftar.item(i).setCheckState(Qt.Checked if nyala else Qt.Unchecked)

    def _terpilih(self):
        nama = {self.daftar.item(i).text() for i in range(self.daftar.count())
                if self.daftar.item(i).checkState() == Qt.Checked}
        return [(n, m) for n, m in self._ligan if n in nama]

    # ------------------------------------------------------------------ hitung
    def _mulai(self):
        pilih = self._terpilih()
        if not pilih:
            self.l_status.setText("Centang setidaknya satu ligan.")
            return
        pelarut = self.cb_pelarut.currentData()
        fukui = self.c_fukui.isChecked()
        esp = self.c_esp.isChecked()
        self._batal = False

        self.b_hitung.setEnabled(False)
        self.b_batal.setEnabled(True)
        self.bar.setVisible(True)
        self.bar.setRange(0, len(pilih))
        self.bar.setValue(0)
        self.l_status.setText(f"Menghitung {len(pilih)} ligan dengan GFN2-xTB…")

        def kerjakan(lapor=None):
            def progres(selesai, total, pesan):
                if lapor:
                    lapor.progres.emit(selesai, total, pesan)
            return xtb.hitung_banyak(pilih, pelarut=pelarut, fukui=fukui, esp=esp,
                                     batal=lambda: self._batal, progres=progres)

        self._kerja = kerja.jalankan(kerjakan, selesai=self._selesai, galat=self._galat,
                                     progres=self._progres)

    def _progres(self, selesai, total, pesan):
        self.bar.setValue(selesai)
        self.l_status.setText(pesan)

    def _batalkan(self):
        self._batal = True
        self.l_status.setText("Membatalkan setelah molekul yang sedang berjalan selesai…")
        self.b_batal.setEnabled(False)

    def _galat(self, teks):
        self.b_hitung.setEnabled(True)
        self.b_batal.setEnabled(False)
        self.bar.setVisible(False)
        self.l_status.setText(f"Gagal: {teks.splitlines()[0]}")

    def _selesai(self, hasil):
        self.b_hitung.setEnabled(True)
        self.b_batal.setEnabled(False)
        self.bar.setVisible(False)
        for h in hasil:
            self._hasil[h.get("nama", "")] = h
        n_ok = sum(1 for h in hasil if h.get("tersedia"))
        n_gagal = len(hasil) - n_ok
        pesan = f"{n_ok} ligan selesai"
        if n_gagal:
            sebab = next((h.get("pesan", "") for h in hasil if not h.get("tersedia")), "")
            pesan += f", {n_gagal} gagal ({sebab[:80]})"
        self.l_status.setText(pesan + ".")
        self._isi_tabel()
        self._simpan_ke_proyek()

    def _isi_tabel(self):
        baris = [h for h in self._hasil.values() if h.get("tersedia")]
        self.tabel.setSortingEnabled(False)
        self.tabel.setRowCount(len(baris))
        for r, h in enumerate(baris):
            self.tabel.setItem(r, 0, QTableWidgetItem(str(h.get("nama", ""))))
            for kolom, kunci in enumerate(("homo_ev", "lumo_ev", "celah_ev", "kekerasan_ev",
                                           "elektrofilisitas_ev", "dipol_debye"), start=1):
                self.tabel.setItem(r, kolom, kit.sel_angka(h.get(kunci), d=2))
        self.tabel.setSortingEnabled(True)
        if baris:
            self.tabel.selectRow(0)

    def _simpan_ke_proyek(self):
        if not self.proyek:
            return
        self.proyek.xtb = {n: h for n, h in self._hasil.items() if h.get("tersedia")}
        if self.jw and hasattr(self.jw, "minta_simpan"):
            self.jw.minta_simpan()

    # ------------------------------------------------------------------ penampil
    def _pilih_baris(self):
        sel = self.tabel.selectedItems()
        if not sel:
            return
        self._nama_aktif = self.tabel.item(sel[0].row(), 0).text()
        self._perbarui_viewer()
        self._perbarui_som()

    def _nilai_per_atom(self, nama, mode):
        h = self._hasil.get(nama) or {}
        mol = self._mol.get(nama)
        n = mol.GetNumAtoms() if mol else 0
        if mode == "muatan":
            m = h.get("muatan") or []
            return list(m) + [None] * max(0, n - len(m)), "Muatan parsial Mulliken (e)"
        if mode in ("fukui_minus", "fukui_plus"):
            kunci = "minus" if mode == "fukui_minus" else "plus"
            nilai = [None] * n
            for f in (h.get("fukui") or []):
                if 0 <= f["indeks"] < n:
                    nilai[f["indeks"]] = f[kunci]
            label = "f(-), makin besar makin rentan serangan elektrofil" if kunci == "minus" \
                else "f(+), makin besar makin rentan serangan nukleofil"
            return nilai, label
        return [None] * n, ""

    def _perbarui_viewer(self):
        nama = getattr(self, "_nama_aktif", "")
        mol = self._mol.get(nama)
        h = self._hasil.get(nama)
        if mol is None or not h or not h.get("tersedia"):
            self.l_legenda.setText("")
            return
        mode = self.cb_mode.currentData()

        if mode == "esp":
            hasil_obj = self._hasil_objek(nama)
            nilai = xtb.esp_per_atom(hasil_obj, mol) if hasil_obj else []
            label = "ESP dipetakan ke atom terdekat (Hartree/e); biru positif, merah negatif"
        else:
            nilai, label = self._nilai_per_atom(nama, mode)

        ada = [v for v in nilai if v is not None]
        if not ada:
            self.l_legenda.setText("Nilai untuk mode ini tidak dihitung pada ligan ini.")
            return
        rentang = xtb.rentang_simetris(nilai)

        from rdkit import Chem
        try:
            obj = molekul.Objek(id=f"xtb_{nama}", nama=nama, jenis="ligan",
                                teks=Chem.MolToMolBlock(mol), fmt="sdf")
            self.viewer.muat(obj)
            self.viewer.tampil(obj, {"layers": [{
                "rep": "ballstick",
                "color": {"mode": "nilai", "nilai": nilai, "min": rentang["min"], "max": rentang["max"]},
            }]})
            self.viewer.js("fokusSemua")
        except Exception as e:
            catat.log.warning(f"Gagal menampilkan {nama} di penampil: {e}")
            return
        self.l_legenda.setText(f"{label}. Skala {kit.f(rentang['min'], 3)} sampai {kit.f(rentang['max'], 3)}.")

    def _hasil_objek(self, nama):
        """ESP tidak ikut disimpan di dict hasil (lariknya besar); hitung ulang bila diminta."""
        mol = self._mol.get(nama)
        if mol is None:
            return None
        h = xtb.hitung(mol, pelarut=self.cb_pelarut.currentData(), fukui=False, esp=True, nama=nama)
        return h if h.tersedia else None

    def _perbarui_som(self):
        """Bandingkan f(-) dengan prediksi situs metabolisme CYP bila modulnya punya hasil."""
        nama = getattr(self, "_nama_aktif", "")
        h = self._hasil.get(nama) or {}
        mol = self._mol.get(nama)
        if not h.get("fukui") or mol is None:
            self.l_som.setText("")
            return
        situs = xtb.situs_som(mol)
        if not situs:
            self.l_som.setText("")
            return
        obj = xtb.HasilXtb(fukui=h["fukui"])
        pesan = xtb.korelasi_som(obj, situs)["pesan"]
        self.l_som.setText(pesan.replace(xtb.CATATAN_METODE, "").strip())

    # ------------------------------------------------------------------ keluaran
    def _ekspor(self):
        baris = [h for h in self._hasil.values() if h.get("tersedia")]
        if not baris:
            self.l_status.setText("Belum ada hasil untuk diekspor.")
            return
        p, _ = QFileDialog.getSaveFileName(self, "Simpan CSV sifat elektronik", "sifat_elektronik.csv",
                                           "CSV (*.csv)")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["# metode", "GFN2-xTB", xtb.CATATAN_METODE])
            w.writerow(["ligan", "homo_ev", "lumo_ev", "celah_ev", "kekerasan_ev",
                        "potensial_kimia_ev", "elektrofilisitas_ev", "dipol_debye"])
            for h in baris:
                w.writerow([h.get("nama"), h.get("homo_ev"), h.get("lumo_ev"), h.get("celah_ev"),
                            h.get("kekerasan_ev"), h.get("potensial_kimia_ev"),
                            h.get("elektrofilisitas_ev"), h.get("dipol_debye")])
        self.l_status.setText(f"CSV disimpan ke {p}")

    def _salin_metode(self):
        nama = getattr(self, "_nama_aktif", "")
        h = self._hasil.get(nama)
        if not h or not h.get("tersedia"):
            self.l_status.setText("Pilih satu ligan yang sudah dihitung.")
            return
        obj = xtb.HasilXtb(tersedia=True, celah_ev=h.get("celah_ev"), dipol_debye=h.get("dipol_debye"),
                           fukui=h.get("fukui") or [])
        kit.salin(xtb.paragraf_metode(obj, self.cb_pelarut.currentData()))
        self.l_status.setText("Paragraf metode disalin ke papan klip.")
