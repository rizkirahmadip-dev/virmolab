"""Antarmuka multibahasa (Indonesia bawaan, English) tanpa menulis ulang kode UI.

Teks UI ditulis dalam Bahasa Indonesia di kode. Bila bahasa = 'en', `pasang()` (dipanggil sebelum modul UI
diimpor) memasang lapisan terjemahan saat runtime:
  1. setter Qt yang membawa teks (setText, setToolTip, addItem, addTab, showMessage, QMessageBox.*, …) dibungkus;
  2. widget yang dibuat dengan teks di konstruktor diterjemahkan saat event Polish (sekali, sebelum tampil);
  3. kelas item (QTableWidgetItem, QListWidgetItem, QTreeWidgetItem) diganti subkelas yang menerjemahkan teks awal;
  4. data tampilan di modul core (nama jenis interaksi, label variabel, dll.) dan teks grafik SVG diterjemahkan.
Kamus: i18n/en.json {"teks": {id: en}, "pola": {pola dengan {0}… : en}} - dibuat/dilengkapi lewat
dev/ekstrak_teks.py. Teks yang tidak ada di kamus tampil apa adanya (Bahasa Indonesia).
Ganti bahasa: Tampilan › Bahasa (berlaku setelah aplikasi dibuka ulang).
"""
import json
import re
from pathlib import Path

BAHASA = "id"
_teks, _pola, _cache = {}, [], {}
_frasa = None


def bahasa_tersimpan():
    try:
        from ..core import paths
        return str(paths.settings().value("bahasa", "id") or "id")
    except Exception:
        return "id"


def _muat(kode):
    global _teks, _pola
    f = Path(__file__).with_name(f"{kode}.json")
    d = json.loads(f.read_text(encoding="utf-8"))
    _teks = d.get("teks", {})
    _pola = []
    for pola, hasil in d.get("pola", {}).items():
        bag = re.split(r"(\{\d+\})", pola.replace("{{", "\x00").replace("}}", "\x01"))
        rx, urut = "", []
        for b in bag:
            m = re.fullmatch(r"\{(\d+)\}", b)
            if m:
                rx += "(.*?)"
                urut.append(int(m.group(1)))
            else:
                rx += re.escape(b.replace("\x00", "{").replace("\x01", "}"))
        if not urut or len(re.sub(r"\(\.\*\?\)", "", rx)) < 4:
            continue
        _pola.append((re.compile("^" + rx + "$", re.S), urut, hasil))
    # Pola paling spesifik (bagian tetap terpanjang) dicoba lebih dulu. Tanpa ini pola umum seperti
    # '{0} ligan' menelan '4 atom berat ligan' sebelum pola '{0} atom berat ligan' sempat dicoba.
    _pola.sort(key=lambda p: -len(re.sub(r"\(\.\*\?\)", "", p[0].pattern)))


def t(s):
    """Terjemahkan teks UI (no-op bila bahasa Indonesia atau bukan str)."""
    if BAHASA == "id" or not isinstance(s, str) or not s or len(s) > 6000:
        return s
    h = _cache.get(s)
    if h is not None:
        return h
    h = _terjemah(s)
    if len(_cache) < 50000:
        _cache[s] = h
    return h


def inggris():
    """True bila antarmuka berbahasa Inggris. Dipakai modul core untuk teks yang tidak lewat setter Qt,
    misalnya paragraf metode yang langsung disalin ke papan klip."""
    return BAHASA == "en"


def t_baris(teks):
    """Terjemahkan teks polos berbaris (ringkasan hasil di QPlainTextEdit) baris per baris.

    setPlainText sengaja tidak dibungkus otomatis karena kotak teks yang sama juga memuat skrip dan kode
    yang tidak boleh berubah; pemanggil memakai fungsi ini hanya untuk teks UI buatannya sendiri."""
    if BAHASA == "id" or not teks:
        return teks
    return "\n".join(t(b) if b.strip() else b for b in teks.split("\n"))


