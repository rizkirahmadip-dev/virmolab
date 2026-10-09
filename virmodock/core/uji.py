"""Uji statistik untuk modul 'Uji & Grafik' (alur ala Prism: data kolom -> analisis -> grafik).

Hanya SciPy + NumPy. Pemilihan uji otomatis berdasarkan asumsi (Shapiro–Wilk, Brown–Forsythe), atau manual.
Setiap hasil membawa tabel, paragraf interpretasi, dan paragraf Metode siap tempel (bahasa Indonesia).
"""
import math

import numpy as np

UJI_DUA = {"otomatis": "Otomatis (cek asumsi)", "welch": "t-test Welch", "student": "t-test Student",
           "mann": "Mann–Whitney", "t_pasang": "t-test berpasangan", "wilcoxon": "Wilcoxon bertanda"}
UJI_BANYAK = {"otomatis": "Otomatis (cek asumsi)", "anova": "ANOVA satu arah + Tukey",
              "welch_anova": "ANOVA Welch + Games–Howell", "kruskal": "Kruskal–Wallis + Dunn (Holm)",
              "dunnett": "ANOVA + Dunnett (vs kolom pertama)"}
ALFA = 0.05


def bintang(p, eksak=False):
    if p is None or p != p:
        return ""
    if eksak:
        return "p < 0,0001" if p < 1e-4 else "p = " + f"{p:.4f}".rstrip("0").replace(".", ",")
    return "****" if p < 1e-4 else "***" if p < 1e-3 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"


def f_angka(v, d=3):
    if v is None or (isinstance(v, float) and v != v):
        return "–"
    t = f"{v:.{d}f}"
    return ("−" + t[1:] if t.startswith("-") else t).replace(".", ",")


def f_p(p):
    if p is None or p != p:
        return "–"
    return "< 0,0001" if p < 1e-4 else f_angka(p, 4)


def bersihkan(nilai):
    out = []
    for v in nilai:
        try:
            x = float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if x == x and abs(x) != float("inf"):
            out.append(x)
    return out


def deskriptif(v):
    from scipy import stats
    a = np.asarray(v, float)
    n = len(a)
    if not n:
        return {"n": 0}
    m = float(a.mean())
    sd = float(a.std(ddof=1)) if n > 1 else None
    sem = sd / math.sqrt(n) if sd is not None else None
    ci = float(stats.t.ppf(0.975, n - 1) * sem) if sem is not None else None
    q1, med, q3 = np.percentile(a, [25, 50, 75])
    return {"n": n, "rerata": m, "sd": sd, "sem": sem, "ci95": (m - ci, m + ci) if ci is not None else None,
            "median": float(med), "q1": float(q1), "q3": float(q3), "min": float(a.min()), "maks": float(a.max()),
            "cv": (sd / m * 100) if sd is not None and m else None}


def normalitas(v):
    """Shapiro–Wilk (n 3–5000). Kembalikan (W, p) atau (None, None)."""
    from scipy import stats
    if len(v) < 3 or len(set(v)) < 2:
        return None, None
    w, p = stats.shapiro(v)
    return float(w), float(p)


def _cohen(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = len(a), len(b)
    sp = math.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)) if na + nb > 2 else 0
    d = (a.mean() - b.mean()) / sp if sp else float("nan")
    g = d * (1 - 3 / (4 * (na + nb) - 9)) if na + nb > 2 else float("nan")
    return float(d), float(g)


def _holm(p):
    """Koreksi Holm–Bonferroni."""
    p = np.asarray(p, float)
    urut = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    maks = 0.0
    for k, i in enumerate(urut):
        maks = max(maks, min(1.0, (m - k) * p[i]))
        adj[i] = maks
    return adj.tolist()


