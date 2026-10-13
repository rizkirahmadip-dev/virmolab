"""Uji GUI MD & MM/GBSA (0.9.4): salinan proyek uji flexres -> dialog MD -> ukur kecepatan otomatis -> Ringan
(MM/GBSA, termasuk pose residu fleksibel) -> kolom Hasil -> Sedang 0,2 ns dengan jeda + lanjut -> grafik.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_md_gui.py
Butuh: dev/uji/fleksibel/uji_flex.vmd (dibuat dev/uji_fleksibel.py). Keluaran: dev/uji/md_gui/.
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
st.remove("md/kecepatan")
SUMBER = Path("dev/uji/fleksibel/uji_flex.vmd").resolve()
OUT = Path("dev/uji/md_gui").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
PROYEK = OUT / "proyek_md.vmd"
shutil.copytree(SUMBER, PROYEK)

import virmolab.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def hook():
    from virmolab.ui import mainwindow

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

        def tunggu(s, kondisi, lalu, batas=600, _n=[0]):
            if kondisi():
                _n[0] = 0
                lalu()
                return
            _n[0] += 1
            if _n[0] > batas * 2:
                print("TIMEOUT menunggu", flush=True)
                QApplication.quit()
                return
            QTimer.singleShot(500, lambda: s.tunggu(kondisi, lalu, batas))

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(2000, s.l2)

        def l2(s):
            s.buka_md()
            s.d = s._dlg_md
            s.d.resize(1280, 860)
            cek(s.d.tabel.rowCount() == 4, f"dialog: {s.d.tabel.rowCount()} baris ligan (3 job)")
            # pengukuran kecepatan otomatis saat dibuka
            s.tunggu(lambda: s.d.proses is None and s.d.kecepatan, s.l3)

        def l3(s):
            k = s.d.kecepatan
            cek(k and k["implisit"] > 0 and k["eksplisit"] > 0, f"kecepatan terukur: {k}")
            cek(all(s.d.l_est[t].text() != "belum diukur" for t in ("ringan", "sedang", "lengkap")),
                "perkiraan waktu: " + ", ".join(s.d.l_est[t].text() for t in ("ringan", "sedang", "lengkap")))
            s.d.grab().save(str(OUT / "dialog_awal.png"))
            # Ringan: MK1 (job flex AD-GPU) + aspirin (job flex) + MK1 (job kaku)
            s.d._pilih(-1)
            s.d.grp.button(0).setChecked(True)
            s.d._mulai(None)
            s.tunggu(lambda: s.d.proses is None, s.l4)

        def l4(s):
            h = s.d.hasil or {}
            L = [x for x in h.get("ligan", []) if x.get("selesai")]
            cek(len(L) == 4, f"Ringan: {len(L)}/4 ligan selesai; galat: {[x.get('galat') for x in h.get('ligan', []) if x.get('galat')]}")
            for x in L:
                print(f"   {x['nama']} {x['job']}: dock {x['energi_docking']:.2f} -> MM/GBSA {x['mmgbsa_min']['dG']:.2f}", flush=True)
            from virmolab.core import ekspor
            b = ekspor.baris_hasil(s.proyek)
            cek(all(x.get("mmgbsa") is not None for x in b), "kolom MM/GBSA terisi di baris Hasil")
            s.tab_tengah.setCurrentWidget(s.hasil)
            QApplication.processEvents()
            s.grab().save(str(OUT / "gui_hasil_mmgbsa.png"))
            s.d.grab().save(str(OUT / "dialog_ringan.png"))
            # Sedang: MD implisit singkat untuk MK1 (job kaku) -> jeda -> lanjut
            s.d._pilih(0)
            from PySide6.QtCore import Qt
            kaku = {j["id"] for j in s.proyek.job if not j.get("flex")}      # job reseptor kaku (ID berubah tiap uji)
            n = 0
            for r in range(s.d.tabel.rowCount()):
                it = s.d.tabel.item(r, 0)
                if it.text() == "MK1" and s.d.baris[r]["job"] in kaku and not n:
                    it.setCheckState(Qt.Checked)
                    n += 1
            cek(n == 1, "Sedang: MK1 job kaku dipilih")
            s.d.grp.button(1).setChecked(True)
            s.d.sp_ns_i.setValue(0.1)
            s.d.sp_interval.setValue(2)
            s.d.sp_frame.setValue(10)
            s.d.sp_ns_i.setValue(0.2)
            s.d._mulai(None)
            # jeda saat produksi benar-benar berjalan (bukan pengatur waktu tetap: kecepatan GPU bervariasi)
            s.tunggu(lambda: "Produksi" in s.d.l_status.text() or s.d.proses is None,
                     lambda: (s.d.jeda(), s.tunggu(lambda: s.d.proses is None, s.l5)))

        def l5(s):
            cek(s.d.run and s.d.run.get("status") == "dijeda" and s.d.b_lanjut.isEnabled(),
                f"jeda: status {s.d.run and s.d.run.get('status')}")
            s.d.lanjutkan()
            s.tunggu(lambda: s.d.proses is None, s.l6)

        def l6(s):
            h = s.d.hasil or {}
            x = next((y for y in h.get("ligan", []) if y.get("selesai")), {})
            tr = x.get("trajektori") or {}
            cek(x.get("mmgbsa") and len(tr.get("rmsd_ligan", [])) == 100,
                f"Sedang selesai setelah lanjut: frame {len(tr.get('rmsd_ligan', []))}, MM/GBSA {x.get('mmgbsa', {}).get('dG')}")
            cek(any(r.get("status") == "selesai" and r.get("tingkat") == "sedang" for r in s.proyek.md), "riwayat MD di proyek")
            for i, kunci in enumerate(("rmsd", "rmsf", "energi")):
                s.d.tab.setCurrentIndex(i + 1)
                QApplication.processEvents()
                s.d.grab().save(str(OUT / f"dialog_{kunci}.png"))
            s.d.tab.setCurrentIndex(4)
            QApplication.processEvents()
            s.d.grab().save(str(OUT / "dialog_interaksi.png"))
            s.proyek.simpan()
            print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
try:
    A.main()
except SystemExit:
    pass
