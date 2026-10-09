"""Grafik modul 'Uji & Grafik': grup (batang/titik/kotak) + braket signifikansi, kurva dosis–respons 4PL,
kurva ROC, dan batang bertumpuk tabel kontingensi.

SVG murni (lihat grafik.py). Palet Okabe–Ito (ramah buta warna) atau abu-abu untuk cetak.
Tampilan diatur lewat dict `gaya` (panel Format): ukuran, huruf, penanda, warna per grup, rentang & skala
sumbu Y, patah sumbu. Setiap fungsi bisa mengisi `daerah` = [(kunci, x0, y0, x1, y1)] (koordinat SVG) agar
elemen grafik bisa diklik untuk diformat.
"""
import math

import numpy as np

from .grafik import Kanvas, fmt, tik
from .uji import bintang, deskriptif

PALET = {"okabe": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"],
         "biru": ["#1f4e8c", "#2b6fd6", "#5b9af0", "#9cc2f5", "#173b6c", "#4a7fc0", "#7aa7e0", "#c4d9f7"],
         "abu": ["#222222", "#555555", "#888888", "#aaaaaa", "#333333", "#666666", "#999999", "#bbbbbb"]}
JENIS_GRAFIK = {"batang": "Batang + titik (rerata ± galat)", "titik": "Titik (rerata ± galat)",
                "kotak": "Kotak & kumis (Tukey)", "median": "Titik (median ± IQR)", "qq": "Q–Q plot (cek normalitas)"}
GALAT = {"sd": "SD", "sem": "SEM", "ci": "CI 95%"}
BENTUK = {"lingkaran": "Lingkaran", "kotak": "Kotak", "segitiga": "Segitiga", "berlian": "Belah ketupat"}

# Nilai None = otomatis. Kunci baru wajib ditambah di sini (gaya_lengkap membuang kunci tak dikenal).
GAYA = {"lebar": 0, "tinggi": 470, "font": 12, "font_label": 13, "font_judul": 15, "font_tanda": 13,
        "tebal": 1.4, "titik": True, "ukuran_titik": 3.4, "bentuk": "lingkaran", "opasitas": 0.28,
        "lebar_batang": 0.55, "kisi": False, "miring": False, "label_x": "",
        "y_min": None, "y_maks": None, "y_langkah": None, "y_log": False, "patah_dari": None, "patah_sampai": None,
        "warna": {}, "acuan": "", "anotasi": "", "pos_anotasi": "kanan_atas"}
POSISI_ANOTASI = {"kiri_atas": "Kiri atas", "kanan_atas": "Kanan atas", "kiri_bawah": "Kiri bawah",
                  "kanan_bawah": "Kanan bawah"}
# kunci yang ikut 'gaya tersimpan' (tampilan saja; teks & rentang sumbu milik data)
KUNCI_PRESET = ("lebar", "tinggi", "font", "font_label", "font_judul", "font_tanda", "tebal", "titik", "ukuran_titik",
                "bentuk", "opasitas", "lebar_batang", "kisi", "miring", "warna")


def gaya_lengkap(g=None):
    d = {k: (dict(v) if isinstance(v, dict) else v) for k, v in GAYA.items()}
    for k, v in (g or {}).items():
        if k in GAYA:
            d[k] = dict(v) if isinstance(v, dict) else v
    return d


def warna_grup(gaya, palet, i):
    w = PALET.get(palet, PALET["okabe"])
    return (gaya.get("warna") or {}).get(str(i)) or w[i % len(w)]


def penanda(bentuk, x, y, r, isi, garis, opas=0.85, lebar_garis=0.6):
    a = f'fill="{isi}" fill-opacity="{opas}" stroke="{garis}" stroke-width="{lebar_garis}"'
    if bentuk == "kotak":
        s = r * 0.9
        return f'<rect x="{x - s:.1f}" y="{y - s:.1f}" width="{2 * s:.1f}" height="{2 * s:.1f}" {a}/>'
    if bentuk == "segitiga":
        s = r * 1.25
        return (f'<path d="M{x:.1f} {y - s:.1f} L{x + s * 0.92:.1f} {y + s * 0.6:.1f} '
                f'L{x - s * 0.92:.1f} {y + s * 0.6:.1f} Z" {a}/>')
    if bentuk == "berlian":
        s = r * 1.25
        return f'<path d="M{x:.1f} {y - s:.1f} L{x + s:.1f} {y:.1f} L{x:.1f} {y + s:.1f} L{x - s:.1f} {y:.1f} Z" {a}/>'
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" {a}/>'


def _galat(d, jenis):
    if d["n"] < 2:
        return 0.0, 0.0
    if jenis == "sem":
        return d["sem"], d["sem"]
    if jenis == "ci":
        return d["rerata"] - d["ci95"][0], d["ci95"][1] - d["rerata"]
    return d["sd"], d["sd"]


