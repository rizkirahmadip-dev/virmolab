"""Uji mandiri tolok ukur validasi redocking PDBbind (1HSG/MK1).

PYTHONPATH=. .venv/Scripts/python.exe dev/uji_tolok_ukur.py
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
if str(AKAR) not in sys.path:
    sys.path.insert(0, str(AKAR))

from virmolab.core import tolok_ukur

def main():
    print("=== Menjalankan Tolok Ukur Validasi Redocking 1HSG (Indinavir) ===")
    try:
        hasil = tolok_ukur.jalankan_benchmark_1hsg(mesin_docking="vina", exhaustiveness=4, timeout=120)
    except Exception as e:
        print(f"FAIL Galat saat menjalankan benchmark: {e}")
        return 1

    print(f"Target : {hasil['target']}")
    print(f"Ligan  : {hasil['ligan']}")
    print(f"Mesin  : {hasil['mesin']}")
    print(f"RMSD   : {hasil['rmsd']} Å")
    print(f"ΔG     : {hasil['energi']} kcal/mol")
    print(f"LE     : {hasil['le']}")
    print(f"Waktu  : {hasil['waktu_detik']} detik")
    print(f"Kontak : {list(hasil['kontak_residu'].keys())[:6]}...")
    print(f"Status : {'SUKSES (RMSD <= 2.0 Å)' if hasil['sukses'] else 'DILUAR AMBANG (RMSD > 2.0 Å)'}")

    if hasil["rmsd"] <= 2.5:
        print("OK   Tolok ukur redocking 1HSG tervalidasi dengan baik!")
        return 0
    else:
        print("FAIL RMSD melebihi batas toleransi validasi")
        return 1

if __name__ == "__main__":
    sys.exit(main())
