"""Draf bab skripsi, BibTeX, dan pemeriksa figur.

Draf bukan naskah jadi: ia menyusun metode dan tabel hasil dari proyek supaya bisa ditempel
ke Bab III dan Bab IV, lalu disunting penulis.
"""
import re

from .arti import paragraf
from .laporan import SITASI

# Machado dkk. 2009, aproksimasi buta warna merah-hijau (protanopia) pada RGB 0-1.
_PROTAN = (
    (0.152286, 1.052583, -0.204868),
    (0.114503, 0.786281, 0.099216),
    (-0.003882, -0.048116, 1.051998),
)


def _hex(warna):
    w = warna.strip().lstrip("#")
    if len(w) == 3:
        w = "".join(c * 2 for c in w)
    return tuple(int(w[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _sim(rgb):
    return tuple(max(0.0, min(1.0, sum(baris[k] * rgb[k] for k in range(3)))) for baris in _PROTAN)


def _jarak(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


def periksa_figur(dpi, lebar_mm, font_pt, warna=()):
    """Daftar peringatan. Kosong berarti tidak ada yang mencolok."""
    pesan = []
    if dpi < 300:
        pesan.append(f"Resolusi {dpi:g} dpi di bawah 300 dpi yang diminta sebagian besar jurnal.")
    if lebar_mm and font_pt:
        # huruf 6 pt pada lebar kolom adalah batas baca; tidak diskalakan ulang di sini
        if font_pt < 6:
            pesan.append(f"Ukuran huruf {font_pt:g} pt lebih kecil dari 6 pt pada ukuran cetak.")
    if lebar_mm and lebar_mm > 190:
        pesan.append(f"Lebar {lebar_mm:g} mm melebihi halaman A4 (±190 mm termasuk tepi).")
    rgb = []
    for w in warna:
        try:
            rgb.append((w, _hex(w)))
        except Exception:
            continue   # warna yang tidak dikenali dilewati; pemeriksaan buta warna memakai sisanya
    for i in range(len(rgb)):
        for j in range(i + 1, len(rgb)):
            asli = _jarak(rgb[i][1], rgb[j][1])
            buta = _jarak(_sim(rgb[i][1]), _sim(rgb[j][1]))
            if asli > 0.25 and buta < 0.12:
                pesan.append(f"Warna {rgb[i][0]} dan {rgb[j][0]} sulit dibedakan pada buta warna merah-hijau.")
    return pesan


def _kunci(teks):
    kata = re.findall(r"[A-Za-z]{3,}", teks)
    return (kata[0] + (kata[-1] if len(kata) > 1 else "")).lower()[:24] or "rujukan"


def bibtex(tambahan=()):
    """Teks BibTeX dari sitasi mesin yang sudah dipakai laporan, plus pasangan (kunci, teks) tambahan."""
    blok = []
    lihat = set()
    for k, teks in list(SITASI.items()) + list(tambahan):
        kunci = re.sub(r"[^a-z0-9]+", "", _kunci(teks)) or k
        if kunci in lihat:
            kunci += k[:4]
        lihat.add(kunci)
        tahun = re.search(r"(19|20)\d{2}", teks)
        blok.append(
            f"@misc{{{kunci},\n  note = {{{teks}}}" +
            (f",\n  year = {{{tahun.group(0)}}}" if tahun else "") + "\n}")
    return "\n\n".join(blok) + "\n"


def draf_skripsi(info):
    """info: nama, reseptor, mesin, parameter, validasi, baris=[(ligan, energi, ki)], catatan."""
    baris = info.get("baris") or []
    tabel = ["| Ligan | Skor (kkal/mol) | Ki perkiraan |", "|---|---:|---|"]
    for nama, energi, ki in baris[:20]:
        tabel.append(f"| {nama} | {energi} | {ki or ' - '} |")
    if not baris:
        tabel.append("| - | - | belum ada hasil |")
    val = info.get("validasi") or "Validasi redocking belum dicatat."
    return "\n".join([
        f"# {info.get('nama') or 'Proyek docking'}",
        "",
        "## Bab III - Metode (draf)",
        "",
        f"Reseptor yang digunakan adalah {info.get('reseptor') or 'struktur yang disiapkan di VirmoDock'}. "
        f"Docking dijalankan dengan {info.get('mesin') or 'mesin yang dipilih di aplikasi'}"
        + (f" ({info.get('parameter')})" if info.get("parameter") else "") + ". "
        "Preparasi reseptor memakai gemmi dan Meeko; ligan diprotonasi lalu diubah ke PDBQT. "
        "Interaksi dikenali dengan kriteria jarak dan sudut yang tercantum di laporan metode VirmoDock. "
        "Skor docking adalah prediksi komputasi, bukan bukti aktivitas biologis.",
        "",
        val,
        "",
        "## Bab IV - Hasil (draf)",
        "",
        "Peringkat berikut diambil dari pose terbaik tiap ligan pada job terakhir yang sudah selesai. "
        "Angka pada docking kovalen adalah skor aduk, bukan ΔG, dan tidak dibandingkan dengan docking biasa.",
        "",
        *tabel,
        "",
        "## Arti angka",
        "",
        paragraf(),
        "",
        info.get("catatan") or "",
        "",
        "Draf ini disusun otomatis agar angka tidak disalin dengan tangan. Sunting kalimatnya sebelum "
        "dimasukkan ke naskah.",
        "",
    ])
