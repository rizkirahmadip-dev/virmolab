"""Uji core/qc.py (PoseBusters): semua pose terbaik proyek uji + pose rusak buatan harus gagal.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_qc.py
Butuh dev/uji/statistik/gui/proyek_uji.vmd (dibuat dev/uji_statistik_gui.py).
"""
import time

import numpy as np
from rdkit import Chem
from rdkit.Geometry import Point3D

from virmodock.core import analisis, qc
from virmodock.core import mesin as M
from virmodock.core.proyek import Proyek

assert qc.tersedia()
pr = Proyek.buka("dev/uji/statistik/gui/proyek_uji.vmd")
prot = qc.jalur_protein(pr)
j = pr.job[-1]
t0 = time.perf_counter()
n_lulus = 0
contoh = None
for l in j["ligan"]:
    if l["status"] != "selesai":
        continue
    pose = M.baca_hasil(j["mesin"], pr.p(l["keluaran"]))
    t = time.perf_counter()
    h = qc.periksa_ligan(pr, j, l, pose)
    n_lulus += bool(h.get("lulus"))
    print(f"{l['nama']:28s} {qc.teks_sel(h):10s} {time.perf_counter() - t:5.2f} s  {', '.join(h.get('gagal', []))}"
          f"{h.get('galat', '')}")
    contoh = contoh or (l, pose)
print(f"total {time.perf_counter() - t0:.1f} s, lulus {n_lulus}")

# pose rusak 1: ligan digeser ke pusat atom protein terdekat (tabrakan dengan protein)
l, pose = contoh
mol = analisis.pose_mol(pr.p(l["pdbqt"]).read_text(), pose[0].pdbqt)
from posebusters.tools.loading import safe_load_mol
p = safe_load_mol(prot)
xyz_p = p.GetConformer().GetPositions()
xyz_l = mol.GetConformer().GetPositions()
pusat_l = xyz_l.mean(0)
dekat = xyz_p[np.argmin(((xyz_p - pusat_l) ** 2).sum(1))]
geser = Chem.Mol(mol)
c = geser.GetConformer()
for i, (x, y, z) in enumerate(xyz_l - pusat_l + dekat):
    c.SetAtomPosition(i, Point3D(x, y, z))
h1 = qc.periksa(geser, prot)
print("pose digeser ke protein:", qc.teks_sel(h1), h1["gagal"])
assert not h1["lulus"] and any("protein" in g for g in h1["gagal"])

# pose rusak 2: satu atom berat ditarik 1,2 Å (panjang ikatan salah)
regang = Chem.Mol(mol)
c = regang.GetConformer()
atom = next(x for x in regang.GetAtoms() if x.GetAtomicNum() > 1 and x.GetDegree() == 1)
tetangga = atom.GetNeighbors()[0].GetIdx()
q, r = np.array(c.GetAtomPosition(atom.GetIdx())), np.array(c.GetAtomPosition(tetangga))
q = q + (q - r) / np.linalg.norm(q - r) * 0.6       # ikatan 0,6 Å lebih panjang, searah ikatan
c.SetAtomPosition(atom.GetIdx(), Point3D(*q))
h2 = qc.periksa(regang, prot)
print("ikatan diregangkan:", qc.teks_sel(h2), h2["gagal"])
assert not h2["lulus"] and "Panjang ikatan" in h2["gagal"]
print(qc.tooltip(h2))
print("OK")
