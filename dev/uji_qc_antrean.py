"""Uji QC PoseBusters otomatis di antrean: salinan proyek 1HSG -> job AD-GPU -> qcSelesai per ligan -> tersimpan.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_qc_antrean.py
"""
import shutil
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer

from virmolab.core import antrean as A
from virmolab.core import proyek as P

app = QCoreApplication([])
SUMBER = sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1]
TUJUAN = Path("dev/uji/qc/antrean.vmd").resolve()
shutil.rmtree(TUJUAN, ignore_errors=True)
shutil.copytree(SUMBER, TUJUAN)
pr = P.Proyek.buka(TUJUAN)
lig = pr.ligan_siap()
print("ligan:", [l["nama"] for l in lig], "kotak:", pr.kotak)
pl = A.Pelaksana()
pl.atur_proyek(pr)
pl.pesan.connect(lambda s: print("PESAN", s))
pl.perluSimpan.connect(pr.simpan)
qc_masuk = []
jeda = []          # jeda terpanjang event loop (responsif?)
t_akhir = [time.perf_counter()]


def detak():
    t = time.perf_counter()
    jeda.append(t - t_akhir[0])
    t_akhir[0] = t


tm = QTimer()
tm.setInterval(20)
tm.timeout.connect(detak)
tm.start()


def qc(jid, lid, h):
    qc_masuk.append(lid)
    print(f"QC {lid}: {'lulus' if h.get('lulus') else h.get('gagal') or h.get('galat')}", flush=True)


def selesai(jid):
    print("JOB selesai", jid, flush=True)


def cek():
    j = pl.cari(jid)
    if j and j["status"] == "selesai" and len(qc_masuk) >= sum(1 for l in j["ligan"] if l["status"] == "selesai"):
        app.quit()


pl.qcSelesai.connect(qc)
pl.jobSelesai.connect(selesai)
t = QTimer()
t.timeout.connect(cek)
t.start(500)
job = A.job_baru(pr, lig, "adgpu", "gpu", {"nrun": 10}, pr.kotak)
jid = job["id"]
pl.tambah(job)
QTimer.singleShot(240000, lambda: (print("TIMEOUT"), app.quit()))
app.exec()
pr.simpan()
pr2 = P.Proyek.buka(TUJUAN)
j2 = next(j for j in pr2.job if j["id"] == jid)
print("tersimpan:", [(l["nama"], (l.get("qc") or {}).get("lulus")) for l in j2["ligan"]])
print(f"jeda event loop terbesar: {max(jeda) * 1000:.0f} ms")
assert all(l.get("qc") for l in j2["ligan"] if l["status"] == "selesai")
print("OK")
