"""Grafik SVG sederhana kualitas publikasi (tanpa matplotlib): sumbu, tik, histogram, sebar, batang, peta panas.

Semua fungsi mengembalikan teks SVG berukuran piksel tetap (lebar × tinggi); JendelaUtama._simpan_svg
mengubahnya ke SVG ber-mm, PDF vektor, atau PNG/TIFF ber-DPI.
"""
import math
from xml.sax.saxutils import escape

FONT = "Segoe UI, Arial, Helvetica, sans-serif"
AKSEN = "#2b6fd6"
MERAH = "#cf3f3f"


def tik(a, b, n=6):
    """Tik 'bagus' (1, 2, 2.5, 5 × 10^k) yang mencakup [a, b]."""
    if b - a < 1e-12:
        a, b = a - 1, b + 1
    kasar = (b - a) / n
    p = 10 ** math.floor(math.log10(kasar))
    langkah = next(m * p for m in (1, 2, 2.5, 5, 10) if m * p >= kasar * 0.999)
    t, akhir = math.floor(a / langkah + 1e-9) * langkah, math.ceil(b / langkah - 1e-9) * langkah
    hasil = []
    while t <= akhir + langkah * 1e-6:
        hasil.append(round(t, 10))
        t += langkah
    return hasil, langkah


def fmt(v, desimal=2):
    """Angka gaya Indonesia: koma desimal, tanda minus asli."""
    t = f"{v:.{desimal}f}".rstrip("0").rstrip(".") if desimal else f"{v:.0f}"
    if t in ("-0", ""):
        t = "0"
    return ("−" + t[1:] if t.startswith("-") else t).replace(".", ",")


def warna(gelap):
    return {"tinta": "#e2e6ed" if gelap else "#1b2430", "tinta2": "#aab3c0" if gelap else "#465263",
            "latar": "#14171c" if gelap else "#ffffff", "kisi": "#262b33" if gelap else "#eceff3",
            "garis": "#7d8796" if gelap else "#465263"}