class SkalaY:
    """Pemetaan nilai -> piksel sumbu Y: linear, log10, atau linear dengan patah sumbu (dua segmen)."""
    CELAH = 12

    def __init__(self, lo, hi, atas, ph, gaya, batang=False):
        self.atas, self.ph = atas, ph
        self.bawah = atas + ph
        self.log = bool(gaya.get("y_log")) and lo > 0 and not batang
        self.patah = None
        mn, mk, lg = gaya.get("y_min"), gaya.get("y_maks"), gaya.get("y_langkah")
        if self.log:
            l0 = math.floor(math.log10(mn if mn and mn > 0 else lo))
            l1 = math.ceil(math.log10(mk if mk and mk > 0 else hi))
            self.l0, self.l1 = l0, max(l1, l0 + 1)
            self.y0, self.y1 = 10.0 ** self.l0, 10.0 ** self.l1
            self.tik = [10.0 ** k for k in range(self.l0, self.l1 + 1)]
            return
        a = mn if mn is not None else lo
        b = mk if mk is not None else hi
        if b <= a:
            b = a + 1
        if lg and lg > 0 and (b - a) / lg <= 60:
            t0 = math.floor(a / lg + 1e-9) * lg if mn is None else a
            self.tik = [round(t0 + i * lg, 10) for i in range(int(math.ceil((b - t0) / lg - 1e-9)) + 1)]
        else:
            self.tik = tik(a, b, 6)[0]
            if mn is not None:
                self.tik = [v for v in self.tik if v >= mn - 1e-9]
                if not self.tik or self.tik[0] > mn + 1e-9:
                    self.tik.insert(0, mn)
            if mk is not None:
                self.tik = [v for v in self.tik if v <= mk + 1e-9]
                if self.tik[-1] < mk - 1e-9:
                    self.tik.append(mk)
        self.y0, self.y1 = self.tik[0], self.tik[-1]
        pa, pb = gaya.get("patah_dari"), gaya.get("patah_sampai")
        if pa is not None and pb is not None and self.y0 < pa < pb < self.y1:
            r1, r2 = pa - self.y0, self.y1 - pb
            f1 = min(0.75, max(0.3, r1 / (r1 + r2)))
            tinggi = ph - self.CELAH
            self.h1, self.h2 = tinggi * f1, tinggi * (1 - f1)
            self.patah = (pa, pb)
            bawah_t = [v for v in tik(self.y0, pa, max(2, round(6 * f1)))[0] if self.y0 - 1e-9 <= v <= pa + 1e-9]
            atas_t = [v for v in tik(pb, self.y1, max(2, round(6 * (1 - f1))))[0] if pb - 1e-9 <= v <= self.y1 + 1e-9]
            self.tik = bawah_t + atas_t

    def Y(self, v):
        if self.log:
            lv = math.log10(max(v, 1e-300))
            return self.atas + (self.l1 - lv) / (self.l1 - self.l0) * self.ph
        if not self.patah:
            return self.atas + (self.y1 - v) / (self.y1 - self.y0) * self.ph
        pa, pb = self.patah
        if v >= pb:
            return self.atas + (self.y1 - v) / (self.y1 - pb) * self.h2
        v = max(v, self.y0) if v < pa else pa
        return self.bawah - (v - self.y0) / (pa - self.y0) * self.h1

    def celah(self):
        """(y_atas_px, y_bawah_px) celah patah sumbu, atau None."""
        if not self.patah:
            return None
        return self.atas + self.h2, self.atas + self.h2 + self.CELAH

    def potong(self, ya, yb):
        """Ruas vertikal piksel [ya, yb] dikurangi celah patah -> daftar ruas."""
        a, b = min(ya, yb), max(ya, yb)
        c = self.celah()
        if not c or b <= c[0] or a >= c[1]:
            return [(a, b)]
        out = []
        if a < c[0]:
            out.append((a, c[0]))
        if b > c[1]:
            out.append((c[1], b))
        return out

    def label(self, v):
        if self.log:
            k = round(math.log10(v))
            return fmt(v, max(0, -k)) if -3 <= k <= 4 else f"10^{k}"
        if not hasattr(self, "_des"):   # desimal terkecil yang menampilkan semua tik dengan tepat
            self._des = max(next((d for d in range(7) if abs(round(t, d) - t) < 1e-9 * max(1, abs(t))), 6)
                            for t in self.tik)
        return fmt(v, self._des)


def _sumbu_y(c, s, gaya, label_y, daerah):
    """Garis sumbu Y (terputus bila patah), tik, label tik, label sumbu."""
    w = c.w
    tb = gaya["tebal"]
    for ya, yb in s.potong(c.atas, s.bawah):
        c.out.append(f'<line x1="{c.kiri}" y1="{ya:.1f}" x2="{c.kiri}" y2="{yb:.1f}" stroke="{w["garis"]}" '
                     f'stroke-width="{tb}"/>')
    ce = s.celah()
    if ce:
        for yy in ce:   # tanda patah //
            c.out.append(f'<line x1="{c.kiri - 7}" y1="{yy + 3:.1f}" x2="{c.kiri + 7}" y2="{yy - 3:.1f}" '
                         f'stroke="{w["garis"]}" stroke-width="{tb}"/>')
    lebar_lbl = 0
    for v in s.tik:
        y = s.Y(v)
        if gaya.get("kisi"):
            c.out.append(f'<line x1="{c.kiri}" y1="{y:.1f}" x2="{c.kiri + c.pw}" y2="{y:.1f}" stroke="{w["kisi"]}" '
                         f'stroke-width="1"/>')
        c.out.append(f'<line x1="{c.kiri - 6}" y1="{y:.1f}" x2="{c.kiri}" y2="{y:.1f}" stroke="{w["garis"]}" '
                     f'stroke-width="{tb}"/>')
        t = s.label(v)
        lebar_lbl = max(lebar_lbl, len(t))
        c.teks(c.kiri - 10, y + gaya["font"] * 0.35, t, gaya["font"], "end")
    if s.log:   # tik minor 2..9
        for k in range(s.l0, s.l1):
            for m in range(2, 10):
                y = s.Y(m * 10.0 ** k)
                c.out.append(f'<line x1="{c.kiri - 3}" y1="{y:.1f}" x2="{c.kiri}" y2="{y:.1f}" stroke="{w["garis"]}" '
                             f'stroke-width="1"/>')
    x_lbl = max(12, c.kiri - 16 - lebar_lbl * gaya["font"] * 0.58 - gaya["font_label"] * 0.4)
    if label_y:
        c.teks(x_lbl, c.atas + c.ph / 2, label_y, gaya["font_label"], "middle", putar=-90)
    if daerah is not None:
        daerah.append(("sumbu_y", c.kiri - 14 - lebar_lbl * gaya["font"] * 0.58, c.atas - 6, c.kiri + 4, s.bawah + 6))
        daerah.append(("label_y", x_lbl - gaya["font_label"], c.atas, x_lbl + gaya["font_label"] * 0.4,
                       s.bawah))


def _judul(c, judul, gaya, daerah):
    if judul:
        c.teks(c.kiri, 8 + gaya["font_judul"] * 1.15, judul, gaya["font_judul"], tebal=True)
    if daerah is not None:
        daerah.append(("judul", c.kiri - 4, 2, c.lebar - 4, 14 + gaya["font_judul"] * 1.2))


def _tinggi_judul(judul, gaya):
    return (22 + gaya["font_judul"] * 1.4) if judul else 20


def baca_acuan(teks):
    """'−8,2=Ligan asli; −7' -> [(−8.2, 'Ligan asli'), (−7.0, '')]."""
    out = []
    for bag in (teks or "").split(";"):
        nilai, _, label = bag.partition("=")
        t = nilai.strip().replace("−", "-").replace(",", ".")
        try:
            out.append((float(t), label.strip()))
        except ValueError:
            continue
    return out


