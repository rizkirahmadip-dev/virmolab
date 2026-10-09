"""Validasi statistik lanjut terhadap rujukan independen (tanpa GUI):
BH = SciPy, Holm contoh teori, ANOVA berulang = OLS, ANOVA dua arah seimbang = rumus klasik, Grubbs = tabel kritis,
Friedman = SciPy, BEDROC/EF = RDKit, logAUC acak ≈ 14,46 %, pemilihan model 4PL/3PL, Kendall W = Friedman.
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/uji_statistik_lanjut.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

from virmodock.core import konsensus as K  # noqa: E402
from virmodock.core import uji as U  # noqa: E402

gagal = []


def cek(nama, kondisi, detail=""):
    print(("OK   " if kondisi else "GAGAL") + f" {nama} {detail}", flush=True)
    if not kondisi:
        gagal.append(nama)


rng = np.random.default_rng(11)
p = rng.uniform(0, 0.2, 12)
cek("BH = SciPy", np.allclose(U.koreksi_p(p, "bh"), stats.false_discovery_control(p)))
cek("Holm teori", np.allclose(U.koreksi_p([0.01, 0.02, 0.04], "holm"), [0.03, 0.04, 0.04]))
cek("Šidák", np.allclose(U.koreksi_p([0.01, 0.02], "sidak"), [1 - 0.99 ** 2, 1 - 0.98 ** 2]))
n, k = 8, 4
X = rng.normal(0, 1, (n, 1)) + np.array([0, 0.3, 0.8, 0.5]) + rng.normal(0, 0.6, (n, k))
r = U._anova_berulang(X, list("ABCD"), "holm")
y = X.ravel()
sub, kon = np.repeat(np.arange(n), k), np.tile(np.arange(k), n)
D = np.column_stack([np.ones(n * k)] + [(sub == i).astype(float) for i in range(1, n)]
                    + [(kon == j).astype(float) for j in range(1, k)])
F_ols = ((U._sse(D[:, :n], y) - U._sse(D, y)) / (k - 1)) / (U._sse(D, y) / ((n - 1) * (k - 1)))
cek("ANOVA berulang = OLS", abs(r["stat"][1] - F_ols) < 1e-8, f"{r['stat'][1]:.6f}")
cek("Friedman = SciPy", abs(U._friedman(X, "holm")["stat"][1] - stats.friedmanchisquare(*X.T).statistic) < 1e-9)
a, b, rep = 3, 2, 5
fa, fb, yy = [], [], []
for i in range(a):
    for j in range(b):
        for _ in range(rep):
            fa.append(f"A{i}")
            fb.append(f"B{j}")
            yy.append(rng.normal(i * 0.6 + j * 0.4, 1))
h = U.anova_dua_arah(yy, fa, fb)
Y = np.array(yy).reshape(a, b, rep)
g = Y.mean()
ssa = b * rep * ((Y.mean(axis=(1, 2)) - g) ** 2).sum()
ssb = a * rep * ((Y.mean(axis=(0, 2)) - g) ** 2).sum()
ssab = rep * ((Y.mean(axis=2) - g) ** 2).sum() - ssa - ssb
cek("ANOVA dua arah = rumus klasik",
    np.allclose([x["ss"] for x in h["tabel"][:3]], [ssa, ssb, ssab]))
t = math.sqrt(10 * 8 * 2.29 ** 2 / (81 - 10 * 2.29 ** 2))
cek("Grubbs kritis n=10", abs(min(1, 20 * stats.t.sf(t, 8)) - 0.05) < 0.002)
from rdkit.ML.Scoring import Scoring as RS  # noqa: E402
pos, neg = rng.normal(1.2, 1, 50), rng.normal(0, 1, 2000)
u = U._urutan(pos, neg)
cek("BEDROC = RDKit", abs(U.bedroc(u) - RS.CalcBEDROC([[0, int(x)] for x in u], 1, 20.0)) < 1e-9)
cek("EF5 = RDKit", abs(U.faktor_pengayaan(u, 5) - RS.CalcEnrichment([[0, int(x)] for x in u], 1, [0.05])[0]) < 1e-9)
cek("logAUC acak", abs(U.log_auc(np.linspace(0, 1, 100001), np.linspace(0, 1, 100001)) - U.LOGAUC_ACAK) < 0.05)
x = np.repeat([0.01, 0.1, 1, 10, 100, 1000], 3)
y1 = U.model_4pl(np.log10(x), 0, 100, 0.5, 1.0) + rng.normal(0, 3, len(x))
y2 = U.model_4pl(np.log10(x), 0, 100, 0.5, 2.2) + rng.normal(0, 3, len(x))
cek("model Hill 1 -> 3PL", U.dosis_respons(x, y1, model="auto")["model"] == "3pl")
cek("model Hill 2,2 -> 4PL", U.dosis_respons(x, y2, model="auto")["model"] == "4pl")
R = np.array([[1, 6, 3, 2, 5, 4], [1, 5, 6, 4, 2, 3], [6, 3, 2, 5, 4, 1]])
w = K.kendall_w(R)
cek("Kendall W = Friedman", abs(w[1] - stats.friedmanchisquare(*R.T).statistic) < 1e-9)
print("SEMUA LULUS" if not gagal else f"GAGAL: {gagal}")
sys.exit(1 if gagal else 0)