def _terjemah(s):
    if s in _teks:
        return _teks[s]
    inti = s.strip()
    if inti != s and inti in _teks:            # spasi tepi dipertahankan
        a = s[:len(s) - len(s.lstrip())]
        b = s[len(s.rstrip()):]
        return a + _teks[inti] + b
    for akhir in ("…", ":", " ›", "…:"):
        if inti.endswith(akhir) and inti[:-len(akhir)] in _teks:
            return _teks[inti[:-len(akhir)]] + akhir
    polos = s.replace("&&", "\x00").replace("&", "").replace("\x00", "&") if "&" in s else None
    if polos and polos != s and polos in _teks:     # akselerator menu: '&' di huruf pertama terjemahan
        return s if _teks[polos] == polos else "&" + _teks[polos].replace("&", "&&")
    for rx, urut, hasil in _pola:
        m = rx.match(s)
        if m:
            nilai = {u: t(_titik_desimal(g)) for u, g in zip(urut, m.groups())}
            try:
                return hasil.format(*[nilai.get(i, "") for i in range(max(urut) + 1)])
            except (IndexError, KeyError):
                return s
    if "<" in s and ">" in s:                  # teks kaya: terjemahkan tiap potongan teks di antara tag
        bag = re.split(r"(<[^>]+>)", s)
        hasil = "".join(b if b.startswith("<") or not re.search(r"[A-Za-z]{2}", b) else t(b) for b in bag)
        return hasil if hasil != s else _ganti_frasa(s)
    if "\n" in s:                              # teks berbaris: per baris
        return "\n".join(t(b) for b in s.split("\n"))
    m = re.match(r"^(\s*[✓•⚠●▸›]\s*)(.+)$", s, re.S)    # simbol di depan
    if m:
        h = t(m.group(2))
        return m.group(1) + h if h != m.group(2) else s
    if ": " in inti:                           # 'Label: nilai'
        kiri, kanan = s.split(": ", 1)
        tk = _teks.get(kiri + ": ") or _teks.get(kiri)
        if tk:
            return tk.rstrip() + " " + t(kanan) if tk.endswith(": ") else tk + ": " + t(kanan)
    # Paragraf yang dirakit dari beberapa kalimat (paragraf metode, catatan dialog): terjemahkan per kalimat,
    # tetapi hanya bila SEMUA kalimat dikenal. Paragraf setengah Inggris setengah Indonesia lebih buruk
    # daripada paragraf Indonesia utuh.
    kalimat = re.split(r"(?<=[.!?])\s+(?=[A-ZΔ(0-9])", inti)
    if len(kalimat) > 1:
        hasil = [t(k) for k in kalimat]
        if all(h != k or not re.search(r"[a-z]{3}", k) for h, k in zip(hasil, kalimat)):
            return s[:len(s) - len(s.lstrip())] + " ".join(hasil) + s[len(s.rstrip()):]
    return s


_DESIMAL = re.compile(r"(?<=\d),(?=\d)")


def _titik_desimal(g):
    """Angka berkoma desimal ala Indonesia (1,34) ditulis bertitik di teks Inggris. Daftar yang dipisah
    koma-spasi ('A, B') tidak disentuh, dan teks Indonesia tidak pernah melewati fungsi ini."""
    if not g or ", " in g or not _DESIMAL.search(g):
        return g
    return _DESIMAL.sub(".", g)


def _ganti_frasa(s):
    global _frasa
    if _frasa is None:
        kunci = sorted((k for k in _teks if len(k) >= 8 and not k.startswith("<") and "\n" not in k),
                       key=len, reverse=True)
        _frasa = re.compile("|".join(re.escape(k) for k in kunci)) if kunci else None
    if _frasa is None:
        return s
    return _frasa.sub(lambda m: _teks.get(m.group(0), m.group(0)), s)


