"""Story WhatsApp/Instagram VirmoLab (1080 x 1920, latar putih) -> branding/promosi/story_0N.png

Teks diubah jadi kurva (Figtree), tangkapan layar diberi sudut membulat + bayangan lembut lewat Pillow.
Zona aman story: konten utama di y 300-1580 (atas/bawah tertutup UI Instagram/WhatsApp).

  .venv\\Scripts\\python.exe build_tools\\logo\\promosi_story.py
"""
import base64
import io
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buat_logo import qpath_ke_svg, render, teks_ke_path  # noqa: E402

AKAR = Path(__file__).resolve().parents[2]
B = AKAR / "branding"
OUT = B / "promosi"
OUT.mkdir(exist_ok=True)
GBR = AKAR / "docs" / "gambar"

W, H = 1080, 1920
MX = 96
NAVY, AZURE, ABU, ABU_MUDA = "#12305a", "#2f74e0", "#5b6678", "#8a94a6"
FONT = "Figtree Light"
TOTAL = 6
UJI = AKAR / "dev" / "uji"
PENGEMBANG = "apt. Rizki Rahmadi Pratama, M. Farm"


# ---------------------------------------------------------------- utilitas
def campur(a, b, t):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def teks(s, x, base, px, berat=400, warna=NAVY, spasi=0.0, rata="kiri"):
    """Teks -> path SVG. rata: kiri | tengah | kanan. Kembalikan (svg, lebar)."""
    path, kotak, _ = teks_ke_path(s, FONT, berat, px, spasi)
    lebar = kotak.width()
    if rata == "tengah":
        x = x - lebar / 2
    elif rata == "kanan":
        x = x - lebar
    return f'<path d="{qpath_ke_svg(path, x - kotak.left(), base)}" fill="{warna}"/>', lebar


def paragraf(baris, x, base, px, jarak, **kw):
    out = []
    for i, b in enumerate(baris):
        out.append(teks(b, x, base + i * jarak, px, **kw)[0])
    return "".join(out), base + (len(baris) - 1) * jarak


def sisip_svg(nama, x, y, lebar, ubah_warna=None):
    """Sisipkan SVG branding (tanpa pembungkus) di (x, y) dengan lebar tertentu. Kembalikan (svg, tinggi)."""
    s = (B / f"{nama}.svg").read_text(encoding="utf-8")
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', s).group(1).split()]
    dalam = re.sub(r"^<svg[^>]*>|<title>.*?</title>|</svg>\s*$", "", s.strip())
    if ubah_warna:
        dalam = re.sub(r'fill="(#[0-9a-fA-F]{6})"', lambda m: f'fill="{ubah_warna(m.group(1))}"', dalam)
    k = lebar / vb[2]
    return f'<g transform="translate({x:.1f},{y:.1f}) scale({k:.5f})">{dalam}</g>', vb[3] * k


