"""Eksplorasi putaran 2: 12 variasi konsep B "Heksa-Kantong" -> keluaran/virmolab/lembar_variasi_B.png

  .venv\\Scripts\\python.exe build_tools\\logo\\eksplorasi_virmolab2.py
"""
import itertools
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buat_logo import render  # noqa: E402
from eksplorasi_virmolab import OUT, S3, WM, heks, poli, poli_bulat, teks, wordmark  # noqa: E402

PALET = {
    "navy": {"badan": "#12305a", "aksen": "#2f74e0", "teks": "#12305a", "latar": "#ffffff"},
    "emas": {"badan": "#0f2240", "aksen": "#c9a24e", "teks": "#0f2240", "latar": "#ffffff"},
    "gelap": {"badan": "#ffffff", "aksen": "#6aa8ff", "teks": "#ffffff", "latar": "#0e1a2c", "bayang": "#9dbbe6"},
}
_id = itertools.count()


def campur(a, b, t):
    """Campur warna hex a->b sebesar t (0..1)."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def heks_runcing(cx, cy, r):
    """Heksagon puncak-runcing; urutan: kanan-bawah, bawah, kiri-bawah, kiri-atas, puncak, kanan-atas."""
    return [(cx + r * math.cos(math.radians(30 + 60 * k)), cy + r * math.sin(math.radians(30 + 60 * k)))
            for k in range(6)]


def jarak(a, b, p):
    """Jarak bertanda titik p ke garis a->b (positif = sisi dalam kantong)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    return ((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / math.hypot(dx, dy)


def taruh_ligan(dinding, titik_fn, g, y_lo, y_hi):
    """Bisection: cari y pusat ligan agar jarak terdekat ke dinding kiri = g."""
    a, b = dinding
    for _ in range(60):
        ym = (y_lo + y_hi) / 2
        d = min(jarak(a, b, p) for p in titik_fn(ym))
        y_lo, y_hi = (ym, y_hi) if d > g else (y_lo, ym)
    return (y_lo + y_hi) / 2


def badan(cx=50.0, cy=56.0, r=42.0, f=1.0):
    h = heks(cx, cy, r)
    ytop = cy - r * S3 / 2
    apex = (cx, ytop + f * (cy - ytop))
    return [h[4], apex, h[5], h[0], h[1], h[2], h[3]], apex, h


def varian(c, f=1.0, rr=1.6, s=11.5, g=4.2, ligan="heks", gaya="isi", w=5.0):
    """Kembalikan (elemen svg, titik untuk bbox)."""
    pts, apex, h = badan(f=f)
    cx = 50.0
    el = []
    # ---- badan
    if gaya == "isi":
        el.append(f'<path d="{poli_bulat(pts, rr)}" fill="{c["badan"]}"/>')
    elif gaya == "garis":
        el.append(f'<path d="{poli(pts)}" fill="none" stroke="{c["badan"]}" stroke-width="{w}" stroke-linejoin="round"/>')
    elif gaya == "gradien":
        i = next(_id)
        el.append(f'<defs><linearGradient id="gb{i}" x1="0" y1="0" x2="0.8" y2="1">'
                  f'<stop offset="0" stop-color="{campur(c["badan"], "#ffffff", 0.24) if c["badan"] != "#ffffff" else "#ffffff"}"/>'
                  f'<stop offset="1" stop-color="{campur(c["badan"], "#000000", 0.18) if c["badan"] != "#ffffff" else "#b9cff0"}"/></linearGradient>'
                  f'<linearGradient id="gl{i}" x1="0" y1="0" x2="1" y2="1">'
                  f'<stop offset="0" stop-color="{campur(c["aksen"], "#ffffff", 0.35)}"/>'
                  f'<stop offset="1" stop-color="{c["aksen"]}"/></linearGradient></defs>')
        el.append(f'<path d="{poli_bulat(pts, rr)}" fill="url(#gb{i})"/>')
    elif gaya == "faset":
        luar = [h[5], h[0], h[1], h[2], h[3], h[4]]
        nada = [0.16, 0.09, 0.03, -0.05, -0.12]       # kanan terang -> kiri gelap
        for (p, q), t in zip(zip(luar, luar[1:]), nada):
            warna = campur(c["badan"], "#ffffff", t) if t >= 0 else campur(c["badan"], c.get("bayang", "#000000"), -t * (2.2 if "bayang" in c else 1))
            el.append(f'<path d="{poli([apex, p, q])}" fill="{warna}" stroke="{warna}" stroke-width="0.35" '
                      f'stroke-linejoin="round"/>')
    # ---- ligan
    dinding = (pts[0], apex)
    if ligan == "bulat":
        yl = taruh_ligan(dinding, lambda y: [(cx + s * math.cos(t), y + s * math.sin(t))
                                             for t in [k * math.pi / 36 for k in range(72)]], g, apex[1] - 80, apex[1])
        el.append(f'<circle cx="{cx}" cy="{yl:.2f}" r="{s}" fill="{c["aksen"]}"/>')
        lig = [(cx - s, yl - s), (cx + s, yl + s)]
    else:
        gw = (w if gaya == "garis" or ligan == "cincin" else 0)
        yl = taruh_ligan(dinding, lambda y: heks(cx, y, s + gw / 2), g + (w / 2 if gaya == "garis" else 0),
                         apex[1] - 80, apex[1])
        lig = heks(cx, yl, s)
        if ligan == "cincin" or gaya == "garis":
            el.append(f'<path d="{poli(lig)}" fill="none" stroke="{c["aksen"]}" stroke-width="{w}" '
                      f'stroke-linejoin="round"/>')
        else:
            isi = f"url(#gl{i})" if gaya == "gradien" else c["aksen"]
            el.append(f'<path d="{poli_bulat(lig, rr * 0.6)}" fill="{isi}"/>')
    return el, pts + lig


def varian_tertambat(c, rr=1.6):
    """Ligan sudah masuk ke kantong; dipisah garis warna latar."""
    pts, apex, _ = badan(f=1.0)
    s = 13.0
    yl = apex[1] - s * 1.05
    lig = heks(50, yl, s)
    return ([f'<path d="{poli_bulat(pts, rr)}" fill="{c["badan"]}"/>',
             f'<path d="{poli_bulat(lig, 1.0)}" fill="{c["aksen"]}" stroke="{c["latar"]}" stroke-width="5" '
             f'stroke-linejoin="round" paint-order="stroke"/>',
             f'<path d="{poli_bulat(lig, 1.0)}" fill="{c["aksen"]}"/>'], pts + lig)


def varian_cawan(c, rr=1.8):
    """Heksagon puncak-runcing tanpa dua segitiga atas -> cawan/lumpang farmasi."""
    cx, cy, r = 50.0, 50.0, 44.0
    h = heks_runcing(cx, cy, r)
    pts = [h[3], (cx, cy), h[5], h[0], h[1], h[2]]
    s, g = 12.5, 4.2
    yl = taruh_ligan((h[3], (cx, cy)), lambda y: heks_runcing(cx, y, s), g, cy - 80, cy)
    lig = heks_runcing(cx, yl, s)
    return ([f'<path d="{poli_bulat(pts, rr)}" fill="{c["badan"]}"/>',
             f'<path d="{poli_bulat(lig, rr * 0.6)}" fill="{c["aksen"]}"/>'], pts + lig)


VARIAN = [
    ("1", "Asli", "titik awal", lambda c: varian(c)),
    ("2", "Celah dangkal", "kesan 'telinga' hilang, lebih kokoh", lambda c: varian(c, f=0.62, s=12.5)),
    ("3", "Ligan besar", "molekul lebih menonjol", lambda c: varian(c, s=14.5, g=3.6)),
    ("4", "Lembut", "sudut membulat, ramah", lambda c: varian(c, rr=5.5, s=12)),
    ("5", "Tajam", "presisi, teknis", lambda c: varian(c, rr=0.01)),
    ("6", "Ligan atom", "bulatan, paling sederhana", lambda c: varian(c, f=0.75, ligan="bulat", s=10.5, g=4.5)),
    ("7", "Ligan cincin", "cincin benzena berongga", lambda c: varian(c, f=0.8, ligan="cincin", s=10.5, w=4.6)),
    ("8", "Garis tunggal", "monoline, ringan", lambda c: varian(c, gaya="garis", s=10, w=5.0)),
    ("9", "Faset permata", "dimensi, mewah", lambda c: varian(c, gaya="faset")),
    ("10", "Gradien", "modern, bercahaya", lambda c: varian(c, gaya="gradien", f=0.8, s=12.5)),
    ("11", "Tertambat", "ligan sudah masuk kantong", varian_tertambat),
    ("12", "Cawan", "heksagon runcing = lumpang farmasi", varian_cawan),
]


def pas(el_pts, x, y, ukuran, pad=0.08):
    """Skala & pusatkan elemen ke kotak ukuran x ukuran."""
    el, pts = el_pts
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = ukuran * (1 - 2 * pad) / max(x1 - x0, y1 - y0)
    ox = x + ukuran / 2 - (x0 + x1) / 2 * k
    oy = y + ukuran / 2 - (y0 + y1) / 2 * k
    return f'<g transform="translate({ox:.2f},{oy:.2f}) scale({k:.4f})">{"".join(el)}</g>'


def lockup(fn, c, x, y, H):
    kap = H * 0.40
    t, lb = wordmark(WM["W1"], x + H * 1.10, y + H / 2 + kap / 2, kap, c["teks"])
    return pas(fn(c), x, y, H, pad=0.02) + t, H * 1.10 + lb


def lembar():
    W, el = 1600, [""]
    el.append(teks(60, 78, "VirmoLab — variasi konsep B", 40, "#0f1b2d", 600))
    el.append(teks(60, 112, "Tunjuk nomor yang terasa paling pas — boleh gabungan (mis. 2 + 9).", 18, "#5b6575"))
    y = 150
    kol, gap = 4, 24
    cw = (W - 120 - (kol - 1) * gap) / kol
    ch = 330
    for i, (no, nama, ket, fn) in enumerate(VARIAN):
        x = 60 + (i % kol) * (cw + gap)
        yy = y + (i // kol) * (ch + gap)
        el.append(f'<rect x="{x:.1f}" y="{yy}" width="{cw:.1f}" height="{ch}" rx="18" fill="#ffffff" stroke="#e3e7ee"/>')
        el.append(pas(fn(PALET["navy"]), x + cw / 2 - 100, yy + 26, 200))
        el.append(teks(x + 22, yy + 266, f"{no} · {nama}", 21, "#0f1b2d", 600))
        el.append(teks(x + 22, yy + 294, ket, 14.5, "#5b6575"))
        # mini 24 px + ikon gelap 40 px
        el.append(pas(fn(PALET["navy"]), x + cw - 92, yy + 250, 26, pad=0.02))
        el.append(f'<rect x="{x + cw - 60:.1f}" y="{yy + 238}" width="40" height="40" rx="9" fill="#12305a"/>')
        el.append(pas(fn(dict(PALET["gelap"], latar="#12305a")), x + cw - 56, yy + 242, 32))
    y += 3 * (ch + gap) + 20

    el.append(teks(60, y + 30, "Midnight & Emas · latar gelap · lockup", 24, "#0f1b2d", 600))
    y += 50
    pw = (W - 120 - gap) / 2
    pilih = [VARIAN[1], VARIAN[8], VARIAN[9], VARIAN[10]]
    for i, (no, nama, _, fn) in enumerate(pilih):
        for j, key in enumerate(("emas", "gelap")):
            px = 60 + j * (pw + gap)
            py = y + i * 150
            p = PALET[key]
            el.append(f'<rect x="{px:.1f}" y="{py}" width="{pw:.1f}" height="130" rx="16" fill="{p["latar"]}" '
                      f'stroke="#e3e7ee"/>')
            lk, lb = lockup(fn, p, 0, 0, 78)
            el.append(f'<g transform="translate({px + (pw - lb) / 2:.1f},{py + 26})">{lk}</g>')
            el.append(teks(px + 18, py + 30, no, 15, "#9aa6b8" if key == "gelap" else "#a0a8b5", 600))
    y += 4 * 150 + 30
    el[0] = f'<rect width="{W}" height="{y}" fill="#f6f7f9"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {y}" width="{W}" height="{y}">'
            + "".join(el) + "</svg>")


if __name__ == "__main__":
    s = lembar()
    (OUT / "lembar_variasi_B.svg").write_text(s, encoding="utf-8")
    render(s, 2400, OUT / "lembar_variasi_B.png")
    print("ok", OUT / "lembar_variasi_B.png")
