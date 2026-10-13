import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog
import virmolab.app as A
from virmolab.core import paths
from pathlib import Path
Path("dev/uji/gambar").mkdir(parents=True, exist_ok=True)  # keluaran gambar uji
st = paths.settings(); st.setValue("wizard_selesai", True)
def hook():
    from virmolab.ui import mainwindow
    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            QTimer.singleShot(2500, s.a)
        def a(s):
            for mode in ("terang", "gelap"):
                s.terapkan_tema(mode)
                QDialog.exec = lambda d, mode=mode: (d.show(), QApplication.processEvents(), d.grab().save(f"dev/uji/gambar/logo_tentang_{mode}.png"), d.close())
                s.tentang()
            from virmolab.ui.dialogs import Wizard
            s.terapkan_tema("terang")
            w = Wizard(s.env, "C:/x", s); w.show(); QApplication.processEvents()
            QTimer.singleShot(500, lambda: (w.grab().save("dev/uji/gambar/logo_wizard.png"), QApplication.quit()))
    mainwindow.JendelaUtama = U
    A.main()
hook()
