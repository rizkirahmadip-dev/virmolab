"""Uji GUI penapisan bertahap (pembelajaran aktif) dari awal sampai akhir dengan docking sungguhan.

Alur: impor 1HSG -> siapkan reseptor -> kotak di MK1 -> pustaka 600 senyawa Enamine (MolPAL) + MK1 -> kampanye
60 + 2 x 60 ligan (docking Uni-Dock bila ada di WSL, selain itu Vina exhaustiveness 2) -> tangkap layar dialog
(terang & gelap) -> buka ulang proyek: kampanye, skor, dan pengecualian ligan AL dari docking biasa tetap benar.

  PYTHONPATH=. .venv/Scripts/python.exe dev/uji_al_gui.py            (VD_MESIN=vina untuk memaksa Vina)
Keluaran: dev/uji/al/*.png
"""
import csv
import gzip
import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
AKAR = Path(__file__).resolve().parents[1]
KERJA = (AKAR / "dev" / "uji" / "kerja_al").resolve()
KELUAR = AKAR / "dev" / "uji" / "al"
shutil.rmtree(KERJA, ignore_errors=True)
KERJA.mkdir(parents=True)
KELUAR.mkdir(parents=True, exist_ok=True)
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")
st.setValue("folder_kerja", str(KERJA))
st.remove("layout")
st.remove("sesi_terbuka")

import virmolab.app as A                                     # noqa: E402
from PySide6.QtWidgets import QApplication                  # noqa: E402

MK1 = "CC(C)(C)NC(=O)[C@@H]1CN(Cc2cccnc2)CCN1C[C@@H](O)C[C@@H](Cc1ccccc1)C(=O)N[C@H]1c2ccccc2C[C@H]1O"
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def tulis_pustaka():
    f = KERJA / "pustaka_uji.csv"
    with gzip.open("C:/VirmoLab-tolok-ukur/unduhan/Enamine10k_scores.csv.gz", "rt", encoding="utf-8") as g:
        baris = list(csv.DictReader(g))[::17][:600]
    with open(f, "w", encoding="utf-8", newline="") as o:
        w = csv.writer(o)
        w.writerow(["smiles", "id"])
        w.writerow([MK1, "MK1_indinavir"])
        w.writerow(["CCO.Cl", "garam_uji"])
        w.writerow(["bukan_smiles", "rusak_uji"])
        for i, b in enumerate(baris):
            w.writerow([b["smiles"], f"EN{i:04d}"])
    return f


