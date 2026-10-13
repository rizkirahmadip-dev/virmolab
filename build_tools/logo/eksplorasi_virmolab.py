"""Eksplorasi logo VirmoLab -> keluaran/virmolab/ (lembar konsep PNG + SVG per konsep).

Konsep utama B "Heksa-Kantong": cincin heksagon (molekul) yang sisi atasnya terlipat ke dalam
membentuk V (Virmo + kantong pengikatan). Ligan heksagon kecil masuk ke celah itu; sisi miringnya
sejajar dinding V dengan celah seragam — warisan gagasan logo VirmoLab.

  .venv\\Scripts\\python.exe build_tools\\logo\\eksplorasi_virmolab.py
"""
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buat_logo import qpath_ke_svg, render, teks_ke_path  # noqa: E402

OUT = Path(__file__).resolve().parent / "keluaran" / "virmolab"
OUT.mkdir(parents=True, exist_ok=True)

S3 = math.sqrt(3)
PALET = {
    "navy":  {"badan": "#12305a", "aksen": "#2f74e0", "teks": "#12305a", "label": "Navy & Azure (lanjutan VirmoLab)"},
    "emas":  {"badan": "#0f2240", "aksen": "#c9a24e", "teks": "#0f2240", "label": "Midnight & Emas"},
    "teal":  {"badan": "#0d3b40", "aksen": "#1fa598", "teks": "#0d3b40", "label": "Teal Farmasi"},
    "gelap": {"badan": "#ffffff", "aksen": "#6aa8ff", "teks": "#ffffff", "label": "Latar gelap"},
}


# ---------- geometri ----------
def heks(cx, cy, r):
    """Heksagon sisi-datar-atas; urutan: kanan, kanan-bawah, kiri-bawah, kiri, kiri-atas, kanan-atas."""
    return [(cx + r * math.cos(math.radians(60 * k)), cy + r * math.sin(math.radians(60 * k))) for k in range(6)]


def poli_bulat(pts, rr):
    """Poligon tertutup dengan sudut membulat (radius potong rr)."""
    d = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        def ke(q):
            dx, dy = q[0] - p1[0], q[1] - p1[1]
            L = math.hypot(dx, dy)
            k = min(rr, L / 2.2) / L
            return p1[0] + dx * k, p1[1] + dy * k
        a, b = ke(p0), ke(p2)
        d.append(f"{'M' if i == 0 else 'L'}{a[0]:.2f},{a[1]:.2f}Q{p1[0]:.2f},{p1[1]:.2f} {b[0]:.2f},{b[1]:.2f}")
    return "".join(d) + "Z"


def poli(pts):
    return "M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + "Z"


# ---------- tanda (kotak 100x100) ----------
def tanda_B(c, rr=1.6):
    """Heksa-Kantong, isi penuh."""
    cx, cy, r = 50.0, 56.0, 42.0
    h = heks(cx, cy, r)
    badan = [h[4], (cx, cy), h[5], h[0], h[1], h[2], h[3]]
    s, g = 11.5, 4.2                                 # radius ligan, celah ke dinding V
    yl = cy - (2 * g + s * S3)
    return (f'<path d="{poli_bulat(badan, rr)}" fill="{c["badan"]}"/>'
            f'<path d="{poli_bulat(heks(cx, yl, s), rr * 0.6)}" fill="{c["aksen"]}"/>')


def tanda_B_garis(c, w=5.0):
    """Heksa-Kantong, versi garis tunggal (monoline)."""
    cx, cy, r = 50.0, 57.0, 40.0
    h = heks(cx, cy, r)
    badan = [h[4], (cx, cy), h[5], h[0], h[1], h[2], h[3]]
    s, g = 10.0, 4.5
    yl = cy - (2 * (g + w) + s * S3)
    gaya = f'fill="none" stroke-width="{w}" stroke-linejoin="round"'
    return (f'<path d="{poli(badan)}" stroke="{c["badan"]}" {gaya}/>'
            f'<path d="{poli(heks(cx, yl, s))}" stroke="{c["aksen"]}" {gaya}/>')


def tanda_A(c, w=7.0):
    """V-Ring: dua garis V halus + cincin ligan bersarang."""
    ax, ay = 50.0, 84.0
    top = 22.0
    dx = (ay - top) / S3
    s, g = 13.0, 4.5
    hc = 2 * (s * S3 / 2 + w / 2 + g + w / 2)
    gaya = f'fill="none" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"'
    return (f'<path d="M{ax - dx:.2f},{top}L{ax},{ay}L{ax + dx:.2f},{top}" stroke="{c["badan"]}" {gaya}/>'
            f'<path d="{poli(heks(ax, ay - hc, s))}" stroke="{c["aksen"]}" {gaya}/>')


