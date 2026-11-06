"""Figur siap publikasi untuk farmakologi jaringan: hub melingkar, bubble plot jalur, batang jalur.

Semua keluaran berupa teks SVG berukuran piksel tetap, sama seperti core.grafik dan core.graf, sehingga
bisa diubah ke SVG ber-mm, PDF vektor, atau PNG/TIFF ber-DPI oleh jalur ekspor yang sudah ada.

Pilihan warna mengikuti disiplin yang sama dengan seluruh grafik VirmoLab:

- Besaran berurutan (peringkat hub, nilai q) memakai **satu rona, terang ke gelap**, bukan pelangi.
  Rampnya diambil dari skala biru yang sudah divalidasi (pita terang, lantai kroma, pemisahan buta
  warna, kontras terhadap latar). Karena peringkat hub adalah tanda berurutan yang terpisah-pisah,
  langkah paling terang yang dipakai adalah 250 — lebih terang dari itu tenggelam ke latar.
- Rona kategori (jenis simpul) tetap memakai Okabe-Ito, lihat ui.widget_graf.WARNA_JENIS.

Keterbacaan tanpa warna juga dijaga: tiap gelembung dan tiap kotak hub membawa angkanya sendiri, jadi
pembaca yang mencetak hitam-putih tetap mendapat seluruh isinya.
"""
import math
from typing import Any, Dict, List, Sequence
from xml.sax.saxutils import escape

from .grafik import FONT, Kanvas, fmt, warna

# Ramp biru tervalidasi, terang -> gelap. Dipakai untuk besaran berurutan.
RAMP_BIRU = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf",
             "#1c5cab", "#184f95", "#104281", "#0d366b"]
# Mulai langkah ke berapa tulisan di atas ramp harus putih agar kontrasnya cukup.
_AMBANG_TEKS_PUTIH = 4


def _tr(s: str) -> str:
    """Terjemahkan label figur mengikuti bahasa antarmuka (no-op dalam Bahasa Indonesia)."""
    try:
        from .. import i18n
        return i18n.t(s)
    except Exception:
        return s


def _langkah(i: int, n: int) -> int:
    """Indeks ramp untuk butir ke-i dari n, paling gelap untuk peringkat teratas."""
    if n <= 1:
        return len(RAMP_BIRU) - 1
    pecahan = 1.0 - (i / (n - 1))
    return max(0, min(len(RAMP_BIRU) - 1, int(round(pecahan * (len(RAMP_BIRU) - 1)))))


def _teks_di_atas(idx: int) -> str:
    return "#ffffff" if idx >= _AMBANG_TEKS_PUTIH else "#0d366b"


def _t(x, y, teks, ukuran=11, warna_="#1b2430", anchor="start", tebal=False, putar=None):
    tr = f' transform="rotate({putar} {x:.1f} {y:.1f})"' if putar else ""
    berat = ' font-weight="600"' if tebal else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="{FONT}" '
            f'font-size="{ukuran}"{berat} fill="{warna_}"{tr}>{escape(str(teks))}</text>')