def hook():
    from virmolab.core import prep_reseptor, unidock
    from virmolab.ui import kerja, mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            s.d_al = None
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(3 * 3600 * 1000, lambda: (print("TIMEOUT"), s.akhir()))

        def l1(s, n=0):
            if n == 0:
                s.impor([str((AKAR / "dev" / "uji" / "1HSG.pdb").resolve())])
            ada = any(o.jenis == "protein" for o in s.objek.values())
            if ada:
                QTimer.singleShot(500, s.l2)
            elif n > 60:
                print("GAGAL protein tidak termuat", flush=True)
                s.akhir()
            else:
                QTimer.singleShot(1000, lambda: s.l1(n + 1))

        def l2(s):
            prot = next(o for o in s.objek.values() if o.jenis == "protein")
            opsi = prep_reseptor.OpsiReseptor()
            kerja.jalankan(prep_reseptor.siapkan, prot.teks, opsi,
                           selesai=lambda h: (s._reseptor_siap(prot, h, opsi), QTimer.singleShot(800, s.l3)),
                           galat=lambda g: (print("GALAT reseptor", g), s.akhir()))

        def l3(s):
            s.aksi_kotak("ligan_asli")
            ud = os.environ.get("VD_MESIN", "") != "vina" and unidock.status(segar=True)["ada"]
            if ud:
                s.param.atur_unidock(True)
                s.param.set_parameter({"mesin": "unidock", "perangkat": "gpu", "unidock_mode": "balance"})
            else:
                s.param.set_parameter({"mesin": "vina", "perangkat": "cpu", "exhaustiveness": 2})
            s._param_berubah(s.param.parameter())
            print("mesin:", s.param.parameter()["mesin"], "kotak:", s.box, flush=True)
            s.d_al = s.buka_pembelajaran_aktif()
            d = s.d_al
            d.resize(1240, 760)
            from virmolab.core import pembelajaran_aktif as PA
            f = tulis_pustaka()
            d.e_berkas.setText(str(f))
            d._sumber_teks = f.name
            pus = PA.siapkan_pustaka(PA.baca_entri(f))
            d._pustaka_siap(pus)
            cek(len(pus) == 602 and pus.ringkasan["tidak_valid"] == 1 and pus.ringkasan["garam"] == 1,
                f"pustaka: 602 unik, 1 tidak valid, 1 garam ({pus.ringkasan})")
            cek("602" in d.l_pustaka.text(), "ringkasan pustaka tampil: " + d.l_pustaka.text())
            d.sp_awal.setValue(60)
            d.sp_batch.setValue(60)
            d.sp_putaran.setValue(2)
            cek(d.b_mulai.isEnabled(), "tombol Mulai aktif (reseptor + kotak + pustaka siap)")
            cek("180" in d.l_rencana.text(), "rencana menyebut 180 senyawa: " + d.l_rencana.text())
            QApplication.processEvents()
            d.grab().save(str(KELUAR / "al_siap_terang.png"))
            s.pengendali_al.berubah.connect(s.pantau)
            d._mulai()

        def pantau(s, cid):
            st_ = s.pengendali_al.status(cid)
            kp = s.pengendali_al.kampanye(cid)
            if kp is not None:
                print(f"[{st_}] tahap='{s.pengendali_al.tahap(cid)}' putaran={len(kp.putaran)} skor={len(kp.skor)}",
                      flush=True)
            n_skor = len(kp.skor) if kp is not None else 0
            if st_ == "selesai" and n_skor >= 180 and not getattr(s, "_sudah", False):
                s._sudah = True
                QTimer.singleShot(1500, lambda: s.l4(cid))

        def l4(s, cid):
            d = s.d_al
            kp = s.pengendali_al.kampanye(cid)
            rp = kp.ringkasan_putaran(100)
            cek(len(kp.putaran) == 3, f"3 putaran (0 acak + 2 model), tercatat {len(kp.putaran)}")
            cek(len(kp.skor) >= 170, f"≥ 170 senyawa punya skor/status ({len(kp.skor)})")
            ok = [x for x in kp.skor.values() if x is not None]
            cek(len(ok) >= 150, f"≥ 150 docking berhasil ({len(ok)})")
            cek(all(x["mutu"] for x in rp[1:]), "mutu prediksi prospektif dihitung tiap putaran model")
            print("ringkasan putaran:", [(x["ke"], x["metode"], x["terbaik"], round(x["rata_top"] or 0, 2),
                                          x["mutu"].get("rho")) for x in rp], flush=True)
            # rata-rata putaran model vs putaran acak (skor lebih negatif = lebih baik)
            import numpy as np
            rata = [np.mean([kp.skor[i] for i in p["indeks"] if kp.skor.get(i) is not None]) for p in kp.putaran]
            print("rata-rata ΔG per putaran:", [round(float(r), 2) for r in rata], flush=True)
            # Pustaka uji hanya 600 senyawa dan batch awal 60: model belum bisa belajar banyak, jadi yang diperiksa
            # hanya bahwa putaran model tidak membuat ΔG terbaik memburuk (uji skala sebenarnya: dev/tolok_ukur_al.py).
            cek(rp[-1]["terbaik"] <= rp[0]["terbaik"] + 1e-9,
                f"ΔG terbaik tidak memburuk setelah putaran model ({rp[-1]['terbaik']} <= {rp[0]['terbaik']})")
            e = s.pengendali_al.cari(cid)
            cek(len(e.get("pose") or {}) >= 150, f"tautan pose tersimpan ({len(e.get('pose') or {})})")
            cek(all(l.get("al") != cid for l in s.proyek.ligan_siap()), "ligan AL tidak ikut ligan_siap() biasa")
            cek(len([l for l in s.proyek.ligan_siap(al=True) if l.get("al") == cid]) >= 150, "ligan AL ada di al=True")
            d.tab.setCurrentIndex(0)
            QApplication.processEvents()
            d.grab().save(str(KELUAR / "al_putaran_terang.png"))
            d.tab.setCurrentIndex(1)
            QApplication.processEvents()
            cek(d.t_peringkat.rowCount() >= 150, f"tabel peringkat terisi ({d.t_peringkat.rowCount()})")
            d.grab().save(str(KELUAR / "al_peringkat_terang.png"))
            # buka pose peringkat 1
            it = d.t_peringkat.item(0, 1)
            n_obj = len(s.objek)
            d._buka_pose(it)
            cek(len(s.objek) > n_obj, "klik dua kali peringkat membuka pose di viewer")
            # prediksi kandidat
            d._hitung_prediksi()
            s._tunggu_prediksi(cid, 0)

        def _tunggu_prediksi(s, cid, n):
            """Prediksi berjalan di thread latar; tunggu sampai tabelnya terisi (maks ±90 detik)."""
            if s.d_al.t_prediksi.rowCount() > 0 or n > 45:
                s.l5(cid)
            else:
                QTimer.singleShot(2000, lambda: s._tunggu_prediksi(cid, n + 1))

        def l5(s, cid):
            d = s.d_al
            cek(d.t_prediksi.rowCount() == 200, f"tabel prediksi 200 kandidat ({d.t_prediksi.rowCount()})")
            d.grab().save(str(KELUAR / "al_prediksi_terang.png"))
            teks_id = __import__("virmolab.core.pembelajaran_aktif", fromlist=["x"]).teks_metode(
                s.pengendali_al.kampanye(cid), "Uni-Dock", s.pengendali_al.cari(cid)["ringkasan_pustaka"])
            print("METODE:", teks_id, flush=True)
            s.terapkan_tema("gelap")
            for _ in range(6):
                QApplication.processEvents()
            d.tab.setCurrentIndex(0)
            d._tampilkan()
            QTimer.singleShot(1500, lambda: s.l6(cid))

        def l6(s, cid):
            d = s.d_al
            d.grab().save(str(KELUAR / "al_putaran_gelap.png"))
            d.tab.setCurrentIndex(1)
            QApplication.processEvents()
            d.grab().save(str(KELUAR / "al_peringkat_gelap.png"))
            s.terapkan_tema("terang")
            d.close()
            folder = s.proyek.folder
            n_skor = len(s.pengendali_al.kampanye(cid).skor)
            s._simpan_diam()
            s.buka_proyek(str(folder))
            QTimer.singleShot(3000, lambda: s.l7(cid, n_skor))

        def l7(s, cid, n_skor):
            e = s.pengendali_al.cari(cid)
            cek(e is not None, "kampanye ada setelah proyek dibuka ulang")
            kp = s.pengendali_al.kampanye(cid)
            cek(kp is not None and len(kp.skor) == n_skor, f"skor kampanye utuh ({len(kp.skor) if kp else 0}/{n_skor})")
            cek(s.pengendali_al.status(cid) == "selesai", f"status selesai ({s.pengendali_al.status(cid)})")
            d = s.buka_pembelajaran_aktif()
            d.resize(1240, 760)
            QTimer.singleShot(6000, lambda: (d.grab().save(str(KELUAR / "al_buka_ulang.png")),
                                             cek(d.t_peringkat.rowCount() >= 150 and
                                                 d.t_peringkat.item(0, 5).text() not in ("", "–"),
                                                 "peringkat & SMILES tampil setelah buka ulang (pustaka dimuat latar)"),
                                             s.akhir()))

        def akhir(s):
            print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
            for g in gagal:
                print("  -", g)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