def tanda_C(c, w=6.0):
    """Labu Erlenmeyer + cincin benzena di dalamnya."""
    gaya = f'fill="none" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"'
    labu = "M40,16L40,40L19.5,76Q15.5,85 26,85L74,85Q84.5,85 80.5,76L60,40L60,16"
    return (f'<path d="{labu}" stroke="{c["badan"]}" {gaya}/>'
            f'<path d="M34,16L66,16" stroke="{c["badan"]}" {gaya}/>'
            f'<path d="{poli(heks(50, 68, 9.5))}" stroke="{c["aksen"]}" fill="none" stroke-width="{w * 0.8}" '
            f'stroke-linejoin="round"/>'
            f'<circle cx="57" cy="50" r="3.4" fill="{c["aksen"]}"/>')


def tanda_D(c, w=8.0):
    """Monogram VL: kaki kiri V menyambung jadi alas L; ujung kanan berupa atom."""
    gaya = f'fill="none" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"'
    return (f'<path d="M16,18L41,82L86,82" stroke="{c["badan"]}" {gaya}/>'
            f'<path d="M41,82L61,30" stroke="{c["badan"]}" {gaya}/>'
            f'<circle cx="64.5" cy="21" r="8" fill="{c["aksen"]}"/>')


TANDA = {
    "A": (tanda_A, "V-Ring", "Evolusi paling dekat: V garis halus + cincin ligan"),
    "B": (tanda_B, "Heksa-Kantong", "Heksagon terlipat jadi V; ligan masuk kantong"),
    "C": (tanda_C, "Labu", "Labu Erlenmeyer + cincin benzena: 'Lab' paling literal"),
    "D": (tanda_D, "Monogram VL", "Huruf V dan L dalam satu tarikan + atom"),
}


def taruh(fn, c, x, y, ukuran):
    k = ukuran / 100.0
    return f'<g transform="translate({x:.2f},{y:.2f}) scale({k:.4f})">{fn(c)}</g>'


# ---------- wordmark ----------
WM = {
    "W1": {"keluarga": "Figtree Light", "potong": [("Virmo", 600), ("Lab", 300)], "spasi": 0.0,
           "label": "Figtree — Virmo tebal + Lab tipis"},
    "W2": {"keluarga": "Albert Sans", "potong": [("Virmo", 500), ("Lab", 500)], "spasi": 0.005,
           "label": "Albert Sans Medium — bersih, modern"},
    "W3": {"keluarga": "Montserrat", "potong": [("VIRMO", 500), ("LAB", 300)], "spasi": 0.14,
           "label": "Montserrat kapital berjarak — mewah"},
    "W4": {"keluarga": "Cormorant", "potong": [("Virmo", 600), ("Lab", 600)], "spasi": 0.01,
           "label": "Cormorant serif — klasik, akademik"},
}


def wordmark(spec, x, baseline, kap_target, warna, warna2=None):
    """Teks jadi path; kapital setinggi kap_target. Kembalikan (svg, lebar)."""
    isi, cur = [], x
    for i, (t, b) in enumerate(spec["potong"]):
        path, kotak, kap = teks_ke_path(t, spec["keluarga"], b, 200, spec["spasi"])
        sk = kap_target / kap
        if i == 0:
            cur -= kotak.left() * sk
        isi.append(f'<path d="{qpath_ke_svg(path, cur, baseline, sk)}" fill="{warna if i == 0 else (warna2 or warna)}"/>')
        cur += (kotak.right() + spec["spasi"] * 200 * 0.6) * sk
    return "".join(isi), cur - x


def lockup(fn, c, wm, x, y, H, warna2=None):
    """Tanda tinggi H + wordmark di kanan, kapital = 0.40 H, berpusat vertikal."""
    kap = H * 0.40
    tm = taruh(fn, c, x, y, H)
    t, lebar = wordmark(wm, x + H * 1.12, y + H / 2 + kap / 2, kap, c["teks"], warna2)
    return tm + t, H * 1.12 + lebar


# ---------- lembar ----------
def teks(x, y, s, ukuran=18, warna="#2a3445", berat=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-family="Segoe UI" font-size="{ukuran}" font-weight="{berat}" '
            f'fill="{warna}" text-anchor="{anchor}">{escape(s)}</text>')


