"""Produksi logo final VirmoLab -> branding/ (SVG vektor + PNG + ICO + lembar panduan merek).

Tanda "Heksa-Kantong Faset": cincin heksagon (molekul) yang sisi atasnya terlipat ke dalam membentuk V
(Virmo + kantong pengikatan protein). Ligan heksagon masuk ke kantong; sisi miringnya sejajar dinding V
dengan celah seragam (komplementaritas bentuk). Lima faset dari titik kantong memberi kesan permata.

  .venv\\Scripts\\python.exe build_tools\\logo\\produksi_virmolab.py
"""
import base64
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buat_logo import qpath_ke_svg, render, teks_ke_path  # noqa: E402
from eksplorasi_virmolab import S3, WM, heks, poli, poli_bulat, wordmark  # noqa: E402

AKAR = Path(__file__).resolve().parents[2]
B = AKAR / "branding"
B.mkdir(exist_ok=True)

NAVY = "#12305a"
AZURE = "#2f74e0"
AZURE_MUDA = "#6aa8ff"
ABU_TAG = "#6b7a90"
TAG = "VIRTUAL MOLECULAR LAB"
FONT = "Figtree Light"          # nama keluarga Figtree (OFL) seperti terdaftar di Windows


def campur(a, b, t):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def _nada_navy(dasar):
    """Lima faset kanan-atas -> kiri-atas: terang di kanan, gelap di kiri (cahaya dari kanan atas)."""
    return [campur(dasar, "#ffffff", 0.16), campur(dasar, "#ffffff", 0.09), campur(dasar, "#ffffff", 0.03),
            campur(dasar, "#000000", 0.05), campur(dasar, "#000000", 0.12)]


GAYA = {
    "warna": {"faset": _nada_navy(NAVY), "dasar": NAVY, "ligan": AZURE, "teks": NAVY, "tag": ABU_TAG},
    "putih": {"faset": ["#ffffff", "#f1f6fd", "#e4edf9", "#cfdef3", "#bccfeb"], "dasar": "#e4edf9",
              "ligan": AZURE_MUDA, "teks": "#ffffff", "tag": "#b9c7dc"},
    "hitam": {"faset": None, "dasar": "#111111", "ligan": "#111111", "teks": "#111111", "tag": "#111111"},
}

# ---------------------------------------------------------------- geometri tanda
CX, CY, R = 50.0, 56.0, 42.0
S_LIG, CELAH = 11.5, 4.2
_h = heks(CX, CY, R)
APEX = (CX, CY)
BADAN = [_h[4], APEX, _h[5], _h[0], _h[1], _h[2], _h[3]]
Y_LIG = CY - (2 * CELAH + S_LIG * S3)          # sisi miring ligan sejajar dinding V, celah = CELAH
LIGAN = heks(CX, Y_LIG, S_LIG)
_xs = [p[0] for p in BADAN + LIGAN]
_ys = [p[1] for p in BADAN + LIGAN]
BB = (min(_xs), min(_ys), max(_xs), max(_ys))   # x0, y0, x1, y1


def tanda_elemen(g):
    el = [f'<path d="{poli(BADAN)}" fill="{g["dasar"]}"/>']
    if g["faset"]:
        luar = [_h[5], _h[0], _h[1], _h[2], _h[3], _h[4]]
        for (p, q), w in zip(zip(luar, luar[1:]), g["faset"]):
            el.append(f'<path d="{poli([APEX, p, q])}" fill="{w}"/>')
    el.append(f'<path d="{poli_bulat(LIGAN, 0.95)}" fill="{g["ligan"]}"/>')
    return "".join(el)


def taruh_tanda(g, x, y, tinggi):
    """Tanda dengan tepi atas di y dan tinggi kotak batas = tinggi. Kembalikan (svg, lebar)."""
    k = tinggi / (BB[3] - BB[1])
    return (f'<g transform="translate({x - BB[0] * k:.3f},{y - BB[1] * k:.3f}) scale({k:.5f})">{tanda_elemen(g)}</g>',
            (BB[2] - BB[0]) * k)


def _svg(w, h, isi, judul="VirmoLab"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" width="{w:.0f}" height="{h:.0f}">'
            f'<title>{judul}</title>' + "".join(isi) + "</svg>\n")


def _tagline(x, baseline, kap, warna, tengah_w=None):
    path, kotak, k0 = teks_ke_path(TAG, FONT, 500, 200, 0.26)
    sk = kap / k0
    lebar = kotak.width() * sk
    if tengah_w is not None:
        x = tengah_w / 2 - lebar / 2
    return f'<path d="{qpath_ke_svg(path, x - kotak.left() * sk, baseline, sk)}" fill="{warna}"/>', lebar


# ---------------------------------------------------------------- lockup
def tanda(gaya="warna", ukuran=512, pad=0.08):
    g = GAYA[gaya]
    w, h = BB[2] - BB[0], BB[3] - BB[1]
    t = ukuran * (1 - 2 * pad) * min(1, h / w)
    tw = t * w / h
    s, _ = taruh_tanda(g, (ukuran - tw) / 2, (ukuran - t) / 2, t)
    return _svg(ukuran, ukuran, [s])