def _hiasan(c, gaya, s=None):
    """Garis acuan horizontal (gaya['acuan']) dan anotasi teks di pojok area plot. s: skala Y (SkalaY atau Kanvas
    yang punya Y, y0, y1)."""
    w = c.w
    f = gaya["font"]
    if s is not None:
        y0, y1 = min(s.y0, s.y1), max(s.y0, s.y1)
        celah = s.celah() if hasattr(s, "celah") else None
        for v, label in baca_acuan(gaya.get("acuan")):
            if not y0 <= v <= y1:
                continue
            y = s.Y(v)
            if celah and celah[0] < y < celah[1]:
                continue
            c.out.append(f'<line x1="{c.kiri:.1f}" y1="{y:.1f}" x2="{c.kiri + c.pw:.1f}" y2="{y:.1f}" '
                         f'stroke="{w["tinta2"]}" stroke-width="{max(1.0, gaya["tebal"] * 0.8):.2f}" '
                         f'stroke-dasharray="6 4"/>')
            teks = (label + " " if label else "") + fmt(v, 2)
            c.teks(c.kiri + c.pw - 4, y - 5, teks, f - 1, "end", warna_=w["tinta2"])
    a = (gaya.get("anotasi") or "").strip()
    if a:
        pos = gaya.get("pos_anotasi") or "kanan_atas"
        kanan = pos.startswith("kanan")
        x = c.kiri + c.pw - 8 if kanan else c.kiri + 10
        baris = [b.strip() for b in a.split("|") if b.strip()]
        tinggi = len(baris) * (f + 4)
        y = c.atas + 8 + f if pos.endswith("atas") else c.atas + c.ph - 8 - tinggi + f
        for k, b in enumerate(baris):
            c.teks(x, y + k * (f + 4), b, f, "end" if kanan else "start")


def grafik_grup(nama, kelompok, jenis="batang", galat="sd", posthoc=None, tanda="bintang", tampil_ns=False,
                palet="okabe", label_y="", judul="", gelap=False, transparan=False, lebar=None, gaya=None,
                daerah=None):
    gaya = gaya_lengkap(gaya)
    k = len(kelompok)
    f = gaya["font"]
    lebar = lebar or gaya["lebar"] or max(420, 110 + 92 * k)
    des = [deskriptif(g) for g in kelompok]
    sig = [(i, j, p) for i, j, _d, _c, p in (posthoc or []) if p is not None and (tampil_ns or p < 0.05)] if tanda else []
    n_braket = len(sig)
    jarak_braket = 9 + gaya["font_tanda"]
    atas = _tinggi_judul(judul, gaya) + jarak_braket * n_braket
    pjg = max((len(t) for t in nama), default=0)
    bawah = (18 + f * 1.6 + (pjg * f * 0.45 if gaya["miring"] else (14 if pjg > 10 else 0))
             + (gaya["font_label"] * 1.8 if gaya["label_x"] else 0))
    kiri = 50 + f * 2.4 + gaya["font_label"]
    c = Kanvas(lebar, gaya["tinggi"] + jarak_braket * n_braket, gelap, transparan, "", kiri=kiri, kanan=20,
               atas=atas, bawah=bawah)
    _judul(c, judul, gaya, daerah)
    if daerah is not None:
        daerah.append(("braket", c.kiri, atas - jarak_braket * n_braket - 4, c.kiri + c.pw, atas + 4))
    semua = [v for g in kelompok for v in g]
    if not semua:
        return c.selesai(), (c.lebar, c.tinggi)
    ujung = []
    for d in des:
        if not d["n"]:
            continue
        if jenis in ("kotak", "median"):
            ujung += [d["min"], d["maks"]]
        else:
            lo, hi = _galat(d, galat)
            ujung += [d["rerata"] - lo, d["rerata"] + hi]
    lo_y, hi_y = min(semua + ujung), max(semua + ujung)
    if jenis == "batang" and not gaya["y_log"]:
        lo_y, hi_y = min(0.0, lo_y), max(0.0, hi_y)
    rentang = (hi_y - lo_y) or 1.0
    s = SkalaY(lo_y - 0.04 * rentang * (jenis != "batang"), hi_y + 0.06 * rentang, c.atas, c.ph, gaya,
               batang=(jenis == "batang" and lo_y <= 0))
    c.x0, c.x1, c.y0, c.y1 = 0, k, s.y0, s.y1
    w = c.w
    tb = gaya["tebal"]
    bawah_px = s.bawah
    c.out.append(f'<line x1="{c.kiri}" y1="{bawah_px}" x2="{c.kiri + c.pw}" y2="{bawah_px}" stroke="{w["garis"]}" '
                 f'stroke-width="{tb}"/>')
    _sumbu_y(c, s, gaya, label_y, daerah)
    lebar_kat = c.pw / k
    rng = np.random.default_rng(7)
    puncak = []

    def vgaris(x, ya, yb, col, lebar_):
        for a, b in s.potong(ya, yb):
            c.out.append(f'<line x1="{x:.1f}" y1="{a:.1f}" x2="{x:.1f}" y2="{b:.1f}" stroke="{col}" '
                         f'stroke-width="{lebar_}"/>')

    def kotak(x, ya, yb, bw, col, opas, lebar_):
        for a, b in s.potong(ya, yb):
            c.out.append(f'<rect x="{x - bw / 2:.1f}" y="{a:.1f}" width="{bw:.1f}" height="{max(1.0, b - a):.1f}" '
                         f'fill="{col}" fill-opacity="{opas}" stroke="{col}" stroke-width="{lebar_}"/>')

    y_teks = bawah_px + 8 + f
    for i, (g, d) in enumerate(zip(kelompok, des)):
        cx = c.kiri + (i + 0.5) * lebar_kat
        col = warna_grup(gaya, palet, i)
        if gaya["miring"]:
            c.teks(cx + 4, y_teks - 2, nama[i], f, "end", putar=-40)
        else:
            c.teks(cx, y_teks, nama[i], f, "middle")
        c.out.append(f'<line x1="{cx:.1f}" y1="{bawah_px}" x2="{cx:.1f}" y2="{bawah_px + 6}" stroke="{w["garis"]}" '
                     f'stroke-width="{tb}"/>')
        if daerah is not None:
            daerah.append((f"grup:{i}", cx - lebar_kat * 0.42, c.atas, cx + lebar_kat * 0.42, bawah_px))
        if not d["n"]:
            puncak.append(s.Y(s.y0))
            continue
        bw = min(56 * (gaya["lebar_batang"] / 0.55), lebar_kat * gaya["lebar_batang"])
        r_tt = gaya["ukuran_titik"]
        if jenis == "kotak":
            q1, q3, med = d["q1"], d["q3"], d["median"]
            iqr = q3 - q1
            ga = [v for v in g if v >= q1 - 1.5 * iqr]
            gb = [v for v in g if v <= q3 + 1.5 * iqr]
            kb, ka = min(ga) if ga else q1, max(gb) if gb else q3
            vgaris(cx, s.Y(kb), s.Y(ka), col, 1.5)
            for v in (kb, ka):
                c.out.append(f'<line x1="{cx - bw / 4:.1f}" y1="{s.Y(v):.1f}" x2="{cx + bw / 4:.1f}" y2="{s.Y(v):.1f}" '
                             f'stroke="{col}" stroke-width="1.5"/>')
            kotak(cx, s.Y(q3), s.Y(q1), bw, col, gaya["opasitas"] * 0.65, 1.5)
            c.out.append(f'<line x1="{cx - bw / 2:.1f}" y1="{s.Y(med):.1f}" x2="{cx + bw / 2:.1f}" y2="{s.Y(med):.1f}" '
                         f'stroke="{col}" stroke-width="2.4"/>')
            for v in g:
                if v < kb or v > ka:   # pencilan
                    c.out.append(penanda(gaya["bentuk"], cx, s.Y(v), r_tt * 0.95, "none", col, 0, 1))
            puncak.append(s.Y(max(g)))
            continue
        if jenis == "batang":
            dasar = max(s.y0, min(0.0, s.y1)) if not s.log else s.y0
            kotak(cx, s.Y(dasar), s.Y(d["rerata"]), bw, col, gaya["opasitas"], 1.5)
        if gaya["titik"]:   # titik individu (jitter)
            for v in g:
                jx = cx + (rng.random() - 0.5) * bw * 0.6
                c.out.append(penanda(gaya["bentuk"], jx, s.Y(v), r_tt, col, w["latar"]))
        if jenis == "median":
            pusat, lo, hi = d["median"], d["median"] - d["q1"], d["q3"] - d["median"]
        else:
            pusat, (lo, hi) = d["rerata"], _galat(d, galat)
        if not gaya["titik"] and jenis != "batang":   # tanpa titik individu: penanda besar di pusat
            c.out.append(penanda(gaya["bentuk"], cx, s.Y(pusat), r_tt * 1.6, col, w["latar"], 1, 1))
        else:
            c.out.append(f'<line x1="{cx - bw / 2.6:.1f}" y1="{s.Y(pusat):.1f}" x2="{cx + bw / 2.6:.1f}" '
                         f'y2="{s.Y(pusat):.1f}" stroke="{w["tinta"]}" stroke-width="2.2"/>')
        if lo or hi:
            bwah = pusat - lo if not s.log else max(pusat - lo, s.y0)
            vgaris(cx, s.Y(bwah), s.Y(pusat + hi), w["tinta"], 1.5)
            for v in (bwah, pusat + hi):
                c.out.append(f'<line x1="{cx - bw / 6:.1f}" y1="{s.Y(v):.1f}" x2="{cx + bw / 6:.1f}" '
                             f'y2="{s.Y(v):.1f}" stroke="{w["tinta"]}" stroke-width="1.5"/>')
        puncak.append(min(s.Y(max(g)), s.Y(pusat + hi)))
    if daerah is not None:
        daerah.append(("sumbu_x", c.kiri, bawah_px + 2, c.kiri + c.pw, c.tinggi - 2))
    if gaya["label_x"]:
        c.teks(c.kiri + c.pw / 2, c.tinggi - 10, gaya["label_x"], gaya["font_label"], "middle")
    _hiasan(c, gaya, s)
    # braket signifikansi: urut dari jarak terpendek, ditumpuk agar tidak bertabrakan
    terpasang = []
    for i, j, p in sorted(sig, key=lambda t: (abs(t[1] - t[0]), t[0])):
        a, b = min(i, j), max(i, j)
        y = min(puncak[a:b + 1]) - 14
        for pa, pb, py in terpasang:          # di atas braket lain yang rentangnya beririsan
            if not (b < pa or a > pb):
                y = min(y, py - jarak_braket)
        terpasang.append((a, b, y))
        xa, xb = c.kiri + (a + 0.5) * lebar_kat, c.kiri + (b + 0.5) * lebar_kat
        c.out.append(f'<path d="M{xa:.1f} {y + 6:.1f} V{y:.1f} H{xb:.1f} V{y + 6:.1f}" fill="none" '
                     f'stroke="{w["tinta"]}" stroke-width="1.2"/>')
        ft = gaya["font_tanda"] * (0.85 if tanda == "eksak" else 1)
        c.teks((xa + xb) / 2, y - 4, bintang(p, tanda == "eksak"), ft, "middle")
    return c.selesai(), (c.lebar, c.tinggi)