def _games_howell(data):
    from scipy import stats
    out = []
    k = len(data)
    for i in range(k):
        for j in range(i + 1, k):
            a, b = np.asarray(data[i], float), np.asarray(data[j], float)
            va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
            se = math.sqrt(va + vb)
            df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
            q = abs(a.mean() - b.mean()) / se * math.sqrt(2)
            p = float(stats.studentized_range.sf(q, k, df))
            h = stats.studentized_range.ppf(0.95, k, df) * se / math.sqrt(2)
            dif = float(a.mean() - b.mean())
            out.append((i, j, dif, (dif - h, dif + h), p))
    return out


def _dunn(data):
    """Dunn (rangking gabungan, koreksi ties) + Holm."""
    from scipy import stats
    semua = np.concatenate([np.asarray(d, float) for d in data])
    r = stats.rankdata(semua)
    N = len(semua)
    _, hit = np.unique(semua, return_counts=True)
    ties = (hit ** 3 - hit).sum() / (12 * (N - 1)) if N > 1 else 0
    rata, n, pos = [], [], 0
    for d in data:
        rata.append(r[pos:pos + len(d)].mean())
        n.append(len(d))
        pos += len(d)
    pas, praw = [], []
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            se = math.sqrt((N * (N + 1) / 12 - ties) * (1 / n[i] + 1 / n[j]))
            z = (rata[i] - rata[j]) / se
            pas.append((i, j, float(np.median(data[i]) - np.median(data[j])), None))
            praw.append(2 * stats.norm.sf(abs(z)))
    adj = _holm(praw)
    return [(i, j, d, ci, p) for (i, j, d, ci), p in zip(pas, adj)]


def _welch_anova(data):
    from scipy import stats
    k = len(data)
    n = np.array([len(d) for d in data], float)
    m = np.array([np.mean(d) for d in data])
    v = np.array([np.var(d, ddof=1) for d in data])
    w = n / v
    mw = (w * m).sum() / w.sum()
    a = (w * (m - mw) ** 2).sum() / (k - 1)
    lam = 3 * (((1 - w / w.sum()) ** 2) / (n - 1)).sum() / (k ** 2 - 1)
    F = a / (1 + 2 * lam * (k - 2) / 3)
    df2 = 1 / lam
    return float(F), (k - 1, float(df2)), float(stats.f.sf(F, k - 1, df2))