def ikon(ukuran=512):
    """Ikon aplikasi: kotak membulat navy + tanda putih berfaset."""
    w, h = BB[2] - BB[0], BB[3] - BB[1]
    t = ukuran * 0.62
    tw = t * w / h
    s, _ = taruh_tanda(GAYA["putih"], (ukuran - tw) / 2, (ukuran - t) / 2 + ukuran * 0.005, t)
    return _svg(ukuran, ukuran, [f'<rect width="{ukuran}" height="{ukuran}" rx="{ukuran * 0.22:.1f}" fill="{NAVY}"/>', s])


def horizontal(gaya="warna", tagline=True, latar=None):
    g = GAYA[gaya]
    H = 200.0
    pad = H * 0.22
    s_t, tw = taruh_tanda(g, pad, pad, H)
    tx = pad + tw + H * 0.24
    kap = H * 0.40
    if tagline:
        kap_tag = H * 0.075
        jarak = H * 0.16
        blok = kap + jarak + kap_tag
        base = pad + (H - blok) / 2 + kap
    else:
        base = pad + H / 2 + kap / 2
    s_w, lw = wordmark(WM["W1"], tx, base, kap, g["teks"])
    isi = [f'<rect width="100%" height="100%" fill="{latar}"/>'] if latar else []
    isi += [s_t, s_w]
    lebar = tx + lw
    if tagline:
        s_g, lg = _tagline(tx + H * 0.012, base + jarak + kap_tag, kap_tag, g["tag"])
        isi.append(s_g)
        lebar = max(lebar, tx + lg)
    return _svg(lebar + pad, H + 2 * pad, isi)


def bertumpuk(gaya="warna", tagline=True):
    g = GAYA[gaya]
    H = 200.0
    pad = H * 0.25
    kap = H * 0.30
    _, lw = wordmark(WM["W1"], 0, 0, kap, g["teks"])
    w_t = (BB[2] - BB[0]) / (BB[3] - BB[1]) * H
    W = max(w_t, lw) + 2 * pad
    s_t, _ = taruh_tanda(g, (W - w_t) / 2, pad, H)
    base = pad + H + H * 0.24 + kap
    s_w, _ = wordmark(WM["W1"], (W - lw) / 2, base, kap, g["teks"])
    isi = [s_t, s_w]
    Ht = base + pad
    if tagline:
        kap_tag = H * 0.058
        bt = base + H * 0.15 + kap_tag
        s_g, _ = _tagline(0, bt, kap_tag, g["tag"], tengah_w=W)
        isi.append(s_g)
        Ht = bt + pad
    return _svg(W, Ht, isi)


def tulis(nama, svg, png_lebar=None, latar_png=None):
    (B / f"{nama}.svg").write_text(svg, encoding="utf-8")
    if png_lebar:
        render(svg, png_lebar, B / f"{nama}.png", latar_png)


# ---------------------------------------------------------------- berkas
tulis("virmolab_logo_horizontal", horizontal(), 2400)
tulis("virmolab_logo_horizontal_tanpa_tagline", horizontal(tagline=False), 2400)
tulis("virmolab_logo_horizontal_putih", horizontal("putih"), 2400)
tulis("virmolab_logo_horizontal_tanpa_tagline_putih", horizontal("putih", tagline=False), 2400)
tulis("virmolab_logo_horizontal_hitam", horizontal("hitam"), 2400)
tulis("virmolab_logo_bertumpuk", bertumpuk(), 1600)
tulis("virmolab_logo_bertumpuk_putih", bertumpuk("putih"), 1600)
tulis("virmolab_tanda", tanda(), 1024)
tulis("virmolab_tanda_putih", tanda("putih"), 1024)
tulis("virmolab_tanda_hitam", tanda("hitam"), 1024)
IKON = ikon()
tulis("virmolab_ikon", IKON, 1024)

# ICO multi-ukuran untuk aplikasi & installer
from PIL import Image  # noqa: E402
UK = [16, 20, 24, 32, 40, 48, 64, 128, 256]
gambar = {}
for n in UK:
    render(IKON, n, B / "_i.png")
    gambar[n] = Image.open(B / "_i.png").convert("RGBA")
    gambar[n].load()
gambar[256].save(B / "virmolab.ico", sizes=[(n, n) for n in UK], append_images=[gambar[n] for n in UK[:-1]])


# ---------------------------------------------------------------- panduan merek
def _teks(x, y, s, uk=18, warna="#465263", berat=400):
    return (f'<text x="{x}" y="{y}" font-family="Segoe UI" font-size="{uk}" font-weight="{berat}" '
            f'fill="{warna}">{escape(s)}</text>')