def kartu_gambar(berkas, kotak, lebar, radius=28, bayang=34):
    """Potong tangkapan layar, sudut membulat + bayangan lembut -> <image> data URI. Kembalikan (svg, tinggi)."""
    im = Image.open(berkas).convert("RGB").crop(kotak)
    skala = 2                                    # simpan 2x agar tajam saat dirender
    lw = lebar * skala
    lh = round(im.height * lw / im.width)
    im = im.resize((lw, lh), Image.LANCZOS)
    r, pad = radius * skala, bayang * skala
    kanvas = Image.new("RGBA", (lw + 2 * pad, lh + 2 * pad), (0, 0, 0, 0))
    bay = Image.new("L", kanvas.size, 0)
    ImageDraw.Draw(bay).rounded_rectangle((pad, pad + 14 * skala, pad + lw, pad + lh + 14 * skala), r, fill=70)
    bay = bay.filter(ImageFilter.GaussianBlur(18 * skala))
    warna_bay = Image.new("RGBA", kanvas.size, (18, 48, 90, 255))
    kanvas = Image.composite(warna_bay, kanvas, bay)
    topeng = Image.new("L", (lw, lh), 0)
    ImageDraw.Draw(topeng).rounded_rectangle((0, 0, lw - 1, lh - 1), r, fill=255)
    kanvas.paste(im, (pad, pad), topeng)
    garis = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    ImageDraw.Draw(garis).rounded_rectangle((0, 0, lw - 1, lh - 1), r, outline=(18, 48, 90, 28), width=2)
    kanvas.alpha_composite(garis, (pad, pad))
    buf = io.BytesIO()
    kanvas.save(buf, "PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    tw, th = kanvas.width / skala, kanvas.height / skala
    return (lambda x, y: f'<image x="{x - bayang:.1f}" y="{y - bayang:.1f}" width="{tw:.1f}" height="{th:.1f}" '
                         f'xlink:href="{uri}"/>'), lh / skala


def pil(s, cx, y, warna_teks=AZURE, latar="#eef4fd", px=24):
    t, lb = teks(s, 0, 0, px, 600, warna_teks, 0.16)
    w, h = lb + 2 * 30, px * 2.3
    x = cx - w / 2
    base = y + h / 2 + px * 0.36
    tt, _ = teks(s, cx, base, px, 600, warna_teks, 0.16, "tengah")
    return f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" fill="{latar}"/>' + tt, h


def label(s, x, base, rata="kiri"):
    """Label kecil berjarak huruf dengan garis aksen."""
    t, lb = teks(s, x + (44 if rata == "kiri" else 0), base, 23, 600, AZURE, 0.22, rata)
    if rata == "kiri":
        g = f'<rect x="{x}" y="{base - 9}" width="30" height="2.5" fill="{AZURE}"/>'
    else:
        g = (f'<rect x="{x - lb / 2 - 46}" y="{base - 9}" width="30" height="2.5" fill="{AZURE}"/>'
             f'<rect x="{x + lb / 2 + 16}" y="{base - 9}" width="30" height="2.5" fill="{AZURE}"/>')
    return g + t


def kepala(no):
    m, _ = sisip_svg("virmolab_tanda", MX - 6, 262, 54)
    t, _ = teks("VirmoLab", MX + 56, 300, 30, 600, NAVY)
    n, _ = teks(f"{no:02d} / {TOTAL:02d}", W - MX, 298, 22, 500, ABU_MUDA, 0.12, "kanan")
    return m + t + n


def tanda_air(x, y, lebar, t=0.94):
    s, _ = sisip_svg("virmolab_tanda", x, y, lebar, lambda c: campur(c, "#ffffff", t))
    return s


def svg(isi):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {W} {H}" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#ffffff"/>'
            + "".join(isi) + "</svg>")


# ---------------------------------------------------------------- slide 1: perkenalan
def slide1():
    el = [tanda_air(470, 1230, 900, 0.955), tanda_air(-330, -240, 640, 0.965), kepala(1)]
    el.append(label("MEMPERKENALKAN", W / 2, 560, "tengah"))
    logo, lh = sisip_svg("virmolab_logo_bertumpuk", (W - 600) / 2, 610, 600)
    el.append(logo)
    y = 610 + lh + 40
    s, y = paragraf(["Laboratorium molekuler virtual,", "kini di laptop Anda."], W / 2, y + 60, 54, 70,
                    berat=600, warna=NAVY, rata="tengah")
    el.append(s)
    s, y = paragraf(["Aplikasi desktop molecular docking berbahasa", "Indonesia, gratis, dan open-source."],
                    W / 2, y + 70, 30, 46, berat=400, warna=ABU, rata="tengah")
    el.append(s)
    p, ph = pil("SEGERA RILIS  ·  VERSI 1.2", W / 2, y + 70)
    el.append(p)
    el.append(teks(f"oleh {PENGEMBANG}", W / 2, y + 70 + ph + 58, 25, 500, NAVY, 0.01, "tengah")[0])
    return svg(el)


