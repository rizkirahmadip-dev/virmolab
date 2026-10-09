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
              "dunnett": "ANOVA + Dunnett (vs kolom pertama)",
              "rm_anova": "ANOVA pengukuran berulang + t berpasangan", "friedman": "Friedman + Wilcoxon bertanda"}
KOREKSI = {"holm": "Holm", "bonferroni": "Bonferroni", "sidak": "Šidák", "bh": "Benjamini–Hochberg (FDR)"}
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


def koreksi_p(p, metode="holm"):
    """p disesuaikan untuk perbandingan ganda: holm | bonferroni | sidak | bh (Benjamini–Hochberg, FDR)."""
    p = np.asarray(p, float)
    m = len(p)
    if m == 0:
        return []
    if metode == "bonferroni":
        return np.minimum(1.0, p * m).tolist()
    if metode == "sidak":
        return (1 - (1 - p) ** m).tolist()
    if metode == "bh":
        urut = np.argsort(p)[::-1]
        adj = np.empty(m)
        terkecil = 1.0
        for k, i in enumerate(urut):
            terkecil = min(terkecil, p[i] * m / (m - k))
            adj[i] = terkecil
        return np.minimum(adj, 1.0).tolist()
    return _holm(p)


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


def _dunn(data, koreksi="holm"):
    """Dunn (rangking gabungan, koreksi ties) + koreksi p perbandingan ganda (bawaan Holm)."""
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
    adj = koreksi_p(praw, koreksi)
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


def grubbs(v):
    """Uji Grubbs dua sisi untuk satu pencilan (n ≥ 3). Kembalikan (indeks, nilai, G, p) atau None."""
    from scipy import stats
    a = np.asarray(v, float)
    n = len(a)
    if n < 3 or a.std(ddof=1) == 0:
        return None
    d = np.abs(a - a.mean())
    i = int(d.argmax())
    G = float(d[i] / a.std(ddof=1))
    pembagi = (n - 1) ** 2 - n * G ** 2
    if pembagi <= 0:
        return i, float(a[i]), G, 0.0
    t = math.sqrt(n * (n - 2) * G ** 2 / pembagi)
    return i, float(a[i]), G, float(min(1.0, 2 * n * stats.t.sf(t, n - 2)))


def _anova_berulang(X, nama, koreksi):
    """X: n subjek × k kondisi. ANOVA pengukuran berulang satu faktor + epsilon Greenhouse–Geisser; uji lanjut
    t berpasangan dengan koreksi p."""
    from scipy import stats
    n, k = X.shape
    g = X.mean()
    ss_kon = n * ((X.mean(axis=0) - g) ** 2).sum()
    ss_sub = k * ((X.mean(axis=1) - g) ** 2).sum()
    ss_gal = ((X - g) ** 2).sum() - ss_kon - ss_sub
    df1, df2 = k - 1, (k - 1) * (n - 1)
    F = (ss_kon / df1) / (ss_gal / df2) if ss_gal > 0 else float("inf")
    S = np.cov(X, rowvar=False)
    C = np.eye(k) - np.ones((k, k)) / k
    Sc = C @ S @ C
    eps = float(np.trace(Sc) ** 2 / ((k - 1) * (Sc ** 2).sum())) if (Sc ** 2).sum() > 0 else 1.0
    eps = min(1.0, max(1 / (k - 1), eps))
    p_gg = float(stats.f.sf(F, eps * df1, eps * df2))
    praw, pas = [], []
    for i in range(k):
        for j in range(i + 1, k):
            r = stats.ttest_rel(X[:, i], X[:, j])
            ci = r.confidence_interval()
            pas.append((i, j, float((X[:, i] - X[:, j]).mean()), (float(ci.low), float(ci.high))))
            praw.append(float(r.pvalue))
    adj = koreksi_p(praw, koreksi)
    return {"stat": ("F", float(F)), "df": (round(eps * df1, 2), round(eps * df2, 2)), "p": p_gg,
            "p_tanpa_koreksi": float(stats.f.sf(F, df1, df2)), "epsilon": eps,
            "efek": ("η²ₚ", float(ss_kon / (ss_kon + ss_gal)) if ss_kon + ss_gal else float("nan")),
            "posthoc": [(i, j, d, ci, q) for (i, j, d, ci), q in zip(pas, adj)],
            "nama_posthoc": f"t berpasangan (koreksi {KOREKSI[koreksi]})"}