# ------------------------------------------------------------------ 1. hub melingkar
def lingkar_hub(hub: Sequence[Dict[str, Any]], tepi: Sequence = (), n: int = 10,
                lebar: int = 620, tinggi: int = 560, gelap: bool = False, transparan: bool = False,
                judul: str = "", metrik: str = "mcc") -> str:
    """Protein paling sentral disusun melingkar, diwarnai menurut peringkat (gelap = paling sentral).

    hub: keluaran core.farmakologi.hub() — butuh kunci 'gen' dan `metrik`.
    tepi: [(gen_a, gen_b, skor)] apa pun; hanya pasangan yang kedua ujungnya masuk lingkaran digambar.
    Susunan melingkar dipakai karena yang dibaca adalah peringkat dan kerapatan hubungan antarhub,
    bukan jarak topologisnya — tata letak gaya pegas justru menyembunyikan peringkat itu.
    """
    w = warna(gelap)
    atas = 46 if judul else 20
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{lebar}" height="{tinggi}" '
         f'viewBox="0 0 {lebar} {tinggi}">']
    if not transparan:
        o.append(f'<rect width="{lebar}" height="{tinggi}" fill="{w["latar"]}"/>')
    if judul:
        o.append(_t(lebar / 2, 28, judul, 14, w["tinta"], "middle", tebal=True))

    pilih = list(hub)[:max(1, n)]
    if not pilih:
        o.append(_t(lebar / 2, tinggi / 2, _tr("Belum ada protein hub."), 12, w["tinta2"], "middle"))
        o.append("</svg>")
        return "\n".join(o)

    kw, kh = 86.0, 26.0                      # ukuran kotak gen
    cx, cy = lebar / 2.0, atas + (tinggi - atas - 46) / 2.0
    jari = min(lebar / 2 - kw / 2 - 16, (tinggi - atas - 46) / 2 - kh / 2 - 10)
    sudut0 = -math.pi / 2                    # peringkat 1 di puncak, lalu searah jarum jam
    pos = {}
    for i, b in enumerate(pilih):
        a = sudut0 + 2 * math.pi * i / len(pilih)
        pos[str(b["gen"]).upper()] = (cx + jari * math.cos(a), cy + jari * math.sin(a))

    # Tepi lebih dulu supaya tertutup kotak, bukan menimpanya.
    ada = set(pos)
    digambar = set()
    for e in tepi:
        if len(e) < 2:
            continue
        a, b = str(e[0]).upper(), str(e[1]).upper()
        if a in ada and b in ada and a != b and (b, a) not in digambar:
            digambar.add((a, b))
            (x1, y1), (x2, y2) = pos[a], pos[b]
            o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="{w["garis"]}" stroke-width="1" stroke-opacity="0.5"/>')

    for i, b in enumerate(pilih):
        gen = str(b["gen"]).upper()
        x, y = pos[gen]
        idx = _langkah(i, len(pilih))
        o.append(f'<rect x="{x - kw / 2:.1f}" y="{y - kh / 2:.1f}" width="{kw}" height="{kh}" rx="5" '
                 f'fill="{RAMP_BIRU[idx]}" stroke="{w["latar"]}" stroke-width="2"/>')
        o.append(_t(x, y + 4, gen, 11.5, _teks_di_atas(idx), "middle", tebal=True))

    # Keterangan ramp: peringkat 1 paling gelap. Angka metriknya tetap ada di tabel, jadi di sini
    # cukup arah peringkatnya.
    lx, ly = 24, tinggi - 30
    lebar_kotak = 15
    o.append(_t(lx, ly - 8, _tr("Peringkat {0}").format(metrik.upper()), 10.5, w["tinta2"]))
    for i in range(len(pilih)):
        idx = _langkah(i, len(pilih))
        o.append(f'<rect x="{lx + i * lebar_kotak}" y="{ly}" width="{lebar_kotak}" height="10" '
                 f'fill="{RAMP_BIRU[idx]}"/>')
    o.append(_t(lx, ly + 24, _tr("1 (paling sentral)"), 10, w["tinta2"]))
    o.append(_t(lx + len(pilih) * lebar_kotak, ly + 24, str(len(pilih)), 10, w["tinta2"], "end"))
    o.append("</svg>")
    return "\n".join(o)


