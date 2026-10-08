import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog
import virmodock.app as A
from virmodock.core import paths
st = paths.settings(); st.setValue("wizard_selesai", True)
def hook():
    from virmodock.ui import mainwindow
    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            QTimer.singleShot(2500, s.a)
        def a(s):
            for mode in ("terang", "gelap"):
                s.terapkan_tema(mode)
                QDialog.exec = lambda d, mode=mode: (d.show(), QApplication.processEvents(), d.grab().save(f"dev/logo_tentang_{mode}.png"), d.close())
                s.tentang()
            from virmodock.ui.dialogs import Wizard
            s.terapkan_tema("terang")
            w = Wizard(s.env, "C:/x", s); w.show(); QApplication.processEvents()
            QTimer.singleShot(500, lambda: (w.grab().save("dev/logo_wizard.png"), QApplication.quit()))
    mainwindow.JendelaUtama = U
    A.main()
hook()
