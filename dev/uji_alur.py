"""Uji alur Tahap 2 di GUI: impor -> reseptor -> ligan -> docking AD-GPU & Vina -> pose -> buka ulang proyek.

Dialog dilewati (fungsi intinya dipanggil langsung). Tangkapan hanya jendela VirmoDock (widget.grab()).
  VD_SHOT=dev/uji/gambar/alur.png PYTHONPATH=. .venv/Scripts/python.exe dev/uji_alur.py
"""
import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/kerja").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
KERJA.mkdir(parents=True)
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("wizard_selesai", True)
st.setValue("tema", os.environ.get("VD_TEMA", "terang"))
st.setValue("folder_kerja", str(KERJA))
st.remove("layout")
st.remove("sesi_terbuka")
out = os.environ.get("VD_SHOT", "dev/uji/gambar/alur.png")

import virmodock.app as A
from PySide6.QtWidgets import QApplication
Path("dev/uji/gambar").mkdir(parents=True, exist_ok=True)  # keluaran gambar uji


def hook():
    from virmodock.ui import mainwindow
    from virmodock.core import prep_reseptor, prep_ligan, molekul
    from virmodock.ui import kerja
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            s.langkah = 0
            s.pelaksana.jobSelesai.connect(s._job_ok)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(400000, lambda: (print("TIMEOUT"), s._foto("dev/uji/gambar/alur_timeout.png"), QApplication.quit()))

        def cetak(s, *a):
            print(*a, flush=True)

        def l1(s):
            s.impor([str(Path("dev/uji/1HSG.pdb").resolve())])
            QTimer.singleShot(3000, s.l2)

        def l2(s):
            prot = next(o for o in s.objek.values() if o.jenis == "protein")
            s.cetak("box awal", s.box)
            opsi = prep_reseptor.OpsiReseptor()
            kerja.jalankan(prep_reseptor.siapkan, prot.teks, opsi,
                           selesai=lambda h: (s._reseptor_siap(prot, h, opsi), QTimer.singleShot(500, s.l3)),
                           galat=s.cetak)

        def l3(s):
            s.cetak("reseptor", s.proyek.reseptor["atom"], s.proyek.folder)
            asli = next(o for o in s.objek.values() if o.info.get("ligan_asli"))
            asp = molekul.dari_smiles("CC(=O)Oc1ccccc1C(=O)O", "aspirin")[0]
            data = [(asli.nama, asli.teks, "pdb"), (asp.nama, asp.teks, "sdf")]
            kerja.jalankan(prep_ligan.siapkan_banyak, data, prep_ligan.OpsiLigan(),
                           selesai=lambda h: (s._ligan_siap(list(zip([asli, asp], h))), QTimer.singleShot(500, s.l4)),
                           galat=s.cetak)

        def l4(s):
            s.cetak("ligan siap", [l["id"] for l in s.proyek.ligan_siap()])
            s.aksi_kotak("ligan_asli")
            s.param.set_parameter({"mesin": "adgpu", "perangkat": "gpu", "nrun_gpu": 10})
            s._param_berubah(s.param.parameter())
            s.jalankan_docking()
            s.param.set_parameter({"mesin": "vina", "perangkat": "cpu", "exhaustiveness": 4})
            s._param_berubah(s.param.parameter())
            s.jalankan_docking()
            QTimer.singleShot(3000, lambda: s._foto("dev/uji/gambar/alur_jalan.png"))

        def _job_ok(s, jid):
            j = s.pelaksana.cari(jid)
            s.cetak("JOB", jid, j["mesin"], j["status"], [(l["id"], l["status"], l["energi"], l["detik"]) for l in j["ligan"]])
            s.langkah += 1
            if s.langkah == 2:
                QTimer.singleShot(800, s.l5)

        def l5(s):
            j = s.proyek.job[0]
            s.buka_pose(j["id"], j["ligan"][0]["id"])
            asli = next(o for o in s.objek.values() if o.info.get("ligan_asli") and o.fmt == "pdb")
            s.set_tampil(asli.id, True)
            s.hier.set_centang(asli.id, True)
            QTimer.singleShot(4000, s.l6)

        def l6(s):
            s._foto(out)
            folder = s.proyek.folder
            n_obj = len(s.objek)
            s._simpan_diam()
            s.buka_proyek(str(folder))
            s.cetak("buka ulang:", n_obj, "->", len(s.objek), "objek; kotak", s.proyek.kotak,
                    "; param mesin", s.proyek.parameter.get("mesin"), "; job", [j["status"] for j in s.proyek.job])
            s.cetak("panel kotak", s.param.kotak())
            QTimer.singleShot(4000, lambda: (s._foto("dev/uji/gambar/alur_buka.png"), s.cetak(s.log.toPlainText()[-2500:]),
                                             s.cetak("PESAN:", s.pesan.toPlainText()[-1500:]), QApplication.quit()))

        def _foto(s, f):
            s.grab().save(f)
            s.cetak("saved", f)

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