class Kanvas:
    """Kerangka plot: area data + sumbu + kisi + label. Pakai X()/Y() untuk memetakan data ke piksel."""

    def __init__(self, lebar=760, tinggi=560, gelap=False, transparan=False, judul="", kiri=70, kanan=24,
                 atas=None, bawah=64):
        self.lebar, self.tinggi, self.gelap = lebar, tinggi, gelap
        self.w = warna(gelap)
        self.judul = judul
        self.kiri, self.kanan = kiri, kanan
        self.atas = atas if atas is not None else (44 if judul else 20)
        self.bawah = bawah
        self.out = [f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{lebar}" height="{tinggi}" '
                    f'viewBox="0 0 {lebar} {tinggi}">']
        if not transparan:
            self.out.append(f'<rect x="0" y="0" width="{lebar}" height="{tinggi}" fill="{self.w["latar"]}"/>')
        if judul:
            self.out.append(f'<text x="{kiri}" y="26" font-family="{FONT}" font-size="14" font-weight="600" '
                            f'fill="{self.w["tinta"]}">{escape(judul)}</text>')
        self.x0 = self.x1 = self.y0 = self.y1 = None
        self.f_tik = 11

    @property
    def pw(self):
        return self.lebar - self.kiri - self.kanan

    @property
    def ph(self):
        return self.tinggi - self.atas - self.bawah

    def X(self, v):
        return self.kiri + (v - self.x0) / (self.x1 - self.x0) * self.pw

    def Y(self, v):
        return self.atas + (self.y1 - v) / (self.y1 - self.y0) * self.ph

    def teks(self, x, y, t, ukuran=11, anchor="start", tebal=False, warna_=None, putar=None):
        tr = f' transform="rotate({putar} {x:.1f} {y:.1f})"' if putar else ""
        self.out.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="{FONT}" '
                        f'font-size="{ukuran}"{" font-weight=\"600\"" if tebal else ""} '
                        f'fill="{warna_ or self.w["tinta"]}"{tr}>{escape(str(t))}</text>')

    def sumbu(self, xs, ys, label_x="", label_y="", desimal_x=2, desimal_y=2, kisi=True, tik_x=None, bulat_y=False, pad=0.0):
        """Tetapkan rentang dari data lalu gambar kisi, bingkai, tik, dan label sumbu. pad = ruang tepi (fraksi)."""
        ax, bx, ay, by = min(xs), max(xs), min(ys), max(ys)
        ax, bx = ax - pad * (bx - ax), bx + pad * (bx - ax)
        ay, by = ay - pad * (by - ay), by + pad * (by - ay)
        tx = tik_x or tik(ax, bx, 7)[0]
        ty, _ = tik(ay, by, 6)
        if bulat_y and len(ty) > 1 and ty[1] - ty[0] < 1:
            ty = list(range(int(math.floor(min(ys))), int(math.ceil(max(ys))) + 1))
        self.x0, self.x1 = tx[0], tx[-1]
        self.y0, self.y1 = ty[0], ty[-1]
        w = self.w
        if kisi:
            for v in ty:
                self.out.append(f'<line x1="{self.kiri}" y1="{self.Y(v):.1f}" x2="{self.kiri + self.pw}" '
                                f'y2="{self.Y(v):.1f}" stroke="{w["kisi"]}" stroke-width="1"/>')
        b = self.atas + self.ph
        self.out.append(f'<line x1="{self.kiri}" y1="{b}" x2="{self.kiri + self.pw}" y2="{b}" stroke="{w["garis"]}"/>')
        self.out.append(f'<line x1="{self.kiri}" y1="{self.atas}" x2="{self.kiri}" y2="{b}" stroke="{w["garis"]}"/>')
        for v in tx:
            self.out.append(f'<line x1="{self.X(v):.1f}" y1="{b}" x2="{self.X(v):.1f}" y2="{b + 5}" '
                            f'stroke="{w["garis"]}"/>')
            self.teks(self.X(v), b + 8 + self.f_tik, fmt(v, desimal_x), self.f_tik, anchor="middle")
        for v in ty:
            self.out.append(f'<line x1="{self.kiri - 5}" y1="{self.Y(v):.1f}" x2="{self.kiri}" y2="{self.Y(v):.1f}" '
                            f'stroke="{w["garis"]}"/>')
            self.teks(self.kiri - 8, self.Y(v) + 4, fmt(v, desimal_y), self.f_tik, anchor="end")
        if label_x:
            self.teks(self.kiri + self.pw / 2, b + 42, label_x, 12, "middle")
        if label_y:
            self.teks(18, self.atas + self.ph / 2, label_y, 12, "middle", putar=-90)

    def catatan(self, t):
        self.teks(self.kiri, self.tinggi - 8, t, 9.5, warna_=self.w["tinta2"])

    def selesai(self):
        return "\n".join(self.out + ["</svg>"])


# ------------------------------------------------------------------ jenis grafik
def histogram(nilai, label_x="", judul="", kelas=None, gelap=False, transparan=False, lebar=760, tinggi=520,
              garis_rerata=True, catatan=""):
    import numpy as np
    v = np.asarray(nilai, float)
    if kelas is None or kelas <= 0:
        kelas = min(30, max(5, len(np.histogram_bin_edges(v, "fd")) - 1)) if len(v) > 3 else 5
    jumlah, tepi = np.histogram(v, bins=kelas)
    k = Kanvas(lebar, tinggi, gelap, transparan, judul)
    k.sumbu([tepi[0], tepi[-1]], [0, max(1, int(jumlah.max()))], label_x, "Jumlah ligan", desimal_y=0, bulat_y=True)
    for n, a, b in zip(jumlah, tepi[:-1], tepi[1:]):
        if n:
            k.out.append(f'<rect x="{k.X(a) + 0.5:.2f}" y="{k.Y(n):.2f}" width="{max(0.5, k.X(b) - k.X(a) - 1):.2f}" '
                         f'height="{k.Y(0) - k.Y(n):.2f}" fill="{AKSEN}" fill-opacity="0.85"><title>{fmt(a)} – '
                         f'{fmt(b)}: {n}</title></rect>')
    if garis_rerata and len(v):
        m = float(v.mean())
        k.out.append(f'<line x1="{k.X(m):.2f}" y1="{k.atas}" x2="{k.X(m):.2f}" y2="{k.atas + k.ph}" '
                     f'stroke="{MERAH}" stroke-width="1.5" stroke-dasharray="5,3"/>')
        k.teks(k.X(m) + 5, k.atas + 12, f"rerata {fmt(m)}", 10.5, warna_=MERAH)
    if catatan:
        k.catatan(catatan)
    return k.selesai()


