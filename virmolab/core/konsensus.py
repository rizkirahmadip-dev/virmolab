"""Konsensus skor: gabungkan beberapa fungsi skor/mesin docking agar peringkat ligan tidak bergantung pada satu
fungsi skor saja.

Sumber kolom skor:
 - hasil job berbeda (mis. AutoDock-GPU, AutoDock Vina, AutoDock4) - ΔG terbaik tiap ligan per job;
 - rescoring pose terbaik tiap ligan dengan fungsi skor Vina dan Vinardo (`vina --score_only --autobox`),
    tanpa docking ulang. Hasil rescoring disimpan di data ligan job (`l["rescore"]`) agar tidak dihitung ulang.
Per kolom: peringkat (1 = ΔG terendah) dan z-score (dibalik: makin besar makin baik). Konsensus = rata-rata
peringkat (utama) dan rata-rata z. "Konsisten" = masuk persentil teratas di SEMUA kolom. Kesepakatan antar
kolom: Kendall W (koreksi ties) + uji χ², dan korelasi Spearman berpasangan.
"""
import math
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import paths

NOWIN = 0x08000000
FUNGSI_RESCORE = {"vina": "Vina (rescoring)", "vinardo": "Vinardo (rescoring)"}
SITASI_VINARDO = ("Quiroga R, Villarreal MA. Vinardo: a scoring function based on AutoDock Vina improves scoring, "
                  "docking, and virtual screening. PLoS One. 2016;11(5):e0155183. doi:10.1371/journal.pone.0155183")


def rescore(rec_pdbqt, pose_pdbqt, fungsi="vina"):
    """ΔG (kcal/mol) pose dengan fungsi skor Vina/Vinardo tanpa optimasi. Kembalikan float atau galat."""
    exe = paths.program("vina.exe")
    if not exe:
        raise FileNotFoundError("vina.exe tidak ditemukan")
    with tempfile.TemporaryDirectory(prefix="vmd_rescore_") as d:
        f = Path(d, "pose.pdbqt")
        f.write_text(pose_pdbqt.rstrip() + "\n", encoding="utf-8")
        p = subprocess.run([exe, "--receptor", str(rec_pdbqt), "--ligand", str(f), "--score_only", "--autobox",
                            "--scoring", fungsi], capture_output=True, timeout=120, creationflags=NOWIN)
    teks = (p.stdout + p.stderr).decode("utf-8", "replace")
    m = re.search(r"Estimated Free Energy of Binding\s*:\s*(-?\d+\.\d+)", teks)
    if not m:
        raise RuntimeError(teks.strip().splitlines()[-1] if teks.strip() else "rescoring gagal")
    return float(m.group(1))


def _peringkat(v):
    from scipy.stats import rankdata
    return rankdata(v, method="average")


def kendall_w(matriks_peringkat):
    """Kendall W untuk m penilai (baris) × n objek (kolom), koreksi ties. Kembalikan (W, χ², df, p)."""
    from scipy.stats import chi2
    R = np.asarray(matriks_peringkat, float)
    m, n = R.shape
    if m < 2 or n < 3:
        return None
    S = ((R.sum(axis=0) - m * (n + 1) / 2) ** 2).sum()
    T = 0.0
    for baris in R:
        _, hit = np.unique(baris, return_counts=True)
        T += (hit ** 3 - hit).sum()
    pembagi = m ** 2 * (n ** 3 - n) - m * T
    if pembagi <= 0:
        return None
    W = 12 * S / pembagi
    x2 = m * (n - 1) * W
    return float(W), float(x2), n - 1, float(chi2.sf(x2, n - 1))


