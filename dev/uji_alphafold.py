"""Uji AlphaFold DB (0.9.3, butuh internet): dialog cari UniProt -> impor CA2 (P00918) -> pewarnaan pLDDT,
info Properti -> P2Rank konfigurasi 'alphafold' -> grid box -> cek pLDDT kotak; ACE2 (Q9BYF1) ujung C dipangkas.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_alphafold.py
Keluaran: dev/uji/alphafold/ (gui_*.png = grab jendela VirmoLab saja).
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
OUT = Path("dev/uji/alphafold").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True, exist_ok=True)

import virmolab.app as A
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[2] if len(a) > 2 else a, flush=True))
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def hook():
    from virmolab.core import alphafold
    from virmolab.core.proyek import Proyek
    from virmolab.ui import mainwindow
    from virmolab.ui.dialogs import DialogAmbil

    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(300000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _galat(s, t):
            print("GALAT:", t, flush=True)
            gagal.append(t)

        def l1(s):
            s._set_proyek(Proyek.baru(OUT, "uji_af"))
            s.d = DialogAmbil(s, 3)
            s.d.resize(640, 520)
            s.d.show()
            s.d.af_kueri.setText("carbonic anhydrase 2")
            s.d._af_cari()
            QTimer.singleShot(500, s.l2)

        def l2(s, n=[0]):
            n[0] += 1
            if not s.d.af_daftar.count() and n[0] < 60:
                QTimer.singleShot(500, s.l2)
                return
            teks = [s.d.af_daftar.item(i).text() for i in range(s.d.af_daftar.count())]
            cek(any("P00918" in t for t in teks), f"cari UniProt: {len(teks)} hasil, P00918 ada")
            for i, t in enumerate(teks):
                if "P00918" in t:
                    s.d.af_daftar.setCurrentRow(i)
            QApplication.processEvents()
            s.d.grab().save(str(OUT / "dialog_alphafold.png"))
            req = s.d.permintaan()
            cek(req and req[0] == "alphafold" and req[1] == ["P00918"] and req[2]["pangkas_aktif"],
                f"permintaan dialog: {req}")
            s.d.reject()
            objs, _teks, meta = alphafold.unduh("P00918", **req[2])
            s._objek_unduhan(objs)
            p = next(o for o in s.objek.values() if o.jenis == "protein")
            cek(p.gaya["warna"]["mode"] == "plddt" and p.info["plddt"] > 90, f"CA2 pLDDT {p.info['plddt']}, warna plddt")
            s.pilih_objek(p.id)
            QTimer.singleShot(3000, s.l3)

        def l3(s):
            s.grab().save(str(OUT / "gui_ca2_plddt.png"))
            s.deteksi_kantong()
            s._kantong_asli = s._kantong_siap
            s._kantong_siap = s.kantong_uji
            QTimer.singleShot(90000, lambda: (print("TIMEOUT P2Rank"), QApplication.quit()))

        def kantong_uji(s, o, k):
            cek(bool(k), f"P2Rank {len(k)} kantong; #1 skor {k[0]['skor']:.1f}" if k else "P2Rank kosong")
            res = {f"{c}{i}" for c, i in k[0]["residu"]} if k else set()
            cek({"A199", "A200"} <= res, "kantong #1 memuat Thr199/Thr200 (situs aktif CA2)")
            s._atur_kotak(k[0]["pusat"], (20, 20, 20), sumber="uji kantong #1")
            log = s.log.toPlainText() if hasattr(s.log, "toPlainText") else ""
            print("log pLDDT kotak:", [b for b in log.splitlines() if "pLDDT di grid box" in b][-1:], flush=True)
            # ACE2: ujung C tak beraturan dipangkas
            _o, _t, meta = alphafold.unduh("Q9BYF1")
            cek(meta["n_dibuang"] > 0 and "805" in meta["dibuang"], f"ACE2 dipangkas: {meta['dibuang']}")
            h = alphafold.plddt_di_kotak(next(x for x in _o if x.jenis == "protein").teks, (0, 0, 0), (500, 500, 500))
            cek(h is not None and h[0] > 85, f"ACE2 pLDDT setelah pangkas {h}")
            s.grab().save(str(OUT / "gui_ca2_kantong.png"))
            print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


hook()
try:
    A.main()
except SystemExit:
    pass
