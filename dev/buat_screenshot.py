"""Tangkapan layar untuk dokumentasi (widget.grab(), bukan layar). Hasil: docs/gambar/*.png (lebar ≤ 1400 px).

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/buat_screenshot.py
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer

sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/kerja_docs").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
KERJA.mkdir(parents=True)
OUT = Path("docs/gambar").resolve()
OUT.mkdir(parents=True, exist_ok=True)
st = QSettings("VirmoDock", "VirmoDock")
for k in ("layout", "layout_v2", "sesi_terbuka", "geometri", "kolom_hasil", "proyek_terakhir"):
    st.remove(k)
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")
st.setValue("folder_kerja", str(KERJA))

import virmodock.app as A
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: None)


def simpan(w, nama):
    pm = w.grab()
    if pm.width() > 1400 * pm.devicePixelRatio():
        pm = pm.scaledToWidth(int(1400 * pm.devicePixelRatio()), Qt.SmoothTransformation)
    pm.save(str(OUT / f"{nama}.png"))
    print("gambar", nama, pm.width(), pm.height(), flush=True)


def hook():
    from virmodock.ui import mainwindow
    from virmodock.core import prep_reseptor, prep_ligan, molekul, ekspor
    from virmodock.ui import kerja
    from virmodock.ui.dialog_reseptor import DialogReseptor
    from virmodock.ui.dialog_ligan import DialogLigan
    from virmodock.ui.dialog_ekspor import DialogEkspor
    from virmodock.ui.dialog_bantuan import DialogLapor
    from virmodock.ui.dialogs import Wizard

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1440, 900)
            s.move(30, 30)
            s.n = 0
            s.pelaksana.jobSelesai.connect(s._job)
            QTimer.singleShot(3000, s.l0)
            QTimer.singleShot(600000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l0(s):
            w = Wizard(s.env, str(KERJA), s)
            w.show()
            QTimer.singleShot(600, lambda: (simpan(w, "01_wizard"), w.reject(),
                                            QTimer.singleShot(800, lambda: (simpan(s, "00_sambutan"), s.l1()))))

        def l1(s):
            s.impor([str(Path("dev/uji/1HSG.pdb").resolve())])
            QTimer.singleShot(4000, lambda: (simpan(s, "02_impor"), s.l2()))

        def l2(s):
            prot = [o for o in s.objek.values() if o.jenis == "protein"]
            d = DialogReseptor(prot, {}, s)
            d.show()
            QTimer.singleShot(500, lambda: (simpan(d, "03_dialog_reseptor"), d.reject(), s.l3(prot[0])))

        def l3(s, prot):
            opsi = prep_reseptor.OpsiReseptor()
            kerja.jalankan(prep_reseptor.siapkan, prot.teks, opsi,
                           selesai=lambda h: (s._reseptor_siap(prot, h, opsi), QTimer.singleShot(1500, s.l4)))

        def l4(s):
            simpan(s, "04_reseptor_siap")
            asli = next(o for o in s.objek.values() if o.info.get("ligan_asli"))
            lig = [asli] + molekul.dari_smiles("CC(=O)Oc1ccccc1C(=O)O", "aspirin") + \
                molekul.dari_smiles("O=c1cc(-c2ccc(O)c(O)c2)oc2cc(O)cc(O)c12", "luteolin")
            d = DialogLigan(lig, "terang", s)
            d.resize(980, 560)
            d.show()
            s._dlg = d
            d.siap.connect(s._ligan_siap)
            QTimer.singleShot(400, d.jalankan)
            QTimer.singleShot(6000, lambda: (simpan(d, "05_dialog_ligan"), d.close(), s.l5()))

        def l5(s):
            s.aksi_kotak("ligan_asli")
            s.ke_langkah(2)
            s.param.set_parameter({"mesin": "adgpu", "perangkat": "gpu", "nrun_gpu": 20})
            s._param_berubah(s.param.parameter())
            QTimer.singleShot(1500, lambda: (simpan(s, "06_parameter_gridbox"), s.ke_langkah(3),
                                             QTimer.singleShot(1200, lambda: (simpan(s, "06b_jalankan"), s.l6()))))

        def l6(s):
            s.jalankan_docking()
            QTimer.singleShot(4500, lambda: simpan(s, "07_antrean"))

        def _job(s, jid):
            s.n += 1
            if s.n == 1:
                QTimer.singleShot(1500, s.l7)
            elif s.n == 2:
                QTimer.singleShot(1500, s.l10)

        def l7(s):
            s.atur_ruang("analisis")
            s.tab_tengah.setCurrentWidget(s.hasil)
            QTimer.singleShot(800, lambda: (simpan(s, "08_hasil"), s.l8()))

        def l8(s):
            b = ekspor.baris_hasil(s.proyek)
            s.buka_pose(b[0]["job"], b[0]["lid"], 1)
            s.d_inter.raise_()
            QTimer.singleShot(3000, lambda: (simpan(s, "09_interaksi"), s.l9()))

        def l9(s):
            s.tab_tengah.setCurrentWidget(s.diagram)
            QTimer.singleShot(1200, lambda: (simpan(s, "10_diagram2d"), s.validasi_redocking()))

        def l10(s):
            QTimer.singleShot(2500, lambda: (simpan(s, "11_validasi"), s.l11()))

        def l11(s):
            b = ekspor.baris_hasil(s.proyek)
            s.bandingkan([(x["job"], x["lid"]) for x in b[:3]])
            QTimer.singleShot(7000, lambda: (simpan(s, "12_bandingkan"), s.l12()))

        def l12(s):
            d = DialogEkspor((s.viewer.width(), s.viewer.height()), True, s, 0)
            d.show()
            QTimer.singleShot(500, lambda: (simpan(d, "13_ekspor"), d.reject(), s.l13()))

        def l13(s):
            d = DialogLapor(mainwindow.VERSI, s.env, s)
            d.show()
            QTimer.singleShot(500, lambda: (simpan(d, "14_lapor"), d.reject(), s.l14()))

        def l14(s):
            s.atur_ruang("analisis")
            s.tab_tengah.setCurrentWidget(s.sifat)
            QTimer.singleShot(2500, lambda: (simpan(s, "16_sifat"), s.tab_tengah.setCurrentWidget(s.statistik),
                                             s.statistik.c_jenis.setCurrentIndex(1),
                                             QTimer.singleShot(1500, lambda: (simpan(s, "17_statistik"), s.l15()))))

        def l15(s):
            s.atur_ruang("siapkan")
            s.terapkan_tema("gelap")
            s.tab_tengah.setCurrentWidget(s.w_view)
            QTimer.singleShot(2500, lambda: (simpan(s, "15_gelap"), s.terapkan_tema("terang"), QApplication.quit()))

    mainwindow.JendelaUtama = U
    A.main()


hook()