def sebar(x, y, nama=None, label_x="", label_y="", judul="", regresi=None, gelap=False, transparan=False,
          lebar=760, tinggi=560, label=False, pilih=None, catatan=""):
    """regresi: dict dari statistik.korelasi (garis + pita kepercayaan 95 %) atau None."""
    k = Kanvas(lebar, tinggi, gelap, transparan, judul)
    k.sumbu(list(x), list(y), label_x, label_y, pad=0.05)
    k.out.append(f'<defs><clipPath id="area"><rect x="{k.kiri}" y="{k.atas}" width="{k.pw}" height="{k.ph}"/>'
                 f'</clipPath></defs>')
    if regresi and regresi.get("pita"):
        atas_ = [(k.X(a), k.Y(b)) for a, b, _ in regresi["pita"]]
        bawah_ = [(k.X(a), k.Y(c)) for a, _, c in reversed(regresi["pita"])]
        d = "M" + " L".join(f"{a:.2f},{b:.2f}" for a, b in atas_ + bawah_) + " Z"
        k.out.append(f'<path d="{d}" fill="{AKSEN}" fill-opacity="0.12" clip-path="url(#area)"/>')
    if regresi and regresi.get("kemiringan") is not None:
        a, b = k.x0, k.x1
        f = lambda t: regresi["potong"] + regresi["kemiringan"] * t   # noqa: E731
        k.out.append(f'<line x1="{k.X(a):.2f}" y1="{k.Y(f(a)):.2f}" x2="{k.X(b):.2f}" y2="{k.Y(f(b)):.2f}" '
                     f'stroke="{AKSEN}" stroke-width="1.6" clip-path="url(#area)"/>')
    urut = list(range(len(x)))
    if pilih is not None and 0 <= pilih < len(x):
        urut.append(urut.pop(pilih))
    for i in urut:
        s = i == pilih
        t = f"{escape(nama[i])}: " if nama else ""
        k.out.append(f'<circle cx="{k.X(x[i]):.2f}" cy="{k.Y(y[i]):.2f}" r="{6 if s else 4.5}" '
                     f'fill="{MERAH if s else AKSEN}" fill-opacity="{1 if s else 0.85}" stroke="{k.w["latar"]}" '
                     f'stroke-width="1"><title>{t}{fmt(x[i])}; {fmt(y[i])}</title></circle>')
        if label and nama:
            k.teks(k.X(x[i]) + 7, k.Y(y[i]) - 5, nama[i] if len(x) <= 25 else i + 1, 9.5, warna_=k.w["tinta2"])
    if regresi and regresi.get("n", 0) >= 3:
        r = regresi
        t = (f"y = {fmt(r['kemiringan'], 3)}x {'+' if r['potong'] >= 0 else '−'} {fmt(abs(r['potong']), 3)}   "
             f"R² = {fmt(r['r2'], 3)}   r = {fmt(r['r'], 3)} (p {p_teks(r['p'])})   "
             f"ρ Spearman = {fmt(r['rho'], 3)} (p {p_teks(r['p_rho'])})   n = {r['n']}")
        k.teks(k.kiri, k.tinggi - 24 if catatan else k.tinggi - 10, t, 10.5)
    if catatan:
        k.catatan(catatan)
    return k.selesai()