def analisis(kelompok, nama, uji="otomatis", berpasangan=False):
    """kelompok: list nilai per grup (sudah dibersihkan). Kembalikan dict hasil lengkap."""
    from scipy import stats
    k = len(kelompok)
    des = [deskriptif(g) for g in kelompok]
    norm = [normalitas(g) for g in kelompok]
    hasil = {"nama": nama, "deskriptif": des, "normalitas": norm, "peringatan": [], "posthoc": [], "uji": uji}
    if k < 2 or any(len(g) < 2 for g in kelompok):
        hasil["peringatan"].append("Butuh minimal 2 grup dengan n ≥ 2 untuk uji perbandingan.")
        return hasil
    normal = all(p is None or p > ALFA for _w, p in norm)
    if any(len(g) < 3 for g in kelompok):
        hasil["peringatan"].append("n < 3 pada sebagian grup: normalitas tidak dapat diuji; hasil kurang andal.")
    bf = stats.levene(*kelompok, center="median")
    hasil["varians"] = (float(bf.statistic), float(bf.pvalue))
    sama_var = bf.pvalue > ALFA
    if k == 2:
        a, b = kelompok
        if berpasangan and len(a) != len(b):
            hasil["peringatan"].append("Data berpasangan butuh n sama di kedua kolom; dianalisis tidak berpasangan.")
            berpasangan = False
        if uji == "otomatis":
            uji = ("t_pasang" if normal else "wilcoxon") if berpasangan else ("welch" if normal else "mann")
        d, g = _cohen(a, b)
        if uji in ("welch", "student"):
            r = stats.ttest_ind(a, b, equal_var=(uji == "student"))
            ci = r.confidence_interval()
            hasil.update(nama_uji=UJI_DUA[uji], stat=("t", float(r.statistic)), df=float(r.df), p=float(r.pvalue),
                         selisih=float(np.mean(a) - np.mean(b)), ci=(float(ci.low), float(ci.high)),
                         efek=("Cohen d", d, "Hedges g", g))
        elif uji == "t_pasang":
            r = stats.ttest_rel(a, b)
            ci = r.confidence_interval()
            dd = np.asarray(a) - np.asarray(b)
            dz = float(dd.mean() / dd.std(ddof=1)) if dd.std(ddof=1) else float("nan")
            hasil.update(nama_uji=UJI_DUA[uji], stat=("t", float(r.statistic)), df=float(r.df), p=float(r.pvalue),
                         selisih=float(dd.mean()), ci=(float(ci.low), float(ci.high)), efek=("Cohen dz", dz))
        elif uji == "mann":
            r = stats.mannwhitneyu(a, b, alternative="two-sided")
            z = stats.norm.isf(r.pvalue / 2)
            hasil.update(nama_uji=UJI_DUA[uji], stat=("U", float(r.statistic)), p=float(r.pvalue),
                         selisih=float(np.median(a) - np.median(b)),
                         efek=("r", float(z / math.sqrt(len(a) + len(b)))))
        else:
            r = stats.wilcoxon(a, b)
            hasil.update(nama_uji=UJI_DUA["wilcoxon"], stat=("W", float(r.statistic)), p=float(r.pvalue),
                         selisih=float(np.median(np.asarray(a) - np.asarray(b))))
        hasil["posthoc"] = [(0, 1, hasil.get("selisih"), hasil.get("ci"), hasil["p"])]
    else:
        if uji == "otomatis":
            uji = ("anova" if sama_var else "welch_anova") if normal else "kruskal"
        semua = np.concatenate([np.asarray(g, float) for g in kelompok])
        if uji in ("anova", "dunnett"):
            r = stats.f_oneway(*kelompok)
            dfb, dfw = k - 1, len(semua) - k
            sst = ((semua - semua.mean()) ** 2).sum()
            ssb = sum(len(g) * (np.mean(g) - semua.mean()) ** 2 for g in kelompok)
            hasil.update(nama_uji=UJI_BANYAK[uji], stat=("F", float(r.statistic)), df=(dfb, dfw),
                         p=float(r.pvalue), efek=("η²", float(ssb / sst) if sst else float("nan")))
            if uji == "anova":
                t = stats.tukey_hsd(*kelompok)
                ci = t.confidence_interval()
                hasil["posthoc"] = [(i, j, float(np.mean(kelompok[i]) - np.mean(kelompok[j])),
                                     (float(ci.low[i, j]), float(ci.high[i, j])), float(t.pvalue[i, j]))
                                    for i in range(k) for j in range(i + 1, k)]
                hasil["nama_posthoc"] = "Tukey HSD"
            else:
                t = stats.dunnett(*kelompok[1:], control=kelompok[0])
                ci = t.confidence_interval()
                hasil["posthoc"] = [(0, i + 1, float(np.mean(kelompok[i + 1]) - np.mean(kelompok[0])),
                                     (float(ci.low[i]), float(ci.high[i])), float(t.pvalue[i]))
                                    for i in range(k - 1)]
                hasil["nama_posthoc"] = f"Dunnett vs {nama[0]}"
        elif uji == "welch_anova":
            F, df, p = _welch_anova(kelompok)
            hasil.update(nama_uji=UJI_BANYAK[uji], stat=("F", F), df=df, p=p)
            hasil["posthoc"] = _games_howell(kelompok)
            hasil["nama_posthoc"] = "Games–Howell"
        else:
            r = stats.kruskal(*kelompok)
            n = len(semua)
            hasil.update(nama_uji=UJI_BANYAK["kruskal"], stat=("H", float(r.statistic)), df=k - 1,
                         p=float(r.pvalue), efek=("ε²", float(r.statistic * (n + 1) / (n ** 2 - 1))))
            hasil["posthoc"] = _dunn(kelompok)
            hasil["nama_posthoc"] = "Dunn (koreksi Holm)"
    hasil["uji"] = uji
    if not normal and uji in ("welch", "student", "t_pasang", "anova", "welch_anova", "dunnett"):
        hasil["peringatan"].append("Sebagian data tidak normal (Shapiro–Wilk p < 0,05): pertimbangkan uji "
                                   "nonparametrik.")
    if k > 2 and uji == "anova" and not sama_var:
        hasil["peringatan"].append("Varians tidak homogen (Brown–Forsythe p < 0,05): pertimbangkan ANOVA Welch.")
    hasil["interpretasi"], hasil["metode"] = _teks(hasil, nama)
    return hasil


