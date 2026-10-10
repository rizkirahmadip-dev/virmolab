"""Uji pencarian RCSB (0.9.5, butuh internet): dialog impor tab RCSB -> cari -> saran ★ -> kode terisi.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_rcsb.py
Keluaran: dev/uji/v095/dialog_rcsb.png
"""
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from virmodock.app import siapkan_kimia

siapkan_kimia()
app = QApplication(sys.argv)
app.setStyle("Fusion")
from virmodock.ui import theme

app.setPalette(theme.palet("terang"))
app.setStyleSheet(theme.qss("terang").replace("ICON_CHECK", ""))
from virmodock.ui.dialogs import DialogAmbil

OUT = Path("dev/uji/v095")
OUT.mkdir(parents=True, exist_ok=True)
gagal = []
d = DialogAmbil(None, 0)
d.show()
d.rc_kueri.setText("carbonic anhydrase 2 acetazolamide")
d.rc_org.setCurrentIndex(1)       # Homo sapiens
d._rc_cari()
t0 = time.time()
while d.rc_daftar.topLevelItemCount() == 0 and time.time() - t0 < 60:
    app.processEvents()
    time.sleep(0.1)
app.processEvents()
n = d.rc_daftar.topLevelItemCount()
print(("OK    " if n else "GAGAL ") + f"hasil {n}: {d.rc_status.text()[:140]}")
if not n:
    gagal.append("hasil")
it = d.rc_daftar.topLevelItem(0) if n else None
ok = bool(it) and "★" in it.text(0) and d.pdbid.text() == it.text(0).split()[0]
print(("OK    " if ok else "GAGAL ") + f"saran teratas {it.text(0) if it else '-'} -> ID PDB '{d.pdbid.text()}'")
if not ok:
    gagal.append("saran")
req = d.permintaan()
print(("OK    " if req and req[0] == "rcsb" else "GAGAL ") + f"permintaan: {req}")
d.grab().save(str(OUT / "dialog_rcsb.png"))
print("GAGAL" if gagal else "LULUS", len(gagal))