def batang(nama, nilai, label_x="", judul="", gelap=False, transparan=False, lebar=760, tinggi=None, catatan=""):
    """Batang horizontal (mis. ΔG teratas). Nilai negatif digambar ke kiri dari 0."""
    n = len(nilai)
    tinggi = tinggi or max(260, 70 + 22 * n + (44 if judul else 20))
    pjg = max((len(str(t)) for t in nama), default=4)
    k = Kanvas(lebar, tinggi, gelap, transparan, judul, kiri=min(260, 16 + int(pjg * 6.4)), bawah=56)
    lo, hi = min(0, min(nilai, default=0)), max(0, max(nilai, default=0))
    tx, _ = tik(lo, hi, 6)
    k.x0, k.x1 = tx[0], tx[-1]
    k.y0, k.y1 = 0, n
    w = k.w
    b = k.atas + k.ph
    for v in tx:
        k.out.append(f'<line x1="{k.X(v):.1f}" y1="{k.atas}" x2="{k.X(v):.1f}" y2="{b}" stroke="{w["kisi"]}"/>')
        k.teks(k.X(v), b + 18, fmt(v), anchor="middle")
    tinggi_b = k.ph / max(n, 1)
    for i, (t, v) in enumerate(zip(nama, nilai)):
        y = k.atas + i * tinggi_b
        x_a, x_b = sorted((k.X(0), k.X(v)))
        k.out.append(f'<rect x="{x_a:.2f}" y="{y + tinggi_b * 0.18:.2f}" width="{max(0.5, x_b - x_a):.2f}" '
                     f'height="{tinggi_b * 0.64:.2f}" fill="{AKSEN}" fill-opacity="{0.95 - 0.5 * i / max(n, 1):.2f}">'
                     f'<title>{escape(str(t))}: {fmt(v)}</title></rect>')
        k.teks(k.kiri - 8, y + tinggi_b / 2 + 4, t, 10.5, "end")
        dalam = x_b - x_a > 46          # angka di dalam batang, di ujung yang jauh dari nol
        if v < 0:
            xt, anc = (x_a + 5, "start") if dalam else (x_a - 4, "end")
        else:
            xt, anc = (x_b - 5, "end") if dalam else (x_b + 4, "start")
        k.teks(xt, y + tinggi_b / 2 + 4, fmt(v), 9.5, anc, warna_="#ffffff" if dalam else w["tinta2"])
    k.out.append(f'<line x1="{k.X(0):.1f}" y1="{k.atas}" x2="{k.X(0):.1f}" y2="{b}" stroke="{w["garis"]}"/>')
    if label_x:
        k.teks(k.kiri + k.pw / 2, b + 40, label_x, 12, "middle")
    if catatan:
        k.catatan(catatan)
    return k.selesai()


def _divergen(r):
    """−1 merah … 0 putih … +1 biru."""
    r = max(-1.0, min(1.0, r))
    ujung = (43, 111, 214) if r > 0 else (207, 63, 63)
    return "#%02x%02x%02x" % tuple(round(255 + (c - 255) * abs(r)) for c in ujung)


def peta_korelasi(label, matriks, judul="", gelap=False, transparan=False, lebar=None, catatan="", p=None,
                  skala01=False):
    """Matriks korelasi (−1…1) berwarna divergen; '*' bila p < 0,05. skala01: nilai 0…1 (mis. Tanimoto)."""
    n = len(label)
    sel = max(34, min(64, 560 // max(n, 1)))
    kiri = 16 + int(max(len(t) for t in label) * 6.6)
    atas = (44 if judul else 16) + int(max(len(t) for t in label) * 4.8) + 10
    lebar = lebar or kiri + n * sel + 90
    tinggi = atas + n * sel + 52
    k = Kanvas(lebar, tinggi, gelap, transparan, judul, kiri=kiri, atas=atas, bawah=52)
    for i in range(n):
        k.teks(kiri - 8, atas + i * sel + sel / 2 + 4, label[i], 10.5, "end")
        x = kiri + i * sel + sel / 2
        k.teks(x, atas - 8, label[i], 10.5, "start", putar=-55)
        for j in range(n):
            r = matriks[i][j]
            isi = "#999999" if r is None or r != r else _divergen(r)
            k.out.append(f'<rect x="{kiri + j * sel}" y="{atas + i * sel}" width="{sel - 1}" height="{sel - 1}" '
                         f'fill="{isi}"><title>{escape(label[i])} × {escape(label[j])}: '
                         f'{"–" if r is None or r != r else fmt(r, 2)}</title></rect>')
            if r is not None and r == r:
                bintang = "*" if p is not None and i != j and p[i][j] is not None and p[i][j] < 0.05 else ""
                k.teks(kiri + j * sel + sel / 2, atas + i * sel + sel / 2 + 4, fmt(r, 2) + bintang, 9.5, "middle",
                       warna_="#ffffff" if abs(r) > 0.6 else "#1b2430")
    # skala warna
    sx = kiri + n * sel + 22
    for s in range(41):
        r = 1 - s / (40 if skala01 else 20)
        k.out.append(f'<rect x="{sx}" y="{atas + s * (n * sel) / 41:.2f}" width="14" height="{(n * sel) / 41 + 0.5:.2f}" '
                     f'fill="{_divergen(r)}"/>')
    for r in ((1, 0.5, 0) if skala01 else (1, 0, -1)):
        k.teks(sx + 20, atas + ((1 - r) if skala01 else (1 - r) / 2) * n * sel + 4, fmt(r), 10)
    if catatan:
        k.catatan(catatan)
    return k.selesai()


PALET_KELOMPOK = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#8C6D31", "#6A51A3",
                  "#2CA0A0", "#B2182B"]


def _skala_biru(f):
    """0 -> biru tua (nilai kecil, mis. ΔG paling negatif) … 1 -> kuning pucat."""
    a, b, c = (33, 64, 154), (65, 182, 196), (237, 248, 177)
    f = max(0.0, min(1.0, f))
    u, v, t = (a, b, f * 2) if f < 0.5 else (b, c, f * 2 - 1)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(u, v))


