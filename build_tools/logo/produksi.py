"""ARSIP: logo lama VirmoDock -> branding/arsip_virmodock/. Logo aktif: produksi_virmolab.py.

Produksi logo VirmoDock -> branding/arsip_virmodock/ (SVG vektor + PNG + ICO + lembar panduan merek).

  .venv\\Scripts\\python.exe build_tools\\logo\\produksi.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buat_logo import (BIRU, BIRU_MUDA, NAVY, ambil_geo, path_poligon, qpath_ke_svg, render,  # noqa: E402
                       teks_ke_path)
from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402

AKAR = Path(__file__).resolve().parents[2]
B = AKAR / "branding" / "arsip_virmodock"
B.mkdir(exist_ok=True)

GEO = {"bentuk": "kantong", "g": 0.16, "t": 0.70, "atas": 1.15}
GEO_IKON = {"bentuk": "kantong", "g": 0.26, "t": 0.78, "atas": 1.15}   # celah lebih lebar agar terbaca di 16 px
WM = {"keluarga": "Bahnschrift", "berat": 600, "spasi": 0.0}
TAG = "MOLECULAR DOCKING"


def bbox(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def tanda(warna_v, warna_h, geo=GEO, ukuran=512, latar=None, rx=0, pad=0.08):
    v, h = ambil_geo(geo)
    x0, y0, x1, y1 = bbox(v + h)
    sx = ukuran * (1 - 2 * pad) / max(x1 - x0, y1 - y0)
    ox = ukuran / 2 - (x0 + x1) / 2 * sx
    oy = ukuran / 2 - (y0 + y1) / 2 * sx
    isi = [f'<rect width="{ukuran}" height="{ukuran}" rx="{rx}" fill="{latar}"/>'] if latar else []
    isi += [f'<path d="{path_poligon(v, sx, ox, oy)}" fill="{warna_v}"/>',
            f'<path d="{path_poligon(h, sx, ox, oy)}" fill="{warna_h}"/>']
    return _svg(ukuran, ukuran, isi)


def _svg(w, h, isi, judul="VirmoDock"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" width="{w:.0f}" height="{h:.0f}">'
            f'<title>{judul}</title>' + "".join(isi) + "</svg>\n")


def horizontal(warna_v=NAVY, warna_h=BIRU, warna_t=NAVY, warna_tag="#5b6b82", tagline=True, latar=None):
    """Puncak kapital = ujung lengan V; garis dasar tagline = ujung bawah V."""
    v, h = ambil_geo(GEO)
    x0, y0, x1, y1 = bbox(v + h)
    H = 200.0
    sx = H / (y1 - y0)
    path, kotak, kap = teks_ke_path("VirmoDock", WM["keluarga"], WM["berat"], 200, WM["spasi"])
    kap_t = H * 0.50
    sk = kap_t / kap
    pad = H * 0.22
    gap = H * 0.30
    mx = pad - x0 * sx
    my = pad - y0 * sx
    y_atas = pad + (min(p[1] for p in v) - y0) * sx           # ujung lengan
    tx = pad + (x1 - x0) * sx + gap
    base = y_atas + kap_t
    d_t = qpath_ke_svg(path, tx - kotak.left() * sk, base, sk)
    W = tx + kotak.width() * sk + pad
    isi = [f'<rect width="{W:.1f}" height="{H + 2 * pad:.1f}" fill="{latar}"/>'] if latar else []
    isi += [f'<path d="{path_poligon(v, sx, mx, my)}" fill="{warna_v}"/>',
            f'<path d="{path_poligon(h, sx, mx, my)}" fill="{warna_h}"/>',
            f'<path d="{d_t}" fill="{warna_t}"/>']
    if tagline:
        tp, tk, tkap = teks_ke_path(TAG, WM["keluarga"], 400, 200, 0.22)
        tsk = (H * 0.095) / tkap
        isi.append(f'<path d="{qpath_ke_svg(tp, tx - tk.left() * tsk, pad + H, tsk)}" fill="{warna_tag}"/>')
    return _svg(W, H + 2 * pad, isi)


def bertumpuk(warna_v=NAVY, warna_h=BIRU, warna_t=NAVY, warna_tag="#5b6b82", latar=None):
    v, h = ambil_geo(GEO)
    x0, y0, x1, y1 = bbox(v + h)
    H = 200.0
    sx = H / (y1 - y0)
    path, kotak, kap = teks_ke_path("VirmoDock", WM["keluarga"], WM["berat"], 200, WM["spasi"])
    kap_t = H * 0.30
    sk = kap_t / kap
    tp, tk, tkap = teks_ke_path(TAG, WM["keluarga"], 400, 200, 0.28)
    tsk = (H * 0.065) / tkap
    pad = H * 0.25
    W = max((x1 - x0) * sx, kotak.width() * sk, tk.width() * tsk) + 2 * pad
    mx = W / 2 - (x0 + x1) / 2 * sx
    my = pad - y0 * sx
    base = pad + H + H * 0.22 + kap_t
    base_tag = base + H * 0.17
    Ht = base_tag + pad
    isi = [f'<rect width="{W:.1f}" height="{Ht:.1f}" fill="{latar}"/>'] if latar else []
    isi += [f'<path d="{path_poligon(v, sx, mx, my)}" fill="{warna_v}"/>',
            f'<path d="{path_poligon(h, sx, mx, my)}" fill="{warna_h}"/>',
            f'<path d="{qpath_ke_svg(path, W / 2 - kotak.width() * sk / 2 - kotak.left() * sk, base, sk)}" fill="{warna_t}"/>',
            f'<path d="{qpath_ke_svg(tp, W / 2 - tk.width() * tsk / 2 - tk.left() * tsk, base_tag, tsk)}" fill="{warna_tag}"/>']
    return _svg(W, Ht, isi)


def tulis(nama, svg, png_lebar=None, latar_png=None):
    (B / f"{nama}.svg").write_text(svg, encoding="utf-8")
    if png_lebar:
        render(svg, png_lebar, B / f"{nama}.png", latar_png)


# ---------------------------------------------------------------- berkas
tulis("virmodock_logo_horizontal", horizontal(), 2400)
tulis("virmodock_logo_horizontal_tanpa_tagline", horizontal(tagline=False), 2400)
tulis("virmodock_logo_horizontal_putih", horizontal("#ffffff", BIRU_MUDA, "#ffffff", "#c9d8ee"), 2400)
tulis("virmodock_logo_horizontal_tanpa_tagline_putih", horizontal("#ffffff", BIRU_MUDA, "#ffffff", tagline=False), 2400)
tulis("virmodock_logo_horizontal_hitam", horizontal("#111111", "#111111", "#111111", "#111111"), 2400)
tulis("virmodock_logo_bertumpuk", bertumpuk(), 1600)
tulis("virmodock_logo_bertumpuk_putih", bertumpuk("#ffffff", BIRU_MUDA, "#ffffff", "#c9d8ee"), 1600)
tulis("virmodock_tanda", tanda(NAVY, BIRU), 1024)
tulis("virmodock_tanda_putih", tanda("#ffffff", BIRU_MUDA), 1024)
tulis("virmodock_tanda_hitam", tanda("#111111", "#111111"), 1024)
ikon_svg = tanda("#ffffff", BIRU_MUDA, GEO_IKON, 512, NAVY, rx=104, pad=0.17)
tulis("virmodock_ikon", ikon_svg, 1024)

# ICO multi-ukuran untuk aplikasi & installer
from PIL import Image  # noqa: E402
uk = [16, 20, 24, 32, 40, 48, 64, 128, 256]
gambar = {}
for n in uk:
    render(ikon_svg, n, B / "_i.png")
    gambar[n] = Image.open(B / "_i.png").convert("RGBA")
    gambar[n].load()
(B / "_i.png").unlink()
gambar[256].save(B / "virmodock.ico", sizes=[(n, n) for n in uk], append_images=[gambar[n] for n in uk[:-1]])


# -------------------------------------------------------- panduan merek
def panel(p, x, y, w, h, svg, latar, label, isi_lebar=0.78):
    p.fillRect(QRectF(x, y, w, h), QColor(latar))
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    r = QSvgRenderer(QByteArray(svg.encode()))
    s = r.defaultSize()
    k = min(w * isi_lebar / s.width(), h * 0.70 / s.height())
    rw, rh = s.width() * k, s.height() * k
    r.render(p, QRectF(x + (w - rw) / 2, y + (h - rh) / 2, rw, rh))
    f = QFont("Bahnschrift")
    f.setPixelSize(17)
    p.setFont(f)
    p.setPen(QColor("#7b8698"))
    p.drawText(QRectF(x, y + h + 6, w, 26), Qt.AlignLeft, label)


W, H = 2400, 2860
img = QImage(W, H, QImage.Format_RGB32)
img.fill(QColor("#ffffff"))
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
p.setRenderHint(QPainter.SmoothPixmapTransform)
m = 120
f = QFont("Bahnschrift")
f.setPixelSize(30)
f.setWeight(QFont.Weight(600))
p.setFont(f)
p.setPen(QColor(NAVY))
p.drawText(QRectF(m, 70, 1800, 50), Qt.AlignLeft, "VirmoDock · Panduan logo")
f.setPixelSize(19)
f.setWeight(QFont.Weight(400))
p.setFont(f)
p.setPen(QColor("#5b6b82"))
p.drawText(QRectF(m, 118, 2160, 60), Qt.AlignLeft | Qt.TextWordWrap,
           "Huruf V adalah kantong pengikatan protein; heksagon adalah cincin ligan. Sisi dalam V mengikuti persis "
           "setengah bawah heksagon dengan celah seragam — komplementaritas bentuk, inti dari molecular docking.")
y = 220
panel(p, m, y, W - 2 * m, 700, horizontal(), "#f3f5f8", "Logo utama (horizontal) — latar terang", 0.80)
y += 760
panel(p, m, y, (W - 2 * m - 40) / 2, 520, horizontal("#ffffff", BIRU_MUDA, "#ffffff", "#c9d8ee"), NAVY,
      "Latar gelap / navy")
panel(p, m + (W - 2 * m + 40) / 2, y, (W - 2 * m - 40) / 2, 520, horizontal("#111111", "#111111", "#111111", "#111111"),
      "#ffffff", "Satu warna (cetak hitam)")
y += 590
cw = (W - 2 * m - 3 * 40) / 4
panel(p, m, y, cw * 2 + 40, 640, bertumpuk(), "#f3f5f8", "Bertumpuk (sampul, poster, slide judul)", 0.70)
panel(p, m + (cw + 40) * 2, y, cw, 640, tanda(NAVY, BIRU), "#ffffff", "Tanda saja", 0.6)
panel(p, m + (cw + 40) * 3, y, cw, 640, ikon_svg, "#ffffff", "Ikon aplikasi", 0.6)
y += 710
# warna
f.setPixelSize(22)
f.setWeight(QFont.Weight(600))
p.setFont(f)
p.setPen(QColor(NAVY))
p.drawText(QRectF(m, y, 800, 34), Qt.AlignLeft, "Warna")
for i, (nama, hexa, rgb) in enumerate((("Navy VirmoDock", NAVY, "23 · 59 · 108"), ("Biru ligan", BIRU, "43 · 111 · 214"),
                                       ("Biru terang (latar gelap)", BIRU_MUDA, "91 · 154 · 240"),
                                       ("Abu tagline", "#5b6b82", "91 · 107 · 130"))):
    x = m + i * 540
    p.fillRect(QRectF(x, y + 50, 500, 150), QColor(hexa))
    f.setPixelSize(19)
    f.setWeight(QFont.Weight(600))
    p.setFont(f)
    p.setPen(QColor(NAVY))
    p.drawText(QRectF(x, y + 212, 500, 28), Qt.AlignLeft, nama)
    f.setWeight(QFont.Weight(400))
    p.setFont(f)
    p.setPen(QColor("#5b6b82"))
    p.drawText(QRectF(x, y + 240, 500, 28), Qt.AlignLeft, f"{hexa.upper()}   RGB {rgb}")
y += 310
# ukuran kecil
f.setPixelSize(22)
f.setWeight(QFont.Weight(600))
p.setFont(f)
p.setPen(QColor(NAVY))
p.drawText(QRectF(m, y, 1200, 34), Qt.AlignLeft, "Keterbacaan ukuran kecil & aturan")
x = m
for n in (16, 24, 32, 48, 64, 128):
    im = render(ikon_svg, n, B / "_i.png")
    p.drawImage(int(x), int(y + 60 + (128 - n) / 2), im)
    p.setPen(QColor("#7b8698"))
    f.setPixelSize(16)
    f.setWeight(QFont.Weight(400))
    p.setFont(f)
    p.drawText(QRectF(x - 20, y + 200, n + 40, 24), Qt.AlignCenter, f"{n} px")
    x += n + 60
(B / "_i.png").unlink(missing_ok=True)
f.setPixelSize(18)
p.setFont(f)
p.setPen(QColor("#465263"))
aturan = ["Ruang kosong minimal di sekeliling logo = tinggi heksagon.",
          "Ukuran minimum: logo horizontal 30 mm / 160 px lebar; tanda 6 mm / 24 px.",
          "Jangan memutar, meregangkan, memberi bayangan, gradien, atau garis tepi.",
          "Jangan mengganti huruf atau warna; di latar foto pakai versi putih di atas panel navy.",
          "Huruf wordmark: Bahnschrift SemiBold (sudah diubah jadi kurva — tidak butuh font terpasang)."]
for i, t in enumerate(aturan):
    p.drawText(QRectF(m + 760, y + 60 + i * 34, 1500, 30), Qt.AlignLeft, "—  " + t)
p.end()
img.save(str(B / "virmodock_panduan_logo.png"))
print("selesai:", sorted(f.name for f in B.iterdir()))