def _teks(h, nama):
    if "p" not in h:
        return "", ""
    st, nilai = h["stat"]
    df = h.get("df")
    def fdf(x):
        return f_angka(x, 2) if float(x) % 1 else f_angka(x, 0)
    df_t = (f"({fdf(df[0])}; {fdf(df[1])})" if isinstance(df, tuple) else f"({fdf(df)})" if df is not None else "")
    makna = "berbeda bermakna" if h["p"] < ALFA else "tidak berbeda bermakna"
    inter = (f"{h['nama_uji']}: {st}{df_t} = {f_angka(nilai, 3)}, p {('< 0,0001' if h['p'] < 1e-4 else '= ' + f_p(h['p']))}. "
             f"Kelompok {makna} (α = 0,05).")
    if h.get("efek"):
        inter += f" Ukuran efek {h['efek'][0]} = {f_angka(h['efek'][1], 2)}."
    if h.get("posthoc") and len(nama) > 2:
        sig = [f"{nama[i]} vs {nama[j]} ({bintang(p)})" for i, j, _d, _c, p in h["posthoc"] if p < ALFA]
        inter += (f" Uji lanjut {h.get('nama_posthoc', '')}: " + (", ".join(sig) if sig else
                                                                  "tidak ada pasangan yang berbeda bermakna") + ".")
    norm = "Normalitas diuji dengan Shapiro–Wilk dan homogenitas varians dengan uji Brown–Forsythe."
    if len(nama) == 2:
        met = f"Perbedaan kedua kelompok dianalisis dengan {h['nama_uji']}. {norm}"
    else:
        met = (f"Perbedaan antar kelompok dianalisis dengan {h['nama_uji'].split(' + ')[0]}"
               + (f" diikuti uji {h.get('nama_posthoc')}" if h.get("nama_posthoc") else "") + f". {norm}")
    met += " Nilai p < 0,05 dianggap bermakna. Analisis dilakukan dengan VirmoDock (SciPy)."
    return inter, met


# ------------------------------------------------------------------ dosis–respons
def model_4pl(x, bawah, atas, log_ic50, hill):
    with np.errstate(over="ignore"):     # iterasi awal curve_fit bisa melampaui rentang; hasilnya inf -> 0
        return bawah + (atas - bawah) / (1 + np.power(10.0, (log_ic50 - x) * hill))