# ------------------------------------------------------------------ 2. bubble plot jalur
def gelembung_jalur(jalur: Sequence[Dict[str, Any]], n: int = 15, lebar: int = 860, tinggi: int = 560,
                    gelap: bool = False, transparan: bool = False, judul: str = "") -> str:
    """Dot plot pengayaan jalur: sumbu x rasio gen, ukuran titik jumlah gen, warna −log₁₀(q).

    Bentuk baku pada naskah farmakologi jaringan. Rasio gen = gen kueri yang jatuh pada jalur dibagi
    seluruh gen kueri yang terpetakan; angkanya ditulis di samping tiap titik supaya figurnya tetap
    terbaca saat dicetak hitam-putih.
    """
    w = warna(gelap)
    baris = [b for b in jalur if b.get("n_overlap")][:max(1, n)]
    if not baris:
        k = Kanvas(lebar, 200, gelap, transparan, judul)
        k.teks(lebar / 2, 110, _tr("Belum ada jalur yang lolos ambang q."), 12, "middle", warna_=w["tinta2"])
        return k.selesai()

    baris = list(reversed(baris))            # q terkecil di atas gambar
    n_kueri = max(int(baris[0].get("n_kueri") or 1), 1)
    rasio = [int(b["n_overlap"]) / n_kueri for b in baris]
    jumlah = [int(b["n_overlap"]) for b in baris]
    qv = [max(float(b.get("q") or 1.0), 1e-300) for b in baris]
    nlq = [-math.log10(q) for q in qv]

    # Lebar kiri mengikuti nama jalur terpanjang supaya tidak ada label terpotong.
    maks_huruf = min(46, max(len(str(b["nama"])) for b in baris))
    kiri = min(400, 40 + int(maks_huruf * 6.1))
    kanan = 118                              # ruang untuk dua keterangan
    atas = 50 if judul else 26
    bawah = 76                               # judul sumbu + catatan kaki, masing-masing punya barisnya
    ph = tinggi - atas - bawah
    pw = lebar - kiri - kanan
    if pw < 120:
        kiri = max(120, lebar - kanan - 120)
        pw = lebar - kiri - kanan

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{lebar}" height="{tinggi}" '
         f'viewBox="0 0 {lebar} {tinggi}">']
    if not transparan:
        o.append(f'<rect width="{lebar}" height="{tinggi}" fill="{w["latar"]}"/>')
    if judul:
        o.append(_t(kiri, 30, judul, 14, w["tinta"], tebal=True))

    x_maks = max(rasio) * 1.18 or 1.0
    def X(v):
        return kiri + (v / x_maks) * pw
    pita = ph / len(baris)
    def Y(i):
        return atas + pita * (i + 0.5)

    for i in range(len(baris)):
        o.append(f'<line x1="{kiri}" y1="{Y(i):.1f}" x2="{kiri + pw}" y2="{Y(i):.1f}" '
                 f'stroke="{w["kisi"]}" stroke-width="1"/>')
    o.append(f'<line x1="{kiri}" y1="{atas}" x2="{kiri}" y2="{atas + ph}" stroke="{w["garis"]}"/>')
    o.append(f'<line x1="{kiri}" y1="{atas + ph}" x2="{kiri + pw}" y2="{atas + ph}" stroke="{w["garis"]}"/>')

    from .grafik import tik as _tik
    tx, _ = _tik(0, x_maks, 5)
    for v in tx:
        if v < 0 or v > x_maks:
            continue
        o.append(f'<line x1="{X(v):.1f}" y1="{atas + ph}" x2="{X(v):.1f}" y2="{atas + ph + 5}" '
                 f'stroke="{w["garis"]}"/>')
        o.append(_t(X(v), atas + ph + 18, fmt(v, 2), 10.5, w["tinta2"], "middle"))
    o.append(_t(kiri + pw / 2, atas + ph + 40, _tr("Rasio gen (gen jalur ÷ gen kueri)"), 11.5, w["tinta2"], "middle"))

    r_min, r_maks = 4.0, 13.0
    j_min, j_maks = min(jumlah), max(jumlah)
    def R(j):
        if j_maks == j_min:
            return (r_min + r_maks) / 2
        # Luas sebanding jumlah: mata membaca luas, bukan jari-jari.
        f = (j - j_min) / (j_maks - j_min)
        return math.sqrt(r_min ** 2 + f * (r_maks ** 2 - r_min ** 2))

    nl_min, nl_maks = min(nlq), max(nlq)
    def C(v):
        f = 0.5 if nl_maks == nl_min else (v - nl_min) / (nl_maks - nl_min)
        return RAMP_BIRU[max(0, min(len(RAMP_BIRU) - 1, int(round(f * (len(RAMP_BIRU) - 1)))))]

    for i, b in enumerate(baris):
        nama = str(b["nama"])
        if len(nama) > maks_huruf:
            nama = nama[:maks_huruf - 1] + "…"
        o.append(_t(kiri - 10, Y(i) + 4, nama, 11, w["tinta"], "end"))
        r = R(jumlah[i])
        o.append(f'<circle cx="{X(rasio[i]):.1f}" cy="{Y(i):.1f}" r="{r:.1f}" fill="{C(nlq[i])}" '
                 f'stroke="{w["latar"]}" stroke-width="1.5"/>')
        o.append(_t(X(rasio[i]) + r + 5, Y(i) + 4, jumlah[i], 10, w["tinta2"]))

    # Keterangan warna (−log10 q) dan ukuran (jumlah gen) — identitas tidak boleh warna saja.
    lx = kiri + pw + 18
    o.append(_t(lx, atas + 10, "−log₁₀(q)", 10.5, w["tinta2"]))
    for i in range(len(RAMP_BIRU)):
        o.append(f'<rect x="{lx}" y="{atas + 16 + i * 9}" width="14" height="9" fill="{RAMP_BIRU[i]}"/>')
    o.append(_t(lx + 19, atas + 24, fmt(nl_min, 1), 9.5, w["tinta2"]))
    o.append(_t(lx + 19, atas + 16 + len(RAMP_BIRU) * 9, fmt(nl_maks, 1), 9.5, w["tinta2"]))

    ly = atas + 30 + len(RAMP_BIRU) * 9 + 28
    o.append(_t(lx, ly - 10, _tr("Jumlah gen"), 10.5, w["tinta2"]))
    for k, j in enumerate(sorted({j_min, (j_min + j_maks) // 2, j_maks})):
        r = R(j)
        o.append(f'<circle cx="{lx + 10}" cy="{ly + 10 + k * 30:.1f}" r="{r:.1f}" fill="none" '
                 f'stroke="{w["garis"]}" stroke-width="1.2"/>')
        o.append(_t(lx + 26, ly + 14 + k * 30, j, 9.5, w["tinta2"]))

    o.append(_t(kiri, tinggi - 10, _tr("Uji hipergeometrik satu sisi, koreksi Benjamini-Hochberg."),
                9.5, w["tinta2"]))
    o.append("</svg>")
    return "\n".join(o)


# ------------------------------------------------------------------ 3. batang jalur
def batang_jalur(jalur: Sequence[Dict[str, Any]], n: int = 10, lebar: int = 820, tinggi: int = 460,
                 gelap: bool = False, transparan: bool = False, judul: str = "") -> str:
    """Batang mendatar jumlah gen per jalur, terurut dari yang terbanyak."""
    w = warna(gelap)
    baris = [b for b in jalur if b.get("n_overlap")][:max(1, n)]
    if not baris:
        k = Kanvas(lebar, 200, gelap, transparan, judul)
        k.teks(lebar / 2, 110, _tr("Belum ada jalur yang lolos ambang."), 12, "middle", warna_=w["tinta2"])
        return k.selesai()
    baris = sorted(baris, key=lambda b: int(b["n_overlap"]))

    maks_huruf = min(48, max(len(str(b["nama"])) for b in baris))
    kiri = min(420, 30 + int(maks_huruf * 6.1))
    kanan, bawah = 52, 54
    atas = 48 if judul else 24
    ph, pw = tinggi - atas - bawah, lebar - kiri - kanan

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{lebar}" height="{tinggi}" '
         f'viewBox="0 0 {lebar} {tinggi}">']
    if not transparan:
        o.append(f'<rect width="{lebar}" height="{tinggi}" fill="{w["latar"]}"/>')
    if judul:
        o.append(_t(kiri, 30, judul, 14, w["tinta"], tebal=True))

    nilai = [int(b["n_overlap"]) for b in baris]
    from .grafik import tik as _tik
    tx, _ = _tik(0, max(nilai), 6)
    x_maks = tx[-1] or 1
    pita = ph / len(baris)
    tebal = min(22.0, pita * 0.62)

    for v in tx:
        x = kiri + v / x_maks * pw
        o.append(f'<line x1="{x:.1f}" y1="{atas}" x2="{x:.1f}" y2="{atas + ph}" stroke="{w["kisi"]}"/>')
        o.append(_t(x, atas + ph + 18, fmt(v, 0), 10.5, w["tinta2"], "middle"))
    o.append(f'<line x1="{kiri}" y1="{atas}" x2="{kiri}" y2="{atas + ph}" stroke="{w["garis"]}"/>')

    for i, b in enumerate(baris):
        y = atas + pita * (i + 0.5)
        panjang = nilai[i] / x_maks * pw
        nama = str(b["nama"])
        if len(nama) > maks_huruf:
            nama = nama[:maks_huruf - 1] + "…"
        o.append(_t(kiri - 10, y + 4, nama, 11, w["tinta"], "end"))
        # Ujung data dibulatkan, pangkalnya menempel sumbu — batang tidak mengambang.
        o.append(f'<rect x="{kiri}" y="{y - tebal / 2:.1f}" width="{max(panjang, 1):.1f}" height="{tebal:.1f}" '
                 f'rx="4" fill="{RAMP_BIRU[6]}"/>')
        o.append(_t(kiri + panjang + 7, y + 4, nilai[i], 10.5, w["tinta2"]))

    o.append(_t(kiri + pw / 2, atas + ph + 40, _tr("Jumlah gen kueri pada jalur"), 11.5, w["tinta2"], "middle"))
    o.append("</svg>")
    return "\n".join(o)


# ------------------------------------------------------------------ daftar figur
def daftar() -> List[Dict[str, str]]:
    """Figur yang tersedia: (kunci, nama tampilan, keterangan singkat)."""
    return [
        {"kunci": "venn", "nama": "Diagram Venn irisan",
         "ket": "Target senyawa dibandingkan dengan gen penyakit; irisannya adalah target terapi potensial."},
        {"kunci": "jaringan", "nama": "Jaringan berlapis",
         "ket": "Senyawa–target–jalur–penyakit dengan tata letak gaya pegas."},
        {"kunci": "hub", "nama": "Hub melingkar (peringkat MCC)",
         "ket": "Protein paling sentral, diwarnai menurut peringkat."},
        {"kunci": "gelembung", "nama": "Bubble plot jalur",
         "ket": "Rasio gen, jumlah gen, dan nilai q dalam satu gambar."},
        {"kunci": "batang", "nama": "Batang jalur",
         "ket": "Jumlah gen per jalur, bentuk paling ringkas."},
    ]
