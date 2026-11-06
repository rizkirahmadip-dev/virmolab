"""Diagram Venn SVG untuk 2 atau 3 himpunan (tanpa matplotlib), senada dengan core.grafik dan core.graf.

Dipakai farmakologi jaringan untuk menampilkan irisan target senyawa dengan gen penyakit — gambar yang
hampir selalu diminta pada naskah network pharmacology.

Lingkaran berukuran tetap (bukan proporsional terhadap jumlah anggota). Venn proporsional untuk tiga
himpunan tidak selalu punya solusi geometris, dan memaksakannya membuat luas wilayah menyesatkan;
jumlah anggota ditulis sebagai angka di tiap wilayah.
"""
from typing import Dict, Iterable, List, Sequence
from xml.sax.saxutils import escape

FONT = "Segoe UI, Arial, Helvetica, sans-serif"

TEMA_VENN = {
    "terang": {"latar": "#ffffff", "teks": "#1b2430", "teks2": "#465263", "garis": "#ffffff"},
    "gelap": {"latar": "#14171c", "teks": "#e2e6ed", "teks2": "#aab3c0", "garis": "#14171c"},
}

# Palet aman buta warna (Okabe-Ito), sama dengan core.grafik_uji
WARNA = ["#0072b2", "#e69f00", "#009e73"]


def _tr(s: str) -> str:
    """Terjemahkan label diagram mengikuti bahasa antarmuka."""
    try:
        from .. import i18n
        return i18n.t(s)
    except Exception:
        return s


def _t(x, y, teks, ukuran=13, warna="#1b2430", anchor="middle", tebal=False, kelas=""):
    gaya = f"font-family:{FONT};font-size:{ukuran}px;fill:{warna}"
    if tebal:
        gaya += ";font-weight:600"
    k = f' class="{kelas}"' if kelas else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" style="{gaya}"{k}>{escape(str(teks))}</text>'


def hitung2(a: Iterable[str], b: Iterable[str]) -> Dict[str, List[str]]:
    """Wilayah Venn dua himpunan: 'A' (hanya A), 'B' (hanya B), 'AB' (irisan)."""
    sa, sb = {str(x).strip().upper() for x in a if str(x).strip()}, {str(x).strip().upper() for x in b if str(x).strip()}
    return {"A": sorted(sa - sb), "B": sorted(sb - sa), "AB": sorted(sa & sb)}


def hitung3(a: Iterable[str], b: Iterable[str], c: Iterable[str]) -> Dict[str, List[str]]:
    """Wilayah Venn tiga himpunan: A, B, C, AB, AC, BC, ABC (masing-masing eksklusif)."""
    sa = {str(x).strip().upper() for x in a if str(x).strip()}
    sb = {str(x).strip().upper() for x in b if str(x).strip()}
    sc = {str(x).strip().upper() for x in c if str(x).strip()}
    return {
        "A": sorted(sa - sb - sc), "B": sorted(sb - sa - sc), "C": sorted(sc - sa - sb),
        "AB": sorted((sa & sb) - sc), "AC": sorted((sa & sc) - sb), "BC": sorted((sb & sc) - sa),
        "ABC": sorted(sa & sb & sc),
    }


def svg(himpunan: Dict[str, Sequence[str]], lebar: int = 560, tinggi: int = 420,
        mode: str = "terang", judul: str = "") -> str:
    """Diagram Venn untuk 2 atau 3 himpunan.

    himpunan: {label: [anggota, ...]} — urutan kunci menentukan posisi lingkaran.
    """
    nama = list(himpunan.keys())
    if len(nama) not in (2, 3):
        raise ValueError("Diagram Venn modul ini hanya untuk 2 atau 3 himpunan.")
    t = TEMA_VENN.get(mode, TEMA_VENN["terang"])
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{lebar}" height="{tinggi}" '
         f'viewBox="0 0 {lebar} {tinggi}">',
         f'<rect width="{lebar}" height="{tinggi}" fill="{t["latar"]}"/>']
    atas = 34 if judul else 10
    if judul:
        o.append(_t(lebar / 2, 24, judul, 15, t["teks"], tebal=True))

    cx, cy = lebar / 2, atas + (tinggi - atas) / 2 - 6
    r = min(lebar, tinggi - atas) * 0.27

    if len(nama) == 2:
        w = hitung2(himpunan[nama[0]], himpunan[nama[1]])
        pusat = [(cx - r * 0.56, cy), (cx + r * 0.56, cy)]
        wilayah = [(pusat[0][0] - r * 0.52, cy, len(w["A"])),
                   (cx, cy, len(w["AB"])),
                   (pusat[1][0] + r * 0.52, cy, len(w["B"]))]
    else:
        w = hitung3(himpunan[nama[0]], himpunan[nama[1]], himpunan[nama[2]])
        pusat = [(cx - r * 0.54, cy - r * 0.32), (cx + r * 0.54, cy - r * 0.32), (cx, cy + r * 0.56)]
        wilayah = [(cx - r * 0.95, cy - r * 0.52, len(w["A"])),
                   (cx + r * 0.95, cy - r * 0.52, len(w["B"])),
                   (cx, cy + r * 1.10, len(w["C"])),
                   (cx, cy - r * 0.62, len(w["AB"])),
                   (cx - r * 0.60, cy + r * 0.32, len(w["AC"])),
                   (cx + r * 0.60, cy + r * 0.32, len(w["BC"])),
                   (cx, cy + r * 0.06, len(w["ABC"]))]

    for i, (px, py) in enumerate(pusat):
        o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r:.1f}" fill="{WARNA[i]}" fill-opacity="0.34" '
                 f'stroke="{WARNA[i]}" stroke-width="1.6"/>')

    for px, py, n in wilayah:
        if n:
            o.append(_t(px, py + 5, n, 15, t["teks"], tebal=True))

    # Label himpunan di luar lingkaran, ikut jumlah totalnya
    if len(nama) == 2:
        posisi = [(pusat[0][0] - r * 0.35, cy - r - 12, "middle"), (pusat[1][0] + r * 0.35, cy - r - 12, "middle")]
    else:
        posisi = [(pusat[0][0] - r * 0.40, pusat[0][1] - r - 10, "middle"),
                  (pusat[1][0] + r * 0.40, pusat[1][1] - r - 10, "middle"),
                  (pusat[2][0], pusat[2][1] + r + 22, "middle")]
    for i, (px, py, anc) in enumerate(posisi):
        total = len({str(x).strip().upper() for x in himpunan[nama[i]] if str(x).strip()})
        o.append(_t(px, py, f"{nama[i]} ({total})", 13, WARNA[i], anchor=anc, tebal=True))

    o.append("</svg>")
    return "\n".join(o)


def ringkas(w: Dict[str, List[str]]) -> str:
    """Satu kalimat Bahasa Indonesia yang merangkum isi tiap wilayah."""
    bagian = [f"{k}: {len(v)}" for k, v in w.items() if v]
    return "; ".join(bagian) if bagian else _tr("Semua wilayah kosong.")