def dosis_respons(konsentrasi, respons, log_x=True):
    """Regresi nonlinear 4PL (sigmoid, kemiringan bebas). konsentrasi > 0 (bila log_x) dan respons per titik
    (boleh replikat: konsentrasi berulang). Kembalikan dict: parameter, IC50 ± CI95, R², kurva."""
    from scipy import optimize, stats
    x = np.asarray(konsentrasi, float)
    y = np.asarray(respons, float)
    ok = np.isfinite(x) & np.isfinite(y) & ((x > 0) if log_x else True)
    x, y = x[ok], y[ok]
    if len(set(x)) < 4:
        return {"galat": "Butuh minimal 4 konsentrasi berbeda untuk model 4PL."}
    if float(np.ptp(y)) < 1e-9:
        return {"galat": "Respons sama di semua konsentrasi: tidak ada kurva dosis–respons yang bisa dihitung."}
    lx = np.log10(x) if log_x else x
    p0 = [float(y.min()), float(y.max()), float(np.median(lx)), 1.0 if y[np.argmax(lx)] > y[np.argmin(lx)] else -1.0]
    try:
        par, cov = optimize.curve_fit(model_4pl, lx, y, p0=p0, maxfev=20000)
    except Exception as e:
        return {"galat": f"Kurva tidak konvergen ({type(e).__name__})."}
    pred = model_4pl(lx, *par)
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    dof = max(1, len(y) - 4)
    se = np.sqrt(np.diag(cov)) if np.all(np.isfinite(cov)) else np.full(4, np.nan)
    t = stats.t.ppf(0.975, dof)
    lo, hi = par[2] - t * se[2], par[2] + t * se[2]
    xs = np.linspace(lx.min() - 0.3, lx.max() + 0.3, 200)
    r2 = 1 - ss_res / ss_tot if ss_tot else None
    ci_ok = bool(np.isfinite(se[2]) and abs(lo) < 300 and abs(hi) < 300)
    peringatan = []
    if not lx.min() <= par[2] <= lx.max():
        peringatan.append("IC₅₀ berada di luar rentang konsentrasi yang diuji (ekstrapolasi): kurang andal — "
                          "tambahkan konsentrasi di sekitar IC₅₀.")
    if not ci_ok or (hi - lo) > 2:
        peringatan.append("CI 95% IC₅₀ sangat lebar atau tak terhitung: data belum cukup mendefinisikan kurva "
                          "(perlu titik di dasar, puncak, dan sekitar IC₅₀).")
    if abs(par[1] - par[0]) < 0.25 * float(np.ptp(y)) or abs(par[3]) > 10:
        peringatan.append("Bentuk kurva tidak sigmoid wajar (dasar ≈ puncak atau kemiringan ekstrem): periksa data.")
    if r2 is not None and r2 < 0.8:
        peringatan.append(f"Kecocokan model rendah (R² = {f_angka(r2, 2)}).")
    return {"peringatan": peringatan, "bawah": float(par[0]), "atas": float(par[1]), "log_ic50": float(par[2]), "hill": float(par[3]),
            "ic50": float(10 ** par[2]) if log_x else float(par[2]),
            "ic50_ci": ((float(10 ** lo), float(10 ** hi)) if log_x else (float(lo), float(hi)))
            if ci_ok else None,
            "r2": r2, "n": int(len(y)), "dof": dof,
            "kurva": (xs.tolist(), model_4pl(xs, *par).tolist()), "titik": (lx.tolist(), y.tolist()),
            "log_x": log_x}


