"""Cetak struktur menu, pintasan, tab, dock, dan judul panel langkah (untuk menulis dokumentasi)."""
import sys

from PySide6.QtCore import QTimer

sys.argv = [sys.argv[0]]
import virmolab.app as A  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget, QWidgetAction  # noqa: E402


def cetak_menu(m, ind=0):
    for a in m.actions():
        if a.isSeparator():
            continue
        if isinstance(a, QWidgetAction):
            w = a.defaultWidget()
            print("  " * ind + f"== {w.text() if hasattr(w, 'text') else ''}")
            continue
        t = a.text().replace("&", "")
        k = a.shortcut().toString()
        print("  " * ind + f"- {t}" + (f"  [{k}]" if k else ""))
        if a.menu():
            cetak_menu(a.menu(), ind + 1)


def hook():
    from virmolab.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            QTimer.singleShot(2500, s.d)

        def d(s):
            for a in s.menuBar().actions():
                print("#", a.text().replace("&", ""))
                cetak_menu(a.menu(), 1)
            print("# DOCK", [d.windowTitle() for d in s.findChildren(QDockWidget)])
            print("# TAB", [s.tab_tengah.tabText(i) for i in range(s.tab_tengah.count())])
            print("# TOOLBAR", [a.text() or a.toolTip() for a in s.tb.actions() if not a.isSeparator()])
            QApplication.quit()

    mainwindow.JendelaUtama = U
    A.main()


hook()
