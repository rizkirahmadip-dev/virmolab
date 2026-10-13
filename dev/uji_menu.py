"""Uji menu atas: semua menu dibuka & digambar (widget menu saja), pintasan ganda, aksi tanpa keterangan.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_menu.py   -> dev/uji/menu/*.png
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("tema", "terang")
st.setValue("wizard_selesai", True)
for k in ("layout", "layout_v2", "sesi_terbuka"):
    st.remove(k)
OUT = Path("dev/uji/menu").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True, exist_ok=True)

import virmolab.app as A
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1700, 1000)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(60000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            kunci = {}
            for a in s.findChildren(QAction):
                k = a.shortcut().toString(QKeySequence.PortableText)
                if k:
                    kunci.setdefault(k, set()).add(a.text().replace("&", ""))
            ganda = {k: v for k, v in kunci.items() if len(v) > 1}
            print("jumlah pintasan:", len(kunci), "| GANDA:", ganda or "tidak ada", flush=True)
            s.menus = [a.menu() for a in s.menuBar().actions() if a.menu()]
            print("menu:", [m.title().replace("&", "") for m in s.menus], flush=True)
            s.i = 0
            QTimer.singleShot(200, s.buka)

        def buka(s):
            if s.i >= len(s.menus):
                QApplication.quit()
                return
            m = s.menus[s.i]
            m.aboutToShow.emit()
            n = sum(1 for a in m.actions() if not a.isSeparator())
            tanpa = [a.text() for a in m.actions() if not a.isSeparator() and not a.menu() and not a.statusTip()]
            print(f"  {m.title().replace('&', ''):10s} {n:2d} item"
                  + (f" | tanpa keterangan: {tanpa}" if tanpa else ""), flush=True)
            m.popup(s.mapToGlobal(s.rect().center()))
            QTimer.singleShot(300, s.foto)

        def foto(s):
            m = s.menus[s.i]
            m.grab().save(str(OUT / f"{s.i}_{m.title().replace('&', '')}.png"))
            m.hide()
            s.i += 1
            QTimer.singleShot(150, s.buka)

    mainwindow.JendelaUtama = Uji


hook()
A.main()