def sebar_kelompok(x, y, nama, kelompok=None, nilai=None, label_x="", label_y="", judul="", gelap=False,
                   transparan=False, lebar=780, tinggi=580, label=False, acuan=None, label_nilai="", catatan="",
                   tanpa_tik=False):
    """Sebar berwarna: kelompok (int, 0 = lain-lain) -> palet kategori; atau nilai kontinu -> skala biru–kuning.

    acuan: indeks titik yang ditandai (cincin merah). tanpa_tik: sumbu PCA/MDS (angka tik tidak bermakna)."""
    k = Kanvas(lebar, tinggi, gelap, transparan, judul, kanan=120 if (kelompok or nilai) else 24)
    k.sumbu(list(x), list(y), label_x, label_y, pad=0.08)
    if nilai:
        ada = [v for v in nilai if v is not None]
        lo, hi = (min(ada), max(ada)) if ada else (0, 1)
    urut = sorted(range(len(x)), key=lambda i: -(kelompok[i] if kelompok else 0))
    for i in urut:
        if nilai:
            v = nilai[i]
            isi = "#9aa3ae" if v is None else _skala_biru((v - lo) / (hi - lo) if hi > lo else 0.5)
        elif kelompok:
            g = kelompok[i]
            isi = PALET_KELOMPOK[(g - 1) % len(PALET_KELOMPOK)] if g and g <= len(PALET_KELOMPOK) else "#9aa3ae"
        else:
            isi = AKSEN
        info = f"{escape(nama[i])}" + (f" · klaster {kelompok[i]}" if kelompok else "") + (
            f" · {fmt(nilai[i])}" if nilai and nilai[i] is not None else "")
        k.out.append(f'<circle cx="{k.X(x[i]):.2f}" cy="{k.Y(y[i]):.2f}" r="5" fill="{isi}" fill-opacity="0.9" '
                     f'stroke="{k.w["latar"]}" stroke-width="1"><title>{info}</title></circle>')
    if label:
        kotak = [(k.X(x[i]) - 5, k.Y(y[i]) - 5, k.X(x[i]) + 5, k.Y(y[i]) + 5) for i in range(len(x))]
        if acuan is not None and 0 <= acuan < len(x):      # label acuan (tebal, merah) dipesan lebih dulu
            ax_, ay_ = k.X(x[acuan]), k.Y(y[acuan])
            kotak.append((ax_ - 10, ay_ - 10, ax_ + 14 + len(nama[acuan]) * 6.4, ay_ + 10))
        for i in urut:
            if i == acuan:
                continue
            t = str(nama[i] if len(x) <= 30 else i + 1)
            pos = tempat_label(k.X(x[i]), k.Y(y[i]), t, 9.5, kotak, (k.kiri, k.atas, k.kiri + k.pw, k.atas + k.ph))
            if pos:
                k.teks(pos[0], pos[1], t, 9.5, anchor=pos[2], warna_=k.w["tinta2"])
    if acuan is not None and 0 <= acuan < len(x):
        k.out.append(f'<circle cx="{k.X(x[acuan]):.2f}" cy="{k.Y(y[acuan]):.2f}" r="9" fill="none" stroke="{MERAH}" '
                     f'stroke-width="2"/>')
        k.teks(k.X(x[acuan]) + 11, k.Y(y[acuan]) + 4, nama[acuan], 10.5, tebal=True, warna_=MERAH)
    lx = k.kiri + k.pw + 16
    if nilai:
        h = min(220, k.ph)
        for s in range(40):
            k.out.append(f'<rect x="{lx}" y="{k.atas + s * h / 40:.2f}" width="14" height="{h / 40 + 0.5:.2f}" '
                         f'fill="{_skala_biru(s / 39)}"/>')
        k.teks(lx + 20, k.atas + 9, fmt(lo), 10)
        k.teks(lx + 20, k.atas + h, fmt(hi), 10)
        if label_nilai:
            k.teks(lx, k.atas + h + 20, label_nilai, 10, warna_=k.w["tinta2"])
    elif kelompok:
        ada = sorted({g for g in kelompok if g})[:len(PALET_KELOMPOK)]
        for i, g in enumerate(ada):
            yy = k.atas + 6 + i * 18
            k.out.append(f'<circle cx="{lx + 6}" cy="{yy}" r="5" fill="{PALET_KELOMPOK[(g - 1) % len(PALET_KELOMPOK)]}"/>')
            k.teks(lx + 16, yy + 4, f"Klaster {g} ({kelompok.count(g)})", 10)
        if max(kelompok) > len(PALET_KELOMPOK):
            yy = k.atas + 6 + len(ada) * 18
            k.out.append(f'<circle cx="{lx + 6}" cy="{yy}" r="5" fill="#9aa3ae"/>')
            k.teks(lx + 16, yy + 4, "Klaster lain", 10)
    if tanpa_tik:      # sembunyikan angka tik: hanya arah relatif yang bermakna
        k.out = [o for o in k.out if not (o.startswith("<text") and 'font-size="11"' in o and _angka(o))]
    if catatan:
        k.catatan(catatan)
    return k.selesai()


