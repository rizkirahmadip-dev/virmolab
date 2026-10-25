"""Uji GUI dialog Pasang alat lanjutan (WSL) dengan prasyarat WSL sungguhan dan skrip pemasang tiruan.

Prasyarat dibaca dari WSL di laptop ini. Skrip pemasangnya diganti skrip tiruan supaya uji tidak mengunduh apa pun:
(1) sukses: semua penanda langkah dicetak, kemajuan penuh, sinyal alatBerubah terpancar, jendela utama memperbarui
tombol Uni-Dock; (2) gagal: galat curl -> pesan internet, log terbuka; (3) Hentikan: bash tiruan yang tidur lama
benar-benar mati di dalam WSL (bukan hanya wsl.exe). Tangkapan terang dan gelap disimpan.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_alat_wsl_gui.py [--en]
Keluaran: dev/uji/alat_wsl/
"""
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))
BAHASA = "en" if "--en" in sys.argv else "id"
sys.argv = [sys.argv[0]]
OUT = AKAR / "dev" / "uji" / "alat_wsl"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
gagal = []


def cek(ok, pesan):
    print(("OK    " if ok else "GAGAL ") + pesan, flush=True)
    if not ok:
        gagal.append(pesan)


def _pengecualian(*info):
    # pengecualian di slot Qt tidak menghentikan loop peristiwa; tanpa ini uji menggantung sampai TIMEOUT
    traceback.print_exception(*info)
    print(f"\nGAGAL pengecualian: {info[1]}", flush=True)
    os._exit(1)


sys.excepthook = _pengecualian


from PySide6.QtCore import QSettings, Qt, QTimer                      # noqa: E402

st = QSettings("VirmoLab", "VirmoLab")
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")
st.setValue("bahasa", BAHASA)
st.remove("layout")
st.remove("sesi_terbuka")
DISTRO_LAMA = st.value("wsl_distro", "")

import virmolab.app as A_app                                        # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402
from virmolab.core import alat_wsl as A                             # noqa: E402

PENANDA = {k: [m for m, _l in p["langkah"]] for k, p in A.PAKET.items()}


def skrip_tiruan(jenis):
    def buat(kunci, lewati=()):
        baris = ['echo "VIRMOLAB_PID=$$"']
        if jenis == "sukses":
            for m in PENANDA[kunci]:
                baris += [f"echo {m}", "echo 'keluaran biasa paket'", "sleep 0.2"]
            baris.append("echo PAKET_SELESAI")
        elif jenis == "gagal":
            baris += [f"echo {PENANDA[kunci][0]}", "echo 'curl: (6) Could not resolve host: github.com' >&2", "exit 6"]
        else:  # lama: untuk Hentikan
            baris += ["echo UNDUH_MICROMAMBA", "sleep 300", "echo PAKET_SELESAI"]
        return ("\n".join(baris) + "\n").encode()
    return buat


def hidup_di_wsl(pid):
    return subprocess.run(A.argv_pasang("")[:-2] + ["kill", "-0", str(pid)], capture_output=True).returncode == 0


