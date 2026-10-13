"""Logo VirmoLab: tanda "V-kantong + heksagon-ligan" dan wordmark (huruf diubah jadi path).

Gagasan: huruf V adalah kantong pengikatan protein; heksagon (cincin ligan) masuk ke dalamnya.
Sisi bawah-miring heksagon sejajar persis dengan sisi dalam V dengan celah seragam —
komplementaritas bentuk, inti dari molecular docking.

  .venv\\Scripts\\python.exe build_tools\\logo\\buat_logo.py [--lembar]
"""
import math
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QPainter, QPainterPath
from PySide6.QtSvg import QSvgRenderer

app = QGuiApplication.instance() or QGuiApplication(sys.argv)
OUT = Path(__file__).resolve().parent / "keluaran"
OUT.mkdir(exist_ok=True)

NAVY = "#173b6c"
BIRU = "#2b6fd6"
BIRU_MUDA = "#5b9af0"
PUTIH = "#ffffff"
S60, C60 = math.sin(math.radians(60)), 0.5


# ------------------------------------------------------------------ tanda
def geometri(g=0.30, t=0.92, atas=1.95, sudut=30.0):
    """Koordinat tanda dalam satuan radius heksagon (pusat heksagon di 0,0; y ke bawah).

    g: celah heksagon–V, t: tebal lengan V (tegak lurus), atas: tinggi ujung lengan di atas pusat heksagon,
    sudut: kemiringan lengan dari vertikal (30° = sejajar sisi heksagon flat-top)."""
    a = math.radians(sudut)
    d = (math.sin(a), math.cos(a))             # arah lengan kiri ke bawah-kanan
    n = (-math.cos(a), math.sin(a))            # normal keluar sisi bawah-kiri
    # titik pada sisi bawah-kiri heksagon (flat-top): (-1, 0)
    def garis(off):
        p = (-1 + n[0] * off, 0 + n[1] * off)
        s = -p[0] / d[0]                       # titik potong x = 0
        return p, p[1] + d[1] * s

    (p_in, y_in), (p_out, y_out) = garis(g), garis(g + t)

    def x_pada(p, y):                          # x garis kiri pada ketinggian y
        return p[0] + d[0] * (y - p[1]) / d[1]
    ya = -atas
    v = [(x_pada(p_out, ya), ya), (x_pada(p_in, ya), ya), (0, y_in),
         (-x_pada(p_in, ya), ya), (-x_pada(p_out, ya), ya), (0, y_out)]
    hexa = [(math.cos(math.radians(60 * k)), math.sin(math.radians(60 * k))) for k in range(6)]
    return v, hexa


def geometri_kantong(g=0.16, t=0.62, atas=1.30, ujung=0.0, sudut=30.0):
    """Varian 'kantong': sisi dalam V mengikuti setengah bawah heksagon (dua sisi miring + dasar datar)
    dengan celah seragam g — kantong berbentuk persis komplemen ligan.

    ujung: potongan datar pada titik bawah luar (0 = runcing)."""
    a = math.radians(sudut)
    d = (math.sin(a), math.cos(a))
    n = (-math.cos(a), math.sin(a))
    h = S60                                     # setengah tinggi heksagon flat-top (r = 1)

    def titik_kiri(off, y):                     # garis sejajar sisi bawah-kiri, digeser off, pada ketinggian y
        p = (-1 + n[0] * off, n[1] * off)
        return (p[0] + d[0] * (y - p[1]) / d[1], y)

    yb = h + g                                  # dasar dalam kantong
    ya = -atas
    il_atas, il_bawah = titik_kiri(g, ya), titik_kiri(g, yb)
    ol_atas = titik_kiri(g + t, ya)
    # titik bawah luar: garis luar kiri memotong x = 0
    p = (-1 + n[0] * (g + t), n[1] * (g + t))
    y_luar = p[1] + d[1] * (-p[0] / d[0])
    luar_bawah = [(0, y_luar)] if ujung <= 0 else [(-ujung, titik_kiri(g + t, 0)[1] * 0 + y_luar - ujung / math.tan(a)),
                                                   (ujung, y_luar - ujung / math.tan(a))]
    v = [ol_atas, il_atas, il_bawah, (-il_bawah[0], yb), (-il_atas[0], ya), (-ol_atas[0], ya)]
    v += luar_bawah[::-1] if ujung > 0 else luar_bawah
    hexa = [(math.cos(math.radians(60 * k)), math.sin(math.radians(60 * k))) for k in range(6)]
    return v, hexa