def tempat_label(px, py, t, ukuran, kotak, batas):
    """Cari posisi label dekat titik (px, py) yang tidak menimpa kotak lain; kotak diperbarui.

    Kembalikan (x, y_baseline, anchor) atau None bila semua kandidat bertabrakan (label dilewati)."""
    w, h = len(t) * ukuran * 0.56 + 2, ukuran + 2
    calon = [(7, -4, "start"), (-7, -4, "end"), (7, 10, "start"), (-7, 10, "end"), (0, -10, "middle"),
             (0, 18, "middle"), (7, -15, "start"), (-7, -15, "end"), (7, 21, "start"), (-7, 21, "end")]
    for dx, dy, anc in calon:
        x0 = px + dx - (w if anc == "end" else w / 2 if anc == "middle" else 0)
        b = (x0, py + dy - h + 3, x0 + w, py + dy + 3)
        if b[0] < batas[0] - 30 or b[2] > batas[2] + 110 or b[1] < batas[1] - 10 or b[3] > batas[3] + 10:
            continue
        if all(b[2] < q[0] or b[0] > q[2] or b[3] < q[1] or b[1] > q[3] for q in kotak):
            kotak.append(b)
            return px + dx, py + dy, anc
    return None


def _angka(o):
    t = o.split(">", 1)[1].rsplit("<", 1)[0]
    return bool(t) and all(c in "0123456789,−-" for c in t)


def _kunci_residu(r):
    """'ASP 25 A' -> ('A', 25, 'ASP') untuk mengurutkan kolom menurut rantai lalu nomor residu."""
    b = r.split()
    try:
        no = int("".join(c for c in (b[1] if len(b) > 1 else "") if c.isdigit() or c == "-") or 0)
    except ValueError:
        no = 0
    return (b[2] if len(b) > 2 else "", no, b[0] if b else "")