def grafik_dosis(h, label_x="Konsentrasi", label_y="Respons (%)", judul="", gelap=False, transparan=False,
                 warna_="#0072B2", gaya=None, daerah=None):
    """h: hasil uji.dosis_respons. Sumbu x log10 (dekade), titik rerata ± SD per konsentrasi, kurva 4PL, garis IC50."""
    gaya = gaya_lengkap(gaya)
    warna_ = (gaya.get("warna") or {}).get("0") or warna_
    f = gaya["font"]
    W, H = gaya["lebar"] or 720, max(360, gaya["tinggi"] + 50)
    c = Kanvas(W, H, gelap, transparan, "", kiri=50 + f * 2.4 + gaya["font_label"], kanan=24,
               atas=_tinggi_judul(judul, gaya), bawah=30 + f * 1.4 + gaya["font_label"] * 1.6)
    _judul(c, judul, gaya, daerah)
    if h.get("galat"):
        c.teks(c.kiri, c.atas + 30, h["galat"], 13)
        return c.selesai(), (W, H)
    lx, y = np.asarray(h["titik"][0]), np.asarray(h["titik"][1])
    kx, ky = h["kurva"]
    xs = list(kx) + list(lx)
    if h["log_x"]:
        c.x0, c.x1 = math.floor(min(xs)), math.ceil(max(xs))
    else:
        tx = tik(min(xs), max(xs), 7)[0]
        c.x0, c.x1 = tx[0], tx[-1]
    rata = {}
    for ux in sorted(set(lx.tolist())):
        v = y[lx == ux]
        rata[ux] = (float(v.mean()), float(v.std(ddof=1)) if len(v) > 1 else 0.0)
    ys = list(ky) + [m - s_ for m, s_ in rata.values()] + [m + s_ for m, s_ in rata.values()]
    lo, hi = min(ys), max(ys)
    pad = 0.04 * ((hi - lo) or 1)
    s = SkalaY(lo - pad, hi + pad, c.atas, c.ph, dict(gaya, y_log=False))
    c.y0, c.y1 = s.y0, s.y1
    w = c.w
    tb = gaya["tebal"]
    b = s.bawah
    c.out.append(f'<line x1="{c.kiri}" y1="{b}" x2="{c.kiri + c.pw}" y2="{b}" stroke="{w["garis"]}" '
                 f'stroke-width="{tb}"/>')
    _sumbu_y(c, s, gaya, label_y, daerah)
    if h["log_x"]:
        tik_x = list(range(int(c.x0), int(c.x1) + 1))
        for v in range(int(c.x0), int(c.x1)):
            for m in range(2, 10):
                xv = v + math.log10(m)
                c.out.append(f'<line x1="{c.X(xv):.1f}" y1="{b}" x2="{c.X(xv):.1f}" y2="{b + 3}" '
                             f'stroke="{w["garis"]}"/>')
    else:
        tik_x = tik(c.x0, c.x1, 7)[0]
    for v in tik_x:
        c.out.append(f'<line x1="{c.X(v):.1f}" y1="{b}" x2="{c.X(v):.1f}" y2="{b + 6}" stroke="{w["garis"]}" '
                     f'stroke-width="{tb}"/>')
        c.teks(c.X(v), b + 8 + f, fmt(10 ** v, max(0, -v)) if h["log_x"] else fmt(v), f, "middle")
    lx_teks = (gaya["label_x"] or label_x) + (" (skala log)" if h["log_x"] else "")
    c.teks(c.kiri + c.pw / 2, c.tinggi - 12, lx_teks, gaya["font_label"], "middle")
    if daerah is not None:
        daerah.append(("sumbu_x", c.kiri, b + 2, c.kiri + c.pw, c.tinggi - 2))
        daerah.append(("data", c.kiri + 4, c.atas + 4, c.kiri + c.pw, b - 2))
    titik = []
    pts = " ".join(f"{c.X(a):.1f},{s.Y(v):.1f}" for a, v in zip(kx, ky)
                   if s.y0 <= v <= s.y1 and not (s.patah and s.patah[0] < v < s.patah[1]))
    c.out.append(f'<polyline points="{pts}" fill="none" stroke="{warna_}" stroke-width="{1.6 * tb:.1f}"/>')
    for ux, (m, sd) in rata.items():
        titik.append((ux, m))
        if sd:
            for ya, yb in s.potong(s.Y(m - sd), s.Y(m + sd)):
                c.out.append(f'<line x1="{c.X(ux):.1f}" y1="{ya:.1f}" x2="{c.X(ux):.1f}" y2="{yb:.1f}" '
                             f'stroke="{w["tinta"]}" stroke-width="1.3"/>')
            for e in (m - sd, m + sd):
                c.out.append(f'<line x1="{c.X(ux) - 4:.1f}" y1="{s.Y(e):.1f}" x2="{c.X(ux) + 4:.1f}" '
                             f'y2="{s.Y(e):.1f}" stroke="{w["tinta"]}" stroke-width="1.3"/>')
        c.out.append(penanda(gaya["bentuk"], c.X(ux), s.Y(m), gaya["ukuran_titik"] * 1.35, warna_, w["latar"], 1, 1))
    # IC50
    _hiasan(c, gaya, s)
    xi = h["log_ic50"] if h["log_x"] else h["ic50"]
    if c.x0 <= xi <= c.x1:
        yi = (h["atas"] + h["bawah"]) / 2
        c.out.append(f'<path d="M{c.X(xi):.1f} {b} V{s.Y(yi):.1f} H{c.kiri}" fill="none" stroke="{w["tinta2"]}" '
                     f'stroke-dasharray="5 4" stroke-width="1.1"/>')
    ci = h.get("ic50_ci")
    t = f"IC₅₀ = {fmt(h['ic50'], 3)}" + (f" (CI 95% {fmt(ci[0], 3)}–{fmt(ci[1], 3)})" if ci else "")
    t2 = f"Hill = {fmt(h['hill'], 2)} · R² = {fmt(h['r2'], 3)} · n = {h['n']}"
    naik = h["hill"] > 0
    xt = c.kiri + 12
    yt = c.atas + 6 + f if naik else s.bawah - 10 - f * 1.5
    c.teks(xt, yt, t, f, tebal=True)
    c.teks(xt, yt + f * 1.5, t2, f - 1, warna_=w["tinta2"])
    return c.selesai(), (W, H)