def path_poligon(pts, sx, ox, oy):
    return "M" + " L".join(f"{ox + x * sx:.3f},{oy + y * sx:.3f}" for x, y in pts) + " Z"


def ambil_geo(geo):
    geo = dict(geo)
    bentuk = geo.pop("bentuk", "kantong")
    return geometri_kantong(**geo) if bentuk == "kantong" else geometri(**geo)


def tanda_svg(warna_v=NAVY, warna_h=BIRU, gaya="isi", ukuran=100, latar=None, rx=0, pad=0.10, **geo):
    """SVG tanda saja, persegi `ukuran`."""
    v, hexa = ambil_geo(geo)
    xs = [p[0] for p in v + hexa]
    ys = [p[1] for p in v + hexa]
    lebar, tinggi = max(xs) - min(xs), max(ys) - min(ys)
    sx = ukuran * (1 - 2 * pad) / max(lebar, tinggi)
    ox = ukuran / 2 - (max(xs) + min(xs)) / 2 * sx
    oy = ukuran / 2 - (max(ys) + min(ys)) / 2 * sx
    isi = []
    if latar:
        isi.append(f'<rect width="{ukuran}" height="{ukuran}" rx="{rx}" fill="{latar}"/>')
    isi.append(f'<path d="{path_poligon(v, sx, ox, oy)}" fill="{warna_v}"/>')
    if gaya == "isi":
        isi.append(f'<path d="{path_poligon(hexa, sx, ox, oy)}" fill="{warna_h}"/>')
    elif gaya == "cincin":       # cincin benzena: heksagon garis + lingkaran dalam
        w = 0.22
        luar = [(x * 1.0, y * 1.0) for x, y in hexa]
        dalam = [(x * (1 - w / S60), y * (1 - w / S60)) for x, y in hexa]
        d = path_poligon(luar, sx, ox, oy) + " " + path_poligon(dalam[::-1], sx, ox, oy)
        isi.append(f'<path d="{d}" fill="{warna_h}" fill-rule="evenodd"/>')
        isi.append(f'<circle cx="{ox:.3f}" cy="{oy:.3f}" r="{0.36 * sx:.3f}" fill="none" stroke="{warna_h}" '
                   f'stroke-width="{0.14 * sx:.3f}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ukuran} {ukuran}" width="{ukuran}" '
            f'height="{ukuran}">' + "".join(isi) + "</svg>"), (sx, ox, oy)


# --------------------------------------------------------------- wordmark
def teks_ke_path(teks, keluarga, berat, ukuran_pt=100, spasi=0.0, potong=None):
    """Teks -> (data path SVG, lebar, tinggi-huruf-kapital, baseline). potong: [(teks, berat)] untuk dua bobot."""
    bagian = potong or [(teks, berat)]
    path = QPainterPath()
    x = 0.0
    tinggi_kap = 0
    for t, b in bagian:
        f = QFont(keluarga)
        f.setPixelSize(ukuran_pt)
        f.setWeight(QFont.Weight(b))
        f.setLetterSpacing(QFont.AbsoluteSpacing, spasi * ukuran_pt)
        f.setHintingPreference(QFont.PreferNoHinting)
        fm = QFontMetricsF(f)
        tinggi_kap = fm.capHeight()
        path.addText(QPointF(x, 0), f, t)
        x += fm.horizontalAdvance(t)
    path = path.simplified()   # satukan kontur tumpang-tindih (font variabel) agar tepi huruf bersih
    kotak = path.boundingRect()
    return path, kotak, tinggi_kap


def qpath_ke_svg(path, dx=0.0, dy=0.0, sk=1.0):
    out, i = [], 0
    while i < path.elementCount():
        e = path.elementAt(i)
        if e.type == QPainterPath.MoveToElement:
            out.append(f"M{dx + e.x * sk:.2f},{dy + e.y * sk:.2f}")
        elif e.type == QPainterPath.LineToElement:
            out.append(f"L{dx + e.x * sk:.2f},{dy + e.y * sk:.2f}")
        elif e.type == QPainterPath.CurveToElement:
            c1, c2 = path.elementAt(i + 1), path.elementAt(i + 2)
            out.append(f"C{dx + e.x * sk:.2f},{dy + e.y * sk:.2f} {dx + c1.x * sk:.2f},{dy + c1.y * sk:.2f} "
                       f"{dx + c2.x * sk:.2f},{dy + c2.y * sk:.2f}")
            i += 2
        i += 1
    return "".join(out)


