"""Uji GUI 0.9.5 (offline): templat + proyek contoh HIV-1 protease, urungkan/ulangi (grid box & gaya), palet perintah,
tur aplikasi, mode Ahli/Pemula, paket Supplementary, paket Lapor masalah.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_095_gui.py
Keluaran: dev/uji/v095/ (gui_*.png = grab jendela VirmoDock saja). Butuh dev/uji/md_gui/proyek_md.vmd untuk
uji Supplementary (dibuat dev/uji_md_gui.py); bila tidak ada, bagian itu dilewati.
"""
import shutil
import sys
import zipfile
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
st.setValue("tema", "terang")
st.remove("layout")
st.remove("sesi_terbuka")
st.setValue("mode_pengguna", "pemula")
OUT = Path("dev/uji/v095").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
st.setValue("folder_kerja", str(OUT))
SUPP = Path("dev/uji/md_gui/proyek_md.vmd").resolve()

import virmodock.app as A
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(OUT / Path(a[2]).name) if len(a) > 2 else "", ""))
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def hook():
    from virmodock.ui import dialog_templat, mainwindow

    def exec_templat(self):
        self.show()
        QApplication.processEvents()
        self.grab().save(str(OUT / "dialog_templat.png"))
        from virmodock.core import templat as Tm
        cek(self.daftar.count() == len(Tm.TEMPLAT), f"templat: {self.daftar.count()} pilihan")
        self.daftar.setCurrentRow(0)
        return 1
    dialog_templat.DialogTemplat.exec = exec_templat

    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(3500, s.l1)
            QTimer.singleShot(400000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _galat(s, t):
            print("GALAT:", t, flush=True)
            gagal.append(t)

        def tunggu(s, kondisi, lalu, n=[0]):
            n[0] += 1
            if kondisi() or n[0] > 240:
                n[0] = 0
                lalu()
            else:
                QTimer.singleShot(500, lambda: s.tunggu(kondisi, lalu))

        def l1(s):
            s.grab().save(str(OUT / "gui_sambutan.png"))
            s.proyek_templat()
            s.tunggu(lambda: sum(1 for o in s.objek.values() if o.jenis == "ligan" and not o.info.get("ligan_asli")) >= 10,
                     s.l2)

        def l2(s):
            lig = [o.nama for o in s.objek.values() if o.jenis == "ligan" and not o.info.get("ligan_asli")]
            cek(s.proyek and s.proyek.templat == "contoh", f"proyek contoh dibuat: {s.proyek and s.proyek.nama}")
            cek(any(o.jenis == "protein" for o in s.objek.values()) and len(lig) >= 10,
                f"1HSG + {len(lig)} ligan dimuat: {', '.join(sorted(lig))[:120]}")
            cek(bool(s.box.get("pusat")), "grid box otomatis di MK1")
            cek("Templat: Contoh" in s.pesan.toPlainText(), "langkah templat di panel Pesan")
            s.grab().save(str(OUT / "gui_contoh.png"))
            # urungkan / ulangi grid box
            awal = list(s.box["pusat"])
            s._atur_kotak([awal[0] + 5, awal[1], awal[2]], sumber="uji geser")
            s.urungkan()
            cek([round(v, 3) for v in s.box["pusat"]] == [round(v, 3) for v in awal], "urungkan grid box")
            s.ulangi()
            cek(abs(s.box["pusat"][0] - (awal[0] + 5)) < 1e-6, "ulangi grid box")
            s.urungkan()
            # urungkan gaya
            p = next(o for o in s.objek.values() if o.jenis == "protein")
            lama = dict(p.gaya)
            g = dict(p.gaya, reps=["surface"])
            s.ubah_gaya(p.id, g)
            s.urungkan()
            cek(p.gaya.get("reps") == lama.get("reps"), f"urungkan gaya tampilan: {p.gaya.get('reps')}")
            # palet perintah
            from virmodock.ui.palet import DialogPalet
            d = DialogPalet(s)
            d.show()
            d.kotak.setText("siapkan reseptor")
            QApplication.processEvents()
            teks = [d.daftar.item(i).text() for i in range(d.daftar.count())]
            cek(bool(teks) and "Siapkan reseptor" in teks[0], f"palet: '{teks[0] if teks else '-'}' ({len(d.aksi)} perintah)")
            d.grab().save(str(OUT / "palet.png"))
            d.close()
            # mode Ahli / Pemula
            s.atur_mode_pengguna("ahli")
            QApplication.processEvents()
            cek(not s.d_langkah.isVisible() and s.param.b_lanjutan.isChecked(), "mode Ahli")
            s.atur_mode_pengguna("pemula")
            QApplication.processEvents()
            cek(s.d_langkah.isVisible(), "mode Pemula")
            # tur
            s.tur()
            QTimer.singleShot(800, s.l3)

        def l3(s):
            t = getattr(s, "_tur", None)
            cek(t is not None and t.isVisible(), "tur tampil")
            n = len(t.langkah)
            for i in range(n):
                t.ke(i)
                QApplication.processEvents()
                if i in (1, 3, 5):
                    s.grab().save(str(OUT / f"gui_tur_{i + 1}.png"))
            t.ke(n)
            QApplication.processEvents()
            cek(not t.isVisible(), f"tur {n} langkah lalu tertutup")
            # lapor masalah: paket zip
            from virmodock.ui.dialog_bantuan import DialogLapor
            dl = DialogLapor("uji", s.env, s)
            dl.simpan_zip()
            z = sorted(OUT.glob("laporan_VirmoDock_*.zip"))
            cek(bool(z) and "laporan.txt" in zipfile.ZipFile(z[-1]).namelist(), f"paket lapor masalah: {z[-1].name if z else '-'}")
            # Supplementary dari proyek uji MD
            if SUPP.exists():
                s.buka_proyek(str(SUPP))
                QTimer.singleShot(2500, s.l4)
            else:
                print("LEWAT: proyek uji MD tidak ada", flush=True)
                s.l5()

        def l4(s):
            s._ekspor_paket({"n_kompleks": 5})
            s.tunggu(lambda: any(OUT.glob("*_supplementary.zip")) and not s.s_prog.text(), s.l5)

        def l5(s):
            z = sorted(OUT.glob("*_supplementary.zip"))
            if SUPP.exists():
                nm = zipfile.ZipFile(z[-1]).namelist() if z else []
                cek(any(n.endswith("pose/terbaik.sdf") for n in nm) and any(n.endswith("SHA256SUMS.txt") for n in nm),
                    f"paket Supplementary: {len(nm)} berkas")
            print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
try:
    A.main()
except SystemExit:
    pass