# ------------------------------------------------------------------ pemasangan pada Qt
def _bungkus(kelas, nama, posisi=(0,)):
    asli = getattr(kelas, nama, None)
    if asli is None or getattr(asli, "_vm_i18n", False):
        return

    def f(self, *a, **k):
        a = list(a)
        for i in posisi:
            if i < len(a) and isinstance(a[i], str):
                a[i] = t(a[i])
        return asli(self, *a, **k)
    f._vm_i18n = True
    setattr(kelas, nama, f)


def _bungkus_str_mana_pun(kelas, nama):
    """Untuk overload seperti addAction(teks) / addAction(ikon, teks) / addTab(w, teks): terjemahkan semua str."""
    asli = getattr(kelas, nama, None)
    if asli is None or getattr(asli, "_vm_i18n", False):
        return

    def f(self, *a, **k):
        return asli(self, *[t(x) if isinstance(x, str) else x for x in a], **k)
    f._vm_i18n = True
    setattr(kelas, nama, f)


def _bungkus_statis(kelas, nama, posisi):
    asli = getattr(kelas, nama, None)
    if asli is None or getattr(asli, "_vm_i18n", False):
        return

    def f(*a, **k):
        a = list(a)
        for i in posisi:
            if i < len(a) and isinstance(a[i], str):
                a[i] = t(a[i])
        for kk in ("caption", "filter", "title", "label", "text"):
            if isinstance(k.get(kk), str):
                k[kk] = t(k[kk])
        return asli(*a, **k)
    f._vm_i18n = True
    setattr(kelas, nama, staticmethod(f))


def _polish(w):
    from PySide6 import QtWidgets as W
    try:
        for get, set_ in (("windowTitle", "setWindowTitle"), ("toolTip", "setToolTip"), ("statusTip", "setStatusTip")):
            v = getattr(w, get)()
            if v:
                tv = t(v)
                if tv != v:
                    getattr(w, set_)(tv)
        # QToolButton milik QAction: JANGAN sentuh defaultAction() di sini - Polish bisa terjadi di dalam
        # QToolBar.addAction sebelum PySide mendaftarkan pembungkus aksi; pembungkus sementara yang dibuat
        # di sini lalu dibuang ikut menghapus QAction C++ ("already deleted"). Aksi diterjemahkan lewat setter.
        if isinstance(w, W.QToolButton):
            return
        if isinstance(w, (W.QLabel, W.QAbstractButton)) and w.text():
            w.setText(w.text())
        if isinstance(w, W.QGroupBox) and w.title():
            w.setTitle(w.title())
        if isinstance(w, W.QLineEdit) and w.placeholderText():
            w.setPlaceholderText(w.placeholderText())
        if isinstance(w, W.QAbstractSpinBox):
            for g in ("prefix", "suffix", "specialValueText"):
                if hasattr(w, g) and getattr(w, g)():
                    getattr(w, "set" + g[0].upper() + g[1:])(t(getattr(w, g)()))
        if isinstance(w, W.QComboBox):
            for i in range(w.count()):
                v = w.itemText(i)
                if t(v) != v:
                    w.setItemText(i, t(v))
        if isinstance(w, W.QTabBar):
            for i in range(w.count()):
                v = w.tabText(i)
                if t(v) != v:
                    w.setTabText(i, t(v))
                tt = w.tabToolTip(i)
                if tt and t(tt) != tt:
                    w.setTabToolTip(i, t(tt))
        if isinstance(w, W.QMenu):
            if w.title():
                w.setTitle(w.title())
            for a in w.actions():
                _aksi(a)
    except RuntimeError:
        pass


def _aksi(a):
    for get, set_ in (("text", "setText"), ("toolTip", "setToolTip"), ("statusTip", "setStatusTip"),
                      ("iconText", "setIconText")):
        v = getattr(a, get)()
        if v:
            tv = t(v)
            if tv != v:
                getattr(a, set_)(tv)
    m = a.menu()
    if m is not None and m.title():
        m.setTitle(t(m.title()))


