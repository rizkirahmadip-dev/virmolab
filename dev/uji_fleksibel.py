"""Uji residu fleksibel (0.9.3) lewat jendela utama: 1HSG -> reseptor -> dialog residu fleksibel -> antrean
AD-GPU + Vina dengan flex -> pose + objek rantai samping -> interaksi memakai posisi flex -> kembali kaku.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_fleksibel.py
Keluaran: dev/uji/fleksibel/ (proyek, gui_*.png = grab jendela VirmoDock saja).
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", "terang")
st.remove("layout")
st.remove("sesi_terbuka")
OUT = Path("dev/uji/fleksibel").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True, exist_ok=True)
PILIH = ("A:25", "B:25", "A:50", "B:50")

import virmodock.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def hook():
    from virmodock.core import antrean as AN
    from virmodock.core import mesin as M
    from virmodock.core import prep_reseptor as R
    from virmodock.core.proyek import Proyek
    from virmodock.ui import dialog_fleksibel, mainwindow

    def exec_uji(self):
        self.resize(560, 560)
        self.show()
        QApplication.processEvents()
        n = 0
        for r in range(self.tabel.rowCount()):
            it = self.tabel.item(r, 0)
            if it.data(Qt.UserRole) in PILIH:
                it.setCheckState(Qt.Checked)
                n += 1
        QApplication.processEvents()
        self.grab().save(str(OUT / "dialog_fleksibel.png"))
        print("dialog: calon", self.tabel.rowCount(), "dicentang", n, "|", self.l_info.text(), flush=True)
        return 1
    dialog_fleksibel.DialogFleksibel.exec = exec_uji

    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            s.selesai = []
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(560000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _galat(s, t):
            print("GALAT:", t, flush=True)
            gagal.append(t)

        def l1(s):
            s._set_proyek(Proyek.baru(OUT, "uji_flex"))
            s.impor([str(Path("dev/uji/1HSG.pdb").resolve())])
            QTimer.singleShot(3000, s.l2)

        def l2(s):
            asal = next(o for o in s.objek.values() if o.jenis == "protein")
            opsi = R.OpsiReseptor(protonasi="templat")
            h = R.siapkan(s._teks_sumber_reseptor(asal), opsi)
            s._reseptor_siap(asal, h, opsi)
            pr = s.proyek
            cek(pr.p("reseptor", "untuk_meeko.pdb").exists() and pr.reseptor.get("meeko"), "masukan Meeko tersimpan")
            for n in ("MK1", "aspirin"):
                shutil.copy(f"dev/uji/{n}.pdbqt", pr.p("ligan", "pdbqt", f"{n}.pdbqt"))
                pr.ligan.append({"id": n, "nama": n, "status": "siap", "pdbqt": f"ligan/pdbqt/{n}.pdbqt"})
            cek(bool(s.box.get("pusat")), f"grid box otomatis di ligan asli: {s.box.get('pusat')}")
            s.atur_fleksibel()
            QTimer.singleShot(200, s.l3)

        def l3(s):
            fx = (s.proyek.reseptor or {}).get("fleksibel")
            if not fx:     # pekerja Meeko masih berjalan
                QTimer.singleShot(500, s.l3)
                return
            cek(sorted(fx["residu"]) == sorted(PILIH), f"residu fleksibel: {fx['residu']} ({fx['torsi']} torsi)")
            cek(s.param.l_flex.text() != "kaku", f"panel Jalankan: {s.param.l_flex.text()}")
            k = {"pusat": s.box["pusat"], "ukuran": s.box["ukuran"], "spasi": 0.375}
            pr = s.proyek
            s.j_gpu = AN.job_baru(pr, pr.ligan, "adgpu", "gpu", {"nrun": 10}, k)
            cek(s.j_gpu.get("flex") == "reseptor/flex.pdbqt" and s.j_gpu["reseptor"].endswith("_kaku.pdbqt"),
                "job memakai reseptor kaku + flex")
            s.pelaksana.tambah(s.j_gpu)
            s.j_vina = AN.job_baru(pr, pr.ligan[:1], "vina", "cpu", {"exhaustiveness": 4}, k)
            s.pelaksana.tambah(s.j_vina)
            s.pelaksana.jobSelesai.connect(s.job_selesai)

        def job_selesai(s, jid):
            s.selesai.append(jid)
            j = s.pelaksana.cari(jid)
            print("JOB", jid, j["mesin"], j["status"], [(l["nama"], l["status"], l["energi"], l.get("pesan"))
                                                       for l in j["ligan"]], flush=True)
            if len(s.selesai) == 2:
                QTimer.singleShot(500, s.l4)

        def l4(s):
            pr = s.proyek
            for j in (s.j_gpu, s.j_vina):
                l = j["ligan"][0]
                cek(l["status"] == "selesai", f"{M.MESIN[j['mesin']]} MK1 flex selesai: {l['energi']}")
                pose = M.baca_hasil(j["mesin"], pr.p(l["keluaran"]))
                cek(bool(pose[0].flex) and len(M.residu_flex(pose[0].flex)) == 4,
                    f"  flex di pose: {M.residu_flex(pose[0].flex)}")
                n_lig = sum(1 for b in pose[0].pdbqt.splitlines() if b.startswith(("ATOM", "HETATM")))
                cek(n_lig < 60, f"  pose ligan bersih dari atom flex ({n_lig} atom)")
                cek(l.get("interaksi") is not None, f"  interaksi tersimpan: {l.get('interaksi')}")
            o = s.buka_pose(s.j_gpu["id"], s.j_gpu["ligan"][0]["id"], 1)
            fo = [x for x in s.objek.values() if x.info.get("flex_pose") == 1 and x.grup == o.grup]
            cek(len(fo) == 1 and fo[0].tampil, "objek rantai samping pose 1 tampil")
            cek(bool(o.info.get("residu_flex")), f"info pose: {o.info.get('residu_flex')}")
            QTimer.singleShot(2500, s.l5)

        def l5(s):
            ai = s._aktif_inter or {}
            res = {h["residu"] for h in ai.get("daftar", [])}
            cek(any("ASP 25" in r or "ASH 25" in r for r in res), f"interaksi pose memuat Asp25 ({len(res)} residu)")
            s.grab().save(str(OUT / "gui_pose_flex.png"))
            o2 = s.buka_pose(s.j_gpu["id"], s.j_gpu["ligan"][0]["id"], 2)
            if o2 and o2.info.get("peringkat") == 2:
                f1 = [x for x in s.objek.values() if x.info.get("flex_pose") == 1 and x.grup == o2.grup]
                f2 = [x for x in s.objek.values() if x.info.get("flex_pose") == 2 and x.grup == o2.grup]
                cek(f2 and f2[0].tampil and not f1[0].tampil, "ganti pose: rantai samping ikut berganti")
            # kembali ke reseptor kaku
            s.proyek.reseptor.pop("fleksibel", None)
            j = AN.job_baru(s.proyek, s.proyek.ligan[:1], "adgpu", "gpu", {"nrun": 5}, s.j_gpu["kotak"])
            cek("flex" not in j and j["reseptor"] == "reseptor/reseptor.pdbqt", "job kaku setelah dimatikan")
            s.j_kaku = j
            s.pelaksana.jobSelesai.disconnect(s.job_selesai)
            s.pelaksana.jobSelesai.connect(s.l6)
            s.pelaksana.tambah(j)

        def l6(s, jid):
            j = s.pelaksana.cari(jid)
            l = j["ligan"][0]
            gpf = s.proyek.p("grid", "reseptor.gpf").read_text()
            cek(l["status"] == "selesai", f"AD-GPU kaku sesudah flex: {l['energi']} (grid dibuat ulang: "
                f"{'# reseptor' in gpf})")
            s.proyek.simpan()
            print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
try:
    A.main()
except SystemExit:
    pass