def hitung(kolom, nama_ligan, teratas=20.0):
    """kolom: {nama kolom: {kunci ligan: ΔG}}; nama_ligan: {kunci: nama}. Hanya ligan yang punya nilai di semua
    kolom. Kembalikan dict: kolom, baris (urut konsensus), W, spearman, n, teratas."""
    from scipy.stats import spearmanr
    nama_kol = [k for k, v in kolom.items() if v]
    kunci = sorted(set.intersection(*(set(kolom[k]) for k in nama_kol))) if nama_kol else []
    hasil = {"kolom": nama_kol, "baris": [], "W": None, "spearman": None, "n": len(kunci), "teratas": teratas,
             "galat": None}
    if len(nama_kol) < 2:
        hasil["galat"] = ("Butuh minimal 2 kolom skor: jalankan docking dengan mesin lain, atau aktifkan rescoring "
                          "Vina/Vinardo.")
        return hasil
    if len(kunci) < 3:
        hasil["galat"] = "Butuh minimal 3 ligan yang punya skor di semua kolom."
        return hasil
    X = np.array([[kolom[k][x] for x in kunci] for k in nama_kol], float)   # baris = fungsi skor
    R = np.vstack([_peringkat(b) for b in X])                              # 1 = ΔG terendah (terbaik)
    Z = np.vstack([-(b - b.mean()) / (b.std(ddof=1) or 1.0) for b in X])
    batas = max(1, math.ceil(len(kunci) * teratas / 100))
    rata_r, rata_z = R.mean(axis=0), Z.mean(axis=0)
    konsisten = (R <= batas).all(axis=0)
    urut = np.lexsort((-rata_z, rata_r))
    for posisi, i in enumerate(urut, 1):
        hasil["baris"].append({"peringkat": posisi, "kunci": kunci[i], "ligan": nama_ligan.get(kunci[i], kunci[i]),
                               "skor": [float(v) for v in X[:, i]], "rank": [float(v) for v in R[:, i]],
                               "rata_rank": float(rata_r[i]), "rata_z": float(rata_z[i]),
                               "konsisten": bool(konsisten[i])})
    hasil["W"] = kendall_w(R)
    rho = np.ones((len(nama_kol), len(nama_kol)))
    for a in range(len(nama_kol)):
        for b in range(a + 1, len(nama_kol)):
            rho[a, b] = rho[b, a] = float(spearmanr(X[a], X[b]).statistic)
    hasil["spearman"] = rho.tolist()
    hasil["n_konsisten"] = int(konsisten.sum())
    return hasil


def teks_metode(h):
    if not h or h.get("galat"):
        return ""
    w = h.get("W")
    from .. import i18n
    if i18n.inggris():
        t = (f"Consensus ranks were built from {len(h['kolom'])} scoring functions ({', '.join(h['kolom'])}): each "
             "ligand was ranked per scoring function (1 = lowest ΔG), then sorted by mean rank (mean z-score as "
             f"tie-breaker). A ligand was considered consistent if it was in the top {h['teratas']:g} % for every "
             "scoring function. Agreement between scoring functions was assessed with Kendall's coefficient of "
             "concordance W")
        if w:
            t += (f" (W = {w[0]:.3f}; χ²({w[2]}) = {w[1]:.2f}; "
                  f"p {'< 0.0001' if w[3] < 1e-4 else '= ' + f'{w[3]:.4f}'})")
        return t + f". {h['n_konsisten']} of {h['n']} ligands were consistent."
    t = (f"Peringkat konsensus disusun dari {len(h['kolom'])} fungsi skor ({', '.join(h['kolom'])}): tiap ligan "
         "diberi peringkat per fungsi skor (1 = ΔG terendah), lalu diurutkan menurut rata-rata peringkat (z-score "
         f"rata-rata sebagai pemisah). Ligan dianggap konsisten bila berada pada {h['teratas']:g} % teratas di semua "
         "fungsi skor. Kesepakatan antar fungsi skor dinilai dengan koefisien konkordansi Kendall W")
    if w:
        t += f" (W = {w[0]:.3f}".replace(".", ",") + f"; χ²({w[2]}) = {w[1]:.2f}".replace(".", ",") + \
             f"; p {'< 0,0001' if w[3] < 1e-4 else '= ' + f'{w[3]:.4f}'.replace('.', ',')})"
    return t + f". {h['n_konsisten']} dari {h['n']} ligan konsisten."
