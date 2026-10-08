"""Jendela utama VirmoDock."""
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QComboBox, QDockWidget, QFileDialog, QInputDialog, QLabel, QMainWindow,
                               QMenu, QMessageBox, QSystemTrayIcon, QTabWidget, QToolBar, QToolButton, QVBoxLayout,
                               QWidget)

from ..core import analisis, diagram2d, laporan
from ..core import antrean as antreanmod
from ..core import ekspor as eksmod
from ..core import env as envmod
from ..core import mesin as mesinmod
from ..core import molekul, paths
from ..core import prep_reseptor
from ..core.proyek import Proyek, nama_aman
from . import icons, kerja, theme
from .dialog_ligan import DialogLigan
from .dialog_reseptor import DialogReseptor
from .dialog_bantuan import DialogLapor, DialogLisensi
from .dialogs import DialogAmbil, Wizard
from .dialog_ekspor import DialogEkspor
from .panel_antrean import PanelAntrean
from .panel_hasil import PanelHasil
from .panel_interaksi import PanelInteraksi, TabDiagram
from .tab_banding import TabBanding
from .panel_docking import PanelDocking
from .panels import PanelHierarki, PanelLog, PanelProperti, PanelTampilan
from .viewer_widget import Viewer

from .. import __version__ as VERSI
GRUP_LIGAN = "Ligan siap docking"
MESIN_URUT = ["adgpu", "vina", "ad4"]