def peta_ifp(nama, ifps, judul="", gelap=False, transparan=False, catatan="", warna_jenis=None, nama_jenis=None,
             urut_jenis=None, min_frek=0.0):
    """Peta sidik jari interaksi ala ProLIF: baris = ligan, kolom = residu × jenis interaksi.

    ifps: list himpunan bit 'residu|jenis'. Sel berwarna sesuai jenis bila interaksi ada. Baris terakhir =
    frekuensi (% ligan). min_frek: kolom dengan frekuensi < nilai ini (0–1) dibuang.
    """
    warna_jenis = warna_jenis or {}
    nama_jenis = nama_jenis or {}
    urut_jenis = urut_jenis or []
    n = len(nama)
    hitung = {}
    for s in ifps:
        for bit in s:
            hitung[bit] = hitung.get(bit, 0) + 1
    bits = [b for b in hitung if n and hitung[b] / n >= min_frek - 1e-9]
    rank = {j: i for i, j in enumerate(urut_jenis)}
    bits.sort(key=lambda b: (_kunci_residu(b.split("|")[0]), rank.get(b.split("|")[1], 99)))
    kolom = len(bits)
    if not n or not kolom:
        return ""
    sel_w = max(13, min(26, 900 // kolom))
    sel_h = max(16, min(24, 520 // n))
    kiri = 16 + int(max(len(t) for t in nama) * 6.4)
    pjg_res = max(len(b.split("|")[0]) for b in bits)
    atas = (44 if judul else 16) + int(pjg_res * 5.2) + 16
    jenis_ada = [j for j in urut_jenis if any(b.endswith("|" + j) for b in bits)]
    lebar = max(kiri + kolom * sel_w + 70, kiri + min(4, len(jenis_ada)) * 150 + 20, 460)
    tinggi = atas + (n + 1) * sel_h + 14 + 26 * ((len(jenis_ada) + 3) // 4) + 30
    k = Kanvas(lebar, tinggi, gelap, transparan, judul, kiri=kiri, atas=atas, bawah=40)
    w = k.w
    kosong = "#1d2128" if gelap else "#f2f4f7"
    # label residu (sekali per kelompok) + garis pemisah antar residu
    res_sebelum = None
    for c, b in enumerate(bits):
        res = b.split("|")[0]
        x = kiri + c * sel_w
        if res != res_sebelum:
            if res_sebelum is not None:
                k.out.append(f'<line x1="{x - 0.5:.1f}" y1="{atas - 4}" x2="{x - 0.5:.1f}" '
                             f'y2="{atas + (n + 1) * sel_h + 4}" stroke="{w["garis"]}" stroke-width="0.8"/>')
            k.teks(x + sel_w / 2 + 3, atas - 8, res, 10, "start", putar=-55)
            res_sebelum = res
    for i, t in enumerate(nama):
        y = atas + i * sel_h
        k.teks(kiri - 8, y + sel_h / 2 + 4, t, 10.5, "end")
        for c, b in enumerate(bits):
            j = b.split("|")[1]
            ada = b in ifps[i]
            isi = warna_jenis.get(j, AKSEN) if ada else kosong
            k.out.append(f'<rect x="{kiri + c * sel_w + 0.5:.1f}" y="{y + 0.5:.1f}" width="{sel_w - 1}" '
                         f'height="{sel_h - 1}" fill="{isi}"><title>{escape(t)} · {escape(b.split("|")[0])} · '
                         f'{escape(nama_jenis.get(j, j))}: {"ada" if ada else "tidak"}</title></rect>')
    # baris frekuensi
    y = atas + n * sel_h + 6
    k.teks(kiri - 8, y + sel_h / 2 + 4, "Frekuensi", 10, "end", tebal=True, warna_=w["tinta2"])
    for c, b in enumerate(bits):
        f = hitung[b] / n
        j = b.split("|")[1]
        h = max(1.0, (sel_h - 2) * f)
        k.out.append(f'<rect x="{kiri + c * sel_w + 1.5:.1f}" y="{y + sel_h - 1 - h:.1f}" width="{sel_w - 3}" '
                     f'height="{h:.1f}" fill="{warna_jenis.get(j, AKSEN)}"><title>{escape(b.split("|")[0])} · '
                     f'{escape(nama_jenis.get(j, j))}: {round(f * 100)} % ligan</title></rect>')
    # legenda jenis interaksi
    ly = y + sel_h + 22
    for idx, j in enumerate(jenis_ada):
        lx = kiri + (idx % 4) * 150
        yy = ly + (idx // 4) * 22
        k.out.append(f'<rect x="{lx}" y="{yy - 10}" width="12" height="12" fill="{warna_jenis.get(j, AKSEN)}"/>')
        k.teks(lx + 18, yy, nama_jenis.get(j, j), 10.5)
    if catatan:
        k.catatan(catatan)
    return k.selesai()


def p_teks(p):
    if p is None or p != p:
        return "–"
    return "< 0,001" if p < 0.001 else "= " + fmt(p, 3)