KURVA_ROC = {"roc": "Kurva ROC", "semilog": "ROC semilog (logAUC, pengayaan dini)",
             "enrich": "Kurva pengayaan (enrichment)"}


def grafik_roc(h, judul="", gelap=False, transparan=False, gaya=None, daerah=None, mode="roc"):
    """h: hasil uji.roc. mode 'roc': ROC + diagonal acak + AUC (CI 95 %) + titik Youden; 'semilog': sumbu FPR
    log10 0,1–100 % (menonjolkan pengayaan dini) + logAUC; 'enrich': % positif ditemukan vs % data teratas,
    dengan garis ideal & acak, penanda EF1%/EF5% + BEDROC."""
    gaya = gaya_lengkap(gaya)
    f = gaya["font"]
    warna_ = (gaya.get("warna") or {}).get("0") or "#0072B2"
    W = gaya["lebar"] or 560
    sisi = W - (50 + f * 2.4 + gaya["font_label"]) - 24
    H = _tinggi_judul(judul, gaya) + sisi + 30 + f * 1.4 + gaya["font_label"] * 1.6
    c = Kanvas(W, H, gelap, transparan, "", kiri=50 + f * 2.4 + gaya["font_label"], kanan=24,
               atas=_tinggi_judul(judul, gaya), bawah=30 + f * 1.4 + gaya["font_label"] * 1.6)
    _judul(c, judul, gaya, daerah)
    if h.get("galat"):
        c.teks(c.kiri, c.atas + 30, h["galat"], 13)
        return c.selesai(), (W, H)
    c.f_tik = f
    w = c.w
    tebal = 1.6 * gaya["tebal"]
    bawah = c.atas + c.ph
    if mode == "semilog":
        c.x0, c.x1, c.y0, c.y1 = -3, 0, 0, 100
        if gaya["kisi"]:
            for v in (20, 40, 60, 80):
                c.out.append(f'<line x1="{c.kiri}" y1="{c.Y(v):.1f}" x2="{c.kiri + c.pw}" y2="{c.Y(v):.1f}" '
                             f'stroke="{w["kisi"]}"/>')
        c.out.append(f'<line x1="{c.kiri}" y1="{bawah}" x2="{c.kiri + c.pw}" y2="{bawah}" stroke="{w["garis"]}"/>')
        c.out.append(f'<line x1="{c.kiri}" y1="{c.atas}" x2="{c.kiri}" y2="{bawah}" stroke="{w["garis"]}"/>')
        for k, t in ((-3, "0,1"), (-2, "1"), (-1, "10"), (0, "100")):
            c.out.append(f'<line x1="{c.X(k):.1f}" y1="{bawah}" x2="{c.X(k):.1f}" y2="{bawah + 5}" stroke="{w["garis"]}"/>')
            c.teks(c.X(k), bawah + 8 + f, t, f, "middle")
            for m in range(2, 10):
                if k < 0:
                    xv = k + math.log10(m)
                    c.out.append(f'<line x1="{c.X(xv):.1f}" y1="{bawah}" x2="{c.X(xv):.1f}" y2="{bawah + 3}" '
                                 f'stroke="{w["garis"]}"/>')
        for v in (0, 20, 40, 60, 80, 100):
            c.out.append(f'<line x1="{c.kiri - 5}" y1="{c.Y(v):.1f}" x2="{c.kiri}" y2="{c.Y(v):.1f}" stroke="{w["garis"]}"/>')
            c.teks(c.kiri - 8, c.Y(v) + 4, str(v), f, "end")
        lx = lambda a: max(-3.0, math.log10(a)) if a > 0 else -3.0   # noqa: E731
        acak = " ".join(f"{c.X(u):.1f},{c.Y(100 * 10 ** u):.1f}" for u in np.linspace(-3, 0, 120))
        c.out.append(f'<polyline points="{acak}" fill="none" stroke="{w["tinta2"]}" stroke-dasharray="5 4" '
                     f'stroke-width="1"/>')
        titik, lalu = [], 0.0
        for a, b in zip(h["fpr"], h["tpr"]):      # kurva tangga pada skala log
            titik += [(lx(a), lalu), (lx(a), b)]
            lalu = b
        titik.append((0, lalu))
        pts = " ".join(f"{c.X(a):.1f},{c.Y(100 * b):.1f}" for a, b in titik)
        c.out.append(f'<polyline points="{pts}" fill="none" stroke="{warna_}" stroke-width="{tebal:.1f}" '
                     f'stroke-linejoin="round"/>')
        lbl_x, lbl_y = "FPR = 100 − spesifisitas (%, skala log)", "Sensitivitas (%)"
        from .uji import LOGAUC_ACAK
        t1 = f"logAUC = {fmt(h['logauc'], 1)} % (acak {fmt(LOGAUC_ACAK, 1)} %)"
        t2 = f"logAUC terkoreksi = {fmt(h['logauc'] - LOGAUC_ACAK, 1)} % · AUC = {fmt(h['auc'], 3)}"
        c.teks(c.kiri + 10, c.atas + 6 + f, t1, f, tebal=True)
        c.teks(c.kiri + 10, c.atas + 8 + f * 2.4, t2, f - 1, warna_=w["tinta2"])
    elif mode == "enrich":
        c.sumbu([0, 100], [0, 100], "", "", 0, 0, kisi=gaya["kisi"], tik_x=[0, 20, 40, 60, 80, 100])
        n1, N = h["n1"], h["n0"] + h["n1"]
        ra = n1 / N * 100
        c.out.append(f'<line x1="{c.X(0):.1f}" y1="{c.Y(0):.1f}" x2="{c.X(100):.1f}" y2="{c.Y(100):.1f}" '
                     f'stroke="{w["tinta2"]}" stroke-dasharray="5 4" stroke-width="1"/>')
        c.out.append(f'<polyline points="{c.X(0):.1f},{c.Y(0):.1f} {c.X(ra):.1f},{c.Y(100):.1f} '
                     f'{c.X(100):.1f},{c.Y(100):.1f}" fill="none" stroke="{w["tinta2"]}" stroke-width="1" '
                     f'stroke-dasharray="2 3"/>')
        c.teks(c.X(ra) + 6, c.Y(100) + 14, "ideal", f - 1, warna_=w["tinta2"])
        xs, ys = h["kurva_ef"]
        pts = " ".join(f"{c.X(100 * a):.1f},{c.Y(100 * b):.1f}" for a, b in zip(xs, ys))
        c.out.append(f'<polyline points="{pts}" fill="none" stroke="{warna_}" stroke-width="{tebal:.1f}" '
                     f'stroke-linejoin="round"/>')
        for persen in (1, 5):
            xv = c.X(persen)
            c.out.append(f'<line x1="{xv:.1f}" y1="{c.atas}" x2="{xv:.1f}" y2="{bawah}" stroke="{w["tinta2"]}" '
                         f'stroke-width="0.8" stroke-dasharray="1 3"/>')
        lbl_x, lbl_y = "Data teratas yang diperiksa (%)", "Positif ditemukan (%)"
        c.teks(c.X(100) - 8, c.Y(0) - 12 - f * 1.5, f"BEDROC (α = 20) = {fmt(h['bedroc'], 3)}", f, "end", tebal=True)
        c.teks(c.X(100) - 8, c.Y(0) - 12, f"EF1% = {fmt(h['ef'][1], 1)} · EF5% = {fmt(h['ef'][5], 1)} · "
                                          f"EF10% = {fmt(h['ef'][10], 1)}", f - 1, "end", warna_=w["tinta2"])
    else:
        c.sumbu([0, 100], [0, 100], "", "", 0, 0, kisi=gaya["kisi"], tik_x=[0, 20, 40, 60, 80, 100])
        c.out.append(f'<line x1="{c.X(0):.1f}" y1="{c.Y(0):.1f}" x2="{c.X(100):.1f}" y2="{c.Y(100):.1f}" '
                     f'stroke="{w["tinta2"]}" stroke-dasharray="5 4" stroke-width="1"/>')
        pts = " ".join(f"{c.X(100 * a):.1f},{c.Y(100 * b):.1f}" for a, b in zip(h["fpr"], h["tpr"]))
        c.out.append(f'<polyline points="{pts}" fill="none" stroke="{warna_}" stroke-width="{tebal:.1f}" '
                     f'stroke-linejoin="round"/>')
        yx, yy = 100 * (1 - h["spes"]), 100 * h["sens"]
        c.out.append(penanda(gaya["bentuk"], c.X(yx), c.Y(yy), gaya["ukuran_titik"] * 1.5, warna_, w["latar"], 1, 1.2))
        c.teks(c.X(yx) + 9, c.Y(yy) + 14, f"potong {fmt(h['potong'], 2)}", f - 1, warna_=w["tinta2"])
        ci = h.get("ci")
        t = f"AUC = {fmt(h['auc'], 3)}" + (f" (CI 95% {fmt(ci[0], 3)}–{fmt(ci[1], 3)})" if ci else "")
        c.teks(c.X(100) - 8, c.Y(0) - 12 - f * 1.5, t, f, "end", tebal=True)
        c.teks(c.X(100) - 8, c.Y(0) - 12, f"n positif = {h['n1']} · n negatif = {h['n0']}", f - 1, "end",
               warna_=w["tinta2"])
        lbl_x, lbl_y = "100 − Spesifisitas (%)", "Sensitivitas (%)"
    _hiasan(c, gaya)
    c.teks(c.kiri + c.pw / 2, c.tinggi - 12, gaya["label_x"] or lbl_x, gaya["font_label"], "middle")
    c.teks(18 + gaya["font_label"] * 0.2, c.atas + c.ph / 2, lbl_y, gaya["font_label"], "middle", putar=-90)
    if daerah is not None:
        daerah.append(("data", c.kiri + 4, c.atas + 4, c.kiri + c.pw, c.atas + c.ph - 2))
        daerah.append(("sumbu_x", c.kiri, c.atas + c.ph + 2, c.kiri + c.pw, c.tinggi - 2))
    return c.selesai(), (W, H)