class JendelaUtama(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VirmoDock")
        self.setObjectName("VirmoDock")
        self.setAcceptDrops(True)
        self.setDockNestingEnabled(True)
        self.st = paths.settings()
        self.mode = self.st.value("tema", "terang")
        self.objek = {}
        self.env = None
        self.aktif = None
        self.residu_terpilih = (None, [])
        self.box = {"pusat": None, "ukuran": [22.5, 22.5, 22.5], "spasi": 0.375, "tampil": True}
        self.proyek = None
        self._sinkron = False
        self.pelaksana = antreanmod.Pelaksana(self)
        self.t_simpan = QTimer(self)
        self.t_simpan.setSingleShot(True)
        self.t_simpan.setInterval(1000)
        self.t_simpan.timeout.connect(self._simpan_diam)
        self.t_auto = QTimer(self)
        self.t_auto.setInterval(3 * 60 * 1000)   # simpan otomatis berkala (E1)
        self.t_auto.timeout.connect(self._simpan_diam)
        self.t_auto.start()

        self.viewer = Viewer()
        self.viewer.atomDipilih.connect(self._atom_diklik)
        self.viewer.jarakDiukur.connect(lambda d: self.log.tulis(
            f"Jarak {d['a']['resn']}{d['a']['resi']}:{d['a']['atom']} – {d['b']['resn']}{d['b']['resi']}:{d['b']['atom']} = {d['d']:.2f} Å"))
        self.viewer.kotakDigeser.connect(self._kotak_dari_viewer)
        self.tab_tengah = QTabWidget()
        self.tab_tengah.setDocumentMode(True)
        self.tab_tengah.addTab(self.viewer, "Viewport 3D")
        self.hasil = PanelHasil()
        self.hasil.bukaPose.connect(lambda jid, lid, k: self.buka_pose(jid, lid, k))
        self.hasil.bandingkan.connect(self.bandingkan)
        self.hasil.petaInteraksi.connect(self.peta_interaksi)
        self.hasil.ekspor.connect(lambda: self.buka_ekspor(3))
        self.tab_tengah.addTab(self.hasil, "Hasil")
        self.diagram = TabDiagram()
        self.diagram.minta.connect(self._gambar_diagram)
        self.diagram.ekspor.connect(self._diagram_cepat)
        self.tab_tengah.addTab(self.diagram, "Diagram 2D")
        self.banding = None
        self._aktif_inter = None
        self._cache_mol, self._cache_rec = {}, {}
        tengah = QWidget()
        tengah.setObjectName("central")
        v = QVBoxLayout(tengah)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.bar_view = QToolBar()
        self.bar_view.setIconSize(QSize(16, 16))
        v.addWidget(self.bar_view)
        v.addWidget(self.tab_tengah)
        self.setCentralWidget(tengah)

        self._panel()
        self.viewer.pesanJs.connect(self.log.tulis)
        self._aksi()
        self._menu()
        self._toolbar()
        self._status()
        self._tray()
        self._hubungkan_pelaksana()
        self.terapkan_tema(self.mode)

        geo = self.st.value("geometri")
        if geo:
            self.restoreGeometry(geo)
        else:
            self._ukuran_awal()
        self._pastikan_di_layar()
        state = self.st.value("layout")
        if state:
            self.restoreState(state)
        else:
            QTimer.singleShot(0, lambda: (self.resizeDocks([self.d_antre], [190], Qt.Vertical),
                                          self.resizeDocks([self.d_hier, self.d_prop], [270, 330], Qt.Horizontal)))
        QTimer.singleShot(50, self.deteksi)
        QTimer.singleShot(400, self._cek_pemulihan)

    # ------------------------------------------------------------ panel
    def _dock(self, judul, w, area, nama):
        d = QDockWidget(judul, self)
        d.setObjectName(nama)
        d.setWidget(w)
        d.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(area, d)
        return d

    def _panel(self):
        self.hier = PanelHierarki()
        self.hier.visibilitasBerubah.connect(self.set_tampil)
        self.hier.objekDipilih.connect(self.pilih_objek)
        self.hier.residuDipilih.connect(self.pilih_residu)
        self.hier.aksiKonteks.connect(self.aksi_konteks)
        self.d_hier = self._dock("Hierarki", self.hier, Qt.LeftDockWidgetArea, "dock_hierarki")
        self.d_hier.setMinimumWidth(240)

        self.prop = PanelProperti()
        self.tampilan = PanelTampilan()
        self.tampilan.gayaBerubah.connect(self.ubah_gaya)
        self.d_prop = self._dock("Properti", self.prop, Qt.RightDockWidgetArea, "dock_properti")
        self.d_tamp = self._dock("Tampilan", self.tampilan, Qt.RightDockWidgetArea, "dock_tampilan")
        self.d_prop.setMinimumWidth(300)
        self.param = PanelDocking()
        self.param.parameterBerubah.connect(self._param_berubah)
        self.param.kotakBerubah.connect(self._kotak_dari_panel)
        self.param.aksiKotak.connect(self.aksi_kotak)
        self.param.tampilKotak.connect(lambda on: self.a_box.setChecked(on) or self.toggle_box(on))
        self.param.jalankan.connect(self.jalankan_docking)
        self.d_param = self._dock("Parameter", self.param, Qt.RightDockWidgetArea, "dock_parameter")
        self.tabifyDockWidget(self.d_tamp, self.d_param)
        self.p_inter = PanelInteraksi()
        self.p_inter.jenisBerubah.connect(self._tampilkan_interaksi)
        self.p_inter.opsiBerubah.connect(self._tampilkan_interaksi)
        self.p_inter.fokusResidu.connect(self._fokus_interaksi)
        self.d_inter = self._dock("Interaksi", self.p_inter, Qt.RightDockWidgetArea, "dock_interaksi")
        self.tabifyDockWidget(self.d_param, self.d_inter)
        self.d_param.raise_()

        self.log = PanelLog()
        self.antrean = PanelAntrean()
        self.antrean.aksi.connect(self.aksi_antrean)
        self.pesan = PanelLog("warning")
        self.d_antre = self._dock("Antrean job", self.antrean, Qt.BottomDockWidgetArea, "dock_antrean")
        self.d_log = self._dock("Log", self.log, Qt.BottomDockWidgetArea, "dock_log")
        self.d_pesan = self._dock("Pesan", self.pesan, Qt.BottomDockWidgetArea, "dock_pesan")
        self.tabifyDockWidget(self.d_antre, self.d_log)
        self.tabifyDockWidget(self.d_log, self.d_pesan)
        self.d_antre.raise_()
        self.resizeDocks([self.d_antre], [200], Qt.Vertical)
        self.resizeDocks([self.d_hier, self.d_prop], [270, 320], Qt.Horizontal)

    # ------------------------------------------------------------- aksi
    def _a(self, teks, ikon=None, fn=None, kunci=None, cek=False, tip=None):
        a = QAction(teks, self)
        a.setData(ikon)
        if fn:
            a.triggered.connect(fn)
        if kunci:
            a.setShortcut(QKeySequence(kunci))
        a.setCheckable(cek)
        a.setToolTip(tip or teks)
        return a

    def _aksi(self):
        A = self._a
        self.a_baru = A("Proyek baru…", "new", self.proyek_baru, "Ctrl+N")
        self.a_buka_proyek = A("Buka proyek…", "folder", self.buka_proyek, "Ctrl+Shift+O",
                               tip="Buka folder proyek VirmoDock (.vmd)")
        self.a_buka = A("Buka…", "open", self.buka_berkas, "Ctrl+O", tip="Buka berkas struktur (PDB, PDBQT, CIF, SDF, MOL2, SMILES)")
        self.a_simpan = A("Simpan proyek", "save", self.simpan, "Ctrl+S")
        self.a_rcsb = A("Ambil dari RCSB PDB…", "import", lambda: self.ambil(0), "Ctrl+Shift+P")
        self.a_pubchem = A("Ambil dari PubChem…", None, lambda: self.ambil(1))
        self.a_smiles = A("Dari SMILES…", None, lambda: self.ambil(2))
        self.a_keluar = A("Keluar", None, self.close, "Ctrl+Q")
        self.a_rec = A("Siapkan reseptor…", "rec", self.siapkan_reseptor, tip="Hapus air/ligan, tambah hidrogen dan muatan, ekspor PDBQT")
        self.a_lig = A("Siapkan ligan…", "lig", self.siapkan_ligan, tip="Tambah H, protonasi pH, minimisasi, torsi, PDBQT")
        self.a_box = A("Grid box", "box", self.toggle_box, "G", cek=True, tip="Tampilkan / atur grid box")
        self.a_run = A("Jalankan", "play", self.jalankan_docking, "F5", tip="Jalankan docking (F5)")
        self.a_antre = A("Antrean job", "queue", lambda: (self.d_antre.show(), self.d_antre.raise_()))
        self.a_param = A("Parameter docking", "sliders", lambda: (self.d_param.show(), self.d_param.raise_()), "Ctrl+D")
        self.a_ukur = A("Ukur jarak", "ruler", self.toggle_ukur, "M", cek=True, tip="Klik dua atom untuk mengukur jarak")
        self.a_inter = A("Interaksi", "hbond", self._tampilkan_interaksi, "I", cek=True,
                         tip="Tampilkan interaksi protein–ligan")
        self.a_inter.setChecked(True)
        self.a_foto = A("Ekspor gambar…", "camera", lambda: self.buka_ekspor(0), "Ctrl+Shift+S",
                        tip="Gambar 3D resolusi tinggi (PNG/TIFF/JPEG, DPI pilihan)")
        self.a_ekspor = A("Ekspor…", "dl", lambda: self.buka_ekspor(3), "Ctrl+E",
                          tip="Pusat ekspor: gambar, diagram 2D, struktur, tabel, laporan")
        self.a_lapor = A("Laporan PDF…", "report", lambda: self.buka_ekspor(4))
        self.a_validasi = A("Validasi redocking…", "check", self.validasi_redocking,
                            tip="Docking ulang ligan kristal dan hitung RMSD (≤ 2,0 Å = valid)")
        self.a_fit = A("Sesuaikan tampilan", "fit", lambda: self.viewer.js("fokusSemua"), "F")
        self.a_putar = A("Putar otomatis", "rotate", lambda on: self.viewer.js("spin", on), cek=True)
        self.a_tema = A("Mode gelap", "moon", self.ganti_tema, "Ctrl+T", cek=True)
        self.a_cek = A("Cek sistem / GPU…", "gpu", lambda: self.deteksi(wizard=True))
        self.a_reset = A("Atur ulang layout", None, self.reset_layout)

    def _menu(self):
        mb = self.menuBar()
        m = mb.addMenu("&File")
        for a in (self.a_baru, self.a_buka_proyek, self.a_simpan):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_buka)
        m.addSeparator()
        sub = m.addMenu("Impor dari database")
        for a in (self.a_rcsb, self.a_pubchem, self.a_smiles):
            sub.addAction(a)
        m.addSeparator()
        m.addAction(self.a_ekspor)
        m.addAction(self.a_foto)
        m.addAction(self.a_lapor)
        m.addSeparator()
        sub = m.addMenu("Pindah laptop")
        sub.addAction("Ekspor pengaturan & proyek…", self.ekspor_cadangan)
        sub.addAction("Impor pengaturan & proyek…", self.impor_cadangan)
        m.addSeparator()
        m.addAction(self.a_keluar)
        m = mb.addMenu("&Edit")
        m.addAction("Hapus objek terpilih", self.hapus_terpilih, QKeySequence.Delete)
        m.addAction("Pilih semua", lambda: self.hier.pohon.selectAll(), QKeySequence.SelectAll)
        m = mb.addMenu("&View")
        for d in (self.d_hier, self.d_prop, self.d_tamp, self.d_param, self.d_antre, self.d_log, self.d_pesan):
            m.addAction(d.toggleViewAction())
        m.addSeparator()
        for a in (self.a_fit, self.a_putar, self.a_tema, self.a_reset):
            m.addAction(a)
        m = mb.addMenu("&Prepare")
        for a in (self.a_rec, self.a_lig, self.a_box):
            m.addAction(a)
        m = mb.addMenu("&Dock")
        m.addAction(self.a_param)
        m.addAction(self.a_run)
        m.addAction(self.a_antre)
        m.addSeparator()
        m.addAction("Tabel hasil", lambda: self.tab_tengah.setCurrentWidget(self.hasil))
        m = mb.addMenu("&Analyze")
        m.addAction(self.a_validasi)
        m.addSeparator()
        m.addAction("Diagram interaksi 2D", lambda: self.tab_tengah.setCurrentWidget(self.diagram))
        m.addAction("Peta interaksi residu × ligan", self.peta_interaksi)
        m.addAction("Hitung ulang analisis hasil", self.analisis_ulang)
        m.addSeparator()
        for a in (self.a_inter, self.a_ukur):
            m.addAction(a)
        m.addAction("Hapus pengukuran", lambda: self.viewer.js("hapusUkur"))
        m = mb.addMenu("&Tools")
        self.m_buka_di = m.addMenu("Buka di…")
        m.addAction(self.a_cek)
        m.addAction("Uji mandiri komponen…", self.uji_mandiri)
        m = mb.addMenu("&Help")
        m.addAction("Panduan pengguna", lambda: self.buka_panduan("panduan"), "F1")
        m.addAction("Tutorial docking (PDF)", lambda: self.buka_panduan("Tutorial_Docking_VirmoDock.pdf"))
        sub = m.addMenu("Dokumentasi")
        for k, t in (("instalasi", "Instalasi"), ("pindah_laptop", "Pindah laptop"), ("gpu", "Setup GPU"),
                     ("troubleshooting", "Troubleshooting"), ("metode", "Metode & kriteria")):
            sub.addAction(t, lambda k=k: self.buka_panduan(k))
        m.addSeparator()
        m.addAction("Lapor masalah / kirim saran…", self.lapor_masalah)
        m.addAction("Buka folder log", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.LOG))))
        m.addAction("Lisensi & cara mengutip…", lambda: DialogLisensi(VERSI, self).exec())
        m.addSeparator()
        m.addAction("Tentang VirmoDock", self.tentang)

    def _toolbar(self):
        tb = QToolBar("Utama")
        tb.setObjectName("toolbar_utama")
        tb.setIconSize(QSize(16, 16))
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        self.tb = tb

        def ikon_saja(a):
            tb.addAction(a)
            tb.widgetForAction(a).setToolButtonStyle(Qt.ToolButtonIconOnly)
        ikon_saja(self.a_buka)
        ikon_saja(self.a_simpan)
        tb.addAction(self.a_rcsb)
        self.a_rcsb.setIconText("Impor")
        tb.addSeparator()
        self.a_rec.setIconText("Reseptor")
        self.a_lig.setIconText("Ligan")
        tb.addAction(self.a_rec)
        tb.addAction(self.a_lig)
        tb.addAction(self.a_box)
        tb.addSeparator()
        tb.addWidget(self._lbl(" Mesin "))
        self.cmb_mesin = QComboBox()
        for k in MESIN_URUT:
            self.cmb_mesin.addItem(mesinmod.MESIN[k], k)
        self.cmb_mesin.currentIndexChanged.connect(self._toolbar_mesin)
        tb.addWidget(self.cmb_mesin)
        tb.addWidget(self._lbl("  Perangkat "))
        self.cmb_alat = QComboBox()
        self.cmb_alat.addItem("Mendeteksi…")
        self.cmb_alat.setMinimumWidth(210)
        self.cmb_alat.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.cmb_alat.currentIndexChanged.connect(self._toolbar_alat)
        tb.addWidget(self.cmb_alat)
        tb.addAction(self.a_run)
        tb.widgetForAction(self.a_run).setObjectName("run")
        ikon_saja(self.a_antre)
        tb.addSeparator()
        for a in (self.a_inter, self.a_ukur, self.a_foto, self.a_lapor):
            ikon_saja(a)
        tb.addSeparator()
        self.btn_buka_di = QToolButton()
        self.btn_buka_di.setText("Buka di…")
        self.btn_buka_di.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_buka_di.setPopupMode(QToolButton.InstantPopup)
        self.btn_buka_di.setMenu(self.m_buka_di)
        tb.addWidget(self.btn_buka_di)
        sp = QWidget()
        sp.setSizePolicy(sp.sizePolicy().horizontalPolicy().Expanding, sp.sizePolicy().verticalPolicy().Preferred)
        tb.addWidget(sp)
        ikon_saja(self.a_tema)

        # toolbar kecil di atas viewport: gaya cepat
        bv = self.bar_view
        bv.setObjectName("toolbar_view")
        bv.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.grp_gaya = QActionGroup(self)
        for k, t in (("cartoon", "Kartun"), ("sticks", "Stick"), ("ballstick", "Bola–stick"), ("surface", "Permukaan")):
            a = QAction(t, self, checkable=True)
            a.setData(k)
            a.triggered.connect(lambda _=False, k=k: self.gaya_cepat(k))
            self.grp_gaya.addAction(a)
            bv.addAction(a)
        self.grp_gaya.actions()[0].setChecked(True)
        bv.addSeparator()
        for a in (self.a_fit, self.a_putar):
            bv.addAction(a)
            bv.widgetForAction(a).setToolButtonStyle(Qt.ToolButtonIconOnly)

    def _lbl(self, t):
        l = QLabel(t)
        l.setObjectName("muted")
        return l

    def _status(self):
        sb = self.statusBar()
        self.s_gpu = QLabel("Mendeteksi perangkat…")
        self.s_prog = QLabel("")
        self.s_atom = QLabel("")
        self.s_folder = QLabel("")
        sb.addWidget(self.s_gpu)
        sb.addWidget(self.s_prog)
        sb.addWidget(self.s_atom, 1)
        sb.addPermanentWidget(self.s_folder)

    # -------------------------------------------------------------- tema
    def terapkan_tema(self, mode):
        self.mode = mode
        t = theme.TOKEN[mode]
        app = QApplication.instance()
        cek = paths.APPDATA / f"cek_{mode}.png"
        if not cek.exists():
            icons.pixmap("check", "#ffffff", 12, 2).save(str(cek))
        app.setPalette(theme.palet(mode))
        app.setStyleSheet(theme.qss(mode).replace("ICON_CHECK", cek.as_posix()))
        warna, aktif = t["ink2"], t["acct"]
        for a in self.findChildren(QAction):
            if a.data() and isinstance(a.data(), str) and a.data() in icons.PATH:
                a.setIcon(icons.ikon(a.data(), "#ffffff" if a is self.a_run else warna, aktif))
        self.a_tema.setIcon(icons.ikon("sun" if mode == "gelap" else "moon", warna))
        self.a_tema.setChecked(mode == "gelap")
        self.btn_buka_di.setIcon(icons.ikon("ext", warna))
        self.hier.warna_ikon = warna
        self.antrean.terapkan_tema(mode)
        self.hasil.mode = self.p_inter.mode = mode
        if self.proyek:
            self._muat_hasil()
        self._gambar_diagram()
        self.param.warna_warn = t["warn"]
        self.param._info_kotak()
        self.viewer.page().setBackgroundColor(t["view"])
        self.viewer.js("tema", mode == "gelap", t["view"])
        self.st.setValue("tema", mode)

    def ganti_tema(self):
        self.terapkan_tema("gelap" if self.mode == "terang" else "terang")

    # ---------------------------------------------------- deteksi perangkat
    def deteksi(self, wizard=False):
        self.s_gpu.setText("Mendeteksi GPU…")
        manual = self.st.value("eksternal", {}) or {}
        kerja.jalankan(lambda lapor: envmod.deteksi(manual), selesai=lambda e: self._env_siap(e, wizard),
                       galat=lambda g: self.pesan.tulis("Deteksi perangkat gagal: " + g))

    def _env_siap(self, e, wizard):
        self.env = e
        g = e.gpu_utama
        self._sinkron = True
        self.cmb_alat.clear()
        alat = []
        for x in e.gpu:
            if x.opencl:
                alat.append((f"GPU · {x.nama.replace('NVIDIA GeForce ', '')}", "gpu",
                             icons.ikon("gpu", theme.TOKEN[self.mode]["ok"])))
                break  # AutoDock-GPU memakai satu perangkat OpenCL (yang pertama)
        alat.append((f"CPU · {e.inti} thread", "cpu", icons.ikon("cpu", theme.TOKEN[self.mode]["ink2"])))
        for t, d, ik in alat:
            self.cmb_alat.addItem(ik, t, d)
        self.param.set_perangkat(alat)
        self._sinkron = False
        simpan = (self.proyek.parameter if self.proyek else None) or {}
        if e.mode_bawaan == "cpu":
            self.param.set_parameter({"mesin": "vina", "perangkat": "cpu"})
            if simpan.get("mesin") == "adgpu":
                self.pesan.tulis("GPU/OpenCL tidak tersedia di laptop ini: mesin diganti ke AutoDock Vina (CPU).")
        elif simpan:
            self.param.set_parameter(simpan)
        self._param_berubah(self.param.parameter())
        if g and g.opencl:
            self.s_gpu.setText(f"● {g.nama} · {g.vram_gb:g} GB · driver {g.driver} · OpenCL")
            self.s_gpu.setStyleSheet(f"color:{theme.TOKEN[self.mode]['ink2']}")
        elif g:
            self.s_gpu.setText(f"● {g.nama} · OpenCL tidak tersedia — mode CPU")
        else:
            self.s_gpu.setText("● Tidak ada GPU — mode CPU (Vina)")
        self.s_prog.setText(f"CPU {e.inti} thread · RAM {e.ram_gb:g} GB")
        self.log.tulis(f"Perangkat: {g.nama if g else 'tanpa GPU'}; mode bawaan {e.mode_bawaan.upper()}")
        for c in e.catatan:
            self.pesan.tulis(c)
        self.m_buka_di.clear()
        for nama in ("PyMOL", "ChimeraX", "Discovery Studio Visualizer"):
            a = self.m_buka_di.addAction(nama, lambda n=nama: self.buka_di(n))
            a.setEnabled(nama in e.eksternal)
        self.m_buka_di.addSeparator()
        self.m_buka_di.addAction("Atur lokasi program…", self.atur_eksternal)
        if wizard or not self.st.value("wizard_selesai", False, type=bool):
            w = Wizard(e, self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())), self)
            if w.exec():
                self.st.setValue("folder_kerja", w.ed_folder.text())
                Path(w.ed_folder.text()).mkdir(parents=True, exist_ok=True)
            self.st.setValue("wizard_selesai", True)
        self.s_folder.setText(self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))

    # ------------------------------------------------------------- objek
    def tambah_objek(self, daftar, fokus=True):
        for o in daftar:
            self.objek[o.id] = o
            self.hier.tambah(o)
            self.viewer.muat(o)
            self.viewer.tampil(o, molekul.spek_viewer(o))
            self.log.tulis(f"Dimuat: {o.nama} ({o.jenis})")
        asli = [o for o in daftar if o.jenis == "ligan" and o.info.get("ligan_asli") and o.fmt == "pdb"]
        if asli and not self.box["pusat"]:  # grid otomatis pada ligan asli terbesar
            self.box_ke_objek(max(asli, key=lambda o: o.info.get("atom_berat", 0)))
        if fokus and daftar:
            prot = next((o for o in daftar if o.jenis == "protein"), daftar[0])
            self.viewer.js("fokus", {"id": prot.id})
            self.hier.pilih_objek(prot.id)
        self._hitung_atom()

    def _hitung_atom(self):
        n = sum(o.info.get("atom", 0) or 0 for o in self.objek.values())
        self.s_atom.setText(f"{len(self.objek)} objek · {n} atom")

    def set_tampil(self, oid, on):
        o = self.objek.get(oid)
        if o:
            o.tampil = on
            self.viewer.tampil(o, molekul.spek_viewer(o))
            if self._aktif_inter and oid in (self._aktif_inter["oid"], self._aktif_inter["rec"]):
                self._tampilkan_interaksi()

    def ubah_gaya(self, oid, gaya):
        o = self.objek.get(oid)
        if o:
            o.gaya = gaya
            self.viewer.tampil(o, molekul.spek_viewer(o))

    def pilih_objek(self, oid):
        o = self.objek.get(oid)
        if not o:
            return
        self.aktif = oid
        self.tampilan.muat(o)
        i = o.info
        if o.jenis == "protein":
            baris = [("Jenis", "Protein (siap docking)" if i.get("siap_docking") else "Protein"),
                     ("Sumber", o.sumber or "–"), ("Rantai", ", ".join(o.rantai)),
                     ("Residu", i.get("residu")), ("Atom", i.get("atom"))]
            if i.get("siap_docking") and self.proyek and self.proyek.reseptor:
                r = self.proyek.reseptor
                baris += [("Metode", r.get("metode")), ("Ion logam", ", ".join(r.get("logam") or []) or "–"),
                          ("Residu dibuang", ", ".join(r.get("dibuang") or []) or "–"), ("PDBQT", r.get("pdbqt"))]
            if i.get("resolusi"):
                baris.append(("Resolusi", f"{i['resolusi']:.2f} Å"))
        elif o.jenis in ("ligan", "pose"):
            baris = [("Jenis", "Ligan" if o.jenis == "ligan" else "Pose docking"), ("Sumber", o.sumber or "–"),
                     ("Rumus", i.get("rumus", "–")), ("Massa molekul", f"{i.get('mw', 0):.2f} g/mol"),
                     ("Atom berat", i.get("atom_berat", "–"))]
            for k, t in (("torsi", "Ikatan rotasi"), ("donor", "Donor ikatan H"), ("akseptor", "Akseptor ikatan H"),
                         ("logp", "LogP (Crippen)"), ("tpsa", "TPSA (Å²)"), ("smiles", "SMILES")):
                if k in i:
                    baris.append((t, i[k]))
            if i.get("ligan_asli"):
                baris.append(("Catatan", "Ligan asli kristal — bisa dipakai untuk pusat grid dan validasi redocking"))
            if i.get("siap_docking"):
                baris.append(("Preparasi", f"{i.get('status', 'siap')}" + (f" — {i['keterangan']}" if i.get("keterangan") else "")))
                baris.append(("PDBQT", f"ligan/pdbqt/{i.get('lid')}.pdbqt"))
            if o.jenis == "pose":
                baris = [("Jenis", "Pose docking"), ("Ligan", i.get("ligan")), ("Mesin", i.get("mesin")),
                         ("Job", i.get("job")), ("ΔG (kcal/mol)", f"{i.get('energi', 0):.2f}"),
                         ("Ki perkiraan", i.get("ki") or "–")]
                if i.get("klaster"):
                    baris.append(("Ukuran klaster", i["klaster"]))
                if i.get("rmsd_ref") is not None and i.get("rmsd_ref", -1) >= 0:
                    baris.append(("RMSD ke masukan (Å)", f"{i['rmsd_ref']:.2f}"))
                if i.get("rmsd_lb") or i.get("rmsd_ub"):
                    baris.append(("RMSD l.b. / u.b. (Å)", f"{i.get('rmsd_lb', 0):.2f} / {i.get('rmsd_ub', 0):.2f}"))
        else:
            baris = [("Jenis", o.jenis.capitalize()), ("Jumlah", i.get("jumlah", "–"))]
        self.prop.tampil(f"{o.nama}", baris)
        if o.jenis in ("pose", "ligan"):
            self.analisis_objek(o)

    def pilih_residu(self, oid, res):
        o = self.objek.get(oid)
        if not o or not res:
            return
        self.residu_terpilih = (oid, res)
        sel = self._sel_residu(res)
        self.viewer.js("sorot", oid, sel)
        c, r = res[0]
        resn = next((x[0] for x in o.rantai.get(c, []) if x[1] == r), "")
        self.prop.tampil(f"{resn} {r} · rantai {c}", [("Objek", o.nama), ("Residu", f"{resn} {r}"), ("Rantai", c),
                                                       ("Terpilih", f"{len(res)} residu")])

    def _sel_residu(self, res):
        rantai = {}
        for c, r in res:
            rantai.setdefault(c, []).append(r)
        if len(rantai) == 1:
            c, rs = next(iter(rantai.items()))
            return {"chain": c, "resi": rs}
        return {"or": [{"chain": c, "resi": rs} for c, rs in rantai.items()]}

    def _atom_diklik(self, a):
        o = self.objek.get(a["id"])
        if not o:
            return
        self.hier.pilih_objek(o.id)
        self.prop.tampil(f"{a.get('resn', '')} {a.get('resi', '')} · {a.get('atom', '')}", [
            ("Objek", o.nama), ("Residu", f"{a.get('resn', '')} {a.get('resi', '')}"), ("Rantai", a.get("chain") or "–"),
            ("Atom", f"{a.get('atom', '')} ({a.get('elem', '')})"), ("Serial", a.get("serial")),
            ("Koordinat (Å)", f"{a['x']:.3f}  {a['y']:.3f}  {a['z']:.3f}")])
        self.viewer.js("sorot", o.id, {"chain": a.get("chain"), "resi": a.get("resi")})
        self.residu_terpilih = (o.id, [(a.get("chain"), a.get("resi"))])

    def aksi_konteks(self, oid, aksi, nilai):
        if aksi == "hapus_grup":
            for x in [x for x in self.objek.values() if x.grup == nilai]:
                if x.info.get("siap_docking"):
                    continue  # ligan siap docking tetap ada di proyek; hanya pose/hasil yang dihapus
                self.hapus_objek(x.id)
            return
        o = self.objek.get(oid)
        if not o:
            return
        g = dict(o.gaya)
        g["reps"] = list(g["reps"])
        if aksi == "show":
            if nilai in ("surface", "mesh"):
                g["permukaan"] = {"type": "ses", "color": {"mode": "solid", "val": "#dfe5f0"}, "opacity": 0.75,
                                  "mesh": nilai == "mesh"}
            elif nilai not in g["reps"]:
                g["reps"].append(nilai)
        elif aksi == "hide":
            if nilai in ("surface", "mesh"):
                g["permukaan"] = None
            else:
                g["reps"] = [r for r in g["reps"] if r != nilai and not (nilai == "spheres" and r == "spheres_kecil")]
        elif aksi == "hide_all":
            g["reps"], g["permukaan"] = [], None
        elif aksi == "color":
            g["warna"] = {"mode": nilai, "carbon": g["warna"].get("carbon", "#2fb3a0")}
        elif aksi == "color_pick":
            from PySide6.QtWidgets import QColorDialog
            c = QColorDialog.getColor(parent=self, title="Pilih warna")
            if not c.isValid():
                return
            g["warna"] = {"mode": "solid", "val": c.name()}
        elif aksi == "zoom":
            if nilai[0] == "residu":
                self.viewer.js("fokus", {"id": oid, "chain": nilai[2], "resi": nilai[3]})
            elif nilai[0] == "rantai":
                self.viewer.js("fokus", {"id": oid, "chain": nilai[2]})
            else:
                self.viewer.js("fokus", {"id": oid})
            return
        elif aksi in ("res_sticks", "res_hide"):
            _, res = self.residu_terpilih
            if not res:
                return
            sel = self._sel_residu(res)
            g["khusus"] = [k for k in g.get("khusus", []) if k["sel"] != sel]
            if aksi == "res_sticks":
                g["khusus"].append({"sel": sel, "rep": "sticks", "warna": {"mode": "element", "carbon": "#8a94a6"}})
        elif aksi == "grid_res":
            self.aksi_kotak("residu")
            self.d_param.raise_()
            return
        elif aksi == "rantai_tampil":
            c, on = nilai
            if on:
                g["khusus"] = [k for k in g.get("khusus", []) if k.get("sembunyi") != c]
            else:
                g["khusus"] = g.get("khusus", []) + [{"sel": {"chain": c}, "rep": "hide", "sembunyi": c}]
        elif aksi == "pilih_rantai":
            self.viewer.js("sorot", oid, {"chain": nilai})
            return
        elif aksi == "rename":
            nama, ok = QInputDialog.getText(self, "Ganti nama", "Nama baru:", text=o.nama)
            if ok and nama.strip():
                o.nama = nama.strip()
                self.hier.ganti_nama(oid, o.nama)
            return
        elif aksi == "export":
            self.ekspor_objek(o)
            return
        elif aksi == "delete":
            self.hapus_objek(oid)
            return
        o.gaya = g
        self.viewer.tampil(o, molekul.spek_viewer(o))
        if self.aktif == oid:
            self.tampilan.muat(o)

    def gaya_cepat(self, k):
        """Toolbar viewport: gaya cepat untuk objek aktif (atau protein pertama)."""
        o = self.objek.get(self.aktif) or next((x for x in self.objek.values() if x.jenis == "protein"), None)
        if not o:
            return
        g = dict(o.gaya)
        if k == "surface":
            g["permukaan"] = {"type": "ses", "color": {"mode": "hydro"}, "opacity": 0.85, "mesh": False}
        else:
            g["reps"], g["permukaan"] = [k], None
        self.ubah_gaya(o.id, g)
        self.tampilan.muat(o)

    def hapus_objek(self, oid):
        self._cache_mol.pop(oid, None)
        if self._aktif_inter and self._aktif_inter["oid"] == oid:
            self.viewer.js("interaksi", [], {})
            self._aktif_inter = None
            self.p_inter.kosong()
        if oid in self.objek:
            self.viewer.hapus(oid)
            self.hier.hapus(oid)
            del self.objek[oid]
            self._hitung_atom()

    def hapus_terpilih(self):
        for it in self.hier.pohon.selectedItems():
            d = it.data(0, Qt.UserRole)
            if d and d[0] == "obj":
                self.hapus_objek(d[1])

    # -------------------------------------------------------------- impor
    def buka_berkas(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Buka struktur", self.st.value("dir_terakhir", ""),
                                             "Struktur (*.pdb *.ent *.pdbqt *.cif *.mmcif *.sdf *.sd *.mol *.mol2 *.smi);;Semua (*.*)")
        if fs:
            self.st.setValue("dir_terakhir", str(Path(fs[0]).parent))
            self.impor(fs)

    def impor(self, berkas):
        def kerjakan(lapor):
            hasil = []
            for f in berkas:
                try:
                    hasil += molekul.impor_berkas(f)
                    lapor.log.emit(f"Impor {Path(f).name}")
                except Exception as e:
                    lapor.log.emit(f"Gagal impor {Path(f).name}: {e}")
            return hasil
        self.statusBar().showMessage("Mengimpor…", 3000)
        kerja.jalankan(kerjakan, selesai=self.tambah_objek, galat=self._galat, log=self.log.tulis)

    def ambil(self, tab):
        d = DialogAmbil(self, tab)
        if not d.exec():
            return
        req = d.permintaan()
        if not req:
            return
        jenis, isi = req

        def kerjakan(lapor):
            hasil = []
            for x in isi:
                try:
                    if jenis == "rcsb":
                        objs, teks, fmt = molekul.unduh_rcsb(x)
                        hasil += objs
                    elif jenis == "pubchem":
                        hasil += molekul.unduh_pubchem(x)
                    else:
                        bag = x.split()
                        hasil += molekul.dari_smiles(bag[0], bag[1] if len(bag) > 1 else None)
                    lapor.log.emit(f"Diambil: {x}")
                except Exception as e:
                    lapor.log.emit(f"Gagal: {x} — {e}")
            return hasil
        self.statusBar().showMessage("Mengunduh…", 3000)
        kerja.jalankan(kerjakan, selesai=self.tambah_objek, galat=self._galat, log=self.log.tulis)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        fs = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        dirs = [f for f in fs if os.path.isdir(f)]
        for d in dirs:
            fs.remove(d)
            fs += [str(p) for p in Path(d).rglob("*") if p.suffix.lower() in
                   (".pdb", ".pdbqt", ".cif", ".sdf", ".mol", ".mol2", ".smi")]
        if fs:
            self.impor(fs)

    # ------------------------------------------------------------ grid box
    def _koordinat(self, o, sel=None):
        """Koordinat atom objek; sel = {(rantai, resi)} untuk membatasi ke residu tertentu."""
        xs = []
        for b in o.teks.splitlines():
            if b.startswith(("ATOM", "HETATM")):
                if sel is not None:
                    try:
                        if (b[21].strip(), int(b[22:26])) not in sel:
                            continue
                    except ValueError:
                        continue
                xs.append([float(b[30:38]), float(b[38:46]), float(b[46:54])])
        if not xs and o.fmt == "sdf":
            from rdkit import Chem
            m = Chem.MolFromMolBlock(o.teks, removeHs=False)
            xs = [list(p) for p in m.GetConformer().GetPositions()] if m else []
        return xs

    def _atur_kotak(self, pusat, ukuran=None, spasi=None, sumber=""):
        self.box["pusat"] = [round(v, 3) for v in pusat]
        if ukuran:
            self.box["ukuran"] = [round(v, 2) for v in ukuran]
        if spasi:
            self.box["spasi"] = spasi
        self.box["tampil"] = True
        self.a_box.setChecked(True)
        self._gambar_box()
        self.param.set_kotak(self.box)
        self._simpan_kotak()
        if sumber:
            self.log.tulis(f"Grid box: {sumber} · pusat {self.box['pusat']} · ukuran {self.box['ukuran']}")

    def box_ke_objek(self, o, tepi=None):
        xs = self._koordinat(o)
        if not xs:
            return
        c = [sum(p[i] for p in xs) / len(xs) for i in range(3)]
        ext = [max(p[i] for p in xs) - min(p[i] for p in xs) for i in range(3)]
        uk = [max(20.0, e + 10) for e in ext] if tepi is None else [e + 2 * tepi for e in ext]
        self._atur_kotak(c, uk, sumber=f"dipusatkan pada {o.nama}")

    def aksi_kotak(self, k):
        if k == "ligan_asli":
            o = self.objek.get(self.aktif)
            if not (o and o.info.get("ligan_asli")):
                o = next((x for x in self.objek.values() if x.info.get("ligan_asli")), None)
            if not o:
                self._galat("Tidak ada ligan asli kristal. Impor struktur PDB yang berisi ligan, atau pakai "
                            "'Pusat ke residu terpilih'.")
                return
            self.box_ke_objek(o)
        elif k == "residu":
            oid, res = self.residu_terpilih
            o = self.objek.get(oid)
            xs = self._koordinat(o, set(res)) if o and res else []
            if not xs:
                self._galat("Pilih residu dulu: klik atom di viewport atau pilih residu di panel Hierarki "
                            "(Ctrl+klik untuk beberapa residu).")
                return
            c = [sum(p[i] for p in xs) / len(xs) for i in range(3)]
            self._atur_kotak(c, sumber=f"pusat {len(res)} residu terpilih")
        elif k == "sesuai":
            o = self.objek.get(self.aktif)
            if not o or o.jenis not in ("ligan", "pose"):
                self._galat("Pilih ligan di panel Hierarki dulu.")
                return
            self.box_ke_objek(o, tepi=8.0)
        elif k == "blind":
            o = next((x for x in self.objek.values() if x.jenis == "protein" and x.info.get("siap_docking")), None) \
                or next((x for x in self.objek.values() if x.jenis == "protein"), None)
            if not o:
                self._galat("Belum ada protein.")
                return
            xs = self._koordinat(o)
            c = [(max(p[i] for p in xs) + min(p[i] for p in xs)) / 2 for i in range(3)]
            uk = [max(p[i] for p in xs) - min(p[i] for p in xs) + 10 for i in range(3)]
            import math
            sp = max(0.375, math.ceil(max(uk) / 126 * 1000) / 1000)
            self._atur_kotak(c, uk, sp, sumber=f"blind docking seluruh {o.nama} (spasi {sp} Å)")
            if sp > 0.375:
                self.pesan.tulis(f"Blind docking: spasi grid dinaikkan ke {sp} Å agar ≤ 126 titik per sumbu. "
                                 "Untuk hasil lebih teliti gunakan Vina dengan exhaustiveness ≥ 32.")

    def _kotak_dari_panel(self, k):
        self.box.update(pusat=k["pusat"], ukuran=k["ukuran"], spasi=k["spasi"])
        self._gambar_box()
        self._simpan_kotak()

    def _kotak_dari_viewer(self, k):
        self.box.update(pusat=k["pusat"], ukuran=k["ukuran"])
        self.param.set_kotak(self.box)
        self._simpan_kotak()

    def _simpan_kotak(self):
        if self.proyek and self.box["pusat"]:
            self.proyek.kotak = {"pusat": self.box["pusat"], "ukuran": self.box["ukuran"],
                                 "spasi": self.box.get("spasi", 0.375)}
            self.minta_simpan()

    def toggle_box(self, on):
        self.box["tampil"] = on
        self.param.c_tampil.blockSignals(True)
        self.param.c_tampil.setChecked(on)
        self.param.c_tampil.blockSignals(False)
        self._gambar_box()

    def _gambar_box(self):
        self.viewer.js("box", self.box["pusat"], self.box["ukuran"], self.box["tampil"], theme.TOKEN[self.mode]["acc"])

    # -------------------------------------------------------------- proyek
    def _pastikan_proyek(self):
        if self.proyek:
            return self.proyek
        induk = Path(self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))
        induk.mkdir(parents=True, exist_ok=True)
        dasar = next((o.nama for o in self.objek.values() if o.jenis == "protein"), "Proyek")
        from datetime import datetime
        self._set_proyek(Proyek.baru(induk, f"{dasar}_{datetime.now():%Y%m%d_%H%M}"))
        self._simpan_kotak()
        self.log.tulis(f"Proyek dibuat otomatis: {self.proyek.folder}")
        return self.proyek

    def _set_proyek(self, pr):
        self.proyek = pr
        self.pelaksana.atur_proyek(pr)
        self.setWindowTitle(f"{pr.nama} — VirmoDock" if pr else "VirmoDock")
        self.s_folder.setText(str(pr.folder) if pr else self.st.value("folder_kerja", ""))
        if pr:
            self.st.setValue("proyek_terakhir", str(pr.folder))
            self.st.setValue("sesi_terbuka", str(pr.folder))
        self.antrean.muat(pr.job if pr else [])
        self._muat_hasil()
        self._ringkasan()

    def _ringkasan(self):
        pr = self.proyek
        rec = None
        if pr and pr.reseptor:
            rec = f"{pr.reseptor.get('nama', '')} · {pr.reseptor.get('atom', 0)} atom"
        lig = pr.ligan_siap() if pr else []
        self.param.set_ringkasan(rec, len(lig), sum(1 for l in lig if l.get("status") == "peringatan"))

    def minta_simpan(self):
        if self.proyek:
            self.t_simpan.start()

    def _simpan_diam(self):
        if not self.proyek:
            return
        try:
            self.proyek.simpan_objek(list(self.objek.values()))
            self.proyek.parameter = self.param.parameter()
            self.proyek.simpan()
        except OSError as e:
            self.pesan.tulis(f"Gagal menyimpan proyek: {e}")

    def simpan(self):
        if not self.proyek:
            nama, ok = QInputDialog.getText(self, "Simpan proyek", "Nama proyek:",
                                            text=next((o.nama for o in self.objek.values() if o.jenis == "protein"),
                                                      "Proyek"))
            if not ok or not nama.strip():
                return
            induk = Path(self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))
            induk.mkdir(parents=True, exist_ok=True)
            self._set_proyek(Proyek.baru(induk, nama.strip()))
            self._simpan_kotak()
        self._simpan_diam()
        self.statusBar().showMessage(f"Proyek disimpan: {self.proyek.folder}", 4000)
        self.log.tulis(f"Proyek disimpan: {self.proyek.folder}")

    def proyek_baru(self):
        if self.pelaksana.sibuk() and QMessageBox.question(
                self, "Proyek baru", "Docking sedang berjalan. Job akan dijeda dan bisa dilanjutkan saat proyek "
                                     "ini dibuka lagi. Lanjutkan?") != QMessageBox.Yes:
            return
        nama, ok = QInputDialog.getText(self, "Proyek baru", "Nama proyek:")
        if not ok:
            return
        self.pelaksana.hentikan_semua()
        self._simpan_diam()
        self._tutup_sesi()
        if nama.strip():
            induk = Path(self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))
            induk.mkdir(parents=True, exist_ok=True)
            self._set_proyek(Proyek.baru(induk, nama.strip()))
            self.log.tulis(f"Proyek baru: {self.proyek.folder}")

    def _tutup_sesi(self):
        self.proyek = None
        self.pelaksana.atur_proyek(None)
        for oid in list(self.objek):
            self.hapus_objek(oid)
        self.hier.kosongkan()
        self.viewer.js("clear")
        self.box.update(pusat=None, ukuran=[22.5, 22.5, 22.5], spasi=0.375)
        self.antrean.muat([])
        self.hasil.muat([])
        self._aktif_inter = None
        self._cache_mol, self._cache_rec = {}, {}
        self.p_inter.kosong()
        self.diagram.tampil("", theme.TOKEN[self.mode]["surf"])
        self.setWindowTitle("VirmoDock")
        self._ringkasan()

    def buka_proyek(self, folder=None):
        if not folder:
            folder = QFileDialog.getExistingDirectory(self, "Buka proyek (.vmd)",
                                                      self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))
        if not folder:
            return
        try:
            pr = Proyek.buka(folder)
        except Exception as e:
            QMessageBox.warning(self, "Buka proyek", str(e))
            return
        self.pelaksana.hentikan_semua()
        self._simpan_diam()
        self._tutup_sesi()
        objek, _ = pr.muat_objek()
        if pr.kotak:
            self.box.update(pusat=pr.kotak["pusat"], ukuran=pr.kotak["ukuran"], spasi=pr.kotak.get("spasi", 0.375))
        self._set_proyek(pr)
        self.tambah_objek(objek)
        self.param.set_kotak(self.box)
        self._gambar_box()
        if pr.parameter:
            self.param.set_parameter(pr.parameter)
            self._param_berubah(self.param.parameter())
        self._isi_kristal()
        if any(l["status"] == "selesai" and "le" not in l for j in pr.job for l in j["ligan"]):
            self.analisis_ulang()
        dijeda = [j for j in pr.job if j["status"] == "dijeda"]
        self.log.tulis(f"Proyek dibuka: {pr.folder} · {len(objek)} objek · {len(pr.ligan_siap())} ligan siap · "
                       f"{len(pr.job)} job")
        if dijeda:
            self.pesan.tulis(f"{len(dijeda)} job terputus berstatus 'Dijeda'. Pilih job di panel Antrean lalu "
                             "klik Lanjut; ligan yang sudah selesai tidak diulang.")
            self.d_antre.raise_()

    def _cek_pemulihan(self):
        """E1: sesi sebelumnya tidak ditutup normal -> tawarkan pemulihan."""
        f = self.st.value("sesi_terbuka", "")
        if f and Path(f, "proyek.json").exists() and not self.proyek:
            if QMessageBox.question(self, "Pulihkan pekerjaan",
                                    f"VirmoDock tidak ditutup dengan normal sebelumnya.\n\nPulihkan proyek terakhir?\n{f}"
                                    ) == QMessageBox.Yes:
                self.buka_proyek(f)
                return
        self.st.remove("sesi_terbuka")

    # --------------------------------------------------------- preparasi
    def _logam_dari(self, o):
        nama = []
        for x in self.objek.values():
            if x.jenis == "ion" and x.sumber == o.sumber:
                for b in x.teks.splitlines():
                    if b.startswith("HETATM") and b[17:20].strip().upper() in prep_reseptor.LOGAM:
                        nama.append(f"{b[17:20].strip()} {b[21]}{b[22:26].strip()}")
        return nama

    def siapkan_reseptor(self):
        protein = [o for o in self.objek.values() if o.jenis == "protein" and not o.info.get("siap_docking")]
        if not protein:
            self._galat("Belum ada protein. Impor struktur dulu (File › Buka atau Impor dari RCSB PDB).")
            return
        d = DialogReseptor(protein, {o.id: self._logam_dari(o) for o in protein}, self, self.aktif)
        if not d.exec():
            return
        o, opsi = d.objek(), d.opsi()
        # gabungkan kembali protein + ion + ligan asli dari sumber yang sama (untuk radius ion logam)
        bagian = [o.teks] + [x.teks for x in self.objek.values()
                             if x.sumber == o.sumber and x.id != o.id and x.fmt == "pdb"
                             and (x.jenis == "ion" or (x.jenis == "ligan" and x.info.get("ligan_asli")))]
        teks = "\n".join(b for t in bagian for b in t.splitlines()
                         if b.startswith(("ATOM", "HETATM", "TER", "CRYST1"))) + "\nEND\n"
        self.statusBar().showMessage("Menyiapkan reseptor…", 4000)
        self.s_prog.setText("Preparasi reseptor…")
        kerja.jalankan(prep_reseptor.siapkan, teks, opsi, selesai=lambda h: self._reseptor_siap(o, h, opsi),
                       galat=lambda g: (self._galat("Preparasi reseptor gagal:\n" + g), self.s_prog.setText("")),
                       log=self.log.tulis)

    def _reseptor_siap(self, asal, h, opsi):
        pr = self._pastikan_proyek()
        pr.siapkan_folder()
        pr.p("reseptor", "asli.pdb").write_text(asal.teks, encoding="utf-8")
        pr.p("reseptor", "bersih.pdb").write_text(h.pdb_bersih, encoding="utf-8")
        pr.p("reseptor", "reseptor.pdbqt").write_text(h.pdbqt, encoding="utf-8")
        pr.p("reseptor", "laporan_prep.txt").write_text(h.laporan, encoding="utf-8")
        pr.reseptor = {"nama": asal.nama, "sumber": asal.sumber, "pdbqt": "reseptor/reseptor.pdbqt",
                       "bersih": "reseptor/bersih.pdb", "asli": "reseptor/asli.pdb", "metode": h.metode,
                       "atom": h.atom, "residu": h.residu, "dibuang": h.dibuang, "logam": h.logam,
                       "opsi": vars(opsi)}
        for x in [x for x in self.objek.values() if x.jenis == "protein" and x.info.get("siap_docking")]:
            self.hapus_objek(x.id)
        teks = prep_reseptor.pdbqt_ke_pdb(h.pdbqt)
        import gemmi
        o = molekul.Objek(nama=f"{asal.nama} (siap)", jenis="protein", teks=teks, sumber=asal.sumber)
        o.rantai = molekul._hierarki(gemmi.read_pdb_string(teks))
        o.info = {"atom": h.atom, "residu": h.residu, "rantai": len(o.rantai), "siap_docking": True,
                  "metode": h.metode}
        o.gaya = dict(asal.gaya)
        asal.tampil = False
        self.hier.set_centang(asal.id, False)
        self.viewer.tampil(asal, molekul.spek_viewer(asal))
        self.tambah_objek([o], fokus=False)
        self.hier.pilih_objek(o.id)
        self.s_prog.setText("")
        self.log.tulis(f"Reseptor siap: {h.atom} atom, {h.residu} residu, {h.metode} → {pr.p('reseptor', 'reseptor.pdbqt')}")
        for p in h.peringatan:
            self.pesan.tulis("Reseptor: " + p)
        if h.peringatan:
            self.d_pesan.raise_()
        self._ringkasan()
        self.minta_simpan()

    def siapkan_ligan(self):
        calon = [o for o in self.objek.values() if o.jenis == "ligan" and not o.info.get("siap_docking")]
        d = DialogLigan(calon, self.mode, self)
        d.siap.connect(self._ligan_siap)
        d.exec()

    def _ligan_siap(self, daftar):
        pr = self._pastikan_proyek()
        pr.siapkan_folder()
        baru = []
        for asal, h in daftar:
            lid = pr.id_ligan_baru(h.nama)
            pr.p("ligan", "sumber", f"{lid}.sdf").write_text(h.sdf, encoding="utf-8")
            pr.p("ligan", "pdbqt", f"{lid}.pdbqt").write_text(h.pdbqt, encoding="utf-8")
            info = h.ke_dict()
            info.update(id=lid, sumber=asal.sumber, sdf=f"ligan/sumber/{lid}.sdf", pdbqt=f"ligan/pdbqt/{lid}.pdbqt",
                        ligan_asli=bool(asal.info.get("ligan_asli")))
            if asal.info.get("ligan_asli") and asal.fmt == "pdb":  # acuan RMSD redocking
                pr.p("ligan", "sumber", f"{lid}_kristal.pdb").write_text(asal.teks, encoding="utf-8")
                info["kristal"] = f"ligan/sumber/{lid}_kristal.pdb"
            pr.ligan.append(info)
            o = molekul.Objek(nama=h.nama, jenis="ligan", teks=h.sdf, fmt="sdf", sumber=asal.sumber, grup=GRUP_LIGAN)
            o.tampil = False
            o.info = {"rumus": h.rumus, "mw": h.mw, "torsi": h.torsi, "atom": h.atom, "siap_docking": True,
                      "lid": lid, "status": h.status, "keterangan": h.alasan,
                      "ligan_asli": bool(asal.info.get("ligan_asli"))}
            baru.append(o)
        self.tambah_objek(baru, fokus=False)
        self.log.tulis(f"{len(baru)} ligan siap docking disimpan di {pr.p('ligan', 'pdbqt')}")
        self._ringkasan()
        self.minta_simpan()

    # ------------------------------------------------------------ docking
    def _param_berubah(self, p):
        if self._sinkron:
            return
        self._sinkron = True
        self.cmb_mesin.setCurrentIndex(MESIN_URUT.index(p["mesin"]))
        i = self.cmb_alat.findData(p["perangkat"])
        if i >= 0:
            self.cmb_alat.setCurrentIndex(i)
        self._sinkron = False
        if self.proyek:
            self.proyek.parameter = p
            self.minta_simpan()

    def _toolbar_mesin(self, _i):
        if not self._sinkron:
            self._sinkron = True
            self.param.set_parameter({"mesin": self.cmb_mesin.currentData()})
            self._sinkron = False
            self._param_berubah(self.param.parameter())

    def _toolbar_alat(self, _i):
        if not self._sinkron and self.cmb_alat.currentData():
            self._sinkron = True
            self.param.set_parameter({"perangkat": self.cmb_alat.currentData()})
            self._sinkron = False
            self._param_berubah(self.param.parameter())

    def _ligan_terpilih(self):
        lid = []
        for it in self.hier.pohon.selectedItems():
            d = it.data(0, Qt.UserRole)
            if d and d[0] == "obj" and d[1] in self.objek and self.objek[d[1]].info.get("lid"):
                lid.append(self.objek[d[1]].info["lid"])
        return lid

    def jalankan_docking(self):
        pr = self.proyek
        if not pr or not pr.reseptor or not pr.p(pr.reseptor["pdbqt"]).exists():
            self._galat("Reseptor belum disiapkan. Jalankan Prepare › Siapkan reseptor dulu.")
            return
        siap = pr.ligan_siap()
        if not siap:
            self._galat("Belum ada ligan siap docking. Jalankan Prepare › Siapkan ligan dulu.")
            return
        if not self.box["pusat"]:
            self._galat("Grid box belum diatur. Gunakan tombol di panel Parameter (mis. 'Pusat ke ligan asli').")
            self.d_param.raise_()
            return
        pilih = set(self._ligan_terpilih())
        ligan = [l for l in siap if l["id"] in pilih] if pilih else siap
        p = self.param.parameter()
        mesin, alat = p["mesin"], p["perangkat"]
        if mesin == "adgpu" and (alat != "gpu" or not (self.env and self.env.opencl_ok)):
            mesin, alat = "vina", "cpu"
            self.pesan.tulis("AutoDock-GPU membutuhkan GPU dengan OpenCL; job dijalankan dengan AutoDock Vina (CPU).")
        if not mesinmod.tersedia(mesin):
            self._galat(f"{mesinmod.PROGRAM[mesin]} tidak ditemukan di folder bin. Pasang ulang VirmoDock.")
            return
        k = mesinmod.Kotak(pusat=self.box["pusat"], ukuran=self.box["ukuran"], spasi=self.box.get("spasi", 0.375))
        if mesin in ("adgpu", "ad4") and k.terpotong():
            if QMessageBox.question(self, "Grid box terlalu besar",
                                    "Grid box melebihi 126 titik per sumbu pada spasi ini sehingga AutoGrid akan "
                                    "memotongnya. Tetap jalankan?") != QMessageBox.Yes:
                return
        par = dict(p, nrun=p["nrun_gpu"] if mesin == "adgpu" else p["nrun_ad4"],
                   nev=p["nev_gpu"] if mesin == "adgpu" else p["nev_ad4"])
        job = antreanmod.job_baru(pr, ligan, mesin, alat, par, {"pusat": k.pusat, "ukuran": k.ukuran,
                                                                "spasi": k.spasi})
        self.pelaksana.tambah(job)
        self.d_antre.show()
        self.d_antre.raise_()

    def _hubungkan_pelaksana(self):
        pl = self.pelaksana
        pl.log.connect(self.log.tulis)
        pl.pesan.connect(self._galat)
        pl.perluSimpan.connect(self.minta_simpan)
        pl.jobBerubah.connect(self._job_berubah)
        pl.liganSelesai.connect(lambda jid, lid: self._muat_hasil())
        pl.jobSelesai.connect(self._job_selesai)

    def _job_berubah(self, jid):
        if not self.proyek:
            return
        j = self.pelaksana.cari(jid)
        if j:
            self.antrean.perbarui(j)
        else:
            self.antrean.muat(self.proyek.job)
        jalan = next((x for x in self.proyek.job if x["status"] == "berjalan"), None)
        if jalan:
            n = len(jalan["ligan"])
            k = sum(1 for l in jalan["ligan"] if l["status"] not in ("menunggu", "berjalan"))
            self.s_prog.setText(f"Docking {k}/{n} · {mesinmod.MESIN[jalan['mesin']]}")
        else:
            self.s_prog.setText("")

    def _job_selesai(self, jid):
        j = self.pelaksana.cari(jid)
        if not j:
            return
        self._muat_hasil()
        ok = [l for l in j["ligan"] if l["status"] == "selesai"]
        if j.get("validasi") and j["status"] == "selesai":
            QTimer.singleShot(200, lambda: self._hasil_validasi(j))
        if j["status"] == "selesai":
            terbaik = min(ok, key=lambda l: l["energi"])
            judul = "Docking selesai"
            isi = f"{len(ok)}/{len(j['ligan'])} ligan · terbaik {terbaik['nama']} {terbaik['energi']:.2f} kcal/mol"
            self.tab_tengah.setCurrentWidget(self.hasil)
        elif j["status"] == "dibatalkan":
            judul, isi = "Docking dibatalkan", f"{j['id']} · {len(ok)} ligan sempat selesai"
        else:
            judul = "Docking gagal"
            alasan = "; ".join(j.get("catatan") or []) or next((l["pesan"] for l in j["ligan"] if l.get("pesan")), "")
            isi = f"{j['id']}: {alasan[:180]}"
            self.pesan.tulis(f"{judul} — {isi}")
        self.notifikasi(judul, isi, gagal=j["status"] == "gagal")
        self._simpan_diam()

    def aksi_antrean(self, aksi, jid):
        pl = self.pelaksana
        if aksi == "jeda":
            pl.jeda(jid)
        elif aksi == "lanjut":
            pl.lanjut(jid)
        elif aksi == "batal":
            j = pl.cari(jid)
            if j and QMessageBox.question(self, "Batalkan job", f"Batalkan job {jid}? Ligan yang sudah selesai "
                                                                "tetap tersimpan.") == QMessageBox.Yes:
                pl.batal(jid)
        elif aksi == "hapus_selesai":
            pl.hapus_selesai()
            self.antrean.muat(self.proyek.job if self.proyek else [])
        elif aksi == "ulang":
            pl.lanjut(jid)
        elif aksi in ("folder", "log") and self.proyek and jid:
            f = self.proyek.p("hasil", jid)
            if aksi == "log":
                _j, lid = self.antrean.ligan_terpilih()
                if lid and (f / "log" / f"{lid}.log").exists():
                    f = f / "log" / f"{lid}.log"
                else:
                    f = f / "log"
            if f.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(f)))

    def buka_pose(self, jid, lid, k=1, maks=9):
        """Muat pose hasil satu ligan sebagai objek di grup 'Hasil · <ligan>'; pose k ditampilkan & dipilih."""
        pr = self.proyek
        j = self.pelaksana.cari(jid)
        l = next((x for x in j["ligan"] if x["id"] == lid), None) if j else None
        if not l or not l.get("keluaran") or not pr.p(l["keluaran"]).exists():
            self._galat("Berkas hasil tidak ditemukan.")
            return None
        grup = f"Hasil · {l['nama']} · {jid[-6:]}"
        # grup hasil lain disembunyikan agar viewport bersih (tidak dihapus)
        for o in self.objek.values():
            if o.jenis == "pose" and o.grup != grup and o.tampil:
                self.set_tampil(o.id, False)
                self.hier.set_centang(o.id, False)
        lama = [o for o in self.objek.values() if o.grup == grup]
        if lama and any("pdbqt" not in o.info for o in lama):  # pose dari versi lama: muat ulang lengkap
            for o in lama:
                self.hapus_objek(o.id)
            lama = []
        if not lama:
            pose = mesinmod.baca_hasil(j["mesin"], pr.p(l["keluaran"]))[:max(maks, k)]
            simpan = {p["peringkat"]: p for p in l.get("pose", [])}
            for p in pose:
                o = molekul.Objek(nama=f"Pose {p.peringkat}", jenis="pose", teks=mesinmod.pose_ke_pdb(p.pdbqt),
                                  grup=grup, sumber=f"{jid}/{lid}")
                o.tampil = False
                o.info = {"energi": p.energi, "ki": p.ki, "rmsd_lb": p.rmsd_lb, "rmsd_ub": p.rmsd_ub,
                          "rmsd_ref": p.rmsd_ref, "klaster": p.klaster, "ligan": l["nama"], "job": jid, "lid": lid,
                          "peringkat": p.peringkat, "mesin": mesinmod.MESIN[j["mesin"]], "pdbqt": p.pdbqt,
                          "lig_pdbqt": l["pdbqt"], "atom": len(o.teks.splitlines()) - 1,
                          "rmsd_kristal": simpan.get(p.peringkat, {}).get("rmsd_kristal")}
                lama.append(o)
            self.tambah_objek(lama, fokus=False)
        sasaran = next((o for o in lama if o.info.get("peringkat") == k), lama[0] if lama else None)
        for o in lama:
            on = o is sasaran
            if o.tampil != on:
                self.set_tampil(o.id, on)
                self.hier.set_centang(o.id, on)
        if sasaran:
            self.viewer.js("fokus", {"id": sasaran.id})
            self.hier.pilih_objek(sasaran.id)
            self.pilih_objek(sasaran.id)
        self.tab_tengah.setCurrentWidget(self.viewer)
        self.minta_simpan()
        return sasaran

    # ------------------------------------------------------------ analisis
    def _muat_hasil(self):
        self.hasil.muat(eksmod.baris_hasil(self.proyek) if self.proyek else [])

    def _reseptor_objek(self):
        siap = [o for o in self.objek.values() if o.jenis == "protein" and o.info.get("siap_docking")]
        lain = [o for o in self.objek.values() if o.jenis == "protein"]
        return (siap or lain or [None])[0]

    def _mol_objek(self, o):
        if o.jenis == "pose" and o.info.get("pdbqt") and self.proyek and o.info.get("lig_pdbqt"):
            f = self.proyek.p(o.info["lig_pdbqt"])
            if f.exists():
                return analisis.pose_mol(f.read_text(), o.info["pdbqt"])
        return analisis.mol_dari_objek(o)

    def analisis_objek(self, o):
        """Interaksi pose/ligan aktif -> panel Interaksi, viewport, diagram 2D."""
        rec = self._reseptor_objek()
        if rec is None or o.jenis not in ("pose", "ligan") or o.info.get("aditif"):
            return
        try:
            if o.id not in self._cache_mol:
                self._cache_mol[o.id] = self._mol_objek(o)
            if rec.id not in self._cache_rec:
                self._cache_rec = {rec.id: analisis.baca_reseptor(rec.teks)}
            mol = self._cache_mol[o.id]
            daftar = analisis.interaksi(self._cache_rec[rec.id], mol)
        except Exception as e:
            self.log.tulis(f"Analisis interaksi {o.nama} gagal: {e}")
            return
        self._aktif_inter = {"oid": o.id, "rec": rec.id, "daftar": daftar, "mol": mol,
                             "judul": f"{o.info.get('ligan', o.nama)}" + (f" · {o.nama}" if o.jenis == "pose" else "")
                             + (f" · {o.info['energi']:.2f} kcal/mol" if o.info.get("energi") is not None else "")}
        self.p_inter.muat(self._aktif_inter["judul"], daftar)
        self._tampilkan_interaksi()
        self._gambar_diagram()

    def _tampilkan_interaksi(self, *_):
        a = self._aktif_inter
        if not a:
            return
        if not self.a_inter.isChecked() or a["oid"] not in self.objek or not self.objek[a["oid"]].tampil:
            self.viewer.js("interaksi", [], {})
            self.viewer.js("residuKontak", a["rec"], None)
            return
        jenis = self.p_inter.jenis_tampil()
        d = [dict(h, warna=theme.INTERAKSI.get(h["jenis"], "#888888")) for h in a["daftar"] if h["jenis"] in jenis]
        self.viewer.js("interaksi", d, {"jarak": self.p_inter.c_jarak.isChecked(),
                                         "label": self.p_inter.c_label.isChecked()})
        res = {}
        for h in d:
            res.setdefault(h["rantai"] or " ", set()).add(h["resi"])
        sel = {"or": [{"chain": c.strip() or None, "resi": sorted(r)} if c.strip() else {"resi": sorted(r)}
                      for c, r in res.items()]} if res and self.p_inter.c_stick.isChecked() else None
        self.viewer.js("residuKontak", a["rec"], sel)

    def _fokus_interaksi(self, h):
        a = self._aktif_inter
        if a:
            sel = {"id": a["rec"], "resi": h["resi"]}
            if h["rantai"]:
                sel["chain"] = h["rantai"]
            self.viewer.js("fokus", sel)

    def _svg_diagram(self, vdw=True, jarak=True, transparan=False, judul=True, lebar=960, tinggi=720, gelap=None):
        a = self._aktif_inter
        if not a:
            return ""
        daftar = [h for h in a["daftar"] if vdw or h["jenis"] != "vdw"]
        return diagram2d.svg(a["mol"], daftar, lebar, tinggi, a["judul"] if judul else "",
                             gelap=(self.mode == "gelap") if gelap is None else gelap, transparan=transparan,
                             warna=theme.INTERAKSI, jarak=jarak)

    def _gambar_diagram(self):
        try:
            s = self._svg_diagram(self.diagram.c_vdw.isChecked(), self.diagram.c_jarak.isChecked())
        except Exception as e:
            self.log.tulis(f"Diagram 2D gagal: {e}")
            s = ""
        self.diagram.tampil(s, theme.TOKEN[self.mode]["surf"])

    def analisis_ulang(self):
        if not self.proyek:
            return
        self.s_prog.setText("Menganalisis hasil…")
        kerja.jalankan(analisis.analisis_ulang, self.proyek, log=self.log.tulis,
                       selesai=lambda n: (self.s_prog.setText(""), self._muat_hasil(), self.minta_simpan(),
                                          n and self.log.tulis(f"Analisis dilengkapi untuk {n} ligan.")),
                       galat=self._galat)

    def _isi_kristal(self):
        """Proyek lama: simpan koordinat ligan kristal untuk RMSD redocking."""
        pr = self.proyek
        for l in pr.ligan:
            if l.get("ligan_asli") and not l.get("kristal"):
                o = next((x for x in self.objek.values() if x.nama == l["nama"] and x.fmt == "pdb"
                          and x.info.get("ligan_asli")), None)
                if o:
                    pr.p("ligan", "sumber", f"{l['id']}_kristal.pdb").write_text(o.teks, encoding="utf-8")
                    l["kristal"] = f"ligan/sumber/{l['id']}_kristal.pdb"

    # ------------------------------------------------------------ validasi
    def validasi_redocking(self):
        pr = self.proyek
        if not pr or not pr.reseptor:
            self._galat("Siapkan reseptor dulu (Prepare › Siapkan reseptor).")
            return
        asli = [o for o in self.objek.values() if o.jenis == "ligan" and o.fmt == "pdb" and o.info.get("ligan_asli")]
        if not asli:
            self._galat("Tidak ada ligan asli kristal di sesi ini. Validasi redocking membutuhkan struktur PDB "
                        "yang berisi ligan (mis. 1HSG dengan MK1).")
            return
        o = asli[0]
        if len(asli) > 1:
            nama, ok = QInputDialog.getItem(self, "Validasi redocking", "Ligan kristal:", [x.nama for x in asli], 0, False)
            if not ok:
                return
            o = next(x for x in asli if x.nama == nama)
        if not self.box["pusat"]:
            self.box_ke_objek(o)
        # ligan validasi disiapkan dari konformasi kristal TANPA minimisasi: cincin kaku tetap seperti kristal
        # (minimisasi MMFF mengubah konformasi cincin dan bisa membuat redocking gagal walau metodenya benar)
        nama_val = f"{o.nama} (kristal)"
        lig = next((l for l in pr.ligan if l.get("kristal") and l["nama"] == nama_val
                    and l.get("status") in ("siap", "peringatan")), None)
        if lig:
            self._jalankan_validasi(o, lig)
            return
        from ..core import prep_ligan
        self.s_prog.setText("Menyiapkan ligan kristal…")

        def selesai(h):
            self.s_prog.setText("")
            if h[0].status == "gagal":
                self._galat(f"Ligan kristal gagal disiapkan: {h[0].alasan}")
                return
            self._ligan_siap([(o, h[0])])
            l2 = next((l for l in reversed(pr.ligan) if l.get("kristal") and l["nama"] == nama_val), None)
            if l2:
                self._jalankan_validasi(o, l2)
        kerja.jalankan(prep_ligan.siapkan_banyak, [(nama_val, o.teks, "pdb")], prep_ligan.OpsiLigan(minimisasi=False),
                       selesai=selesai, galat=self._galat)

    def _jalankan_validasi(self, o, lig):
        p = self.param.parameter()
        mesin, alat = p["mesin"], p["perangkat"]
        if mesin == "adgpu" and (alat != "gpu" or not (self.env and self.env.opencl_ok)):
            mesin, alat = "vina", "cpu"
        par = dict(p, nrun=p["nrun_gpu"] if mesin == "adgpu" else p["nrun_ad4"],
                   nev=p["nev_gpu"] if mesin == "adgpu" else p["nev_ad4"])
        k = {"pusat": self.box["pusat"], "ukuran": self.box["ukuran"], "spasi": self.box.get("spasi", 0.375)}
        job = antreanmod.job_baru(self.proyek, [lig], mesin, alat, par, k,
                                  nama=f"Validasi redocking · {o.nama}")
        job["validasi"] = True
        job["kristal_objek"] = o.nama
        self.pelaksana.tambah(job)
        self.log.tulis(f"Validasi redocking dimulai: {o.nama} dengan {mesinmod.MESIN[mesin]}")
        self.d_antre.raise_()

    def _hasil_validasi(self, j):
        l = j["ligan"][0]
        if l["status"] != "selesai" or l.get("rmsd_kristal") is None:
            self._galat("Validasi redocking gagal: RMSD terhadap kristal tidak bisa dihitung.")
            return
        r = l["rmsd_kristal"]
        self.proyek.validasi = {"ligan": l["nama"], "job": j["id"], "mesin": mesinmod.MESIN[j["mesin"]],
                                "rmsd": r, "rmsd_min": l.get("rmsd_kristal_min"), "energi": l["energi"],
                                "tanggal": j.get("selesai")}
        ok = r <= 2.0
        teks = (f"RMSD pose terbaik terhadap kristal: {r:.2f} Å — {'VALID (≤ 2,0 Å)' if ok else 'TIDAK VALID (> 2,0 Å)'}\n"
                f"RMSD minimum di antara pose teratas: {l.get('rmsd_kristal_min', r):.2f} Å\n"
                f"ΔG pose terbaik: {l['energi']:.2f} kcal/mol ({mesinmod.MESIN[j['mesin']]})")
        self.pesan.tulis("Validasi redocking — " + teks.replace("\n", "; "))
        # tumpang-tindih: kristal karbon magenta, pose karbon biru (residu kontak abu-abu)
        pose = self.buka_pose(j["id"], l["id"], 1)
        kr = next((o for o in self.objek.values() if o.fmt == "pdb" and o.info.get("ligan_asli")
                   and o.nama == j.get("kristal_objek")), None)
        if kr:
            g = dict(kr.gaya, reps=["sticks"], warna={"mode": "element", "carbon": "#c25bb5"})
            self.ubah_gaya(kr.id, g)
            self.set_tampil(kr.id, True)
            self.hier.set_centang(kr.id, True)
        if pose:
            self.ubah_gaya(pose.id, dict(pose.gaya, reps=["sticks"], warna={"mode": "element", "carbon": "#2b6fd6"}))
        self.minta_simpan()
        QMessageBox.information(self, "Validasi redocking", teks + "\n\nViewport: kristal (karbon magenta) vs pose "
                                                                  "terbaik (karbon biru).")

    # ------------------------------------------------------------ banding
    def bandingkan(self, pilih):
        pr = self.proyek
        rec = self._reseptor_objek()
        if not pr or rec is None:
            return
        if self.banding is None:
            self.banding = TabBanding()
            self.banding.peta.mode = self.mode
            self.banding.samakan.connect(self._samakan_pandang)
            self.tab_tengah.addTab(self.banding, "Bandingkan")
        viewer = self.banding.siapkan(len(pilih))
        baris = []
        t = theme.TOKEN[self.mode]
        for i, (jid, lid) in enumerate(pilih):
            j = self.pelaksana.cari(jid)
            l = next(x for x in j["ligan"] if x["id"] == lid)
            p = mesinmod.baca_hasil(j["mesin"], pr.p(l["keluaran"]))[0]
            mol = analisis.pose_mol(pr.p(l["pdbqt"]).read_text(), p.pdbqt)
            daftar = analisis.interaksi(analisis.baca_reseptor(rec.teks), mol)
            v = viewer[i]
            v.js("clear")
            v.js("tema", self.mode == "gelap", t["view"])
            r = molekul.Objek(nama="rec", jenis="protein", teks=rec.teks, id=f"b{i}r")
            r.gaya = {"reps": ["cartoon"], "warna": {"mode": "solid", "val": "#c9d1dc" if self.mode == "terang"
                                                      else "#4a5363"}, "opacity": 0.85, "permukaan": None, "khusus": []}
            po = molekul.Objek(nama="pose", jenis="pose", teks=mesinmod.pose_ke_pdb(p.pdbqt), id=f"b{i}p")
            po.gaya = {"reps": ["sticks"], "warna": {"mode": "element", "carbon": molekul.WARNA_KARBON[i]},
                       "opacity": 1.0, "permukaan": None, "khusus": []}
            for o in (r, po):
                v.muat(o)
                v.tampil(o, molekul.spek_viewer(o))
            d = [dict(h, warna=theme.INTERAKSI.get(h["jenis"], "#888")) for h in daftar if h["jenis"] != "vdw"]
            v.js("interaksi", d, {"jarak": False, "label": True})
            res = {}
            for h in d:
                res.setdefault(h["rantai"], set()).add(h["resi"])
            if res:
                v.js("residuKontak", r.id, {"or": [dict({"resi": sorted(x)}, **({"chain": c} if c else {}))
                                                   for c, x in res.items()]})
            v.js("fokus", {"id": po.id}, 0)
            self.banding.label[i].setText(f"{l['nama']} · {p.energi:.2f} kcal/mol · {mesinmod.MESIN[j['mesin']]}")
            pendek = {"adgpu": "AD-GPU", "vina": "Vina", "ad4": "AD4"}[j["mesin"]]
            baris.append((f"{l['nama']} · {pendek}", p.energi, analisis.residu_kontak(daftar)))
        semua = self.banding.peta.muat(baris)
        bersama = [r for r in semua if all(r in b[2] and b[2][r] != "vdw" for b in baris)]
        self.banding.l_info.setText("   Residu berinteraksi dengan semua ligan: " + (", ".join(bersama) or "–"))
        self.tab_tengah.setCurrentWidget(self.banding)

    def peta_interaksi(self):
        if not self.proyek:
            return
        if self.banding is None:
            self.banding = TabBanding()
            self.banding.samakan.connect(self._samakan_pandang)
            self.tab_tengah.addTab(self.banding, "Bandingkan")
        self.banding.peta.mode = self.mode
        self.banding.siapkan(0)
        baris = [(f"{b['ligan']} · {b['mesin'].replace('AutoDock-GPU', 'AD-GPU').replace('AutoDock ', '')}",
                  b["energi"], b["residu"]) for b in eksmod.baris_hasil(self.proyek) if b["residu"]][:200]
        if not baris:
            self._galat("Belum ada data interaksi. Jalankan Analyze › Hitung ulang analisis hasil.")
            return
        semua = self.banding.peta.muat(baris)
        frek = {r: sum(1 for b in baris if b[2].get(r) and b[2][r] != "vdw") for r in semua}
        top = sorted(frek, key=frek.get, reverse=True)[:8]
        self.banding.l_info.setText(f"   {len(baris)} ligan · residu tersering: "
                                    + ", ".join(f"{r} ({frek[r]})" for r in top))
        self.tab_tengah.setCurrentWidget(self.banding)

    def _samakan_pandang(self):
        def atur(v):
            for x in self.banding.viewer:
                x.js("aturLihat", v)
        self.viewer.js("lihat", cb=atur)

    # -------------------------------------------------------------- ekspor
    def buka_ekspor(self, kategori=0):
        ada_pose = bool(self._aktif_inter and self.objek.get(self._aktif_inter["oid"]) and
                        self.objek[self._aktif_inter["oid"]].jenis == "pose")
        d = DialogEkspor((self.viewer.width(), self.viewer.height()), ada_pose, self, kategori)
        d.minta.connect(self._ekspor)
        d.exec()

    def _nama_dasar(self):
        a = self._aktif_inter
        o = self.objek.get(a["oid"]) if a else None
        if o and o.jenis == "pose":
            return nama_aman(f"{o.info.get('ligan', 'ligan')}_pose{o.info.get('peringkat', 1)}")
        return nama_aman(o.nama) if o else (nama_aman(self.proyek.nama) if self.proyek else "virmodock")

    def _path(self, judul, nama, filter_):
        awal = str(self.proyek.p("ekspor", nama)) if self.proyek else nama
        if self.proyek:
            self.proyek.p("ekspor").mkdir(exist_ok=True)
        f, _ = QFileDialog.getSaveFileName(self, judul, awal, filter_)
        return f

    def _ekspor(self, d):
        try:
            getattr(self, "_ekspor_" + d["jenis"])(d)
        except Exception as e:
            import traceback
            self._galat(f"Ekspor gagal: {e}\n{traceback.format_exc(limit=3)}")

    def _ekspor_gambar3d(self, d):
        fmt = d["fmt"]
        f = self._path("Simpan gambar 3D", f"{self._nama_dasar()}_3d.{fmt}", f"Gambar (*.{fmt})")
        if not f:
            return
        t = theme.TOKEN[self.mode]
        latar = {"putih": "#ffffff", "hitam": "#000000", "tema": t["view"], "transparan": t["view"]}[d["latar"]]
        self.statusBar().showMessage(f"Merender {d['lebar']} × {d['tinggi']} px…")
        self.tab_tengah.setCurrentWidget(self.viewer)  # WebGL hanya merender benar bila viewport terlihat

        def simpan(url):
            import base64
            if not url or "," not in url:
                self._galat("Render gambar gagal (WebGL). Coba ukuran lebih kecil.")
                return
            data = base64.b64decode(url.split(",", 1)[1])
            uk = eksmod.simpan_gambar(data, f, d["dpi"], fmt, d.get("kompresi", "tiff_lzw"),
                                      latar=None if d["latar"] == "transparan" and fmt not in ("jpg",) else latar,
                                      ukuran=(d["lebar"], d["tinggi"]))
            self.statusBar().showMessage(f"Gambar disimpan: {f}", 5000)
            self.log.tulis(f"Gambar 3D {uk[0]}×{uk[1]} px @ {d['dpi']} dpi: {f}")
        QTimer.singleShot(250, lambda: self.viewer.js("gambar", d["lebar"], d["tinggi"], d["latar"] == "transparan",
                                                      latar, cb=simpan))

    def _ekspor_diagram(self, d):
        if not self._aktif_inter:
            self._galat("Pilih pose atau ligan dulu untuk diagram 2D.")
            return
        fmt = d["fmt"]
        f = self._path("Simpan diagram 2D", f"{self._nama_dasar()}_2d.{fmt}", f"Diagram (*.{fmt})")
        if f:
            self._simpan_diagram(f, fmt, d["mm"], d["dpi"], d["vdw"], d["transparan"], d["judul"])

    def _simpan_diagram(self, f, fmt, mm=120, dpi=600, vdw=True, transparan=False, judul=True):
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QRectF, QSizeF
        from PySide6.QtGui import QImage, QPageSize, QPainter, QPdfWriter
        from PySide6.QtSvg import QSvgRenderer
        s = self._svg_diagram(vdw, True, transparan, judul, gelap=False)
        lebar_px, tinggi_px = 960, 720
        if fmt == "svg":
            s = s.replace(f'width="{lebar_px}" height="{tinggi_px}"',
                          f'width="{mm:.1f}mm" height="{mm * tinggi_px / lebar_px:.1f}mm"', 1)
            Path(f).write_text(s, encoding="utf-8")
        else:
            r = QSvgRenderer(QByteArray(s.encode("utf-8")))
            if fmt == "pdf":
                w = QPdfWriter(f)
                w.setPageSize(QPageSize(QSizeF(mm, mm * tinggi_px / lebar_px), QPageSize.Millimeter))
                w.setPageMargins(QMarginsF(0, 0, 0, 0))
                w.setResolution(600)
                p = QPainter(w)
                r.render(p, QRectF(0, 0, w.width(), w.height()))
                p.end()
            else:
                px = eksmod.mm_ke_px(mm, dpi)
                img = QImage(px, int(px * tinggi_px / lebar_px), QImage.Format_ARGB32)
                img.fill(0)
                p = QPainter(img)
                p.setRenderHint(QPainter.Antialiasing)
                r.render(p)
                p.end()
                buf = QBuffer()
                buf.open(QIODevice.WriteOnly)
                img.save(buf, "PNG")
                eksmod.simpan_gambar(bytes(buf.data()), f, dpi, fmt, latar=None if transparan else "#ffffff")
        self.log.tulis(f"Diagram 2D disimpan: {f}")
        self.statusBar().showMessage(f"Diagram disimpan: {f}", 5000)

    def _diagram_cepat(self, fmt):
        if not self._aktif_inter:
            self._galat("Belum ada diagram.")
            return
        if fmt == "svg":
            f = self._path("Simpan diagram 2D", f"{self._nama_dasar()}_2d.svg", "SVG (*.svg)")
            if f:
                self._simpan_diagram(f, "svg")
        else:
            f = self._path("Simpan diagram 2D", f"{self._nama_dasar()}_2d.png", "PNG (*.png);;TIFF (*.tif)")
            if f:
                self._simpan_diagram(f, "tif" if f.lower().endswith((".tif", ".tiff")) else "png")

    def _tag_pose(self, b, p=None):
        p = p or (b["pose"][0] if b["pose"] else {})
        return {"Ligan": b["ligan"], "dG_kcal_mol": p.get("energi", b["energi"]), "Ki_perkiraan": b["ki"],
                "LE": b["le"], "Pose": p.get("peringkat", 1), "Klaster_n": p.get("klaster") or None,
                "RMSD_kristal_A": p.get("rmsd_kristal"), "Mesin": b["mesin"], "Job": b["job"],
                "Ikatan_H": b["hbond"], "Hidrofobik": b["hidrofobik"], "Pi": b["pi"] + b["pikation"],
                "SMILES": b["smiles"]}

    def _ekspor_struktur(self, d):
        pr = self.proyek
        isi = d["isi"]
        rec = self._reseptor_objek()
        if isi in ("kompleks", "sdf_pose", "pdbqt"):
            a = self._aktif_inter
            o = self.objek.get(a["oid"]) if a else None
            if not o or o.jenis != "pose":
                self._galat("Pilih pose dulu (klik dua kali baris di tab Hasil).")
                return
            if isi == "kompleks":
                f = self._path("Simpan kompleks", f"{self._nama_dasar()}_kompleks.pdb", "PDB (*.pdb)")
                if f:
                    rem = [f"Ligan {o.info.get('ligan')} pose {o.info.get('peringkat')} dG {o.info.get('energi'):.2f} "
                           f"kcal/mol ({o.info.get('mesin')}, job {o.info.get('job')})"]
                    Path(f).write_text(eksmod.kompleks_pdb(rec.teks, a["mol"], rem), encoding="utf-8")
                    self.log.tulis(f"Kompleks disimpan: {f}")
            elif isi == "pdbqt":
                f = self._path("Simpan pose PDBQT", f"{self._nama_dasar()}.pdbqt", "PDBQT (*.pdbqt)")
                if f:
                    rem = [b for b in pr.p(o.info["lig_pdbqt"]).read_text().splitlines() if b.startswith("REMARK")]
                    Path(f).write_text("\n".join(rem) + "\n" + o.info["pdbqt"] + "\n", encoding="utf-8")
            else:
                f = self._path("Simpan semua pose (SDF)", f"{nama_aman(o.info.get('ligan', 'ligan'))}_pose.sdf",
                               "SDF (*.sdf)")
                if f:
                    j = self.pelaksana.cari(o.info["job"])
                    l = next(x for x in j["ligan"] if x["id"] == o.info["lid"])
                    b = next(x for x in eksmod.baris_hasil(pr, [j]) if x["lid"] == l["id"])
                    teks_in = pr.p(l["pdbqt"]).read_text()
                    entri = []
                    for p, pd in zip(mesinmod.baca_hasil(j["mesin"], pr.p(l["keluaran"])), l["pose"]):
                        entri.append((analisis.pose_mol(teks_in, p.pdbqt), f"{l['nama']}_pose{p.peringkat}",
                                      self._tag_pose(b, pd)))
                    Path(f).write_text(eksmod.sdf_bertag(entri), encoding="utf-8")
                    self.log.tulis(f"{len(entri)} pose disimpan: {f}")
            return
        baris = eksmod.baris_hasil(pr)
        if not baris:
            self._galat("Belum ada hasil docking.")
            return
        if isi == "sdf_terbaik":
            f = self._path("Simpan pose terbaik (SDF)", f"{nama_aman(pr.nama)}_terbaik.sdf", "SDF (*.sdf)")
            if not f:
                return
        else:
            f = QFileDialog.getExistingDirectory(self, "Folder untuk kompleks PDB", str(pr.p("ekspor")))
            if not f:
                return
        rec_teks = rec.teks

        def kerjakan(lapor):
            entri = []
            for b in baris:
                j = self.pelaksana.cari(b["job"])
                l = next(x for x in j["ligan"] if x["id"] == b["lid"])
                p = mesinmod.baca_hasil(j["mesin"], pr.p(l["keluaran"]))[0]
                m = analisis.pose_mol(pr.p(l["pdbqt"]).read_text(), p.pdbqt)
                if isi == "sdf_terbaik":
                    entri.append((m, b["ligan"], self._tag_pose(b)))
                else:
                    rem = [f"Ligan {b['ligan']} pose 1 dG {b['energi']:.2f} kcal/mol ({b['mesin']}, job {b['job']})"]
                    Path(f, f"{b['peringkat']:03d}_{nama_aman(b['ligan'])}_kompleks.pdb").write_text(
                        eksmod.kompleks_pdb(rec_teks, m, rem), encoding="utf-8")
            if isi == "sdf_terbaik":
                Path(f).write_text(eksmod.sdf_bertag(entri), encoding="utf-8")
            return len(baris)
        kerja.jalankan(kerjakan, selesai=lambda n: self.log.tulis(f"Ekspor struktur: {n} ligan → {f}"),
                       galat=self._galat)

    def _ekspor_tabel(self, d):
        pr = self.proyek
        baris = eksmod.baris_hasil(pr) if pr else []
        if not baris:
            self._galat("Belum ada hasil docking.")
            return
        if d["fmt"] == "csv":
            f = self._path("Simpan tabel CSV", f"{nama_aman(pr.nama)}_hasil.csv", "CSV (*.csv)")
            if f:
                with open(f, "w", encoding="utf-8", newline="") as h:
                    h.write(eksmod.csv_teks(baris, d["sep"], d["koma"]))
                self.log.tulis(f"Tabel CSV disimpan: {f}")
            return
        f = self._path("Simpan tabel Excel", f"{nama_aman(pr.nama)}_hasil.xlsx", "Excel (*.xlsx)")
        if not f:
            return
        rec = self._reseptor_objek()
        info = {"Proyek": pr.nama, "Folder": str(pr.folder), "VirmoDock": VERSI,
                "Reseptor": (pr.reseptor or {}).get("nama"), "Metode reseptor": (pr.reseptor or {}).get("metode"),
                "Perangkat": self.s_gpu.text().lstrip("● ")}

        def kerjakan(lapor):
            inter = {}
            if d["interaksi"] and rec is not None:
                r = analisis.baca_reseptor(rec.teks)
                for b in baris:
                    j = self.pelaksana.cari(b["job"])
                    l = next(x for x in j["ligan"] if x["id"] == b["lid"])
                    p = mesinmod.baca_hasil(j["mesin"], pr.p(l["keluaran"]))[0]
                    inter[(b["ligan"], b["job"])] = analisis.interaksi(
                        r, analisis.pose_mol(pr.p(l["pdbqt"]).read_text(), p.pdbqt))
            eksmod.simpan_xlsx(f, pr, baris, inter, info)
            return f
        self.s_prog.setText("Menyusun Excel…")
        kerja.jalankan(kerjakan, selesai=lambda x: (self.s_prog.setText(""), self.log.tulis(f"Tabel Excel disimpan: {x}")),
                       galat=lambda g: (self.s_prog.setText(""), self._galat(g)))

    # ------------------------------------------------------------- laporan
    def _ekspor_laporan(self, d):
        pr = self.proyek
        if not pr or not pr.job:
            self._galat("Belum ada hasil docking untuk dilaporkan.")
            return
        f = self._path("Simpan laporan PDF", f"{nama_aman(pr.nama)}_laporan.pdf", "PDF (*.pdf)")
        if not f:
            return
        baris = eksmod.baris_hasil(pr)
        if not baris or not d["gambar"]:
            self._tulis_laporan(f, d, baris, None, None)
            return
        b = baris[0]
        self.buka_pose(b["job"], b["lid"], 1)
        self.statusBar().showMessage("Menyiapkan gambar laporan…")

        box_tampil = self.box["tampil"]
        self.box["tampil"] = False
        self._gambar_box()

        def ambil():
            def png(url):
                import base64
                self.box["tampil"] = box_tampil
                self._gambar_box()
                img3d = base64.b64decode(url.split(",", 1)[1]) if url and "," in url else None
                self._tulis_laporan(f, d, baris, img3d, self._svg_diagram(True, True, False, False, gelap=False))
            self.viewer.js("zoom", 0.8)  # setelah animasi fokus selesai
            QTimer.singleShot(300, lambda: self.viewer.js("gambar", 1600, 1200, False, "#ffffff", cb=png))
        QTimer.singleShot(1800, ambil)  # tunggu viewport menggambar pose & interaksi

    def _tulis_laporan(self, f, d, baris, img3d, svg2d):
        from PySide6.QtCore import QByteArray, QMarginsF
        from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument
        from PySide6.QtSvg import QSvgRenderer
        pr = self.proyek
        doc = QTextDocument()
        if img3d:
            doc.addResource(QTextDocument.ImageResource, QUrl("img3d"), QImage.fromData(img3d))
        if svg2d:
            r = QSvgRenderer(QByteArray(svg2d.encode("utf-8")))
            img = QImage(1600, 1200, QImage.Format_ARGB32)
            img.fill(0xffffffff)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            r.render(p)
            p.end()
            doc.addResource(QTextDocument.ImageResource, QUrl("img2d"), img)
        inter = self._aktif_inter["daftar"] if (self._aktif_inter and baris) else None
        info = {"versi": VERSI, "perangkat": self.s_gpu.text().lstrip("● ")}
        doc.setHtml(laporan.html(pr, baris, info, inter, bool(img3d), bool(svg2d), d.get("penulis", "")))
        w = QPdfWriter(f)
        w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(16, 14, 16, 14),
                                    QPageLayout.Millimeter))
        w.setResolution(150)
        w.setTitle(f"Laporan docking {pr.nama}")
        w.setCreator(f"VirmoDock {VERSI}")
        doc.setPageSize(w.pageLayout().paintRectPixels(150).size().toSizeF())
        doc.print_(w)
        self.statusBar().showMessage(f"Laporan disimpan: {f}", 6000)
        self.log.tulis(f"Laporan PDF disimpan: {f}")
        if not pr.validasi:
            self.pesan.tulis("Laporan dibuat tanpa validasi redocking. Jalankan Analyze › Validasi redocking agar "
                             "metode dapat dipertanggungjawabkan.")
        QDesktopServices.openUrl(QUrl.fromLocalFile(f))

    # -------------------------------------------------------------- tray
    def _tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        ik = QApplication.instance().windowIcon()
        if ik.isNull():
            ik = QIcon(icons.pixmap("logo", "#1f5fbf", 32))
        self.tray = QSystemTrayIcon(ik, self)
        self.tray.setToolTip("VirmoDock")
        self.tray.activated.connect(lambda *_: (self.showNormal(), self.raise_(), self.activateWindow()))
        self.tray.show()

    def notifikasi(self, judul, isi, gagal=False):
        self.log.tulis(f"{judul}: {isi}")
        if self.tray:
            self.tray.showMessage(judul, isi, QSystemTrayIcon.Warning if gagal else QSystemTrayIcon.Information, 8000)
        QApplication.alert(self)

    # ------------------------------------------------------------- lain
    def toggle_ukur(self, on):
        self.viewer.js("setMode", "ukur" if on else "putar")
        self.statusBar().showMessage("Mode ukur: klik dua atom" if on else "Mode ukur dimatikan", 4000)

    def ekspor_objek(self, o):
        ext = "sdf" if o.fmt == "sdf" else "pdb"
        f, _ = QFileDialog.getSaveFileName(self, "Ekspor objek", f"{o.nama}.{ext}", f"{ext.upper()} (*.{ext})")
        if f:
            Path(f).write_text(o.teks)
            self.log.tulis(f"Diekspor: {f}")

    def buka_di(self, nama):
        if not self.env or nama not in self.env.eksternal:
            return
        tmp = paths.CACHE / "buka"
        tmp.mkdir(exist_ok=True)
        berkas = []
        for o in self.objek.values():
            if not o.tampil:
                continue
            ext = "sdf" if o.fmt == "sdf" else "pdb"
            p = tmp / f"{molekul.re.sub(r'[^A-Za-z0-9_.-]+', '_', o.nama)}.{ext}"
            p.write_text(o.teks)
            berkas.append(str(p))
        if not berkas:
            QMessageBox.information(self, "Buka di…", "Belum ada objek yang ditampilkan.")
            return
        subprocess.Popen([self.env.eksternal[nama]] + berkas, creationflags=0)
        self.log.tulis(f"Dibuka di {nama}: {len(berkas)} berkas")

    def atur_eksternal(self):
        manual = self.st.value("eksternal", {}) or {}
        nama, ok = QInputDialog.getItem(self, "Atur lokasi program", "Program:",
                                        ["PyMOL", "ChimeraX", "Discovery Studio Visualizer"], 0, False)
        if not ok:
            return
        f, _ = QFileDialog.getOpenFileName(self, f"Lokasi {nama}", "C:/Program Files", "Program (*.exe)")
        if f:
            manual[nama] = f
            self.st.setValue("eksternal", manual)
            self.deteksi()

    def reset_layout(self):
        self.st.remove("layout")
        QMessageBox.information(self, "Layout", "Layout bawaan dipakai lagi saat VirmoDock dibuka berikutnya.")

    def tentang(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        from .logo import Logo
        d = QDialog(self)
        d.setWindowTitle("Tentang VirmoDock")
        lay = QVBoxLayout(d)
        lay.setContentsMargins(28, 24, 28, 16)
        lay.addWidget(Logo(64, self.mode == "gelap"))
        lay.addSpacing(14)
        teks = QLabel(f"<b>Versi {VERSI}</b>" + (" (portable)" if paths.PORTABLE else "") +
                      "<br>Aplikasi molecular docking desktop, gratis dan open-source (GPL-3.0-or-later).<br><br>"
                      "Mesin: AutoDock-GPU (OpenCL), AutoDock Vina 1.2.7, AutoDock 4.2.6.<br>"
                      "Kimia: RDKit, Meeko, Open Babel, gemmi. Viewer: 3Dmol.js. UI: Qt (PySide6).<br><br>"
                      "© 2026 apt. Rizki Rahmadi Pratama, M. Farm<br><br>"
                      f"<span style='color:{theme.TOKEN[self.mode]['mut']}'>Data aplikasi: {paths.APPDATA}</span>")
        teks.setWordWrap(True)
        teks.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(teks)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(d.accept)
        lay.addWidget(bb)
        d.setFixedWidth(560)
        d.exec()

    # ------------------------------------------------------- jendela & DPI
    def _ukuran_awal(self):
        layar = QApplication.primaryScreen().availableGeometry()
        w, h = min(1440, int(layar.width() * 0.92)), min(900, int(layar.height() * 0.9))
        self.resize(w, h)
        self.move(layar.center().x() - w // 2, layar.center().y() - h // 2)

    def _pastikan_di_layar(self):
        """Geometri tersimpan di monitor yang sudah tidak ada -> pusatkan di layar utama."""
        pusat = self.frameGeometry().center()
        if not any(s.availableGeometry().contains(pusat) for s in QApplication.screens()):
            self.showNormal()
            self._ukuran_awal()

    # ------------------------------------------------------ pindah laptop
    def ekspor_cadangan(self):
        from datetime import datetime
        from ..core import pindah
        ikut = []
        if self.proyek and QMessageBox.question(
                self, "Ekspor pengaturan",
                f"Sertakan proyek yang sedang dibuka?\n{self.proyek.folder}") == QMessageBox.Yes:
            self._simpan_diam()
            ikut = [self.proyek.folder]
        self.st.setValue("geometri", self.saveGeometry())
        self.st.setValue("layout", self.saveState())
        f, _ = QFileDialog.getSaveFileName(self, "Ekspor pengaturan & proyek",
                                           str(Path.home() / f"VirmoDock_{datetime.now():%Y%m%d}.vmdbackup"),
                                           "Cadangan VirmoDock (*.vmdbackup)")
        if not f:
            return
        kerja.jalankan(pindah.ekspor, f, self.st, ikut, VERSI, log=self.log.tulis, galat=self._galat,
                       selesai=lambda m: (self.log.tulis(f"Cadangan disimpan: {f}"),
                                          QMessageBox.information(self, "Pindah laptop",
                                                                  f"Cadangan tersimpan:\n{f}\n\nSalin berkas ini ke "
                                                                  "laptop baru, lalu File › Pindah laptop › Impor.")))

    def impor_cadangan(self, f=None):
        from ..core import pindah
        if not f:
            f, _ = QFileDialog.getOpenFileName(self, "Impor pengaturan & proyek", str(Path.home()),
                                               "Cadangan VirmoDock (*.vmdbackup)")
        if not f:
            return
        try:
            meta = pindah.baca_meta(f)
        except Exception as e:
            self._galat(f"Berkas cadangan tidak terbaca: {e}")
            return
        if QMessageBox.question(self, "Impor pengaturan",
                                f"Cadangan VirmoDock {meta.get('versi', '')} dari {meta.get('dibuat', '')}.\n"
                                f"Proyek di dalamnya: {', '.join(meta.get('proyek') or []) or '-'}\n\n"
                                "Pengaturan saat ini akan ditimpa. Lanjutkan?") != QMessageBox.Yes:
            return
        tujuan = Path(self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))

        def selesai(h):
            n, proyek, catatan = h
            for c in catatan:
                self.pesan.tulis(c)
            self.log.tulis(f"Impor pengaturan: {n} kunci, {len(proyek)} proyek")
            self.deteksi()  # GPU & software dideteksi ulang di laptop ini
            if proyek and QMessageBox.question(
                    self, "Impor selesai", f"{len(proyek)} proyek dipulihkan ke {tujuan}.\nBuka sekarang?") == QMessageBox.Yes:
                self.buka_proyek(proyek[0])
            else:
                QMessageBox.information(self, "Impor selesai", "Pengaturan dipulihkan. Tata letak jendela dipakai saat "
                                                               "VirmoDock dibuka berikutnya.")
        kerja.jalankan(pindah.impor, f, self.st, tujuan, log=self.log.tulis, selesai=selesai, galat=self._galat)

    # --------------------------------------------------------------- help
    def buka_panduan(self, nama):
        f = paths.DOCS / (nama if "." in nama else f"{nama}.html")
        if not f.exists():
            self._galat(f"Dokumen {f.name} tidak ditemukan di {paths.DOCS}.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(f)))

    def uji_mandiri(self):
        from ..core import ujimandiri
        self.d_log.raise_()
        self.log.tulis("Uji mandiri dimulai…")

        def selesai(h):
            gagal = [x for x in h if not x["ok"]]
            teks = "\n".join(f"{'✓' if x['ok'] else '✗'}  {x['uji']}: {x['detail']}" for x in h)
            (QMessageBox.information if not gagal else QMessageBox.warning)(
                self, "Uji mandiri", ("Semua komponen berfungsi.\n\n" if not gagal else
                                      f"{len(gagal)} uji gagal — lihat Help › Dokumentasi › Troubleshooting.\n\n")
                + teks)
        kerja.jalankan(ujimandiri.uji, selesai=selesai, galat=self._galat, log=self.log.tulis)

    def lapor_masalah(self):
        DialogLapor(VERSI, self.env, self).exec()

    def _belum(self):
        self.pesan.tulis("Fitur ini sedang dibangun di tahap berikutnya.")
        self.d_pesan.raise_()

    def _galat(self, g):
        self.pesan.tulis(g)
        self.d_pesan.raise_()

    def closeEvent(self, e):
        if self.pelaksana.sibuk():
            r = QMessageBox.question(self, "Docking sedang berjalan",
                                     "Docking masih berjalan. Tutup VirmoDock?\n\nJob akan dijeda dan bisa dilanjutkan "
                                     "saat proyek dibuka lagi (ligan yang sudah selesai tidak diulang).\n\n"
                                     "Tip: minimize jendela agar docking tetap berjalan.")
            if r != QMessageBox.Yes:
                e.ignore()
                return
        self.pelaksana.hentikan_semua()
        self._simpan_diam()
        self.st.setValue("geometri", self.saveGeometry())
        self.st.setValue("layout", self.saveState())
        self.st.remove("sesi_terbuka")  # ditutup normal: tidak perlu pemulihan
        if self.tray:
            self.tray.hide()
        super().closeEvent(e)
