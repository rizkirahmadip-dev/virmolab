"""Panel Antrean job dan tabel Hasil (ringkas; analisis penuh di Tahap 3)."""
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QMenu, QProgressBar,
                               QTableWidget, QTableWidgetItem, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from ..core import mesin as M
from ..core.laporan import id_angka
from . import icons, theme

LABEL_STATUS = {"menunggu": "Menunggu", "berjalan": "Berjalan", "dijeda": "Dijeda", "selesai": "Selesai",
                "gagal": "Gagal", "dibatalkan": "Dibatalkan", "dilewati": "Dilewati"}


def _durasi(s):
    if s is None:
        return ""
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


class PanelAntrean(QWidget):
    aksi = Signal(str, str)          # aksi (jeda|lanjut|batal|hapus_selesai|folder|log|ulang), id job
    KOLOM = ["Job / ligan", "Mesin", "Perangkat", "Progres", "Status", "ΔG (kcal/mol)", "Waktu", "Sisa"]

    def __init__(self):
        super().__init__()
        self.mode = "terang"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.bar = QToolBar()
        self.bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.a = {}
        for k, t, ik in (("jeda", "Jeda", "pause"), ("lanjut", "Lanjut", "play"), ("batal", "Batal", "stop"),
                         ("folder", "Folder hasil", "folder"), ("hapus_selesai", "Hapus selesai", "trash")):
            a = self.bar.addAction(t)
            a.setData(ik)
            a.triggered.connect(lambda _=False, k=k: self.aksi.emit(k, self.job_terpilih() or ""))
            self.a[k] = a
        lay.addWidget(self.bar)
        self.pohon = QTreeWidget()
        self.pohon.setColumnCount(len(self.KOLOM))
        self.pohon.setHeaderLabels(self.KOLOM)
        self.pohon.setRootIsDecorated(True)
        self.pohon.setUniformRowHeights(True)
        self.pohon.setIndentation(14)
        h = self.pohon.header()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.Fixed)
        h.resizeSection(3, 140)
        h.setStretchLastSection(False)
        self.pohon.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pohon.customContextMenuRequested.connect(self._menu)
        self.pohon.itemSelectionChanged.connect(self._tombol)
        lay.addWidget(self.pohon)
        self._item = {}
        self._jobs = []
        self._tombol()

    def terapkan_tema(self, mode):
        self.mode = mode
        w = theme.TOKEN[mode]["ink2"]
        for a in self.a.values():
            a.setIcon(icons.ikon(a.data(), w))

    def job_terpilih(self):
        it = self.pohon.currentItem()
        while it and it.parent():
            it = it.parent()
        return it.data(0, Qt.UserRole) if it else None

    def _tombol(self):
        j = next((x for x in self._jobs if x["id"] == self.job_terpilih()), None)
        s = j["status"] if j else None
        self.a["jeda"].setEnabled(s in ("berjalan", "menunggu"))
        self.a["lanjut"].setEnabled(s in ("dijeda", "gagal", "dibatalkan"))
        self.a["batal"].setEnabled(s in ("berjalan", "menunggu", "dijeda"))
        self.a["folder"].setEnabled(j is not None)

    def _warna(self, status):
        t = theme.TOKEN[self.mode]
        return {"selesai": t["ok"], "gagal": t["bad"], "dibatalkan": t["mut"], "dilewati": t["warn"],
                "berjalan": t["acc"], "dijeda": t["warn"]}.get(status, t["ink2"])

    def _bar(self, it, nilai):
        b = self.pohon.itemWidget(it, 3)
        if b is None:
            b = QProgressBar()
            b.setRange(0, 100)
            b.setTextVisible(False)
            b.setFixedHeight(6)
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(4, 0, 8, 0)
            hl.addWidget(b)
            self.pohon.setItemWidget(it, 3, w)
        else:
            b = b.findChild(QProgressBar)
        b.setValue(int(nilai))

    def muat(self, jobs):
        """Sinkronkan tampilan dengan daftar job (dict dari proyek)."""
        self._jobs = jobs
        ada = {j["id"] for j in jobs}
        for jid in list(self._item):
            if jid not in ada:
                it = self._item.pop(jid)
                self.pohon.takeTopLevelItem(self.pohon.indexOfTopLevelItem(it))
        for j in jobs:
            self.perbarui(j)
        self._tombol()

    def perbarui(self, j):
        it = self._item.get(j["id"])
        baru = it is None
        if baru:
            it = QTreeWidgetItem(self.pohon)
            it.setData(0, Qt.UserRole, j["id"])
            self._item[j["id"]] = it
        lig = j["ligan"]
        selesai = [l for l in lig if l["status"] in ("selesai", "gagal", "dilewati", "dibatalkan")]
        jalan = next((l for l in lig if l["status"] == "berjalan"), None)
        prog = (len(selesai) + (jalan["progres"] / 100 if jalan else 0)) / max(1, len(lig)) * 100
        it.setText(0, f"{j['id']} · {j['nama']}")
        it.setText(1, M.MESIN.get(j["mesin"], j["mesin"]) + (" (alih)" if j["mesin"] != j.get("mesin_asal") else ""))
        it.setText(2, "GPU" if j.get("perangkat") == "gpu" else "CPU")
        it.setText(4, f"{LABEL_STATUS.get(j['status'], j['status'])} {len(selesai)}/{len(lig)}")
        it.setForeground(4, QColor(self._warna(j["status"])))
        e = [l["energi"] for l in lig if l.get("energi") is not None]
        it.setText(5, id_angka(f"{min(e):.2f}") if e else "")
        detik = [l["detik"] for l in lig if l.get("detik") and l["status"] == "selesai"]
        total = None
        if j.get("mulai"):
            akhir = datetime.fromisoformat(j["selesai"]) if j.get("selesai") else datetime.now()
            total = (akhir - datetime.fromisoformat(j["mulai"])).total_seconds() if j["status"] == "berjalan" \
                or j.get("selesai") else sum(l.get("detik") or 0 for l in lig)
        it.setText(6, _durasi(total))
        sisa = [l for l in lig if l["status"] in ("menunggu", "berjalan")]
        it.setText(7, _durasi(sum(detik) / len(detik) * len(sisa)) if detik and sisa and j["status"] == "berjalan" else "")
        for k in (5, 6, 7):
            it.setTextAlignment(k, Qt.AlignRight | Qt.AlignVCenter)
        self._bar(it, 100 if j["status"] == "selesai" else prog)
        # anak: ligan
        while it.childCount() < len(lig):
            QTreeWidgetItem(it)
        for i, l in enumerate(lig):
            c = it.child(i)
            c.setData(0, Qt.UserRole, l["id"])
            c.setText(0, l["nama"])
            c.setText(4, LABEL_STATUS.get(l["status"], l["status"]))
            c.setForeground(4, QColor(self._warna(l["status"])))
            c.setToolTip(4, l.get("pesan") or "")
            c.setToolTip(0, l.get("pesan") or "")
            c.setText(5, id_angka(f"{l['energi']:.2f}") if l.get("energi") is not None else "")
            c.setText(6, _durasi(l.get("detik")))
            for k in (5, 6):
                c.setTextAlignment(k, Qt.AlignRight | Qt.AlignVCenter)
            if l["status"] == "berjalan" or (it.isExpanded() and l["status"] != "menunggu"):
                self._bar(c, l["progres"] if l["status"] == "berjalan" else 100 if l["status"] == "selesai" else 0)
            elif self.pohon.itemWidget(c, 3):
                self.pohon.removeItemWidget(c, 3)
        if baru:
            it.setExpanded(len(lig) <= 12)
        self._tombol()

    def _menu(self, pos):
        jid = self.job_terpilih()
        if not jid:
            return
        m = QMenu(self)
        for k, t in (("folder", "Buka folder hasil"), ("log", "Lihat log ligan"), ("ulang", "Jalankan ulang yang gagal"),
                     ("jeda", "Jeda"), ("lanjut", "Lanjut"), ("batal", "Batal")):
            m.addAction(t, lambda k=k: self.aksi.emit(k, jid))
        m.exec(self.pohon.viewport().mapToGlobal(pos))

    def ligan_terpilih(self):
        it = self.pohon.currentItem()
        if it and it.parent():
            return it.parent().data(0, Qt.UserRole), it.data(0, Qt.UserRole)
        return None, None