def lembar():
    W, el, y = 1600, [], 0
    el.append(f'<rect width="{W}" height="3000" fill="#f6f7f9"/>')
    el.append(teks(60, 78, "VirmoLab — eksplorasi logo", 40, "#0f1b2d", 600))
    el.append(teks(60, 112, "Empat arah tanda, palet warna, pilihan huruf, dan uji ukuran kecil. Semua huruf sudah jadi kurva.",
                   18, "#5b6575"))
    y = 150
    # 1) empat konsep
    cw = (W - 120 - 3 * 24) / 4
    c = PALET["navy"]
    for i, (k, (fn, nama, ket)) in enumerate(TANDA.items()):
        x = 60 + i * (cw + 24)
        el.append(f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="380" rx="18" fill="#ffffff" stroke="#e3e7ee"/>')
        el.append(taruh(fn, c, x + cw / 2 - 110, y + 40, 220))
        el.append(teks(x + 24, y + 310, f"{k} · {nama}", 22, "#0f1b2d", 600))
        el.append(teks(x + 24, y + 340, ket, 14.5, "#5b6575"))
    y += 380 + 28
    el.append(f'<rect x="{60 + cw + 24 - 4:.1f}" y="{150 - 4}" width="{cw + 8:.1f}" height="388" rx="21" fill="none" '
              f'stroke="#2f74e0" stroke-width="2.5"/>')
    el.append(teks(60 + cw + 24 + cw - 16, 150 + 30, "REKOMENDASI", 13, "#2f74e0", 700, "end"))

    # 2) lockup konsep B, tiga palet + gelap
    el.append(teks(60, y + 40, "Konsep B dalam palet warna", 24, "#0f1b2d", 600))
    y += 60
    pw = (W - 120 - 24) / 2
    for i, key in enumerate(["navy", "emas", "teal", "gelap"]):
        px = 60 + (i % 2) * (pw + 24)
        py = y + (i // 2) * 214
        p = PALET[key]
        latar = "#0e1a2c" if key == "gelap" else "#ffffff"
        el.append(f'<rect x="{px:.1f}" y="{py}" width="{pw:.1f}" height="190" rx="18" fill="{latar}" stroke="#e3e7ee"/>')
        lk, lb = lockup(tanda_B, p, WM["W1"], 0, 0, 104)
        ox = px + (pw - lb) / 2
        el.append(f'<g transform="translate({ox:.1f},{py + 34})">{lk}</g>')
        el.append(teks(px + 20, py + 174, p["label"], 13.5, "#9aa6b8" if key == "gelap" else "#7a8494"))
    y += 2 * 214 + 20

    # 3) pilihan huruf
    el.append(teks(60, y + 40, "Pilihan huruf (wordmark)", 24, "#0f1b2d", 600))
    y += 60
    for i, (k, spec) in enumerate(WM.items()):
        px = 60 + (i % 2) * (pw + 24)
        py = y + (i // 2) * 170
        el.append(f'<rect x="{px:.1f}" y="{py}" width="{pw:.1f}" height="150" rx="18" fill="#ffffff" stroke="#e3e7ee"/>')
        t, lb = wordmark(spec, 0, 0, 46, PALET["navy"]["teks"], PALET["navy"]["aksen"] if k in ("W1", "W3") else None)
        el.append(f'<g transform="translate({px + (pw - lb) / 2:.1f},{py + 88})">{t}</g>')
        el.append(teks(px + 20, py + 134, f"{k} · {spec['label']}", 13.5, "#7a8494"))
    y += 2 * 170 + 20

    # 4) uji ukuran kecil
    el.append(teks(60, y + 40, "Uji ukuran kecil (ikon aplikasi / favicon)", 24, "#0f1b2d", 600))
    y += 60
    el.append(f'<rect x="60" y="{y}" width="{W - 120}" height="150" rx="18" fill="#ffffff" stroke="#e3e7ee"/>')
    x = 90
    for k, (fn, nama, _) in TANDA.items():
        for u in (16, 24, 32, 64):
            el.append(taruh(fn, c, x, y + 105 - u, u))
            x += u + 16
        el.append(teks(x - 70, y + 135, k, 15, "#7a8494", 600, "middle"))
        x += 46
    # ikon aplikasi (kotak membulat) konsep B
    for u, gx in ((64, x + 10), (96, x + 94)):
        el.append(f'<g transform="translate({gx},{y + 112 - u})"><rect width="{u}" height="{u}" rx="{u * 0.22}" '
                  f'fill="#12305a"/>{taruh(tanda_B, PALET["gelap"], u * 0.14, u * 0.12, u * 0.72)}</g>')
    y += 150 + 50
    tinggi = y
    el[0] = f'<rect width="{W}" height="{tinggi}" fill="#f6f7f9"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {tinggi}" width="{W}" height="{tinggi}">'
            + "".join(el) + "</svg>")


def svg_tanda(fn, c, judul):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="512" height="512">'
            f'<title>{judul}</title>{fn(c)}</svg>\n')


if __name__ == "__main__":
    s = lembar()
    (OUT / "lembar_konsep.svg").write_text(s, encoding="utf-8")
    render(s, 2400, OUT / "lembar_konsep.png")
    for k, (fn, nama, _) in TANDA.items():
        (OUT / f"tanda_{k}.svg").write_text(svg_tanda(fn, PALET["navy"], f"VirmoLab {nama}"), encoding="utf-8")
    (OUT / "tanda_B_garis.svg").write_text(svg_tanda(tanda_B_garis, PALET["navy"], "VirmoLab B garis"), encoding="utf-8")
    print("ok", OUT)
