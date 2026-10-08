"""Viewport 3D: QWebEngineView berisi 3Dmol.js, dihubungkan lewat QWebChannel."""
import json

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from ..core import paths


class Jembatan(QObject):
    siapSignal = Signal()
    dipilihSignal = Signal(dict)
    ukurSignal = Signal(dict)
    kotakSignal = Signal(dict)

    @Slot()
    def siap(self):
        self.siapSignal.emit()

    @Slot(str)
    def dipilih(self, s):
        self.dipilihSignal.emit(json.loads(s))

    @Slot(str)
    def ukur(self, s):
        self.ukurSignal.emit(json.loads(s))

    @Slot(str)
    def kotak(self, s):
        self.kotakSignal.emit(json.loads(s))


class Halaman(QWebEnginePage):
    pesan = Signal(str)

    def javaScriptConsoleMessage(self, level, teks, baris, sumber):
        self.pesan.emit(f"[viewer] {teks} (baris {baris})")


class Viewer(QWebEngineView):
    atomDipilih = Signal(dict)
    jarakDiukur = Signal(dict)
    kotakDigeser = Signal(dict)
    pesanJs = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._siap = False
        self._antre = []
        self.setPage(Halaman(self))
        self.page().pesan.connect(self.pesanJs)
        s = self.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        self.page().setBackgroundColor("#ffffff")
        self.jembatan = Jembatan()
        self.kanal = QWebChannel(self)
        self.kanal.registerObject("py", self.jembatan)
        self.page().setWebChannel(self.kanal)
        self.jembatan.siapSignal.connect(self._saat_siap)
        self.jembatan.dipilihSignal.connect(self.atomDipilih)
        self.jembatan.ukurSignal.connect(self.jarakDiukur)
        self.jembatan.kotakSignal.connect(self.kotakDigeser)
        self.setContextMenuPolicy(self.contextMenuPolicy().NoContextMenu)
        self.load(QUrl.fromLocalFile(str(paths.VIEWER / "viewer.html")))

    def _saat_siap(self):
        self._siap = True
        for js, cb in self._antre:
            self._jalankan(js, cb)
        self._antre = []

    def _jalankan(self, js, cb=None):
        if cb:
            self.page().runJavaScript(js, 0, cb)
        else:
            self.page().runJavaScript(js)

    def js(self, fungsi, *arg, cb=None):
        kode = f"VM.{fungsi}(" + ",".join(json.dumps(a) for a in arg) + ")"
        if self._siap:
            self._jalankan(kode, cb)
        else:
            self._antre.append((kode, cb))

    # pembungkus praktis
    def muat(self, o, cb=None):
        self.js("load", o.id, o.teks, o.fmt, cb=cb)

    def tampil(self, o, spek):
        self.js("tampil", o.id, spek)

    def hapus(self, oid):
        self.js("remove", oid)
