"""Statistik dasar hasil docking: deskriptif, korelasi Pearson/Spearman + regresi linear, matriks korelasi.

numpy + scipy (scipy sudah ikut sebagai dependensi Meeko; BSD-3).
Satu baris data = satu ligan dalam satu job (pose terbaik), digabung dengan sifat ligan (core.sifat).
"""
import math

# (kunci, label sumbu, label pendek, desimal)
VARIABEL = [
    ("energi", "ΔG (kcal/mol)", "ΔG", 2),
    ("le", "Efisiensi ligan (kcal/mol/atom)", "LE", 3),
    ("pki", "pKi perkiraan", "pKi", 2),
    ("hbond", "Jumlah ikatan H", "Ikatan H", 0),
    ("hidrofobik", "Jumlah kontak hidrofobik", "Hidrofobik", 0),
    ("pi_total", "Jumlah interaksi π", "π", 0),
    ("interaksi", "Jumlah interaksi (tanpa vdW)", "Interaksi", 0),
    ("rmsd_kristal", "RMSD kristal (Å)", "RMSD", 2),
    ("ifp_sim", "Kemiripan IFP vs kristal (Tanimoto)", "IFP", 2),
    ("mw", "Massa molekul (g/mol)", "MW", 1),
    ("wlogp", "WLOGP", "WLOGP", 2),
    ("tpsa", "TPSA (Å²)", "TPSA", 1),
    ("hbd", "Donor ikatan H", "Donor H", 0),
    ("hba", "Akseptor ikatan H", "Akseptor H", 0),
    ("rotb", "Ikatan rotasi", "Rotasi", 0),
    ("atom_berat", "Atom berat", "Atom berat", 0),
    ("fsp3", "Fsp3", "Fsp3", 2),
    ("qed", "QED", "QED", 2),
]
LABEL = {k: l for k, l, _, _ in VARIABEL}
PENDEK = {k: p for k, _, p, _ in VARIABEL}
DESIMAL = {k: d for k, _, _, d in VARIABEL}
R_KAL = 1.987207e-3
T = 298.15


def dataset(baris, sifat_per_lid):
    """baris: core.ekspor.baris_hasil. sifat_per_lid: {lid: dict sifat}. Kembalikan list dict datar."""
    out = []
    for b in baris:
        s = sifat_per_lid.get(b["lid"]) or {}
        d = {"ligan": b["ligan"], "lid": b["lid"], "job": b["job"], "mesin": b["mesin"],
             "energi": b["energi"], "le": b.get("le"),
             "pki": -b["energi"] / (R_KAL * T * math.log(10)) if b.get("energi") is not None else None,
             "hbond": b.get("hbond"), "hidrofobik": b.get("hidrofobik"),
             "pi_total": (b.get("pi") or 0) + (b.get("pikation") or 0),
             "interaksi": sum(b.get(k) or 0 for k in ("hbond", "hidrofobik", "pi", "pikation", "garam", "halogen",
                                                     "logam")),
             "rmsd_kristal": b.get("rmsd_kristal"), "ifp": b.get("ifp") or [], "ifp_sim": b.get("ifp_sim")}
        for k in ("mw", "wlogp", "tpsa", "hbd", "hba", "rotb", "atom_berat", "fsp3", "qed"):
            d[k] = s.get(k)
        out.append(d)
    return out


def matriks_ifp(data):
    """Matriks kemiripan Tanimoto IFP antar ligan (baris tanpa IFP dilewati). Kembalikan (label, matriks)."""
    from .analisis import tanimoto
    d = [x for x in data if x.get("ifp")]
    return [x["ligan"] for x in d], [[tanimoto(a["ifp"], b["ifp"]) for b in d] for a in d]


def kolom(data, k):
    return [d[k] for d in data if d.get(k) is not None]


def pasangan(data, kx, ky):
    """[(nama, x, y)] hanya baris dengan kedua nilai ada."""
    return [(d["ligan"], float(d[kx]), float(d[ky])) for d in data
            if d.get(kx) is not None and d.get(ky) is not None]