# ---------------------------------------------------------------- slide 2: satu jendela
def slide2():
    el = [tanda_air(560, 1380, 760, 0.96), kepala(2)]
    el.append(label("DARI PROTEIN KE PUBLIKASI", MX, 430))
    s, y = paragraf(["Semua tahap docking,", "dalam satu jendela."], MX, 520, 66, 80, berat=600)
    el.append(s)
    s, y = paragraf(["Unduh protein, siapkan ligan, jalankan docking,", "lalu analisis interaksinya dalam 3D dan 2D."],
                    MX, y + 66, 30, 46, warna=ABU)
    el.append(s)
    kartu, kh = kartu_gambar(GBR / "09_interaksi.png", (342, 232, 1582, 1222), W - 2 * MX)
    y_k = y + 64
    el.append(kartu(MX, y_k))
    el.append(teks("Contoh: inhibitor protease HIV-1 (PDB 1HSG), hasil docking AutoDock-GPU",
                   MX, y_k + kh + 52, 22, 400, ABU_MUDA)[0])
    return svg(el)


# ---------------------------------------------------------------- slide 3-4: fitur
FITUR_DOCKING = [
    ("Target & ligan", "RCSB PDB, AlphaFold DB, PubChem, ChEMBL, SMILES, gambar struktur "
                       "dengan Ketcher, serta pustaka obat dan ZINC"),
    ("Docking", "AutoDock-GPU (NVIDIA, AMD, Intel), Vina, AutoDock 4, GNINA · kovalen, residu "
                "fleksibel, blind docking, banyak ligan sekaligus"),
    ("Situs pengikatan", "Deteksi kantong dengan P2Rank dan metode geometri, saluran akses ligan, "
                         "antarmuka protein–protein"),
    ("Analisis interaksi", "Ikatan hidrogen, hidrofobik, π–π, π–kation, jembatan garam, halogen, dan logam · "
                           "tampilan 3D, diagram 2D, peta residu × ligan"),
    ("Validasi", "Redocking (RMSD), PoseBusters, cross-docking, uji pengayaan (ROC, EF, BEDROC), "
                 "skor konsensus"),
]
FITUR_LANJUT = [
    ("ADMET & toksisitas", "ADMET-AI: absorpsi, penembusan sawar darah otak, CYP450, hERG, Ames, DILI, "
                           "karsinogenisitas · peta organ, BOILED-Egg"),
    ("Desain obat", "MPO, kemiripan struktur & farmakofor, MMP, FBDD, PROTAC, situs metabolisme "
                    "CYP, selektivitas multitarget"),
    ("Dinamika molekul", "Simulasi MD & MM/GBSA (OpenMM): RMSD, RMSF, Rg, SASA, PCA & FEL, klaster, "
                         "multireplika · kinetika dan waktu tinggal"),
    ("Bahan alam Indonesia", "Senyawa tanaman obat dari LOTUS & COCONUT, dapat dicari dengan nama lokal"),
    ("Siap publikasi", "Gambar resolusi tinggi & komposer panel, video 4K, uji statistik, laporan "
                       "PDF/Word/HTML, draf bab metode"),
]


def bungkus(kalimat, lebar, px, berat=400):
    """Pecah kalimat jadi baris selebar <= lebar piksel."""
    baris, cur, kata2 = [], "", []
    for k in kalimat.split(" "):          # pemisah "·" ikut kata sebelumnya: baris tak pernah diawali "·"
        if k == "·" and kata2:
            kata2[-1] += " ·"
        else:
            kata2.append(k)
    for kata in kata2:
        coba = (cur + " " + kata).strip()
        if cur and teks(coba, 0, 0, px, berat)[1] > lebar:
            baris.append(cur)
            cur = kata
        else:
            cur = coba
    return baris + [cur]


def hex_nomor(cx, cy, n, r=30):
    import math
    pts = [(cx + r * math.cos(math.radians(60 * k)), cy + r * math.sin(math.radians(60 * k))) for k in range(6)]
    d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"
    t, _ = teks(str(n), cx, cy + 9, 25, 600, AZURE, 0, "tengah")
    return f'<path d="{d}" fill="#eef4fd" stroke="{campur(AZURE, "#ffffff", 0.55)}" stroke-width="1.6"/>' + t