def _friedman(X, koreksi):
    from scipy import stats
    n, k = X.shape
    r = stats.friedmanchisquare(*X.T)
    praw, pas = [], []
    for i in range(k):
        for j in range(i + 1, k):
            w = stats.wilcoxon(X[:, i], X[:, j])
            pas.append((i, j, float(np.median(X[:, i] - X[:, j])), None))
            praw.append(float(w.pvalue))
    adj = koreksi_p(praw, koreksi)
    return {"stat": ("χ²", float(r.statistic)), "df": k - 1, "p": float(r.pvalue),
            "efek": ("Kendall W", float(r.statistic / (n * (k - 1)))),
            "posthoc": [(i, j, d, ci, q) for (i, j, d, ci), q in zip(pas, adj)],
            "nama_posthoc": f"Wilcoxon bertanda (koreksi {KOREKSI[koreksi]})"}


def analisis(kelompok, nama, uji="otomatis", berpasangan=False, koreksi="holm"):
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
    hasil["dagostino"] = [float(stats.normaltest(g).pvalue) if len(g) >= 8 and len(set(g)) > 2 else None
                          for g in kelompok]
    for nm, g in zip(nama, kelompok):
        gb = grubbs(g) if len(g) >= 4 else None
        if gb and gb[3] < ALFA:
            hasil["peringatan"].append(f"Kemungkinan pencilan di {nm}: {f_angka(gb[1])} (Grubbs G = "
                                       f"{f_angka(gb[2], 2)}, p = {f_p(gb[3])}). Periksa data; jangan dibuang tanpa "
                                       "alasan eksperimen.")
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
    elif berpasangan and len({len(g) for g in kelompok}) == 1 and len(kelompok[0]) >= 3:
        if uji not in ("rm_anova", "friedman"):
            uji = "rm_anova" if normal else "friedman"
        X = np.column_stack([np.asarray(g, float) for g in kelompok])
        r = _anova_berulang(X, nama, koreksi) if uji == "rm_anova" else _friedman(X, koreksi)
        hasil.update(r, nama_uji=UJI_BANYAK[uji])
        if uji == "rm_anova" and r["epsilon"] < 1:
            hasil["peringatan"].append(f"Koreksi Greenhouse–Geisser diterapkan (ε = {f_angka(r['epsilon'], 3)}); "
                                       f"p tanpa koreksi = {f_p(r['p_tanpa_koreksi'])}.")
    else:
        if berpasangan:
            hasil["peringatan"].append("Data berpasangan butuh n sama (≥ 3) di semua kolom; dianalisis tidak "
                                       "berpasangan.")
        if uji in ("rm_anova", "friedman"):
            uji = "otomatis"
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
            hasil["posthoc"] = _dunn(kelompok, koreksi)
            hasil["nama_posthoc"] = f"Dunn (koreksi {KOREKSI[koreksi]})"
    hasil["uji"] = uji
    if not normal and uji in ("welch", "student", "t_pasang", "anova", "welch_anova", "dunnett", "rm_anova"):
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


MODEL_DOSIS = {"auto": "Otomatis: 4PL vs 3PL (uji F)", "4pl": "4PL — kemiringan bebas",
               "3pl": "3PL — Hill = ±1 (kemiringan standar)"}


def _aicc(ss, n, k):
    """AICc kuadrat terkecil; k = jumlah parameter model + 1 (varians)."""
    k += 1
    if ss <= 0 or n - k - 1 <= 0:
        return float("nan")
    return n * math.log(ss / n) + 2 * k + 2 * k * (k + 1) / (n - k - 1)


