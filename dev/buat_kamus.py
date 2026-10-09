"""Gabungkan terjemahan ke virmodock/i18n/en.json.

Sumber: virmodock/i18n/en.json (kamus lama, dipertahankan) + dev/i18n_tambahan.json ({"teks": {id: en},
"pola": {pola: en}}) — entri tambahan menimpa. Teks baru: jalankan dev/ekstrak_teks.py (-> dev/i18n_teks_baru.json),
terjemahkan, tulis ke i18n_tambahan.json, lalu jalankan skrip ini.
(Riwayat: kamus awal dibuat dari dev/i18n_teks.json + i18n_b*/p*.json berbasis indeks; berkas indeks itu kini
diarsipkan di dev/uji/arsip_lama/i18n_indeks/ dan langkah indeks hanya berjalan bila dev/i18n_teks.json ada.)

  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/buat_kamus.py
"""
import json
import re
from pathlib import Path

KELUAR = Path("virmodock/i18n/en.json")
kamus = json.loads(KELUAR.read_text(encoding="utf-8")) if KELUAR.exists() else {"teks": {}, "pola": {}}
src = Path("dev/i18n_teks.json")
if src.exists():
    d = json.loads(src.read_text(encoding="utf-8"))
    for f in sorted(Path("dev").glob("i18n_b*.json")):
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            if int(k) < len(d["literal"]):
                kamus["teks"].setdefault(d["literal"][int(k)], v)
    for f in sorted(Path("dev").glob("i18n_p*.json")):
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            if int(k) < len(d["pola"]):
                kamus["pola"].setdefault(d["pola"][int(k)], v)
tambah = Path("dev/i18n_tambahan.json")
if tambah.exists():
    d = json.loads(tambah.read_text(encoding="utf-8"))
    kamus["teks"].update(d.get("teks", {}))
    for k, v in d.get("pola", {}).items():
        (kamus["pola"] if re.search(r"\{\d+\}", k) else kamus["teks"])[k] = v
for k, v in kamus["pola"].items():
    if sorted(re.findall(r"\{\d+\}", k)) != sorted(re.findall(r"\{\d+\}", v)):
        print("PLACEHOLDER BEDA:", k[:70])
KELUAR.write_text(json.dumps(kamus, ensure_ascii=False, indent=0), encoding="utf-8")
print(len(kamus["teks"]), "teks,", len(kamus["pola"]), "pola")