class PanelHasil(QWidget):
    """Tabel hasil ringkas: satu baris per ligan per job. Klik dua kali = muat pose ke viewport."""
    bukaPose = Signal(str, str)      # id job, id ligan
    KOLOM = ["Ligan", "ΔG terbaik (kcal/mol)", "Ki perkiraan", "RMSD ref (Å)", "Pose", "Mesin", "Job", "Waktu"]

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.tabel = QTableWidget(0, len(self.KOLOM))
        self.tabel.setHorizontalHeaderLabels(self.KOLOM)
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabel.setSortingEnabled(True)
        self.tabel.setShowGrid(False)
        self.tabel.verticalHeader().setDefaultSectionSize(24)
        h = self.tabel.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabel.cellDoubleClicked.connect(self._klik)
        lay.addWidget(self.tabel, 1)
        cat = QLabel("Hasil docking adalah prediksi komputasi, bukan bukti aktivitas biologis; konfirmasi dengan "
                     "uji eksperimen. Ki dihitung dari ΔG (perkiraan, 298 K). Klik dua kali baris untuk memuat pose.")
        cat.setObjectName("muted")
        cat.setWordWrap(True)
        cat.setContentsMargins(8, 4, 8, 4)
        lay.addWidget(cat)

    def muat(self, jobs):
        self.tabel.setSortingEnabled(False)
        self.tabel.setRowCount(0)
        for j in jobs:
            for l in j["ligan"]:
                if l["status"] != "selesai":
                    continue
                r = self.tabel.rowCount()
                self.tabel.insertRow(r)
                nilai = [l["nama"], l["energi"], l.get("ki", ""),
                         l["rmsd_ref"] if l.get("rmsd_ref") is not None else None, l.get("n_pose", 0),
                         M.MESIN.get(j["mesin"], j["mesin"]), j["id"], _durasi(l.get("detik"))]
                for k, v in enumerate(nilai):
                    it = QTableWidgetItem()
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        it.setData(Qt.DisplayRole, round(v, 2) if isinstance(v, float) else v)
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:
                        it.setText("" if v is None else str(v))
                    if k == 0:
                        it.setData(Qt.UserRole, (j["id"], l["id"]))
                    self.tabel.setItem(r, k, it)
        self.tabel.setSortingEnabled(True)
        self.tabel.sortItems(1, Qt.AscendingOrder)

    def _klik(self, r, _k):
        d = self.tabel.item(r, 0).data(Qt.UserRole)
        if d:
            self.bukaPose.emit(*d)