def dosis_respons(konsentrasi, respons, log_x=True, model="4pl"):
    """Regresi nonlinear dosis–respons. model: '4pl' (kemiringan bebas), '3pl' (Hill = ±1), atau 'auto'
    (pilih lewat uji F extra sum-of-squares, α 0,05; AICc ikut dilaporkan). konsentrasi > 0 (bila log_x),
    respons per titik (boleh replikat). Kembalikan dict: parameter model terpilih, IC50 ± CI95, R², kurva,
    perbandingan model."""
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
    tanda = 1.0 if y[np.argmax(lx)] > y[np.argmin(lx)] else -1.0
    p0 = [float(y.min()), float(y.max()), float(np.median(lx)), tanda]
    try:
        par4, cov4 = optimize.curve_fit(model_4pl, lx, y, p0=p0, maxfev=20000)
    except Exception as e:
        return {"galat": f"Kurva tidak konvergen ({type(e).__name__})."}
    h3 = math.copysign(1.0, par4[3] if par4[3] else tanda)

    def m3(xx, bawah, atas, log_ic50):
        return model_4pl(xx, bawah, atas, log_ic50, h3)
    try:
        par3, cov3 = optimize.curve_fit(m3, lx, y, p0=p0[:3], maxfev=20000)
        ss3 = float(((y - m3(lx, *par3)) ** 2).sum())
    except Exception:
        par3 = cov3 = None
        ss3 = float("nan")
    n = len(y)
    ss4 = float(((y - model_4pl(lx, *par4)) ** 2).sum())
    banding = {"ss4": ss4, "ss3": ss3, "aicc4": _aicc(ss4, n, 4), "aicc3": _aicc(ss3, n, 3), "F": None, "p": None}
    if par3 is not None and n > 4 and ss4 > 0:
        F = ((ss3 - ss4) / 1) / (ss4 / (n - 4))
        banding.update(F=float(F), df=(1, n - 4), p=float(stats.f.sf(max(F, 0.0), 1, n - 4)))
        d = banding["aicc3"] - banding["aicc4"]
        if math.isfinite(d):    # bobot Akaike: peluang 4PL lebih tepat
            banding["peluang4"] = float(1 / (1 + math.exp(-d / 2)))
    if model == "auto":
        pakai = "4pl" if (banding["p"] is not None and banding["p"] < ALFA) or par3 is None else "3pl"
    else:
        pakai = "3pl" if model == "3pl" and par3 is not None else "4pl"
    banding["terpilih"] = pakai
    if pakai == "3pl":
        par = [*par3, h3]
        se3 = np.sqrt(np.diag(cov3)) if np.all(np.isfinite(cov3)) else np.full(3, np.nan)
        se = np.array([*se3, 0.0])
        ss_res, dof = ss3, max(1, n - 3)
    else:
        par = list(par4)
        se = np.sqrt(np.diag(cov4)) if np.all(np.isfinite(cov4)) else np.full(4, np.nan)
        ss_res, dof = ss4, max(1, n - 4)
    ss_tot = float(((y - y.mean()) ** 2).sum())
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
    return {"peringatan": peringatan, "model": pakai, "banding": banding,
            "bawah": float(par[0]), "atas": float(par[1]), "log_ic50": float(par[2]), "hill": float(par[3]),
            "ic50": float(10 ** par[2]) if log_x else float(par[2]),
            "ic50_ci": ((float(10 ** lo), float(10 ** hi)) if log_x else (float(lo), float(hi))) if ci_ok else None,
            "r2": r2, "n": int(n), "dof": dof,
            "kurva": (xs.tolist(), model_4pl(xs, *par).tolist()), "titik": (lx.tolist(), y.tolist()),
            "log_x": log_x}


# ------------------------------------------------------------------ ROC
LOG_FPR_MIN = 0.001          # batas bawah logAUC (Mysinger & Shoichet 2010)
LOGAUC_ACAK = (1 - LOG_FPR_MIN) / (3 * math.log(10)) * 100   # 14,46 % untuk tebakan acak


def _urutan(sp, sn):
    """Label (1 = positif) diurutkan dari skor terbaik. Skor sama: negatif didahulukan (konservatif,
    tidak menguntungkan positif secara kebetulan)."""
    semua = np.concatenate([sp, sn])
    label = np.concatenate([np.ones(len(sp)), np.zeros(len(sn))])
    return label[np.lexsort((label, -semua))]


