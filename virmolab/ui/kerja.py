"""Pekerja latar belakang supaya UI tidak pernah freeze."""
import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class SinyalKerja(QObject):
    selesai = Signal(object)
    galat = Signal(str)
    log = Signal(str)
    progres = Signal(int, int, str)


class Kerja(QRunnable):
    """Jalankan fn(*arg, lapor=SinyalKerja) di thread pool."""

    def __init__(self, fn, *arg, **kw):
        super().__init__()
        self.fn, self.arg, self.kw = fn, arg, kw
        self.s = SinyalKerja()
        self.setAutoDelete(False)

    def run(self):
        try:
            hasil = self.fn(*self.arg, lapor=self.s, **self.kw)
            self.s.selesai.emit(hasil)
        except Exception as e:  # galat ditampilkan rapi di panel Pesan
            try:
                self.s.galat.emit(f"{e}\n\n{traceback.format_exc(limit=4)}")
            except RuntimeError:  # objek sinyal sudah dihapus (jendela ditutup saat pekerja masih jalan)
                pass


_aktif = set()


def jalankan(fn, *arg, selesai=None, galat=None, log=None, progres=None, **kw):
    k = Kerja(fn, *arg, **kw)
    _aktif.add(k)  # jaga referensi Python sampai pekerjaan selesai
    k.s.selesai.connect(lambda *_: _aktif.discard(k))
    k.s.galat.connect(lambda *_: _aktif.discard(k))
    if selesai:
        k.s.selesai.connect(selesai)
    if galat:
        k.s.galat.connect(galat)
    if log:
        k.s.log.connect(log)
    if progres:
        k.s.progres.connect(progres)
    QThreadPool.globalInstance().start(k)
    return k
