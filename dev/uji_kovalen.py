"""Uji docking kovalen lewat jendela utama: 6OIM (KRAS G12C) -> reseptor -> dialog Docking kovalen (Cys12) ->
Jalankan docking (aduk dibuat di latar) -> AD-GPU --flexres saja -> pose sotorasib vs kristal, kloroasetamida
ikut, aspirin dilewati -> objek rantai samping Cys12 -> interaksi -> matikan kovalen.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_kovalen.py
Keluaran: dev/uji/kovalen_gui/ (proyek, gui_*.png = grab jendela VirmoLab saja).
"""
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("tema", "terang")
st.remove("layout")
st.remove("sesi_terbuka")
OUT = Path("dev/uji/kovalen_gui").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True, exist_ok=True)
PDB = Path("dev/uji/kovalen/6OIM.pdb").resolve()
LIGAN = {"sotorasib": "C=CC(=O)N1CCN([C@@H](C)C1)C2=NC(=O)N(c3nc(c(F)cc23)c4c(O)cccc4F)c5c(C)ccnc5C(C)C",
         "kloroasetamida": "ClCC(=O)Nc1ccc(cc1)C(=O)N"}

import virmolab.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def hook():
    import numpy as np
    from virmolab.core import mesin as M
    from virmolab.core import prep_ligan as PL
    from virmolab.core import prep_reseptor as R
    from virmolab.core.proyek import Proyek
    from virmolab.ui import dialog_kovalen, mainwindow

    def exec_uji(self):
        self.resize(640, 620)
        self.show()
        QApplication.processEvents()
        baris = [self.t_res.item(r, 0).data(0x0100) for r in range(self.t_res.rowCount())]
        for r, b in enumerate(baris):
            if b[0] == "A:12":
                self.t_res.selectRow(r)
        QApplication.processEvents()
        self.grab().save(str(OUT / "dialog_kovalen.png"))
        isi = [(self.t_lig.item(r, 0).text(), self.t_lig.item(r, 1).text()) for r in range(self.t_lig.rowCount())]
        print("dialog: calon", baris, "| ligan", isi, "|", self.l_info.text(), flush=True)
        cek(self.pilihan() == ("A:12", "CYS"), "dialog memilih CYS 12 A")
        cek(sum("tidak ada" in w for _n, w in isi) == 1, "dialog: aspirin tanpa gugus reaktif")
        return 1
    dialog_kovalen.DialogKovalen.exec = exec_uji

    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(900000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _galat(s, t):
            print("GALAT:", t, flush=True)
            gagal.append(t)

        def l1(s):
            s._set_proyek(Proyek.baru(OUT, "uji_kovalen"))
            s.impor([str(PDB)])
            QTimer.singleShot(3000, s.l2)

        def l2(s):
            asal = next(o for o in s.objek.values() if o.jenis == "protein")
            opsi = R.OpsiReseptor(protonasi="templat")
            h = R.siapkan(s._teks_sumber_reseptor(asal), opsi)
            s._reseptor_siap(asal, h, opsi)
            pr = s.proyek
            teks = PDB.read_text()
            mov = [b for b in teks.splitlines() if b.startswith("HETATM") and b[17:20] == "MOV"]
            pusat = np.array([[float(b[30:38]), float(b[38:46]), float(b[46:54])] for b in mov]).mean(0)
            s._atur_kotak(pusat.tolist(), [24, 24, 24], 0.375, sumber="uji MOV")
            pr.siapkan_folder()
            for n, smi in LIGAN.items():
                hl = PL.siapkan_satu(n, smi, "smiles", PL.OpsiLigan())
                cek(hl.status != "gagal", f"ligan {n} disiapkan ({hl.status} {hl.alasan})")
                pr.p("ligan", "pdbqt", f"{n}.pdbqt").write_text(hl.pdbqt, encoding="utf-8")
                info = {"id": n, "nama": n, "status": "siap", "pdbqt": f"ligan/pdbqt/{n}.pdbqt"}
                if n == "sotorasib":
                    pr.p("ligan", "sumber", "sotorasib_kristal.pdb").write_text("\n".join(mov) + "\nEND\n")
                    info["kristal"] = "ligan/sumber/sotorasib_kristal.pdb"
                pr.ligan.append(info)
            shutil.copy("dev/uji/aspirin.pdbqt", pr.p("ligan", "pdbqt", "aspirin.pdbqt"))
            pr.ligan.append({"id": "aspirin", "nama": "aspirin", "status": "siap", "pdbqt": "ligan/pdbqt/aspirin.pdbqt"})
            s._ringkasan()
            s.atur_kovalen()
            QTimer.singleShot(200, s.l3)

        def l3(s):
            kv = (s.proyek.reseptor or {}).get("kovalen")
            if not kv:     # pekerja Meeko masih berjalan
                QTimer.singleShot(500, s.l3)
                return
            pr = s.proyek
            cek(kv["residu"] == "A:12" and kv["resn"] == "CYS", f"kovalen tersimpan: {kv['label']} → {kv['kaku']}")
            kaku = pr.p(kv["kaku"]).read_text()
            sisi = [b[12:16].strip() for b in kaku.splitlines() if b.startswith("ATOM") and b[17:20] == "CYS"
                    and b[21] == "A" and int(b[22:26]) == 12]
            cek("SG" not in sisi and "CB" not in sisi and "N" in sisi, f"reseptor kaku tanpa rantai samping Cys12: {sisi}")
            cek(s.param.l_kov.text().startswith("ya"), f"panel Jalankan: {s.param.l_kov.text()}")
            asli = s.param.parameter
            s.param.parameter = lambda: dict(asli(), mesin="adgpu", perangkat="gpu", nrun_gpu=50)
            if s.env is not None:
                s.env.opencl_ok = True
            s.pelaksana.jobSelesai.connect(s.job_selesai)
            s.jalankan_docking()

        def job_selesai(s, jid):
            j = s.pelaksana.cari(jid)
            s.job = j
            print("JOB", jid, j["nama"], j["status"], [(l["nama"], l["status"], l["energi"], l.get("warhead"),
                                                      l.get("pesan")) for l in j["ligan"]], flush=True)
            QTimer.singleShot(500, s.l4)

        def l4(s):
            pr, j = s.proyek, s.job
            cek(bool(j.get("kovalen")) and "flex" not in j, f"job kovalen: {j.get('kovalen')}")
            nama = {l["nama"]: l for l in j["ligan"]}
            cek(set(nama) == {"sotorasib", "kloroasetamida"}, f"aspirin tidak masuk job: {sorted(nama)}")
            lg = nama.get("sotorasib", {})
            cek(lg.get("status") == "selesai", f"sotorasib selesai: {lg.get('energi')} ({lg.get('detik')} s)")
            cek(lg.get("ki") == "" and lg.get("le") is None, "Ki/LE dikosongkan untuk skor kovalen")
            cek(lg.get("rmsd_kristal_min") is not None and lg["rmsd_kristal_min"] < 2.0,
                f"RMSD kristal terbaik < 2 Å: pose 1 {lg.get('rmsd_kristal')} | min {lg.get('rmsd_kristal_min')}")
            cek(lg.get("interaksi") is not None, f"interaksi tersimpan: {lg.get('interaksi')}")
            lk = nama.get("kloroasetamida", {})
            cek(lk.get("status") == "selesai", f"kloroasetamida selesai: {lk.get('energi')} [{lk.get('warhead')}]")
            pose = M.baca_hasil("adgpu", pr.p(lg["keluaran"]))
            cek(M.residu_flex(pose[0].flex) == ["CYS12 A"], f"rantai samping di pose: {M.residu_flex(pose[0].flex)}")
            pdb = M.pose_ke_pdb(pose[0].pdbqt)
            berat = [b for b in pdb.splitlines() if b.startswith("HETATM") and b[76:78].strip() != "H"]
            cek(len(berat) == 41 and not any(b[76:78].strip() == "S" for b in berat),
                f"pose ligan {len(berat)} atom berat tanpa atom residu (kristal 41)")
            o = s.buka_pose(j["id"], lg["id"], 1)
            fo = [x for x in s.objek.values() if x.info.get("flex_pose") == 1 and x.grup == o.grup]
            cek(len(fo) == 1 and fo[0].tampil, "objek rantai samping Cys12 pose 1 tampil")
            cek(o.info.get("ki") == "", "info pose tanpa Ki")
            QTimer.singleShot(2500, s.l5)

        def l5(s, sisa=40):
            lg = next(l for l in s.job["ligan"] if l["nama"] == "sotorasib")
            q = lg.get("qc") or {}
            if not q and sisa:      # PoseBusters berjalan di proses pekerja
                QTimer.singleShot(500, lambda: s.l5(sisa - 1))
                return
            cek(bool(q) and q.get("kovalen") and q.get("lulus"),
                f"PoseBusters pose kovalen: {q.get('n_uji')} uji, gagal {q.get('gagal')}")

            ai = s._aktif_inter or {}
            res = sorted({h["residu"] for h in ai.get("daftar", [])})
            cek(len(res) >= 3, f"interaksi pose aktif: {res}")
            s.grab().save(str(OUT / "gui_pose_kovalen.png"))
            s.proyek.reseptor["kovalen"]["aktif"] = True
            s.proyek.reseptor.pop("kovalen")
            s._ringkasan()
            cek(s.param.l_kov.text() == "tidak", "kovalen dimatikan di panel")
            s.proyek.simpan()
            print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
try:
    A.main()
except SystemExit:
    pass
