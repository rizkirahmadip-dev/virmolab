"""Uji Kemiripan/ruang kimia/farmakofor: salinan proyek docs + 14 ligan SMILES, semua tab dialog, farmakofor
pose aktif & bersama di viewport, ekspor CSV/SVG/PML.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_kemiripan.py
Keluaran: dev/uji/kemiripan/
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

SUMBER = Path(str(sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1])).resolve()
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/kemiripan").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
shutil.copytree(SUMBER, KERJA / SUMBER.name)
st = QSettings("VirmoDock", "VirmoDock")
for k in ("sesi_terbuka", "proyek_terakhir", "layout_v2"):
    st.remove(k)
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")

SMILES = {"ritonavir": "CC(C)c1nc(CN(C)C(=O)N[C@@H](C(C)C)C(=O)N[C@@H](Cc2ccccc2)C[C@H](O)[C@H](Cc2ccccc2)NC(=O)OCc2cncs2)cs1",
          "saquinavir": "CC(C)(C)NC(=O)[C@@H]1C[C@@H]2CCCC[C@@H]2CN1C[C@@H](O)[C@H](Cc1ccccc1)NC(=O)[C@H](CC(N)=O)NC(=O)c1ccc2ccccc2n1",
          "nelfinavir": "Cc1c(O)cccc1C(=O)N[C@@H](CSc1ccccc1)[C@H](O)CN1C[C@H]2CCCC[C@H]2C[C@H]1C(=O)NC(C)(C)C",
          "kuersetin": "O=c1c(O)c(-c2ccc(O)c(O)c2)oc2cc(O)cc(O)c12",
          "kaempferol": "O=c1c(O)c(-c2ccc(O)cc2)oc2cc(O)cc(O)c12",
          "apigenin": "O=c1cc(-c2ccc(O)cc2)oc2cc(O)cc(O)c12",
          "naringenin": "O=C1CC(c2ccc(O)cc2)Oc2cc(O)cc(O)c21",
          "kurkumin": "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O",
          "kafein": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
          "teofilin": "Cn1c(=O)c2[nH]cnc2n(C)c1=O",
          "ibuprofen": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
          "naproksen": "COc1ccc2cc(C(C)C(=O)O)ccc2c1",
          "parasetamol": "CC(=O)Nc1ccc(O)cc1",
          "salisilat": "OC(=O)c1ccccc1O"}

import virmodock.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: None)


def hook():
    from virmodock.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1500, 920)
            s._galat = lambda t: print("GALAT", t, flush=True)
            s._path = lambda judul, nama, f: str(KERJA / nama)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(180000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            from virmodock.core import molekul
            ob = []
            for n, smi in SMILES.items():
                ob += molekul.dari_smiles(smi, n)
            s.tambah_objek(ob, fokus=False)
            j = s.proyek.job[0]
            l = next(x for x in j["ligan"] if x["status"] == "selesai")
            s.buka_pose(j["id"], l["id"], 1)
            s.a_farma.setChecked(True)
            s._tampilkan_farmakofor()
            print("STATUS farmakofor:", s.statusBar().currentMessage(), flush=True)
            QTimer.singleShot(2500, s.l3)

        def l3(s):
            s.viewer.grab().save(str(KERJA / "farmakofor_pose.png"))
            from virmodock.ui.dialog_kemiripan import DialogKemiripan
            d = s.dlg = DialogKemiripan(s)
            d.resize(1300, 820)
            d.show()
            print("ligan:", len(d.lig), d.l_info.text(), "klaster:", d.klaster, flush=True)
            for i, n in enumerate(("peta", "matriks", "mirip", "klaster")):
                d.tab.setCurrentIndex(i)
                QApplication.processEvents()
                d.grab().save(str(KERJA / f"dlg_{n}.png"))
            d.tab.setCurrentIndex(0)
            d.c_warna.setCurrentIndex(1)
            d.c_lbl.setChecked(True)
            QApplication.processEvents()
            d.grab().save(str(KERJA / "dlg_peta_dg.png"))
            d.c_peta.setCurrentIndex(1)
            QApplication.processEvents()
            d.grab().save(str(KERJA / "dlg_peta_pca.png"))
            d._grafik("svg")
            for k in range(d.c_fp.count()):
                d.c_fp.setCurrentIndex(k)
                print(f"  {d.c_fp.currentText()}: klaster {max(d.klaster)}", flush=True)
            d.c_fp.setCurrentIndex(0)
            d.tab.setCurrentIndex(2)
            d.e_smiles.setText("CC(=O)Oc1ccccc1C(=O)O")
            d.isi_mirip()
            print("mirip aspirin:", [d.t_mirip.item(r, 1).text() + " " + d.t_mirip.item(r, 2).text()
                                     for r in range(3)], flush=True)
            d.ekspor_csv()
            d.tab.setCurrentIndex(4)
            d.s_top.setValue(4)
            d.s_frek.setValue(30)
            d.s_rad.setValue(2.0)
            d.hitung_farma()
            QTimer.singleShot(6000, s.l4)

        def l4(s):
            d = s.dlg
            print("farmakofor bersama:", d.t_farma.rowCount(), "fitur", flush=True)
            d.grab().save(str(KERJA / "dlg_farma.png"))
            d.simpan_pml()
            QTimer.singleShot(1500, s.l5)

        def l5(s):
            s.viewer.grab().save(str(KERJA / "farmakofor_bersama.png"))
            for f in sorted(KERJA.iterdir()):
                if f.is_file():
                    print(f"  {f.name}: {f.stat().st_size} B")
            QTimer.singleShot(300, QApplication.quit)

    mainwindow.JendelaUtama = U


hook()
A.main()