def grafik_kontingensi(h, label_y="Persentase (%)", judul="", gelap=False, transparan=False, palet="okabe",
                       gaya=None, daerah=None):
    """Batang bertumpuk 100 % per baris tabel (kelompok), segmen = kategori kolom, berlabel jumlah."""
    gaya = gaya_lengkap(gaya)
    f = gaya["font"]
    baris, kolom, obs = h["baris"], h["kolom"], np.asarray(h["obs"], float)
    r = len(baris)
    legenda = max(len(t) for t in kolom) * f * 0.6 + 40
    W = gaya["lebar"] or int(max(440, 150 + 100 * r + legenda))
    pjg = max((len(t) for t in baris), default=0)
    c = Kanvas(W, gaya["tinggi"], gelap, transparan, "", kiri=50 + f * 2.4 + gaya["font_label"],
               kanan=20 + legenda, atas=_tinggi_judul(judul, gaya),
               bawah=18 + f * 1.6 + (pjg * f * 0.45 if gaya["miring"] else 0) + (
                   gaya["font_label"] * 1.8 if gaya["label_x"] else 0))
    _judul(c, judul, gaya, daerah)
    s = SkalaY(0, 100, c.atas, c.ph, dict(gaya, y_min=0, y_maks=100, y_log=False, patah_dari=None,
                                          patah_sampai=None, y_langkah=gaya.get("y_langkah") or 20))
    c.x0, c.x1, c.y0, c.y1 = 0, r, 0, 100
    w = c.w
    c.out.append(f'<line x1="{c.kiri}" y1="{s.bawah}" x2="{c.kiri + c.pw}" y2="{s.bawah}" stroke="{w["garis"]}" '
                 f'stroke-width="{gaya["tebal"]}"/>')
    _sumbu_y(c, s, gaya, label_y, daerah)
    lk = c.pw / r
    bw = min(80, lk * gaya["lebar_batang"] * 1.2)
    for i in range(r):
        cx = c.kiri + (i + 0.5) * lk
        tot = obs[i].sum() or 1
        acc = 0.0
        for j in range(len(kolom)):
            pr = obs[i, j] / tot * 100
            col = warna_grup(gaya, palet, j)
            ya, yb = s.Y(acc + pr), s.Y(acc)
            c.out.append(f'<rect x="{cx - bw / 2:.1f}" y="{ya:.1f}" width="{bw:.1f}" height="{max(0.0, yb - ya):.1f}" '
                         f'fill="{col}" fill-opacity="{min(1, gaya["opasitas"] + 0.55):.2f}" stroke="{w["latar"]}" '
                         f'stroke-width="1"/>')
            if yb - ya > f + 4:
                c.teks(cx, (ya + yb) / 2 + f * 0.35, f"{int(obs[i, j])}", f - 1, "middle", warna_="#ffffff")
            acc += pr
        if gaya["miring"]:
            c.teks(cx + 4, s.bawah + 6 + f, baris[i], f, "end", putar=-40)
        else:
            c.teks(cx, s.bawah + 8 + f, baris[i], f, "middle")
    _hiasan(c, gaya, s)
    for j, t in enumerate(kolom):
        y = c.atas + 6 + j * (f + 10)
        x = c.kiri + c.pw + 18
        c.out.append(f'<rect x="{x}" y="{y:.1f}" width="{f}" height="{f}" fill="{warna_grup(gaya, palet, j)}" '
                     f'fill-opacity="{min(1, gaya["opasitas"] + 0.55):.2f}"/>')
        c.teks(x + f + 6, y + f * 0.85, t, f)
        if daerah is not None:
            daerah.append((f"grup:{j}", x - 2, y - 3, c.lebar - 4, y + f + 3))
    if gaya["label_x"]:
        c.teks(c.kiri + c.pw / 2, c.tinggi - 10, gaya["label_x"], gaya["font_label"], "middle")
    if daerah is not None:
        daerah.append(("sumbu_x", c.kiri, s.bawah + 2, c.kiri + c.pw, c.tinggi - 2))
    return c.selesai(), (W, gaya["tinggi"])