def hook():
    from virmolab.ui import mainwindow, theme
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1500, 920)
            s.d = None
            s.berubah = 0
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(600000, lambda: (cek(False, "TIMEOUT"), s.akhir()))

        def l1(s):
            s.d = s.buka_alat_wsl("gpu_rbfe")
            s.d.alatBerubah.connect(lambda: setattr(s, "berubah", s.berubah + 1))
            s._tunggu(lambda: s.d._pr is not None and s.d.b_periksa.isEnabled(), 90, s.l2, "prasyarat")

        def l2(s):
            pr = s.d._pr
            cek(pr.wsl_siap and pr.distro, f"prasyarat WSL terbaca ({pr.distro}, {len(pr.syarat)} syarat)")
            cek(s.d.grid.rowCount() >= len(pr.syarat), "tiap syarat tampil sebagai baris")
            cek(all(k["tombol"].isEnabled() for k in s.d.kartu.values()), "tombol Pasang kedua paket aktif")
            cek(all(k["status"].text() and "Memeriksa" not in k["status"].text() for k in s.d.kartu.values()),
                f"status alat terbaca ({[k['status'].text() for k in s.d.kartu.values()]})")
            if all(x.ok for x in pr.syarat):
                cek(not s.d.w_syarat.isVisible() and s.d.b_rincian.isVisible() and "✓" in s.d.l_ringkas.text(),
                    f"semua lulus: prasyarat diringkas satu baris ({s.d.l_ringkas.text()})")
                s.d.grab().save(str(OUT / f"awal_{BAHASA}.png"))
                s.d.b_rincian.click()
                QApplication.processEvents()
                cek(s.d.w_syarat.isVisible(), "Tampilkan rincian membuka daftar prasyarat")
                s.d.grab().save(str(OUT / f"rincian_{BAHASA}.png"))
                s.d.b_rincian.click()
            else:
                perlu = [x.judul for x in pr.syarat if not x.ok]
                cek(s.d.w_syarat.isVisible() and not s.d.b_rincian.isVisible(),
                    f"ada prasyarat belum lulus {perlu}: daftar terbuka sendiri ({s.d.l_ringkas.text()})")
                s.d.grab().save(str(OUT / f"awal_{BAHASA}.png"))
            A.skrip_paket = skrip_tiruan("sukses")
            s.d.kartu["gpu_rbfe"]["tombol"].click()
            cek(s.d._proc is not None and not s.d.kartu["cofolding"]["tombol"].isEnabled(),
                "selama memasang, tombol lain mati")
            # dua tunggu terpisah: proses tiruan (cepat) lalu pemeriksaan ulang status (lambat bila WSL sedang sibuk)
            s._tunggu(lambda: s.d._proc is None, 60,
                      lambda: s._tunggu(lambda: s.d.b_periksa.isEnabled(), 180, s.l3, "periksa ulang"),
                      "pemasangan tiruan sukses")

        def l3(s):
            n = len(PENANDA["gpu_rbfe"])
            cek(s.d.daftar_langkah.count() == n, f"daftar langkah berisi {n} baris ({s.d.daftar_langkah.count()})")
            cek(s.d.pb.value() == s.d.pb.maximum() == n, f"kemajuan penuh ({s.d.pb.value()}/{s.d.pb.maximum()})")
            cek(all(s.d.daftar_langkah.item(i).data(Qt.UserRole) == "selesai" for i in range(n)),
                "semua langkah dicentang")
            cek(s.berubah == 1, "sinyal alatBerubah terpancar sekali")
            cek(s.d._pid is not None and "VIRMOLAB_PID" not in s.d.t_log.toPlainText(), "PID terbaca, tidak masuk log")
            log = A.berkas_log("gpu_rbfe").read_text(encoding="utf-8")
            cek("PAKET_SELESAI" in log and "keluaran biasa paket" in log, "log ditulis ke data/log")
            s.d.grab().save(str(OUT / f"sukses_{BAHASA}.png"))
            A.skrip_paket = skrip_tiruan("gagal")
            s.d.kartu["cofolding"]["tombol"].click()
            s._tunggu(lambda: s.d._proc is None, 60,
                      lambda: s._tunggu(lambda: s.d.b_periksa.isEnabled(), 180, s.l4, "periksa ulang"),
                      "pemasangan tiruan gagal")

        def l4(s):
            teks = s.d.l_langkah.text()
            cek(("internet" in teks.lower()) and s.d.t_log.isVisible(), f"gagal curl: pesan internet + log terbuka ({teks})")
            keadaan = [s.d.daftar_langkah.item(i).data(Qt.UserRole) for i in range(s.d.daftar_langkah.count())]
            cek(keadaan[:1] == ["gagal"] and set(keadaan[1:]) == {"tunggu"}, f"langkah yang gagal ditandai ({keadaan})")
            cek(s.berubah == 1, "gagal tidak memancarkan alatBerubah")
            cek("log" in s.d.l_status.text().lower() and s.d.l_status.contentsMargins().left() > 0,
                f"jalur log tetap tampil sesudah periksa ulang, label peringatan berpadding ({s.d.l_status.text()})")
            s.d.grab().save(str(OUT / f"gagal_{BAHASA}.png"))
            A.skrip_paket = skrip_tiruan("lama")
            s.d.kartu["gpu_rbfe"]["tombol"].click()
            s._tunggu(lambda: s.d._pid is not None, 60, s.l5, "PID bash tiruan")

        def l5(s):
            s.pid = s.d._pid
            cek(hidup_di_wsl(s.pid), f"bash tiruan berjalan di WSL (pid {s.pid})")
            s.t_henti = time.time()
            s.d.b_henti.click()
            s._tunggu(lambda: s.d._proc is None, 30, s.l5b, "proses berhenti")

        def l5b(s):
            cek(time.time() - s.t_henti < 5, f"Hentikan cepat: proses berhenti dalam {time.time() - s.t_henti:.1f} s")
            s._tunggu(lambda: s.d.b_periksa.isEnabled(), 180, s.l6, "periksa ulang sesudah berhenti")

        def l6(s):
            for _ in range(20):                    # perintah penghenti asinkron: beri waktu sampai bash mati
                if not hidup_di_wsl(s.pid):
                    break
                time.sleep(0.5)
            cek(not hidup_di_wsl(s.pid), "bash di dalam WSL ikut mati (bukan hanya wsl.exe)")
            cek("dihentikan" in s.d.l_langkah.text().lower() or "stopped" in s.d.l_langkah.text().lower(),
                f"pesan dihentikan ({s.d.l_langkah.text()})")
            app = QApplication.instance()
            app.setPalette(theme.palet("gelap"))
            app.setStyleSheet(theme.qss_berikon("gelap", __import__("virmolab.core.paths", fromlist=["x"]).APPDATA))
            QTimer.singleShot(900, lambda: (s.d.grab().save(str(OUT / f"gelap_{BAHASA}.png")), s.akhir()))

        def _tunggu(s, syarat, detik, lanjut, nama, _m=[0]):
            if not _m[0]:
                _m[0] = time.time()
            if syarat():
                _m[0] = 0
                QTimer.singleShot(200, lanjut)
            elif time.time() - _m[0] > detik:
                cek(False, f"menunggu {nama} > {detik} s")
                s.akhir()
            else:
                QTimer.singleShot(300, lambda: s._tunggu(syarat, detik, lanjut, nama))

        def akhir(s):
            print("\n" + ("LULUS" if not gagal else f"GAGAL {len(gagal)}: " + "; ".join(gagal)), flush=True)
            st2 = QSettings("VirmoLab", "VirmoLab")
            st2.setValue("bahasa", "id")
            if DISTRO_LAMA:
                st2.setValue("wsl_distro", DISTRO_LAMA)
            else:
                st2.remove("wsl_distro")
            QApplication.quit()
            os._exit(1 if gagal else 0)

    mainwindow.JendelaUtama = Uji


from virmolab import i18n                                           # noqa: E402
_pasang_asli = i18n.pasang


def _pasang_lalu_hook(app):
    _pasang_asli(app)
    hook()


i18n.pasang = _pasang_lalu_hook
A_app.main()
