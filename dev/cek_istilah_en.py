# -*- coding: utf-8 -*-
"""Nama menu dan tombol di dokumen berbahasa Inggris harus benar-benar ada di antarmuka.

Panduan yang rapi tetapi menyebut menu yang tidak ada lebih menyesatkan daripada panduan yang belum
diterjemahkan: pembaca mencari-cari sesuatu yang memang tidak pernah ada. Terjemahan dokumen mudah
menghasilkan itu — nama menu diterjemahkan sekenanya, padahal antarmukanya memakai kata lain yang
sudah tercatat di virmolab/i18n/en.json.

Alat ini membaca tiap <b>…</b> di docs/_sumber/*_en.html, memecah jalur menu pada tanda ›, lalu
mencocokkan tiap bagiannya dengan nilai bahasa Inggris di en.json.

Keluarannya daftar untuk diperiksa, bukan vonis: <b> juga dipakai untuk penegasan biasa ("Yes",
"The portable build"), dan itu wajar tidak ada di en.json. Yang dicari adalah nama menu atau tombol
yang salah tulis.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/cek_istilah_en.py [nama_en ...]
"""
import json
import re
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
SUMBER = AKAR / "docs" / "_sumber"

# Kata penegasan yang lazim dan memang bukan nama kontrol; menandainya hanya jadi kebisingan.
BIASA = {"yes", "no", "note", "warning", "important", "tip", "example", "default", "optional",
         "required", "new", "paused", "running", "done", "failed", "the portable build",
         "portable build", "installer", "a single project", "without exporting"}


def teks_bersih(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&nbsp;", " ").replace("&Delta;", "Δ"))
    return " ".join(s.split())


def nilai_en() -> set:
    d = json.loads((AKAR / "virmolab" / "i18n" / "en.json").read_text(encoding="utf-8"))["teks"]
    ada = set()
    for v in d.values():
        v = teks_bersih(v)
        ada.add(v.casefold())
        ada.add(v.rstrip(".…").casefold())
        # Label tombol kadang memuat tanda pintasan Qt yang tidak terlihat pengguna.
        ada.add(v.replace("&&", "&").casefold())
        ada.add(v.replace("&", "").casefold())
    return ada


def periksa(berkas: Path, ada: set):
    isi = berkas.read_text(encoding="utf-8")
    hilang = []
    for m in re.finditer(r"<b>(.*?)</b>", isi, re.S):
        penuh = teks_bersih(m.group(1))
        for bagian in (p.strip() for p in penuh.split("›")):
            if not bagian or bagian.casefold() in BIASA:
                continue
            if len(bagian.split()) > 8:          # kalimat yang ditebalkan, bukan nama kontrol
                continue
            k = bagian.casefold()
            if k in ada or k.rstrip(".…") in ada:
                continue
            hilang.append((bagian, "jalur menu" if "›" in penuh else "penegasan atau kontrol"))
    return hilang


def main():
    ada = nilai_en()
    pilih = sys.argv[1:]
    berkas = sorted(SUMBER.glob("*_en.html"))
    if pilih:
        berkas = [b for b in berkas if b.stem in pilih or b.stem.removesuffix("_en") in pilih]
    total = 0
    for b in berkas:
        hilang = periksa(b, ada)
        print(f"\n{b.name}: {len(hilang)} perlu diperiksa")
        for teks, jenis in hilang:
            print(f"    [{jenis}] {teks!r}")
        total += len(hilang)
    print(f"\n{len(berkas)} berkas, {total} istilah perlu diperiksa "
          f"({len(ada)} nilai Inggris di en.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
