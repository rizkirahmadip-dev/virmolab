"""Uji visual: buka VirmoLab, muat struktur, simpan tangkapan layar, keluar."""
import sys, os
from PySide6.QtCore import QTimer, QSettings
sys.argv = [sys.argv[0]]
out = os.environ.get("VD_SHOT", "dev/uji/gambar/shot.png")
tema = os.environ.get("VD_TEMA", "terang")
pdb = os.environ.get("VD_PDB", "1HSG")
QSettings("VirmoLab", "VirmoLab").setValue("wizard_selesai", True)
QSettings("VirmoLab", "VirmoLab").setValue("tema", tema)
import virmolab.app as A
from PySide6.QtWidgets import QApplication
from pathlib import Path
Path("dev/uji/gambar").mkdir(parents=True, exist_ok=True)  # keluaran gambar uji
orig = A.main
def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama
    class Uji(Asli):
        def __init__(s):
            super().__init__()
            u = os.environ.get("VD_UKURAN", "1600x960").split("x"); s.resize(int(u[0]), int(u[1])); s.move(10, 10)
            QTimer.singleShot(1500, lambda: s._muat())
            QTimer.singleShot(int(os.environ.get("VD_WAIT", "14000")), lambda: s._foto())
        def _muat(s):
            from virmolab.core import molekul
            from virmolab.ui import kerja
            kerja.jalankan(lambda lapor: molekul.unduh_rcsb(pdb)[0], selesai=s.tambah_objek, galat=s._galat)
        def _foto(s):
            pm = s.grab()  # render isi jendela VirmoLab saja, bukan layar
            pm.save(out); print("saved", out); print(s.log.toPlainText()[-3000:]); QApplication.quit()
    mainwindow.JendelaUtama = Uji
    orig()
hook()
