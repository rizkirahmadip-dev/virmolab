"""Uji core/statistik.py + core/grafik.py: bandingkan dengan nilai rujukan scipy/numpy dan tulis SVG contoh.

PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_statistik.py
"""
from pathlib import Path

import numpy as np

from virmodock.core import grafik, statistik
from virmodock.core.ekspor import baris_hasil
from virmodock.core.proyek import Proyek

# data sintetis dengan korelasi diketahui
rng = np.random.default_rng(1)
x = rng.normal(300, 60, 40)
y = -0.02 * x + rng.normal(0, 0.8, 40)
k = statistik.korelasi(x, y)
r_np = np.corrcoef(x, y)[0, 1]
assert abs(k["r"] - r_np) < 1e-9, (k["r"], r_np)
b, a = np.polyfit(x, y, 1)
assert abs(k["kemiringan"] - b) < 1e-9 and abs(k["potong"] - a) < 1e-9
print(f"sintetis: r {k['r']:.4f} (numpy {r_np:.4f}) p {k['p']:.2e} rho {k['rho']:.3f} R² {k['r2']:.3f}")
d = statistik.deskriptif([1, 2, 3, 4, 100])
assert d["median"] == 3 and d["q1"] == 2 and d["n"] == 5
print("deskriptif:", d)
assert statistik.korelasi([1, 1, 1], [1, 2, 3])["r"] is None   # varian nol -> tidak dihitung

OUT = Path("dev/uji/statistik")
OUT.mkdir(parents=True, exist_ok=True)
pr = Proyek.buka("dev/uji/sifat/proyek_uji.vmd")   # dibuat dev/uji_sifat_gui.py (berisi sifat)
sif = {l["id"]: l.get("sifat") for l in pr.ligan}
data = statistik.dataset(baris_hasil(pr), sif)
print("baris data:", len(data), "contoh:", {k: data[0][k] for k in ("ligan", "energi", "pki", "mw", "interaksi")})
eg = statistik.kolom(data, "energi")
(OUT / "hist.svg").write_text(grafik.histogram(eg, "ΔG (kcal/mol)", "Sebaran ΔG"), encoding="utf-8")
pr_ = statistik.pasangan(data, "mw", "energi")
kr = statistik.korelasi([p[1] for p in pr_], [p[2] for p in pr_])
print(f"MW vs ΔG: r {kr['r']:.3f} p {kr['p']:.3g} n {kr['n']} ({statistik.kekuatan(kr['r'])})")
(OUT / "sebar.svg").write_text(grafik.sebar([p[1] for p in pr_], [p[2] for p in pr_], [p[0] for p in pr_],
                                            "Massa molekul (g/mol)", "ΔG (kcal/mol)", "MW vs ΔG", kr, label=True),
                               encoding="utf-8")
top = sorted(data, key=lambda d: d["energi"])[:15]
(OUT / "batang.svg").write_text(grafik.batang([d["ligan"] for d in top], [d["energi"] for d in top],
                                              "ΔG (kcal/mol)", "15 ligan terbaik"), encoding="utf-8")
kun = ["energi", "le", "mw", "wlogp", "tpsa", "hbd", "hba", "rotb", "qed", "interaksi"]
r, p = statistik.matriks(data, kun)
(OUT / "matriks.svg").write_text(grafik.peta_korelasi([statistik.PENDEK[k] for k in kun], r, "Korelasi Pearson",
                                                      p=p), encoding="utf-8")
(OUT / "matriks_gelap.svg").write_text(grafik.peta_korelasi([statistik.PENDEK[k] for k in kun], r, gelap=True, p=p),
                                       encoding="utf-8")

import sys
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
app = QGuiApplication(sys.argv)
for f in OUT.glob("*.svg"):
    rr = QSvgRenderer(str(f))
    assert rr.isValid(), f
    img = QImage(rr.defaultSize(), QImage.Format_ARGB32)
    img.fill(0)
    pa = QPainter(img)
    rr.render(pa)
    pa.end()
    img.save(str(f.with_suffix(".png")))
print("SVG valid & dirender:", sorted(f.name for f in OUT.glob("*.png")))