def deskriptif(nilai):
    import numpy as np
    v = np.asarray(nilai, float)
    if not len(v):
        return {"n": 0}
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    return {"n": int(len(v)), "rerata": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else None,
            "median": float(med), "q1": float(q1), "q3": float(q3), "min": float(v.min()), "maks": float(v.max())}


def korelasi(x, y, pita=True):
    """Pearson r, p; Spearman ρ, p; regresi OLS y = a + b x; R²; pita kepercayaan 95 % garis rerata."""
    import numpy as np
    from scipy import stats
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    hasil = {"n": n, "r": None, "p": None, "rho": None, "p_rho": None, "kemiringan": None, "potong": None,
             "r2": None, "pita": None, "se_kemiringan": None}
    if n < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return hasil
    lr = stats.linregress(x, y)
    sp = stats.spearmanr(x, y)
    hasil.update(r=float(lr.rvalue), p=float(lr.pvalue), rho=float(sp.statistic), p_rho=float(sp.pvalue),
                 kemiringan=float(lr.slope), potong=float(lr.intercept), r2=float(lr.rvalue ** 2),
                 se_kemiringan=float(lr.stderr))
    if pita and n > 3:
        sisa = y - (lr.intercept + lr.slope * x)
        s = math.sqrt(float((sisa ** 2).sum()) / (n - 2))
        tk = float(stats.t.ppf(0.975, n - 2))
        xm, sxx = float(x.mean()), float(((x - x.mean()) ** 2).sum())
        lo, hi = float(x.min()), float(x.max())
        span = hi - lo
        titik = []
        for i in range(61):
            t = lo - 0.1 * span + 1.2 * span * i / 60
            yh = lr.intercept + lr.slope * t
            e = tk * s * math.sqrt(1 / n + (t - xm) ** 2 / sxx)
            titik.append((t, yh + e, yh - e))
        hasil["pita"] = titik
    return hasil


def matriks(data, kunci, metode="pearson"):
    """(r[i][j], p[i][j]) memakai pasangan lengkap per sel."""
    from scipy import stats
    n = len(kunci)
    r = [[None] * n for _ in range(n)]
    p = [[None] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                r[i][j] = 1.0 if len(kolom(data, kunci[i])) > 2 else None
                continue
            if j < i:
                r[i][j], p[i][j] = r[j][i], p[j][i]
                continue
            pr = pasangan(data, kunci[i], kunci[j])
            if len(pr) < 3:
                continue
            xs, ys = [a for _, a, _ in pr], [b for _, _, b in pr]
            if len(set(xs)) < 2 or len(set(ys)) < 2:
                continue
            res = stats.spearmanr(xs, ys) if metode == "spearman" else stats.pearsonr(xs, ys)
            r[i][j], p[i][j] = float(res.statistic), float(res.pvalue)
    return r, p


def kekuatan(r):
    """Tafsiran kasar besaran |r| (Evans 1996) — hanya panduan."""
    a = abs(r)
    return ("sangat lemah" if a < 0.2 else "lemah" if a < 0.4 else "sedang" if a < 0.6 else
            "kuat" if a < 0.8 else "sangat kuat")


def csv_teks(data, pemisah=";", desimal_koma=True):
    """Dataset -> CSV (BOM) untuk diolah lanjut di Excel/SPSS/R/Prism."""
    import csv
    import io

    def f(v):
        if isinstance(v, float):
            t = f"{v:.4f}".rstrip("0").rstrip(".")
            return t.replace(".", ",") if desimal_koma else t
        return "" if v is None else str(v)

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=pemisah, lineterminator="\r\n")
    w.writerow(["Ligan", "Job", "Mesin"] + [label for _, label, _, _ in VARIABEL])
    for d in data:
        w.writerow([d["ligan"], d["job"], d["mesin"]] + [f(d.get(k)) for k, _, _, _ in VARIABEL])
    return "﻿" + buf.getvalue()