# ------------------------------------------------------------------ ROC
def roc(negatif, positif, rendah_positif=False):
    """Kurva ROC dua kolom (negatif = kontrol/decoy, positif = kasus/aktif). Ambang: skor ≥ t -> positif
    (atau ≤ t bila rendah_positif, mis. ΔG docking). AUC = statistik Mann–Whitney; CI 95 % DeLong;
    titik potong Youden; faktor pengayaan (EF) 1/5/10 % untuk penapisan virtual."""
    from scipy import stats
    neg, pos = np.asarray(negatif, float), np.asarray(positif, float)
    n0, n1 = len(neg), len(pos)
    if n0 < 2 or n1 < 2:
        return {"galat": "Butuh minimal 2 nilai di kolom negatif dan positif."}
    tanda = -1.0 if rendah_positif else 1.0
    sn, sp = neg * tanda, pos * tanda
    # komponen penempatan DeLong (ties = 0,5)
    psi = (sp[:, None] > sn[None, :]).astype(float) + 0.5 * (sp[:, None] == sn[None, :])
    auc = float(psi.mean())
    v10, v01 = psi.mean(axis=1), psi.mean(axis=0)
    var = v10.var(ddof=1) / n1 + v01.var(ddof=1) / n0
    se = math.sqrt(var) if var > 0 else 0.0
    ci = (max(0.0, auc - 1.96 * se), min(1.0, auc + 1.96 * se)) if se else None
    p = float(stats.mannwhitneyu(sp, sn, alternative="two-sided").pvalue)
    ambang = np.unique(np.concatenate([sn, sp]))[::-1]
    fpr, tpr, titik = [0.0], [0.0], []
    for t in ambang:
        tp, fp = float((sp >= t).mean()), float((sn >= t).mean())
        fpr.append(fp)
        tpr.append(tp)
        titik.append((float(t * tanda), tp, 1 - fp))
    j = max(range(len(titik)), key=lambda i: titik[i][1] + titik[i][2])
    potong, sens, spes = titik[j]
    semua = np.concatenate([sp, sn])
    label = np.concatenate([np.ones(n1), np.zeros(n0)])
    urut = label[np.argsort(-semua, kind="stable")]
    ef = {}
    for persen in (1, 5, 10):
        n = max(1, math.ceil(len(semua) * persen / 100))
        ef[persen] = float(urut[:n].mean() / (n1 / len(semua)))
    arah = "≤" if rendah_positif else "≥"
    makna = ("membedakan kedua kelompok secara bermakna" if p < ALFA
             else "tidak membedakan kedua kelompok secara bermakna")
    kualitas = ("sangat baik" if auc >= 0.9 else "baik" if auc >= 0.8 else "cukup" if auc >= 0.7 else
                "lemah" if auc >= 0.6 else "setara tebakan acak")
    inter = (f"AUC = {f_angka(auc)}" + (f" (CI 95% {f_angka(ci[0])}–{f_angka(ci[1])})" if ci else "")
             + f", p {'< 0,0001' if p < 1e-4 else '= ' + f_p(p)}: skor {makna} (daya pembeda {kualitas}). "
             f"Titik potong optimal (indeks Youden) {arah} {f_angka(potong, 2)}: sensitivitas "
             f"{f_angka(sens * 100, 1)} %, spesifisitas {f_angka(spes * 100, 1)} %. EF1% = {f_angka(ef[1], 1)}, "
             f"EF5% = {f_angka(ef[5], 1)}.")
    met = ("Kemampuan skor membedakan kelompok positif dan negatif dinilai dengan kurva receiver operating "
           "characteristic (ROC). Luas di bawah kurva (AUC) dihitung dengan metode nonparametrik (Mann–Whitney) "
           "beserta interval kepercayaan 95 % metode DeLong; titik potong optimal ditentukan dengan indeks Youden. "
           "Analisis dilakukan dengan VirmoDock (SciPy).")
    peringatan = []
    if auc < 0.5:
        peringatan.append("AUC < 0,5: skor justru membedakan ke arah sebaliknya — periksa pilihan arah "
                          "(“Skor rendah = positif” untuk ΔG docking) atau letak kolom negatif/positif.")
    if min(n0, n1) < 10:
        peringatan.append("Jumlah data kecil (< 10 per kelompok): interval kepercayaan AUC kurang andal.")
    return {"peringatan": peringatan, "auc": auc, "se": se, "ci": ci, "p": p, "potong": float(potong), "sens": sens, "spes": spes, "ef": ef,
            "fpr": fpr, "tpr": tpr, "n0": n0, "n1": n1, "rendah_positif": rendah_positif, "titik": titik,
            "interpretasi": inter, "metode": met}