def slide_fitur(no, lbl, judul, daftar, air):
    el = [air, kepala(no)]
    el.append(label(lbl, MX, 430))
    s, y = paragraf(judul, MX, 520, 62, 76, berat=600)
    el.append(s)
    y += 92
    x_t = MX + 96
    lebar = W - MX - x_t
    for i, (jdl, ket) in enumerate(daftar):
        el.append(hex_nomor(MX + 32, y - 12, i + 1))
        el.append(teks(jdl, x_t, y, 34, 600, NAVY)[0])
        b = bungkus(ket, lebar, 26)
        s, yb = paragraf(b, x_t, y + 46, 26, 37, warna=ABU)
        el.append(s)
        y = yb + 34
        if i < len(daftar) - 1:
            el.append(f'<rect x="{x_t}" y="{y - 4}" width="{lebar}" height="1.2" fill="#e6eaf1"/>')
            y += 60
    return svg(el)


def slide3():
    return slide_fitur(3, "FITUR · DOCKING & ANALISIS", ["Dari target", "sampai pose terbaik."], FITUR_DOCKING,
                       tanda_air(600, -180, 700, 0.965))


def slide4():
    return slide_fitur(4, "FITUR · LEBIH DARI DOCKING", ["Dari pose", "menuju kandidat obat."], FITUR_LANJUT,
                       tanda_air(-320, 1300, 760, 0.965))


# ---------------------------------------------------------------- slide 5: galeri visual
GALERI = [   # (berkas tangkapan di dev/uji, potongan area grafik, judul, keterangan)
    ("statistik/gui/gui_matriks.png", (470, 190, 1650, 1470), "Matriks korelasi", "Statistik"),
    ("kemiripan/dlg_matriks.png", (490, 175, 1385, 1105), "Koefisien Tanimoto", "Kemiripan struktur"),
    ("sifat/uji_flex_boiled_egg.png", (0, 0, 3307, 2610), "BOILED-Egg", "Absorpsi & BBB"),
    ("peta_tubuh/peta_terang.png", (0, 100, 1600, 1000), "Peta ADMET per organ", "Toksisitas"),
    ("md_gui/dialog_rmsd.png", (820, 300, 1920, 1040), "RMSD simulasi MD", "Stabilitas"),
    ("grafik_lanjut/05_roc.png", (800, 70, 1745, 960), "Kurva ROC", "Validasi"),
]


