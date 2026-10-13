"""Tab 'Uji & Grafik': lembar data -> uji statistik -> grafik publikasi.

Jenis data: kolom (bandingkan grup), XY dosis-respons (IC₅₀), ROC (skor negatif vs positif), kontingensi
(tabel frekuensi). Alur ala Prism (Data → Analisis → Grafik) dengan nama & tampilan sendiri. Data bisa
ditempel dari Excel (Ctrl+V), diimpor CSV, atau diisi dari hasil docking. Elemen grafik bisa diklik untuk
diformat di panel Format; tampilan bisa disimpan sebagai 'gaya' dan dipakai ulang. Tersimpan di proyek
(proyek.uji_grafik).
"""
import csv
import io
import json
from html import escape

import numpy as np
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox,
                               QPushButton, QScrollArea, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem,
                               QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from ..core import grafik_uji as G
from ..core import paths
from . import kit
from ..core import uji as U
from . import theme
from .panel_interaksi import KanvasSvg

BARIS_AWAL = 40
CONTOH_KOLOM = (["Kontrol", "Ekstrak 50", "Ekstrak 100"],
                [[4.17, 5.58, 5.18, 6.11, 4.50, 4.61, 5.17, 4.53, 5.33, 5.14],
                 [4.81, 4.17, 4.41, 3.59, 5.87, 3.83, 6.03, 4.89, 4.32, 4.69],
                 [6.31, 5.12, 5.54, 5.50, 5.37, 5.29, 4.92, 6.15, 5.80, 5.26]])
CONTOH_XY = (["Konsentrasi (µM)", "Ulangan 1", "Ulangan 2", "Ulangan 3"],
             [[0.01, 0.1, 1, 10, 100, 1000], [2, 8, 25, 70, 95, 99], [4, 6, 30, 68, 92, 101], [3, 9, 27, 72, 90, 98]])
_r = np.random.default_rng(3)
CONTOH_ROC = (["Decoy (negatif)", "Aktif (positif)"],
              [np.round(_r.normal(-7.3, 0.9, 30), 1).tolist(), np.round(_r.normal(-8.9, 0.9, 12), 1).tolist()])
CONTOH_KONT = (["Kelompok", "Membaik", "Tidak membaik"], [["Ekstrak", "Plasebo"], [18, 9], [7, 16]])
CONTOH_DUA = (["Perlakuan", "Hari 7", "Hari 14"],
              [["Kontrol"] * 5 + ["Ekstrak 50"] * 5 + ["Ekstrak 100"] * 5,
               [4.1, 4.6, 3.9, 4.4, 4.2, 4.9, 5.3, 5.1, 4.7, 5.0, 5.4, 5.9, 5.6, 5.2, 5.7],
               [4.3, 4.5, 4.0, 4.6, 4.2, 5.6, 6.1, 5.8, 5.5, 6.0, 7.2, 7.6, 6.9, 7.4, 7.1]])

JENIS_DATA = {"kolom": "Kolom (bandingkan grup)", "xy": "XY dosis-respons (IC₅₀)",
              "roc": "ROC (skor negatif vs positif)", "kontingensi": "Kontingensi (tabel frekuensi)",
              "dua_faktor": "Dua faktor (ANOVA dua arah)"}
KOLOM_AWAL = {"kolom": ["Grup A", "Grup B", "Grup C"],
              "xy": ["Konsentrasi (µM)", "Ulangan 1", "Ulangan 2", "Ulangan 3"],
              "roc": ["Negatif (decoy/kontrol)", "Positif (aktif/kasus)"],
              "kontingensi": ["Kelompok", "Kategori 1", "Kategori 2"],
              "dua_faktor": ["Faktor A", "B1", "B2"]}
PETUNJUK = {"kolom": "Kolom = grup; baris = ulangan.",
            "xy": "Kolom pertama = konsentrasi (> 0); kolom berikutnya = respons tiap ulangan.",
            "roc": "Kolom 1 = skor kelompok negatif (decoy/kontrol), kolom 2 = skor kelompok positif (aktif/kasus).",
            "kontingensi": "Kolom pertama = nama kelompok (baris tabel); kolom berikutnya = frekuensi tiap kategori.",
            "dua_faktor": "Kolom pertama = level faktor A (diulang tiap ulangan); judul kolom berikutnya = level "
                          "faktor B; isi = nilai."}

ELEMEN = {"grafik": "Grafik (umum)", "judul": "Judul", "label_y": "Label sumbu Y", "sumbu_y": "Sumbu Y",
          "sumbu_x": "Sumbu X", "grup": "Grup / warna", "braket": "Tanda signifikansi", "data": "Kurva & titik"}
ELEMEN_JENIS = {"kolom": ("grafik", "judul", "label_y", "sumbu_y", "sumbu_x", "grup", "braket"),
                "xy": ("grafik", "judul", "label_y", "sumbu_y", "sumbu_x", "data"),
                "roc": ("grafik", "judul", "sumbu_x", "data"),
                "kontingensi": ("grafik", "judul", "label_y", "sumbu_x", "grup"),
                "dua_faktor": ("grafik", "judul", "label_y", "sumbu_y", "sumbu_x", "grup")}
# gaya bawaan (tidak bisa dihapus). Kunci 'palet' ikut disimpan bersama kunci G.KUNCI_PRESET.
PRESET_BAWAAN = {
    "Bawaan VirmoLab": {"palet": "okabe"},
    "Jurnal hitam-putih": {"palet": "abu", "font": 11, "font_label": 12, "font_judul": 13, "font_tanda": 12,
                           "opasitas": 0.15, "tebal": 1.2, "ukuran_titik": 3.0},
    "Kolom jurnal (ringkas)": {"tinggi": 380, "font": 10, "font_label": 11, "font_judul": 12, "font_tanda": 11,
                               "ukuran_titik": 2.6, "tebal": 1.1},
    "Presentasi (huruf besar)": {"tinggi": 560, "font": 16, "font_label": 18, "font_judul": 22, "font_tanda": 18,
                                 "ukuran_titik": 5.0, "tebal": 2.2},
}
KUNCI_SETTINGS = "uji/gaya_tersimpan"


def _angka(t):
    t = (t or "").strip().replace(",", ".").replace("−", "-")
    try:
        return float(t) if t else None
    except ValueError:
        return None


def _p_html(p):
    """Nilai p untuk tabel HTML: '< 0,0001' harus di-escape (tanpa itu '<' dibaca sebagai tag dan nilainya hilang)."""
    return escape(U.f_p(p))


def _teks_angka(v):
    return "" if v is None else f"{v:g}".replace(".", ",")


class KanvasKlik(KanvasSvg):
    """KanvasSvg yang tahu letak elemen grafik: sorot saat disentuh, kirim kunci elemen saat diklik."""
    klik = Signal(str)

    def __init__(self):
        super().__init__()
        self.daerah = []
        self.pilih = None
        self._sorot = None
        self.aksen = kit.warna("acc")
        self.setMouseTracking(True)

    def _geo(self):
        s = self.r.defaultSize()
        k = min(self.width() / max(1, s.width()), self.height() / max(1, s.height()))
        return k, (self.width() - s.width() * k) / 2, (self.height() - s.height() * k) / 2

    def _cari(self, pos):
        if not self.r.isValid():
            return None
        k, ox, oy = self._geo()
        x, y = (pos.x() - ox) / k, (pos.y() - oy) / k
        kena = [(abs((x1 - x0) * (y1 - y0)), kunci) for kunci, x0, y0, x1, y1 in self.daerah
                if x0 <= x <= x1 and y0 <= y <= y1]
        return min(kena)[1] if kena else None

    def _rect(self, kunci):
        k, ox, oy = self._geo()
        for kc, x0, y0, x1, y1 in self.daerah:
            if kc == kunci:
                return QRectF(ox + x0 * k, oy + y0 * k, (x1 - x0) * k, (y1 - y0) * k).adjusted(-2, -2, 2, 2)
        return None

    def mouseMoveEvent(self, e):
        kunci = self._cari(e.position())
        if kunci != self._sorot:
            self._sorot = kunci
            self.setCursor(Qt.PointingHandCursor if kunci else Qt.ArrowCursor)
            nama = ELEMEN.get(kunci.split(":")[0], "") if kunci else ""
            self.setToolTip(f"{nama} - klik untuk memformat" if nama else "Klik latar untuk format grafik umum")
            self.update()

    def leaveEvent(self, _e):
        self._sorot = None
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.r.isValid():
            self.pilih = self._cari(e.position()) or "grafik"
            self.klik.emit(self.pilih)
            self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self.r.isValid():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for kunci, gaya_garis, alfa in ((self._sorot, Qt.DashLine, 120), (self.pilih, Qt.SolidLine, 230)):
            if not kunci or kunci == "grafik":
                continue
            r = self._rect(kunci)
            if r is None:
                continue
            c = QColor(self.aksen)
            c.setAlpha(alfa)
            p.setPen(QPen(c, 1.4, gaya_garis))
            isi = QColor(self.aksen)
            isi.setAlpha(18 if gaya_garis == Qt.SolidLine else 10)
            p.setBrush(isi)
            p.drawRoundedRect(r, 4, 4)
        p.end()


