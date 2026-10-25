"""Tangkapan tambahan untuk tutorial PDF (grab jendela/dialog saja). Hasil: docs/gambar/t*.png"""
import atexit
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer

sys.argv = [sys.argv[0]]
OUT = Path("docs/gambar").resolve()
# Tangkapan ini ikut tutorial PDF di dalam installer: jalur proyek dan sumber tidak boleh memperlihatkan folder
# pengembangan, dan tampilannya harus seperti pemasangan baru (bukan mode ahli pengembang).
KERJA = Path("C:/VirmoLab-dokumentasi")
(KERJA / "contoh").mkdir(parents=True, exist_ok=True)
SUMBER = KERJA / "contoh" / "1HSG.pdb"
shutil.copyfile(Path("dev/uji/1HSG.pdb"), SUMBER)
st = QSettings("VirmoLab", "VirmoLab")
KERJA_LAMA = st.value("folder_kerja", "")
MODE_LAMA = st.value("mode_pengguna", "")
for k in ("layout", "layout_v2", "sesi_terbuka", "geometri"):
    st.remove(k)
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")
st.setValue("folder_kerja", str(KERJA))
st.setValue("mode_pengguna", "pemula")

import virmolab.app as A
from PySide6.QtWidgets import QApplication


def simpan(w, nama):
    pm = w.grab()
    if pm.width() > 1400 * pm.devicePixelRatio():
        pm = pm.scaledToWidth(int(1400 * pm.devicePixelRatio()), Qt.SmoothTransformation)
    pm.save(str(OUT / f"{nama}.png"))
    print("gambar", nama, flush=True)


def hook():
    from virmolab.ui import mainwindow
    from virmolab.ui.dialogs import DialogAmbil

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1600, 950)
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
            s.impor([str(SUMBER)])
            QTimer.singleShot(3500, s.l3)

        def l3(s):
            prot = next(o for o in s.objek.values() if o.jenis == "protein")
            s.hier.pilih_objek(prot.id)
            s.d_tamp.show()
            s.d_tamp.raise_()
            g = dict(prot.gaya, permukaan={"type": "ses", "color": {"mode": "hydro"}, "opacity": 0.85, "mesh": False})
            s.ubah_gaya(prot.id, g)
            s.tampilan.muat(prot)
            QTimer.singleShot(6000, lambda: (simpan(s, "t03_permukaan"), pulih(), QApplication.quit()))

    mainwindow.JendelaUtama = U
    A.main()


def pulih():
    """Pengaturan pengguna dikembalikan: skrip ini mengubah folder kerja dan mode pengguna yang sebenarnya."""
    st2 = QSettings("VirmoLab", "VirmoLab")
    for kunci, lama in (("folder_kerja", KERJA_LAMA), ("mode_pengguna", MODE_LAMA)):
        if lama:
            st2.setValue(kunci, lama)
        else:
            st2.remove(kunci)
    st2.sync()


atexit.register(pulih)


hook()