def kartu_isi(berkas, kotak, lebar, tinggi, radius=22, bayang=26, pad=14):
    """Grafik dimuat utuh (contain) di kartu putih berukuran tetap, sudut membulat + bayangan lembut."""
    im = Image.open(berkas).convert("RGB").crop(kotak)
    skala = 2
    lw, lh, pd = lebar * skala, tinggi * skala, pad * skala
    im.thumbnail((lw - 2 * pd, lh - 2 * pd), Image.LANCZOS)
    isi = Image.new("RGB", (lw, lh), "white")
    isi.paste(im, ((lw - im.width) // 2, (lh - im.height) // 2))
    r, b = radius * skala, bayang * skala
    kanvas = Image.new("RGBA", (lw + 2 * b, lh + 2 * b), (0, 0, 0, 0))
    bay = Image.new("L", kanvas.size, 0)
    ImageDraw.Draw(bay).rounded_rectangle((b, b + 10 * skala, b + lw, b + lh + 10 * skala), r, fill=55)
    bay = bay.filter(ImageFilter.GaussianBlur(14 * skala))
    kanvas = Image.composite(Image.new("RGBA", kanvas.size, (18, 48, 90, 255)), kanvas, bay)
    topeng = Image.new("L", (lw, lh), 0)
    ImageDraw.Draw(topeng).rounded_rectangle((0, 0, lw - 1, lh - 1), r, fill=255)
    kanvas.paste(isi, (b, b), topeng)
    garis = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    ImageDraw.Draw(garis).rounded_rectangle((0, 0, lw - 1, lh - 1), r, outline=(18, 48, 90, 30), width=2)
    kanvas.alpha_composite(garis, (b, b))
    buf = io.BytesIO()
    kanvas.save(buf, "PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return (f'<image x="{{x}}" y="{{y}}" width="{kanvas.width / skala:.1f}" height="{kanvas.height / skala:.1f}" '
            f'xlink:href="{uri}"/>'), bayang


def slide5():
    el = [tanda_air(560, -200, 700, 0.965), kepala(5)]
    el.append(label("VISUALISASI", MX, 430))
    s, y = paragraf(["Grafik siap publikasi."], MX, 520, 62, 76, berat=600)
    el.append(s)
    cw, ch, gx = (W - 2 * MX - 28) / 2, 272, 28
    y0 = y + 62
    for i, (f, kotak, judul, ket) in enumerate(GALERI):
        x = MX + (i % 2) * (cw + gx)
        yy = y0 + (i // 2) * (ch + 64)
        tpl, b = kartu_isi(UJI / f, kotak, round(cw), ch, pad=8)
        el.append(tpl.format(x=f"{x - b:.1f}", y=f"{yy - b:.1f}"))
        jt, lj = teks(judul, x + 4, yy + ch + 38, 23, 600, NAVY)
        el.append(jt + teks("·  " + ket, x + 4 + lj + 12, yy + ch + 38, 19, 400, ABU_MUDA)[0])
    return svg(el)


# ---------------------------------------------------------------- slide 6: penutup
def slide6():
    el = [tanda_air(-300, 1250, 820, 0.96), kepala(6)]
    el.append(label("SEGERA HADIR", W / 2, 430, "tengah"))
    s, y = paragraf(["Gratis. Open-source.", "Berbahasa Indonesia."], W / 2, 520, 66, 80, berat=600, rata="tengah")
    el.append(s)
    s, y = paragraf(["Dibuat untuk mahasiswa dan peneliti farmasi", "serta kimia medisinal di Indonesia."],
                    W / 2, y + 66, 30, 46, warna=ABU, rata="tengah")
    el.append(s)
    lebar = 560
    kartu, kh = kartu_gambar(GBR / "10_diagram2d.png", (330, 330, 1640, 1180), lebar)
    y_k = y + 58
    el.append(kartu((W - lebar) / 2, y_k))
    y = y_k + kh + 52
    chips = ["Windows 10/11", "GPU NVIDIA · AMD · Intel", "GPL-3.0"]
    lebar_c = [teks(c, 0, 0, 22, 600, NAVY, 0.06)[1] + 48 for c in chips]
    x = W / 2 - (sum(lebar_c) + 16 * (len(chips) - 1)) / 2
    for c, lc in zip(chips, lebar_c):
        el.append(f'<rect x="{x:.1f}" y="{y}" width="{lc:.1f}" height="52" rx="26" fill="#ffffff" '
                  f'stroke="#d9e1ec" stroke-width="1.5"/>')
        el.append(teks(c, x + lc / 2, y + 34, 22, 600, NAVY, 0.06, "tengah")[0])
        x += lc + 16
    y += 52 + 76
    el.append(label("DIKEMBANGKAN OLEH", W / 2, y, "tengah"))
    el.append(teks(PENGEMBANG, W / 2, y + 56, 36, 600, NAVY, 0, "tengah")[0])
    logo, _ = sisip_svg("virmolab_logo_horizontal_tanpa_tagline", (W - 300) / 2, y + 92, 300)
    el.append(logo)
    return svg(el)


if __name__ == "__main__":
    hasil = []
    for i, fn in enumerate((slide1, slide2, slide3, slide4, slide5, slide6), 1):
        s = fn()
        (OUT / f"story_{i:02d}.svg").write_text(s, encoding="utf-8")
        render(s, W, OUT / f"story_{i:02d}.png", "#ffffff")
        hasil.append(OUT / f"story_{i:02d}.png")
    # lembar pratinjau (4 berdampingan) untuk diperiksa
    ims = [Image.open(p).convert("RGB") for p in hasil]
    lb = Image.new("RGB", (W * len(ims) + 60 * (len(ims) + 1), H + 120), "#e9edf3")
    for i, im in enumerate(ims):
        lb.paste(im, (60 + i * (W + 60), 60))
    lb.resize((lb.width // 3, lb.height // 3), Image.LANCZOS).save(OUT / "_pratinjau.png")
    print("ok", [p.name for p in hasil])
