"""Dialog Sunting di kantong (3D): tumbuhkan gugus pada pose yang sudah ada, nilai langsung dengan Vina lokal.

Atom tempat gugus baru disambungkan dipilih dengan mengeklik diagram 2D ligan. Tiap usulan dibangun dengan inti
dipaku pada pose induk (core/sunting3d.py), diminimisasi di tempat, lalu diperingkat menurut ΔG lokal dan ΔΔG
terhadap pose induk. Pose usulan bisa dibuka di viewer dan ditambahkan ke proyek sebagai ligan baru.
"""
import re

from PySide6.QtCore import QByteArray, QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QGroupBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QProgressBar, QSplitter, QTabWidget, QVBoxLayout, QWidget)

from .. import i18n
from ..core import sunting3d as S
from . import kerja, kit

KOLOM = ["Usulan", "Perubahan", "ΔG lokal (kkal/mol)", "ΔΔG vs induk", "LE", "Tabrakan", "MW", "logP", "QED",
         "SAScore", "Status"]


def _sel_delta(v):
    """Sel ΔΔG: tanda + ditulis eksplisit supaya arah perubahan langsung terbaca."""
    it = kit.sel_angka(v)
    if isinstance(v, (int, float)) and v > 0:
        it.setText("+" + it.text())
    return it