# ------------------------------------------------------------------ kontingensi
def kontingensi(obs, baris, kolom):
    """Tabel kontingensi r × c (frekuensi). 2 × 2: Fisher eksak (utama) + χ² Yates, OR & RR (CI 95 %).
    r × c: χ² Pearson (Fisher eksak r × c bila frekuensi harapan kecil). Ukuran efek Cramér V."""
    from scipy import stats
    o = np.asarray(obs, float)
    h = {"baris": baris, "kolom": kolom, "obs": o.tolist(), "peringatan": []}
    if o.ndim != 2 or o.shape[0] < 2 or o.shape[1] < 2:
        h["galat"] = "Butuh minimal 2 baris (kelompok) × 2 kolom (kategori)."
        return h
    if (o < 0).any() or (o.sum(axis=1) == 0).any() or (o.sum(axis=0) == 0).any():
        h["galat"] = "Frekuensi harus ≥ 0 dan tidak boleh ada baris/kolom yang seluruhnya nol."
        return h
    if np.any(np.abs(o - np.round(o)) > 1e-9):
        h["peringatan"].append("Tabel kontingensi butuh frekuensi (bilangan bulat), bukan persentase/rerata.")
    n = o.sum()
    chi2, p_chi, dof, harap = stats.chi2_contingency(o, correction=False)
    v = math.sqrt(chi2 / (n * (min(o.shape) - 1)))
    kecil = (harap < 5).mean()
    h.update(n=int(n), chi2=float(chi2), dof=int(dof), p_chi=float(p_chi), harap=harap.tolist(), cramer=v)
    if o.shape == (2, 2):
        a, b, c_, d = o.ravel()
        chi_y, p_y, _, _ = stats.chi2_contingency(o, correction=True)
        _or, p_f = stats.fisher_exact(o)
        k = 0.5 if 0 in (a, b, c_, d) else 0.0       # koreksi Haldane–Anscombe
        orr = float(((a + k) * (d + k)) / ((b + k) * (c_ + k)))
        se_or = math.sqrt(sum(1 / (x + k) for x in (a, b, c_, d)))
        r1, r2 = (a + k) / (a + b + 2 * k), (c_ + k) / (c_ + d + 2 * k)
        rr = float(r1 / r2)
        se_rr = math.sqrt((1 - r1) / ((a + b + 2 * k) * r1) + (1 - r2) / ((c_ + d + 2 * k) * r2))
        h.update(nama_uji="Uji eksak Fisher", p=float(p_f), chi2_yates=float(chi_y), p_yates=float(p_y),
                 OR=orr, OR_ci=(orr * math.exp(-1.96 * se_or), orr * math.exp(1.96 * se_or)),
                 RR=rr, RR_ci=(rr * math.exp(-1.96 * se_rr), rr * math.exp(1.96 * se_rr)))
    else:
        h.update(nama_uji="Uji χ² Pearson", p=float(p_chi))
        if kecil > 0.2 or (harap < 1).any():
            try:
                h["p_fisher"] = float(stats.fisher_exact(o).pvalue)
                h["peringatan"].append("> 20 % sel berfrekuensi harapan < 5: χ² kurang andal — dipakai p uji "
                                       "eksak Fisher (r × c).")
                h.update(nama_uji="Uji eksak Fisher (r × c)", p=h["p_fisher"])
            except Exception:
                h["peringatan"].append("> 20 % sel berfrekuensi harapan < 5: χ² kurang andal; pertimbangkan "
                                       "menggabungkan kategori.")
    p = h["p"]
    st = f"χ²({dof}) = {f_angka(chi2)}, " if h["nama_uji"] == "Uji χ² Pearson" else ""
    inter = (f"{h['nama_uji']}: {st}p {'< 0,0001' if p < 1e-4 else '= ' + f_p(p)}. Distribusi "
             f"{'berbeda bermakna' if p < ALFA else 'tidak berbeda bermakna'} antar kelompok (α = 0,05). "
             f"Cramér V = {f_angka(v, 2)}.")
    if "OR" in h:
        inter += (f" Rasio odds = {f_angka(h['OR'], 2)} (CI 95% {f_angka(h['OR_ci'][0], 2)}–"
                  f"{f_angka(h['OR_ci'][1], 2)}); risiko relatif = {f_angka(h['RR'], 2)} (CI 95% "
                  f"{f_angka(h['RR_ci'][0], 2)}–{f_angka(h['RR_ci'][1], 2)}).")
    met = ("Hubungan antar variabel kategorik dianalisis dengan "
           + ("uji eksak Fisher; rasio odds dan risiko relatif dilaporkan dengan interval kepercayaan 95 % "
              "(metode Woolf/Katz)." if o.shape == (2, 2) else
              h["nama_uji"].replace("Uji", "uji") + "; ukuran efek dinyatakan dengan Cramér V.")
           + " Nilai p < 0,05 dianggap bermakna. Analisis dilakukan dengan VirmoDock (SciPy).")
    h["interpretasi"], h["metode"] = inter, met
    return h