def _legenda(c, gaya, entri, palet, daerah, x=None, y=None):
    """entri: [(teks, indeks warna)] di pojok kanan atas area plot."""
    f = gaya["font"]
    lebar = max((len(t) for t, _ in entri), default=0) * f * 0.58 + f + 14
    x = c.kiri + c.pw - lebar if x is None else x
    y = c.atas + 4 if y is None else y
    for k, (t, i) in enumerate(entri):
        yy = y + k * (f + 8)
        c.out.append(f'<rect x="{x:.1f}" y="{yy:.1f}" width="{f}" height="{f}" rx="2" '
                     f'fill="{warna_grup(gaya, palet, i)}" fill-opacity="{min(1, gaya["opasitas"] + 0.5):.2f}" '
                     f'stroke="{warna_grup(gaya, palet, i)}"/>')
        c.teks(x + f + 6, yy + f * 0.85, t, f)
        if daerah is not None:
            daerah.append((f"grup:{i}", x - 2, yy - 3, x + lebar, yy + f + 3))


def grafik_qq(nama, kelompok, judul="", gelap=False, transparan=False, palet="okabe", gaya=None, daerah=None):
    """Q–Q plot normal: kuantil teoretis (posisi Blom) vs nilai terstandar tiap grup; garis y = x."""
    from scipy import stats
    gaya = gaya_lengkap(gaya)
    f = gaya["font"]
    W = gaya["lebar"] or 560
    sisi = W - (50 + f * 2.4 + gaya["font_label"]) - 24
    H = _tinggi_judul(judul, gaya) + sisi + 30 + f * 2.6 + gaya["font_label"] * 1.6
    c = Kanvas(W, H, gelap, transparan, "", kiri=50 + f * 2.4 + gaya["font_label"], kanan=24,
               atas=_tinggi_judul(judul, gaya), bawah=30 + f * 2.6 + gaya["font_label"] * 1.6)
    _judul(c, judul, gaya, daerah)
    c.f_tik = f
    titik = []
    for i, g in enumerate(kelompok):
        a = np.sort(np.asarray(g, float))
        if len(a) < 3 or a.std(ddof=1) == 0:
            continue
        n = len(a)
        teori = stats.norm.ppf((np.arange(1, n + 1) - 0.375) / (n + 0.25))
        titik.append((i, teori, (a - a.mean()) / a.std(ddof=1)))
    if not titik:
        c.teks(c.kiri, c.atas + 30, "Butuh n ≥ 3 per grup untuk Q–Q plot.", 13)
        return c.selesai(), (W, H)
    batas = max(2.5, max(float(np.abs(np.concatenate([t[1], t[2]])).max()) for t in titik) * 1.08)
    c.sumbu([-batas, batas], [-batas, batas], "", "", 0, 0, kisi=gaya["kisi"])
    w = c.w
    c.out.append(f'<line x1="{c.X(c.x0):.1f}" y1="{c.Y(c.x0):.1f}" x2="{c.X(c.x1):.1f}" y2="{c.Y(c.x1):.1f}" '
                 f'stroke="{w["tinta2"]}" stroke-dasharray="5 4" stroke-width="1"/>')
    for i, tx, ty in titik:
        col = warna_grup(gaya, palet, i)
        for a, b in zip(tx, ty):
            c.out.append(penanda(gaya["bentuk"], c.X(a), c.Y(b), gaya["ukuran_titik"] * 1.1, col, w["latar"]))
    _legenda(c, gaya, [(nama[i], i) for i, _x, _y in titik], palet, daerah, x=c.kiri + 10)
    _hiasan(c, gaya)
    c.teks(c.kiri + c.pw / 2, c.tinggi - 14 - f, gaya["label_x"] or "Kuantil normal teoretis", gaya["font_label"],
           "middle")
    c.teks(18 + gaya["font_label"] * 0.2, c.atas + c.ph / 2, "Nilai terstandar (z)", gaya["font_label"], "middle",
           putar=-90)
    c.catatan("Titik mendekati garis putus-putus = sebaran mendekati normal")
    if daerah is not None:
        daerah.append(("sumbu_x", c.kiri, c.atas + c.ph + 2, c.kiri + c.pw, c.tinggi - 2))
    return c.selesai(), (W, H)


