"""Uji core/sascore.py: perhitungan SAScore untuk berbagai molekul acuan.

PYTHONPATH=. .venv/Scripts/python.exe dev/uji_sascore.py
"""
import sys
from pathlib import Path

# Pastikan import virmolab bekerja
AKAR = Path(__file__).resolve().parents[1]
if str(AKAR) not in sys.path:
    sys.path.insert(0, str(AKAR))

from virmolab.core import sascore

SENYAWA = [
    ("Aspirin", "CC(=O)Oc1ccccc1C(=O)O", 1.0, 2.5, "Mudah"),
    ("Kafein", "Cn1cnc2c1c(=O)n(C)c(=O)n2C", 1.5, 3.0, "Mudah"),
    ("Diazepam", "CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21", 2.0, 3.0, "Mudah"),
    ("Atorvastatin", "CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CC[C@@H](O)C[C@@H](O)CC(=O)O", 3.0, 5.0, "Sedang"),
    ("Siklosporin A", "CC[C@H]1C(=O)N(CC(=O)N([C@H](C(=O)N[C@H](C(=O)N([C@H](C(=O)N[C@H](C(=O)N[C@@H](C(=O)N([C@H](C(=O)N([C@H](C(=O)N([C@H](C(=O)N([C@H](C(=O)N1)[C@@H]([C@H](C)C/C=C/C)O)C)C(C)C)C)CC(C)C)C)CC(C)C)C)C)C)CC(C)C)C)C(C)C)CC(C)C)C)C", 6.0, 9.0, "Sulit"),
]

gagal = 0
for nama, smi, min_s, maks_s, kat_harapan in SENYAWA:
    skor = sascore.hitung_sascore(smi)
    kat = sascore.kategori(skor)
    ok = (skor is not None) and (min_s <= skor <= maks_s) and (kat == kat_harapan)
    if not ok:
        gagal += 1
    print(f"{'OK  ' if ok else 'GAGAL'} {nama:15s} SAScore: {skor} (rentang {min_s}..{maks_s}) | Kategori: {kat} ({kat_harapan})")

# Uji penanganan masukan tidak valid
skor_none = sascore.hitung_sascore(None)
skor_salah = sascore.hitung_sascore("SMILES_TIDAK_VALID_XYZ")
if skor_none is not None or skor_salah is not None:
    gagal += 1
    print("GAGAL: penanganan masukan salah tidak mengembalikan None")
else:
    print("OK   Penanganan masukan tak valid aman (mengembalikan None)")

print(f"\nTotal gagal: {gagal}")
sys.exit(gagal)
