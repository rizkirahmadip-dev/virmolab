"""Panel samping: hierarki molekul, properti, tampilan (gaya ala PyMOL), log, antrean."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QColorDialog, QComboBox, QFormLayout, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QToolButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core.laporan import id_angka
from . import icons
from . import kit

IKON_JENIS = {"protein": "rec", "ligan": "lig", "air": "water", "ion": "ion", "pose": "lig", "kompleks": "layers",
              "grid": "box"}
REPS = [("cartoon", "Kartun"), ("ribbon", "Pita"), ("sticks", "Stick"), ("lines", "Garis"),
        ("ballstick", "Bola-stick"), ("spheres", "Bola"), ("surface", "Permukaan"), ("mesh", "Mesh")]
WARNA_MODE = [("element", "Elemen (karbon pilihan)"), ("chain", "Per rantai"), ("spectrum", "Pelangi N→C"),
              ("ss", "Struktur sekunder"), ("bfactor", "B-faktor"), ("plddt", "pLDDT (AlphaFold)"), ("hydro", "Hidrofobisitas"),
              ("muatan", "Muatan residu"), ("solid", "Warna tunggal")]
PERMUKAAN = [("ses", "Molekuler (SES)"), ("sas", "Terjangkau pelarut (SAS)"), ("vdw", "van der Waals")]


def judul_seksi(teks):
    l = QLabel(teks.upper())
    l.setObjectName("sech")
    return l


# ------------------------------------------------------------------ hierarki
class PanelHierarki(QWidget):
    visibilitasBerubah = Signal(str, bool)          # id objek, tampil
    objekDipilih = Signal(str)                      # id objek
    residuDipilih = Signal(str, list)               # id objek, [(rantai, resi)]
    aksiKonteks = Signal(str, str, object)          # id, aksi, nilai

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(6, 6, 6, 6)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter: residu, rantai, ligan")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._saring)
        bl.addWidget(self.filter)
        lay.addWidget(bar)
        self.pohon = QTreeWidget()
        self.pohon.setHeaderHidden(True)
        self.pohon.setColumnCount(2)
        self.pohon.header().setStretchLastSection(False)
        self.pohon.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.pohon.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pohon.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.pohon.setIndentation(14)
        self.pohon.setUniformRowHeights(True)
        self.pohon.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pohon.customContextMenuRequested.connect(self._menu)
        self.pohon.itemChanged.connect(self._centang)
        self.pohon.itemSelectionChanged.connect(self._pilih)
        self.pohon.itemExpanded.connect(self._buka)
        lay.addWidget(self.pohon)
        self._item = {}
        self._diam = False
        self.warna_ikon = kit.hx("ink2")        # disegarkan lewat set_mode saat tema berganti

    def _baru(self, induk, teks, info="", data=None, cek=None, ikon=None):
        it = QTreeWidgetItem(induk, [teks, info])
        it.setData(0, Qt.UserRole, data)
        it.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
        it.setForeground(1, kit.warna("mut"))
        f = it.font(1)
        f.setFamily("Cascadia Mono")
        f.setPointSizeF(8.2)
        it.setFont(1, f)
        if cek is not None:
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(0, Qt.Checked if cek else Qt.Unchecked)
        if ikon:
            it.setIcon(0, icons.ikon(ikon, self.warna_ikon))
        return it

    def tambah(self, o):
        self._diam = True
        info = {"protein": f"{o.info.get('atom', '')} atom", "ligan": o.info.get("rumus", ""),
                "air": str(o.info.get("jumlah", "")), "ion": str(o.info.get("jumlah", "")),
                "pose": id_angka(f"{o.info.get('energi', 0):.2f}") if "energi" in o.info else ""}.get(o.jenis, "")
        induk = self._grup(o.grup) if getattr(o, "grup", "") else self.pohon
        it = self._baru(induk, o.nama, info, ("obj", o.id), o.tampil, IKON_JENIS.get(o.jenis))
        it.setData(0, Qt.UserRole + 1, o.jenis)
        if o.info.get("sematkan"):
            self.set_sematkan(o.id, True)
        if induk is not self.pohon:
            induk.setText(1, str(induk.childCount()))
        if getattr(o, "grup", "") == "Ligan siap docking":
            it.setToolTip(0, "Ligan masukan (pra-docking) di koordinat asal. Pose docking di binding pocket ada di grup 'Hasil'.")
        elif o.jenis == "pose":
            it.setToolTip(0, f"Pose docking {o.nama} (ΔG: {o.info.get('energi', 0):.2f} kcal/mol) di binding site")
        elif o.info.get("siap_docking"):
            it.setToolTip(0, "Reseptor siap docking (PDBQT)")
        f = it.font(0)
        f.setBold(o.jenis == "protein")
        it.setFont(0, f)
        if o.jenis == "protein":
            for c, rs in o.rantai.items():
                ci = self._baru(it, f"Rantai {c}", f"{len(rs)} res", ("rantai", o.id, c), True, "chain")
                ci.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                ci.setData(1, Qt.UserRole, rs)
            it.setExpanded(True)
        self._item[o.id] = it
        self._diam = False
        return it

    def _grup(self, nama):
        g = self._item.get("grup:" + nama)
        if g is None:
            g = self._baru(self.pohon, nama, "", ("grup", nama), True, "layers")
            f = g.font(0)
            f.setBold(True)
            g.setFont(0, f)
            g.setExpanded(True)
            self._item["grup:" + nama] = g
        return g

    def _buka(self, it):
        """Residu dimuat saat rantai dibuka (cepat untuk protein besar)."""
        d = it.data(0, Qt.UserRole)
        if not d or d[0] != "rantai" or it.childCount():
            return
        self._diam = True
        for resn, resi, n in it.data(1, Qt.UserRole) or []:
            self._baru(it, f"{resn} {resi}", "", ("residu", d[1], d[2], resi, resn))
        self._diam = False

    def hapus(self, oid):
        it = self._item.pop(oid, None)
        if it:
            induk = it.parent()
            if induk:
                induk.removeChild(it)
                if induk.childCount() == 0:
                    self._item.pop("grup:" + induk.text(0), None)
                    self.pohon.takeTopLevelItem(self.pohon.indexOfTopLevelItem(induk))
                else:
                    induk.setText(1, str(induk.childCount()))
            else:
                self.pohon.takeTopLevelItem(self.pohon.indexOfTopLevelItem(it))

    def kosongkan(self):
        self.pohon.clear()
        self._item = {}

    def set_centang(self, oid, on):
        it = self._item.get(oid)
        if it:
            self._diam = True
            it.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
            self._diam = False

    def set_sematkan(self, oid, on):
        """Pose tersemat: ikon pin + tooltip; tetap tampil saat pose lain dibuka."""
        it = self._item.get(oid)
        if not it:
            return
        it.setIcon(0, icons.ikon("pin" if on else IKON_JENIS.get(it.data(0, Qt.UserRole + 1), "lig"),
                                 self.warna_ikon))
        it.setToolTip(0, "Disematkan: tetap tampil saat membuka pose lain" if on else "")
        it.setData(0, Qt.UserRole + 2, bool(on))

    def ganti_nama(self, oid, nama):
        if oid in self._item:
            self._item[oid].setText(0, nama)

    def _centang(self, it, kol):
        if self._diam or kol != 0:
            return
        d = it.data(0, Qt.UserRole)
        if d and d[0] == "obj":
            self.visibilitasBerubah.emit(d[1], it.checkState(0) == Qt.Checked)
        elif d and d[0] == "grup":
            on = it.checkState(0) == Qt.Checked
            self._diam = True
            for i in range(it.childCount()):
                it.child(i).setCheckState(0, Qt.Checked if on else Qt.Unchecked)
            self._diam = False
            for i in range(it.childCount()):
                self.visibilitasBerubah.emit(it.child(i).data(0, Qt.UserRole)[1], on)
        elif d and d[0] == "rantai":
            self.aksiKonteks.emit(d[1], "rantai_tampil", (d[2], it.checkState(0) == Qt.Checked))

    def _atur_grup(self, it, on):
        self._diam = True
        it.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        for i in range(it.childCount()):
            it.child(i).setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self._diam = False
        for i in range(it.childCount()):
            cd = it.child(i).data(0, Qt.UserRole)
            if cd and cd[0] == "obj":
                self.visibilitasBerubah.emit(cd[1], on)

    def _pilih(self):
        its = self.pohon.selectedItems()
        if not its:
            return
        d = its[0].data(0, Qt.UserRole)
        if not d:
            return
        if d[0] == "obj":
            self.objekDipilih.emit(d[1])
        elif d[0] == "rantai":
            self.objekDipilih.emit(d[1])
            self.aksiKonteks.emit(d[1], "pilih_rantai", d[2])
        elif d[0] == "residu":
            res = [(x.data(0, Qt.UserRole)[2], x.data(0, Qt.UserRole)[3]) for x in its
                   if x.data(0, Qt.UserRole) and x.data(0, Qt.UserRole)[0] == "residu"
                   and x.data(0, Qt.UserRole)[1] == d[1]]
            self.residuDipilih.emit(d[1], res)

    def pilih_objek(self, oid):
        if oid in self._item:
            self.pohon.setCurrentItem(self._item[oid])

    def _saring(self, teks):
        t = teks.lower().strip()

        def jalan(it):
            cocok = not t or t in it.text(0).lower()
            anak = False
            for i in range(it.childCount()):
                anak = jalan(it.child(i)) or anak
            it.setHidden(not (cocok or anak))
            if t and anak:
                it.setExpanded(True)
            return cocok or anak
        if t:  # pastikan residu sudah dimuat agar bisa dicari
            for oid, top in self._item.items():
                for i in range(top.childCount()):
                    self._buka(top.child(i))
        for i in range(self.pohon.topLevelItemCount()):
            jalan(self.pohon.topLevelItem(i))

    def _menu(self, pos):
        it = self.pohon.itemAt(pos)
        if not it:
            return
        d = it.data(0, Qt.UserRole)
        if not d:
            return
        oid = d[1]
        m = QMenu(self)
        if d[0] == "grup":
            m.addAction("Tampilkan semua di grup ini", lambda: self._atur_grup(it, True))
            m.addAction("Sembunyikan semua di grup ini", lambda: self._atur_grup(it, False))
            m.addSeparator()
            m.addAction(icons.ikon("trash", self.warna_ikon), "Hapus grup dari tampilan",
                        lambda: self.aksiKonteks.emit("", "hapus_grup", oid))
            m.exec(self.pohon.viewport().mapToGlobal(pos))
            return
        if d[0] in ("obj", "rantai"):
            tampil = m.addMenu("Tampilkan")
            for k, t in REPS:
                tampil.addAction(t, lambda k=k: self.aksiKonteks.emit(oid, "show", k))
            semb = m.addMenu("Sembunyikan")
            semb.addAction("Semua", lambda: self.aksiKonteks.emit(oid, "hide_all", None))
            for k, t in REPS:
                semb.addAction(t, lambda k=k: self.aksiKonteks.emit(oid, "hide", k))
            wr = m.addMenu("Warnai")
            for k, t in WARNA_MODE:
                if k == "solid":
                    continue
                wr.addAction(t, lambda k=k: self.aksiKonteks.emit(oid, "color", k))
            wr.addSeparator()
            wr.addAction("Pilih warna…", lambda: self.aksiKonteks.emit(oid, "color_pick", None))
            m.addSeparator()
            m.addAction(icons.ikon("fit", self.warna_ikon), "Fokuskan", lambda: self.aksiKonteks.emit(oid, "zoom", d))
            if d[0] == "obj" and it.data(0, Qt.UserRole + 1) == "pose":
                a = m.addAction(icons.ikon("pin", self.warna_ikon), "Sematkan (tetap tampil saat buka pose lain)",
                                lambda: self.aksiKonteks.emit(oid, "sematkan", None))
                a.setCheckable(True)
                a.setChecked(bool(it.data(0, Qt.UserRole + 2)))
            if d[0] == "obj" and it.data(0, Qt.UserRole + 1) in ("ligan", "pose"):
                m.addAction(icons.ikon("edit", self.warna_ikon), "Edit struktur di Ketcher…",
                            lambda: self.aksiKonteks.emit(oid, "ketcher", None))
            if d[0] == "obj":
                m.addAction("Ganti nama…", lambda: self.aksiKonteks.emit(oid, "rename", None))
                m.addAction(icons.ikon("dl", self.warna_ikon), "Ekspor…", lambda: self.aksiKonteks.emit(oid, "export", None))
                m.addSeparator()
                m.addAction(icons.ikon("trash", self.warna_ikon), "Hapus objek", lambda: self.aksiKonteks.emit(oid, "delete", None))
        elif d[0] == "residu":
            m.addAction("Tampilkan sebagai stick", lambda: self.aksiKonteks.emit(oid, "res_sticks", None))
            m.addAction("Sembunyikan stick", lambda: self.aksiKonteks.emit(oid, "res_hide", None))
            m.addAction("Fokuskan", lambda: self.aksiKonteks.emit(oid, "zoom", d))
            m.addAction("Pusatkan grid box di sini", lambda: self.aksiKonteks.emit(oid, "grid_res", None))
        m.exec(self.pohon.viewport().mapToGlobal(pos))


# ------------------------------------------------------------------- properti
class PanelProperti(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        self.judul = judul_seksi("Properti")
        self.lay.addWidget(self.judul)
        self.isi = QWidget()
        self.form = QFormLayout(self.isi)
        self.form.setContentsMargins(10, 8, 10, 8)
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(5)
        self.lay.addWidget(self.isi)
        self.lay.addStretch(1)
        self.kosong()

    def _bersih(self):
        while self.form.rowCount():
            self.form.removeRow(0)

    def kosong(self):
        self._bersih()
        self.judul.setText("PROPERTI")
        l = QLabel("Klik objek, rantai, atau residu di panel Objek, atau klik atom di viewport, untuk melihat rinciannya.")
        l.setObjectName("muted")
        l.setWordWrap(True)
        self.form.addRow(l)

    def tampil(self, judul, baris):
        self._bersih()
        self.judul.setText(judul.upper())
        for k, v in baris:
            kk = QLabel(k)
            kk.setObjectName("muted")
            vv = QLabel(id_angka(str(v)))
            vv.setObjectName("mono")
            vv.setTextInteractionFlags(Qt.TextSelectableByMouse)
            vv.setWordWrap(True)
            self.form.addRow(kk, vv)


# ------------------------------------------------------------------- tampilan
class TombolWarna(QPushButton):
    warnaBerubah = Signal(str)

    def __init__(self, warna="#2fb3a0"):
        super().__init__()
        self.setFixedSize(46, 24)
        self.set(warna)
        self.clicked.connect(self._pilih)

    def set(self, w):
        self.warna = w
        self.setStyleSheet(f"QPushButton{{background:{w};border:1px solid rgba(0,0,0,.25);border-radius:3px}}")

    def _pilih(self):
        c = QColorDialog.getColor(QColor(self.warna), self, "Pilih warna")
        if c.isValid():
            self.set(c.name())
            self.warnaBerubah.emit(c.name())


class PanelTampilan(QWidget):
    """Kontrol representasi dan warna untuk objek terpilih (setara show/hide/color di PyMOL)."""
    gayaBerubah = Signal(str, dict)   # id objek, gaya baru

    def __init__(self, parent=None):
        super().__init__(parent)
        self.oid = None
        self.gaya = None
        self._diam = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.label = judul_seksi("Tampilan")
        lay.addWidget(self.label)
        isi = QWidget()
        g = QVBoxLayout(isi)
        g.setContentsMargins(10, 8, 10, 10)
        g.setSpacing(8)

        g.addWidget(self._kecil("Representasi (boleh lebih dari satu)"))
        grid = QGridLayout()
        grid.setSpacing(4)
        self.btn_rep = {}
        for i, (k, t) in enumerate(REPS):
            b = QToolButton()
            b.setText(t)
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.toggled.connect(self._ubah)
            grid.addWidget(b, i // 3, i % 3)
            self.btn_rep[k] = b
        g.addLayout(grid)

        g.addWidget(self._kecil("Warna"))
        h = QHBoxLayout()
        self.cmb_warna = QComboBox()
        for k, t in WARNA_MODE:
            self.cmb_warna.addItem(t, k)
        self.cmb_warna.currentIndexChanged.connect(self._ubah)
        self.btn_warna = TombolWarna()
        self.btn_warna.setToolTip("Warna karbon (mode Elemen) atau warna tunggal")
        self.btn_warna.warnaBerubah.connect(lambda *_: self._ubah())
        h.addWidget(self.cmb_warna, 1)
        h.addWidget(self.btn_warna)
        g.addLayout(h)
        pal = QHBoxLayout()
        pal.setSpacing(3)
        # palet pilihan warna molekul: tetap sama di kedua tema supaya warna objek tidak berubah ikut tema
        for w in ["#2fb3a0", "#33a852", "#1f5fbf", "#7b5cd6", "#c25bb5", "#d4594a", "#d98a1c", "#e8c547", "#8a94a6", "#f2f2f2"]:
            b = QPushButton()
            b.setFixedSize(20, 18)
            b.setStyleSheet(f"QPushButton{{background:{w};border:1px solid rgba(0,0,0,.2);border-radius:2px;padding:0}}")
            b.setToolTip(w)
            b.clicked.connect(lambda _=False, w=w: self._palet(w))
            pal.addWidget(b)
        pal.addStretch(1)
        g.addLayout(pal)

        g.addWidget(self._kecil("Transparansi representasi"))
        self.sl_op = QSlider(Qt.Horizontal)
        self.sl_op.setRange(10, 100)
        self.sl_op.setValue(100)
        self.sl_op.valueChanged.connect(self._ubah)
        g.addWidget(self.sl_op)

        g.addWidget(judul_seksi("Permukaan"))
        f = QFormLayout()
        f.setHorizontalSpacing(10)
        self.cmb_surf = QComboBox()
        for k, t in PERMUKAAN:
            self.cmb_surf.addItem(t, k)
        self.cmb_surf.currentIndexChanged.connect(self._ubah)
        self.cmb_swarna = QComboBox()
        for k, t in WARNA_MODE:
            self.cmb_swarna.addItem(t, k)
        self.cmb_swarna.setCurrentIndex(7)
        self.cmb_swarna.currentIndexChanged.connect(self._ubah)
        self.btn_swarna = TombolWarna("#dfe5f0")
        self.btn_swarna.warnaBerubah.connect(lambda *_: self._ubah())
        hs = QHBoxLayout()
        hs.addWidget(self.cmb_swarna, 1)
        hs.addWidget(self.btn_swarna)
        self.sl_sop = QSlider(Qt.Horizontal)
        self.sl_sop.setRange(5, 100)
        self.sl_sop.setValue(75)
        self.sl_sop.valueChanged.connect(self._ubah)
        f.addRow("Jenis", self.cmb_surf)
        f.addRow("Warna", hs)
        f.addRow("Opasitas", self.sl_sop)
        g.addLayout(f)
        catatan = QLabel("Centang 'Permukaan' atau 'Mesh' di atas untuk menampilkan. Permukaan sekitar ligan "
                         "bisa dibuat dari menu konteks residu.")
        catatan.setObjectName("muted")
        catatan.setWordWrap(True)
        g.addWidget(catatan)
        g.addStretch(1)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QScrollArea.NoFrame)
        sc.setWidget(isi)
        lay.addWidget(sc)
        self.setEnabled(False)

    def _kecil(self, t):
        l = QLabel(t)
        l.setObjectName("muted")
        return l

    def _palet(self, w):
        self.btn_warna.set(w)
        if self.cmb_warna.currentData() not in ("element", "solid"):
            self.cmb_warna.setCurrentIndex(0)
        self._ubah()

    def muat(self, o):
        self.oid, self.gaya = o.id, o.gaya
        self._diam = True
        self.label.setText(f"TAMPILAN · {o.nama}")
        reps = set(o.gaya["reps"])
        if "spheres_kecil" in reps:
            reps.add("spheres")
        surf = o.gaya.get("permukaan")
        for k, b in self.btn_rep.items():
            b.setChecked(bool(k in reps or (k == "surface" and surf and not surf.get("mesh"))
                              or (k == "mesh" and surf and surf.get("mesh"))))
        w = o.gaya["warna"]
        self.cmb_warna.setCurrentIndex(max(0, self.cmb_warna.findData(w.get("mode"))))
        self.btn_warna.set(w.get("carbon") or w.get("val") or "#2fb3a0")
        self.sl_op.setValue(int(o.gaya.get("opacity", 1) * 100))
        if surf:
            self.cmb_surf.setCurrentIndex(max(0, self.cmb_surf.findData(surf.get("type", "ses"))))
            self.cmb_swarna.setCurrentIndex(max(0, self.cmb_swarna.findData(surf["color"].get("mode"))))
            self.btn_swarna.set(surf["color"].get("val") or surf["color"].get("carbon") or "#dfe5f0")
            self.sl_sop.setValue(int(surf.get("opacity", 0.75) * 100))
        self._diam = False
        self.setEnabled(True)

    def _ubah(self, *_):
        if self._diam or not self.oid:
            return
        reps = [k for k, b in self.btn_rep.items() if b.isChecked() and k not in ("surface", "mesh")]
        mode = self.cmb_warna.currentData()
        w = {"mode": mode}
        if mode == "element":
            w["carbon"] = self.btn_warna.warna
        elif mode == "solid":
            w["val"] = self.btn_warna.warna
        surf = None
        if self.btn_rep["surface"].isChecked() or self.btn_rep["mesh"].isChecked():
            sm = self.cmb_swarna.currentData()
            sw = {"mode": sm}
            if sm == "solid":
                sw["val"] = self.btn_swarna.warna
            elif sm == "element":
                sw["carbon"] = self.btn_swarna.warna
            surf = {"type": self.cmb_surf.currentData(), "color": sw, "opacity": self.sl_sop.value() / 100,
                    "mesh": self.btn_rep["mesh"].isChecked() and not self.btn_rep["surface"].isChecked()}
        g = dict(self.gaya)
        g.update(reps=reps, warna=w, opacity=self.sl_op.value() / 100, permukaan=surf)
        self.gaya = g
        self.gayaBerubah.emit(self.oid, g)


# --------------------------------------------------------------- log & antrean
class PanelLog(QPlainTextEdit):
    def __init__(self, level="info"):
        super().__init__()
        self.level = level
        self.setObjectName("log")
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)

    def tulis(self, t):
        from datetime import datetime
        self.appendPlainText(f"[{datetime.now():%H:%M:%S}] {t}")
        from ..core.catat import log
        getattr(log, self.level)(t)
