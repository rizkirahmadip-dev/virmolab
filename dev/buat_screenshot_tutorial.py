"""Tangkapan tambahan untuk tutorial PDF (grab jendela/dialog saja). Hasil: docs/gambar/t*.png"""
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer

sys.argv = [sys.argv[0]]
OUT = Path("docs/gambar").resolve()
st = QSettings("VirmoDock", "VirmoDock")
for k in ("layout", "sesi_terbuka", "geometri"):
    st.remove(k)
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")

import virmodock.app as A
from PySide6.QtWidgets import QApplication


def simpan(w, nama):
    pm = w.grab()
    if pm.width() > 1400 * pm.devicePixelRatio():
        pm = pm.scaledToWidth(int(1400 * pm.devicePixelRatio()), Qt.SmoothTransformation)
    pm.save(str(OUT / f"{nama}.png"))
    print("gambar", nama, flush=True)


def hook():
    from virmodock.ui import mainwindow
    from virmodock.ui.dialogs import DialogAmbil

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1440, 900)
            s.move(30, 30)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(120000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            d = DialogAmbil(s, 0)
            d.pdbid.setText("1HSG")
            d.show()
            QTimer.singleShot(400, lambda: (simpan(d, "t01_rcsb"), d.tab.setCurrentIndex(1),
                                            d.pubchem.setPlainText("quercetin\nluteolin\nkaempferol\nnelfinavir"),
                                            QTimer.singleShot(300, lambda: (simpan(d, "t02_pubchem"), d.reject(),
                                                                            s.l2()))))

        def l2(s):
            s.impor([str(Path("dev/uji/1HSG.pdb").resolve())])
            QTimer.singleShot(3500, s.l3)

        def l3(s):
            prot = next(o for o in s.objek.values() if o.jenis == "protein")
            s.hier.pilih_objek(prot.id)
            s.d_tamp.raise_()
            g = dict(prot.gaya, permukaan={"type": "ses", "color": {"mode": "hydro"}, "opacity": 0.85, "mesh": False})
            s.ubah_gaya(prot.id, g)
            s.tampilan.muat(prot)
            QTimer.singleShot(6000, lambda: (simpan(s, "t03_permukaan"), QApplication.quit()))

    mainwindow.JendelaUtama = U
    A.main()


hook()