def lockup_svg(wm, mode="horizontal", warna_v=NAVY, warna_h=BIRU, warna_t=NAVY, latar=None, tagline=None,
               warna_tag="#7b8698", **geo):
    """wm: dict keluarga/bobot/potong/spasi."""
    path, kotak, kap = teks_ke_path("VirmoLab", wm["keluarga"], wm.get("berat", 600), 200, wm.get("spasi", 0),
                                    wm.get("potong"))
    v, hexa = ambil_geo(geo)
    xs = [p[0] for p in v + hexa]
    ys = [p[1] for p in v + hexa]
    mw, mh = max(xs) - min(xs), max(ys) - min(ys)
    if mode == "horizontal":
        H = 200.0
        sx = H / mh                                   # tinggi tanda = 200
        kap_target = H * 0.62                          # tinggi kapital wordmark relatif tanda
        sk = kap_target / kap
        gap = H * 0.34
        lebar_teks = kotak.width() * sk
        pad = H * 0.18
        W = pad + mw * sx + gap + lebar_teks + pad
        Ht = H + 2 * pad + (H * 0.28 if tagline else 0)
        ox = pad - min(xs) * sx
        oy = pad - min(ys) * sx
        # baseline teks: pusat optik kapital sejajar pusat tinggi tanda
        base = pad + H / 2 + kap_target / 2
        tx = pad + mw * sx + gap - kotak.left() * sk
        d_teks = qpath_ke_svg(path, tx, base, sk)
        isi = []
        if latar:
            isi.append(f'<rect width="{W:.0f}" height="{Ht:.0f}" fill="{latar}"/>')
        isi.append(f'<path d="{path_poligon(v, sx, ox, oy)}" fill="{warna_v}"/>')
        isi.append(f'<path d="{path_poligon(hexa, sx, ox, oy)}" fill="{warna_h}"/>')
        isi.append(f'<path d="{d_teks}" fill="{warna_t}"/>')
        if tagline:
            tp, tk, tkap = teks_ke_path(tagline, wm.get("keluarga_tag", wm["keluarga"]), 400, 200,
                                        wm.get("spasi_tag", 0.12))
            tsk = (H * 0.115) / tkap
            isi.append(f'<path d="{qpath_ke_svg(tp, tx + (kotak.left() - tk.left()) * sk * 0 + 2, base + H * 0.30, tsk)}" '
                       f'fill="{warna_tag}"/>')
    else:  # bertumpuk
        H = 200.0
        sx = H / mh
        kap_target = H * 0.40
        sk = kap_target / kap
        lebar_teks = kotak.width() * sk
        pad = H * 0.2
        W = max(mw * sx, lebar_teks) + 2 * pad
        Ht = pad + H + H * 0.30 + kap_target + pad
        ox = W / 2 - (max(xs) + min(xs)) / 2 * sx
        oy = pad - min(ys) * sx
        base = pad + H + H * 0.30 + kap_target
        tx = W / 2 - lebar_teks / 2 - kotak.left() * sk
        isi = []
        if latar:
            isi.append(f'<rect width="{W:.0f}" height="{Ht:.0f}" fill="{latar}"/>')
        isi.append(f'<path d="{path_poligon(v, sx, ox, oy)}" fill="{warna_v}"/>')
        isi.append(f'<path d="{path_poligon(hexa, sx, ox, oy)}" fill="{warna_h}"/>')
        isi.append(f'<path d="{qpath_ke_svg(path, tx, base, sk)}" fill="{warna_t}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {Ht:.0f}" width="{W:.0f}" '
            f'height="{Ht:.0f}">' + "".join(isi) + "</svg>")


def render(svg, lebar, path, latar=None):
    r = QSvgRenderer(QByteArray(svg.encode()))
    s = r.defaultSize()
    tinggi = int(lebar * s.height() / s.width())
    img = QImage(lebar, tinggi, QImage.Format_ARGB32)
    img.fill(QColor(latar) if latar else Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p, QRectF(0, 0, lebar, tinggi))
    p.end()
    img.save(str(path))
    return img