def _panel(x, y, w, h, svg_logo, latar, label, isi=0.78, garis=True):
    import re
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg_logo).group(1).split()]
    k = min(w * isi / vb[2], h * 0.70 / vb[3])
    rw, rh = vb[2] * k, vb[3] * k
    dalam = re.sub(r"^<svg[^>]*>|<title>.*?</title>|</svg>\s*$", "", svg_logo.strip())
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" fill="{latar}"'
            + (' stroke="#e3e7ee"' if garis else "") + "/>"
            + f'<g transform="translate({x + (w - rw) / 2:.2f},{y + (h - rh) / 2:.2f}) scale({k:.5f})">{dalam}</g>'
            + _teks(x, y + h + 30, label, 17, "#7b8698"))


def _png_data(svg, n):
    render(svg, n, B / "_i.png")
    return "data:image/png;base64," + base64.b64encode((B / "_i.png").read_bytes()).decode()


W, m = 2400, 120
el = [""]
el.append(_teks(m, 110, "VirmoLab · Panduan logo", 46, NAVY, 600))
el.append(_teks(m, 160, "Heksagon (cincin molekul) yang sisi atasnya terlipat membentuk V: kantong pengikatan protein "
                        "sekaligus huruf V dari Virmo.", 21, "#5b6b82"))
el.append(_teks(m, 192, "Ligan heksagon masuk ke kantong dengan celah seragam (komplementaritas bentuk), "
                        "dan lima faset memberi kesan permata yang elegan.", 21, "#5b6b82"))
y = 250
el.append(_panel(m, y, W - 2 * m, 680, horizontal(), "#f3f5f8", "Logo utama (horizontal) - latar terang", 0.74, False))
y += 750
hw = (W - 2 * m - 40) / 2
el.append(_panel(m, y, hw, 500, horizontal("putih"), NAVY, "Latar gelap / navy", 0.80, False))
el.append(_panel(m + hw + 40, y, hw, 500, horizontal("hitam"), "#ffffff", "Satu warna (cetak hitam)", 0.80))
y += 570
cw = (W - 2 * m - 3 * 40) / 4
el.append(_panel(m, y, cw * 2 + 40, 640, bertumpuk(), "#f3f5f8", "Bertumpuk (sampul, poster, slide judul)", 0.62, False))
el.append(_panel(m + (cw + 40) * 2, y, cw, 640, tanda(), "#ffffff", "Tanda saja", 0.66))
el.append(_panel(m + (cw + 40) * 3, y, cw, 640, IKON, "#ffffff", "Ikon aplikasi", 0.62))
y += 720
el.append(_teks(m, y + 10, "Warna", 26, NAVY, 600))
WARNA = (("Navy VirmoLab", NAVY), ("Azure ligan", AZURE), ("Azure terang (latar gelap)", AZURE_MUDA),
         ("Faset terang", GAYA["warna"]["faset"][0]), ("Abu tagline", ABU_TAG))
sw = (W - 2 * m - 4 * 30) / 5
for i, (nama, hexa) in enumerate(WARNA):
    x = m + i * (sw + 30)
    rgb = " · ".join(str(int(hexa[j:j + 2], 16)) for j in (1, 3, 5))
    el.append(f'<rect x="{x:.1f}" y="{y + 40}" width="{sw:.1f}" height="150" rx="14" fill="{hexa}"/>')
    el.append(_teks(x, y + 228, nama, 19, NAVY, 600))
    el.append(_teks(x, y + 256, f"{hexa.upper()}   RGB {rgb}", 17, "#5b6b82"))
y += 320
el.append(_teks(m, y + 10, "Keterbacaan ukuran kecil & aturan", 26, NAVY, 600))
x = m
for n in (16, 24, 32, 48, 64, 128):
    el.append(f'<image x="{x}" y="{y + 50 + 128 - n}" width="{n}" height="{n}" xlink:href="{_png_data(IKON, n)}"/>')
    el.append(_teks(x + n / 2 - 20, y + 212, f"{n} px", 16, "#7b8698"))
    x += n + 56
(B / "_i.png").unlink(missing_ok=True)
ATURAN = ["Ruang kosong minimal di sekeliling logo = tinggi ligan heksagon.",
          "Ukuran minimum: logo horizontal 30 mm / 160 px lebar; tanda 6 mm / 24 px.",
          "Jangan memutar, meregangkan, memberi bayangan, atau garis tepi; faset hanya pada versi warna.",
          "Di latar foto pakai versi putih di atas panel navy; cetak satu warna pakai versi hitam (tanpa faset).",
          "Huruf: Figtree SemiBold + Light (SIL OFL), sudah jadi kurva, tidak butuh font terpasang."]
for i, t in enumerate(ATURAN):
    el.append(_teks(m + 820, y + 70 + i * 34, "-  " + t, 18))
Ht = y + 270
el[0] = f'<rect width="{W}" height="{Ht}" fill="#ffffff"/>'
panduan = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'viewBox="0 0 {W} {Ht}" width="{W}" height="{Ht}">' + "".join(el) + "</svg>")
render(panduan, W, B / "virmolab_panduan_logo.png")
(B / "_i.png").unlink(missing_ok=True)
print("selesai:", sorted(f.name for f in B.glob("virmolab*")))