class TombolWarna(QPushButton):
    warna = Signal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(84)
        self._w = "#0072B2"
        self.clicked.connect(self._pilih)

    def set_warna(self, w):
        self._w = w
        self.setText(w.upper())
        gelap = QColor(w).lightness() < 140
        self.setStyleSheet(f"QPushButton{{background:{w};color:{'#ffffff' if gelap else '#000000'};"
                           "border:1px solid rgba(0,0,0,0.25);border-radius:4px;padding:3px 6px;}}")

    def _pilih(self):
        c = QColorDialog.getColor(QColor(self._w), self, "Pilih warna")
        if c.isValid():
            self.set_warna(c.name())
            self.warna.emit(c.name())


class PanelFormat(QFrame):
    """Panel kanan: format elemen grafik terpilih + gaya tersimpan."""

    def __init__(self, tab):
        super().__init__()
        self.tab = tab
        self._diam = False
        self.setObjectName("panelFormat")
        self.setMinimumWidth(250)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        judul = QLabel("<b>Format grafik</b>")
        lay.addWidget(judul)
        tip = QLabel("Klik bagian grafik (judul, sumbu, batang, tanda *) atau pilih elemen di bawah.")
        tip.setWordWrap(True)
        tip.setObjectName("muted")
        lay.addWidget(tip)
        self.c_el = QComboBox()
        self.c_el.currentIndexChanged.connect(self._ganti_el)
        lay.addWidget(self.c_el)
        self.tumpuk = QStackedWidget()
        lay.addWidget(self.tumpuk)
        self.halaman = {}
        self._kontrol = []          # (widget, kunci gaya, jenis)
        self._buat_halaman()
        lay.addSpacing(6)
        garis = QFrame()
        garis.setFrameShape(QFrame.HLine)
        garis.setObjectName("garis")
        lay.addWidget(garis)
        lay.addWidget(QLabel("<b>Gaya tersimpan</b>"))
        self.c_preset = QComboBox()
        lay.addWidget(self.c_preset)
        bar = QHBoxLayout()
        for t, fn, tip_ in (("Terapkan", self._terapkan, "Pakai gaya ini (teks & rentang sumbu tidak diubah)"),
                            ("Simpan…", self._simpan_preset, "Simpan tampilan sekarang sebagai gaya baru"),
                            ("Hapus", self._hapus_preset, "Hapus gaya buatan Anda")):
            b = QPushButton(t)
            b.setToolTip(tip_)
            b.clicked.connect(fn)
            bar.addWidget(b)
        lay.addLayout(bar)
        b_reset = QPushButton("↺ Kembalikan tampilan bawaan")
        b_reset.clicked.connect(self._atur_ulang)
        lay.addWidget(b_reset)
        lay.addStretch(1)
        self.isi_preset()

    # ------------------------------------------------------------ halaman
    def _form(self, kunci):
        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(0, 4, 0, 0)
        f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.tumpuk.addWidget(w)
        self.halaman[kunci] = w
        return f

    def _spin(self, kunci, lo, hi, langkah=1.0, des=0, khusus=None):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(langkah)
        s.setDecimals(des)
        if khusus:
            s.setSpecialValueText(khusus)
        s.valueChanged.connect(lambda v, k=kunci: self._set(k, int(v) if des == 0 else round(v, des)))
        self._kontrol.append((s, kunci, "spin"))
        return s

    def _cek(self, teks, kunci):
        c = QCheckBox(teks)
        c.toggled.connect(lambda v, k=kunci: self._set(k, v))
        self._kontrol.append((c, kunci, "cek"))
        return c

    def _opsional(self, kunci):
        e = QLineEdit()
        e.setPlaceholderText("otomatis")
        e.setClearButtonEnabled(True)
        e.editingFinished.connect(lambda k=kunci, e=e: self._set(k, _angka(e.text())))
        self._kontrol.append((e, kunci, "opsional"))
        return e

    def _combo(self, kunci, pilihan):
        c = QComboBox()
        for k, t in pilihan.items():
            c.addItem(t, k)
        c.currentIndexChanged.connect(lambda _i, k=kunci, c=c: self._set(k, c.currentData()))
        self._kontrol.append((c, kunci, "combo"))
        return c

    def _buat_halaman(self):
        t = self.tab
        f = self._form("grafik")
        f.addRow("Lebar (px)", self._spin("lebar", 0, 3000, 20, khusus="otomatis"))
        f.addRow("Tinggi (px)", self._spin("tinggi", 250, 1600, 20))
        f.addRow("Ukuran huruf", self._spin("font", 7, 32, 1))
        f.addRow("Tebal garis", self._spin("tebal", 0.5, 4, 0.1, 1))
        f.addRow("Palet", t.c_palet)
        f.addRow("", self._cek("Garis kisi horizontal", "kisi"))
        f.addRow("", self._cek("Tampilkan titik data individual", "titik"))
        self.e_anot = QLineEdit()
        self.e_anot.setPlaceholderText("Teks catatan (| = baris baru)")
        self.e_anot.editingFinished.connect(lambda: self._set("anotasi", self.e_anot.text()))
        f.addRow("Anotasi", self.e_anot)
        f.addRow("Posisi", self._combo("pos_anotasi", G.POSISI_ANOTASI))

        f = self._form("judul")
        f.addRow("Teks", t.e_judul)
        f.addRow("Ukuran", self._spin("font_judul", 8, 40, 1))

        f = self._form("label_y")
        f.addRow("Teks", t.e_y)
        f.addRow("Ukuran", self._spin("font_label", 7, 36, 1))

        f = self._form("sumbu_y")
        f.addRow("Minimum", self._opsional("y_min"))
        f.addRow("Maksimum", self._opsional("y_maks"))
        f.addRow("Jarak tik", self._opsional("y_langkah"))
        f.addRow("", self._cek("Skala logaritmik (log₁₀)", "y_log"))
        sub = QLabel("<b>Patah sumbu</b> - rentang di antara dua nilai ini dilompati (berguna bila satu grup "
                     "jauh lebih besar).")
        sub.setWordWrap(True)
        f.addRow(sub)
        f.addRow("Patah dari", self._opsional("patah_dari"))
        f.addRow("Patah sampai", self._opsional("patah_sampai"))
        b = QPushButton("Sumbu Y otomatis")
        b.clicked.connect(self._y_otomatis)
        f.addRow("", b)
        self.e_acuan = QLineEdit()
        self.e_acuan.setPlaceholderText("mis. −8,2=Ligan asli; −7")
        self.e_acuan.setToolTip("Garis acuan horizontal: nilai=label, pisahkan dengan titik koma")
        self.e_acuan.editingFinished.connect(lambda: self._set("acuan", self.e_acuan.text().strip()))
        f.addRow("Garis acuan", self.e_acuan)

        f = self._form("sumbu_x")
        self.e_lx = QLineEdit()
        self.e_lx.setPlaceholderText("(tanpa label)")
        self.e_lx.editingFinished.connect(lambda: self._set("label_x", self.e_lx.text().strip()))
        f.addRow("Label sumbu X", self.e_lx)
        f.addRow("", self._cek("Nama grup miring", "miring"))
        f.addRow("Ukuran huruf", self._spin("font", 7, 32, 1))

        f = self._form("grup")
        self.c_grup = QComboBox()
        self.c_grup.currentIndexChanged.connect(self._segarkan_warna)
        f.addRow("Grup", self.c_grup)
        self.b_warna = TombolWarna()
        self.b_warna.warna.connect(self._set_warna_grup)
        b_pal = QPushButton("Palet")
        b_pal.setToolTip("Kembalikan warna grup ini ke palet")
        b_pal.clicked.connect(lambda: self._set_warna_grup(None))
        bw = QHBoxLayout()
        bw.addWidget(self.b_warna)
        bw.addWidget(b_pal)
        f.addRow("Warna", bw)
        catatan = QLabel("Berlaku untuk semua grup:")
        catatan.setObjectName("muted")
        f.addRow(catatan)
        f.addRow("Penanda", self._combo("bentuk", G.BENTUK))
        f.addRow("Ukuran penanda", self._spin("ukuran_titik", 1, 12, 0.2, 1))
        f.addRow("Opasitas isi", self._spin("opasitas", 0, 1, 0.05, 2))
        f.addRow("Lebar batang", self._spin("lebar_batang", 0.2, 0.9, 0.05, 2))

        f = self._form("braket")
        f.addRow("Tanda", t.c_tanda)
        f.addRow("", t.c_ns)
        f.addRow("Ukuran", self._spin("font_tanda", 7, 32, 1))

        f = self._form("data")
        self.b_warna_d = TombolWarna()
        self.b_warna_d.warna.connect(lambda w: self._set_warna("0", w))
        f.addRow("Warna", self.b_warna_d)
        f.addRow("Penanda", self._combo("bentuk", G.BENTUK))
        f.addRow("Ukuran penanda", self._spin("ukuran_titik", 1, 12, 0.2, 1))
        f.addRow("Tebal garis", self._spin("tebal", 0.5, 4, 0.1, 1))
        f.addRow("", self._cek("Garis kisi", "kisi"))

    # ------------------------------------------------------------ status
    def atur_elemen(self, jenis):
        self._diam = True
        lama = self.c_el.currentData()
        self.c_el.clear()
        for k in ELEMEN_JENIS[jenis]:
            self.c_el.addItem(ELEMEN[k], k)
        i = self.c_el.findData(lama)
        self.c_el.setCurrentIndex(max(0, i))
        self._diam = False
        self._ganti_el()

    def pilih(self, kunci):
        dasar, _, idx = kunci.partition(":")
        if dasar == "label_x":
            dasar = "sumbu_x"
        i = self.c_el.findData(dasar)
        if i < 0:
            i = 0
        self.c_el.setCurrentIndex(i)
        if dasar == "grup" and idx.isdigit() and int(idx) < self.c_grup.count():
            self.c_grup.setCurrentIndex(int(idx))

    def _ganti_el(self, *_):
        k = self.c_el.currentData()
        if k in self.halaman:
            self.tumpuk.setCurrentWidget(self.halaman[k])
        if not self._diam:
            self.tab.kanvas.pilih = None if k in (None, "grafik") else k if k != "grup" else \
                f"grup:{max(0, self.c_grup.currentIndex())}"
            self.tab.kanvas.update()

    def segarkan(self):
        """Isi semua kontrol dari tab.gaya."""
        g = self.tab.gaya
        self._diam = True
        for w, k, jenis in self._kontrol:
            w.blockSignals(True)
            if jenis == "spin":
                w.setValue(float(g.get(k) or 0))
            elif jenis == "cek":
                w.setChecked(bool(g.get(k)))
            elif jenis == "opsional":
                w.setText(_teks_angka(g.get(k)))
            elif jenis == "combo":
                w.setCurrentIndex(max(0, w.findData(g.get(k))))
            w.blockSignals(False)
        self.e_lx.setText(g.get("label_x", ""))
        self.e_acuan.setText(g.get("acuan", "") or "")
        self.e_anot.setText(g.get("anotasi", "") or "")
        nama = self.tab.nama_grup()
        i = self.c_grup.currentIndex()
        self.c_grup.blockSignals(True)
        self.c_grup.clear()
        self.c_grup.addItems(nama)
        self.c_grup.setCurrentIndex(min(max(0, i), len(nama) - 1) if nama else -1)
        self.c_grup.blockSignals(False)
        self._segarkan_warna()
        self.b_warna_d.set_warna(G.warna_grup(g, "okabe", 0))
        self._diam = False

    def _segarkan_warna(self, *_):
        i = max(0, self.c_grup.currentIndex())
        self.b_warna.set_warna(G.warna_grup(self.tab.gaya, self.tab.c_palet.currentData(), i))
        if not self._diam and self.c_el.currentData() == "grup":
            self.tab.kanvas.pilih = f"grup:{i}"
            self.tab.kanvas.update()

    def _set(self, kunci, nilai):
        if self._diam:
            return
        self.tab.gaya[kunci] = nilai
        self.tab.gaya_berubah()

    def _set_warna(self, i, w):
        warna = dict(self.tab.gaya.get("warna") or {})
        if w:
            warna[str(i)] = w
        else:
            warna.pop(str(i), None)
        self.tab.gaya["warna"] = warna
        self.tab.gaya_berubah()

    def _set_warna_grup(self, w):
        self._set_warna(max(0, self.c_grup.currentIndex()), w)
        self._segarkan_warna()

    def _y_otomatis(self):
        for k in ("y_min", "y_maks", "y_langkah", "patah_dari", "patah_sampai"):
            self.tab.gaya[k] = None
        self.tab.gaya["y_log"] = False
        self.segarkan()
        self.tab.gaya_berubah()

    def _atur_ulang(self):
        teks = {k: self.tab.gaya.get(k) for k in ("label_x",)}
        self.tab.gaya = G.gaya_lengkap(teks)
        self.tab.c_palet.setCurrentIndex(0)
        self.segarkan()
        self.tab.gaya_berubah()

    # ------------------------------------------------------------ gaya tersimpan
    @staticmethod
    def preset_pengguna():
        try:
            d = json.loads(paths.settings().value(KUNCI_SETTINGS, "{}") or "{}")
            return d if isinstance(d, dict) else {}
        except (ValueError, TypeError):
            return {}

    def isi_preset(self, pilih=None):
        self.c_preset.clear()
        for n in PRESET_BAWAAN:
            self.c_preset.addItem(n, ("bawaan", n))
        for n in sorted(self.preset_pengguna()):
            self.c_preset.addItem(f"★ {n}", ("pengguna", n))
        if pilih:
            self.c_preset.setCurrentIndex(max(0, self.c_preset.findData(("pengguna", pilih))))

    def _terapkan(self):
        d = self.c_preset.currentData()
        if not d:
            return
        p = PRESET_BAWAAN.get(d[1]) if d[0] == "bawaan" else self.preset_pengguna().get(d[1])
        if p is None:
            return
        dasar = G.gaya_lengkap()
        for k in G.KUNCI_PRESET:
            self.tab.gaya[k] = p.get(k, dasar[k])
        i = self.tab.c_palet.findData(p.get("palet", "okabe"))
        self.tab._diam = True
        self.tab.c_palet.setCurrentIndex(max(0, i))
        self.tab._diam = False
        self.segarkan()
        self.tab.gaya_berubah()

    def _simpan_preset(self):
        nama, ok = QInputDialog.getText(self, "Simpan gaya", "Nama gaya (huruf, warna, ukuran, penanda):")
        nama = nama.strip()
        if not ok or not nama:
            return
        semua = self.preset_pengguna()
        if nama in semua and QMessageBox.question(self, "Simpan gaya", f"Gaya “{nama}” sudah ada. Timpa?") \
                != QMessageBox.Yes:
            return
        semua[nama] = {k: self.tab.gaya.get(k) for k in G.KUNCI_PRESET}
        semua[nama]["palet"] = self.tab.c_palet.currentData()
        paths.settings().setValue(KUNCI_SETTINGS, json.dumps(semua, ensure_ascii=False))
        self.isi_preset(nama)

    def _hapus_preset(self):
        d = self.c_preset.currentData()
        if not d or d[0] != "pengguna":
            QMessageBox.information(self, "Hapus gaya", "Gaya bawaan tidak bisa dihapus.")
            return
        if QMessageBox.question(self, "Hapus gaya", f"Hapus gaya “{d[1]}”?") != QMessageBox.Yes:
            return
        semua = self.preset_pengguna()
        semua.pop(d[1], None)
        paths.settings().setValue(KUNCI_SETTINGS, json.dumps(semua, ensure_ascii=False))
        self.isi_preset()