class Peta2D(QWidget):
    """Diagram 2D ligan yang bisa diklik: klik pada atom memilih titik tumbuh."""
    atomDipilih = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._r = QSvgRenderer(self)
        self._koordinat = []        # [(x, y)] dalam koordinat gambar
        self._ukuran = (1, 1)
        self.setMinimumHeight(260)
        self.setCursor(Qt.PointingHandCursor)

    def muat(self, svg, koordinat, ukuran):
        self._r.load(QByteArray(svg.encode("utf-8")))
        self._koordinat, self._ukuran = koordinat, ukuran
        self.update()

    def _rect(self):
        uk = self._r.defaultSize()
        if uk.isEmpty():
            return None
        uk.scale(self.size(), Qt.KeepAspectRatio)
        return ((self.width() - uk.width()) // 2, (self.height() - uk.height()) // 2, uk.width(), uk.height())

    def paintEvent(self, _e):
        r = self._rect()
        if not self._r.isValid() or r is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        self._r.render(p, QRectF(*r))
        p.end()

    def mousePressEvent(self, e):
        r = self._rect()
        if not self._koordinat or r is None:
            return
        x0, y0, w, h = r
        sx, sy = w / self._ukuran[0], h / self._ukuran[1]
        pos = e.position()
        terdekat, jarak = -1, 1e9
        for i, (ax, ay) in enumerate(self._koordinat):
            d = (ax * sx + x0 - pos.x()) ** 2 + (ay * sy + y0 - pos.y()) ** 2
            if d < jarak:
                terdekat, jarak = i, d
        if terdekat >= 0 and jarak <= (18 * max(sx, sy)) ** 2:
            self.atomDipilih.emit(terdekat)


def gambar_2d(mol, sorot=None, lebar=460, tinggi=360, gelap=False):
    """(SVG, [(x, y)] koordinat atom, (lebar, tinggi)) diagram 2D dengan nomor atom."""
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from rdkit.Chem.Draw import rdMolDraw2D
    m = Chem.RemoveHs(Chem.Mol(mol))
    m.RemoveAllConformers()
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(m)
    for a in m.GetAtoms():      # nomor atom 1-based, sama dengan label titik tumbuh ("C7")
        a.SetProp("atomNote", str(a.GetIdx() + 1))
    d = rdMolDraw2D.MolDraw2DSVG(lebar, tinggi)
    o = d.drawOptions()
    o.bondLineWidth = 2
    o.padding = 0.1
    o.clearBackground = False
    if gelap:
        o.updateAtomPalette({6: (0.88, 0.9, 0.93), 7: (0.48, 0.66, 1.0), 8: (1.0, 0.45, 0.45),
                             16: (0.95, 0.82, 0.3), 9: (0.55, 0.9, 0.4), 17: (0.4, 0.9, 0.4)})
        o.setSymbolColour((0.88, 0.9, 0.93))
        o.setAnnotationColour((0.78, 0.83, 0.9))
    sorot_atom = [sorot] if sorot is not None and sorot < m.GetNumAtoms() else []
    warna = {sorot: (0.18, 0.62, 0.42)} if sorot_atom else {}
    rdMolDraw2D.PrepareAndDrawMolecule(d, m, highlightAtoms=sorot_atom, highlightAtomColors=warna)
    d.FinishDrawing()
    svg = re.sub(r"<\?xml[^>]*>", "", d.GetDrawingText())
    koordinat = []
    for i in range(m.GetNumAtoms()):
        p = d.GetDrawCoords(i)
        koordinat.append((p.x, p.y))
    return svg, koordinat, (lebar, tinggi)


class DialogSunting3D(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Sunting di kantong (3D)")
        self.setMinimumSize(1140, 720)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._mol = None             # pose 3D induk (RDKit, dengan H)
        self._nama = ""
        self._rec_pdbqt = ""
        self._rec_pdb = ""
        self._atom = None            # titik tumbuh terpilih
        self._induk = None           # Usulan induk (skor acuan)
        self._hasil = []
        self._kerja = None
        self._batal = False
        self._bangun()
        self._muat_sumber()

    # ================================================================== tata letak
    def _bangun(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Sunting di kantong (3D)",
                                "Tambahkan gugus pada pose yang sudah ada, lalu nilai langsung di tempat dengan "
                                "AutoDock Vina (--local_only). Inti ligan tetap pada koordinat pose induk."))
        split = QSplitter(Qt.Horizontal, self)
        split.setChildrenCollapsible(False)
        split.addWidget(self._kiri())
        split.addWidget(self._kanan())
        split.setSizes([440, 700])
        lay.addWidget(split, 1)
        self.pb = QProgressBar()
        self.pb.setTextVisible(False)
        self.pb.setMaximumHeight(6)
        self.pb.setVisible(False)
        lay.addWidget(self.pb)
        self.l_status = kit.catatan("", "muted")
        lay.addWidget(self.l_status)
        self.b_tambah = kit.tombol("Tambahkan ke proyek", self._tambah_ke_proyek,
                                   tip="Simpan usulan terpilih sebagai ligan proyek (siap didocking ulang)")
        self.b_viewer = kit.tombol("Lihat pose di viewer", self._ke_viewer)
        self.b_metode = kit.tombol("Salin metode", self._salin_metode)
        lay.addLayout(kit.bar_bawah(self, kiri=(self.b_tambah, self.b_viewer, self.b_metode)))

    def _kiri(self):
        w = QWidget()
        w.setMaximumWidth(470)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 8, 0)
        v.setSpacing(8)
        h = QHBoxLayout()
        h.addWidget(QLabel("Pose induk"))
        self.cb_ligan = QComboBox()
        self.cb_ligan.currentIndexChanged.connect(self._ganti_ligan)
        h.addWidget(self.cb_ligan, 1)
        v.addLayout(h)
        self.peta = Peta2D()
        self.peta.atomDipilih.connect(self._pilih_atom)
        v.addWidget(self.peta, 1)
        h = QHBoxLayout()
        h.addWidget(QLabel("Titik tumbuh"))
        self.cb_atom = QComboBox()
        self.cb_atom.currentIndexChanged.connect(self._ganti_atom)
        h.addWidget(self.cb_atom, 1)
        v.addLayout(h)
        v.addWidget(kit.catatan("Klik atom pada diagram untuk memilih tempat gugus baru disambungkan. Hanya atom "
                                "yang masih punya hidrogen yang bisa dipilih.", "muted"))
        self.k_induk = kit.Kartu("ΔG pose induk", "–")
        self.k_terbaik = kit.Kartu("Usulan terbaik", "–")
        v.addLayout(kit.baris_kartu(self.k_induk, self.k_terbaik))
        return w

    def _kanan(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 0, 0, 0)
        v.setSpacing(8)
        self.tab = QTabWidget()
        # gugus
        hal = QWidget()
        vg = QVBoxLayout(hal)
        vg.setContentsMargins(0, 6, 0, 0)
        self.daftar_gugus = QListWidget()
        self.daftar_gugus.setSelectionMode(QAbstractItemView.NoSelection)
        for label, smi, singkat in S.GUGUS:
            it = QListWidgetItem(f"{i18n.t(label)}   ({singkat})")      # nama gugus diterjemahkan sebelum disambung
            it.setData(Qt.UserRole, (label, smi, singkat))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if singkat in ("Me", "F", "Cl", "OH", "OMe", "CF3", "CN", "NH2") else
                             Qt.Unchecked)
            self.daftar_gugus.addItem(it)
        vg.addWidget(self.daftar_gugus, 1)
        h = QHBoxLayout()
        h.addWidget(kit.tombol("Centang semua", lambda: self._centang(self.daftar_gugus, True)))
        h.addWidget(kit.tombol("Kosongkan", lambda: self._centang(self.daftar_gugus, False)))
        h.addStretch(1)
        vg.addLayout(h)
        self.tab.addTab(hal, "Tumbuhkan gugus")
        # bioisoster
        hal = QWidget()
        vb = QVBoxLayout(hal)
        vb.setContentsMargins(0, 6, 0, 0)
        vb.addWidget(kit.catatan("Penggantian gugus fungsi pada seluruh ligan (tidak memakai titik tumbuh). Hanya "
                                 "yang pola SMARTS-nya mengenai ligan yang dijalankan.", "muted"))
        self.daftar_bio = QListWidget()
        self.daftar_bio.setSelectionMode(QAbstractItemView.NoSelection)
        for label, smarts in S.BIOISOSTER:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, (label, smarts))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            self.daftar_bio.addItem(it)
        vb.addWidget(self.daftar_bio, 1)
        h = QHBoxLayout()
        h.addWidget(kit.tombol("Centang semua", lambda: self._centang(self.daftar_bio, True)))
        h.addWidget(kit.tombol("Kosongkan", lambda: self._centang(self.daftar_bio, False)))
        h.addStretch(1)
        vb.addLayout(h)
        self.tab.addTab(hal, "Ganti bioisoster")
        v.addWidget(self.tab, 0)
        h = QHBoxLayout()
        self.b_jalan = kit.tombol("Nilai usulan", self._jalankan, utama=True)
        self.b_henti = kit.tombol("Hentikan", self._hentikan)
        self.b_henti.setEnabled(False)
        h.addWidget(self.b_jalan)
        h.addWidget(self.b_henti)
        h.addStretch(1)
        v.addLayout(h)
        g = QGroupBox("Hasil (diurutkan menurut ΔG lokal)")
        vh = QVBoxLayout(g)
        self.tabel = kit.tabel(KOLOM, urut=True)
        self.tabel.itemDoubleClicked.connect(lambda *_: self._ke_viewer())
        vh.addWidget(self.tabel)
        v.addWidget(g, 1)
        return w

    def _centang(self, daftar, nyala):
        for i in range(daftar.count()):
            daftar.item(i).setCheckState(Qt.Checked if nyala else Qt.Unchecked)

    # ================================================================== sumber ligan
    def _muat_sumber(self):
        jw = self.jw
        self._rec_pdbqt = ""
        pr = jw.proyek
        if pr and pr.reseptor and pr.p(pr.reseptor["pdbqt"]).exists():
            self._rec_pdbqt = pr.p(pr.reseptor["pdbqt"]).read_text(encoding="utf-8", errors="replace")
        self._rec_pdb = kit.reseptor_proyek(jw)[0]
        daftar = []
        aktif = kit.pose_aktif(jw)
        for o in jw.objek.values():
            if o.jenis not in ("pose", "ligan") or o.info.get("aditif"):
                continue
            try:
                from ..core import analisis
                mol = analisis.mol_dari_objek(o)
            except Exception:
                mol = None
            if mol is None or mol.GetNumConformers() == 0 or mol.GetNumHeavyAtoms() < 6:
                continue
            daftar.append((o.nama, mol, o is aktif))
        self.cb_ligan.blockSignals(True)
        self.cb_ligan.clear()
        for nama, mol, _a in daftar:
            self.cb_ligan.addItem(nama, mol)
        pilih = next((i for i, (_n, _m, a) in enumerate(daftar) if a), 0)
        self.cb_ligan.setCurrentIndex(pilih if daftar else -1)
        self.cb_ligan.blockSignals(False)
        if not daftar:
            self._status("Belum ada pose di viewer. Buka pose hasil docking (tab Hasil) lalu buka jendela ini lagi.",
                         "peringatan")
            self.b_jalan.setEnabled(False)
            return
        if not self._rec_pdbqt:
            self._status("Reseptor PDBQT belum ada di proyek; skor Vina lokal tidak bisa dihitung. Siapkan reseptor "
                         "di langkah 1.", "peringatan")
            self.b_jalan.setEnabled(False)
        self._ganti_ligan()

    def _ganti_ligan(self, *_):
        mol = self.cb_ligan.currentData()
        if mol is None:
            return
        self._mol = mol
        self._nama = self.cb_ligan.currentText()
        self._induk = None
        self.k_induk.isi("–", "Dinilai saat usulan pertama dijalankan")
        self.k_terbaik.isi("–", "")
        titik = S.titik_tumbuh(mol)
        self.cb_atom.blockSignals(True)
        self.cb_atom.clear()
        for idx, label, n_h in titik:
            self.cb_atom.addItem(f"{label} ({n_h} H)", idx)
        self.cb_atom.setCurrentIndex(0 if titik else -1)
        self.cb_atom.blockSignals(False)
        self._atom = titik[0][0] if titik else None
        self._gambar()

    def _gambar(self):
        if self._mol is None:
            return
        svg, koordinat, ukuran = gambar_2d(self._mol, self._atom, gelap=kit.mode() == "gelap")
        self.peta.muat(svg, koordinat, ukuran)

    def _pilih_atom(self, idx):
        i = self.cb_atom.findData(idx)
        if i < 0:
            from rdkit import Chem
            a = Chem.RemoveHs(self._mol).GetAtomWithIdx(idx)
            self._status(f"Atom {a.GetSymbol()}{idx + 1} tidak punya hidrogen yang bisa diganti; pilih atom lain.",
                         "peringatan")
            return
        self.cb_atom.setCurrentIndex(i)

    def _ganti_atom(self, *_):
        self._atom = self.cb_atom.currentData()
        self._status("")
        self._gambar()

    def _status(self, teks, jenis="muted"):
        self.l_status.setText(teks)
        self.l_status.setObjectName(jenis if teks else "muted")
        self.l_status.style().unpolish(self.l_status)
        self.l_status.style().polish(self.l_status)

    # ================================================================== menjalankan
    def _terpilih(self, daftar):
        return [daftar.item(i).data(Qt.UserRole) for i in range(daftar.count())
                if daftar.item(i).checkState() == Qt.Checked]

    def _jalankan(self):
        if self._mol is None or not self._rec_pdbqt:
            return
        bio = self.tab.currentIndex() == 1
        try:
            if bio:
                pilih = self._terpilih(self.daftar_bio)
                if not pilih:
                    self._status("Centang dulu penggantian yang ingin dicoba.", "peringatan")
                    return
                usulan = S.usulan_bioisoster(self._mol, pilih)
                if not usulan:
                    self._status("Tidak ada penggantian yang mengenai ligan ini. Coba tab Tumbuhkan gugus.",
                                 "peringatan")
                    return
            else:
                pilih = self._terpilih(self.daftar_gugus)
                if not pilih:
                    self._status("Centang dulu gugus yang ingin dicoba.", "peringatan")
                    return
                if self._atom is None:
                    self._status("Pilih titik tumbuh pada diagram dulu.", "peringatan")
                    return
                usulan = S.usulan_tumbuh(self._mol, self._atom, pilih)
        except S.GalatSunting as e:
            self._status(str(e), "peringatan")
            return
        self._batal = False
        self.b_jalan.setEnabled(False)
        self.b_henti.setEnabled(True)
        self.pb.setVisible(True)
        self.pb.setRange(0, len(usulan) + 1)
        self.pb.setValue(0)
        self._status(f"Menilai {len(usulan)} usulan dengan Vina lokal…")
        mol, rec, pdb = self._mol, self._rec_pdbqt, self._rec_pdb
        induk_lama = self._induk

        def kerjakan(lapor):
            ind = induk_lama
            if ind is None or ind.status != "ok":
                ind = S.induk(mol, rec, pdb, "Pose induk")
                lapor.progres.emit(1, len(usulan) + 1, "induk")
            hasil = S.jalankan(mol, usulan, rec, pdb, energi_induk=ind.energi,
                               lapor=lambda i, n, u: lapor.progres.emit(i + 1, n + 1, u.nama),
                               batal=lambda: self._batal)
            return ind, hasil
        self._kerja = kerja.jalankan(kerjakan, selesai=self._selesai, galat=self._gagal,
                                     progres=lambda i, n, t: (self.pb.setRange(0, n), self.pb.setValue(i)))

    def _hentikan(self):
        self._batal = True
        self._status("Dihentikan setelah usulan yang sedang dinilai selesai.")

    def _gagal(self, g):
        self.b_jalan.setEnabled(True)
        self.b_henti.setEnabled(False)
        self.pb.setVisible(False)
        self._status(g.split("\n")[0], "peringatan")

    def _selesai(self, hasil):
        ind, daftar = hasil
        self._induk = ind
        self.b_jalan.setEnabled(True)
        self.b_henti.setEnabled(False)
        self.pb.setVisible(False)
        if ind.status != "ok":
            self._status(f"Pose induk gagal dinilai: {ind.alasan}", "peringatan")
            return
        self.k_induk.isi(kit.f(ind.energi), f"kkal/mol · LE {kit.f(ind.le, 3)} · {ind.atom} atom berat")
        self._hasil = [u for u in self._hasil if u.nama not in {x.nama for x in daftar}] + daftar
        self._isi_tabel()
        ok = [u for u in self._hasil if u.status == "ok"]
        gagal = len(self._hasil) - len(ok)
        lebih = [u for u in ok if u.d_energi is not None and u.d_energi < 0]
        t = i18n.t        # potongan diterjemahkan satu per satu, lalu disambung
        self._status(t(f"{len(ok)} usulan dinilai")
                     + (", " + t(f"{gagal} gagal") if gagal else "")
                     + ("; " + t(f"{len(lebih)} berskor lebih kuat daripada pose induk") + "." if ok else "."))

    def _isi_tabel(self):
        baris = sorted(self._hasil, key=lambda u: (u.status != "ok", u.energi if u.energi is not None else 0))
        t = self.tabel
        t.setSortingEnabled(False)
        t.setRowCount(len(baris))
        terbaik = None
        for r, u in enumerate(baris):
            if u.status == "ok" and (terbaik is None or (u.energi or 0) < (terbaik.energi or 0)):
                terbaik = u
            sel = [kit.sel(u.nama), kit.sel(u.perubahan), kit.sel_angka(u.energi), _sel_delta(u.d_energi),
                   kit.sel_angka(u.le, 3), kit.sel_angka(u.tabrakan, 0), kit.sel_angka(u.mw, 1),
                   kit.sel_angka(u.logp), kit.sel_angka(u.qed, 3), kit.sel_angka(u.sascore),
                   kit.sel("Selesai" if u.status == "ok" else f"Gagal: {u.alasan}")]
            sel[0].setData(Qt.UserRole + 1, u)
            for c, it in enumerate(sel):
                t.setItem(r, c, it)
        t.setSortingEnabled(True)
        if terbaik is not None:
            self.k_terbaik.isi(kit.f(terbaik.energi),
                               f"{terbaik.nama} · ΔΔG {kit.f(terbaik.d_energi)} kkal/mol",
                               "ok" if (terbaik.d_energi or 0) < 0 else None)

    # ================================================================== keluaran
    def _baris_aktif(self):
        it = self.tabel.currentItem()
        if it is None:
            return None
        u = self.tabel.item(it.row(), 0).data(Qt.UserRole + 1)
        return u if u is not None and u.status == "ok" else None

    def _ke_viewer(self):
        u = self._baris_aktif()
        if u is None or not u.sdf:
            self._status("Pilih baris usulan yang berhasil dinilai dulu.", "peringatan")
            return
        from ..core import molekul
        o = molekul.Objek(nama=f"{self._nama} · {u.perubahan}", jenis="ligan", teks=u.sdf, fmt="sdf",
                          sumber="sunting di kantong")
        o.info = {"smiles": u.smiles, "keterangan": f"ΔG lokal {kit.f(u.energi)} kkal/mol"}
        self.jw.tambah_objek([o], fokus=True)
        self._status(f"Pose {u.nama} ditambahkan ke viewer (skor lokal {kit.f(u.energi)} kkal/mol, bukan hasil "
                     f"docking ulang).")

    def _tambah_ke_proyek(self):
        u = self._baris_aktif()
        if u is None:
            self._status("Pilih baris usulan yang berhasil dinilai dulu.", "peringatan")
            return
        from ..core import molekul, prep_ligan
        nama = f"{self._nama} {u.perubahan}"
        h = prep_ligan.siapkan_satu(nama, u.smiles, "smiles", prep_ligan.OpsiLigan())
        if h.status == "gagal":
            self._status(f"Ligan gagal disiapkan: {h.alasan}", "peringatan")
            return
        asal = molekul.Objek(nama=nama, jenis="ligan", teks=u.smiles, fmt="smiles", sumber="sunting di kantong")
        self.jw._ligan_siap([(asal, h)])
        self._status(f"{nama} ditambahkan sebagai ligan proyek. Docking ulang dari awal untuk skor yang sebanding "
                     f"dengan hasil lain.")

    def _salin_metode(self):
        ok = sum(1 for u in self._hasil if u.status == "ok")
        if not self._hasil:
            self._status("Belum ada usulan yang dinilai.", "peringatan")
            return
        kit.salin(S.teks_metode(len(self._hasil), ok, en=i18n.inggris()))
        self._status("Paragraf metode disalin.")