def pasang(app):
    """Pasang lapisan terjemahan (panggil setelah QApplication dibuat, sebelum mengimpor modul UI)."""
    global BAHASA
    kode = bahasa_tersimpan()
    if kode == "id":
        BAHASA = "id"
        return
    try:
        _muat(kode)
    except Exception:
        BAHASA = "id"
        return
    BAHASA = kode
    from PySide6 import QtCore, QtGui, QtWidgets as W
    # Kotak angka (QDoubleSpinBox) mengikuti locale Windows; di Windows berbahasa Indonesia desimalnya koma
    # walaupun antarmuka berbahasa Inggris. Teks Inggris memakai titik, jadi kotak angka juga.
    QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))

    # 1. setter
    for kelas, daftar in ((W.QWidget, ("setWindowTitle", "setToolTip", "setStatusTip", "setWhatsThis")),
                          (W.QLabel, ("setText",)), (W.QAbstractButton, ("setText",)),
                          (W.QGroupBox, ("setTitle",)), (W.QLineEdit, ("setPlaceholderText",)),
                          (W.QMenu, ("setTitle",)), (W.QTextEdit, ("setHtml", "setPlaceholderText")),
                          (W.QPlainTextEdit, ("setPlaceholderText",)),
                          (W.QSpinBox, ("setPrefix", "setSuffix", "setSpecialValueText")),
                          (W.QDoubleSpinBox, ("setPrefix", "setSuffix", "setSpecialValueText")),
                          (W.QStatusBar, ("showMessage",)), (W.QProgressBar, ("setFormat",)),
                          (QtGui.QAction, ("setText", "setToolTip", "setStatusTip", "setIconText")),
                          (W.QTableWidgetItem, ("setText", "setToolTip")),
                          (W.QListWidgetItem, ("setText", "setToolTip")),
                          (W.QDockWidget, ("setWindowTitle",))):
        for n in daftar:
            _bungkus(kelas, n)
    _bungkus(W.QComboBox, "setItemText", (1,))
    _bungkus(W.QTabWidget, "setTabText", (1,))
    _bungkus(W.QTabWidget, "setTabToolTip", (1,))
    _bungkus(W.QTabBar, "setTabText", (1,))
    _bungkus(W.QTreeWidgetItem, "setText", (1,))
    _bungkus(W.QTreeWidgetItem, "setToolTip", (1,))
    _bungkus(QtGui.QStandardItem, "setText")
    _bungkus(W.QSystemTrayIcon, "showMessage", (0, 1))
    for kelas, nama in ((W.QMenu, "addAction"), (W.QMenu, "addMenu"), (W.QMenu, "addSection"),
                        (W.QMenuBar, "addMenu"), (W.QMenuBar, "addAction"), (W.QToolBar, "addAction"),
                        (W.QComboBox, "addItem"), (W.QComboBox, "insertItem"), (W.QTabWidget, "addTab"),
                        (W.QTabWidget, "insertTab"), (W.QTabBar, "addTab"), (W.QToolBox, "addItem"),
                        (W.QStackedWidget, "addWidget"), (W.QDialogButtonBox, "addButton"),
                        (W.QMessageBox, "setText"), (W.QMessageBox, "setInformativeText"),
                        (W.QMessageBox, "setWindowTitle"), (W.QMessageBox, "addButton"),
                        (W.QListWidget, "addItem"), (W.QFormLayout, "addRow"), (W.QFormLayout, "insertRow")):
        _bungkus_str_mana_pun(kelas, nama)

    def daftar_teks(asli):
        def f(self, daftar, *a):
            return asli(self, [t(x) if isinstance(x, str) else x for x in daftar], *a)
        f._vm_i18n = True
        return f
    for kelas, n in ((W.QComboBox, "addItems"), (W.QTableWidget, "setHorizontalHeaderLabels"),
                     (W.QTableWidget, "setVerticalHeaderLabels"), (W.QTreeWidget, "setHeaderLabels"),
                     (W.QListWidget, "addItems"), (QtGui.QStandardItemModel, "setHorizontalHeaderLabels")):
        setattr(kelas, n, daftar_teks(getattr(kelas, n)))
    # dialog statis
    for n in ("information", "warning", "critical", "question", "about"):
        _bungkus_statis(W.QMessageBox, n, (1, 2))
    for n in ("getSaveFileName", "getOpenFileName", "getOpenFileNames", "getExistingDirectory"):
        _bungkus_statis(W.QFileDialog, n, (1, 3))
    for n in ("getText", "getItem", "getInt", "getDouble", "getMultiLineText"):
        _bungkus_statis(W.QInputDialog, n, (1, 2))
    _bungkus_statis(W.QToolTip, "showText", (1,))

    # 2. item dengan teks di konstruktor
    def item(kelas, posisi_teks):
        class Item(kelas):
            def __init__(self, *a, **k):
                a = list(a)
                for i in posisi_teks:
                    if i < len(a) and isinstance(a[i], str):
                        a[i] = t(a[i])
                    elif i < len(a) and isinstance(a[i], list):
                        a[i] = [t(x) if isinstance(x, str) else x for x in a[i]]
                super().__init__(*a, **k)
        Item.__name__ = kelas.__name__
        Item.__qualname__ = kelas.__qualname__
        return Item
    W.QTableWidgetItem = item(W.QTableWidgetItem, (0, 1))
    QtGui.QAction = item(QtGui.QAction, (0, 1))          # QAction(teks, induk) / QAction(ikon, teks, induk)
    W.QListWidgetItem = item(W.QListWidgetItem, (0, 1))
    W.QTreeWidgetItem = item(W.QTreeWidgetItem, (0, 1))

    # 3. Polish: widget yang dibuat dengan teks di konstruktor
    class Penyaring(QtCore.QObject):
        def eventFilter(self, obj, ev):
            if ev.type() == QtCore.QEvent.Polish and isinstance(obj, W.QWidget):
                _polish(obj)
            elif ev.type() == QtCore.QEvent.Show and isinstance(obj, W.QMenu):
                _polish(obj)          # menu yang diisi ulang tiap aboutToShow
            return False
    app._vm_i18n = Penyaring(app)
    app.installEventFilter(app._vm_i18n)

    # 4. data tampilan di modul core & teks grafik SVG
    _terjemahkan_core()