class ComboRingkas(QComboBox):
    """QComboBox dengan minimum size hint fleksibel agar tidak memaksakan lebar berlebih ke layout induk."""
    def minimumSizeHint(self):
        return QSize(80, super().minimumSizeHint().height())


class TabUji(QWidget):
    ekspor = Signal(str)        # salin | svg | png | komposer
    berubah = Signal()          # data/pengaturan berubah -> simpan proyek

    def minimumSizeHint(self):
        return QSize(500, 340)

    def __init__(self):
        super().__init__()
        self.mode = "terang"
        self.hasil = None
        self.gaya = G.gaya_lengkap()
        self._diam = False
        self._teks = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 6)
        self.c_data = ComboRingkas()
        for k, t in JENIS_DATA.items():
            self.c_data.addItem(t, k)
        self.c_data.currentIndexChanged.connect(self._ganti_jenis)
        bar.addWidget(QLabel("Data "))
        bar.addWidget(self.c_data)
        b_isi = QToolButton()
        b_isi.setText("Isi data ▾")
        b_isi.setPopupMode(QToolButton.InstantPopup)
        self.m_isi = QMenu(self)
        self.m_isi.addAction("Contoh data", self.isi_contoh)
        self.m_isi.addAction("Tempel dari Excel (Ctrl+V)", self.tempel)
        self.m_isi.addAction("Impor CSV…", self.impor_csv)
        self.m_isi.addSeparator()
        self.a_docking = self.m_isi.addAction("ΔG per job dari hasil docking", lambda: self.mintaDocking("job"))
        self.a_docking2 = self.m_isi.addAction("ΔG per mesin dari hasil docking", lambda: self.mintaDocking("mesin"))
        self.m_isi.addSeparator()
        self.m_isi.addAction("Tambah kolom", self.tambah_kolom)
        self.m_isi.addAction("Kosongkan lembar", self.kosongkan)
        b_isi.setMenu(self.m_isi)
        bar.addWidget(b_isi)
        bar.addSpacing(14)
        self.c_uji = ComboRingkas()
        self.c_pasang = QCheckBox("Berpasangan")
        self.c_pasang.setToolTip("Baris yang sama di semua kolom = subjek/ulangan yang sama (≥ 3 kolom: ANOVA "
                                 "pengukuran berulang / Friedman)")
        self.c_koreksi = ComboRingkas()
        for k, t in U.KOREKSI.items():
            self.c_koreksi.addItem(f"Koreksi {t}", k)
        self.c_koreksi.setToolTip("Koreksi p untuk perbandingan ganda (Dunn, uji lanjut berpasangan, ANOVA dua arah). "
                                  "Tukey, Games-Howell, dan Dunnett sudah terkoreksi bawaan.")
        self.c_arah = ComboRingkas()
        self.c_arah.addItem("Skor tinggi = positif", False)
        self.c_arah.addItem("Skor rendah = positif (mis. ΔG)", True)
        self.c_arah.setToolTip("Arah skor: untuk ΔG docking, nilai lebih negatif = lebih mungkin aktif")
        self.c_kurva = ComboRingkas()
        for k, t in G.KURVA_ROC.items():
            self.c_kurva.addItem(t, k)
        self.c_kurva.setToolTip("ROC biasa, ROC semilog (menilai pengayaan dini/logAUC), atau kurva pengayaan")
        for w in (QLabel("Uji "), self.c_uji, self.c_pasang, self.c_koreksi, self.c_arah, self.c_kurva):
            bar.addWidget(w)
        bar.addStretch(1)
        lay.addLayout(bar)

        self.c_grafik = ComboRingkas()
        for k, t in G.JENIS_GRAFIK.items():
            self.c_grafik.addItem(t, k)
        self.c_galat = ComboRingkas()
        for k, t in G.GALAT.items():
            self.c_galat.addItem(t, k)
        self.c_tanda = ComboRingkas()
        self.c_tanda.addItem("Tanda * / **", "bintang")
        self.c_tanda.addItem("p eksak", "eksak")
        self.c_tanda.addItem("Tanpa tanda", "")
        self.c_ns = QCheckBox("Tampilkan ns")
        self.c_palet = ComboRingkas()
        self.c_palet.addItem("Okabe-Ito", "okabe")
        self.c_palet.addItem("Biru", "biru")
        self.c_palet.addItem("Abu-abu (cetak)", "abu")
        self.e_y = QLineEdit()
        self.e_y.setPlaceholderText("Label sumbu Y")
        self.e_judul = QLineEdit()
        self.e_judul.setPlaceholderText("Judul (opsional)")
        bar2 = QHBoxLayout()
        bar2.setContentsMargins(8, 0, 8, 6)
        self.l_grafik = QLabel("Grafik ")
        for w in (self.l_grafik, self.c_grafik, self.c_galat):
            bar2.addWidget(w)
        self.l_petunjuk = QLabel()
        self.l_petunjuk.setObjectName("muted")
        bar2.addSpacing(10)
        bar2.addWidget(self.l_petunjuk, 1)

        b_salin = QPushButton("Salin")
        b_salin.setToolTip("Salin grafik ke clipboard")
        b_salin.clicked.connect(lambda: self.ekspor.emit("salin"))
        bar2.addWidget(b_salin)

        b_ekspor = QToolButton()
        b_ekspor.setText("Ekspor ▾")
        b_ekspor.setPopupMode(QToolButton.InstantPopup)
        m_eks = QMenu(self)
        m_eks.addAction("Simpan SVG/PDF…", lambda: self.ekspor.emit("svg"))
        m_eks.addAction("Simpan PNG/TIFF…", lambda: self.ekspor.emit("png"))
        m_eks.addSeparator()
        m_eks.addAction("＋ Tambahkan ke Komposer figur", lambda: self.ekspor.emit("komposer"))
        b_ekspor.setMenu(m_eks)
        bar2.addWidget(b_ekspor)

        self.b_validasi = QPushButton("Paket validasi protokol…")
        self.b_validasi.setToolTip("Buka wizard paket validasi protokol docking terstandar untuk naskah ilmiah")
        self.b_validasi.clicked.connect(self._buka_wizard_validasi)
        bar2.addWidget(self.b_validasi)

        self.b_format = QToolButton()
        self.b_format.setText("Format ▸")
        self.b_format.setCheckable(True)
        self.b_format.setToolTip("Tampilkan/sembunyikan panel Format (klik elemen grafik untuk memformat)")
        bar2.addWidget(self.b_format)
        lay.addLayout(bar2)

        bagi = QSplitter(Qt.Horizontal)
        self.tabel = QTableWidget(BARIS_AWAL, 3)
        self.tabel.horizontalHeader().sectionDoubleClicked.connect(self._ganti_nama_kolom)
        self.tabel.horizontalHeader().setToolTip("Klik dua kali judul kolom untuk mengganti nama")
        self.tabel.itemChanged.connect(self._data_berubah)
        QShortcut(QKeySequence.Paste, self.tabel, self.tempel)
        QShortcut(QKeySequence.Delete, self.tabel, self._hapus_sel)
        bagi.addWidget(self.tabel)
        kanan = QSplitter(Qt.Vertical)
        self.kanvas = KanvasKlik()
        self.kanvas.klik.connect(self._klik_elemen)
        kanan.addWidget(self.kanvas)
        bawah = QWidget()
        bl = QVBoxLayout(bawah)
        bl.setContentsMargins(0, 0, 0, 0)
        self.info = QTextBrowser()
        self.info.setOpenLinks(False)
        bl.addWidget(self.info)
        b_teks = QPushButton("Salin hasil && metode")
        b_teks.clicked.connect(self.salin_teks)
        bl.addWidget(b_teks, 0, Qt.AlignRight)
        kanan.addWidget(bawah)
        kanan.setSizes([520, 300])
        bagi.addWidget(kanan)
        self.format = PanelFormat(self)
        gulir = QScrollArea()
        gulir.setWidget(self.format)
        gulir.setWidgetResizable(True)
        gulir.setFrameShape(QFrame.NoFrame)
        gulir.setMinimumWidth(180)
        self.gulir_format = gulir
        bagi.addWidget(gulir)
        bagi.setSizes([340, 820, 240])
        bagi.setCollapsible(2, True)
        lay.addWidget(bagi, 1)
        tampil = paths.settings().value("uji/panel_format", True)
        tampil = tampil if isinstance(tampil, bool) else str(tampil).lower() == "true"
        self.b_format.setChecked(tampil)
        self._tampil_format(tampil)
        self.b_format.toggled.connect(self._tampil_format)
        for w in (self.c_uji, self.c_grafik, self.c_galat, self.c_tanda, self.c_palet, self.c_arah, self.c_kurva,
                  self.c_koreksi):
            w.currentIndexChanged.connect(self._opsi_berubah)
        for w in (self.c_pasang, self.c_ns):
            w.toggled.connect(self._opsi_berubah)
        for w in (self.e_y, self.e_judul):
            w.editingFinished.connect(self._opsi_berubah)
        self.c_palet.currentIndexChanged.connect(lambda *_: self.format._segarkan_warna())
        self.mintaDocking = lambda _k: None      # diganti JendelaUtama
        self._ganti_jenis()

    def _buka_wizard_validasi(self):
        induk = self.window()
        if hasattr(induk, "buka_validasi_protokol"):
            induk.buka_validasi_protokol()
        else:
            from .dialog_validasi_protokol import DialogValidasiProtokol
            d = DialogValidasiProtokol(self)
            d.exec()

    def _tampil_format(self, v):
        self.gulir_format.setVisible(v)
        self.b_format.setText("Format ◂" if v else "Format ▸")
        paths.settings().setValue("uji/panel_format", bool(v))

    def _klik_elemen(self, kunci):
        if not self.b_format.isChecked():
            self.b_format.setChecked(True)
        self.format.pilih(kunci)

    def _opsi_berubah(self, *_):
        if not self._diam:
            self.hitung()
            self.berubah.emit()

    def gaya_berubah(self):
        self.hitung()
        self.berubah.emit()

    # ------------------------------------------------------------ data
    def jenis(self):
        return self.c_data.currentData()

    def _ganti_jenis(self, *_):
        j = self.jenis()
        self._diam = True
        self.c_uji.clear()
        if j == "xy":
            for k, t in U.MODEL_DOSIS.items():
                self.c_uji.addItem(t, k)
        elif j == "roc":
            self.c_uji.addItem("Kurva ROC (AUC, CI DeLong)", "roc")
        elif j == "kontingensi":
            self.c_uji.addItem("Otomatis (Fisher eksak / χ²)", "kontingensi")
        elif j == "dua_faktor":
            self.c_uji.addItem("ANOVA dua arah (tipe III) + perbandingan per level B", "anova2")
        else:
            for k, t in U.UJI_BANYAK.items():
                self.c_uji.addItem(t, k)
        kolom = j == "kolom"
        for w in (self.c_pasang, self.c_grafik):
            w.setVisible(kolom)
        for w in (self.l_grafik, self.c_galat):
            w.setVisible(j in ("kolom", "dua_faktor"))
        self.c_koreksi.setVisible(j in ("kolom", "dua_faktor"))
        self.c_arah.setVisible(j == "roc")
        self.c_kurva.setVisible(j == "roc")
        self.l_petunjuk.setText(PETUNJUK[j])
        for a in (self.a_docking, self.a_docking2):
            a.setEnabled(j in ("kolom", "roc"))
        if self.tabel.columnCount() and not any(self._ada_isi(i) for i in range(self.tabel.columnCount())):
            self._set_kolom(KOLOM_AWAL[j])
        self.format.atur_elemen(j)
        self._diam = False
        self.hitung()

    def _ada_isi(self, i):
        return any(self.tabel.item(r, i) and self.tabel.item(r, i).text().strip() for r in range(self.tabel.rowCount()))

    def _set_kolom(self, nama):
        self.tabel.setColumnCount(len(nama))
        self.tabel.setHorizontalHeaderLabels(nama)

    def nama_kolom(self):
        return [(self.tabel.horizontalHeaderItem(i).text() if self.tabel.horizontalHeaderItem(i) else f"Kolom {i + 1}")
                for i in range(self.tabel.columnCount())]

    def nama_grup(self):
        """Nama yang dipakai daftar warna di panel Format."""
        j = self.jenis()
        if j == "kolom":
            return self._grup()[0]
        if j == "kontingensi":
            t = self._tabel_kont()
            return t[2] if t else []
        if j == "dua_faktor":
            return [n for i, n in enumerate(self.nama_kolom()) if i and self._kolom(i)]
        return []

    def _kolom(self, i):
        return U.bersihkan([self.tabel.item(r, i).text() for r in range(self.tabel.rowCount())
                            if self.tabel.item(r, i) and self.tabel.item(r, i).text().strip()])

    def _kolom_mentah(self, i):
        """Nilai per baris (None bila kosong/teks) - untuk XY & berpasangan agar baris tetap sejajar."""
        out = []
        for r in range(self.tabel.rowCount()):
            it = self.tabel.item(r, i)
            v = U.bersihkan([it.text()]) if it and it.text().strip() else []
            out.append(v[0] if v else None)
        return out

    def isi(self, nama, kolom, jenis=None):
        """nama: judul kolom; kolom: list nilai per kolom."""
        self._diam = True
        if jenis:
            self.c_data.blockSignals(True)
            self.c_data.setCurrentIndex(self.c_data.findData(jenis))
            self.c_data.blockSignals(False)
            self._diam = False
            self._ganti_jenis()
            self._diam = True
        self.tabel.clearContents()
        self.tabel.setRowCount(max(BARIS_AWAL, max((len(k) for k in kolom), default=0) + 5))
        self._set_kolom(nama)
        for i, k in enumerate(kolom):
            for r, v in enumerate(k):
                self.tabel.setItem(r, i, QTableWidgetItem("" if v is None else f"{v:g}" if isinstance(v, float)
                                                          else str(v)))
        self._diam = False
        self.hitung()
        self.berubah.emit()

    def isi_contoh(self):
        j = self.jenis()
        self.e_judul.setText("")
        if j == "xy":
            self.isi(*CONTOH_XY)
            self.e_y.setText("Inhibisi (%)")
        elif j == "roc":
            self.isi(*CONTOH_ROC)
            self.c_arah.setCurrentIndex(1)
            self.e_judul.setText("Validasi penapisan: aktif vs decoy")
        elif j == "kontingensi":
            self.isi(*CONTOH_KONT)
            self.e_y.setText("Persentase pasien (%)")
        elif j == "dua_faktor":
            self.isi(*CONTOH_DUA)
            self.e_y.setText("Berat kering (g)")
        else:
            self.isi(*CONTOH_KOLOM)
            self.e_y.setText("Berat kering (g)")
        self.hitung()

    def tempel(self):
        teks = QGuiApplication.clipboard().text()
        if not teks.strip():
            return
        baris = [b.split("\t") for b in teks.replace("\r", "").split("\n") if b.strip()]
        r0, c0 = max(0, self.tabel.currentRow()), max(0, self.tabel.currentColumn())
        # baris pertama berisi teks (bukan angka) -> judul kolom (kontingensi: sel pertama boleh kosong)
        judul = None
        cek = baris[0][1:] if self.jenis() == "kontingensi" else baris[0]
        if baris and cek and not U.bersihkan(cek) and r0 == 0:
            judul, baris = baris[0], baris[1:]
        self._diam = True
        need_c = c0 + max((len(b) for b in baris), default=0)
        if need_c > self.tabel.columnCount():
            nama = self.nama_kolom() + [f"Kolom {i + 1}" for i in range(self.tabel.columnCount(), need_c)]
            self._set_kolom(nama)
        if judul:
            nama = self.nama_kolom()
            for i, t in enumerate(judul):
                if c0 + i < len(nama) and t.strip():
                    nama[c0 + i] = t.strip()
            self._set_kolom(nama)
        if r0 + len(baris) > self.tabel.rowCount():
            self.tabel.setRowCount(r0 + len(baris) + 5)
        for r, b in enumerate(baris):
            for c, v in enumerate(b):
                self.tabel.setItem(r0 + r, c0 + c, QTableWidgetItem(v.strip()))
        self._diam = False
        self.hitung()
        self.berubah.emit()

    def impor_csv(self):
        f, _ = QFileDialog.getOpenFileName(self, "Impor CSV", "", "CSV (*.csv *.txt)")
        if not f:
            return
        teks = open(f, encoding="utf-8-sig", errors="replace").read()
        pemisah = ";" if teks.count(";") > teks.count(",") else ("\t" if "\t" in teks else ",")
        baris = list(csv.reader(io.StringIO(teks), delimiter=pemisah))
        if not baris:
            return
        cek = baris[0][1:] if self.jenis() == "kontingensi" else baris[0]
        ada_judul = not U.bersihkan(cek)
        judul = baris[0] if ada_judul else [f"Kolom {i + 1}" for i in range(len(baris[0]))]
        data = baris[1:] if ada_judul else baris
        kolom = [[(r[i] if i < len(r) else "") for r in data] for i in range(len(judul))]
        self.isi(judul, kolom)

    def tambah_kolom(self):
        self._set_kolom(self.nama_kolom() + [f"Kolom {self.tabel.columnCount() + 1}"])
        self.berubah.emit()

    def kosongkan(self):
        self._diam = True
        self.tabel.clearContents()
        self._diam = False
        self.hitung()
        self.berubah.emit()

    def _hapus_sel(self):
        self._diam = True
        for it in self.tabel.selectedItems():
            it.setText("")
        self._diam = False
        self.hitung()
        self.berubah.emit()

    def _ganti_nama_kolom(self, i):
        t, ok = QInputDialog.getText(self, "Nama kolom", "Nama:", text=self.nama_kolom()[i])
        if ok and t.strip():
            nama = self.nama_kolom()
            nama[i] = t.strip()
            self._set_kolom(nama)
            self.hitung()
            self.berubah.emit()

    def _data_berubah(self, *_):
        if not self._diam:
            self.hitung()
            self.berubah.emit()

    # --------------------------------------------------------- simpan/muat
    def ke_dict(self):
        return {"jenis": self.jenis(), "kolom": self.nama_kolom(),
                "data": [[(self.tabel.item(r, i).text() if self.tabel.item(r, i) else "")
                          for r in range(self.tabel.rowCount())] for i in range(self.tabel.columnCount())],
                "uji": self.c_uji.currentData(), "grafik": self.c_grafik.currentData(),
                "galat": self.c_galat.currentData(), "tanda": self.c_tanda.currentData(), "ns": self.c_ns.isChecked(),
                "palet": self.c_palet.currentData(), "pasang": self.c_pasang.isChecked(), "label_y": self.e_y.text(),
                "judul": self.e_judul.text(), "arah": bool(self.c_arah.currentData()),
                "kurva": self.c_kurva.currentData(), "koreksi": self.c_koreksi.currentData(), "gaya": self.gaya}

    def muat(self, d):
        if not d:
            self._diam = True
            self.tabel.clearContents()
            self.gaya = G.gaya_lengkap()
            self._diam = False
            self.format.segarkan()
            self.hitung()
            return
        self.gaya = G.gaya_lengkap(d.get("gaya"))
        self.isi(d.get("kolom") or ["Grup A", "Grup B"], [[v for v in k] for k in d.get("data") or []],
                 d.get("jenis", "kolom") if d.get("jenis") in JENIS_DATA else "kolom")
        self._diam = True
        for w, k in ((self.c_uji, "uji"), (self.c_grafik, "grafik"), (self.c_galat, "galat"), (self.c_tanda, "tanda"),
                     (self.c_palet, "palet")):
            i = w.findData(d.get(k))
            if i >= 0:
                w.setCurrentIndex(i)
        self.c_ns.setChecked(bool(d.get("ns")))
        self.c_pasang.setChecked(bool(d.get("pasang")))
        self.c_arah.setCurrentIndex(1 if d.get("arah") else 0)
        self.c_kurva.setCurrentIndex(max(0, self.c_kurva.findData(d.get("kurva", "roc"))))
        self.c_koreksi.setCurrentIndex(max(0, self.c_koreksi.findData(d.get("koreksi", "holm"))))
        self.e_y.setText(d.get("label_y", ""))
        self.e_judul.setText(d.get("judul", ""))
        self._diam = False
        self.hitung()

    # ------------------------------------------------------------ hitung
    def hitung(self, *_):
        if self._diam:
            return
        t = theme.TOKEN[self.mode]
        self.kanvas.latar = QColor(t["surf"])
        self.kanvas.aksen = QColor(t["acc2"])
        daerah = []
        s, _ = self.svg(daerah=daerah)
        self.kanvas.daerah = daerah
        self.kanvas.set_svg(s)
        self._info()
        self.format.segarkan()

    def _grup(self):
        nama, kel = [], []
        for i, n in enumerate(self.nama_kolom()):
            v = self._kolom(i)
            if v:
                nama.append(n)
                kel.append(v)
        return nama, kel

    def _tabel_kont(self):
        """(obs, label baris, label kolom) dari lembar; kolom pertama = nama kelompok."""
        nama = self.nama_kolom()
        kol = [i for i in range(1, self.tabel.columnCount()) if self._kolom(i)]
        if not kol:
            return None
        nilai = {i: self._kolom_mentah(i) for i in kol}
        obs, baris = [], []
        for r in range(self.tabel.rowCount()):
            v = [nilai[i][r] for i in kol]
            if all(x is None for x in v):
                continue
            it = self.tabel.item(r, 0)
            baris.append(it.text().strip() if it and it.text().strip() else f"Baris {r + 1}")
            obs.append([x or 0 for x in v])
        return obs, baris, [nama[i] for i in kol]

    def svg(self, gelap=None, transparan=False, daerah=None):
        g = (self.mode == "gelap") if gelap is None else gelap
        judul = self.e_judul.text().strip()
        j = self.jenis()
        if j == "xy":
            xs = self._kolom_mentah(0)
            x, y = [], []
            for i in range(1, self.tabel.columnCount()):
                for xv, yv in zip(xs, self._kolom_mentah(i)):
                    if xv is not None and yv is not None:
                        x.append(xv)
                        y.append(yv)
            if len(x) < 4:
                self.hasil = None
                return "", (0, 0)
            self.hasil = U.dosis_respons(x, y, model=self.c_uji.currentData() or "auto")
            return G.grafik_dosis(self.hasil, self.nama_kolom()[0] if self.nama_kolom() else "Konsentrasi",
                                  self.e_y.text() or "Respons", judul, g, transparan, gaya=self.gaya, daerah=daerah)
        if j == "roc":
            if self.tabel.columnCount() < 2:
                self.hasil = None
                return "", (0, 0)
            neg, pos = self._kolom(0), self._kolom(1)
            if not neg and not pos:
                self.hasil = None
                return "", (0, 0)
            self.hasil = U.roc(neg, pos, bool(self.c_arah.currentData()))
            return G.grafik_roc(self.hasil, judul, g, transparan, gaya=self.gaya, daerah=daerah,
                                mode=self.c_kurva.currentData() or "roc")
        if j == "kontingensi":
            t = self._tabel_kont()
            if not t or len(t[0]) < 1:
                self.hasil = None
                return "", (0, 0)
            obs, baris, kolom = t
            self.hasil = U.kontingensi(obs, baris, kolom)
            if self.hasil.get("galat") and (len(baris) < 2 or len(kolom) < 2):
                return "", (0, 0)
            return G.grafik_kontingensi(self.hasil, self.e_y.text() or "Persentase (%)", judul, g, transparan,
                                        self.c_palet.currentData(), gaya=self.gaya, daerah=daerah)
        if j == "dua_faktor":
            nama = self.nama_kolom()
            ya, fa, fb = [], [], []
            for r in range(self.tabel.rowCount()):
                it = self.tabel.item(r, 0)
                a = it.text().strip() if it and it.text().strip() else None
                for c in range(1, self.tabel.columnCount()):
                    v = self._kolom_mentah(c)[r] if a else None
                    if a and v is not None:
                        ya.append(v)
                        fa.append(a)
                        fb.append(nama[c])
            if len(ya) < 4:
                self.hasil = None
                return "", (0, 0)
            self.hasil = U.anova_dua_arah(ya, fa, fb, self.c_koreksi.currentData() or "sidak")
            if self.hasil.get("galat"):
                return "", (0, 0)
            return G.grafik_dua_faktor(self.hasil, self.c_galat.currentData(), self.c_palet.currentData(),
                                       self.e_y.text(), judul, g, transparan, gaya=self.gaya, daerah=daerah)
        nama, kel = self._grup()
        if not kel:
            self.hasil = None
            return "", (0, 0)
        uji = self.c_uji.currentData() or "otomatis"
        if len(kel) == 2 and uji in ("anova", "welch_anova", "kruskal", "dunnett"):
            uji = {"anova": "student", "welch_anova": "welch", "kruskal": "mann", "dunnett": "student"}[uji]
        if self.c_pasang.isChecked() and len(kel) == 2:
            a, b = self._kolom_mentah(self.nama_kolom().index(nama[0])), self._kolom_mentah(
                self.nama_kolom().index(nama[1]))
            pas = [(p, q) for p, q in zip(a, b) if p is not None and q is not None]
            kel = [[p for p, _ in pas], [q for _, q in pas]]
            uji = {"otomatis": "otomatis", "student": "t_pasang", "welch": "t_pasang", "mann": "wilcoxon"}.get(uji, uji)
        elif self.c_pasang.isChecked() and len(kel) > 2:     # baris lengkap saja (subjek yang sama)
            mentah = [self._kolom_mentah(self.nama_kolom().index(n)) for n in nama]
            baris = [r for r in zip(*mentah) if all(v is not None for v in r)]
            kel = [[r[i] for r in baris] for i in range(len(nama))]
        self.hasil = U.analisis(kel, nama, uji, berpasangan=self.c_pasang.isChecked(),
                                koreksi=self.c_koreksi.currentData() or "holm")
        if self.c_grafik.currentData() == "qq":
            return G.grafik_qq(nama, kel, judul, g, transparan, self.c_palet.currentData(), gaya=self.gaya,
                               daerah=daerah)
        return G.grafik_grup(nama, kel, self.c_grafik.currentData(), self.c_galat.currentData(),
                             self.hasil.get("posthoc"), self.c_tanda.currentData(), self.c_ns.isChecked(),
                             self.c_palet.currentData(), self.e_y.text(), judul, g, transparan, gaya=self.gaya,
                             daerah=daerah)

    def _info(self):
        t = theme.TOKEN[self.mode]
        o = [f"<style>td,th{{padding:2px 7px;}} th{{text-align:left;color:{t['ink2']};font-weight:600;}} "
             f"td.n{{text-align:right;font-family:Consolas,monospace;}} .m{{color:{t['mut']};}} "
             f".w{{color:{t['warn']};}}</style>"]
        h = self.hasil
        F = U.f_angka
        self._teks = ""
        if not h:
            o.append("<p class='m'>Isi lembar data (tempel dari Excel dengan Ctrl+V, impor CSV, atau menu "
                     f"<b>Isi data ▾</b> › Contoh data). {escape(PETUNJUK[self.jenis()])}</p>")
            self.info.setHtml("".join(o))
            return
        if h.get("galat"):
            o.append(f"<p class='w'>{escape(h['galat'])}</p>")
            self.info.setHtml("".join(o))
            return
        j = self.jenis()
        if j == "xy":
            ci = h.get("ic50_ci")
            bd = h.get("banding") or {}
            nama_model = ("4 parameter (kemiringan bebas)" if h.get("model") != "3pl"
                          else "3 parameter (Hill = ±1)")
            o.append(f"<p><b>Regresi nonlinear {nama_model} - log[inhibitor] vs respons</b></p>"
                     "<table>"
                     f"<tr><th>IC₅₀ / EC₅₀</th><td class='n'>{F(h['ic50'], 4)}</td><td>CI 95% "
                     f"{(F(ci[0], 4) + ' - ' + F(ci[1], 4)) if ci else '-'}</td></tr>"
                     f"<tr><th>log IC₅₀</th><td class='n'>{F(h['log_ic50'], 4)}</td></tr>"
                     f"<tr><th>Hill slope</th><td class='n'>{F(h['hill'], 3)}</td></tr>"
                     f"<tr><th>Bawah / Atas</th><td class='n'>{F(h['bawah'], 2)} / {F(h['atas'], 2)}</td></tr>"
                     f"<tr><th>R²</th><td class='n'>{F(h['r2'], 4)}</td><td>n = {h['n']}, df = {h['dof']}</td></tr>"
                     "</table>")
            if bd.get("F") is not None:
                pilih = "4PL" if bd.get("terpilih") == "4pl" else "3PL"
                o.append("<p><b>Perbandingan model</b> <span class='m'>(uji F extra sum-of-squares; AICc)</span></p>"
                         "<table><tr><th></th><th>SS galat</th><th>AICc</th></tr>"
                         f"<tr><td>4PL</td><td class='n'>{F(bd['ss4'], 3)}</td><td class='n'>{F(bd['aicc4'], 2)}</td></tr>"
                         f"<tr><td>3PL (Hill = ±1)</td><td class='n'>{F(bd['ss3'], 3)}</td>"
                         f"<td class='n'>{F(bd['aicc3'], 2)}</td></tr></table>"
                         f"<p class='m'>F({bd['df'][0]}; {bd['df'][1]}) = {F(bd['F'], 2)}, p = {_p_html(bd['p'])}"
                         + (f"; peluang 4PL lebih tepat (AICc) {F(bd['peluang4'] * 100, 0)} %" if bd.get("peluang4")
                            is not None else "") + f". Model dipakai: <b>{pilih}</b>.</p>")
            for w in h.get("peringatan") or []:
                o.append(f"<p class='w'>⚠ {escape(w)}</p>")
            self._teks = (f"IC50 = {F(h['ic50'], 3)}" + (f" (CI 95% {F(ci[0], 3)}-{F(ci[1], 3)})" if ci else "")
                          + f"; Hill = {F(h['hill'], 2)}; R² = {F(h['r2'], 3)}.\nNilai IC50 ditentukan dengan "
                          + ("regresi nonlinear model logistik empat parameter (log[inhibitor] vs respons, kemiringan "
                             "bebas)" if h.get("model") != "3pl" else "regresi nonlinear model logistik tiga parameter "
                             "(log[inhibitor] vs respons, kemiringan standar Hill = 1)")
                          + (" yang dipilih dengan uji F extra sum-of-squares terhadap model tiga parameter (α = 0,05)"
                             if (self.c_uji.currentData() == "auto" and bd.get("F") is not None) else "")
                          + " menggunakan VirmoLab (SciPy).")
            self.info.setHtml("".join(o))
            return
        if j == "roc":
            ci = h.get("ci")
            arah = "≤" if h["rendah_positif"] else "≥"
            cs = h["ci_skrining"]
            o.append("<p><b>Kurva ROC</b></p><table>"
                     f"<tr><th>AUC</th><td class='n'>{F(h['auc'], 4)}</td><td>SE {F(h['se'], 4)} · CI 95% "
                     f"{(F(ci[0], 3) + ' - ' + F(ci[1], 3)) if ci else '-'} (DeLong)</td></tr>"
                     f"<tr><th>p (AUC = 0,5)</th><td class='n'>{_p_html(h['p'])}</td><td>Mann-Whitney</td></tr>"
                     f"<tr><th>Titik potong (Youden)</th><td class='n'>{arah} {F(h['potong'], 3)}</td>"
                     f"<td>sensitivitas {F(h['sens'] * 100, 1)} % · spesifisitas {F(h['spes'] * 100, 1)} %</td></tr>"
                     f"<tr><th>EF1%</th><td class='n'>{F(h['ef'][1], 2)}</td><td>CI 95% "
                     f"{F(cs['ef1'][0], 2)} - {F(cs['ef1'][1], 2)} (bootstrap)</td></tr>"
                     f"<tr><th>EF5% · EF10%</th><td class='n'>{F(h['ef'][5], 2)}</td><td>CI 95% "
                     f"{F(cs['ef5'][0], 2)} - {F(cs['ef5'][1], 2)} · EF10% = {F(h['ef'][10], 2)}</td></tr>"
                     f"<tr><th>BEDROC (α = 20)</th><td class='n'>{F(h['bedroc'], 3)}</td><td>CI 95% "
                     f"{F(cs['bedroc'][0], 3)} - {F(cs['bedroc'][1], 3)} · 1 = semua positif di urutan teratas</td></tr>"
                     f"<tr><th>logAUC</th><td class='n'>{F(h['logauc'], 1)} %</td><td>terkoreksi "
                     f"{F(h['logauc'] - U.LOGAUC_ACAK, 1)} % (acak {F(U.LOGAUC_ACAK, 1)} %)</td></tr>"
                     f"<tr><th>n</th><td class='n'>{h['n1']} / {h['n0']}</td><td>positif / negatif</td></tr></table>"
                     f"<p>{escape(h['interpretasi'])}</p><p class='m'><b>Metode:</b> {escape(h['metode'])}</p>")
            for w in h.get("peringatan") or []:
                o.append(f"<p class='w'>⚠ {escape(w)}</p>")
            self._teks = f"{h['interpretasi']}\n{h['metode']}"
            self.info.setHtml("".join(o))
            return
        if j == "dua_faktor":
            o.append("<p><b>ANOVA dua arah</b> <span class='m'>(jumlah kuadrat tipe III)</span></p><table><tr>"
                     "<th>Sumber</th><th>SS</th><th>df</th><th>MS</th><th>F</th><th>p</th><th>η²ₚ</th><th></th></tr>")
            for b in h["tabel"]:
                if "F" in b:
                    o.append(f"<tr><td>{escape(b['efek'])}</td><td class='n'>{F(b['ss'])}</td><td class='n'>{b['df']}"
                             f"</td><td class='n'>{F(b['ms'])}</td><td class='n'>{F(b['F'], 2)}</td><td class='n'>"
                             f"{_p_html(b['p'])}</td><td class='n'>{F(b['eta_p'], 3)}</td><td>{U.bintang(b['p'])}</td></tr>")
                else:
                    o.append(f"<tr><td>Galat</td><td class='n'>{F(b['ss'])}</td><td class='n'>{b['df']}</td>"
                             f"<td class='n'>{F(b['ms'])}</td></tr>")
            o.append("</table>")
            o.append(f"<p><b>Perbandingan faktor A di tiap level B</b> <span class='m'>(koreksi "
                     f"{U.KOREKSI[h['koreksi']]})</span></p><table><tr><th>Level B</th><th>Pasangan</th><th>Selisih</th>"
                     "<th>CI 95%</th><th>p terkoreksi</th><th></th></tr>")
            for b, a1, a2, dif, ci, q in h["posthoc"]:
                o.append(f"<tr><td>{escape(b)}</td><td nowrap>{escape(a1)} vs {escape(a2)}</td><td class='n'>{F(dif)}</td>"
                         f"<td class='n' nowrap>{F(ci[0])} - {F(ci[1])}</td><td class='n'>{_p_html(q)}</td>"
                         f"<td>{U.bintang(q)}</td></tr>")
            o.append(f"</table><p>{escape(h['interpretasi'])}</p><p class='m'><b>Metode:</b> {escape(h['metode'])}</p>")
            for w in h.get("peringatan") or []:
                o.append(f"<p class='w'>⚠ {escape(w)}</p>")
            self._teks = f"{h['interpretasi']}\n{h['metode']}"
            self.info.setHtml("".join(o))
            return
        if j == "kontingensi":
            obs = np.asarray(h["obs"], float)
            harap = np.asarray(h["harap"])
            o.append("<p><b>Tabel kontingensi</b> <span class='m'>(frekuensi · % baris · harapan)</span></p>"
                     "<table><tr><th></th>" + "".join(f"<th>{escape(k)}</th>" for k in h["kolom"])
                     + "<th>Total</th></tr>")
            for i, b in enumerate(h["baris"]):
                tot = obs[i].sum()
                o.append(f"<tr><th>{escape(b)}</th>" + "".join(
                    f"<td class='n' nowrap>{int(obs[i, j_])} · {F(obs[i, j_] / tot * 100, 1)} % · "
                    f"<span class='m'>{F(harap[i, j_], 1)}</span></td>" for j_ in range(obs.shape[1]))
                    + f"<td class='n'>{int(tot)}</td></tr>")
            o.append("</table>")
            o.append(f"<p><b>{escape(h['nama_uji'])}</b></p><table>"
                     f"<tr><th>χ² Pearson</th><td class='n'>{F(h['chi2'])}</td><td>df = {h['dof']}, "
                     f"p = {_p_html(h['p_chi'])}</td></tr>")
            if "p_yates" in h:
                o.append(f"<tr><th>χ² Yates</th><td class='n'>{F(h['chi2_yates'])}</td><td>p = {_p_html(h['p_yates'])}"
                         "</td></tr>"
                         f"<tr><th>Fisher eksak</th><td class='n'>{_p_html(h['p'])}</td><td>dua sisi</td></tr>"
                         f"<tr><th>Rasio odds</th><td class='n'>{F(h['OR'], 3)}</td><td>CI 95% "
                         f"{F(h['OR_ci'][0], 3)} - {F(h['OR_ci'][1], 3)}</td></tr>"
                         f"<tr><th>Risiko relatif</th><td class='n'>{F(h['RR'], 3)}</td><td>CI 95% "
                         f"{F(h['RR_ci'][0], 3)} - {F(h['RR_ci'][1], 3)}</td></tr>")
            elif "p_fisher" in h:
                o.append(f"<tr><th>Fisher eksak (r × c)</th><td class='n'>{_p_html(h['p_fisher'])}</td></tr>")
            o.append(f"<tr><th>Cramér V</th><td class='n'>{F(h['cramer'], 3)}</td><td>n = {h['n']}</td></tr></table>"
                     f"<p>{escape(h['interpretasi'])}</p><p class='m'><b>Metode:</b> {escape(h['metode'])}</p>")
            for w in h.get("peringatan") or []:
                o.append(f"<p class='w'>⚠ {escape(w)}</p>")
            self._teks = f"{h['interpretasi']}\n{h['metode']}"
            self.info.setHtml("".join(o))
            return
        nama = h["nama"]
        o.append("<p><b>Statistik deskriptif</b></p><table><tr><th>Grup</th><th>n</th><th>Rerata</th><th>SD</th>"
                 "<th>SEM</th><th>Median</th><th>Min - Maks</th><th>Shapiro-Wilk p</th><th>D'Agostino p</th></tr>")
        dag = h.get("dagostino") or [None] * len(nama)
        for n, d, (_w, p), pd in zip(nama, h["deskriptif"], h["normalitas"], dag):
            o.append(f"<tr><td>{escape(n)}</td><td class='n'>{d['n']}</td><td class='n'>{F(d['rerata'])}</td>"
                     f"<td class='n'>{F(d['sd'])}</td><td class='n'>{F(d['sem'])}</td><td class='n'>{F(d['median'])}</td>"
                     f"<td class='n' nowrap>{F(d['min'])} - {F(d['maks'])}</td><td class='n'>{_p_html(p)}</td>"
                     f"<td class='n'>{_p_html(pd) if pd is not None else '<span class=m>n &lt; 8</span>'}</td></tr>")
        o.append("</table>")
        if h.get("varians"):
            o.append(f"<p class='m'>Brown-Forsythe (homogenitas varians): F = {F(h['varians'][0])}, "
                     f"p = {_p_html(h['varians'][1])}</p>")
        if "p" in h:
            o.append(f"<p><b>{escape(h['nama_uji'])}</b></p><p>{escape(h['interpretasi'])}</p>")
            if h.get("ci"):
                o.append(f"<p class='m'>Selisih = {F(h['selisih'])} (CI 95% {F(h['ci'][0])} - {F(h['ci'][1])})</p>")
            if h.get("posthoc") and len(nama) > 2:
                o.append(f"<p><b>{escape(h.get('nama_posthoc', 'Uji lanjut'))}</b></p><table><tr><th>Pasangan</th>"
                         "<th>Selisih</th><th>CI 95%</th><th>p terkoreksi</th><th></th></tr>")
                for i, j_, dif, ci, p in h["posthoc"]:
                    o.append(f"<tr><td nowrap>{escape(nama[i])} vs {escape(nama[j_])}</td><td class='n'>{F(dif)}</td>"
                             f"<td class='n' nowrap>{(F(ci[0]) + ' - ' + F(ci[1])) if ci else '-'}</td>"
                             f"<td class='n'>{_p_html(p)}</td><td>{U.bintang(p)}</td></tr>")
                o.append("</table>")
            o.append(f"<p class='m'><b>Metode:</b> {escape(h['metode'])}</p>")
        for w in h.get("peringatan") or []:
            o.append(f"<p class='w'>⚠ {escape(w)}</p>")
        self._teks = f"{h.get('interpretasi', '')}\n{h.get('metode', '')}"
        self.info.setHtml("".join(o))

    def salin_teks(self):
        QGuiApplication.clipboard().setText(self._teks or self.info.toPlainText())

    def set_mode(self, mode):
        self.mode = mode
        self.hitung()
