"""Jendela utama VirmoLab."""
import copy
import os
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDockWidget, QFileDialog, QHBoxLayout,
                               QInputDialog, QLabel, QMainWindow, QPushButton, QSizePolicy, QStackedWidget,
                               QMessageBox, QSystemTrayIcon, QTabWidget, QToolBar, QToolButton, QVBoxLayout,
                               QWidget)

from ..core import analisis, arti, catat, laporan
from ..core.laporan import id_angka
from ..core import antrean as antreanmod
from ..core import ekspor as eksmod
from ..core import env as envmod
from ..core import mesin as mesinmod
from ..core import molekul, paths
from ..core import prep_reseptor
from ..core import sifat as sifat_mod
from ..core import statistik as stat_mod
from ..core.proyek import Proyek, nama_aman
from . import icons, kerja, kit, theme
from .panel_antrean import PanelAntrean
from .panel_hasil import PanelHasil
from .panel_interaksi import PanelInteraksi, TabDiagram
from .tab_sifat import TabSifat
from .tab_statistik import TabStatistik
from .tab_uji import TabUji
from .panel_alur import DaftarLangkah, PanelLangkah, SKEMA_ALUR
from .halaman_awal import HalamanAwal
from .tab_banding import TabBanding
from .panel_docking import PanelDocking
from .mainwindow_dialog import PembukaDialog
from .mainwindow_komposer import KomposerFigur
from .mainwindow_media import MediaAnimasi
from .panels import PanelHierarki, PanelLog, PanelProperti, PanelTampilan
from .viewer_widget import Viewer

from .. import __version__ as VERSI
GRUP_LIGAN = "Ligan siap docking"
MESIN_URUT = ["adgpu", "vina", "ad4"]
KUNCI_LAYOUT = "layout_v2"      # v2: panel Langkah (struktur dock berbeda dari v1)
RUANG = [("siapkan", "Siapkan"), ("docking", "Docking"), ("analisis", "Analisis")]
UBIN_PX = 4096                  # gambar 3D lebih besar dari ini dirender per ubin (batas kanvas WebGL)


