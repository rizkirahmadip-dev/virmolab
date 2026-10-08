"""Ukur jeda event loop terbesar selama docking 20 ligan (AD-GPU) — kriteria 'UI tidak freeze'."""
import time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from virmodock.app import siapkan_kimia
siapkan_kimia()
from virmodock.core import antrean as A, molekul, prep_ligan as L
from virmodock.core.proyek import Proyek

app = QApplication([])
pr = Proyek.buka(sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1])
nama = ("quercetin kaempferol luteolin apigenin naringenin hesperetin curcumin resveratrol caffeine ibuprofen "
        "paracetamol oseltamivir nelfinavir saquinavir darunavir genistein daidzein chrysin baicalein myricetin").split()
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(6) as ex:
    objs = list(ex.map(lambda n: molekul.unduh_pubchem(n)[0], nama))
hasil = L.siapkan_banyak([(o.nama, o.teks, "sdf") for o in objs])
lig = []
for h in hasil:
    if h.status == "gagal":
        continue
    lid = pr.id_ligan_baru(h.nama)
    pr.p("ligan", "pdbqt", f"{lid}.pdbqt").write_text(h.pdbqt)
    d = {"id": lid, "nama": h.nama, "status": h.status, "pdbqt": f"ligan/pdbqt/{lid}.pdbqt"}
    pr.ligan.append(d)
    lig.append(d)
pl = A.Pelaksana()
pl.atur_proyek(pr)
jeda = {"maks": 0.0, "t": time.perf_counter(), "n": 0}


def detak():
    t = time.perf_counter()
    jeda["maks"] = max(jeda["maks"], t - jeda["t"])
    jeda["t"] = t
    jeda["n"] += 1


tm = QTimer()
tm.timeout.connect(detak)
tm.start(20)
mulai = time.perf_counter()
pl.jobSelesai.connect(lambda jid: (print(f"{len(lig)} ligan selesai dalam {time.perf_counter() - mulai:.1f} s; "
                                         f"jeda event loop terbesar {jeda['maks'] * 1000:.0f} ms "
                                         f"({jeda['n']} detak)", flush=True), app.quit()))
pl.tambah(A.job_baru(pr, lig, "adgpu", "gpu", {"nrun": 20, "heuristik": True, "seed": 1}, pr.kotak))
app.exec()