def grafik_dua_faktor(h, galat="sd", palet="okabe", label_y="", judul="", gelap=False, transparan=False,
                      gaya=None, daerah=None):
    """Batang berkelompok: sumbu x = level faktor A (baris), warna = level faktor B (kolom); rerata ± galat +
    titik individu; legenda faktor B."""
    gaya = gaya_lengkap(gaya)
    la, lb = h["level_a"], h["level_b"]
    f = gaya["font"]
    pjg = max((len(t) for t in la), default=0)
    lebar = gaya["lebar"] or max(520, 140 + len(la) * (60 + 46 * len(lb)))
    bawah = (18 + f * 1.6 + (pjg * f * 0.45 if gaya["miring"] else 0)
             + (gaya["font_label"] * 1.8 if gaya["label_x"] else 0))
    kiri = 50 + f * 2.4 + gaya["font_label"]
    c = Kanvas(lebar, gaya["tinggi"], gelap, transparan, "", kiri=kiri, kanan=20, atas=_tinggi_judul(judul, gaya)
               + (f + 8) * len(lb) * 0, bawah=bawah)
    _judul(c, judul, gaya, daerah)
    data = h["data_sel"]
    des = h["sel"]
    semua = [v for xs in data.values() for v in xs]
    ujung = []
    for d in des.values():
        lo, hi = _galat(d, galat)
        ujung += [d["rerata"] - lo, d["rerata"] + hi]
    lo_y, hi_y = min(semua + ujung + [0.0]), max(semua + ujung + [0.0])
    rentang = (hi_y - lo_y) or 1.0
    s = SkalaY(lo_y, hi_y + 0.18 * rentang, c.atas, c.ph, gaya, batang=True)   # ruang untuk legenda
    c.x0, c.x1, c.y0, c.y1 = 0, len(la), s.y0, s.y1
    w = c.w
    c.out.append(f'<line x1="{c.kiri}" y1="{s.bawah}" x2="{c.kiri + c.pw}" y2="{s.bawah}" stroke="{w["garis"]}" '
                 f'stroke-width="{gaya["tebal"]}"/>')
    _sumbu_y(c, s, gaya, label_y, daerah)
    lk = c.pw / len(la)
    bw = min(48, lk * 0.8 / len(lb))
    rng = np.random.default_rng(7)
    for i, a in enumerate(la):
        cx0 = c.kiri + (i + 0.5) * lk
        if gaya["miring"]:
            c.teks(cx0 + 4, s.bawah + 6 + f, a, f, "end", putar=-40)
        else:
            c.teks(cx0, s.bawah + 8 + f, a, f, "middle")
        for j, b in enumerate(lb):
            k = f"{a}|{b}"
            d, xs = des[k], data[k]
            cx = cx0 + (j - (len(lb) - 1) / 2) * bw * 1.08
            col = warna_grup(gaya, palet, j)
            dasar = max(s.y0, min(0.0, s.y1))
            ya, yb = sorted((s.Y(dasar), s.Y(d["rerata"])))
            for p0, p1 in s.potong(ya, yb):
                c.out.append(f'<rect x="{cx - bw / 2:.1f}" y="{p0:.1f}" width="{bw:.1f}" height="{max(1.0, p1 - p0):.1f}" '
                             f'fill="{col}" fill-opacity="{gaya["opasitas"] + 0.12:.2f}" stroke="{col}" stroke-width="1.3"/>')
            if gaya["titik"]:
                for v in xs:
                    c.out.append(penanda(gaya["bentuk"], cx + (rng.random() - 0.5) * bw * 0.55, s.Y(v),
                                         gaya["ukuran_titik"] * 0.9, col, w["latar"]))
            lo, hi = _galat(d, galat)
            if lo or hi:
                for p0, p1 in s.potong(s.Y(d["rerata"] + hi), s.Y(d["rerata"] - lo)):
                    c.out.append(f'<line x1="{cx:.1f}" y1="{p0:.1f}" x2="{cx:.1f}" y2="{p1:.1f}" stroke="{w["tinta"]}" '
                                 f'stroke-width="1.3"/>')
                for v in (d["rerata"] - lo, d["rerata"] + hi):
                    c.out.append(f'<line x1="{cx - bw / 5:.1f}" y1="{s.Y(v):.1f}" x2="{cx + bw / 5:.1f}" y2="{s.Y(v):.1f}" '
                                 f'stroke="{w["tinta"]}" stroke-width="1.3"/>')
    _hiasan(c, gaya, s)
    _legenda(c, gaya, [(b, j) for j, b in enumerate(lb)], palet, daerah)
    if gaya["label_x"]:
        c.teks(c.kiri + c.pw / 2, c.tinggi - 10, gaya["label_x"], gaya["font_label"], "middle")
    if daerah is not None:
        daerah.append(("sumbu_x", c.kiri, s.bawah + 2, c.kiri + c.pw, c.tinggi - 2))
    return c.selesai(), (c.lebar, c.tinggi)