def bedroc(urut, alpha=20.0):
    """BEDROC (Truchon & Bayly 2007) dari label terurut; alpha 20 = 80 % bobot pada 8 % teratas."""
    N, n = len(urut), int(urut.sum())
    if n == 0 or n == N:
        return float("nan")
    r = np.flatnonzero(urut) + 1.0
    ra = n / N
    rie = np.exp(-alpha * r / N).sum() / (ra * (1 - math.exp(-alpha)) / (math.exp(alpha / N) - 1))
    return float(rie * ra * math.sinh(alpha / 2) / (math.cosh(alpha / 2) - math.cosh(alpha / 2 - alpha * ra))
                 + 1 / (1 - math.exp(alpha * (1 - ra))))


def faktor_pengayaan(urut, persen):
    N, n = len(urut), urut.sum()
    k = max(1, math.ceil(N * persen / 100))
    return float(urut[:k].mean() / (n / N)) if n else float("nan")


def log_auc(fpr, tpr):
    """logAUC (%) = rata-rata TPR pada sumbu log10 FPR [0,001; 1] (kurva tangga, konservatif)."""
    fpr, tpr = np.asarray(fpr), np.asarray(tpr)
    u = 10 ** np.linspace(math.log10(LOG_FPR_MIN), 0, 3001)
    i = np.searchsorted(fpr, u, side="right") - 1          # titik ROC terakhir dengan FPR <= u
    return float(np.maximum.accumulate(tpr)[np.clip(i, 0, len(tpr) - 1)].mean() * 100)