def _terjemahkan_core():
    from ..core import analisis, grafik, kemiripan, statistik
    for d in (analisis.NAMA_JENIS, kemiripan.NAMA_SIDIK):
        for k in d:
            d[k] = t(d[k])
    kemiripan.SIDIK[:] = [(k, t(v)) for k, v in kemiripan.SIDIK]
    for k, (n, w, r) in list(kemiripan.FITUR.items()):
        kemiripan.FITUR[k] = (t(n), w, r)
    statistik.VARIABEL[:] = [(k, t(a), t(b), d) for k, a, b, d in statistik.VARIABEL]
    statistik.LABEL.update({k: a for k, a, _b, _d in statistik.VARIABEL})
    statistik.PENDEK.update({k: b for k, _a, b, _d in statistik.VARIABEL})
    try:
        from ..core import admet, protonasi, pustaka
        admet.SIFAT[:] = [(k, t(l), t(g), j, a) for k, l, g, j, a in admet.SIFAT]
        admet.LABEL.update({k: l for k, l, *_ in admet.SIFAT})
        admet.KELOMPOK[:] = [t(x) for x in admet.KELOMPOK]
        for k in protonasi.NAMA_KEADAAN:
            protonasi.NAMA_KEADAAN[k] = t(protonasi.NAMA_KEADAAN[k])
        for k in pustaka.ATC:
            pustaka.ATC[k] = t(pustaka.ATC[k])
    except Exception:
        pass
    asli = grafik.Kanvas.teks

    def teks(self, x, y, s, *a, **k):
        return asli(self, x, y, t(s) if isinstance(s, str) else s, *a, **k)
    grafik.Kanvas.teks = teks
