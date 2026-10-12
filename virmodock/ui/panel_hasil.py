"""Tab Hasil: satu baris per ligan per job (pose terbaik), dapat diperluas ke semua pose."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core.laporan import id_angka
from ..core import arti, qc
from . import theme

KOLOM = ["#", "Ligan", "ΔG (kcal/mol)", "Ki perkiraan", "LE", "Klaster", "RMSD kristal (Å)", "RMSD ref (Å)",
         "PoseBusters", "H", "HF", "π", "Lain", "Mesin", "Job", "IFP vs kristal", "MM/GBSA (kcal/mol)",
         "GNINA (kcal/mol)", "CNNscore", "CNNaffinity (pK)", "Syarat jarak (Å)"]
NUM = {0, 2, 4, 5, 6, 7, 9, 10, 11, 12, 15, 16, 17, 18, 19, 20}
K_IFP = 15
K_MMGBSA = 16
K_GNINA = 17
K_CNN = 18
K_PK = 19
K_JARAK = 20
K_QC = 8
# kolom tampil bawaan (sisanya lewat klik kanan pada judul kolom)
TAMPIL_BAWAAN = {0, 1, 2, 4, 6, K_QC, 9, K_IFP, K_MMGBSA, K_GNINA, K_CNN, K_PK, K_JARAK}


class ItemAngka(QTreeWidgetItem):
    """Sortir numerik untuk kolom angka (sel kosong di akhir)."""

    def __lt__(self, lain):
        k = self.treeWidget().sortColumn() if self.treeWidget() else 0
        if k in NUM:
            a, b = self.data(k, Qt.UserRole), lain.data(k, Qt.UserRole)
            a = 1e9 if a is None else a
            b = 1e9 if b is None else b
            return a < b
        return self.text(k).lower() < lain.text(k).lower()


class PanelHasil(QWidget):
    bukaPose = Signal(str, str, int)        # id job, id ligan, peringkat pose (1 = terbaik)
    bandingkan = Signal(list)               # [(id job, id ligan)]
    petaInteraksi = Signal()
    ekspor = Signal()

    def __init__(self):
        super().__init__()
        self.mode = "terang"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 6, 8, 6)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Cari ligan / job")
        self.filter.setClearButtonEnabled(True)
        self.filter.setMaximumWidth(260)
        self.filter.textChanged.connect(self._saring)
        self.sp_dg = QLineEdit()
        self.sp_dg.setPlaceholderText("ΔG ≤ (mis. -8)")
        self.sp_dg.setToolTip("Tampilkan hanya ligan dengan ΔG ≤ nilai ini (kosong = semua)")
        self.sp_dg.setMaximumWidth(130)
        self.sp_dg.textChanged.connect(self._saring)
        self.l_n = QLabel("")
        self.l_n.setObjectName("muted")
        self.b_banding = QPushButton("Bandingkan")
        self.b_banding.setToolTip("Centang 2-4 ligan di kolom pertama")
        self.b_banding.clicked.connect(self._banding)
        b_peta = QPushButton("Peta interaksi")
        b_peta.setToolTip("Peta panas residu × ligan untuk semua hasil")
        b_peta.clicked.connect(self.petaInteraksi)
        b_eks = QPushButton("Ekspor…")
        b_eks.clicked.connect(self.ekspor)
        for w in (self.filter, self.sp_dg, self.l_n):
            bl.addWidget(w)
        bl.addStretch(1)
        for w in (self.b_banding, b_peta, b_eks):
            bl.addWidget(w)
        lay.addWidget(bar)
        self.pohon = QTreeWidget()
        self.pohon.setColumnCount(len(KOLOM))
        self.pohon.setHeaderLabels(KOLOM)
        judul = self.pohon.headerItem()
        for i, tip in arti.PETUNJUK_KOLOM.items():
            judul.setToolTip(i, tip)
        self.pohon.setSortingEnabled(True)
        self.pohon.setUniformRowHeights(True)
        self.pohon.setIndentation(14)
        self.pohon.setAlternatingRowColors(False)
        h = self.pohon.header()
        h.setContextMenuPolicy(Qt.CustomContextMenu)
        h.customContextMenuRequested.connect(self._menu_kolom)
        h.setToolTip("Klik kanan untuk memilih kolom")
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setStretchLastSection(False)
        self.pohon.itemDoubleClicked.connect(self._klik)
        self.pohon.itemActivated.connect(self._klik)
        self.pohon.itemChanged.connect(lambda *_: self._hitung_centang())
        lay.addWidget(self.pohon, 1)
        self.l_kosong = QLabel("Belum ada hasil docking.\nIkuti langkah 1-4 di panel kiri, lalu klik "
                               "Jalankan docking. Hasil muncul di sini otomatis.")
        self.l_kosong.setObjectName("muted")
        self.l_kosong.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.l_kosong, 1)
        self._terapkan_kolom()
        cat = QLabel("Hasil docking adalah prediksi komputasi, bukan bukti aktivitas biologis; konfirmasi dengan "
                     "uji eksperimen. Ki dihitung dari ΔG (perkiraan, 298 K). LE = −ΔG / atom berat. "
                     "H = ikatan hidrogen, HF = hidrofobik, π = π-π, Lain = π-kation, garam, halogen, logam. "
                     "Klik kanan judul kolom untuk menampilkan kolom lain. "
                     "PoseBusters = uji kewajaran fisik pose terbaik (arahkan kursor untuk rincian). "
                     "GNINA (kcal/mol), CNNscore (0-1), dan CNNaffinity (pK) terisi setelah docking "
                     "bila GNINA ada di WSL, untuk 10 ligan terbaik. Sel kosong bukan nol. "
                     "Syarat jarak adalah jarak terdekat pose ke residu yang dipilih. "
                     "Baris memakai pose berenergi terbaik yang lolos; pose lain tetap di bawahnya. "
                     "Klik dua kali baris untuk memuat pose.")
        cat.setObjectName("muted")
        cat.setWordWrap(True)
        cat.setContentsMargins(8, 4, 8, 4)
        lay.addWidget(cat)

    def _kolom_tampil(self):
        from ..core import paths
        st = paths.settings()
        v = st.value("kolom_hasil")
        if v and not st.value("kolom_hasil_mmgbsa"):     # kolom baru 0.9.4: tampilkan sekali di pengaturan lama
            st.setValue("kolom_hasil", sorted({int(x) for x in v} | {K_MMGBSA}))
            st.setValue("kolom_hasil_mmgbsa", 1)
            v = st.value("kolom_hasil")
        if v and not st.value("kolom_hasil_gnina"):
            st.setValue("kolom_hasil", sorted({int(x) for x in v} | {K_GNINA, K_CNN, K_PK}))
            st.setValue("kolom_hasil_gnina", 1)
            v = st.value("kolom_hasil")
        if v and not st.value("kolom_hasil_jarak"):
            st.setValue("kolom_hasil", sorted({int(x) for x in v} | {K_JARAK}))
            st.setValue("kolom_hasil_jarak", 1)
            v = st.value("kolom_hasil")
        try:
            return {int(x) for x in v} if v else set(TAMPIL_BAWAAN)
        except (TypeError, ValueError):
            return set(TAMPIL_BAWAAN)

    def _terapkan_kolom(self):
        tampil = self._kolom_tampil() | {1}
        for k in range(len(KOLOM)):
            self.pohon.setColumnHidden(k, k not in tampil)

    def _menu_kolom(self, pos):
        from PySide6.QtWidgets import QMenu
        from ..core import paths
        m = QMenu(self)
        tampil = self._kolom_tampil()
        for k, t in enumerate(KOLOM):
            if k == 1:
                continue
            a = m.addAction(t)
            a.setCheckable(True)
            a.setChecked(k in tampil)
            a.setData(k)
        m.addSeparator()
        a_bawaan = m.addAction("Kolom bawaan")
        pilih = m.exec(self.pohon.header().mapToGlobal(pos))
        if not pilih:
            return
        if pilih is a_bawaan:
            tampil = set(TAMPIL_BAWAAN)
        else:
            tampil ^= {pilih.data()}
        paths.settings().setValue("kolom_hasil", sorted(tampil))
        self._terapkan_kolom()

    def _sel(self, it, k, v, fmt="{:.2f}"):
        it.setData(k, Qt.UserRole, v)
        it.setText(k, "" if v is None else (id_angka(fmt.format(v)) if isinstance(v, float) else str(v)))
        if k in NUM:
            it.setTextAlignment(k, Qt.AlignRight | Qt.AlignVCenter)

    def muat(self, baris):
        """baris: dari core.ekspor.baris_hasil."""
        t = theme.TOKEN[self.mode]
        qc_ada = qc.tersedia()
        self.pohon.blockSignals(True)
        self.pohon.setSortingEnabled(False)
        self.pohon.clear()
        for b in baris:
            it = ItemAngka(self.pohon)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(0, Qt.Unchecked)
            it.setData(1, Qt.UserRole + 1, (b["job"], b["lid"]))
            self._sel(it, 0, b["peringkat"])
            it.setText(1, b["ligan"])
            self._sel(it, 2, b["energi"])
            it.setToolTip(2, arti.arti_skor(b.get("kovalen")))
            it.setText(3, id_angka(b["ki"] or ""))
            self._sel(it, 4, b["le"], "{:.3f}")
            self._sel(it, 5, b["klaster"])
            self._sel(it, 6, b["rmsd_kristal"])
            if b["rmsd_kristal"] is not None:
                it.setForeground(6, QColor(t["ok"] if b["rmsd_kristal"] <= 2.0 else t["bad"]))
                it.setToolTip(6, "≤ 2,0 Å: redocking valid" if b["rmsd_kristal"] <= 2.0 else "> 2,0 Å: tidak valid")
            self._sel(it, 7, b["rmsd"])
            q = b.get("qc")
            it.setText(K_QC, qc.teks_sel(q) if q else "…" if qc_ada else "")
            it.setData(K_QC, Qt.UserRole, (0 if q.get("lulus") else 1 + len(q.get("gagal") or [])) if q and
                       not q.get("galat") else None)
            it.setToolTip(K_QC, qc.tooltip(q) if q else ("Sedang/akan diperiksa PoseBusters" if qc_ada else
                                                         "PoseBusters tidak terpasang"))
            if q and not q.get("galat"):
                it.setForeground(K_QC, QColor(t["ok"] if q["lulus"] else t["bad"]))
            self._sel(it, 9, b["hbond"])
            self._sel(it, 10, b["hidrofobik"])
            self._sel(it, 11, b["pi"])
            self._sel(it, 12, b["pikation"] + b["garam"] + b["halogen"] + b["logam"])
            it.setText(13, b["mesin"])
            it.setText(14, b["job"])
            self._sel(it, K_IFP, b.get("ifp_sim"))
            self._sel(it, K_MMGBSA, b.get("mmgbsa"))
            self._sel(it, K_GNINA, b.get("gnina"))
            it.setToolTip(K_GNINA, arti.PETUNJUK_KOLOM[K_GNINA])
            self._sel(it, K_CNN, b.get("cnnscore"), "{:.3f}")
            it.setToolTip(K_CNN, arti.PETUNJUK_KOLOM[K_CNN])
            self._sel(it, K_PK, b.get("cnnaffinity"))
            it.setToolTip(K_PK, arti.PETUNJUK_KOLOM[K_PK])
            self._sel(it, K_JARAK, b.get("syarat_jarak"))
            if b.get("syarat_lolos") is not None:
                it.setForeground(K_JARAK, QColor(t["ok"] if b["syarat_lolos"] else t["bad"]))
                ambang = b.get("syarat_ambang")
                pose_sj = b.get("syarat_pose")
                it.setToolTip(K_JARAK, arti.PETUNJUK_KOLOM[K_JARAK]
                              + (f" Ambang {ambang:.1f} Å." if isinstance(ambang, float) else "")
                              + (f" Pose {pose_sj}." if pose_sj else "")
                              + (f" {b.get('syarat_atom')}." if b.get("syarat_atom") else ""))
                if pose_sj and pose_sj != 1 and b.get("syarat_lolos"):
                    it.setToolTip(2, arti.arti_skor(b.get("kovalen"))
                                  + " Baris ini pose yang lolos syarat jarak, bukan pose 1. "
                                    "ΔG tetap skor docking pose itu.")
                elif pose_sj and not b.get("syarat_lolos"):
                    it.setToolTip(K_JARAK, it.toolTip(K_JARAK)
                                  + " Tidak ada pose di bawah ambang. Baris tetap pose terbaik docking.")
            if b.get("mmgbsa") is not None:
                it.setToolTip(K_MMGBSA, f"{b.get('mmgbsa_metode') or 'MM/GBSA'}"
                              + (f" · SD {b['mmgbsa_sd']:.2f}" if b.get("mmgbsa_sd") else "")
                              + " - peringkat relatif; entropi tidak dihitung")
            it.setToolTip(K_IFP, "Kemiripan Tanimoto sidik jari interaksi (residu × jenis, tanpa vdW) pose terbaik "
                                 "terhadap pose kristal ligan asli; 1 = pola interaksi sama persis")
            for p in b["pose"]:
                c = ItemAngka(it)
                c.setData(1, Qt.UserRole + 1, (b["job"], b["lid"], p["peringkat"]))
                c.setText(1, f"Pose {p['peringkat']}")
                self._sel(c, 2, p["energi"])
                c.setToolTip(2, arti.arti_skor(b.get("kovalen")))
                self._sel(c, 5, p.get("klaster") or None)
                self._sel(c, 6, p.get("rmsd_kristal"))
                self._sel(c, 7, p["rmsd_ref"] if p.get("rmsd_ref", -1) >= 0 else
                          (p.get("rmsd_lb") if p.get("peringkat", 1) > 1 else None))
                self._sel(c, K_JARAK, p.get("syarat_jarak"))
                for k in range(len(KOLOM)):
                    if k != K_JARAK:
                        c.setForeground(k, QColor(t["ink2"]))
                if p.get("syarat_lolos") is not None:
                    c.setForeground(K_JARAK, QColor(t["ok"] if p["syarat_lolos"] else t["bad"]))
                    if p.get("syarat_atom"):
                        c.setToolTip(K_JARAK, p["syarat_atom"])
        self.pohon.setSortingEnabled(True)
        self.pohon.sortItems(2, Qt.AscendingOrder)
        self.pohon.setVisible(bool(baris))
        self.l_kosong.setVisible(not baris)
        self.pohon.blockSignals(False)
        self._saring()
        self._hitung_centang()

    def _saring(self, *_):
        teks = self.filter.text().lower().strip()
        try:
            batas = float(self.sp_dg.text().replace(",", ".").strip())
        except ValueError:
            batas = None
        n = 0
        for i in range(self.pohon.topLevelItemCount()):
            it = self.pohon.topLevelItem(i)
            e = it.data(2, Qt.UserRole)
            tampil = (not teks or teks in it.text(1).lower() or teks in it.text(14).lower()) and \
                     (batas is None or (e is not None and e <= batas))
            it.setHidden(not tampil)
            n += tampil
        self.l_n.setText(f"{n} ligan")

    def _hitung_centang(self):
        n = len(self.dicentang())
        self.b_banding.setText(f"Bandingkan ({n})" if n else "Bandingkan")
        self.b_banding.setEnabled(2 <= n <= 4)

    def dicentang(self):
        hasil = []
        for i in range(self.pohon.topLevelItemCount()):
            it = self.pohon.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                hasil.append(it.data(1, Qt.UserRole + 1))
        return hasil

    def _banding(self):
        self.bandingkan.emit(self.dicentang())

    def _klik(self, it, _k=0):
        d = it.data(1, Qt.UserRole + 1)
        if d:
            self.bukaPose.emit(d[0], d[1], d[2] if len(d) > 2 else 1)

    def terpilih(self):
        """(job, lid, peringkat) baris aktif."""
        it = self.pohon.currentItem()
        d = it.data(1, Qt.UserRole + 1) if it else None
        if not d:
            return None
        return (d[0], d[1], d[2] if len(d) > 2 else 1)