def _bootstrap_skrining(sp, sn, alpha, ulang=1000, seed=0):
    """CI 95 % persentil (bootstrap terstratifikasi) untuk EF1%, EF5%, BEDROC."""
    rng = np.random.default_rng(seed)
    N = len(sp) + len(sn)
    ulang = int(max(200, min(ulang, 4e6 / max(N, 1))))
    hasil = {"ef1": [], "ef5": [], "bedroc": []}
    for _ in range(ulang):
        u = _urutan(rng.choice(sp, len(sp)), rng.choice(sn, len(sn)))
        hasil["ef1"].append(faktor_pengayaan(u, 1))
        hasil["ef5"].append(faktor_pengayaan(u, 5))
        hasil["bedroc"].append(bedroc(u, alpha))
    return {k: (float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))) for k, v in hasil.items()}, ulang


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
    urut = _urutan(sp, sn)
    ef = {persen: faktor_pengayaan(urut, persen) for persen in (1, 5, 10)}
    alpha = 20.0
    bd = bedroc(urut, alpha)
    lauc = log_auc(fpr, tpr)
    ci_skr, n_boot = _bootstrap_skrining(sp, sn, alpha)
    N = len(urut)
    langkah = max(1, N // 400)
    kurva_ef = ([k / N for k in range(0, N + 1, langkah)] + [1.0],
                [float(urut[:k].sum() / n1) for k in range(0, N + 1, langkah)] + [1.0])
    arah = "≤" if rendah_positif else "≥"
    makna = ("membedakan kedua kelompok secara bermakna" if p < ALFA
             else "tidak membedakan kedua kelompok secara bermakna")
    kualitas = ("sangat baik" if auc >= 0.9 else "baik" if auc >= 0.8 else "cukup" if auc >= 0.7 else
                "lemah" if auc >= 0.6 else "setara tebakan acak")
    inter = (f"AUC = {f_angka(auc)}" + (f" (CI 95% {f_angka(ci[0])}–{f_angka(ci[1])})" if ci else "")
             + f", p {'< 0,0001' if p < 1e-4 else '= ' + f_p(p)}: skor {makna} (daya pembeda {kualitas}). "
             f"Titik potong optimal (indeks Youden) {arah} {f_angka(potong, 2)}: sensitivitas "
             f"{f_angka(sens * 100, 1)} %, spesifisitas {f_angka(spes * 100, 1)} %. EF1% = {f_angka(ef[1], 1)}, "
             f"EF5% = {f_angka(ef[5], 1)}; BEDROC (α = 20) = {f_angka(bd, 3)}; logAUC = {f_angka(lauc, 1)} % "
             f"(acak {f_angka(LOGAUC_ACAK, 1)} %).")
    met = ("Kemampuan skor membedakan kelompok positif dan negatif dinilai dengan kurva receiver operating "
           "characteristic (ROC). Luas di bawah kurva (AUC) dihitung dengan metode nonparametrik (Mann–Whitney) "
           "beserta interval kepercayaan 95 % metode DeLong; titik potong optimal ditentukan dengan indeks Youden. "
           "Pengayaan dini dinilai dengan faktor pengayaan (EF1%, EF5%), BEDROC (α = 20; Truchon & Bayly 2007) dan "
           "logAUC pada FPR 0,001–1 (Mysinger & Shoichet 2010); interval kepercayaan 95 % EF dan BEDROC dari "
           f"{n_boot} ulangan bootstrap terstratifikasi. Analisis dilakukan dengan VirmoDock (SciPy).")
    peringatan = []
    if auc < 0.5:
        peringatan.append("AUC < 0,5: skor justru membedakan ke arah sebaliknya — periksa pilihan arah "
                          "(“Skor rendah = positif” untuk ΔG docking) atau letak kolom negatif/positif.")
    if min(n0, n1) < 10:
        peringatan.append("Jumlah data kecil (< 10 per kelompok): interval kepercayaan AUC kurang andal.")
    return {"peringatan": peringatan, "bedroc": bd, "alpha": alpha, "logauc": lauc, "ci_skrining": ci_skr,
            "n_boot": n_boot, "kurva_ef": kurva_ef, "auc": auc, "se": se, "ci": ci, "p": p, "potong": float(potong), "sens": sens, "spes": spes, "ef": ef,
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


# ------------------------------------------------------------------ ANOVA dua arah
def _sse(X, y):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    return float(r @ r)


def _kode_efek(lbl, level):
    """Kode efek (sum-to-zero): level terakhir = −1 di semua kolom."""
    M = np.zeros((len(lbl), len(level) - 1))
    for i, v in enumerate(lbl):
        j = level.index(v)
        if j < len(level) - 1:
            M[i, j] = 1
        else:
            M[i, :] = -1
    return M


def anova_dua_arah(y, fa, fb, koreksi="sidak"):
    """ANOVA dua arah dengan interaksi, jumlah kuadrat tipe III (kode efek; sah untuk data tak seimbang).
    y: nilai; fa, fb: label faktor A (baris) & B (kolom) tiap nilai. Uji lanjut: beda level A di dalam tiap
    level B (t memakai MS galat gabungan) dengan koreksi p (bawaan Šidák)."""
    from scipy import stats
    y = np.asarray(y, float)
    la = list(dict.fromkeys(fa))
    lb = list(dict.fromkeys(fb))
    h = {"level_a": la, "level_b": lb, "peringatan": []}
    sel = {(a, b): y[[i for i in range(len(y)) if fa[i] == a and fb[i] == b]] for a in la for b in lb}
    if len(la) < 2 or len(lb) < 2:
        h["galat"] = "Butuh minimal 2 level di faktor A (baris) dan 2 level di faktor B (kolom)."
        return h
    if any(len(v) == 0 for v in sel.values()):
        h["galat"] = "Setiap kombinasi baris × kolom harus berisi minimal satu nilai."
        return h
    N = len(y)
    if N - len(la) * len(lb) < 1:
        h["galat"] = "Butuh ulangan (> 1 nilai per sel) untuk menguji interaksi."
        return h
    A, B = _kode_efek(fa, la), _kode_efek(fb, lb)
    AB = np.column_stack([A[:, i] * B[:, j] for i in range(A.shape[1]) for j in range(B.shape[1])])
    satu = np.ones((N, 1))
    penuh = np.column_stack([satu, A, B, AB])
    sse = _sse(penuh, y)
    df_gal = N - penuh.shape[1]
    ms_gal = sse / df_gal
    baris = []
    for nm, buang, df in (("Faktor A (baris)", A, A.shape[1]), ("Faktor B (kolom)", B, B.shape[1]),
                          ("Interaksi A × B", AB, AB.shape[1])):
        sisa = [m for m in (A, B, AB) if m is not buang]
        ss = _sse(np.column_stack([satu] + sisa), y) - sse
        F = (ss / df) / ms_gal if ms_gal > 0 else float("inf")
        baris.append({"efek": nm, "ss": ss, "df": df, "ms": ss / df, "F": F, "p": float(stats.f.sf(F, df, df_gal)),
                      "eta_p": ss / (ss + sse) if ss + sse else float("nan")})
    baris.append({"efek": "Galat", "ss": sse, "df": df_gal, "ms": ms_gal})
    h["tabel"] = baris
    h["sel"] = {f"{a}|{b}": deskriptif(v.tolist()) for (a, b), v in sel.items()}
    h["data_sel"] = {f"{a}|{b}": v.tolist() for (a, b), v in sel.items()}
    raw, pas = [], []
    for b in lb:
        for i in range(len(la)):
            for j in range(i + 1, len(la)):
                x1, x2 = sel[(la[i], b)], sel[(la[j], b)]
                d = float(x1.mean() - x2.mean())
                se = math.sqrt(ms_gal * (1 / len(x1) + 1 / len(x2)))
                t = d / se if se else float("inf")
                pas.append((b, la[i], la[j], d, se))
                raw.append(float(2 * stats.t.sf(abs(t), df_gal)))
    adj = koreksi_p(raw, koreksi)
    tkrit = stats.t.ppf(0.975, df_gal)
    h["posthoc"] = [(b, a1, a2, d, (d - tkrit * se, d + tkrit * se), q) for (b, a1, a2, d, se), q in zip(pas, adj)]
    h["koreksi"] = koreksi
    seimbang = len({len(v) for v in sel.values()}) == 1
    if not seimbang:
        h["peringatan"].append("Jumlah ulangan per sel tidak sama: dipakai jumlah kuadrat tipe III.")
    # normalitas residu & homogenitas varians antar sel
    resid = np.concatenate([v - v.mean() for v in sel.values()])
    if len(resid) >= 3:
        h["normal_resid"] = normalitas(resid.tolist())
    grup = [v for v in sel.values() if len(v) > 1]
    if len(grup) >= 2:
        bf = stats.levene(*grup, center="median")
        h["varians"] = (float(bf.statistic), float(bf.pvalue))
        if bf.pvalue < ALFA:
            h["peringatan"].append("Varians antar sel tidak homogen (Brown–Forsythe p < 0,05): tafsirkan hati-hati.")
    if h.get("normal_resid") and h["normal_resid"][1] is not None and h["normal_resid"][1] < ALFA:
        h["peringatan"].append("Residu tidak normal (Shapiro–Wilk p < 0,05): pertimbangkan transformasi data.")
    pa, pb_, pab = (x["p"] for x in baris[:3])

    def pt(p):
        return "< 0,0001" if p < 1e-4 else "= " + f_p(p)
    inter = (f"ANOVA dua arah: faktor A F({baris[0]['df']}; {df_gal}) = {f_angka(baris[0]['F'], 2)}, p {pt(pa)}; "
             f"faktor B F({baris[1]['df']}; {df_gal}) = {f_angka(baris[1]['F'], 2)}, p {pt(pb_)}; interaksi "
             f"F({baris[2]['df']}; {df_gal}) = {f_angka(baris[2]['F'], 2)}, p {pt(pab)}.")
    inter += (" Interaksi bermakna: pengaruh faktor A berbeda antar level faktor B — tafsirkan perbandingan per "
              "level B." if pab < ALFA else " Interaksi tidak bermakna: efek utama dapat ditafsirkan langsung.")
    sig = [f"{a1} vs {a2} pada {b} ({bintang(q)})" for b, a1, a2, _d, _c, q in h["posthoc"] if q < ALFA]
    if sig:
        inter += f" Uji lanjut ({KOREKSI[koreksi]}): " + ", ".join(sig) + "."
    met = ("Data dianalisis dengan ANOVA dua arah (faktor A, faktor B, dan interaksinya; jumlah kuadrat tipe III), "
           f"dilanjutkan perbandingan antar level faktor A di setiap level faktor B dengan koreksi {KOREKSI[koreksi]}. "
           "Normalitas residu diuji dengan Shapiro–Wilk dan homogenitas varians dengan Brown–Forsythe. Nilai p < 0,05 "
           "dianggap bermakna. Analisis dilakukan dengan VirmoDock (NumPy/SciPy).")
    h["interpretasi"], h["metode"] = inter, met
    return h
