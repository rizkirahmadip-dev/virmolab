"""Komposer figur: gabungkan beberapa panel (grafik SVG, diagram 2D, gambar 3D PNG) menjadi satu gambar
berlabel A/B/C siap jurnal.

Panel SVG disisipkan sebagai <g transform> (bukan <svg> bersarang - QtSvg tidak mendukungnya); id internal
diberi awalan per panel agar clipPath dkk. tidak bentrok. Panel raster disisipkan sebagai <image> data URI.
"""
import re
from xml.sax.saxutils import escape

FONT = "Segoe UI, Arial, Helvetica, sans-serif"
LABEL = {"A": "A, B, C", "a": "a, b, c", "(A)": "(A), (B), (C)", "(a)": "(a), (b), (c)", "A.": "A., B., C.",
         "": "Tanpa label"}
OPSI = {"kolom": 2, "jarak": 28, "label": "A", "ukuran_label": 22, "lebar_mm": 174, "judul_panel": False,
        "seragam": True}
LEBAR_PX = 2000      # lebar kanvas kerja; ukuran fisik ditentukan saat ekspor (lebar_mm)


def opsi_lengkap(o=None):
    d = dict(OPSI)
    d.update({k: v for k, v in (o or {}).items() if k in OPSI})
    return d


def teks_label(gaya, i):
    if not gaya:
        return ""
    huruf = chr(ord("a" if gaya in ("a", "(a)") else "A") + i % 26)
    return {"(A)": f"({huruf})", "(a)": f"({huruf})", "A.": f"{huruf}."}.get(gaya, huruf)


def _isi_svg(teks, awalan):
    """Ambil isi elemen <svg> akar + ukurannya; id diberi awalan."""
    m = re.search(r"<svg\b[^>]*>", teks)
    if not m:
        return "", (1, 1)
    kepala = m.group(0)
    vb = re.search(r'viewBox="\s*([-\d.]+)[\s,]+([-\d.]+)[\s,]+([-\d.]+)[\s,]+([-\d.]+)', kepala)
    if vb:
        x0, y0, w, h = (float(v) for v in vb.groups())
    else:
        w = float(re.search(r'width="([\d.]+)', kepala).group(1))
        h = float(re.search(r'height="([\d.]+)', kepala).group(1))
        x0 = y0 = 0.0
    isi = teks[m.end():teks.rfind("</svg>")]
    isi = re.sub(r'\bid="([^"]+)"', lambda g: f'id="{awalan}{g.group(1)}"', isi)
    isi = re.sub(r'url\(#([^)]+)\)', lambda g: f"url(#{awalan}{g.group(1)})", isi)
    isi = re.sub(r'href="#([^"]+)"', lambda g: f'href="#{awalan}{g.group(1)}"', isi)
    if x0 or y0:
        isi = f'<g transform="translate({-x0:.2f} {-y0:.2f})">{isi}</g>'
    return isi, (w, h)


def ukuran_panel(p):
    if p["jenis"] == "svg":
        return _isi_svg(p["isi"], "x")[1]
    return float(p["w"]), float(p["h"])


def susun(panel, opsi=None, latar="#ffffff"):
    """panel: list dict {nama, jenis: svg|png, isi (teks SVG | PNG base64), w, h, penuh: bool}.
    Kembalikan (svg, (W, H))."""
    o = opsi_lengkap(opsi)
    kol = max(1, int(o["kolom"]))
    jarak = float(o["jarak"])
    tl = float(o["ukuran_label"]) * 1.25 if o["label"] else 0.0
    tj = 22.0 if o["judul_panel"] and not o["label"] else 0.0   # judul sebaris dengan label bila ada
    W = LEBAR_PX
    lebar_sel = (W - jarak * (kol + 1)) / kol
    # tata letak baris: panel 'penuh' memakai satu baris sendiri
    baris, sekarang = [], []
    for i, p in enumerate(panel):
        if p.get("penuh"):
            if sekarang:
                baris.append(sekarang)
                sekarang = []
            baris.append([i])
            continue
        sekarang.append(i)
        if len(sekarang) == kol:
            baris.append(sekarang)
            sekarang = []
    if sekarang:
        baris.append(sekarang)
    # skala seragam: semua grafik SVG memakai faktor skala yang sama -> ukuran huruf sama di semua panel
    skala = [((W - 2 * jarak) if p.get("penuh") else lebar_sel) / max(1.0, ukuran_panel(p)[0])
             for p in panel if p["jenis"] == "svg"]
    s_seragam = min(skala) if skala and o["seragam"] else None
    keluar = []
    y = jarak
    for b in baris:
        penuh = len(b) == 1 and panel[b[0]].get("penuh")
        tinggi_b = 0.0
        letak = []
        for k, i in enumerate(b):
            p = panel[i]
            lw = (W - 2 * jarak) if penuh else lebar_sel
            x = jarak if penuh else jarak + k * (lebar_sel + jarak)
            w, h = ukuran_panel(p)
            s = lw / max(1.0, w)
            if s_seragam and p["jenis"] == "svg":
                s = min(s, s_seragam)
            letak.append((i, x, lw, s, w, h))
            tinggi_b = max(tinggi_b, h * s)
        for i, x, lw, s, w, h in letak:
            p = panel[i]
            yy = y + tl + tj
            dy = (tinggi_b - h * s) / 2           # panel lebih pendek diletakkan di tengah baris
            if p["jenis"] == "svg":
                isi, _ = _isi_svg(p["isi"], f"p{i}_")
                dx = (lw - w * s) / 2
                keluar.append(f'<g transform="translate({x + dx:.2f} {yy + dy:.2f}) scale({s:.5f})">{isi}</g>')
            else:
                keluar.append(f'<image x="{x:.2f}" y="{yy + dy:.2f}" width="{w * s:.2f}" height="{h * s:.2f}" '
                              f'preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,{p["isi"]}"/>')
            if o["label"]:
                keluar.append(f'<text x="{x:.2f}" y="{y + float(o["ukuran_label"]):.2f}" font-family="{FONT}" '
                              f'font-size="{o["ukuran_label"]}" font-weight="700" fill="#111111">'
                              f'{escape(teks_label(o["label"], i))}</text>')
            if o["judul_panel"] and p.get("nama"):
                xj = x + (float(o["ukuran_label"]) * 1.7 if o["label"] else 0)
                yj = y + float(o["ukuran_label"]) if o["label"] else y + 16
                keluar.append(f'<text x="{xj:.2f}" y="{yj:.2f}" font-family="{FONT}" font-size="16" '
                              f'fill="#333333">{escape(p["nama"])}</text>')
        y += tl + tj + tinggi_b + jarak
    H = max(y, 100.0)
    kepala = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" '
              f'width="{W}" height="{H:.0f}" viewBox="0 0 {W} {H:.0f}">')
    bg = f'<rect x="0" y="0" width="{W}" height="{H:.0f}" fill="{latar}"/>' if latar else ""
    return "\n".join([kepala, bg] + keluar + ["</svg>"]), (W, int(round(H)))