class JendelaUtama(PembukaDialog, KomposerFigur, MediaAnimasi, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VirmoLab")
        self.setObjectName("VirmoLab")
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
        self._pesan_belum_dibaca = 0      # jumlah galat/peringatan yang belum dilihat (lencana bilah status)
        self._bawah_dikunci = False       # True bila pengguna sendiri yang membuka panel bawah
        self._bawah_ditutup_pengguna = False   # True bila pengguna menutupnya: galat cukup jadi lencana
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
            f"Jarak {d['a']['resn']}{d['a']['resi']}:{d['a']['atom']} - {d['b']['resn']}{d['b']['resi']}:{d['b']['atom']} = {d['d']:.2f} Å"))
        self.viewer.kotakDigeser.connect(self._kotak_dari_viewer)
        self.viewer.atomDiseret.connect(self._atom_diseret)
        self._gnina_antre = []
        self._gnina_jalan = False
        self._gnina_sedang = None
        self._gnina_tidak_ada = False
        self._geser_jalan = False
        self.tab_tengah = QTabWidget()
        self.tab_tengah.setDocumentMode(True)
        self.tab_tengah.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.w_view = QWidget()                 # tab viewport = halaman sambutan ATAU (bar gaya 3D + viewer)
        vv = QVBoxLayout(self.w_view)
        vv.setContentsMargins(0, 0, 0, 0)
        vv.setSpacing(0)
        hal3d = QWidget()
        v3 = QVBoxLayout(hal3d)
        v3.setContentsMargins(0, 0, 0, 0)
        v3.setSpacing(0)
        self.bar_view = QToolBar()
        self.bar_view.setIconSize(QSize(16, 16))
        v3.addWidget(self.bar_view)
        v3.addWidget(self.viewer, 1)
        self.awal = HalamanAwal()
        self.awal.aksi.connect(self._aksi_awal)
        self.stak_view = QStackedWidget()
        self.stak_view.addWidget(hal3d)
        self.stak_view.addWidget(self.awal)
        vv.addWidget(self.stak_view)
        self.tab_tengah.addTab(self.w_view, "Viewport 3D")
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
        self.sifat = TabSifat()
        self.sifat.minta.connect(lambda: self._muat_sifat(paksa=True))
        self.sifat.ekspor.connect(self._ekspor_sifat)
        self.tab_tengah.addTab(self.sifat, "Sifat Ligan")
        self.statistik = TabStatistik()
        self.statistik.ekspor.connect(self._ekspor_statistik)
        self.tab_tengah.addTab(self.statistik, "Statistik")
        self.uji = TabUji()
        self.uji.ekspor.connect(self._ekspor_uji)
        self.uji.berubah.connect(self._uji_berubah)
        self.uji.mintaDocking = self._uji_dari_docking
        self.tab_tengah.addTab(self.uji, "Uji && Grafik")
        self.komposer = None          # DialogKomposer, dibuat saat pertama dibuka
        self.tab_tengah.currentChanged.connect(self._tab_berganti)
        self._stat_kotor = True
        self._sifat_kotor = True
        self.banding = None
        self._aktif_inter = None
        self._cache_mol, self._cache_rec = {}, {}
        tengah = QWidget()
        tengah.setObjectName("central")
        v = QVBoxLayout(tengah)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.tab_tengah)
        self.setCentralWidget(tengah)

        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)   # tab panel di atas, bukan di bawah
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
        self._potong_ukuran_normal()
        if not self.isMaximized():
            QTimer.singleShot(0, self._buka_penuh)
        state = self.st.value(KUNCI_LAYOUT)
        # tata letak tersimpan hanya dipakai bila ukuran layarnya mirip; kalau tidak (mis. dulu di monitor
        # eksternal, sekarang di layar laptop) proporsinya dihitung ulang agar panel tidak menutupi area kerja
        if state and self._layar_sama():
            self.restoreState(state)
        else:
            QTimer.singleShot(0, self._ukuran_dock_awal)
        self._ruang_aktif = None
        QTimer.singleShot(0, lambda: self.atur_ruang("siapkan"))
        if self.st.value("mode_pengguna", "pemula") == "ahli":
            QTimer.singleShot(0, lambda: self.atur_mode_pengguna("ahli", simpan=False))
        # viewer harus TERLIHAT saat 3Dmol dibuat (membaca devicePixelRatio); sambutan baru tampil setelah siap
        self.viewer.jembatan.siapSignal.connect(lambda: QTimer.singleShot(0, self._perbarui_awal))
        self.segarkan_langkah()
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
        # kiri: Langkah (atas) + Objek (bawah)
        self.langkah = DaftarLangkah()
        self.langkah.dipilih.connect(self.ke_langkah)
        self.langkah.alurBerubah.connect(self._alur_berubah)
        self.d_langkah = self._dock("Langkah", self.langkah, Qt.LeftDockWidgetArea, "dock_langkah")
        self.hier = PanelHierarki()
        self.hier.visibilitasBerubah.connect(self.set_tampil)
        self.hier.objekDipilih.connect(self.pilih_objek)
        self.hier.residuDipilih.connect(self.pilih_residu)
        self.hier.aksiKonteks.connect(self.aksi_konteks)
        self.d_hier = self._dock("Objek", self.hier, Qt.LeftDockWidgetArea, "dock_hierarki")
        self.d_hier.setMinimumWidth(self._lebar_huruf(26))
        self.splitDockWidget(self.d_langkah, self.d_hier, Qt.Vertical)

        # kanan: Panel kerja langkah | Tampilan | Interaksi (tab) + Properti (bawah)
        self.param = PanelDocking()
        self.param.parameterBerubah.connect(self._param_berubah)
        self.param.kotakBerubah.connect(self._kotak_dari_panel)
        self.param.aksiKotak.connect(self.aksi_kotak)
        self.param.tampilKotak.connect(lambda on: self.a_box.setChecked(on) or self.toggle_box(on))
        self.param.jalankan.connect(self.jalankan_docking)
        self.p_langkah = PanelLangkah(self.param.hal_area, self.param.hal_jalan)
        self.p_langkah.aksi.connect(self._aksi_langkah)
        self.p_langkah.berikutnya.connect(lambda i: self.ke_langkah(min(i, 4)))
        self.d_kerja = self._dock("Panel kerja", self.p_langkah, Qt.RightDockWidgetArea, "dock_kerja")
        self.d_kerja.setMinimumWidth(self._lebar_huruf(34))
        self.prop = PanelProperti()
        self.prop.mintaKofolding.connect(self.jalankan_kofolding_pose)
        self.prop.togglePoseDocking.connect(self._toggle_pose_docking)
        self.prop.togglePoseBoltz.connect(self._toggle_pose_boltz)
        self.d_prop = self._dock("Properti", self.prop, Qt.RightDockWidgetArea, "dock_properti")
        self.splitDockWidget(self.d_kerja, self.d_prop, Qt.Vertical)   # dulu, sebelum ditab
        self.tampilan = PanelTampilan()
        self.tampilan.gayaBerubah.connect(self.ubah_gaya)
        self.d_tamp = self._dock("Tampilan", self.tampilan, Qt.RightDockWidgetArea, "dock_tampilan")
        self.tabifyDockWidget(self.d_kerja, self.d_tamp)
        self.p_inter = PanelInteraksi()
        self.p_inter.jenisBerubah.connect(self._tampilkan_interaksi)
        self.p_inter.opsiBerubah.connect(self._tampilkan_interaksi)
        self.p_inter.fokusResidu.connect(self._fokus_interaksi)
        self.d_inter = self._dock("Interaksi", self.p_inter, Qt.RightDockWidgetArea, "dock_interaksi")
        self.tabifyDockWidget(self.d_tamp, self.d_inter)
        self.d_kerja.raise_()
        for d in (self.d_kerja, self.d_tamp, self.d_inter):   # sudah ada tab di atas: tanpa judul ganda
            d.setTitleBarWidget(QWidget())

        # bawah: Antrean | Log | Pesan - tersembunyi; dibuka dari bilah status atau saat docking berjalan
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
        for d in (self.d_antre, self.d_log, self.d_pesan):
            d.visibilityChanged.connect(lambda *_: self._sinkron_bawah())
        self._t_tutup_bawah = QTimer(self)    # tunda penutupan panel bawah agar baris terakhir sempat dibaca
        self._t_tutup_bawah.setSingleShot(True)
        self._t_tutup_bawah.setInterval(4000)
        self._t_tutup_bawah.timeout.connect(self._tutup_bawah_bila_selesai)
        self._t_ringkas = QTimer(self)        # tunda penerapan kepadatan saat jendela sedang diseret
        self._t_ringkas.setSingleShot(True)
        self._t_ringkas.setInterval(250)
        self._t_ringkas.timeout.connect(lambda: self.terapkan_tema(self.mode))
        self.t_langkah = QTimer(self)
        self.t_langkah.setSingleShot(True)
        self.t_langkah.setInterval(150)
        self.t_langkah.timeout.connect(self._segarkan_langkah)

    def resizeEvent(self, e):
        """Lewati ambang layar pendek (< 800 px): kepadatan antarmuka disesuaikan sekali, tidak tiap piksel."""
        super().resizeEvent(e)
        ringkas = self.ringkas()
        if getattr(self, "_ringkas_terpasang", None) != ringkas:
            self._ringkas_terpasang = ringkas
            self._t_ringkas.start()

    def _paksa_lebar(self, lebar_dock):
        """Atur lebar dok lalu lepaskan batasnya lagi: resizeDocks sendiri sering diabaikan saat dok bertumpuk."""
        batas_lama = {d: (d.minimumWidth(), d.maximumWidth()) for d in lebar_dock}
        for d, w in lebar_dock.items():
            d.setFixedWidth(int(w))

        def lepas():
            for d, (mn, mx) in batas_lama.items():
                d.setMinimumWidth(mn)
                d.setMaximumWidth(mx)
        QTimer.singleShot(0, lepas)

    def _lebar_huruf(self, n_karakter):
        """Lebar n karakter pada huruf antarmuka saat ini — ikut penskalaan Windows 100/125/150%."""
        from PySide6.QtGui import QFontMetrics
        return int(QFontMetrics(self.font()).horizontalAdvance("0") * n_karakter) + 24

    @staticmethod
    def _bagian(total, rasio, kecil, besar):
        """Bagian proporsional dari `total`, dijepit antara `kecil` dan `besar`."""
        return int(max(kecil, min(besar, total * rasio)))

    def ringkas(self):
        """True bila ruang kerja pendek (laptop 768p atau jendela kecil): tata letak dirapatkan."""
        return self.height() < 800

    def _ukuran_dock_awal(self):
        """Proporsi bawaan: dihitung dari ukuran jendela, bukan angka piksel tetap, agar pas di layar mana pun."""
        lebar, tinggi = max(800, self.width()), max(600, self.height())
        kiri = self._bagian(lebar, 0.18, self._lebar_huruf(24), 340)
        kanan = self._bagian(lebar, 0.24, self._lebar_huruf(32), 480)
        bawah = self._bagian(tinggi, 0.20, 120, 280)
        if self.ringkas():      # layar pendek: Langkah dan Objek ditumpuk jadi tab, bukan dibagi dua
            if self.tabifiedDockWidgets(self.d_langkah) != [self.d_hier]:
                self.tabifyDockWidget(self.d_langkah, self.d_hier)
            self.d_langkah.raise_()
        else:
            self.resizeDocks([self.d_langkah, self.d_hier],
                             [self._bagian(tinggi, 0.32, 180, 340), self._bagian(tinggi, 0.45, 220, 560)],
                             Qt.Vertical)
        self._paksa_lebar({self.d_langkah: kiri, self.d_hier: kiri,
                           self.d_kerja: kanan, self.d_prop: kanan, self.d_tamp: kanan, self.d_inter: kanan})
        self.resizeDocks([self.d_kerja, self.d_prop],
                         [max(320, tinggi - bawah - 180), self._bagian(tinggi, 0.16, 100, 220)], Qt.Vertical)
        self.resizeDocks([self.d_antre, self.d_log, self.d_pesan], [bawah] * 3, Qt.Vertical)
        for d in (self.d_antre, self.d_log, self.d_pesan):
            d.hide()

    # ------------------------------------------------------- alur langkah & ruang kerja
    def _ke_langkah_docking(self, i):
        """Navigasi internal untuk alur docking molekuler standar."""
        self.p_langkah.setCurrentIndex(i)
        self.d_kerja.show()
        self.d_kerja.raise_()
        ruang = "siapkan" if i <= 2 else "docking" if i == 3 else "analisis"
        if ruang != self._ruang_aktif:
            self.atur_ruang(ruang, dari_langkah=True)
        if i == 2 and not self.box.get("tampil", True):
            self.a_box.setChecked(True)
            self.toggle_box(True)

    def ke_langkah(self, i):
        """Tampilkan langkah i (0..4) dan ruang kerja sesuai alur aktif."""
        self.langkah.pilih(i, kirim=False)
        alur = getattr(self.langkah, "alur_aktif", lambda: "docking")()
        self.p_langkah.pilih_langkah(alur, i)
        self.d_kerja.show()
        self.d_kerja.raise_()
        if alur == "docking":
            self._ke_langkah_docking(i)
        elif alur == "md":
            ruang = "siapkan" if i == 0 else "analisis"
            if ruang != self._ruang_aktif:
                self.atur_ruang(ruang, dari_langkah=True)
        elif alur == "screening":
            ruang = "siapkan" if i <= 1 else "docking" if i in (2, 3) else "analisis"
            if ruang != self._ruang_aktif:
                self.atur_ruang(ruang, dari_langkah=True)
            if i == 2 and not self.box.get("tampil", True):
                self.a_box.setChecked(True)
                self.toggle_box(True)
        elif alur == "ppi":
            ruang = "siapkan" if i <= 1 else "analisis"
            if ruang != self._ruang_aktif:
                self.atur_ruang(ruang, dari_langkah=True)
        elif alur == "fbdd":
            ruang = "siapkan" if i <= 1 else "analisis"
            if ruang != self._ruang_aktif:
                self.atur_ruang(ruang, dari_langkah=True)
        else:
            self._ke_langkah_docking(i)

    def _alur_berubah(self, alur):
        """Respon saat pengguna memilih alur kerja baru dari pemilih langkah."""
        from .panel_alur import SKEMA_ALUR
        nama = SKEMA_ALUR.get(alur, {}).get("nama", alur)
        self.statusBar().showMessage(f"Alur kerja aktif: {nama}", 4000)
        if hasattr(self, "grup_alur"):
            for a in self.grup_alur.actions():
                if a.text() == nama:
                    a.setChecked(True)
        self._segarkan_langkah()
        self.ke_langkah(0)
        if alur == "md":
            self.statusBar().showMessage("Alur MD: Siapkan kompleks protein-ligan, lalu jalankan OpenMM / MM-GBSA.", 5000)
        elif alur == "screening":
            self.statusBar().showMessage("Alur Penapisan: Siapkan target reseptor dan pustaka senyawa.", 5000)
        elif alur == "ppi":
            self.statusBar().showMessage("Alur PPI: Siapkan makromolekul reseptor & protein mitra interaksi.", 5000)
        elif alur == "fbdd":
            self.statusBar().showMessage("Alur FBDD: Deteksi kantong pengikatan lalu buka rekayasa fragmen.", 5000)

    def atur_ruang(self, ruang, dari_langkah=False):
        """Siapkan / Docking / Analisis: tab tengah dan panel yang relevan saja."""
        self._ruang_aktif = ruang
        for b in self.grp_ruang.buttons():
            b.setChecked(b.property("ruang") == ruang)
        tab = {"siapkan": {self.w_view}, "docking": {self.w_view, self.hasil}}.get(ruang)
        for i in range(self.tab_tengah.count()):
            w = self.tab_tengah.widget(i)
            self.tab_tengah.setTabVisible(i, tab is None or w in tab)
        if ruang == "analisis":
            self.d_inter.show()
            self.tab_tengah.setCurrentWidget(self.hasil)
            self._tutup_bawah_bila_selesai()
        else:
            self.d_inter.hide()
            self.tab_tengah.setCurrentWidget(self.w_view)
        if ruang == "docking" and self.proyek and any(j["status"] in ("berjalan", "menunggu", "dijeda")
                                                      for j in self.proyek.job):
            self._tampil_bawah(True)
        if not dari_langkah:
            sekarang = self.langkah.aktif()
            if ruang == "siapkan":
                i = sekarang if sekarang <= 2 else self._langkah_belum()
            else:
                i = 3 if ruang == "docking" else 4
            self.langkah.pilih(i, kirim=False)
            self.p_langkah.setCurrentIndex(i)
            self.d_kerja.raise_()

    def _langkah_belum(self):
        st = getattr(self, "_status_langkah", None) or []
        return next((i for i, (s, _k) in enumerate(st[:3]) if s != "selesai"), 2)

    def _aksi_langkah(self, k):
        tab = {"tab_hasil": self.hasil, "tab_diagram": self.diagram, "tab_sifat": self.sifat,
               "tab_statistik": self.statistik, "tab_uji": self.uji}
        if k in tab:
            self.atur_ruang("analisis", dari_langkah=True)
            self.tab_tengah.setCurrentWidget(tab[k])
            return
        aksi_peta = {"rcsb": lambda: self.ambil(0), "alphafold": lambda: self.ambil(3), "pubchem": lambda: self.ambil(1), "smiles": lambda: self.ambil(2),
                     "pustaka": self.buka_pustaka, "tanaman": self.buka_tanaman, "peptida": self.buka_peptida, "xtb": self.buka_xtb, "generatif": self.buka_generatif, "rbfe": self.buka_rbfe, "buka": self.buka_berkas, "reseptor": self.siapkan_reseptor, "ligan": self.siapkan_ligan,
                     "validasi": self.validasi_redocking, "validasi_protokol": self.buka_validasi_protokol,
                     "ekspor": lambda: self.buka_ekspor(3),
                     "laporan": lambda: self.buka_ekspor(4), "mpo": self.buka_mpo, "labplanner": self.buka_labplanner,
                     "md": self.buka_md, "penapisan": self.buka_penapisan, "ppi": self.buka_ppi,
                     "fbdd": self.buka_fbdd, "kantong": self.buka_kantong,
                     "target_balik": self.buka_target_balik, "qsar": self.buka_qsar,
                     "farmakofor": self.buka_farmakofor}
        if k in aksi_peta:
            aksi_peta[k]()

    def segarkan_langkah(self):
        self.t_langkah.start()

    def _segarkan_langkah(self):
        """Status tiap langkah dari keadaan proyek & viewer."""
        pr = self.proyek
        t = theme.TOKEN[self.mode]
        ok = lambda x: f"<span style='color:{t['ok']}'>✓ {x}</span>"         # noqa: E731
        catat = lambda x: f"<span style='color:{t['warn']}'>{x}</span>"      # noqa: E731
        protein = [o for o in self.objek.values() if o.jenis == "protein" and not o.info.get("siap_docking")]
        rec = pr.reseptor if pr and pr.reseptor and pr.p(pr.reseptor["pdbqt"]).exists() else None
        if rec:
            s1 = ("selesai", f"{rec.get('nama', '')} siap")
            t1 = ok(f"Reseptor siap: {rec.get('nama', '')} · {rec.get('atom', 0)} atom") + \
                "<br>Bisa disiapkan ulang bila protein diganti."
        elif protein:
            s1 = ("belum", f"{protein[0].nama} dimuat")
            t1 = f"Protein dimuat: <b>{protein[0].nama}</b>. " + catat("Klik Siapkan reseptor.")
        else:
            s1 = ("belum", "belum ada")
            t1 = "Belum ada protein. Ambil dari RCSB (mis. 1HSG) atau buka berkas."
        siap = pr.ligan_siap() if pr else []
        mentah = [o for o in self.objek.values() if o.jenis == "ligan" and not o.info.get("siap_docking")
                  and not o.info.get("ligan_asli") and not o.info.get("kofaktor")]
        asli = [o for o in self.objek.values() if o.jenis == "ligan" and o.info.get("ligan_asli")
                and not o.info.get("siap_docking")]
        n_war = sum(1 for l in siap if l.get("status") == "peringatan")
        if siap:
            s2 = ("selesai", f"{len(siap)} siap")
            t2 = ok(f"{len(siap)} ligan siap docking") + (f" · {n_war} dengan peringatan" if n_war else "")
            if mentah:
                t2 += "<br>" + catat(f"{len(mentah)} ligan baru belum disiapkan.")
        elif mentah or asli:
            n = len(mentah) + len(asli)
            s2 = ("belum", f"{n} dimuat")
            t2 = f"{n} ligan dimuat. " + catat("Klik Siapkan ligan.")
        else:
            s2 = ("belum", "belum ada")
            t2 = "Belum ada ligan. Ambil dari PubChem, ketik SMILES, atau buka berkas."
        if self.box.get("pusat"):
            u = self.box["ukuran"]
            s3 = ("selesai", " × ".join(f"{x:.1f}".replace(".", ",").replace(",0", "") for x in u) + " Å")
        else:
            s3 = ("belum", "belum diatur")
        jobs = pr.job if pr else []
        jalan = next((j for j in jobs if j["status"] == "berjalan"), None)
        n_hasil = sum(1 for j in jobs for l in j["ligan"] if l["status"] == "selesai")
        if jalan:
            k = sum(1 for l in jalan["ligan"] if l["status"] not in ("menunggu", "berjalan"))
            s4 = ("belum", f"berjalan {k}/{len(jalan['ligan'])}")
        elif n_hasil:
            s4 = ("selesai", f"{len(jobs)} job")
        else:
            s4 = ("belum", "belum dijalankan")
        if n_hasil:
            terbaik = min(((j, l) for j in jobs for l in j["ligan"] if l["status"] == "selesai"),
                          key=lambda jl: jl[1]["energi"])
            dg = terbaik[1]["energi"]
            s5 = ("selesai", f"{n_hasil} hasil")
            nama_skor = "skor kovalen" if terbaik[0].get("kovalen") else "ΔG"
            t5 = ok(f"{n_hasil} hasil docking") + f" · {nama_skor} terbaik {kit.f(dg, 2, 'kcal/mol')}"
            if not getattr(pr, "validasi", None):
                t5 += "<br>" + catat("Belum divalidasi (redocking).")
        else:
            s5 = ("belum", "belum ada")
            t5 = "Belum ada hasil. Jalankan docking di langkah 4."
        alur = getattr(self.langkah, "alur_aktif", lambda: "docking")()
        if alur == "docking":
            self._status_langkah = [s1, s2, s3, s4, s5]
        elif alur == "md":
            ada_md = bool(pr and getattr(pr, "md", None))
            self._status_langkah = [
                s1,
                ("selesai" if ada_md else "belum", "solvasi & ion" if ada_md else "belum diatur"),
                ("selesai" if ada_md else "belum", "amber14" if ada_md else "default OpenMM"),
                ("selesai" if ada_md else "belum", f"{len(pr.md)} simulasi" if ada_md else "belum dijalankan"),
                ("selesai" if ada_md else "belum", "RMSD & MM-GBSA" if ada_md else "belum ada"),
            ]
        elif alur == "screening":
            self._status_langkah = [
                s1,
                ("selesai" if len(siap) > 1 else "belum", f"{len(siap)} ligan pustaka" if siap else "belum ada pustaka"),
                s3,
                s4,
                ("selesai" if n_hasil else "belum", f"{n_hasil} pose diskrining" if n_hasil else "belum ada"),
            ]
        elif alur == "ppi":
            self._status_langkah = [
                s1,
                ("selesai" if len(protein) > 1 else "belum", f"{len(protein)} mitra" if len(protein) > 1 else "belum ada mitra"),
                ("selesai" if rec else "belum", "kontak SASA" if rec else "belum dihitung"),
                ("belum", "HDOCK / pyDock"),
                ("belum", "evaluasi energi"),
            ]
        elif alur == "fbdd":
            self._status_langkah = [
                ("selesai" if self.box.get("pusat") else "belum", "kantong aktif" if self.box.get("pusat") else "belum diatur"),
                ("selesai" if siap else "belum", f"{len(siap)} fragmen" if siap else "belum ada"),
                ("belum", "growing / linking"),
                ("selesai" if siap else "belum", "QED & SAScore" if siap else "belum ada"),
                ("selesai" if siap else "belum", "siap diuji" if siap else "belum ada"),
            ]
        else:
            self._status_langkah = [s1, s2, s3, s4, s5]
        self.langkah.set_status(self._status_langkah)
        self.p_langkah.set_status(t1, t2, t5)
        self.param.set_ringkasan(f"{rec.get('nama', '')} · {rec.get('atom', 0)} atom" if rec else None, len(siap),
                                 n_war, s3[1] if self.box.get("pusat") else "")
        siap_jalan = bool(rec and siap and self.box.get("pusat"))
        self.param.b_run.setText("Jalankan docking" + (f" ({len(siap)} ligan)" if siap_jalan else ""))
        self._sinkron_bawah()

    # ------------------------------------------------------- panel bawah (antrean ringkas)
    def _tampil_bawah(self, on, fokus=None):
        """Buka/tutup panel bawah; `fokus` = dock yang dinaikkan (bawaan: Antrean job)."""
        for d in (self.d_antre, self.d_log, self.d_pesan):
            d.setVisible(on)
        if on:
            (fokus or self.d_antre).raise_()
        self._sinkron_bawah()

    def _bawah_oleh_pengguna(self, on):
        """Pengguna sendiri yang membuka/menutup panel bawah: pilihannya tidak diubah otomatis."""
        self._bawah_dikunci = bool(on)
        self._bawah_ditutup_pengguna = not on
        if on:
            self._pesan_belum_dibaca = 0
        self._tampil_bawah(on)

    def _job_berjalan(self):
        """True bila masih ada job berjalan, menunggu, atau dijeda — panel bawah tetap dibiarkan terbuka."""
        return any(j["status"] in ("berjalan", "menunggu", "dijeda")
                   for j in (self.proyek.job if self.proyek else []))

    def _tutup_bawah_bila_selesai(self):
        """Tutup panel bawah setelah antrean habis dan pesan sudah dibaca — panel kosong tidak menutupi hasil."""
        if self._job_berjalan() or self._pesan_belum_dibaca:
            return
        if any(d.isVisible() for d in (self.d_antre, self.d_log, self.d_pesan)) and not self._bawah_dikunci:
            self._tampil_bawah(False)

    def _sinkron_bawah(self):
        if not hasattr(self, "b_antre"):
            return
        buka = any(d.isVisible() for d in (self.d_antre, self.d_log, self.d_pesan))
        if buka and self.d_pesan.isVisible() and self.d_pesan.visibleRegion().boundingRect().height() > 40:
            self._pesan_belum_dibaca = 0       # tab Pesan benar-benar tampil: dianggap sudah dibaca
        self.b_antre.blockSignals(True)
        self.b_antre.setChecked(buka)
        self.b_antre.blockSignals(False)
        pr = self.proyek
        jobs = pr.job if pr else []
        jalan = next((j for j in jobs if j["status"] == "berjalan"), None)
        if jalan:
            n = len(jalan["ligan"])
            k = sum(1 for l in jalan["ligan"] if l["status"] not in ("menunggu", "berjalan"))
            teks = f"Docking {k}/{n} · {mesinmod.MESIN[jalan['mesin']]}"
        else:
            tunggu = sum(1 for j in jobs if j["status"] in ("menunggu", "dijeda"))
            teks = f"{tunggu} job menunggu/dijeda" if tunggu else (f"{len(jobs)} job" if jobs else "kosong")
        sibuk = bool(jalan) or any(j["status"] in ("menunggu", "dijeda") for j in jobs)
        if buka and not self._bawah_dikunci and not sibuk and not self._pesan_belum_dibaca:
            self._t_tutup_bawah.start()   # antrean habis (selesai/gagal/dibatalkan/dihentikan): tutup sebentar lagi
        else:
            self._t_tutup_bawah.stop()
        lencana = f"  ·  {self._pesan_belum_dibaca} pesan baru" if self._pesan_belum_dibaca else ""
        self.b_antre.setText(f"Antrean: {teks}{lencana}  {'▾' if buka else '▴'}")
        self.b_antre.setProperty("perhatian", bool(self._pesan_belum_dibaca))
        self.b_antre.style().unpolish(self.b_antre)
        self.b_antre.style().polish(self.b_antre)

    # ------------------------------------------------------------- aksi
    def _a(self, teks, ikon=None, fn=None, kunci=None, tip=None, cek=False):
        a = QAction(teks, self)
        a.setData(ikon)
        if fn:
            a.triggered.connect(fn)
        if kunci:
            a.setShortcut(QKeySequence(kunci))
        a.setCheckable(cek)
        a.setToolTip(tip or teks.replace("…", ""))
        a.setStatusTip(tip or teks.replace("…", ""))      # keterangan di bilah status saat diarahkan di menu
        return a

    def _aksi(self):
        A = self._a
        # --- berkas & proyek
        self.a_baru = A("Proyek baru…", "new", self.proyek_baru, "Ctrl+N",
                        "Buat folder proyek baru (.vmd) untuk menyimpan reseptor, ligan, dan hasil docking")
        self.a_templat = A("Proyek baru dari templat…", "new", self.proyek_templat, None,
                           "Docking satu ligan, virtual screening, validasi redocking, pembanding obat standar, "
                           "repurposing obat, atau proyek contoh HIV-1 protease (offline)")
        self.a_buka_proyek = A("Buka proyek…", "folder", lambda: self.buka_proyek(), "Ctrl+Shift+O",
                               "Buka folder proyek VirmoLab (.vmd) yang tersimpan")
        self.a_terakhir = A("Buka proyek terakhir", "rotate",
                            lambda: self.buka_proyek(self.st.value("proyek_terakhir", "")), None,
                            "Lanjutkan proyek yang terakhir dibuka")
        self.a_simpan = A("Simpan proyek", "save", self.simpan, "Ctrl+S",
                          "Simpan sekarang (proyek juga tersimpan otomatis setiap ada perubahan)")
        self.a_buka = A("Buka berkas struktur…", "open", self.buka_berkas, "Ctrl+O",
                        "Buka protein atau ligan dari komputer: PDB, CIF, PDBQT, SDF, MOL2, SMILES")
        self.a_rcsb = A("Protein dari RCSB PDB…", "import", lambda: self.ambil(0), "Ctrl+Shift+P",
                        "Unduh struktur protein dengan kode PDB (mis. 1HSG, 6LU7)")
        self.a_alphafold = A("Protein dari AlphaFold DB…", "import", lambda: self.ambil(3), None,
                             "Struktur prediksi AlphaFold lewat kode UniProt atau nama protein/gen - untuk target "
                             "tanpa struktur kristal")
        self.a_pubchem = A("Ligan dari PubChem…", "search", lambda: self.ambil(1), "Ctrl+Shift+L",
                           "Unduh senyawa dari PubChem dengan nama atau CID (bisa banyak sekaligus)")
        self.a_smiles = A("Ligan dari SMILES…", "smiles", lambda: self.ambil(2), None,
                          "Buat ligan 3D dari teks SMILES")
        self.a_peptida = A("Peptida dari sekuens…", "lig", self.buka_peptida, None,
                           "Bangun kompleks peptida dan reseptor dengan co-folding Boltz-2 (bukan docking Vina)")
        self.a_chembl = A("Ligan dari ChEMBL (aktif dikenal)…", "search", lambda: self.buka_chembl(0), None,
                          "Cari target di ChEMBL lalu impor senyawa aktif (pChEMBL) sebagai ligan pembanding/validasi")
        self.a_ketcher = A("Gambar ligan (Ketcher)…", "edit", lambda: self.gambar_ligan(), "Ctrl+Shift+K",
                           "Gambar struktur 2D di editor Ketcher (offline) lalu jadikan ligan 3D")
        self.a_pustaka = A("Pustaka ligan (obat, bahan alam, ZINC)…", "lig", self.buka_pustaka, None,
                           "3.200 obat disetujui (offline), ±700 ribu bahan alam COCONUT, ZINC22; saring sifat & "
                           "kemiripan lalu impor")
        self.a_tanaman = A("Senyawa dari tanaman obat…", "lig", self.buka_tanaman, None,
                           "Cari senyawa yang dilaporkan dari suatu tanaman (LOTUS/Wikidata, COCONUT), lengkap dengan rujukan, lalu impor ke proyek")
        self.a_keluar = A("Keluar", None, self.close, "Ctrl+Q", "Tutup VirmoLab (docking berjalan akan dijeda)")
        # --- ekspor
        self.a_ekspor = A("Pusat ekspor…", "dl", lambda: self.buka_ekspor(3), "Ctrl+E",
                          "Semua ekspor dalam satu jendela: gambar, diagram, struktur, tabel, laporan")
        self.a_foto = A("Gambar 3D…", "camera", lambda: self.buka_ekspor(0), "Ctrl+Shift+S",
                        "Gambar viewport resolusi tinggi (PNG/TIFF/JPEG, DPI pilihan, preset jurnal)")
        self.a_animasi = A("Video / animasi 3D (MP4 4K, GIF)…", "rotate", self.ekspor_animasi, None,
                           "Rekam viewport berputar, bergoyang, atau zoom masuk ke situs pengikatan: video MP4 "
                           "Full HD/2K/4K untuk presentasi, atau GIF/WebP")
        self.a_eks_2d = A("Diagram interaksi 2D…", "diagram", lambda: self.buka_ekspor(1), None,
                          "Diagram 2D pose aktif sebagai SVG/PDF vektor atau PNG/TIFF")
        self.a_eks_struk = A("Struktur (kompleks PDB, SDF, PDBQT)…", "cube", lambda: self.buka_ekspor(2), None,
                             "Kompleks reseptor-ligan, SDF bertag, atau PDBQT pose")
        self.a_eks_tabel = A("Tabel hasil (Excel/CSV)…", "table", lambda: self.buka_ekspor(3), None,
                             "Ringkasan, semua pose, interaksi, sifat ligan, statistik")
        self.a_eks_sesi = A("Sesi PyMOL / ChimeraX…", "ext", self.ekspor_sesi, None,
                            "Skrip .pml dan .cxc untuk pose aktif: reseptor, ligan, residu kontak, garis interaksi")
        self.a_lapor = A("Laporan (PDF, Word, HTML interaktif)…", "report", lambda: self.buka_ekspor(4),
                         "Ctrl+Shift+R", "Laporan lengkap: validasi, metode, 15 hasil teratas, gambar, interaksi, "
                                         "sitasi - PDF, Word yang bisa disunting, atau HTML dengan penjelajah 3D")
        # --- siapkan
        self.a_rec = A("Siapkan reseptor…", "rec", self.siapkan_reseptor, "Ctrl+Shift+1",
                       "Buang air/ligan, tambah hidrogen dan muatan, simpan PDBQT reseptor")
        self.a_lig = A("Siapkan ligan…", "lig", self.siapkan_ligan, "Ctrl+Shift+2",
                       "Hidrogen, protonasi pH, struktur 3D, minimisasi, torsi, simpan PDBQT ligan")
        self.a_box = A("Tampilkan kotak area docking", "box", self.toggle_box, "G", cek=True,
                       tip="Tampilkan atau sembunyikan kotak biru (grid box) di viewport")
        self.a_kotak_asli = A("Pusat di ligan asli", None, lambda: self.aksi_kotak("ligan_asli"), None,
                              "Kotak di kantong tempat ligan kristal terikat (disarankan)")
        self.a_kotak_res = A("Pusat di residu terpilih", None, lambda: self.aksi_kotak("residu"), None,
                             "Pilih residu di panel Objek atau klik atom di viewport dulu")
        self.a_kotak_sesuai = A("Sesuaikan ke ligan terpilih +8 Å", None, lambda: self.aksi_kotak("sesuai"), None,
                                "Ukuran kotak = rentang ligan terpilih + 8 Å tiap sisi")
        self.a_kotak_blind = A("Seluruh protein (blind docking)", None, lambda: self.aksi_kotak("blind"), None,
                               "Kotak menutupi seluruh protein; lebih lama")
        self.a_kotak_kantong = A("Deteksi kantong (P2Rank)…", "search", lambda: self.aksi_kotak("kantong"), None,
                                 "Cari kantong pengikatan otomatis (P2Rank) lalu pilih untuk grid box")
        self.a_fleksibel = A("Residu fleksibel…", None, lambda: self.aksi_kotak("fleksibel"), None,
                             "Rantai samping kantong yang boleh bergerak saat docking (AD-GPU, Vina)")
        self.a_kovalen = A("Docking kovalen…", None, lambda: self.aksi_kotak("kovalen"), None,
                           "Ikat ligan ber-gugus reaktif ke Cys/Ser/Lys lalu docking sebagai aduk (AutoDock-GPU)")
        # --- docking
        self.a_run = A("Jalankan docking", "play", self.jalankan_docking, "F5",
                       "Docking semua ligan siap (atau ligan terpilih di panel Objek)")
        self.a_antre = A("Antrean job", "queue", lambda: self._tampil_bawah(True), "Ctrl+J",
                         "Lihat progres, jeda, lanjut, atau batalkan docking")
        self.a_param = A("Pengaturan docking…", "sliders", lambda: self.ke_langkah(3), "Ctrl+D",
                         "Mesin, perangkat, ketelitian, dan parameter lanjutan (langkah 4)")
        self.a_validasi = A("Validasi redocking…", "check", self.validasi_redocking, None,
                            "Docking ulang ligan kristal dan hitung RMSD (≤ 2,0 Å = metode valid)")
        # --- analisis & viewport
        self.a_ukur = A("Ukur jarak", "ruler", self.toggle_ukur, "M", cek=True, tip="Klik dua atom untuk mengukur jarak")
        self.a_seret = A("Seret atom ligan", None, self.toggle_seret, None, cek=True,
                         tip="Geser satu atom ligan di bidang layar. Lepas mouse untuk merapikan ikatan "
                             "dan menilai ulang dengan Vina di tempat")
        self.a_geser = A("Geser ligan utuh", None, self.toggle_geser, None, cek=True,
                         tip="Geser seluruh ligan tanpa mengubah bentuknya. Lepas mouse untuk menilai ulang "
                             "dengan Vina di tempat")
        self.a_kontrib = A("Kontribusi energi per atom", "palette", self._tampilkan_kontribusi, "K", cek=True,
                           tip="Bola hijau = atom ligan menguntungkan, merah = merugikan (suku Vina antarmolekul)")
        self.a_farma = A("Farmakofor pose aktif", "target", self._tampilkan_farmakofor, "P", cek=True,
                         tip="Donor/akseptor ikatan H, aromatik, hidrofobik, muatan pada pose aktif (fitur RDKit)")
        self.a_inter = A("Interaksi 3D", "hbond", self._tampilkan_interaksi, "I", cek=True,
                         tip="Tampilkan ikatan hidrogen, hidrofobik, π, dll. pada pose aktif")
        self.a_inter.setChecked(True)
        self.a_qc = A("Periksa pose aktif (PoseBusters)…", "check", self.qc_pose_aktif, None,
                      "Uji kewajaran fisik pose: geometri, tabrakan, jarak ke protein")
        self.a_fit = A("Sesuaikan tampilan", "fit", lambda: self.viewer.js("fokusSemua"), "F",
                       "Pusatkan dan perbesar semua objek yang terlihat")
        self.a_putar = A("Putar otomatis", "rotate", lambda on: self.viewer.js("spin", on), None, cek=True)
        self.a_tema = A("Mode gelap", "moon", self.ganti_tema, "Ctrl+T", cek=True, tip="Ganti tema terang / gelap")
        self.a_presentasi = A("Mode presentasi & fokus", None, self.toggle_mode_presentasi, "F11", cek=True,
                              tip="Sembunyikan panel untuk tampilan bersih presentasi/publikasi (F11 atau Esc untuk kembali)")
        self.a_cek = A("Cek sistem dan GPU…", "gpu", lambda: self.deteksi(wizard=True), None,
                       "Deteksi ulang GPU/OpenCL, panduan driver, dan program pendukung")
        self.a_reset = A("Atur ulang tata letak", None, self.reset_layout, "Ctrl+Shift+0",
                         "Kembalikan susunan panel ke bawaan")

    def _judul_menu(self, menu, teks):
        """Judul kelompok di dalam menu (QMenu.addSection tidak tampil dengan gaya tema ini)."""
        from PySide6.QtWidgets import QWidgetAction
        if menu.actions():
            menu.addSeparator()
        l = QLabel(teks.upper())
        l.setObjectName("judulMenu")
        wa = QWidgetAction(menu)
        wa.setDefaultWidget(l)
        wa.setEnabled(False)
        menu.addAction(wa)

    def _sub(self, menu, judul, aksi):
        sub = menu.addMenu(judul)
        sub.setToolTipsVisible(True)
        for a in aksi:
            sub.addSeparator() if a is None else sub.addAction(a)
        return sub

    def _menu(self):
        mb = self.menuBar()
        A = self._a

        def menu(judul):
            m = mb.addMenu(judul)
            m.setToolTipsVisible(True)
            return m

        def isi(m, aksi):
            for a in aksi:
                m.addSeparator() if a is None else m.addAction(a)

        # ---------------------------------------------------------------- Berkas
        m = menu("&Berkas")
        isi(m, (self.a_baru, self.a_templat, self.a_buka_proyek, self.a_terakhir, self.a_simpan, None, self.a_buka))
        self._sub(m, "Ambil dari internet", (self.a_rcsb, self.a_alphafold, self.a_pubchem, self.a_smiles, self.a_chembl,
                                             self.a_pustaka, self.a_tanaman, self.a_ketcher))
        m.addSeparator()
        self._sub(m, "Ekspor", (self.a_ekspor, None, self.a_foto, self.a_animasi, self.a_eks_2d, self.a_eks_struk, self.a_eks_sesi,
                                self.a_eks_tabel, self.a_lapor))
        self._sub(m, "Pindah laptop", (
            A("Ekspor pengaturan dan proyek…", None, self.ekspor_cadangan, None,
              "Simpan pengaturan (dan proyek) ke satu berkas .vmdbackup untuk laptop lain"),
            A("Impor pengaturan dan proyek…", None, self.impor_cadangan, None,
              "Pulihkan dari berkas .vmdbackup")))
        isi(m, (None, self.a_keluar))
        m.aboutToShow.connect(lambda: self.a_terakhir.setEnabled(
            bool(self.st.value("proyek_terakhir", "")) and Path(self.st.value("proyek_terakhir", "")).exists()))

        # ---------------------------------------------------------------- Edit
        m = menu("&Edit")
        self.a_urung = A("Urungkan", None, self.urungkan, "Ctrl+Z", "Batalkan perubahan grid box, posisi ligan, "
                                                                     "atau gaya tampilan terakhir")
        self.a_ulang = A("Ulangi", None, self.ulangi, "Ctrl+Y", "Ulangi perubahan yang diurungkan")
        self.a_palet = A("Palet perintah…", "search", self.palet, "Ctrl+K",
                         "Cari dan jalankan perintah menu mana pun dengan mengetik")
        self._riwayat, self._maju = [], []
        self._segarkan_urung()
        isi(m, (self.a_urung, self.a_ulang, None, self.a_palet, None))
        isi(m, (A("Salin gambar", "camera", self.salin_gambar, "Ctrl+Shift+C",
                  "Salin gambar tab yang terbuka (viewport 3D, diagram 2D, BOILED-Egg, grafik) ke clipboard "
                  "untuk ditempel di Word/PowerPoint"),
                None,
                A("Ganti nama objek…", None, lambda: self._aksi_objek("rename"), "F2",
                  "Ganti nama objek terpilih di panel Objek"),
                A("Ekspor objek terpilih…", None, lambda: self._aksi_objek("export"), None,
                  "Simpan objek terpilih sebagai berkas struktur"),
                A("Hapus objek terpilih", "trash", self.hapus_terpilih, QKeySequence.Delete,
                  "Hapus objek terpilih dari viewport (berkas proyek tidak ikut terhapus)"),
                None,
                A("Pilih semua objek", None, lambda: self.hier.pohon.selectAll(), QKeySequence.SelectAll),
                A("Cari objek, rantai, atau residu", "search",
                  lambda: (self.d_hier.show(), self.hier.filter.setFocus()), "Ctrl+F",
                  "Ketik di kotak filter panel Objek"),
                None,
                A("Hapus semua pengukuran", None, lambda: self.viewer.js("hapusUkur"), None)))

        # ---------------------------------------------------------------- Tampilan
        m = menu("&Tampilan")
        self._sub(m, "Ruang kerja", [A(t, None, lambda _=False, k=k: self.atur_ruang(k), f"Ctrl+{i + 1}",
                                       {"siapkan": "Protein, ligan, dan area docking (langkah 1-3)",
                                        "docking": "Mesin, ketelitian, jalankan, antrean (langkah 4)",
                                        "analisis": "Hasil, interaksi, diagram, sifat ligan, statistik (langkah 5)"}[k])
                                     for i, (k, t) in enumerate(RUANG)])
        self._sub(m, "Langkah", [A(f"{i + 1}. {t}", None, lambda _=False, i=i: self.ke_langkah(i), f"Alt+{i + 1}")
                                 for i, t in enumerate(("Protein", "Ligan", "Area docking", "Jalankan", "Hasil"))])
        m.addSeparator()
        self._sub(m, "Gaya molekul", [A(t, None, lambda _=False, k=k: self.gaya_cepat(k), None,
                                        f"Tampilkan protein sebagai {t.lower()}")
                                      for k, t in (("cartoon", "Kartun"), ("sticks", "Stick"),
                                                   ("ballstick", "Bola-stick"), ("surface", "Permukaan"))])
        self.m_render = m.addMenu("Render 3D")
        self.m_render.setToolTipsVisible(True)
        r = self._opsi_render()
        self.a_tepi = QAction("Garis tepi", self, checkable=True)
        self.a_tepi.setToolTip("Garis tepi gelap tipis pada kartun & stick, ala ilustrasi jurnal")
        self.a_tepi.setChecked(r["tepi"])
        self.a_ao = QAction("Bayangan sekitar (AO)", self, checkable=True)
        self.a_ao.setToolTip("Ambient occlusion: celah & kantong lebih berdimensi (lebih berat di GPU lemah)")
        self.a_ao.setChecked(r["ao"])
        for a in (self.a_tepi, self.a_ao):
            a.setStatusTip(a.toolTip())
            a.toggled.connect(lambda _=False: self.gaya_render())
            self.m_render.addAction(a)
        mk = self.m_render.addMenu("Kabut kedalaman")
        mk.setToolTipsVisible(True)
        self.grp_kabut = QActionGroup(self)
        for k, t, tip in (("mati", "Mati", "Tanpa kabut: warna penuh sampai bagian terjauh"),
                          ("halus", "Halus (bawaan)", "Bagian terjauh sedikit memudar sebagai isyarat kedalaman"),
                          ("kuat", "Kuat", "Kabut bawaan 3Dmol: kedalaman sangat terasa, warna belakang pucat")):
            a = QAction(t, self, checkable=True)
            a.setData(k)
            a.setToolTip(tip)
            a.setStatusTip(tip)
            a.setChecked(k == r["kabut"])
            a.triggered.connect(lambda _=False: self.gaya_render())
            self.grp_kabut.addAction(a)
            mk.addAction(a)
        isi(m, (self.a_fit, self.a_putar, self.a_box, self.a_inter, None))
        self._sub(m, "Panel", [d.toggleViewAction() for d in (
            self.d_langkah, self.d_hier, self.d_kerja, self.d_prop, self.d_tamp, self.d_inter, self.d_antre,
            self.d_log, self.d_pesan)])
        isi(m, (self.a_tema, self.a_presentasi, self.a_reset))
        m_alur = m.addMenu("Alur kerja")
        self.m_alur = m_alur
        self.grup_alur = QActionGroup(m_alur)
        for kode, info in SKEMA_ALUR.items():
            a = m_alur.addAction(info["nama"], lambda k=kode: self.langkah.ganti_alur(k))
            a.setCheckable(True)
            a.setChecked(self.langkah.alur_aktif() == kode)
            self.grup_alur.addAction(a)
        m_mode = m.addMenu("Mode pengguna")
        grup_mode = QActionGroup(m_mode)
        mode_kini = self.st.value("mode_pengguna", "pemula")
        for kode, nama, tip in (("pemula", "Pemula", "Panel Langkah tampil, pengaturan lanjutan dilipat"),
                                ("ahli", "Ahli", "Panel Langkah disembunyikan (viewport lebih luas), pengaturan "
                                                 "lanjutan terbuka; pakai Ctrl+K untuk semua perintah")):
            a = m_mode.addAction(nama, lambda k=kode: self.atur_mode_pengguna(k))
            a.setCheckable(True)
            a.setChecked(mode_kini == kode)
            a.setStatusTip(tip)
            grup_mode.addAction(a)
        m_bhs = m.addMenu("Bahasa / Language")
        grup = QActionGroup(m_bhs)
        kini = self.st.value("bahasa", "id")
        for kode, nama in (("id", "Bahasa Indonesia"), ("en", "English")):
            a = m_bhs.addAction(nama, lambda k=kode: self.ganti_bahasa(k))
            a.setCheckable(True)
            a.setChecked(kini == kode)
            grup.addAction(a)

        # ---------------------------------------------------------------- Siapkan
        m = menu("&Siapkan")
        self._judul_menu(m, "Langkah 1 · Protein")
        isi(m, (self.a_rcsb, self.a_alphafold, self.a_rec))
        self._judul_menu(m, "Langkah 2 · Ligan")
        isi(m, (self.a_pubchem, self.a_smiles, self.a_ketcher, self.a_chembl, self.a_pustaka, self.a_tanaman,
                self.a_peptida, self.a_lig))
        self._judul_menu(m, "Langkah 3 · Area docking")
        isi(m, (self.a_kotak_asli, self.a_kotak_res, self.a_kotak_sesuai, self.a_kotak_kantong, self.a_kotak_blind,
                self.a_box,
                A("Atur ukuran dan posisi…", None, lambda: self.ke_langkah(2), None,
                  "Buka langkah 3 untuk mengetik pusat, ukuran, dan spasi kotak"), None, self.a_fleksibel,
                self.a_kovalen))

        # ---------------------------------------------------------------- Docking
        m = menu("&Docking")
        isi(m, (self.a_run, self.a_param, None))
        self.m_mesin = self._sub(m, "Mesin", [])
        self.m_ketelitian = self._sub(m, "Ketelitian", [])
        isi(m, (None, self.a_antre,
                A("Jeda job berjalan", "pause", lambda: self._aksi_job("jeda"), None,
                  "Berhenti setelah ligan yang sedang dikerjakan; bisa dilanjutkan"),
                A("Lanjutkan job dijeda", "play", lambda: self._aksi_job("lanjut"), None),
                A("Batalkan job berjalan", "stop", lambda: self._aksi_job("batal"), None,
                  "Hentikan sekarang; ligan yang sudah selesai tetap tersimpan"),
                None, self.a_validasi))
        m.aboutToShow.connect(self._isi_menu_docking)

        # ---------------------------------------------------------------- Analisis
        m = menu("&Analisis")
        tab = lambda w: lambda: (self.atur_ruang("analisis", dari_langkah=True), self.tab_tengah.setCurrentWidget(w))  # noqa: E731
        # yang sering dipakai tetap di tingkat atas; sisanya dikelompokkan agar menu tidak sepanjang layar
        isi(m, (A("Tabel hasil", "table", tab(self.hasil), "Ctrl+R", "Peringkat ΔG semua ligan; klik dua kali untuk pose"),
                A("Diagram interaksi 2D", "diagram", tab(self.diagram), None, "Diagram 2D pose aktif"),
                A("Sifat ligan dan BOILED-Egg", "lig", tab(self.sifat), None,
                  "Lipinski, Veber, QED, PAINS, absorpsi GI, sawar darah otak, SAScore"),
                A("Bandingkan ligan dicentang", None, lambda: self.bandingkan(self.hasil.dicentang()), None,
                  "Centang 2-4 ligan di tab Hasil, lalu bandingkan berdampingan"),
                None))

        self._sub(m, "Telaah pose dan interaksi", (
            self.a_inter, self.a_kontrib, self.a_farma, self.a_ukur,
            A("Hapus pengukuran", None, lambda: self.viewer.js("hapusUkur"), None),
            None, self.a_seret, self.a_geser,
            None,
            A("Peta interaksi residu × ligan", "grid", self.peta_interaksi, None,
              "Peta panas residu yang dikontak oleh semua ligan"),
            A("Periksa kontak atom pose…", "check", self.buka_rescore_ml, None,
              "Sidik jari kontak protein–ligan ≤ 4 Å untuk menyaring pose berskor kuat tetapi kontaknya tipis"),
            A("Syarat jarak…", None, self.atur_syarat_jarak, None,
              "Tandai pose yang atom beratnya lebih jauh dari residu yang dipilih. Pencarian docking tidak dipaksa")))

        self._sub(m, "Validasi dan mutu", (
            self.a_validasi,
            A("Paket validasi protokol…", "check", self.buka_validasi_protokol, None,
              "Validasi terstandarisasi untuk naskah: redocking, cross-docking, pengayaan decoy DUD-E, dan PoseBusters"),
            self.a_qc,
            A("Konsensus skor…", "table", self.buka_konsensus, None,
              "Gabungkan beberapa mesin/fungsi skor (termasuk rescoring Vina & Vinardo) menjadi peringkat "
              "konsensus + Kendall W"),
            A("Korelasi dengan data eksperimen (ChEMBL)…", "chart", lambda: self.buka_chembl(1), None,
              "Cocokkan ligan hasil docking dengan pChEMBL target (IC50/Ki/Kd) → grafik ΔG vs pChEMBL, Pearson/"
              "Spearman"),
            None,
            A("Hitung ulang analisis hasil", "rotate", self.analisis_ulang, None,
              "Lengkapi interaksi, LE, RMSD kristal, dan PoseBusters untuk hasil lama"),
            A("GNINA untuk sisa ligan", None, self._gnina_sisa, None,
              "Nilai GNINA untuk ligan di luar 10 energi terbaik")))

        self._sub(m, "Struktur reseptor", (
            A("Deteksi kantong pengikatan (geometri)…", "cube", self.buka_kantong, None,
              "Pencari rongga bawaan VirmoLab (kisi geometri, tanpa Java). Untuk peringkat kantong "
              "berbasis pembelajaran mesin, pakai Siapkan › Deteksi kantong (P2Rank)"),
            A("Saluran akses ligan…", "cube", self.buka_terowongan, None,
              "Jalur lurus dari sisi aktif ke pelarut: jari-jari leher, panjang, dan residu penjaga"),
            A("Antarmuka protein–protein (PPI)…", "play", self.buka_ppi, None,
              "Residu permukaan dari SASA, kontak dan ikatan hidrogen antar-rantai, luas terkubur "
              "(ΔSASA). Docking PPI-nya sendiri dijalankan di ClusPro")))

        self._sub(m, "Sifat ligan dan desain", (
            A("Prediksi ADMET (ADMET-AI)…", "lig", self.buka_admet, None,
              "Absorpsi, distribusi, metabolisme (CYP), ekskresi, toksisitas (hERG, Ames, DILI) - model "
              "pembelajaran mesin, berjalan offline"),
            A("Optimasi multi-parameter (MPO) dan radar…", "chart", self.buka_mpo, None,
              "Satukan sifat fisikokimia, QED, SAScore, dan ΔG menjadi satu skor kelayakan "
              "(preset Oral MPO dan CNS-MPO) dengan grafik radar"),
            A("Kemiripan, ruang kimia, farmakofor…", "similar", self.buka_kemiripan, None,
              "Tanimoto (ECFP4/FCFP4/MACCS/farmakofor 2D), klaster Butina, peta ruang kimia, cari ligan mirip, "
              "farmakofor bersama pose teratas"),
            A("Pasangan molekul berpadanan (MMP)…", "similar", self.buka_mmp, None,
              "Pasangan ligan yang berbeda satu gugus R, jurang aktivitas (activity cliff), dan arah "
              "substitusi yang menaikkan afinitas"),
            None,
            A("Desain berbasis fragmen (FBDD)…", "plus", self.buka_fbdd, None,
              "Tumbuhkan gugus bioisosterik pada fragmen, atau sambungkan dua fragmen dengan linker"),
            A("Perancang PROTAC…", "link", self.buka_protac, None,
              "Rakit molekul bivalen warhead–linker–pengikat E3 ligase dan nilai kriteria bRo5"),
            A("Titik metabolisme CYP450…", "target", self.buka_metabolisme, None,
              "Gugus yang lazim dioksidasi CYP450 fase I dan saran penggantinya (berbasis pola SMARTS)"),
            A("Kinetika dan waktu tinggal…", "clock", self.buka_kinetika, None,
              "Perkiraan kasar k_off, waktu tinggal τ, dan waktu paruh kompleks dari ΔG dan pola kontak"),
            A("Sifat elektronik (xTB)…", "lig", self.buka_xtb, None,
              "HOMO, LUMO, celah, elektrofilisitas, dipol, muatan, dan indeks Fukui dengan GFN2-xTB semi-empiris"),
            A("Desain generatif…", "lig", self.buka_generatif, None,
              "Bangun analog yang masuk akal untuk disintesis dari satu senyawa induk dengan CReM")))
        # RBFE eksperimental: hanya muncul di mode ahli (lihat atur_mode_pengguna)
        self.a_rbfe = A("Energi bebas relatif (eksperimental)…", "clock", self.buka_rbfe, None,
                        "Susun jaringan perturbasi untuk seri senyawa kongenerik; simulasinya menuntut "
                        "GPU dan sistem Linux")
        m.addAction(self.a_rbfe)

        self._sub(m, "Penapisan banyak ligan", (
            A("Dasbor penapisan virtual…", "table", self.buka_penapisan, None,
              "Peta panas, diagram sebar, saringan multikriteria, dan penandaan hit teratas untuk "
              "penapisan banyak ligan"),
            A("Selektivitas multi-target…", "grid", self.buka_selektivitas, None,
              "Bandingkan afinitas ligan pada beberapa target, normalisasi Z-score, dan celah selektivitas"),
            A("Penapisan farmakofor && bentuk 3D…", "puzzle", self.buka_farmakofor, None,
              "Tapis pustaka senyawa berdasarkan fitur farmakofor 3D dan keselarasan bentuk ligan acuan"),
            A("Penargetan balik & jaringan…", "target", self.buka_target_balik, None,
              "Identifikasi target protein potensial untuk senyawa (profil kemiripan ChEMBL + docking panel target)"),
            A("QSAR && model prediksi…", "chart", self.buka_qsar, None,
              "Latih model dari data aktivitas Anda sendiri dan prediksi pIC50 ligan proyek")))

        self._sub(m, "Simulasi dan penelitian lanjut", (
            A("MD && MM/GBSA…", "play", self.buka_md, None,
              "Minimisasi + MM/GBSA, atau dinamika molekul (OpenMM) pelarut implisit/eksplisit: RMSD, RMSF, "
              "interaksi persisten, ΔG MM/GBSA - VirmoLab menyarankan tingkat sesuai kemampuan laptop"),
            A("Penelitian lanjutan…", "chart", self.buka_penelitian, None,
              "Konservasi, energi per residu, umpan, enumerasi, mutasi, draf skripsi, film trajektori")))

        m.addSeparator()
        self._sub(m, "Statistik dan figur", (
            A("Uji statistik dan grafik publikasi", "chart", tab(self.uji), None,
              "Tempel data uji (in vitro, dll.) → t-test/ANOVA/post-hoc otomatis, braket signifikansi, IC₅₀"),
            A("Statistik dan grafik", "chart", tab(self.statistik), None,
              "Histogram, korelasi, regresi, matriks korelasi"),
            A("Komposer figur (panel A/B/C)…", "grid", self.buka_komposer, "Ctrl+Shift+F",
              "Gabungkan grafik, diagram 2D, dan gambar 3D menjadi satu figur berlabel A/B/C siap jurnal")))
        isi(m, (A("Interpretasi hasil docking…", "chart", self.buka_interpretasi, None,
                  "Draf ringkasan dan Bab Hasil & Pembahasan dari angka proyek; memakai Ollama di komputer "
                  "sendiri bila terpasang, selain itu mesin pakar VirmoLab"),))

        # ---------------------------------------------------------------- Alat
        m = menu("A&lat")
        isi(m, (A("Pengaturan…", "sliders", self.buka_pengaturan, "Ctrl+,",
                  "Pengaturan folder kerja, program eksternal, dan cache internet"),
                None))
        self.m_buka_di = m.addMenu("Buka di program lain")
        self.m_buka_di.setToolTipsVisible(True)
        isi(m, (A("Atur lokasi program lain…", None, self.atur_eksternal, None,
                  "Lokasi PyMOL, ChimeraX, Discovery Studio Visualizer"),
                None, self.a_cek,
                A("Uji mandiri komponen…", None, self.uji_mandiri, None,
                  "Periksa semua mesin docking dan pustaka kimia berfungsi"),
                A("Skrip figur publikasi (PyMOL / ChimeraX)…", "report", self.buka_skrip_publikasi, None,
                  "Skrip siap jalan untuk merender figur kompleks beresolusi tinggi"),
                None,
                A("Konsol Python", None, self.buka_konsol, "Ctrl+Shift+`",
                  "Jalankan perintah Python langsung terhadap proyek (pengguna mahir, pembuat plugin)")))
        self.m_plugin = m.addMenu("Plugin")
        self.m_plugin.setToolTipsVisible(True)
        self._plugin = []
        QTimer.singleShot(1500, self.muat_plugin)
        isi(m, (None,
                A("Buka folder proyek", "folder", self._buka_folder_proyek, None),
                A("Buka folder kerja", "folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(
                    self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))), None,
                  "Folder bawaan tempat proyek baru dibuat")))

        # ---------------------------------------------------------------- Bantuan
        m = menu("Ba&ntuan")
        isi(m, (A("Asisten…", "help", self.buka_asisten, None,
                  "Catatan di aplikasi, plus Ollama bila sudah terpasang di komputer ini"),
                A("Pemeriksa kesehatan sistem…", "check", self.buka_diagnostik, None,
                  "Diagnostik kesiapan Python, RDKit, OpenMM/GPU, Vina, Gemmi, WSL, dan AI lokal"),
                A("Panduan pengguna", "help", lambda: self.buka_panduan("panduan"), "F1"),
                A("Tutorial docking (PDF)", "report", lambda: self.buka_panduan("Tutorial_Docking_VirmoLab.pdf"),
                  None, "Langkah demi langkah dengan contoh 1HSG/MK1"),
                A("Tur aplikasi", None, self.tur, None, "Sorot bagian-bagian jendela satu per satu (± 1 menit)"),
                A("Pintasan keyboard", None, self.pintasan, "Ctrl+/", "Daftar semua pintasan keyboard dan mouse"),
                A("Apa yang baru", None, lambda: self.apa_baru(), None, "Ringkasan perubahan tiap versi")))
        self._sub(m, "Dokumentasi", [A(t, None, lambda _=False, k=k: self.buka_panduan(k))
                                     for k, t in (("instalasi", "Instalasi"), ("pindah_laptop", "Pindah laptop"),
                                                  ("gpu", "Setup GPU"), ("troubleshooting", "Mengatasi masalah"),
                                                  ("metode", "Metode dan kriteria"))])
        isi(m, (None,
                A("Lapor masalah atau kirim saran…", None, self.lapor_masalah, None,
                  "Susun laporan beserta info sistem dan log (Anda yang mengirim)"),
                A("Buka folder log", None, lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.LOG))), None),
                A("Lisensi dan cara mengutip…", None, self._buka_lisensi, None),
                None,
                A("Periksa pembaruan…", None, self.buka_pembaruan, None,
                  "Bandingkan versi terpasang dengan rilis terbaru di GitHub"),
                A("Tentang VirmoLab", None, self.tentang, None)))

    def _buka_lisensi(self):
        from .dialog_bantuan import DialogLisensi
        DialogLisensi(VERSI, self).exec()

    # ------------------------------------------------------------- bantu menu
    def _aksi_objek(self, aksi):
        oid = self.aktif
        if not oid or oid not in self.objek:
            self._galat("Pilih objek dulu di panel Objek.")
            return
        self.aksi_konteks(oid, aksi, None)

    def _aksi_job(self, aksi):
        jobs = self.proyek.job if self.proyek else []
        status = {"jeda": ("berjalan",), "batal": ("berjalan", "menunggu"), "lanjut": ("dijeda", "gagal")}[aksi]
        j = next((x for x in jobs if x["status"] in status), None)
        if not j:
            self._galat({"jeda": "Tidak ada job yang sedang berjalan.", "batal": "Tidak ada job yang berjalan.",
                         "lanjut": "Tidak ada job yang dijeda."}[aksi])
            return
        self._tampil_bawah(True)
        self.aksi_antrean(aksi, j["id"])

    def _isi_menu_docking(self):
        """Submenu Mesin & Ketelitian mengikuti panel langkah 4 (satu sumber kebenaran)."""
        from .panel_docking import PRESET
        p = self.param
        self.m_mesin.clear()
        for k, t in (("adgpu", "AutoDock-GPU (GPU, cepat)"), ("vina", "AutoDock Vina (CPU)"),
                     ("ad4", "AutoDock4 (CPU, klasik)")):
            a = self.m_mesin.addAction(t, lambda k=k: (p.btn_mesin[k].setChecked(True), self.ke_langkah(3)))
            a.setCheckable(True)
            a.setChecked(p.mesin() == k)
            a.setEnabled(p.btn_mesin[k].isEnabled())
        self.m_ketelitian.clear()
        for i in range(p.cmb_preset.count()):
            nama = p.cmb_preset.itemData(i)
            a = self.m_ketelitian.addAction(p.cmb_preset.itemText(i), lambda n=nama: (
                p.cmb_preset.setCurrentIndex(p.cmb_preset.findData(n)), p.terapkan_preset(n)))
            a.setCheckable(True)
            a.setChecked(p.cmb_preset.currentData() == nama)
            if nama in PRESET:
                a.setStatusTip({"Cepat": "Uji coba cepat", "Standar": "Penelitian umum (disarankan)",
                                "Teliti": "Hasil akhir / publikasi; lebih lama"}[nama])

    def _buka_folder_proyek(self):
        if not self.proyek:
            self._galat("Belum ada proyek terbuka.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.proyek.folder)))

    def apa_baru(self, sejak=None):
        from .dialog_bantuan import DialogApaBaru
        d = DialogApaBaru(VERSI, self, sejak)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def pintasan(self):
        """Daftar pintasan dari semua aksi (otomatis) + gerakan mouse viewport."""
        from html import escape
        baris = {}
        for a in self.findChildren(QAction):
            k = a.shortcut().toString(QKeySequence.NativeText)
            if k and a.text():
                baris[k] = a.text().replace("&", "").replace("…", "")
        mouse = [("Seret kiri", "Putar molekul"), ("Seret kanan / gulir", "Perbesar / perkecil"),
                 ("Seret tengah / Ctrl+seret", "Geser"), ("Klik atom", "Pilih atom (lihat Properti)"),
                 ("Seret atom (mode Seret atom ligan)", "Geser satu atom, lalu Vina menilai di tempat"),
                 ("Geser ligan (mode Geser ligan utuh)", "Geser seluruh ligan tanpa mengubah bentuknya"),
                 ("Shift + seret", "Geser kotak area docking"), ("Shift + gulir", "Ubah ukuran kotak"),
                 ("Alt + gulir", "Ubah satu sumbu kotak (pilih dengan X, Y, Z)")]
        t = theme.TOKEN[self.mode]
        h = [f"<style>td{{padding:3px 10px 3px 0;}} td.k{{font-family:Consolas,monospace;color:{t['acct']};"
             "white-space:nowrap;}}</style><p><b>Keyboard</b></p><table>"]
        h += [f"<tr><td class='k'>{escape(k)}</td><td>{escape(v)}</td></tr>"
              for k, v in sorted(baris.items(), key=lambda x: x[1].lower())]
        h.append("</table><p><b>Mouse di viewport 3D</b></p><table>")
        h += [f"<tr><td class='k'>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in mouse]
        h.append("</table>")
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser
        d = QDialog(self)
        d.setWindowTitle("Pintasan keyboard dan mouse")
        d.resize(520, 620)
        v = QVBoxLayout(d)
        tb = QTextBrowser()
        tb.setHtml("".join(h))
        v.addWidget(tb)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)
        d.exec()

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
        self.a_rcsb.setToolTip("Impor protein dari RCSB PDB (Ctrl+Shift+P)")
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
        for _ in range(2):
            sp = QWidget()
            sp.setSizePolicy(sp.sizePolicy().horizontalPolicy().Expanding, sp.sizePolicy().verticalPolicy().Preferred)
            if _ == 0:
                tb.addWidget(sp)
                ruang = QWidget()
                h = QHBoxLayout(ruang)
                h.setContentsMargins(0, 0, 0, 0)
                h.setSpacing(0)
                self.grp_ruang = QButtonGroup(self)
                for k, t in RUANG:
                    b = QPushButton(t)
                    b.setObjectName("ruang")
                    b.setCheckable(True)
                    b.setProperty("ruang", k)
                    b.setToolTip({"siapkan": "Protein, ligan, dan area docking (langkah 1-3)",
                                  "docking": "Mesin, ketelitian, jalankan, antrean (langkah 4)",
                                  "analisis": "Hasil, interaksi, diagram, sifat ligan, statistik (langkah 5)"}[k])
                    b.clicked.connect(lambda _=False, k=k: self.atur_ruang(k))
                    self.grp_ruang.addButton(b)
                    h.addWidget(b)
                tb.addWidget(ruang)
            else:
                tb.addWidget(sp)
        ikon_saja(self.a_tema)

        # toolbar kecil di atas viewport: gaya cepat
        bv = self.bar_view
        bv.setObjectName("toolbar_view")
        bv.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.grp_gaya = QActionGroup(self)
        for k, t in (("cartoon", "Kartun"), ("sticks", "Stick"), ("ballstick", "Bola-stick"), ("surface", "Permukaan")):
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
        bv.addAction(self.a_seret)
        bv.addAction(self.a_geser)
        bv.addSeparator()
        self.a_fok_pose = QAction("Fokus Pose", self, triggered=self.fokus_pose_aktif)
        self.a_fok_pose.setToolTip("Pusatkan kamera ke pose aktif di binding site")
        self.a_fok_site = QAction("Fokus Site", self, triggered=self.fokus_binding_site)
        self.a_fok_site.setToolTip("Pusatkan kamera ke area binding pocket / grid box")
        self.a_bersih = QAction("Bersihkan", self, triggered=self.bersihkan_objek_mentah)
        self.a_bersih.setToolTip("Sembunyikan molekul air, ion, dan ligan input mentah")
        bv.addAction(self.a_fok_pose)
        bv.addAction(self.a_fok_site)
        bv.addAction(self.a_bersih)
        bv.addSeparator()
        b = QToolButton()
        b.setText("Render ▾")
        b.setToolTip("Gaya render 3D: garis tepi ala ilustrasi jurnal dan bayangan sekitar (ambient occlusion)")
        b.setPopupMode(QToolButton.InstantPopup)
        b.setMenu(self.m_render)
        bv.addWidget(b)

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
        self.b_antre = QToolButton()
        self.b_antre.setObjectName("antreanRingkas")
        self.b_antre.setCheckable(True)
        self.b_antre.setText("Antrean: kosong  ▴")
        self.b_antre.setToolTip("Tampilkan/sembunyikan panel Antrean, Log, dan Pesan")
        self.b_antre.toggled.connect(self._bawah_oleh_pengguna)
        sb.addWidget(self.s_gpu)
        sb.addWidget(self.s_prog)
        sb.addWidget(self.s_atom, 1)
        sb.addPermanentWidget(self.s_folder)
        sb.addPermanentWidget(self.b_antre)

    # -------------------------------------------------------------- tema
    def terapkan_tema(self, mode):
        self.mode = mode
        t = theme.TOKEN[mode]
        app = QApplication.instance()
        cek = paths.APPDATA / f"cek_{mode}.png"
        if not cek.exists():
            icons.pixmap("check", "#ffffff", 12, 2).save(str(cek))
        # panah dropdown/spin/submenu: QSS tidak bisa memakai SVG dalam memori, jadi ikonnya dirender ke PNG
        berkas_ikon = {"ICON_CHECK": cek.as_posix()}
        for kunci, nama, warna in (("ICON_CHEVRON", "chevron", t["ink2"]),
                                   ("ICON_CHEVRON_REDUP", "chevron", t["mut"]),
                                   ("ICON_CHEVRON_ATAS", "chevron_atas", t["ink2"]),
                                   ("ICON_CHEVRON_KANAN", "chevron_kanan", t["ink2"])):
            f = paths.APPDATA / f"{nama}_{warna.lstrip('#')}.png"
            if not f.exists():
                icons.pixmap(nama, warna, 12, 2).save(str(f))
            berkas_ikon[kunci] = f.as_posix()
        qss = theme.qss(mode, ringkas=self.ringkas())
        for kunci, jalur in sorted(berkas_ikon.items(), key=lambda x: -len(x[0])):   # nama terpanjang dulu
            qss = qss.replace(kunci, jalur)
        app.setPalette(theme.palet(mode))
        app.setStyleSheet(qss)
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
        self.sifat.set_mode(mode)
        self.statistik.set_mode(mode)
        self.uji.set_mode(mode)
        self.awal.set_mode(mode)
        self.p_langkah.set_mode(mode)
        self.langkah.mode = mode
        self.langkah.segarkan()
        if self.proyek:
            self._muat_hasil()
        self._gambar_diagram()
        self.param.warna_warn = t["warn"]
        self.param._info_kotak()
        self.viewer.page().setBackgroundColor(t["view"])
        self.viewer.js("tema", mode == "gelap", t["view"])
        self.viewer.js("gayaRender", self._opsi_render())
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
        alat = []
        # semua GPU OpenCL (mis. Intel + NVIDIA); GPU utama (VRAM terbesar) di atas sebagai bawaan
        gpus = sorted([x for x in e.gpu if x.opencl], key=lambda x: x is not g)
        for x in gpus:
            alat.append((f"GPU · {x.nama.replace('NVIDIA GeForce ', '')}", f"gpu:{x.devnum}",
                         icons.ikon("gpu", theme.TOKEN[self.mode]["ok"])))
        alat.append((f"CPU · {e.inti} thread", "cpu", icons.ikon("cpu", theme.TOKEN[self.mode]["ink2"])))
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
            self.s_gpu.setText(f"● {g.nama} · OpenCL tidak tersedia - mode CPU")
        else:
            self.s_gpu.setText("● Tidak ada GPU - mode CPU (Vina)")
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
            from .dialogs import Wizard
            w = Wizard(e, self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())), self)
            if w.exec():
                self.st.setValue("folder_kerja", w.ed_folder.text())
                Path(w.ed_folder.text()).mkdir(parents=True, exist_ok=True)
            self.st.setValue("wizard_selesai", True)
            self.st.setValue("versi_dilihat", VERSI)      # pemasangan baru: tak perlu 'Apa yang baru'
        elif self.st.value("versi_dilihat", "") != VERSI:
            QTimer.singleShot(1200, lambda: self.apa_baru(self.st.value("versi_dilihat", "") or None))
            self.st.setValue("versi_dilihat", VERSI)
        self.s_folder.setText(self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))
        if not getattr(self, "_pembaruan_dijadwal", False):
            self._pembaruan_dijadwal = True        # deteksi() bisa dipanggil ulang dari Pengaturan
            QTimer.singleShot(8000, self._cek_pembaruan_otomatis)

    # ------------------------------------------------------------- objek
    def _fokus(self, sel):
        """Pusatkan kamera; bila tab Viewport tersembunyi, tampilkan dulu lalu fokus setelah kanvas aktif
        (WebGL tidak merender benar saat tab tersembunyi)."""
        if self.tab_tengah.currentWidget() is self.w_view and self.stak_view.currentIndex() == 0:
            self.viewer.js("fokus", sel)
            return
        self.tab_tengah.setCurrentWidget(self.w_view)
        QTimer.singleShot(250, lambda: (self.viewer.js("segarkanKanvas"), self.viewer.js("fokus", sel)))

    def fokus_binding_site(self):
        """Pusatkan kamera ke area binding site / grid box."""
        if self.box.get("pusat"):
            c = self.box["pusat"]
            self.tab_tengah.setCurrentWidget(self.w_view)
            self.viewer.js("fokusTitik", {"x": c[0], "y": c[1], "z": c[2]})
            self.statusBar().showMessage(f"Kamera difokuskan ke pusat binding site ({kit.f(c[0], 1)}, {kit.f(c[1], 1)}, {kit.f(c[2], 1)})", 4000)
        else:
            self.statusBar().showMessage("Pusat binding site / grid box belum diatur di langkah 3", 4000)

    def fokus_pose_aktif(self):
        """Pusatkan kamera ke pose yang sedang aktif."""
        if self.aktif and self.aktif in self.objek:
            o = self.objek[self.aktif]
            if o.jenis == "pose":
                self.tab_tengah.setCurrentWidget(self.w_view)
                self._fokus({"id": o.id})
                self.statusBar().showMessage(f"Kamera difokuskan ke {o.nama}", 3000)
                return
        pose_tampil = next((o for o in self.objek.values() if o.jenis == "pose" and o.tampil), None)
        if pose_tampil:
            self.tab_tengah.setCurrentWidget(self.w_view)
            self._fokus({"id": pose_tampil.id})
            self.pilih_objek(pose_tampil.id)
            self.statusBar().showMessage(f"Kamera difokuskan ke {pose_tampil.nama}", 3000)
        else:
            self.statusBar().showMessage("Belum ada pose docking yang dipilih atau tampil", 4000)

    def bersihkan_objek_mentah(self):
        """Sembunyikan air, ion, aditif, dan ligan masukan agar viewport bersih."""
        n = 0
        for oid, obj in list(self.objek.items()):
            if obj.jenis in ("air", "ion") or obj.info.get("aditif") or (
                    obj.grup == GRUP_LIGAN and not obj.info.get("ligan_asli") and not obj.info.get("kofaktor")):
                if obj.tampil:
                    self.set_tampil(oid, False)
                    self.hier.set_centang(oid, False)
                    n += 1
        self.statusBar().showMessage(f"{n} objek mentah/pelarut disembunyikan dari tampilan", 4000)

    def _perbarui_awal(self):
        """Halaman sambutan saat belum ada objek; viewer 3D begitu ada struktur."""
        if not self.viewer._siap:
            return
        kosong = not self.objek
        dari_awal = self.stak_view.currentIndex() == 1
        self.stak_view.setCurrentIndex(1 if kosong else 0)
        if kosong:
            self.awal.set_terakhir(self.st.value("proyek_terakhir", ""))
        elif dari_awal:   # kanvas baru terlihat: ukur ulang lalu pusatkan (dua kali: sebelum & sesudah model dimuat)
            for ms in (250, 900):
                QTimer.singleShot(ms, lambda: self.viewer.js("ukurUlang"))

    def _aksi_awal(self, k):
        {"rcsb": lambda: self.ambil(0), "buka": self.buka_berkas, "proyek": lambda: self.buka_proyek(),
         "terakhir": lambda: self.buka_proyek(self.st.value("proyek_terakhir", "")),
         "tutorial": lambda: self.buka_panduan("Tutorial_Docking_VirmoLab.pdf"),
         "panduan": lambda: self.buka_panduan("panduan"), "templat": self.proyek_templat, "tur": self.tur}[k]()

    def tambah_objek(self, daftar, fokus=True):
        kosong = not self.objek
        if daftar and not self.objek:
            self.objek.update({o.id: o for o in daftar})
            self._perbarui_awal()
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
            terlihat = next((o for o in daftar if o.jenis == "protein" and o.tampil), None)
            if kosong:
                # sesi baru/proyek dibuka: pusatkan semua objek terlihat setelah kanvas berukuran final.
                # (fokus beranimasi ke protein mentah yang tersembunyi dulu menimpa ukurUlang -> kamera meleset)
                if self.tab_tengah.currentWidget() is not self.w_view:
                    self.tab_tengah.setCurrentWidget(self.w_view)
                QTimer.singleShot(1000, lambda: self.viewer.js("fokusSemua"))
            else:
                self._fokus({"id": (terlihat or prot).id})
            self.hier.pilih_objek(prot.id)
        self._hitung_atom()
        self.segarkan_langkah()
        self._kirim_id_seret()

    def _hitung_atom(self):
        n = sum(o.info.get("atom", 0) or 0 for o in self.objek.values())
        self.s_atom.setText(f"{len(self.objek)} objek · {n} atom")

    def set_tampil(self, oid, on):
        o = self.objek.get(oid)
        if o:
            o.tampil = on
            self.viewer.tampil(o, molekul.spek_viewer(o))
            self._kirim_id_seret()
            if self._aktif_inter and oid in (self._aktif_inter["oid"], self._aktif_inter["rec"]):
                self._tampilkan_interaksi()

    def ubah_gaya(self, oid, gaya):
        o = self.objek.get(oid)
        if o:
            self._catat("gaya", oid, copy.deepcopy(o.gaya))
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
                     ("Sumber", o.sumber or "-"), ("Rantai", ", ".join(o.rantai)),
                     ("Residu", i.get("residu")), ("Atom", i.get("atom"))]
            if i.get("siap_docking") and self.proyek and self.proyek.reseptor:
                r = self.proyek.reseptor
                baris += [("Metode", r.get("metode")), ("Ion logam", ", ".join(r.get("logam") or []) or "-"),
                          ("Residu dibuang", ", ".join(r.get("dibuang") or []) or "-"), ("PDBQT", r.get("pdbqt"))]
            if i.get("resolusi"):
                baris.append(("Resolusi", kit.f(i["resolusi"], 2, "Å")))
            m = i.get("alphafold")
            if m:
                fr = m.get("fraksi") or {}
                baris += [("Model", f"AlphaFold {m.get('entri')} v{m.get('versi')}"),
                          ("UniProt", f"{m.get('aksesi')} · {m.get('nama')} ({m.get('organisme')})"),
                          ("pLDDT rerata", f"{m.get('plddt_rerata')} (> 90: {fr.get('sangat tinggi', 0):.0%}, "
                                           f"< 50: {fr.get('sangat rendah', 0):.0%})")]
                if m.get("n_dibuang"):
                    baris.append(("Dipangkas", f"{m['dibuang']} (pLDDT < {m['ambang']:.0f})"))
        elif o.jenis in ("ligan", "pose"):
            baris = [("Jenis", "Ligan" if o.jenis == "ligan" else "Pose docking"), ("Sumber", o.sumber or "-"),
                     ("Rumus", i.get("rumus", "-")), ("Massa molekul", kit.f(i.get("mw", 0), 2, "g/mol")),
                     ("Atom berat", i.get("atom_berat", "-"))]
            for k, t in (("torsi", "Ikatan rotasi"), ("donor", "Donor ikatan H"), ("akseptor", "Akseptor ikatan H"),
                         ("logp", "LogP (Crippen)"), ("tpsa", "TPSA (Å²)"), ("smiles", "SMILES")):
                if k in i:
                    baris.append((t, i[k]))
            if i.get("ligan_asli"):
                baris.append(("Catatan", "Ligan asli kristal - bisa dipakai untuk pusat grid dan validasi redocking"))
            if i.get("siap_docking"):
                baris.append(("Preparasi", f"{i.get('status', 'siap')}" + (f" - {i['keterangan']}" if i.get("keterangan") else "")))
                baris.append(("PDBQT", f"ligan/pdbqt/{i.get('lid')}.pdbqt"))
            if i.get("skor_lokal") is not None and o.jenis != "pose":
                baris.append(("Skor lokal (kcal/mol)", kit.f(i["skor_lokal"])))
                baris.append(("Arti skor lokal", i.get("skor_lokal_ket")
                              or "Minimisasi di tempat (Vina). Bukan ΔG docking."))
            if o.jenis == "pose":
                baris = [("Jenis", "Pose docking"), ("Ligan", i.get("ligan")), ("Mesin", i.get("mesin")),
                         ("Job", i.get("job"))]
                kov = i.get("kovalen")
                if kov:   # skor aduk-reseptor, bukan ΔG ikatan; Ki dan RMSD ke konformer awal tidak bermakna
                    baris += [("Skor kovalen (kcal/mol)", kit.f(i.get("energi", 0))),
                              ("Residu kovalen", kov), ("Gugus reaktif", i.get("warhead") or "-")]
                else:
                    baris += [("ΔG (kcal/mol)", kit.f(i.get("energi", 0))), ("Ki perkiraan", id_angka(i.get("ki") or "–"))]
                if i.get("klaster"):
                    baris.append(("Ukuran klaster", i["klaster"]))
                if i.get("residu_flex") and not kov:
                    baris.append(("Residu fleksibel", ", ".join(i["residu_flex"])))
                if i.get("rmsd_kristal") is not None:
                    baris.append(("RMSD ke kristal (Å)", kit.f(i["rmsd_kristal"])))
                if not kov and i.get("rmsd_ref") is not None and i.get("rmsd_ref", -1) >= 0:
                    baris.append(("RMSD ke masukan (Å)", kit.f(i["rmsd_ref"])))
                if i.get("rmsd_lb") or i.get("rmsd_ub"):
                    baris.append(("RMSD l.b. / u.b. (Å)", f"{kit.f(i.get('rmsd_lb', 0))} / {kit.f(i.get('rmsd_ub', 0))}"))
                if i.get("skor_lokal") is not None:
                    baris.append(("Skor lokal (kcal/mol)", kit.f(i["skor_lokal"])))
                    baris.append(("Arti skor lokal", i.get("skor_lokal_ket")
                                  or "Minimisasi di tempat (Vina). Bukan ΔG docking."))
                if i.get("peringkat") == 1 and self.proyek:
                    j = self.pelaksana.cari(i.get("job"))
                    lj = next((x for x in (j or {}).get("ligan", []) if x["id"] == i.get("lid")), None)
                    q = (lj or {}).get("qc")
                    if q:
                        from ..core import qc
                        baris.append(("PoseBusters", qc.teks_sel(q)))
                        baris += [("  ✗", g) for g in q.get("gagal") or []]
        else:
            baris = [("Jenis", o.jenis.capitalize()), ("Jumlah", i.get("jumlah", "-"))]
        self.prop.tampil(f"{o.nama}", baris)
        if o.jenis == "pose":
            from ..core import kofolding
            st_b = kofolding.status_boltz()
            j = self.pelaksana.cari(i.get("job"))
            lj = next((x for x in (j or {}).get("ligan", []) if x["id"] == i.get("lid")), None)
            self.prop.muat_kofolding((lj or {}).get("kofolding"), st_b, i)
            if not o.tampil:
                self.set_tampil(o.id, True)
                self.hier.set_centang(o.id, True)
            if not self.a_inter.isChecked():
                self.a_inter.setChecked(True)
            self._gambar_syarat(o)
            self.analisis_objek(o)
            self._tampilkan_interaksi()
        elif o.jenis == "ligan":
            if o.grup == GRUP_LIGAN:
                self.statusBar().showMessage(
                    "Ligan ini adalah molekul masukan (pra-docking) di koordinat asal. Pose docking di dalam binding site ada di grup 'Hasil'.",
                    6000
                )
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
            ("Objek", o.nama), ("Residu", f"{a.get('resn', '')} {a.get('resi', '')}"), ("Rantai", a.get("chain") or "-"),
            ("Atom", f"{a.get('atom', '')} ({a.get('elem', '')})"), ("Serial", a.get("serial")),
            ("Koordinat (Å)", f"{a['x']:.3f}  {a['y']:.3f}  {a['z']:.3f}")])
        self.viewer.js("sorot", o.id, {"chain": a.get("chain"), "resi": a.get("resi")})
        self.residu_terpilih = (o.id, [(a.get("chain"), a.get("resi"))])

    def _kirim_id_seret(self):
        seret = getattr(self, "a_seret", None) and self.a_seret.isChecked()
        geser = getattr(self, "a_geser", None) and self.a_geser.isChecked()
        if not seret and not geser:
            return
        ids = [o.id for o in self.objek.values() if o.jenis in ("ligan", "pose") and o.tampil]
        self.viewer.js("aturSeret", ids)

    def _atom_diseret(self, info):
        o = self.objek.get(info.get("id"))
        if not o or o.jenis not in ("ligan", "pose"):
            return
        if self._geser_jalan:
            self.statusBar().showMessage("Masih menyusun ulang geseran sebelumnya.", 4000)
            return
        self._geser_jalan = True
        utuh = bool(info.get("utuh"))
        self.statusBar().showMessage("Menyusun ulang ligan yang digeser…" if utuh
                                     else "Menyusun ulang atom yang digeser…", 8000)
        rec = ""
        pr = self.proyek
        jalur = (pr.reseptor or {}).get("pdbqt") if pr and pr.reseptor else None
        if jalur and pr.p(jalur).exists():
            rec = pr.p(jalur).read_text(encoding="utf-8", errors="replace")
        salin = (o.teks, o.fmt, dict(info), rec, utuh)

        def geser(_lapor, paket=salin):      # jangan dinamai 'kerja': menutupi modul ui.kerja
            from ..core import lokal
            fn = lokal.geser_utuh if paket[4] else lokal.geser_atom
            return fn(paket[0], paket[1], paket[2], paket[3])

        def jadi(h, oid=o.id):
            self._geser_jalan = False
            self._sesudah_geser(oid, h)

        def gagal(e):
            self._geser_jalan = False
            self._galat(str(e).splitlines()[0])

        kerja.jalankan(geser, selesai=jadi, galat=gagal)

    def _sesudah_geser(self, oid, h):
        o = self.objek.get(oid)
        if not o:
            return
        self._catat("koordinat", oid, {"teks": o.teks, "fmt": o.fmt,
                                       "skor_lokal": o.info.get("skor_lokal"),
                                       "skor_lokal_ket": o.info.get("skor_lokal_ket")})
        o.teks, o.fmt = h["teks"], h["fmt"]
        if h.get("energi") is not None:
            o.info["skor_lokal"] = round(float(h["energi"]), 2)
            o.info["skor_lokal_ket"] = "Minimisasi di tempat (Vina). Bukan ΔG docking."
        else:
            o.info.pop("skor_lokal", None)
            o.info.pop("skor_lokal_ket", None)
        self.viewer.muat(o)
        self.viewer.tampil(o, molekul.spek_viewer(o))
        if self.aktif == oid:
            self.pilih_objek(oid)
        self.statusBar().showMessage(h["pesan"], 8000)
        self.log.tulis(h["pesan"])
        self.minta_simpan()

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
        if aksi == "sematkan":
            on = not o.info.get("sematkan")
            o.info["sematkan"] = on
            self.hier.set_sematkan(oid, on)
            if on and not o.tampil:
                self.set_tampil(oid, True)
                self.hier.set_centang(oid, True)
            self.statusBar().showMessage(f"{o.info.get('ligan', '')} {o.nama}: "
                                         + ("disematkan" if on else "tidak disematkan"), 4000)
            self.minta_simpan()
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
                self._fokus({"id": oid, "chain": nilai[2], "resi": nilai[3]})
            elif nilai[0] == "rantai":
                self._fokus({"id": oid, "chain": nilai[2]})
            else:
                self._fokus({"id": oid})
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
            self.ke_langkah(2)
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
        elif aksi == "ketcher":
            self.gambar_ligan(o)
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
            self.viewer.js("kontribusi", None, [])
            self._aktif_inter = None
            self.p_inter.kosong()
        if oid in self.objek:
            self.viewer.hapus(oid)
            self.hier.hapus(oid)
            del self.objek[oid]
            self._hitung_atom()
            self.segarkan_langkah()
            self._perbarui_awal()

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
        from .dialogs import DialogAmbil, DialogProgresUnduh
        d = DialogAmbil(self, tab)
        if not d.exec():
            return
        req = d.permintaan()
        if not req:
            return
        jenis, isi = req[0], req[1]
        opsi = req[2] if len(req) > 2 else {}
        total = len(isi)

        nama_label = {
            "rcsb": "RCSB PDB",
            "pubchem": "PubChem",
            "alphafold": "AlphaFold DB",
            "smiles": "SMILES",
        }.get(jenis, jenis.upper())

        dlg_prog = DialogProgresUnduh(f"Mengunduh dari {nama_label}", total, self)

        def kerjakan(lapor):
            from concurrent.futures import ThreadPoolExecutor, as_completed
            hasil = []
            gagal = []

            if jenis == "pubchem" and total > 1:
                def unduh_satu(s):
                    if dlg_prog.dibatalkan:
                        return None, s, "Dibatalkan"
                    try:
                        res = molekul.unduh_pubchem(s)
                        return res, s, None
                    except Exception as e:
                        return None, s, str(e)

                selesai_count = 0
                max_w = min(6, total)
                with ThreadPoolExecutor(max_workers=max_w) as executor:
                    futures = {executor.submit(unduh_satu, x): x for x in isi}
                    for f in as_completed(futures):
                        if dlg_prog.dibatalkan:
                            break
                        res, nama_senyawa, err = f.result()
                        selesai_count += 1
                        if res:
                            hasil += res
                            lapor.log.emit(f"✓ Diambil: {nama_senyawa}")
                        else:
                            gagal.append(f"{nama_senyawa} ({err})")
                            lapor.log.emit(f"✕ Gagal: {nama_senyawa} - {err}")
                        lapor.progres.emit(selesai_count, total, f"Selesai: {nama_senyawa} ({selesai_count}/{total})")
            else:
                for i, x in enumerate(isi, 1):
                    if dlg_prog.dibatalkan:
                        break
                    lapor.progres.emit(i - 1, total, f"Menghubungi server: {x}…")
                    try:
                        if jenis == "rcsb":
                            objs, teks, fmt = molekul.unduh_rcsb(x)
                            hasil += objs
                        elif jenis == "alphafold":
                            from ..core import alphafold
                            objs, teks, meta = alphafold.unduh(x, lapor=lapor, **opsi)
                            hasil += objs
                        elif jenis == "pubchem":
                            hasil += molekul.unduh_pubchem(x)
                        else:
                            bag = x.split()
                            hasil += molekul.dari_smiles(bag[0], bag[1] if len(bag) > 1 else None)
                        lapor.log.emit(f"✓ Diambil: {x}")
                    except Exception as e:
                        gagal.append(f"{x} ({e})")
                        lapor.log.emit(f"✕ Gagal: {x} - {e}")
                    lapor.progres.emit(i, total, f"Selesai: {x} ({i}/{total})")

            return hasil, gagal

        def saat_progres(saat_ini, tot, teks):
            dlg_prog.set_progres(saat_ini, tot, teks)

        def saat_selesai(data):
            daftar, gagal = data
            dlg_prog.close()
            self._objek_unduhan(daftar)
            pesan = f"✓ Berhasil mengunduh {len(daftar)} molekul dari {nama_label}."
            if gagal:
                pesan += f" ({len(gagal)} gagal, periksa Log)"
            self.statusBar().showMessage(pesan, 6000)

        def saat_galat(g):
            dlg_prog.close()
            self._galat(g)

        self.statusBar().showMessage(f"Sedang mengunduh {total} item dari {nama_label}…")
        kerja.jalankan(kerjakan, selesai=saat_selesai, galat=saat_galat, log=self.log.tulis, progres=saat_progres)
        dlg_prog.exec()

    def _objek_unduhan(self, daftar):
        self.tambah_objek(daftar)
        for o in daftar:
            m = o.info.get("alphafold")
            if not m:
                continue
            fr = m.get("fraksi") or {}
            self.pesan.tulis(
                f"AlphaFold {m['entri']} v{m['versi']} - {m['nama']} ({m['organisme']}): pLDDT rerata "
                f"{m['plddt_rerata']}; sangat tinggi {fr.get('sangat tinggi', 0):.0%}, yakin {fr.get('yakin', 0):.0%}, "
                f"rendah {fr.get('rendah', 0):.0%}, sangat rendah {fr.get('sangat rendah', 0):.0%}."
                + (f" Dipangkas (pLDDT < {m['ambang']:.0f}): {m['dibuang']}." if m.get("n_dibuang") else ""))
            self.pesan.tulis("AlphaFold: model prediksi tanpa ligan/kofaktor/ion - rantai samping kantong bisa "
                             "berbeda dari bentuk terikat. Periksa pLDDT di kantong, pertimbangkan validasi dengan "
                             "ligan pembanding, dan sebutkan sumber model di metode.")
            self._tampil_bawah(True)
            self.d_pesan.raise_()

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
        self._catat("kotak", None, self._potret_kotak())
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
        self.segarkan_langkah()
        if sumber:
            self.log.tulis(f"Grid box: {sumber} · pusat {self.box['pusat']} · ukuran {self.box['ukuran']}")
        self._cek_plddt_kotak()

    def _cek_plddt_kotak(self):
        """Model AlphaFold: peringatkan bila residu di dalam grid box ber-pLDDT rendah (kantong kurang andal)."""
        o = next((x for x in self.objek.values() if x.jenis == "protein" and x.info.get("alphafold")
                  and x.info.get("siap_docking")), None) \
            or next((x for x in self.objek.values() if x.jenis == "protein" and x.info.get("alphafold")), None)
        if not o or not self.box.get("pusat"):
            return
        from ..core import alphafold
        h = alphafold.plddt_di_kotak(o.teks, self.box["pusat"], self.box["ukuran"])
        if not h:
            return
        rerata, n, rendah = h
        teks = f"pLDDT di grid box: rerata {rerata} ({n} residu, {rendah} < 70)"
        self.log.tulis(teks)
        if rerata < 70 or rendah > n * 0.25:
            self.pesan.tulis(teks + " - keyakinan model AlphaFold di area docking rendah; pose dan ΔG kurang andal. "
                             "Pertimbangkan kantong lain, struktur eksperimen, atau validasi dengan ligan pembanding.")

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
                self._galat("Pilih residu dulu: klik atom di viewport atau pilih residu di panel Objek "
                            "(Ctrl+klik untuk beberapa residu).")
                return
            c = [sum(p[i] for p in xs) / len(xs) for i in range(3)]
            self._atur_kotak(c, sumber=f"pusat {len(res)} residu terpilih")
        elif k == "sesuai":
            o = self.objek.get(self.aktif)
            if not o or o.jenis not in ("ligan", "pose"):
                self._galat("Pilih ligan di panel Objek dulu.")
                return
            self.box_ke_objek(o, tepi=8.0)
        elif k == "fleksibel":
            self.atur_fleksibel()
        elif k == "kovalen":
            self.atur_kovalen()
        elif k == "kantong":
            self.deteksi_kantong()
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

    def atur_fleksibel(self):
        """Pilih residu fleksibel -> Meeko memisah reseptor kaku + flex (berkas di reseptor/)."""
        pr = self.proyek
        rec = (pr.reseptor or {}) if pr else {}
        siap = next((x for x in self.objek.values() if x.jenis == "protein" and x.info.get("siap_docking")), None)
        if not rec or not siap:
            self._galat("Siapkan reseptor dulu (langkah 1), lalu atur grid box (langkah 3).")
            return
        if not self.box.get("pusat"):
            self._galat("Atur grid box dulu (langkah 3): calon residu fleksibel diambil dari kantong di dalam kotak.")
            return
        sumber = rec.get("meeko") or (rec.get("bersih") if not rec.get("protonasi") else None)
        if not sumber or not pr.p(sumber).exists():
            self._galat("Reseptor ini disiapkan dengan versi lama. Siapkan ulang reseptor (langkah 1) agar residu "
                        "fleksibel bisa dibuat.")
            return
        acuan, nama_acuan = None, ""
        asli = [o for o in self.objek.values() if o.jenis == "ligan" and o.info.get("ligan_asli") and o.fmt == "pdb"]
        if asli:
            o = max(asli, key=lambda o: o.info.get("atom_berat", 0))
            acuan, nama_acuan = self._koordinat(o), o.nama
        from .dialog_fleksibel import DialogFleksibel
        fx = rec.get("fleksibel") or {}
        d = DialogFleksibel(siap.teks, self.box, acuan, nama_acuan,
                            terpilih=fx.get("residu") if fx.get("aktif") else (), parent=self)
        if not d.exec():
            return
        if d.matikan:
            rec.pop("fleksibel", None)
            self.param.set_fleksibel([])
            self.log.tulis("Residu fleksibel dimatikan: docking memakai reseptor kaku.")
            self.minta_simpan()
            return
        residu = d.residu()
        if not residu:
            return
        from ..core import prep_reseptor as prep
        teks_meeko = pr.p(sumber).read_text(encoding="utf-8")
        teks_pdbqt = pr.p(rec["pdbqt"]).read_text(encoding="utf-8")
        self.statusBar().showMessage("Membuat residu fleksibel (Meeko)…")
        kerja.jalankan(lambda lapor: prep.buat_fleksibel(teks_meeko, teks_pdbqt, residu),
                       selesai=lambda h: self._fleksibel_siap(h),
                       galat=lambda g: (self.statusBar().clearMessage(),
                                        self._galat("Residu fleksibel gagal dibuat:\n" + g)))

    def _fleksibel_siap(self, h):
        from ..core import prep_reseptor as prep
        kaku, flex, ok, gagal = h
        pr = self.proyek
        pr.p("reseptor", "reseptor_kaku.pdbqt").write_text(kaku, encoding="utf-8")
        pr.p("reseptor", "flex.pdbqt").write_text(flex, encoding="utf-8")
        label = [self._label_residu(r) for r in ok]
        pr.reseptor["fleksibel"] = {"aktif": True, "residu": ok, "label": label, "torsi": prep.torsi_flex(flex),
                                    "kaku": "reseptor/reseptor_kaku.pdbqt", "flex": "reseptor/flex.pdbqt"}
        self.param.set_fleksibel(label)
        if pr.reseptor.pop("kovalen", None):
            self.param.set_kovalen(None)
            self.pesan.tulis("Docking kovalen dimatikan karena residu fleksibel diaktifkan (keduanya tidak bisa "
                             "dipakai bersamaan).")
        self.statusBar().showMessage(f"Residu fleksibel: {len(ok)} residu, {prep.torsi_flex(flex)} torsi.", 8000)
        self.log.tulis(f"Residu fleksibel: {', '.join(label)} ({prep.torsi_flex(flex)} torsi) → reseptor/flex.pdbqt")
        if gagal:
            self.pesan.tulis("Residu fleksibel dilewati: " + "; ".join(gagal))
        self.pesan.tulis("Docking berikutnya memakai reseptor fleksibel (" + ", ".join(label) + "). ΔG dengan residu "
                         "fleksibel tidak sebanding langsung dengan docking kaku; bandingkan ligan dalam pengaturan "
                         "yang sama dan sebutkan residu fleksibel di metode.")
        self.minta_simpan()

    def atur_kovalen(self):
        """Pilih residu nukleofil -> reseptor kaku tanpa rantai samping residu tsb (aduk dibuat saat docking)."""
        pr = self.proyek
        rec = (pr.reseptor or {}) if pr else {}
        siap = next((x for x in self.objek.values() if x.jenis == "protein" and x.info.get("siap_docking")), None)
        if not rec or not siap:
            self._galat("Siapkan reseptor dulu (langkah 1), lalu atur grid box (langkah 3).")
            return
        if not self.box.get("pusat"):
            self._galat("Atur grid box dulu (langkah 3): residu sasaran kovalen dipilih dari dalam kotak.")
            return
        sumber = rec.get("meeko") or (rec.get("bersih") if not rec.get("protonasi") else None)
        if not sumber or not pr.p(sumber).exists():
            self._galat("Reseptor ini disiapkan dengan versi lama. Siapkan ulang reseptor (langkah 1) agar docking "
                        "kovalen bisa diatur.")
            return
        ligan = []
        for l in pr.ligan_siap():
            try:
                ligan.append((l["nama"], pr.p(l["pdbqt"]).read_text()))
            except OSError:
                pass
        from .dialog_kovalen import DialogKovalen
        kv = rec.get("kovalen") or {}
        d = DialogKovalen(siap.teks, self.box, ligan, terpilih=kv.get("residu") if kv.get("aktif") else None,
                          parent=self)
        if not d.exec():
            return
        if d.matikan:
            rec.pop("kovalen", None)
            self.param.set_kovalen(None)
            self.log.tulis("Docking kovalen dimatikan: docking kembali non-kovalen.")
            self.minta_simpan()
            return
        p = d.pilihan()
        if not p:
            return
        from ..core import kovalen
        teks_meeko = pr.p(sumber).read_text(encoding="utf-8")
        teks_pdbqt = pr.p(rec["pdbqt"]).read_text(encoding="utf-8")
        self.statusBar().showMessage("Menyiapkan reseptor untuk docking kovalen (Meeko)…")
        kerja.jalankan(lambda lapor: kovalen.siapkan_reseptor(teks_meeko, teks_pdbqt, p[0]),
                       selesai=self._kovalen_siap,
                       galat=lambda g: (self.statusBar().clearMessage(),
                                        self._galat("Docking kovalen gagal diatur:\n" + g)))

    def _kovalen_siap(self, h):
        pr = self.proyek
        rantai, _, resi = h["residu"].partition(":")
        f = pr.p("reseptor", f"reseptor_kovalen_{rantai}{resi}.pdbqt")
        f.write_text(h["kaku_teks"], encoding="utf-8")
        label = self._label_residu(h["residu"])
        pr.reseptor["kovalen"] = {"aktif": True, "residu": h["residu"], "resn": h["resn"], "label": label,
                                  "kaku": pr.rel(f), "ca": h["ca"], "cb": h["cb"]}
        self.param.set_kovalen(label)
        if pr.reseptor.pop("fleksibel", None):
            self.param.set_fleksibel([])
            self.pesan.tulis("Residu fleksibel dimatikan karena docking kovalen diaktifkan (keduanya tidak bisa "
                             "dipakai bersamaan).")
        self.statusBar().showMessage(f"Docking kovalen aktif: {label}.", 8000)
        self.log.tulis(f"Docking kovalen: residu sasaran {label} → {pr.rel(f)}")
        self.pesan.tulis(f"Docking berikutnya bersifat kovalen ke {label} (AutoDock-GPU). Ligan tanpa gugus reaktif "
                         "yang cocok dilewati. Skor kovalen adalah energi aduk-reseptor, bukan ΔG ikatan; bandingkan "
                         "hanya antar-ligan kovalen pada residu yang sama dan sebutkan metode tethered di metode.")
        self.minta_simpan()

    def _label_residu(self, rid):
        """'A:25' -> 'ASP25 A' dari reseptor siap docking."""
        c, _, i = rid.partition(":")
        o = next((x for x in self.objek.values() if x.jenis == "protein" and x.info.get("siap_docking")), None)
        for r in (o.rantai.get(c, []) if o else []):
            if str(r[1]) == i:
                return f"{r[0]}{i} {c}"
        return rid

    def deteksi_kantong(self):
        """P2Rank pada protein (siap docking diutamakan) -> dialog daftar kantong -> grid box."""
        from ..core import p2rank
        if not p2rank.tersedia():
            self._galat("P2Rank atau Java (folder bin/p2rank, bin/jre) tidak ditemukan. Pasang ulang VirmoLab.")
            return
        o = next((x for x in self.objek.values() if x.jenis == "protein" and x.info.get("siap_docking")), None) \
            or next((x for x in self.objek.values() if x.jenis == "protein"), None)
        if not o:
            self._galat("Belum ada protein. Muat protein di langkah 1.")
            return
        import tempfile
        folder = Path(tempfile.mkdtemp(prefix="p2rank_", dir=str(paths.CACHE)))
        self.statusBar().showMessage(f"P2Rank mencari kantong pada {o.nama}… (±10-60 detik)")
        self.log.tulis(f"P2Rank: {o.nama}")
        af = bool(o.info.get("alphafold")) or o.sumber.startswith("AlphaFold")
        if af:
            self.log.tulis("P2Rank: model AlphaFold -> konfigurasi 'alphafold' (tanpa fitur B-factor/pLDDT)")
        kerja.jalankan(lambda lapor: p2rank.prediksi(o.teks, folder, konfigurasi="alphafold" if af else None),
                       selesai=lambda h: self._kantong_siap(o, h),
                       galat=lambda g: (self.statusBar().clearMessage(), self._galat(f"Deteksi kantong gagal: {g}")))

    def _kantong_siap(self, o, kantong):
        from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem,
                                       QVBoxLayout)
        from ..core import p2rank
        self.statusBar().showMessage(f"P2Rank: {len(kantong)} kantong ditemukan.", 6000)
        if not kantong:
            self._galat("P2Rank tidak menemukan kantong pada protein ini.")
            return
        self.log.tulis("P2Rank: " + "; ".join(f"#{k['peringkat']} skor {k['skor']:.2f} prob {k['prob']:.2f} "
                                             f"({len(k['residu'])} residu)" for k in kantong[:5]))
        # tampilkan pusat kantong di viewport (bola buram bernomor)
        self.viewer.js("kantong", [{"pusat": k["pusat"], "nomor": k["peringkat"]} for k in kantong[:10]])
        d = QDialog(self)
        d.setWindowTitle("Kantong pengikatan (P2Rank)")
        d.resize(640, 380)
        v = QVBoxLayout(d)
        t = QTableWidget(len(kantong), 5)
        t.setHorizontalHeaderLabels(["#", "Skor", "Probabilitas", "Residu", "Residu kantong"])
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        lab = {}
        for b in o.teks.splitlines():
            if b.startswith("ATOM"):
                lab[(b[21].strip(), b[22:26].strip())] = f"{b[17:20].strip()}{b[22:26].strip()}"
        for i, k in enumerate(kantong):
            for j, x in enumerate((str(k["peringkat"]), f"{k['skor']:.2f}", f"{k['prob']:.2f}", str(len(k["residu"])),
                                   " ".join(lab.get(r, f"{r[0]}{r[1]}") for r in k["residu"][:30]))):
                t.setItem(i, j, QTableWidgetItem(x))
        t.resizeColumnsToContents()
        t.selectRow(0)
        v.addWidget(t)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Pakai kantong ini untuk grid box")
        bb.button(QDialogButtonBox.Cancel).setText("Tutup")
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        t.doubleClicked.connect(d.accept)
        v.addWidget(bb)
        ok = d.exec()
        self.viewer.js("kantong", [])
        if not ok:
            return
        k = kantong[max(0, t.currentRow())]
        sel = {(r[0], int(r[1])) for r in k["residu"] if r[1].lstrip("-").isdigit()}
        uk = p2rank.ukuran_kotak(k, self._koordinat(o, sel))
        self._atur_kotak(list(k["pusat"]), list(uk),
                         sumber=f"kantong P2Rank #{k['peringkat']} (skor {k['skor']:.2f}, {len(k['residu'])} residu)")

    def _kotak_dari_panel(self, k):
        self._catat("kotak", None, self._potret_kotak())
        self.box.update(pusat=k["pusat"], ukuran=k["ukuran"], spasi=k["spasi"])
        self._gambar_box()
        self._simpan_kotak()

    def _kotak_dari_viewer(self, k):
        self._catat("kotak", None, self._potret_kotak())
        self.box.update(pusat=k["pusat"], ukuran=k["ukuran"])
        self.param.set_kotak(self.box)
        self._simpan_kotak()

    def _simpan_kotak(self):
        if self.proyek and self.box["pusat"]:
            self.proyek.kotak = {"pusat": self.box["pusat"], "ukuran": self.box["ukuran"],
                                 "spasi": self.box.get("spasi", 0.375)}
            self.minta_simpan()

    # ------------------------------------------- urungkan / ulangi (grid box, ligan, gaya)
    def _potret_kotak(self):
        return copy.deepcopy({k: self.box.get(k) for k in ("pusat", "ukuran", "spasi")})

    def _catat(self, jenis, kunci, lama):
        """Simpan keadaan sebelum perubahan; perubahan beruntun < 1,5 s (seret/gulir) digabung jadi satu."""
        if getattr(self, "_mengurung", False) or not hasattr(self, "_riwayat"):
            return
        kini = time.monotonic()
        r = self._riwayat
        if r and r[-1][0] == jenis and r[-1][1] == kunci and kini - r[-1][3] < 1.5:
            r[-1] = (jenis, kunci, r[-1][2], kini)
        else:
            r.append((jenis, kunci, lama, kini))
            del r[:-50]
        self._maju.clear()
        self._segarkan_urung()

    def _nama_urung(self, jenis):
        return {"kotak": "grid box", "koordinat": "posisi ligan"}.get(jenis, "gaya tampilan")

    def _keadaan(self, jenis, kunci):
        if jenis == "kotak":
            return self._potret_kotak()
        o = self.objek.get(kunci)
        if not o:
            return None
        if jenis == "koordinat":
            return {"teks": o.teks, "fmt": o.fmt, "skor_lokal": o.info.get("skor_lokal"),
                    "skor_lokal_ket": o.info.get("skor_lokal_ket")}
        return copy.deepcopy(o.gaya)

    def _pulihkan(self, jenis, kunci, nilai):
        self._mengurung = True
        try:
            if jenis == "kotak":
                self.box.update(nilai)
                self._gambar_box()
                self.param.set_kotak(self.box)
                self._simpan_kotak()
            elif jenis == "koordinat":
                o = self.objek.get(kunci)
                if o is None or not isinstance(nilai, dict):
                    return False
                o.teks, o.fmt = nilai["teks"], nilai["fmt"]
                if "skor_lokal" in nilai:
                    if nilai.get("skor_lokal") is None:
                        o.info.pop("skor_lokal", None)
                        o.info.pop("skor_lokal_ket", None)
                    else:
                        o.info["skor_lokal"] = nilai["skor_lokal"]
                        o.info["skor_lokal_ket"] = nilai.get("skor_lokal_ket")
                self.viewer.muat(o)
                self.viewer.tampil(o, molekul.spek_viewer(o))
                if self.aktif == kunci:
                    self.pilih_objek(kunci)
            else:
                o = self.objek.get(kunci)
                if o is None or nilai is None:
                    return False
                o.gaya = nilai
                self.viewer.tampil(o, molekul.spek_viewer(o))
                if self.aktif == kunci:
                    self.tampilan.muat(o)
            self.minta_simpan()
            return True
        finally:
            self._mengurung = False

    def urungkan(self):
        while self._riwayat:
            jenis, kunci, lama, _t = self._riwayat.pop()
            kini = self._keadaan(jenis, kunci)
            if self._pulihkan(jenis, kunci, lama) is not False:
                self._maju.append((jenis, kunci, kini, time.monotonic()))
                self.statusBar().showMessage("Diurungkan: " + self._nama_urung(jenis), 3000)
                break
        self._segarkan_urung()

    def ulangi(self):
        while self._maju:
            jenis, kunci, nilai, _t = self._maju.pop()
            kini = self._keadaan(jenis, kunci)
            if self._pulihkan(jenis, kunci, nilai) is not False:
                self._riwayat.append((jenis, kunci, kini, 0.0))
                self.statusBar().showMessage("Diulangi: " + self._nama_urung(jenis), 3000)
                break
        self._segarkan_urung()

    def _segarkan_urung(self):
        if hasattr(self, "a_urung"):
            self.a_urung.setEnabled(bool(self._riwayat))
            self.a_ulang.setEnabled(bool(self._maju))

    def tur(self):
        from .tur import Tur
        self.atur_ruang("siapkan")
        QTimer.singleShot(150, lambda: setattr(self, "_tur", Tur(self)))

    def buka_konsol(self):
        d = getattr(self, "d_konsol", None)
        if d is None:
            from .konsol import Konsol
            self.konsol = Konsol(self)
            d = self.d_konsol = self._dock("Konsol Python", self.konsol, Qt.BottomDockWidgetArea, "dock_konsol")
            if self.d_log.isVisible():
                self.tabifyDockWidget(self.d_log, d)
        d.show()
        d.raise_()
        self.konsol.segarkan_ns()
        self.konsol.masuk.setFocus()

    def muat_plugin(self):
        """Muat ulang plugin dari folder plugin pengguna ke menu Alat › Plugin."""
        from ..core import plugin as P
        self.m_plugin.clear()
        try:
            self._plugin = P.muat(self, log=self.log.tulis)
        except Exception as e:
            self._plugin = []
            self.log.tulis(f"Plugin: gagal membaca folder plugin ({e})")
        for p in self._plugin:
            if p.galat:
                a = self.m_plugin.addAction(f"{p.nama} - gagal dimuat")
                a.setEnabled(False)
                a.setToolTip(p.galat)
                continue
            sub = self.m_plugin.addMenu(p.nama + (f" {p.versi}" if p.versi else ""))
            sub.setToolTipsVisible(True)
            for label, fn in p.aksi:
                a = sub.addAction(label, lambda p=p, label=label, fn=fn: P.jalankan(p, label, fn, self.log.tulis))
                a.setToolTip(p.keterangan or label)
        if not self._plugin:
            a = self.m_plugin.addAction("Belum ada plugin")
            a.setEnabled(False)
        self.m_plugin.addSeparator()
        self.m_plugin.addAction("Muat ulang plugin", self.muat_plugin)
        self.m_plugin.addAction("Buka folder plugin", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(P.siapkan_folder()))))

    def palet(self):
        from .palet import DialogPalet
        d = DialogPalet(self)
        d.show()
        d.kotak.setFocus()

    def atur_mode_pengguna(self, mode, simpan=True):
        """Pemula: panel Langkah tampil, Lanjutan dilipat. Ahli: panel Langkah disembunyikan, Lanjutan terbuka."""
        if simpan:
            self.st.setValue("mode_pengguna", mode)
        ahli = mode == "ahli"
        self.d_langkah.setVisible(not ahli)
        if hasattr(self, "a_rbfe"):
            self.a_rbfe.setVisible(ahli)
        self.param.b_lanjutan.setChecked(ahli)
        if simpan:
            self.statusBar().showMessage("Mode Ahli: panel Langkah disembunyikan (Tampilan › Panel untuk menampilkan), "
                                         "Ctrl+K untuk semua perintah." if ahli else
                                         "Mode Pemula: panel Langkah dan panduan per langkah ditampilkan.", 6000)

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
        self.setWindowTitle(f"{pr.nama} - VirmoLab" if pr else "VirmoLab")
        self.s_folder.setText(str(pr.folder) if pr else self.st.value("folder_kerja", ""))
        if pr:
            self.st.setValue("proyek_terakhir", str(pr.folder))
            self.st.setValue("sesi_terbuka", str(pr.folder))
        self.antrean.muat(pr.job if pr else [])
        self.uji.muat(pr.uji_grafik if pr else {})
        if self.komposer:
            self.komposer.muat(self._komposer_dari_proyek())
        self._muat_hasil()
        self._ringkasan()

    def _ringkasan(self):
        pr = self.proyek
        rec = None
        if pr and pr.reseptor:
            rec = f"{pr.reseptor.get('nama', '')} · {pr.reseptor.get('atom', 0)} atom"
        lig = pr.ligan_siap() if pr else []
        self.param.set_ringkasan(rec, len(lig), sum(1 for l in lig if l.get("status") == "peringatan"))
        fx = ((pr.reseptor or {}).get("fleksibel") or {}) if pr else {}
        self.param.set_fleksibel(fx.get("label") or fx.get("residu") or [] if fx.get("aktif") else [])
        kv = ((pr.reseptor or {}).get("kovalen") or {}) if pr else {}
        self.param.set_kovalen((kv.get("label") or kv.get("residu")) if kv.get("aktif") else None)
        self.segarkan_langkah()

    def minta_simpan(self):
        self.segarkan_langkah()
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
        from ..core import qc
        qc.tutup()
        self._simpan_diam()
        self._tutup_sesi()
        if nama.strip():
            induk = Path(self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))
            induk.mkdir(parents=True, exist_ok=True)
            self._set_proyek(Proyek.baru(induk, nama.strip()))
            self.log.tulis(f"Proyek baru: {self.proyek.folder}")

    def proyek_templat(self):
        from ..core import templat as T
        from .dialog_templat import DialogTemplat
        if self.pelaksana.sibuk() and QMessageBox.question(
                self, "Proyek baru", "Docking sedang berjalan. Job akan dijeda dan bisa dilanjutkan saat proyek "
                                     "ini dibuka lagi. Lanjutkan?") != QMessageBox.Yes:
            return
        d = DialogTemplat(self)
        if not d.exec() or not d.kunci() or not d.nama.text().strip():
            return
        t = T.cari(d.kunci())
        self.pelaksana.hentikan_semua()
        from ..core import qc
        qc.tutup()
        self._simpan_diam()
        self._tutup_sesi()
        induk = Path(self.st.value("folder_kerja", str(paths.folder_kerja_bawaan())))
        induk.mkdir(parents=True, exist_ok=True)
        self._set_proyek(Proyek.baru(induk, d.nama.text().strip()))
        self.proyek.templat = t["kunci"]
        self.param.terapkan_preset(t["preset"])
        self.log.tulis(f"Proyek baru dari templat '{t['judul']}': {self.proyek.folder}")
        self.tampil_langkah_templat()
        self.minta_simpan()
        if t["kunci"] == "contoh":
            self._muat_contoh()
        else:
            QTimer.singleShot(300, lambda: self.ambil(0))

    def tampil_langkah_templat(self):
        from ..core import templat as T
        t = T.cari(getattr(self.proyek, "templat", "") or "") if self.proyek else None
        if not t:
            return
        self.pesan.tulis(f"Templat: {t['judul']} - ketelitian {t['preset']}. Langkah:")
        for i, s in enumerate(t["langkah"], 1):
            self.pesan.tulis(f"  {i}. {s}")
        self._tampil_bawah(True)
        self.d_pesan.raise_()

    def _muat_contoh(self):
        """Proyek contoh offline: 1HSG (dibundel) + 9 inhibitor HIV-1 protease + aspirin (kontrol negatif)."""
        from ..core import templat as T
        if not T.CONTOH_PDB.exists():
            self._galat("Data contoh tidak ditemukan. Pasang ulang VirmoLab.")
            return
        self.impor([str(T.CONTOH_PDB)])

        def kerjakan(lapor):
            hasil = []
            for nama, smi in T.ligan_contoh():
                try:
                    ob = molekul.dari_smiles(smi, nama)
                    for o in ob:      # belum berpose (koordinat di titik asal): tampil setelah docking
                        o.tampil = False
                    hasil += ob
                except Exception as e:
                    lapor.log.emit(f"Contoh: {nama} gagal dibuat 3D ({e})")
            return hasil
        self.proyek.validasi = {
            "ligan": "MK1", "mesin": "AutoDock Vina", "rmsd": 1.39, "rmsd_min": 1.39,
            "energi": -11.18, "protokol": "smiles", "gnina": -11.56, "cnnscore": 0.67,
            "cnnaffinity": 8.52,
        }
        if T.CONTOH_HOMOLOG.exists():
            teks = T.CONTOH_HOMOLOG.read_text(encoding="utf-8")
            self.proyek.p("homolog_1hsg.fasta").write_text(teks, encoding="utf-8")
            n = sum(1 for b in teks.splitlines() if b.startswith(">"))
            self.log.tulis(f"Contoh: {n} homolog disalin ke homolog_1hsg.fasta. "
                           "Tempel isinya di Penelitian lanjutan › Konservasi.")
        self.log.tulis("Contoh redocking MK1 yang sudah diukur: RMSD 1,39 Å, Vina −11,18 kcal/mol, "
                       "GNINA Affinity −11,56 kcal/mol. Bukan hasil docking baru.")
        self.minta_simpan()
        kerja.jalankan(kerjakan, selesai=lambda ob: (self.tambah_objek(ob, fokus=False),
                                                     self.log.tulis(f"Contoh: {len(ob)} ligan dimuat")),
                       galat=self._galat, log=self.log.tulis)

    def _tutup_sesi(self):
        self._riwayat, self._maju = [], []
        self._segarkan_urung()
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
        self.setWindowTitle("VirmoLab")
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
        from ..core import qc
        qc.tutup()
        self._simpan_diam()
        self._tutup_sesi()
        objek, _ = pr.muat_objek()
        # Bersihkan duplikat mentah bila versi siap sudah ada di proyek
        nama_siap = {o.nama for o in objek if o.jenis == "ligan" and o.info.get("siap_docking")}
        prot_siap = {o.nama.replace(" (siap)", "") for o in objek if o.jenis == "protein" and o.info.get("siap_docking")}
        objek = [o for o in objek if not (
            (o.jenis == "ligan" and not o.info.get("siap_docking") and not o.info.get("ligan_asli") and o.nama in nama_siap) or
            (o.jenis == "protein" and not o.info.get("siap_docking") and o.nama in prot_siap)
        )]
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
        from ..core import qc
        qc_ok = qc.tersedia()
        if any(l["status"] == "selesai" and ("le" not in l or (qc_ok and (l.get("qc") or {}).get("v") != qc.VERSI))
               for j in pr.job for l in j["ligan"]):
            self.analisis_ulang()   # proyek lama: lengkapi LE/interaksi/RMSD + QC PoseBusters di latar
        dijeda = [j for j in pr.job if j["status"] == "dijeda"]
        self.log.tulis(f"Proyek dibuka: {pr.folder} · {len(objek)} objek · {len(pr.ligan_siap())} ligan siap · "
                       f"{len(pr.job)} job")
        if dijeda:
            self.pesan.tulis(f"{len(dijeda)} job terputus berstatus 'Dijeda'. Pilih job di panel Antrean lalu "
                             "klik Lanjut; ligan yang sudah selesai tidak diulang.")
            self._tampil_bawah(True)
        if getattr(pr, "templat", "") and not pr.job:     # templat belum sampai docking: ingatkan langkahnya
            self.tampil_langkah_templat()

    def _cek_pemulihan(self):
        """E1: sesi sebelumnya tidak ditutup normal -> tawarkan pemulihan."""
        f = self.st.value("sesi_terbuka", "")
        if f and Path(f, "proyek.json").exists() and not self.proyek:
            if QMessageBox.question(self, "Pulihkan pekerjaan",
                                    f"VirmoLab tidak ditutup dengan normal sebelumnya.\n\nPulihkan proyek terakhir?\n{f}"
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

    def _teks_sumber_reseptor(self, o):
        """Protein + ion + ligan asli dari sumber yang sama (untuk radius ion logam & pemeriksaan struktur)."""
        if o.info.get("siap_docking") and self.proyek and self.proyek.p("reseptor", "asli.pdb").exists():
            return self.proyek.p("reseptor", "asli.pdb").read_text(encoding="utf-8", errors="replace")
        if o.fmt != "pdb":
            return o.teks
        bagian = [o.teks] + [x.teks for x in self.objek.values()
                             if x.sumber == o.sumber and x.id != o.id and x.fmt == "pdb"
                             and (x.jenis == "ion" or (x.jenis == "ligan" and (x.info.get("ligan_asli")
                                                                                 or x.info.get("kofaktor"))))]
        return "\n".join(b for t in bagian for b in t.splitlines()
                         if b.startswith(("ATOM", "HETATM", "TER", "CRYST1"))) + "\nEND\n"

    def siapkan_reseptor(self):
        protein = [o for o in self.objek.values() if o.jenis == "protein" and not o.info.get("siap_docking")]
        if not protein:
            protein = [o for o in self.objek.values() if o.jenis == "protein"]
        if not protein:
            self._galat("Belum ada protein. Muat struktur dulu di langkah 1 (Ambil dari RCSB PDB atau Buka berkas).")
            return
        from .dialog_reseptor import DialogReseptor
        d = DialogReseptor(protein, {o.id: self._logam_dari(o) for o in protein}, self, self.aktif,
                           teks_sumber=self._teks_sumber_reseptor)
        d.r_baku.setChecked(self.st.value("prep/protonasi", "propka") == "templat")
        d.r_propka.setChecked(self.st.value("prep/protonasi", "propka") == "propka")
        d.sp_ph.setValue(float(self.st.value("prep/ph", 7.4)))
        if not d.exec():
            return
        o, opsi = d.objek(), d.opsi()
        self.st.setValue("prep/protonasi", opsi.protonasi)
        self.st.setValue("prep/ph", opsi.ph)
        teks = self._teks_sumber_reseptor(o)
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
        hp = getattr(h, "protonasi", None)
        if hp is not None:
            from ..core import protonasi
            pr.p("reseptor", "pka.csv").write_text(protonasi.csv_pka(hp), encoding="utf-8-sig")
            pr.p("reseptor", "protonasi.pqr").write_text(hp.pqr, encoding="utf-8")
        if getattr(h, "pdb_meeko", ""):
            pr.p("reseptor", "untuk_meeko.pdb").write_text(h.pdb_meeko, encoding="utf-8")
        lama_flex = ((pr.reseptor or {}).get("fleksibel") or {}).get("residu")
        lama_kov = ((pr.reseptor or {}).get("kovalen") or {}).get("label")
        pr.reseptor = {"nama": asal.nama, "sumber": asal.sumber, "pdbqt": "reseptor/reseptor.pdbqt",
                       "bersih": "reseptor/bersih.pdb", "asli": "reseptor/asli.pdb", "metode": h.metode,
                       "atom": h.atom, "residu": h.residu, "dibuang": h.dibuang, "logam": h.logam,
                       "opsi": {k: v for k, v in vars(opsi).items() if k != "sekuens"}}
        loop = getattr(h, "loop", None) or []
        if loop:
            pr.reseptor["loop"] = loop
            isi = [c for c in loop if c.get("metode") not in ("", "dibiarkan")]
            self.pesan.tulis(
                f"Residu hilang: {len(isi)} dari {len(loop)} celah dilengkapi ("
                + "; ".join(f"{c['rantai']} {c['sebelum']}–{c['sesudah']}: {c['metode']}"
                            + (f", pLDDT {c['plddt']:.0f}" if c.get("plddt") is not None else "") for c in loop[:4])
                + (" …" if len(loop) > 4 else "") + "). Rincian di reseptor/laporan_prep.txt.")
        if getattr(h, "pdb_meeko", ""):
            pr.reseptor["meeko"] = "reseptor/untuk_meeko.pdb"
        if lama_flex:
            self.pesan.tulis("Reseptor disiapkan ulang: residu fleksibel (" + ", ".join(lama_flex) + ") dinonaktifkan. "
                             "Atur ulang lewat Residu fleksibel bila masih diperlukan.")
        if lama_kov:
            self.pesan.tulis(f"Reseptor disiapkan ulang: docking kovalen ({lama_kov}) dinonaktifkan. Atur ulang lewat "
                             "Docking kovalen bila masih diperlukan.")
            self.param.set_kovalen(None)
        if hp is not None:
            pr.reseptor["protonasi"] = {"ph": hp.ph, "keadaan": [list(k) for k in hp.keadaan],
                                        "dilengkapi": hp.diperbaiki, "pka": "reseptor/pka.csv"}
            if hp.keadaan:
                self.pesan.tulis(f"Reseptor (PROPKA pH {hp.ph:.1f}): " + ", ".join(
                    f"{l} = {k}" for l, _n, k in hp.keadaan))
        for x in [x for x in self.objek.values() if x.jenis == "protein" and x.info.get("siap_docking")]:
            self.hapus_objek(x.id)
        teks = prep_reseptor.pdbqt_ke_pdb(h.pdbqt)
        if asal.info.get("alphafold"):   # pLDDT ikut ke reseptor siap (pewarnaan & cek grid box)
            from ..core import alphafold
            teks = alphafold.salin_plddt(teks, asal.teks)
            pr.reseptor["alphafold"] = asal.info["alphafold"]
        import gemmi
        nama_siap = asal.nama if asal.nama.endswith(" (siap)") else f"{asal.nama} (siap)"
        o = molekul.Objek(nama=nama_siap, jenis="protein", teks=teks, sumber=asal.sumber)
        o.rantai = molekul._hierarki(gemmi.read_pdb_string(teks))
        o.info = {"atom": h.atom, "residu": h.residu, "rantai": len(o.rantai), "siap_docking": True,
                  "metode": h.metode}
        for k in ("alphafold", "plddt"):
            if k in asal.info:
                o.info[k] = asal.info[k]
        o.gaya = dict(asal.gaya)
        self.hapus_objek(asal.id)   # Hapus protein mentah awal agar tidak menumpuk/membingungkan
        self.tambah_objek([o], fokus=False)
        self.hier.pilih_objek(o.id)
        # Sembunyikan air, ion, dan aditif mentah awal agar reseptor bersih dan tidak membingungkan
        for oid, obj in list(self.objek.items()):
            if obj.jenis in ("air", "ion") or obj.info.get("aditif"):
                if obj.tampil:
                    self.set_tampil(oid, False)
                    self.hier.set_centang(oid, False)
        self.s_prog.setText("")
        self.log.tulis(f"Reseptor siap: {h.atom} atom, {h.residu} residu, {h.metode} → {pr.p('reseptor', 'reseptor.pdbqt')}")
        for p in h.peringatan:
            self.pesan.tulis("Reseptor: " + p)
        if h.peringatan:
            self._tampil_bawah(True)
            self.d_pesan.raise_()
        self._ringkasan()
        self.minta_simpan()
        self.ke_langkah(1)   # berikutnya: ligan

    def siapkan_ligan(self):
        calon = [o for o in self.objek.values() if o.jenis == "ligan" and not o.info.get("siap_docking")]
        from .dialog_ligan import DialogLigan
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
            # Hapus objek mentah ligan (selain ligan kristal asli) agar tidak duplikat di viewport & pohon
            if asal.id in self.objek and not asal.info.get("ligan_asli"):
                self.hapus_objek(asal.id)
        self.tambah_objek(baru, fokus=False)
        self.log.tulis(f"{len(baru)} ligan siap docking disimpan di {pr.p('ligan', 'pdbqt')}")
        self._ringkasan()
        self.minta_simpan()
        self.ke_langkah(3 if self.box.get("pusat") else 2)   # berikutnya: area (atau langsung jalankan)

    # ------------------------------------------------------------ docking
    def _param_berubah(self, p):
        if self._sinkron:
            return
        if self.proyek:
            self.proyek.parameter = p
            self.minta_simpan()

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
            self._galat("Reseptor belum disiapkan. Buka langkah 1 Protein lalu klik Siapkan reseptor.")
            self.ke_langkah(0)
            return
        siap = pr.ligan_siap()
        if not siap:
            self._galat("Belum ada ligan siap docking. Buka langkah 2 Ligan lalu klik Siapkan ligan.")
            self.ke_langkah(1)
            return
        if not self.box["pusat"]:
            self._galat("Area docking belum diatur. Pilih salah satu tombol di langkah 3 (mis. 'Pusat di ligan asli').")
            self.ke_langkah(2)
            return
        pilih = set(self._ligan_terpilih())
        ligan = [l for l in siap if l["id"] in pilih] if pilih else siap
        p = self.param.parameter()
        mesin, alat = p["mesin"], p["perangkat"]
        if mesin == "adgpu" and (alat != "gpu" or not (self.env and self.env.opencl_ok)):
            mesin, alat = "vina", "cpu"
            self.pesan.tulis("AutoDock-GPU membutuhkan GPU dengan OpenCL; job dijalankan dengan AutoDock Vina (CPU).")
        if not mesinmod.tersedia(mesin):
            self._galat(f"{mesinmod.PROGRAM[mesin]} tidak ditemukan di folder bin. Pasang ulang VirmoLab.")
            return
        k = mesinmod.Kotak(pusat=self.box["pusat"], ukuran=self.box["ukuran"], spasi=self.box.get("spasi", 0.375))
        if mesin in ("adgpu", "ad4") and k.terpotong():
            if QMessageBox.question(self, "Grid box terlalu besar",
                                    "Grid box melebihi 126 titik per sumbu pada spasi ini sehingga AutoGrid akan "
                                    "memotongnya. Tetap jalankan?") != QMessageBox.Yes:
                return
        par = dict(p, nrun=p["nrun_gpu"] if mesin == "adgpu" else p["nrun_ad4"],
                   nev=p["nev_gpu"] if mesin == "adgpu" else p["nev_ad4"])
        kotak = {"pusat": k.pusat, "ukuran": k.ukuran, "spasi": k.spasi}
        kv = pr.reseptor.get("kovalen") or {}
        if kv.get("aktif"):
            self._jalankan_kovalen(ligan, mesin, alat, par, kotak, kv)
            return
        job = antreanmod.job_baru(pr, ligan, mesin, alat, par, kotak)
        self.pelaksana.tambah(job)
        self._tampil_bawah(True)
        self.segarkan_langkah()

    def _jalankan_kovalen(self, ligan, mesin, alat, par, kotak, kv):
        """Docking kovalen: aduk tiap ligan dibuat di latar, lalu job AD-GPU --flexres ditambahkan ke antrean."""
        pr = self.proyek
        if mesin != "adgpu":
            self._galat("Docking kovalen membutuhkan AutoDock-GPU dengan GPU OpenCL. Pilih mesin AutoDock-GPU di "
                        "langkah 4, atau matikan docking kovalen (langkah 3 › Docking kovalen › Matikan).")
            return
        if not pr.p(kv["kaku"]).exists():
            self._galat("Berkas reseptor kovalen tidak ditemukan. Atur ulang lewat langkah 3 › Docking kovalen.")
            return
        from ..core import kovalen

        def selesai(h):
            self.statusBar().clearMessage()
            siap, lewat = h
            if lewat:
                self.pesan.tulis(f"Docking kovalen ke {kv.get('label') or kv['residu']}: {len(lewat)} ligan dilewati - "
                                 + "; ".join(f"{n}: {a}" for n, a in lewat[:10]) + (" …" if len(lewat) > 10 else ""))
            if not siap:
                self._galat("Tidak ada ligan yang bisa dibuat aduk kovalennya (gugus reaktif tidak cocok untuk "
                            f"{kv['resn']}). Lihat panel Pesan.")
                return
            job = antreanmod.jadikan_kovalen(antreanmod.job_baru(pr, siap, mesin, alat, par, kotak), kv)
            self.pelaksana.tambah(job)
            self._tampil_bawah(True)
            self.segarkan_langkah()

        self.statusBar().showMessage("Membuat aduk kovalen ligan…")
        kerja.jalankan(lambda lapor: kovalen.siapkan_ligan_job(pr, ligan, kv, lapor), selesai=selesai,
                       galat=lambda g: (self.statusBar().clearMessage(),
                                        self._galat("Aduk kovalen gagal dibuat:\n" + g)))

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
        self.segarkan_langkah()

    def _antre_gnina(self, j, semua=False):
        """Isi kolom GNINA setelah docking. Bawaan: 10 ligan berenergi terbaik. Tidak menggagalkan job."""
        if self._gnina_tidak_ada:
            return
        pr = self.proyek
        rec = j.get("reseptor")
        if not pr or not rec or not pr.p(rec).exists():
            self.log.tulis("Kolom GNINA kosong: reseptor PDBQT tidak ada.")
            return
        from ..core import lanjutan
        calon = []
        for l in j["ligan"]:
            if l["status"] != "selesai" or l.get("gnina"):
                continue
            if not l.get("pdbqt") or not l.get("keluaran"):
                continue
            if not pr.p(l["pdbqt"]).exists() or not pr.p(l["keluaran"]).exists():
                continue
            calon.append(l)
        pilih = lanjutan.batasi_gnina(calon, semua=semua)
        sudah = {(t["jid"], t["lid"]) for t in self._gnina_antre}
        if self._gnina_sedang:
            sudah.add(self._gnina_sedang)
        n_baru = 0
        for l in pilih:
            kunci = (j["id"], l["id"])
            if kunci in sudah:
                continue
            self._gnina_antre.append({
                "jid": j["id"], "lid": l["id"], "nama": l["nama"], "mesin": j["mesin"],
                "rec": str(pr.p(rec)), "lig": str(pr.p(l["pdbqt"])),
                "out": str(pr.p(l["keluaran"])), "folder": str(pr.p("gnina", j["id"], l["id"])),
            })
            n_baru += 1
        if not n_baru:
            return
        sisa = len(calon) - len(pilih)
        if sisa:
            self.log.tulis(
                f"GNINA akan mengisi {n_baru} dari {len(calon)} ligan (10 energi terbaik). "
                "Analisis › GNINA untuk sisa ligan mengisi yang lain.")
        else:
            self.log.tulis(f"GNINA akan mengisi {n_baru} baris (skor ulang pose yang sudah ada, bukan pose baru).")
        self._gnina_berikut()

    def _gnina_sisa(self):
        if not self.proyek:
            self.statusBar().showMessage("Belum ada proyek.", 4000)
            return
        self._gnina_tidak_ada = False
        sebelum = len(self._gnina_antre)
        for j in self.proyek.job:
            if j.get("status") == "selesai" and not j.get("kovalen"):
                self._antre_gnina(j, semua=True)
        if len(self._gnina_antre) == sebelum and not self._gnina_jalan:
            self.statusBar().showMessage("Tidak ada ligan tersisa yang belum dinilai GNINA.", 5000)

    def _gnina_berikut(self):
        if self._gnina_jalan or self._gnina_tidak_ada or not self._gnina_antre:
            return
        self._gnina_jalan = True
        t = self._gnina_antre.pop(0)
        self._gnina_sedang = (t["jid"], t["lid"])

        def nilai_gnina(_lapor, tugas=t):    # jangan dinamai 'kerja': menutupi modul ui.kerja
            from pathlib import Path
            from ..core import lanjutan, mesin
            st = lanjutan.status_gnina()
            if not st["ada"]:
                return {"tidak_ada": st["pesan"]}
            pose = mesin.baca_hasil(tugas["mesin"], Path(tugas["out"]))
            if not pose or not pose[0].pdbqt:
                raise RuntimeError("Pose tidak terbaca untuk GNINA.")
            return lanjutan.nilai_gnina_pose(
                Path(tugas["rec"]).read_text(encoding="utf-8", errors="replace"),
                Path(tugas["lig"]).read_text(encoding="utf-8", errors="replace"),
                pose[0].pdbqt, tugas["folder"])

        def jadi(angka, tugas=t):
            self._gnina_jalan = False
            self._gnina_sedang = None
            if isinstance(angka, dict) and angka.get("tidak_ada"):
                self._gnina_tidak_ada = True
                self._gnina_antre.clear()
                self.log.tulis("Kolom GNINA kosong: " + angka["tidak_ada"])
                return
            self._isi_gnina(tugas["jid"], tugas["lid"], angka)
            self._gnina_berikut()

        def gagal(e, tugas=t):
            self._gnina_jalan = False
            self._gnina_sedang = None
            self.log.tulis(f"GNINA {tugas['nama']}: {str(e).splitlines()[0]}")
            self._gnina_berikut()

        kerja.jalankan(nilai_gnina, selesai=jadi, galat=gagal)

    def _isi_gnina(self, jid, lid, angka):
        pr = self.proyek
        if not pr or not isinstance(angka, dict) or angka.get("affinity") is None:
            return
        for j in pr.job:
            if j["id"] != jid:
                continue
            for l in j["ligan"]:
                if l["id"] == lid:
                    l["gnina"] = {"affinity": angka["affinity"], "cnnscore": angka.get("cnnscore"),
                                  "cnnaffinity": angka.get("cnnaffinity")}
                    self.log.tulis(
                        f"GNINA {l['nama']}: Affinity {angka['affinity']:.2f} kcal/mol, "
                        f"CNNscore {angka.get('cnnscore')}, CNNaffinity {angka.get('cnnaffinity')} pK")
                    self._muat_hasil()
                    self.minta_simpan()
                    return

    def atur_syarat_jarak(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLineEdit
        pr = self.proyek
        if not pr:
            self.statusBar().showMessage("Belum ada proyek.", 4000)
            return
        d = QDialog(self)
        d.setWindowTitle("Syarat jarak")
        form = QFormLayout(d)
        e_rantai = QLineEdit()
        e_resi = QLineEdit()
        e_rantai2 = QLineEdit()
        e_resi2 = QLineEdit()
        sp = QDoubleSpinBox()
        sp.setRange(0.5, 12.0)
        sp.setDecimals(1)
        sp.setSingleStep(0.5)
        sp.setValue(3.5)
        from ..core.syarat import daftar_residu
        ada = daftar_residu(pr.syarat_jarak or {})
        if ada:
            e_rantai.setText(ada[0][0])
            e_resi.setText(ada[0][1])
            if len(ada) > 1:
                e_rantai2.setText(ada[1][0])
                e_resi2.setText(ada[1][1])
            if (pr.syarat_jarak or {}).get("jarak"):
                sp.setValue(float(pr.syarat_jarak["jarak"]))
        elif getattr(self, "residu_terpilih", None):
            _oid, daftar = self.residu_terpilih
            if daftar:
                e_rantai.setText(str(daftar[0][0] or ""))
                e_resi.setText(str(daftar[0][1] or ""))
            if len(daftar) > 1:
                e_rantai2.setText(str(daftar[1][0] or ""))
                e_resi2.setText(str(daftar[1][1] or ""))
        form.addRow("Rantai", e_rantai)
        form.addRow("Nomor residu", e_resi)
        form.addRow("Rantai kedua", e_rantai2)
        form.addRow("Nomor residu kedua", e_resi2)
        form.addRow("Jarak maksimum (Å)", sp)
        ket = QLabel("Lolos bila atom berat pose cukup dekat ke salah satu residu. "
                     "Baris tabel memakai pose berenergi terbaik yang lolos. Pose yang gagal tetap terlihat. "
                     "Vina dan AD-GPU tidak memaksa kontak saat pencarian.")
        ket.setWordWrap(True)
        form.addRow(ket)
        tombol = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        matikan = tombol.addButton("Matikan syarat", QDialogButtonBox.ResetRole)
        form.addRow(tombol)
        pilihan = {"mati": False}
        tombol.accepted.connect(d.accept)
        tombol.rejected.connect(d.reject)
        matikan.clicked.connect(lambda: (pilihan.__setitem__("mati", True), d.accept()))
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        if pilihan["mati"] or not e_resi.text().strip():
            pr.syarat_jarak = {}
            self._bersihkan_syarat_jarak()
            self.viewer.js("garisSyarat", None)
            self._muat_hasil()
            self.minta_simpan()
            self.statusBar().showMessage("Syarat jarak dimatikan.", 4000)
            return
        residu = [{"rantai": e_rantai.text().strip()[:1], "resi": e_resi.text().strip()}]
        if e_resi2.text().strip():
            residu.append({"rantai": e_rantai2.text().strip()[:1], "resi": e_resi2.text().strip()})
        pr.syarat_jarak = {"jarak": float(sp.value()), "residu": residu}
        self._hitung_syarat_jarak()
        self.minta_simpan()

    def _bersihkan_syarat_jarak(self):
        if not self.proyek:
            return
        for j in self.proyek.job:
            for l in j.get("ligan") or []:
                l.pop("syarat_jarak", None)

    def _hitung_syarat_jarak(self):
        pr = self.proyek
        aturan = (pr.syarat_jarak or {}) if pr else {}
        from ..core import mesin, syarat
        residu = syarat.daftar_residu(aturan)
        if not residu:
            return
        jalur = (pr.reseptor or {}).get("pdbqt")
        if not jalur or not pr.p(jalur).exists():
            self.log.tulis("Syarat jarak belum dihitung: reseptor PDBQT tidak ada.")
            return
        rec = pr.p(jalur).read_text(encoding="utf-8", errors="replace")
        ambang = float(aturan.get("jarak") or 3.5)
        n = 0
        for j in pr.job:
            for l in j.get("ligan") or []:
                if l.get("status") != "selesai" or not l.get("keluaran"):
                    continue
                f = pr.p(l["keluaran"])
                if not f.exists():
                    continue
                pose = mesin.baca_hasil(j["mesin"], f)
                ukur = []
                for p in pose:
                    pas = syarat.pasangan_terdekat(rec, residu, p.pdbqt)
                    if not pas:
                        continue
                    ukur.append({"peringkat": p.peringkat, "energi": p.energi, "min": round(pas["min"], 2),
                                 "lolos": pas["min"] <= ambang + 1e-9, "atom_ligan": pas["atom_ligan"],
                                 "atom_residu": pas["atom_residu"], "resn": pas["resn"], "rantai": pas["rantai"],
                                 "resi": pas["resi"], "ligan": pas["ligan"], "protein": pas["protein"]})
                pilihan = syarat.pilih_pose_syarat(ukur, ambang)
                if not pilihan:
                    l.pop("syarat_jarak", None)
                    continue
                rekam = {"ambang": ambang, "min": pilihan["min"], "lolos": pilihan["min"] <= ambang + 1e-9,
                         "peringkat": pilihan["peringkat"], "atom_ligan": pilihan.get("atom_ligan"),
                         "atom_residu": pilihan.get("atom_residu"), "resn": pilihan.get("resn"),
                         "rantai": pilihan.get("rantai"), "resi": pilihan.get("resi"),
                         "ligan": pilihan.get("ligan"), "protein": pilihan.get("protein"), "pose": ukur}
                if pilihan["peringkat"] != 1:
                    self._interaksi_pose_syarat(pr, j, l, pose, pilihan, rec, rekam)
                l["syarat_jarak"] = rekam
                n += 1
        self._muat_hasil()
        nama = " atau ".join(f"{r} {n}".strip() for r, n in residu)
        self.log.tulis(
            f"Syarat jarak {nama} ≤ {ambang:.1f} Å dihitung pada semua pose dari {n} ligan. "
            "Baris memakai pose berenergi terbaik yang lolos. Pencarian docking tidak dipaksa mendekat.")
        aktif = self.objek.get(getattr(self, "aktif", None))
        if aktif and aktif.jenis == "pose":
            self._gambar_syarat(aktif)

    def _interaksi_pose_syarat(self, pr, j, l, pose, pilihan, rec, rekam):
        """Isi interaksi baris tabel untuk pose yang lolos, tanpa mengubah ΔG docking pose 1."""
        try:
            from ..core.analisis import baca_reseptor, efisiensi_ligan, gabung_flex, hitung, interaksi, pose_mol
            if not l.get("pdbqt") or not pr.p(l["pdbqt"]).exists():
                return
            blok = next((p for p in pose if p.peringkat == pilihan["peringkat"]), None)
            if not blok or not blok.pdbqt:
                return
            mol = pose_mol(pr.p(l["pdbqt"]).read_text(encoding="utf-8", errors="replace"), blok.pdbqt)
            protein = baca_reseptor(rec)
            if blok.flex:
                protein = gabung_flex(protein, blok.flex)
            rekam["interaksi"] = hitung(interaksi(protein, mol))
            rekam["le"] = efisiensi_ligan(blok.energi, mol.GetNumHeavyAtoms())
        except Exception as err:
            catat.log.debug(f"Gagal menghitung interaksi pose: {err}")
            return

    def _gambar_syarat(self, o):
        info = o.info or {}
        pr = self.proyek
        if not pr:
            return
        j = next((x for x in pr.job if x.get("id") == info.get("job")), None)
        l = next((x for x in (j or {}).get("ligan") or [] if x.get("id") == info.get("lid")), None)
        sj = (l or {}).get("syarat_jarak") if isinstance((l or {}).get("syarat_jarak"), dict) else {}
        entri = next((p for p in sj.get("pose") or [] if p.get("peringkat") == info.get("peringkat")), None)
        if not entri or not entri.get("ligan") or not entri.get("protein"):
            self.viewer.js("garisSyarat", None)
            return
        self.viewer.js("garisSyarat", {
            "ligan": entri["ligan"], "protein": entri["protein"], "atom_ligan": entri.get("atom_ligan"),
            "atom_residu": entri.get("atom_residu"), "resn": entri.get("resn"), "resi": entri.get("resi"),
            "rantai": entri.get("rantai"), "lolos": bool(entri.get("lolos")), "min": entri.get("min"),
        })

    def _job_selesai(self, jid):
        j = self.pelaksana.cari(jid)
        if not j:
            return
        self._muat_hasil()
        if j["status"] == "selesai" and not j.get("kovalen"):
            self._antre_gnina(j)
        from ..core.syarat import daftar_residu
        if j["status"] == "selesai" and daftar_residu(self.proyek.syarat_jarak or {}):
            self._hitung_syarat_jarak()
        ok = [l for l in j["ligan"] if l["status"] == "selesai"]
        if j.get("validasi") and j["status"] == "selesai":
            QTimer.singleShot(200, lambda: self._hasil_validasi(j))
        if j["status"] == "selesai":
            # Sembunyikan ligan input masukan agar tidak mengapung di koordinat asal
            for o in self.objek.values():
                if o.grup == GRUP_LIGAN and o.tampil:
                    self.set_tampil(o.id, False)
                    self.hier.set_centang(o.id, False)
            terbaik = min(ok, key=lambda l: l["energi"])
            judul = "Docking selesai"
            isi = f"{len(ok)}/{len(j['ligan'])} ligan · terbaik {terbaik['nama']} {terbaik['energi']:.2f} kcal/mol"
            if not j.get("validasi"):
                self.ke_langkah(4)
                # Otomatis buka pose terbaik di binding site
                QTimer.singleShot(250, lambda: self.buka_pose(jid, terbaik["id"], 1))
            if not any(x["status"] in ("berjalan", "menunggu") for x in self.proyek.job):
                self._tampil_bawah(False)   # sukses: antrean dilipat lagi (tetap di bilah status)
        elif j["status"] == "dibatalkan":
            judul, isi = "Docking dibatalkan", f"{j['id']} · {len(ok)} ligan sempat selesai"
        else:
            judul = "Docking gagal"
            alasan = "; ".join(j.get("catatan") or []) or next((l["pesan"] for l in j["ligan"] if l.get("pesan")), "")
            isi = f"{j['id']}: {alasan[:180]}"
            self.pesan.tulis(f"{judul} - {isi}")
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
        # grup hasil lain disembunyikan agar viewport bersih (tidak dihapus); pose tersemat tetap tampil
        for o in self.objek.values():
            if (o.jenis == "pose" or o.info.get("flex_pose")) and o.grup != grup and o.tampil \
                    and not o.info.get("sematkan"):
                self.set_tampil(o.id, False)
                self.hier.set_centang(o.id, False)
            # Sembunyikan ligan input masukan agar tidak mengambang di luar binding pocket / viewport
            if o.grup == GRUP_LIGAN and o.tampil:
                self.set_tampil(o.id, False)
                self.hier.set_centang(o.id, False)
        lama = [o for o in self.objek.values() if o.grup == grup]
        if lama and any("pdbqt" not in o.info for o in lama if o.jenis == "pose"):  # pose versi lama: muat ulang
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
                o.info = {"energi": p.energi, "ki": "" if j.get("kovalen") else p.ki, "rmsd_lb": p.rmsd_lb, "rmsd_ub": p.rmsd_ub,
                          "rmsd_ref": p.rmsd_ref, "klaster": p.klaster, "ligan": l["nama"], "job": jid, "lid": lid,
                          "peringkat": p.peringkat, "mesin": mesinmod.MESIN[j["mesin"]], "pdbqt": p.pdbqt,
                          "lig_pdbqt": l["pdbqt"], "atom": len(o.teks.splitlines()) - 1,
                          "rmsd_kristal": simpan.get(p.peringkat, {}).get("rmsd_kristal")}
                if j.get("kovalen"):
                    o.info["kovalen"] = j["kovalen"].get("label") or j["kovalen"].get("residu")
                    o.info["warhead"] = l.get("warhead", "")
                lama.append(o)
                if p.flex:    # rantai samping fleksibel pada posisi pose ini
                    o.info["flex"] = p.flex
                    o.info["residu_flex"] = mesinmod.residu_flex(p.flex)
                    fo = molekul.Objek(nama=f"Pose {p.peringkat} · residu fleksibel", jenis="kompleks",
                                       teks=mesinmod.flex_ke_pdb(p.flex), grup=grup, sumber=f"{jid}/{lid}")
                    fo.tampil = False
                    fo.gaya = {"reps": ["sticks"], "warna": {"mode": "element", "carbon": "#e0a030"}, "opacity": 1.0,
                               "permukaan": None, "khusus": []}
                    fo.info = {"flex_pose": p.peringkat, "job": jid, "lid": lid,
                               "residu": len(o.info["residu_flex"])}
                    lama.append(fo)
            self.tambah_objek(lama, fokus=False)
        sasaran = next((o for o in lama if o.info.get("peringkat") == k), lama[0] if lama else None)
        for o in lama:
            on = o is sasaran or bool(o.info.get("sematkan")) or bool(
                sasaran and o.info.get("flex_pose") and o.info["flex_pose"] == sasaran.info.get("peringkat"))
            if o.tampil != on:
                self.set_tampil(o.id, on)
                self.hier.set_centang(o.id, on)
        if sasaran:
            if not self.a_inter.isChecked():
                self.a_inter.setChecked(True)
            self._fokus({"id": sasaran.id})
            self.hier.pilih_objek(sasaran.id)
            self.pilih_objek(sasaran.id)
            self.analisis_objek(sasaran)
            self._tampilkan_interaksi()
            e = sasaran.info.get("energi", 0)
            n_int = len(self._aktif_inter.get("daftar", [])) if self._aktif_inter else 0
            self.statusBar().showMessage(
                f"Pose {k} ({l['nama']}) di binding site · ΔG = {e:.2f} kcal/mol · {n_int} interaksi aktif", 6000)
        self.tab_tengah.setCurrentWidget(self.w_view)
        self.minta_simpan()
        return sasaran

    def _toggle_pose_docking(self, on):
        info = getattr(self.prop, "_pose_aktif", None)
        if not info:
            return
        grup = f"Hasil · {info.get('ligan')} · {info.get('job', '')[-6:]}"
        k = info.get("peringkat", 1)
        sasaran = next((o for o in self.objek.values() if o.grup == grup and o.info.get("peringkat") == k and not o.info.get("boltz")), None)
        if sasaran and sasaran.tampil != on:
            self.set_tampil(sasaran.id, on)
            self.hier.set_centang(sasaran.id, on)

    def _toggle_pose_boltz(self, on):
        info = getattr(self.prop, "_pose_aktif", None)
        if not info:
            return
        grup = f"Hasil · {info.get('ligan')} · {info.get('job', '')[-6:]}"
        sasaran = next((o for o in self.objek.values() if o.grup == grup and o.info.get("boltz")), None)
        if sasaran and sasaran.tampil != on:
            self.set_tampil(sasaran.id, on)
            self.hier.set_centang(sasaran.id, on)

    def jalankan_kofolding_pose(self, info_pose):
        """Jalankan inferensi & analisis konsensus Boltz-2 untuk pose yang dipilih."""
        from ..core import kofolding, konservasi, molekul, mesin as mesinmod
        pr = self.proyek
        if not pr:
            return
        st = kofolding.status_boltz()
        if not st.get("ada"):
            self._galat("Boltz-2 belum terpasang di WSL.\n\n" + st.get("pesan", ""))
            return

        j = self.pelaksana.cari(info_pose.get("job"))
        l = next((x for x in (j or {}).get("ligan", []) if x["id"] == info_pose.get("lid")), None) if j else None
        if not l:
            self._galat("Data ligan tidak ditemukan.")
            return

        rec_obj = self._reseptor_objek()
        if not rec_obj or not rec_obj.teks:
            self._galat("Reseptor proyek tidak memiliki koordinat PDB.")
            return

        # Ekstraksi sekuens rantai dari reseptor
        sekuens_rantai = []
        for c, res_list in sorted(rec_obj.rantai.items()):
            huruf = [konservasi.TIGA_KE_SATU.get(r[0], "X") for r in res_list]
            if huruf:
                sekuens_rantai.append((c, "".join(huruf)))

        smiles = pr.smiles_ligan(l) if hasattr(pr, "smiles_ligan") else l.get("smiles", "")
        if not smiles:
            self._galat("SMILES ligan tidak ditemukan.")
            return

        folder_keluar = pr.p("kofolding", l["id"])
        folder_keluar.mkdir(parents=True, exist_ok=True)
        nama_lig = l.get("nama", "Ligan")

        def kerjakan(lapor):
            lapor.log.emit(f"Menjalankan Boltz-2 co-folding untuk {nama_lig}…")
            kofolding.jalankan_boltz(sekuens_rantai, smiles, folder_keluar, gpu=True)
            lapor.log.emit("Inferensi selesai. Menganalisis superposisi dan kesepakatan pose…")

            # Pose docking RDKit mol
            k = info_pose.get("peringkat", 1)
            poses = mesinmod.baca_hasil(j["mesin"], pr.p(l["keluaran"]))
            pose_pilih = poses[k - 1] if len(poses) >= k else poses[0]
            mol_dock = analisis.pose_mol(l["pdbqt"], pose_pilih.pdbqt)

            p_rec_pdb = pr.p("reseptor", "reseptor_bersih.pdb")
            if not p_rec_pdb.exists() and pr.reseptor and pr.reseptor.get("pdb"):
                p_rec_pdb = pr.p(pr.reseptor["pdb"])

            hasil = kofolding.analisis_kofolding(
                folder_atau_berkas_boltz=folder_keluar,
                reseptor_pdb=rec_obj.teks,
                mol_docking=mol_dock,
                smiles=smiles,
                path_reseptor_pdb=p_rec_pdb if p_rec_pdb.exists() else None,
            )
            return hasil

        def selesai(hasil):
            if not hasil.tersedia:
                self._galat(f"Co-folding gagal: {hasil.pesan}")
                return
            l["kofolding"] = hasil.to_dict()
            self.minta_simpan()
            self.prop.muat_kofolding(l["kofolding"], st, info_pose)

            # Tambahkan pose Boltz-2 ke viewport jika ada struktur terselaraskan
            if hasil.pdb_ligan_terselaraskan:
                grup = f"Hasil · {l['nama']} · {j['id'][-6:]}"
                lama_boltz = [o.id for o in self.objek.values() if o.grup == grup and o.info.get("boltz")]
                for oid in lama_boltz:
                    self.hapus_objek(oid)

                o_b = molekul.Objek(
                    nama=f"Pose Boltz-2 · {l['nama']}",
                    jenis="pose",
                    teks=hasil.pdb_ligan_terselaraskan,
                    grup=grup,
                    sumber=f"{j['id']}/{l['id']}/boltz"
                )
                o_b.tampil = True
                o_b.gaya = {
                    "reps": ["sticks"],
                    "warna": {"mode": "solid", "val": "#20c997"},
                    "opacity": 0.65,
                    "permukaan": None,
                    "khusus": []
                }
                o_b.info = {
                    "boltz": True,
                    "ligan": l["nama"],
                    "job": j["id"],
                    "lid": l["id"],
                    "kesepakatan": hasil.kesepakatan,
                    "rmsd": hasil.rmsd,
                    "afinitas": hasil.afinitas_pred_value
                }
                self.tambah_objek([o_b], fokus=False)

            self.statusBar().showMessage(
                f"Co-folding selesai: RMSD {kit.f(hasil.rmsd, 2, 'Å')} · Kesepakatan: {hasil.kesepakatan}",
                6000
            )

        self.statusBar().showMessage(f"Menjalankan Boltz-2 untuk {nama_lig} di latar belakang…")
        kerja.jalankan(kerjakan, selesai=selesai, galat=self._galat, log=self.log.tulis)

    # ------------------------------------------------------------ analisis
    def _muat_hasil(self):
        self.hasil.muat(eksmod.baris_hasil(self.proyek) if self.proyek else [])
        self.segarkan_langkah()
        self._sifat_kotor = self._stat_kotor = True
        self._tab_berganti()

    def _tab_berganti(self, *_):
        w = self.tab_tengah.currentWidget()
        if w is self.w_view and self.viewer._siap:   # setelah tata letak tab final
            for ms in (300, 1000):
                QTimer.singleShot(ms, lambda: self.viewer.js("segarkanKanvas"))
        if w is self.sifat:
            self._muat_sifat()
        elif w is self.statistik and self._stat_kotor:
            self._muat_statistik()

    def _muat_statistik(self):
        self._stat_kotor = False
        pr = self.proyek
        if not pr:
            self.statistik.muat([], [])
            return
        self._data_sifat()   # pastikan sifat tiap ligan proyek sudah dihitung (cache)
        sif = {l["id"]: dict(l.get("sifat") if isinstance(l.get("sifat"), dict) else {}, pchembl=l.get("pchembl"))
               for l in pr.ligan}
        baris = stat_mod.dataset(eksmod.baris_hasil(pr), sif)
        jobs = [(j["id"], f"{j['id']} · {mesinmod.MESIN.get(j['mesin'], j['mesin'])}") for j in pr.job]
        self.statistik.muat(baris, jobs)

    def _ekspor_statistik(self, fmt):
        st_ = self.statistik
        if not st_.data:
            self._galat("Belum ada data statistik (jalankan docking dulu).")
            return
        dasar = f"{nama_aman(self.proyek.nama)}_{st_.c_jenis.currentData()}"
        if fmt == "csv":
            f = self._path("Simpan data statistik", f"{dasar}_data.csv", "CSV (*.csv)")
            if f:
                Path(f).write_text(stat_mod.csv_teks(st_.data), encoding="utf-8")
                self.log.tulis(f"Data statistik disimpan: {f}")
            return
        s, (w, h) = st_.svg(gelap=False)
        if not s:
            self._galat("Grafik kosong (data kurang).")
            return
        if fmt == "salin":
            self._salin_svg(s, w, h, "Grafik")
            return
        if fmt == "svg":
            f = self._path("Simpan grafik", f"{dasar}.svg", "SVG (*.svg);;PDF (*.pdf)")
            jenis = "pdf" if f.lower().endswith(".pdf") else "svg"
        else:
            f = self._path("Simpan grafik", f"{dasar}.png", "PNG (*.png);;TIFF (*.tif)")
            jenis = "tif" if f.lower().endswith((".tif", ".tiff")) else "png"
        if f:
            self._simpan_svg(s, f, jenis, w, h, mm=140, dpi=600)
            self.log.tulis(f"Grafik disimpan: {f}")
            self.statusBar().showMessage(f"Grafik disimpan: {f}", 5000)

    def _sumber_sifat(self):
        """[(kunci, nama, teks, fmt, dict ligan proyek | None)]: ligan proyek + ligan viewer yang belum disiapkan."""
        hasil, lid_ada = [], set()
        pr = self.proyek
        for l in (pr.ligan if pr else []):
            f = pr.p(l["sdf"]) if l.get("sdf") else None
            if f and f.exists():
                hasil.append((l["id"], l["nama"], f.read_text(encoding="utf-8"), "sdf", l))
                lid_ada.add(l["nama"])
                continue
            smi = pr.smiles_ligan(l)      # proyek lama tanpa SDF sumber: pakai REMARK SMILES di PDBQT
            if smi:
                hasil.append((l["id"], l["nama"], smi, "smiles", l))
                lid_ada.add(l["nama"])
        for o in self.objek.values():   # ligan yang sudah disiapkan punya nama sama dengan objek asalnya
            if o.jenis == "ligan" and not o.info.get("siap_docking") and o.nama not in lid_ada:
                hasil.append((o.id, o.nama, o.teks, o.fmt, None))
        return hasil

    def _muat_sifat(self, paksa=False):
        if not paksa and not self._sifat_kotor:
            return
        self._sifat_kotor = False
        self.sifat.muat(self._data_sifat(paksa))

    def _data_sifat(self, paksa=False):
        """[(nama, sifat dict | teks galat, ΔG terbaik)]; hasil disimpan di proyek.ligan[*]['sifat']."""
        dg = {}
        if self.proyek:
            for b in eksmod.baris_hasil(self.proyek):
                dg[b["lid"]] = min(dg.get(b["lid"], 0.0), b["energi"])
        data, ubah = [], False
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for kunci, nama, teks, fmt, lig in self._sumber_sifat():
                s = lig.get("sifat") if lig else None
                if paksa or not s or s.get("v") != sifat_mod.VERSI:
                    try:
                        s = sifat_mod.dari_teks(teks, fmt)
                    except Exception as e:
                        s = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
                    if lig is not None and isinstance(s, dict):
                        lig["sifat"] = s
                        ubah = True
                data.append((nama, s, dg.get(kunci)))
        finally:
            QApplication.restoreOverrideCursor()
        if ubah:
            self.minta_simpan()
        return data

    def _uji_berubah(self):
        if self.proyek:
            self.proyek.uji_grafik = self.uji.ke_dict()
            self.minta_simpan()

    def _uji_dari_docking(self, mode):
        """Isi lembar Uji & Grafik: ΔG per job (kolom = job) atau per mesin."""
        baris = eksmod.baris_hasil(self.proyek) if self.proyek else []
        if not baris:
            self._galat("Belum ada hasil docking.")
            return
        kel = {}
        for b in baris:
            k = b["mesin"] if mode == "mesin" else f"{b['mesin']} · {b['job'][-6:]}"
            kel.setdefault(k, []).append(b["energi"])
        self.uji.isi(list(kel), list(kel.values()), "kolom")
        self.uji.e_y.setText("ΔG (kcal/mol)")
        self.uji.hitung()
        self._uji_berubah()

    def _ekspor_uji(self, fmt):
        if fmt == "komposer":
            self._komposer_tambah("uji")
            return
        s, (w, h) = self.uji.svg(gelap=False)
        if not s:
            self._galat("Grafik kosong: isi lembar data dulu.")
            return
        if fmt == "salin":
            self._salin_svg(s, w, h, "Grafik")
            return
        dasar = nama_aman(self.proyek.nama) if self.proyek else "virmolab"
        if fmt == "svg":
            f = self._path("Simpan grafik", f"{dasar}_uji.svg", "SVG (*.svg);;PDF (*.pdf)")
            jenis = "pdf" if f.lower().endswith(".pdf") else "svg"
        else:
            f = self._path("Simpan grafik", f"{dasar}_uji.png", "PNG (*.png);;TIFF (*.tif)")
            jenis = "tif" if f.lower().endswith((".tif", ".tiff")) else "png"
        if f:
            self._simpan_svg(s, f, jenis, w, h, mm=85 if w <= 520 else 120, dpi=600)
            self.log.tulis(f"Grafik uji disimpan: {f}")
            self.statusBar().showMessage(f"Grafik disimpan: {f}", 5000)

    def _opsi_render(self):
        b = lambda k, d: str(self.st.value(k, d)).lower() in ("true", "1")   # noqa: E731
        kabut = self.st.value("render_kabut", "halus")
        return {"tepi": b("render_tepi", True), "ao": b("render_ao", False),
                "kabut": kabut if kabut in ("mati", "halus", "kuat") else "halus"}

    def gaya_render(self):
        a = self.grp_kabut.checkedAction()
        self.st.setValue("render_tepi", self.a_tepi.isChecked())
        self.st.setValue("render_ao", self.a_ao.isChecked())
        self.st.setValue("render_kabut", a.data() if a else "halus")
        self.viewer.js("gayaRender", self._opsi_render())

    # ------------------------------------------------------------ validasi
    def validasi_redocking(self):
        pr = self.proyek
        if not pr or not pr.reseptor:
            self._galat("Siapkan reseptor dulu (langkah 1 › Siapkan reseptor).")
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
        self._tampil_bawah(True)

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
        teks = (f"RMSD pose terbaik terhadap kristal: {r:.2f} Å - {'VALID (≤ 2,0 Å)' if ok else 'TIDAK VALID (> 2,0 Å)'}\n"
                f"RMSD minimum di antara pose teratas: {l.get('rmsd_kristal_min', r):.2f} Å\n"
                f"ΔG pose terbaik: {l['energi']:.2f} kcal/mol ({mesinmod.MESIN[j['mesin']]})")
        self.pesan.tulis("Validasi redocking - " + teks.replace("\n", "; "))
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
            daftar = analisis.interaksi(analisis.gabung_flex(analisis.baca_reseptor(rec.teks), p.flex), mol)
            v = viewer[i]
            v.js("clear")
            v.js("tema", self.mode == "gelap", t["view"])
            v.js("gayaRender", self._opsi_render())
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
        self.banding.l_info.setText("   Residu berinteraksi dengan semua ligan: " + (", ".join(bersama) or "-"))
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
            self._galat("Belum ada data interaksi. Jalankan Analisis › Hitung ulang analisis hasil.")
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
        from .dialog_ekspor import DialogEkspor
        d = DialogEkspor((self.viewer.width(), self.viewer.height()), ada_pose, self, kategori)
        d.minta.connect(self._ekspor)
        d.exec()

    def _nama_dasar(self):
        a = self._aktif_inter
        o = self.objek.get(a["oid"]) if a else None
        if o and o.jenis == "pose":
            return nama_aman(f"{o.info.get('ligan', 'ligan')}_pose{o.info.get('peringkat', 1)}")
        return nama_aman(o.nama) if o else (nama_aman(self.proyek.nama) if self.proyek else "virmolab")

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
        self.tab_tengah.setCurrentWidget(self.w_view)  # WebGL hanya merender benar bila viewport terlihat

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
        if max(d["lebar"], d["tinggi"]) > UBIN_PX:
            QTimer.singleShot(250, lambda: self._render_ubin(d["lebar"], d["tinggi"], d["latar"] == "transparan",
                                                             latar, simpan))
            return
        QTimer.singleShot(250, lambda: self.viewer.js("gambar", d["lebar"], d["tinggi"], d["latar"] == "transparan",
                                                      latar, cb=simpan))

    def _render_ubin(self, lebar, tinggi, transparan, latar, selesai):
        """Gambar > UBIN_PX: render n x n ubin di WebGL lalu satukan; `selesai` menerima data URL PNG."""
        import base64
        import math
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QImage, QPainter
        n = math.ceil(max(lebar, tinggi) / UBIN_PX)
        ubin = {}

        def gagal(pesan):
            self.viewer.js("ubinSelesai")
            self._galat(pesan)

        def satukan():
            tw = max(im.width() for im in ubin.values())
            th = max(im.height() for im in ubin.values())
            img = QImage(tw * n, th * n, QImage.Format_ARGB32)
            img.fill(0)
            p = QPainter(img)
            for (i, j), im in ubin.items():
                p.drawImage(i * tw, j * th, im)
            p.end()
            if (img.width(), img.height()) != (lebar, tinggi):
                img = img.scaled(lebar, tinggi, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            img.save(buf, "PNG")
            selesai("data:image/png;base64," + base64.b64encode(bytes(buf.data())).decode())

        urutan = [(i, j) for j in range(n) for i in range(n)]

        def ambil(k=0):
            if k == len(urutan):
                self.viewer.js("ubinSelesai", cb=lambda _: satukan())
                return
            i, j = urutan[k]
            self.statusBar().showMessage(f"Merender {lebar} × {tinggi} px: ubin {k + 1}/{len(urutan)}…")

            def terima(url):
                if not url or "," not in url:
                    return gagal("Render ubin gagal (WebGL). Coba ukuran lebih kecil.")
                ubin[(i, j)] = QImage.fromData(base64.b64decode(url.split(",", 1)[1]), "PNG")
                QTimer.singleShot(0, lambda: ambil(k + 1))
            self.viewer.js("ubin", i, j, cb=terima)
        self.viewer.js("ubinMulai", lebar, tinggi, n, transparan, latar, cb=lambda ok: ambil() if ok else
                       gagal("Render ubin gagal dimulai."))

    def _ekspor_diagram(self, d):
        if not self._aktif_inter:
            self._galat("Pilih pose atau ligan dulu untuk diagram 2D.")
            return
        fmt = d["fmt"]
        f = self._path("Simpan diagram 2D", f"{self._nama_dasar()}_2d.{fmt}", f"Diagram (*.{fmt})")
        if f:
            self._simpan_diagram(f, fmt, d["mm"], d["dpi"], d["vdw"], d["transparan"], d["judul"])

    def _simpan_diagram(self, f, fmt, mm=120, dpi=600, vdw=True, transparan=False, judul=True):
        s = self._svg_diagram(vdw, True, transparan, judul, gelap=False)
        self._simpan_svg(s, f, fmt, 960, 720, mm, dpi, transparan)
        self.log.tulis(f"Diagram 2D disimpan: {f}")
        self.statusBar().showMessage(f"Diagram disimpan: {f}", 5000)

    @staticmethod
    def _svg_ke_qimage(s, lebar_px, tinggi_px, px, latar="#ffffff"):
        from PySide6.QtCore import QByteArray
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
        img = QImage(px, int(px * tinggi_px / lebar_px), QImage.Format_ARGB32)
        img.fill(QColor(latar) if latar else 0)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        QSvgRenderer(QByteArray(s.encode("utf-8"))).render(p)
        p.end()
        return img

    def _salin_svg(self, s, w, h, nama):
        """Grafik SVG -> gambar 2400 px berlatar putih di clipboard (setara 200 mm @ 300 dpi)."""
        img = self._svg_ke_qimage(s, w, h, 2400)
        img.setDotsPerMeterX(round(300 / 0.0254))
        img.setDotsPerMeterY(round(300 / 0.0254))
        QGuiApplication.clipboard().setImage(img)
        self.statusBar().showMessage(f"{nama} disalin ke clipboard ({img.width()} × {img.height()} px).", 5000)

    def salin_gambar(self):
        """Salin isi tab tengah yang aktif ke clipboard."""
        w = self.tab_tengah.currentWidget()
        if w is self.diagram:
            return self._diagram_cepat("salin")
        if w is self.sifat:
            return self._ekspor_sifat("salin")
        if w is self.statistik:
            return self._ekspor_statistik("salin")
        if w is self.uji:
            return self._ekspor_uji("salin")
        if w is not self.w_view:
            self.tab_tengah.setCurrentWidget(self.w_view)
        rasio = 2
        lebar, tinggi = self.viewer.width() * rasio, self.viewer.height() * rasio
        latar = theme.TOKEN[self.mode]["view"]

        def taruh(url):
            import base64
            from PySide6.QtGui import QImage
            if not url or "," not in url:
                self._galat("Render gambar gagal (WebGL).")
                return
            img = QImage.fromData(base64.b64decode(url.split(",", 1)[1]), "PNG")
            QGuiApplication.clipboard().setImage(img)
            self.statusBar().showMessage(f"Gambar viewport disalin ke clipboard ({img.width()} × {img.height()} px).",
                                         5000)
        QTimer.singleShot(150, lambda: self.viewer.js("gambar", lebar, tinggi, False, latar, cb=taruh))

    def _simpan_svg(self, s, f, fmt, lebar_px, tinggi_px, mm=120, dpi=600, transparan=False):
        """SVG -> svg (ukuran mm) / pdf (vektor) / png / tif ber-DPI."""
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QRectF, QSizeF
        from PySide6.QtGui import QImage, QPageSize, QPainter, QPdfWriter
        from PySide6.QtSvg import QSvgRenderer
        if fmt == "svg":
            s = s.replace(f'width="{lebar_px}" height="{tinggi_px}"',
                          f'width="{mm:.1f}mm" height="{mm * tinggi_px / lebar_px:.1f}mm"', 1)
            Path(f).write_text(s, encoding="utf-8")
            return
        r = QSvgRenderer(QByteArray(s.encode("utf-8")))
        if fmt == "pdf":
            w = QPdfWriter(f)
            w.setPageSize(QPageSize(QSizeF(mm, mm * tinggi_px / lebar_px), QPageSize.Millimeter))
            w.setPageMargins(QMarginsF(0, 0, 0, 0))
            w.setResolution(600)
            p = QPainter(w)
            r.render(p, QRectF(0, 0, w.width(), w.height()))
            p.end()
            return
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

    def _diagram_cepat(self, fmt):
        if not self._aktif_inter:
            self._galat("Belum ada diagram.")
            return
        if fmt == "salin":
            self._salin_svg(self._svg_diagram(True, True, False, True, gelap=False), 960, 720, "Diagram 2D")
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

    def _ekspor_paket(self, d):
        from ..core import supplementary
        pr = self.proyek
        baris = eksmod.baris_hasil(pr) if pr else []
        if not baris:
            self._galat("Belum ada hasil docking.")
            return
        f = self._path("Simpan paket Supplementary", f"{nama_aman(pr.nama)}_supplementary.zip", "Arsip zip (*.zip)")
        if not f:
            return
        # versi mesin docking (tanpa jalur berkas: paket ini dibagikan; jalur memuat nama pengguna Windows)
        info = {"Perangkat": self.s_gpu.text().lstrip("● "),
                "Mesin": "AutoDock-GPU 1.6 (OpenCL), AutoDock Vina 1.2.7, AutoGrid/AutoDock 4.2.6"}
        self.s_prog.setText("Menyusun paket Supplementary…")
        kerja.jalankan(lambda lapor: supplementary.buat(f, pr, baris, self.pelaksana.cari, VERSI, info,
                                                        d.get("n_kompleks", 20), lapor),
                       selesai=lambda n: (self.s_prog.setText(""),
                                          self.log.tulis(f"Paket Supplementary ({n} berkas) disimpan: {f}"),
                                          self.statusBar().showMessage(f"Paket Supplementary tersimpan: {f}", 8000)),
                       galat=lambda g: (self.s_prog.setText(""), self._galat("Paket Supplementary gagal:\n" + g)),
                       progres=lambda a, b, t: self.s_prog.setText(f"Paket Supplementary {a}/{b}…"))

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
        info = {"Proyek": pr.nama, "Folder": pr.folder.name, "VirmoLab": VERSI,
                "Reseptor": (pr.reseptor or {}).get("nama"), "Metode reseptor": (pr.reseptor or {}).get("metode"),
                "Perangkat": self.s_gpu.text().lstrip("● ")}
        sifat_lig = [x for x in self._data_sifat() if isinstance(x[1], dict)]   # di thread GUI (cursor)

        def kerjakan(lapor):
            inter = {}
            if d["interaksi"] and rec is not None:
                r = analisis.baca_reseptor(rec.teks)
                for b in baris:
                    j = self.pelaksana.cari(b["job"])
                    l = next(x for x in j["ligan"] if x["id"] == b["lid"])
                    p = mesinmod.baca_hasil(j["mesin"], pr.p(l["keluaran"]))[0]
                    inter[(b["ligan"], b["job"])] = analisis.interaksi(
                        analisis.gabung_flex(r, p.flex), analisis.pose_mol(pr.p(l["pdbqt"]).read_text(), p.pdbqt))
            eksmod.simpan_xlsx(f, pr, baris, inter, info, sifat_lig)
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
        fmt = d.get("fmt", "pdf")
        ext, filt = {"docx": ("docx", "Dokumen Word (*.docx)"), "html": ("html", "HTML interaktif (*.html)")}.get(
            fmt, ("pdf", "PDF (*.pdf)"))
        f = self._path("Simpan laporan", f"{nama_aman(pr.nama)}_laporan.{ext}", filt)
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
        fmt = d.get("fmt", "pdf")
        img2d = None
        if svg2d:
            r = QSvgRenderer(QByteArray(svg2d.encode("utf-8")))
            img2d = QImage(1600, 1200, QImage.Format_ARGB32)
            img2d.fill(0xffffffff)
            p = QPainter(img2d)
            p.setRenderHint(QPainter.Antialiasing)
            r.render(p)
            p.end()
        inter = self._aktif_inter["daftar"] if (self._aktif_inter and baris) else None
        info = {"versi": VERSI, "perangkat": self.s_gpu.text().lstrip("● ")}
        sifat_lap = {n: x for n, x, _ in self._data_sifat() if isinstance(x, dict)}
        html = laporan.html(pr, baris, info, inter, bool(img3d), bool(svg2d), d.get("penulis", ""), sifat_lap)
        judul = f"Laporan docking {pr.nama}"

        def selesai(_=None):
            self.statusBar().showMessage(f"Laporan disimpan: {f}", 6000)
            self.log.tulis(f"Laporan {fmt.upper()} disimpan: {f}")
            if not pr.validasi:
                self.pesan.tulis("Laporan dibuat tanpa validasi redocking. Jalankan Docking › Validasi redocking agar "
                                 "metode dapat dipertanggungjawabkan.")
            QDesktopServices.openUrl(QUrl.fromLocalFile(f))

        if fmt == "docx":
            from ..core import docx_ringan
            gambar = {"img3d": img3d} if img3d else {}
            if img2d is not None:
                gambar["img2d"] = self._qimage_png(img2d)
            docx_ringan.simpan(html, f, gambar, judul, d.get("penulis", ""))
            selesai()
            return
        if fmt == "html":
            self._tulis_laporan_html(f, html, baris, img3d, svg2d, d, selesai)
            return
        doc = QTextDocument()
        if img3d:
            doc.addResource(QTextDocument.ImageResource, QUrl("img3d"), QImage.fromData(img3d))
        if img2d is not None:
            doc.addResource(QTextDocument.ImageResource, QUrl("img2d"), img2d)
        doc.setHtml(html)
        w = QPdfWriter(f)
        w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(16, 14, 16, 14),
                                    QPageLayout.Millimeter))
        w.setResolution(150)
        w.setTitle(judul)
        w.setCreator(f"VirmoLab {VERSI}")
        doc.setPageSize(w.pageLayout().paintRectPixels(150).size().toSizeF())
        doc.print_(w)
        selesai()

    @staticmethod
    def _qimage_png(img):
        from PySide6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        return bytes(buf.data())

    def _tulis_laporan_html(self, f, html, baris, img3d, svg2d, d, selesai):
        """Laporan HTML interaktif: pose 30 ligan teratas + interaksi dihitung di latar belakang."""
        from datetime import datetime
        from rdkit import Chem
        from ..core import laporan_interaktif
        pr = self.proyek
        rec = self._reseptor_objek()
        if not rec:
            self._galat("Reseptor tidak ditemukan di sesi; buka proyek dengan reseptor siap docking.")
            return
        rec_teks, rec_fmt = rec.teks, rec.fmt
        lapor_baris = [dict(b) for b in baris]
        jobs = {b["job"]: self.pelaksana.cari(b["job"]) for b in lapor_baris}

        def kerjakan(lapor):
            r = analisis.baca_reseptor(rec_teks)
            pose = []
            for b in lapor_baris[:30]:
                try:
                    j = jobs[b["job"]]
                    l = next(x for x in j["ligan"] if x["id"] == b["lid"])
                    p = mesinmod.baca_hasil(j["mesin"], pr.p(l["keluaran"]))[0]
                    m = analisis.pose_mol(pr.p(l["pdbqt"]).read_text(), p.pdbqt)
                    daftar = analisis.interaksi(analisis.gabung_flex(r, p.flex), m)
                except Exception as e:      # satu ligan rusak tidak menggagalkan laporan
                    lapor.log.emit(f"Pose {b['ligan']} dilewati: {e}")
                    continue
                b["_pose"] = len(pose)
                pose.append({"ligan": b["ligan"], "energi": b["energi"], "peringkat": 1, "mesin": b["mesin"],
                             "sdf": Chem.MolToMolBlock(m),
                             "kontak": sorted({(h["rantai"], int(h["resi"])) for h in daftar if h.get("resi") is not None}),
                             "interaksi": [{"jenis": h["jenis"], "residu": h["residu"], "atom": h["atom_p"],
                                            "jarak": h["jarak"], "p": h["p"], "l": h["l"]} for h in daftar]})
            js = (paths.VIEWER / "3Dmol-min.js").read_text(encoding="utf-8")
            n = datetime.now()
            sub = (f"{n:%d-%m-%Y %H:%M} · VirmoLab {VERSI}" + (f" · {d.get('penulis')}" if d.get("penulis") else "")
                   + f" · {len(lapor_baris)} hasil")
            teks = laporan_interaktif.buat(f"Laporan docking - {pr.nama}", html, lapor_baris, pose, rec_teks,
                                           rec_fmt, js, [(k, analisis.NAMA_JENIS[k]) for k in analisis.URUT_JENIS],
                                           img3d, svg2d, sub)
            Path(f).write_text(teks, encoding="utf-8")
            return f
        self.statusBar().showMessage("Menyusun laporan HTML interaktif…")
        kerja.jalankan(kerjakan, selesai=selesai, galat=self._galat)

    # -------------------------------------------------------------- tray
    def _tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        ik = QApplication.instance().windowIcon()
        if ik.isNull():
            ik = QIcon(icons.pixmap("logo", "#1f5fbf", 32))
        self.tray = QSystemTrayIcon(ik, self)
        self.tray.setToolTip("VirmoLab")
        self.tray.activated.connect(lambda *_: (self.showNormal(), self.raise_(), self.activateWindow()))
        self.tray.show()

    def notifikasi(self, judul, isi, gagal=False):
        self.log.tulis(f"{judul}: {isi}")
        if self.tray:
            self.tray.showMessage(judul, isi, QSystemTrayIcon.Warning if gagal else QSystemTrayIcon.Information, 8000)
        QApplication.alert(self)

    # ------------------------------------------------------------- lain
    def toggle_ukur(self, on):
        if on:
            self._matikan_centang(self.a_seret, self.a_geser)
        self.viewer.js("setMode", "ukur" if on else "putar")
        self.statusBar().showMessage("Mode ukur: klik dua atom" if on else "Mode ukur dimatikan", 4000)

    def _matikan_centang(self, *aksi):
        for a in aksi:
            if a.isChecked():
                a.blockSignals(True)
                a.setChecked(False)
                a.blockSignals(False)

    def toggle_seret(self, on):
        if on:
            self._matikan_centang(self.a_ukur, self.a_geser)
            self.viewer.js("setMode", "seret")
            self._kirim_id_seret()
            self.statusBar().showMessage(
                "Seret atom ligan. Lepas mouse untuk merapikan ikatan dan menilai dengan Vina.", 6000)
        else:
            self.viewer.js("setMode", "putar")
            self.statusBar().showMessage("Mode seret dimatikan", 4000)

    def toggle_geser(self, on):
        if on:
            self._matikan_centang(self.a_ukur, self.a_seret)
            self.viewer.js("setMode", "geser")
            self._kirim_id_seret()
            self.statusBar().showMessage(
                "Geser ligan utuh. Bentuknya tetap. Lepas mouse untuk menilai dengan Vina.", 6000)
        else:
            self.viewer.js("setMode", "putar")
            self.statusBar().showMessage("Mode geser ligan dimatikan", 4000)

    def ekspor_objek(self, o):
        ext = "sdf" if o.fmt == "sdf" else "pdb"
        f, _ = QFileDialog.getSaveFileName(self, "Ekspor objek", f"{o.nama}.{ext}", f"{ext.upper()} (*.{ext})")
        if f:
            Path(f).write_text(o.teks)
            self.log.tulis(f"Diekspor: {f}")

    def _tulis_sesi(self, folder):
        """Skrip sesi untuk pose/ligan aktif; None bila belum ada."""
        from ..core import sesi_eksternal
        a = self._aktif_inter
        o = self.objek.get(a["oid"]) if a else None
        rec = self.objek.get(a["rec"]) if a else None
        if not o or not rec or a.get("mol") is None:
            return None
        return sesi_eksternal.tulis(folder, self._nama_dasar(), rec.teks, a["mol"], a["daftar"], a.get("judul", ""))

    def ekspor_sesi(self):
        if not self._aktif_inter:
            self._galat("Pilih pose dulu (klik dua kali baris di tab Hasil).")
            return
        awal = str(self.proyek.p("ekspor")) if self.proyek else ""
        if self.proyek:
            self.proyek.p("ekspor").mkdir(exist_ok=True)
        d = QFileDialog.getExistingDirectory(self, "Folder untuk sesi PyMOL / ChimeraX", awal)
        if not d:
            return
        try:
            hasil = self._tulis_sesi(Path(d) / f"{self._nama_dasar()}_sesi")
        except Exception as e:
            self._galat(f"Gagal menulis sesi: {e}")
            return
        if hasil:
            self.log.tulis(f"Sesi PyMOL/ChimeraX disimpan: {hasil[0].parent}")
            self.statusBar().showMessage(f"Sesi disimpan: {hasil[0].parent}", 5000)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(hasil[0].parent)))

    def buka_di(self, nama):
        if not self.env or nama not in self.env.eksternal:
            return
        tmp = paths.CACHE / "buka"
        tmp.mkdir(exist_ok=True)
        if nama in ("PyMOL", "ChimeraX") and self._aktif_inter:
            # pose aktif: buka sebagai sesi lengkap (residu kontak + garis interaksi)
            try:
                hasil = self._tulis_sesi(tmp / "sesi")
            except Exception as e:
                hasil = None
                self.log.tulis(f"Sesi {nama} gagal dibuat ({e}); membuka berkas biasa.")
            if hasil:
                skrip = hasil[0] if nama == "PyMOL" else hasil[1]
                subprocess.Popen([self.env.eksternal[nama], str(skrip)], cwd=str(skrip.parent), creationflags=0)
                self.log.tulis(f"Dibuka di {nama}: sesi pose aktif ({skrip.name})")
                return
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

    def _kunci_layar(self):
        """Tanda ukuran layar tempat tata letak disimpan (lebar×tinggi area kerja)."""
        layar = self.screen() or QApplication.primaryScreen()
        g = layar.availableGeometry() if layar else None
        return f"{g.width()}x{g.height()}" if g else "?"

    def _layar_sama(self, toleransi=0.15):
        """True bila layar sekarang sebesar layar saat tata letak terakhir disimpan (beda ≤ 15%)."""
        lama = self.st.value("layar_layout")
        if not lama or "x" not in str(lama):
            return False
        try:
            lw, lt = (int(x) for x in str(lama).split("x"))
            sw, st_ = (int(x) for x in self._kunci_layar().split("x"))
        except ValueError:
            return False
        return (abs(lw - sw) <= lw * toleransi) and (abs(lt - st_) <= lt * toleransi)

    def reset_layout(self):
        self.st.remove(KUNCI_LAYOUT)
        self._bawah_dikunci = False
        self._bawah_ditutup_pengguna = False
        self._pesan_belum_dibaca = 0
        for d in (self.d_langkah, self.d_hier, self.d_kerja, self.d_prop, self.d_tamp, self.d_inter):
            d.setFloating(False)
            d.show()
        self._ukuran_dock_awal()
        self.atur_ruang(self._ruang_aktif or "siapkan")

    def toggle_mode_presentasi(self, on=None):
        """Mode presentasi/fokus bersih: sembunyikan dock & toolbar untuk tampilan publikasi/seminar."""
        if on is None:
            on = not getattr(self, "_mode_presentasi_aktif", False)
        self._mode_presentasi_aktif = on
        if hasattr(self, "a_presentasi"):
            self.a_presentasi.setChecked(on)
        if on:
            self._vis_docks = {}
            for d in (self.d_langkah, self.d_hier, self.d_kerja, self.d_prop, self.d_tamp,
                      self.d_inter, self.d_antre, self.d_log, self.d_pesan):
                if d is not None:
                    self._vis_docks[d] = d.isVisible()
                    d.hide()
            self._vis_toolbars = []
            for tb in self.findChildren(QToolBar):
                if tb.isVisible():
                    self._vis_toolbars.append(tb)
                    tb.hide()
            self.statusBar().showMessage("Mode Presentasi aktif — tekan F11 atau Esc untuk kembali.", 6000)
        else:
            for d, vis in getattr(self, "_vis_docks", {}).items():
                if vis:
                    d.show()
            for tb in getattr(self, "_vis_toolbars", []):
                tb.show()
            self.statusBar().showMessage("Kembali ke mode kerja biasa.", 3000)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape and getattr(self, "_mode_presentasi_aktif", False):
            self.toggle_mode_presentasi(False)
            ev.accept()
            return
        super().keyPressEvent(ev)

    def tentang(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        from .logo import Logo
        d = QDialog(self)
        d.setWindowTitle("Tentang VirmoLab")
        lay = QVBoxLayout(d)
        lay.setContentsMargins(28, 24, 28, 16)
        lay.addWidget(Logo(64, self.mode == "gelap"))
        lay.addSpacing(14)
        teks = QLabel(f"<b>Versi {VERSI}</b>" + (" (portable)" if paths.PORTABLE else "") +
                      "<br>Aplikasi molecular docking desktop, gratis dan open-source (GPL-3.0-or-later).<br><br>"
                      "Mesin: AutoDock-GPU (OpenCL), AutoDock Vina 1.2.7, AutoDock 4.2.6.<br>"
                      "Kimia: RDKit, Meeko, Open Babel, gemmi. Viewer: 3Dmol.js. UI: Qt (PySide6).<br>"
                      "MD &amp; MM/GBSA: OpenMM, OpenFF (Sage, NAGL), Amber ff14SB.<br><br>"
                      "© 2026 apt. Rizki Rahmadi Pratama, M. Farm<br>"
                      "<span style='font-size:8pt'>Hilbert Curve implementation copyright 1998, Rice University "
                      "(bagian dari OpenMM).</span><br><br>"
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

    def _layar_kerja(self):
        s = self.screen() or QApplication.primaryScreen()
        return s.availableGeometry()

    def _potong_ukuran_normal(self):
        """Ukuran tersimpan yang lebih besar dari area kerja membuat jendela melewati tepi layar."""
        if self.isMaximized():
            return
        layar = self._layar_kerja()
        g = self.geometry()
        pusat = g.center()
        if g.width() <= layar.width() and g.height() <= layar.height() and layar.contains(pusat):
            return
        if not any(s.availableGeometry().contains(pusat) for s in QApplication.screens()):
            self._ukuran_awal()
            return
        w = min(g.width(), layar.width())
        h = min(g.height(), layar.height())
        self.resize(w, h)
        self.move(max(layar.left(), min(g.left(), layar.right() - w + 1)),
                  max(layar.top(), min(g.top(), layar.bottom() - h + 1)))

    def _buka_penuh(self):
        """Memenuhi area kerja. Taskbar tetap tampil."""
        if not self.isMaximized():
            self.showMaximized()

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
        self.st.setValue(KUNCI_LAYOUT, self.saveState())
        self.st.setValue("layar_layout", self._kunci_layar())
        f, _ = QFileDialog.getSaveFileName(self, "Ekspor pengaturan & proyek",
                                           str(Path.home() / f"VirmoLab_{datetime.now():%Y%m%d}.vmdbackup"),
                                           "Cadangan VirmoLab (*.vmdbackup)")
        if not f:
            return
        kerja.jalankan(pindah.ekspor, f, self.st, ikut, VERSI, log=self.log.tulis, galat=self._galat,
                       selesai=lambda m: (self.log.tulis(f"Cadangan disimpan: {f}"),
                                          QMessageBox.information(self, "Pindah laptop",
                                                                  f"Cadangan tersimpan:\n{f}\n\nSalin berkas ini ke "
                                                                  "laptop baru, lalu Berkas › Pindah laptop › Impor.")))

    def impor_cadangan(self, f=None):
        from ..core import pindah
        if not f:
            f, _ = QFileDialog.getOpenFileName(self, "Impor pengaturan & proyek", str(Path.home()),
                                               "Cadangan VirmoLab (*.vmdbackup)")
        if not f:
            return
        try:
            meta = pindah.baca_meta(f)
        except Exception as e:
            self._galat(f"Berkas cadangan tidak terbaca: {e}")
            return
        if QMessageBox.question(self, "Impor pengaturan",
                                f"Cadangan VirmoLab {meta.get('versi', '')} dari {meta.get('dibuat', '')}.\n"
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
                                                               "VirmoLab dibuka berikutnya.")
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
        self._tampil_bawah(True)
        self.d_log.raise_()
        self.log.tulis("Uji mandiri dimulai…")

        def selesai(h):
            gagal = [x for x in h if not x["ok"]]
            teks = "\n".join(f"{'✓' if x['ok'] else '✗'}  {x['uji']}: {x['detail']}" for x in h)
            try:      # disertakan di paket Lapor masalah
                import json
                (paths.APPDATA / "uji_mandiri.json").write_text(json.dumps(
                    {"versi": VERSI, "hasil": h, "semua_ok": not gagal}, ensure_ascii=False, indent=1), encoding="utf-8")
            except OSError:
                pass
            (QMessageBox.information if not gagal else QMessageBox.warning)(
                self, "Uji mandiri", ("Semua komponen berfungsi.\n\n" if not gagal else
                                      f"{len(gagal)} uji gagal - lihat Bantuan › Dokumentasi › Mengatasi masalah.\n\n")
                + teks)
        kerja.jalankan(ujimandiri.uji, selesai=selesai, galat=self._galat, log=self.log.tulis)

    def lapor_masalah(self):
        from .dialog_bantuan import DialogLapor
        DialogLapor(VERSI, self.env, self).exec()

    def _belum(self):
        self._galat("Fitur ini sedang dibangun di tahap berikutnya.")

    def _info(self, t, detik=8000):
        """Kabar singkat: bilah status + catatan log (tanpa membuka panel Pesan)."""
        self.statusBar().showMessage(t, detik)
        self.log.tulis(t)

    def _galat(self, g):
        g_edu = arti.edukasi_galat(g)
        self.pesan.tulis(g_edu)
        self._pesan_belum_dibaca += 1
        if self._bawah_ditutup_pengguna:
            self._sinkron_bawah()      # pengguna sengaja menutup panel: cukup lencana di bilah status
        else:
            self._tampil_bawah(True, fokus=self.d_pesan)
        self.statusBar().showMessage(g.splitlines()[0][:160] if g else "", 8000)

    def closeEvent(self, e):
        d = getattr(self, "_dlg_md", None)
        if d is not None and d.proses_berjalan():
            r = QMessageBox.question(self, "MD sedang berjalan",
                                     "MD/MM-GBSA masih berjalan. Tutup VirmoLab?\n\nMD akan dijeda dengan checkpoint "
                                     "dan bisa dilanjutkan dari Analisis › MD & MM/GBSA.")
            if r != QMessageBox.Yes:
                e.ignore()
                return
            d.hentikan_untuk_keluar()
        if self.pelaksana.sibuk():
            r = QMessageBox.question(self, "Docking sedang berjalan",
                                     "Docking masih berjalan. Tutup VirmoLab?\n\nJob akan dijeda dan bisa dilanjutkan "
                                     "saat proyek dibuka lagi (ligan yang sudah selesai tidak diulang).\n\n"
                                     "Tip: minimize jendela agar docking tetap berjalan.")
            if r != QMessageBox.Yes:
                e.ignore()
                return
        self.pelaksana.hentikan_semua()
        from ..core import qc
        qc.tutup()
        self._simpan_diam()
        self.st.setValue("geometri", self.saveGeometry())
        self.st.setValue(KUNCI_LAYOUT, self.saveState())
        self.st.setValue("layar_layout", self._kunci_layar())
        self.st.remove("sesi_terbuka")  # ditutup normal: tidak perlu pemulihan
        if self.tray:
            self.tray.hide()
        super().closeEvent(e)
