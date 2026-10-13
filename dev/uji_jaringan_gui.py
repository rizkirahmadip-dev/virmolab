#!/usr/bin/env python3
"""Uji GUI tab Jaringan & jalur: bangun jaringan sungguhan (STRING + Open Targets + Reactome) dan simpan tangkapan layar.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_jaringan_gui.py [terang|gelap]
Keluaran: dev/uji/lanjut/jaringan_<tema>.png
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from virmolab.ui import theme  # noqa: E402
from virmolab.ui.dialog_target_balik import DialogTargetBalik  # noqa: E402

TEMA = sys.argv[1] if len(sys.argv) > 1 else "terang"
KELUAR = AKAR / "dev" / "uji" / "lanjut"
KELUAR.mkdir(parents=True, exist_ok=True)

app = QApplication([])
app.setPalette(theme.palet(TEMA))
app.setStyleSheet(theme.qss(TEMA))
d = DialogTargetBalik(None, proyek=None)
d.resize(1250, 820)
d.show()

# target contoh = panel antiinflamasi (gen nyata), seperti setelah "Kirim target terpilih ke Jaringan"
d._gen_terpilih = ["PTGS2", "PTGS1", "MAPK14", "JAK2", "BTK", "PDE4D", "DHODH", "NR3C1"]
d._lig_data = {"id": "L1", "nama": "Ibuprofen"}
d._perbarui_ringkasan_jaringan()
d.tabs.setCurrentIndex(1)

galat = []


def selesai():
    if d._graf is None:
        galat.append("graf tidak terbentuk: " + d.l_status_jaringan.text())
    else:
        print("status:", d.l_status_jaringan.text())
        print("simpul:", d._graf.number_of_nodes(), "tepi:", d._graf.number_of_edges())
        print("inti stabil:", d._sens.get("inti_stabil"))
        print("jalur teratas:", [(b["nama"][:40], round(b["q"], 4)) for b in d._pengayaan[:3]])
        print("paragraf:", d._info_jaringan)
    d.grab().save(str(KELUAR / f"jaringan_{TEMA}.png"))
    app.quit()


d._utas_asli = d._jaringan_siap


def bungkus(hasil, g):
    d._utas_asli(hasil, g)
    QTimer.singleShot(400, selesai)


d._jaringan_siap = bungkus
d._bangun_jaringan()
d._utas_jaringan.selesai.disconnect()
d._utas_jaringan.selesai.connect(bungkus)
QTimer.singleShot(180000, app.quit)
app.exec()
print("GAGAL" if galat else "OK", *galat)
sys.exit(1 if galat else 0)
