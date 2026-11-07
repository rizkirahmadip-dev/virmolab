"""Bungkus docs/_sumber/*.html dengan kerangka & navigasi seragam -> docs/*.html."""
from pathlib import Path
import re
SUMBER = Path("docs/_sumber")
NAV = [("panduan", "Panduan pengguna"), ("instalasi", "Instalasi"), ("pindah_laptop", "Pindah laptop"),
       ("gpu", "Setup GPU"), ("troubleshooting", "Mengatasi masalah"), ("metode", "Metode & kriteria"),
       ("validasi", "Validasi")]
# Dokumen berbahasa Inggris dibangun dari <nama>_en.html dengan navigasinya sendiri, supaya pengguna
# antarmuka Inggris tidak mendarat di halaman berbahasa Indonesia.
NAV_EN = [("instalasi_en", "Installation"), ("pindah_laptop_en", "Move to another laptop"),
          ("gpu_en", "GPU setup"), ("troubleshooting_en", "Troubleshooting"),
          ("validasi_en", "Validation")]
versi = re.search(r'__version__ = "([^"]+)"', Path("virmolab/__init__.py").read_text()).group(1)
for nama, judul in NAV + NAV_EN:
    isi = (SUMBER / f"{nama}.html").read_text(encoding="utf-8")
    nav = "".join(f'<a href="{n}.html"{" class=\"aktif\"" if n == nama else ""}>{t.replace("&", "&amp;")}</a>' for n, t in (NAV_EN if nama.endswith('_en') else NAV))
    inggris = nama.endswith('_en')
    # Tombol bahasa menuju halaman yang sama dalam bahasa lain bila ada; kalau belum diterjemahkan,
    # jatuh ke halaman instalasi, bukan ke tautan mati.
    if inggris:
        pasangan = nama.removesuffix("_en")
        nav += f'<a href="{pasangan if any(n == pasangan for n, _ in NAV) else "panduan"}.html">ID</a>'
    else:
        pasangan = f"{nama}_en"
        nav += f'<a href="{pasangan if any(n == pasangan for n, _ in NAV_EN) else "instalasi_en"}.html">EN</a>'
    html = (f'<!doctype html><html lang="{"en" if inggris else "id"}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{judul.replace("&", "&amp;")} · VirmoLab</title><link rel="stylesheet" href="gaya.css">'
            f'<link rel="icon" href="gambar/ikon.png"></head><body><header><img src="gambar/logo_putih.svg" alt="VirmoLab" style="height:30px;margin-right:6px"><span style="color:#9fb4d3;font-size:13px;margin-right:10px">{versi}</span>{nav}</header><main>{isi}'
            f'<footer>VirmoLab {versi} · {"offline documentation" if inggris else "dokumentasi offline"} · GPL-3.0-or-later</footer></main></body></html>\n')
    Path(f"docs/{nama}.html").write_text(html, encoding="utf-8")
    print("docs/" + nama + ".html")
import shutil; shutil.copy("virmolab/aset/virmolab_256.png", "docs/gambar/ikon.png"); shutil.copy("branding/virmolab_logo_horizontal_putih.svg", "docs/gambar/logo_putih.svg"); shutil.copy("branding/virmolab_logo_horizontal.svg", "docs/gambar/logo_horizontal.svg")
