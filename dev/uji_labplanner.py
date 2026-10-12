"""Uji core/labplanner.py: Kalkulator Pengujian Laboratorium Basah (Wet-Lab Planner).

PYTHONPATH=. .venv/Scripts/python.exe dev/uji_labplanner.py
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
if str(AKAR) not in sys.path:
    sys.path.insert(0, str(AKAR))

from virmodock.core import labplanner

gagal = 0

# 1. Uji prediksi Ki & IC50 dari ΔG
# ΔG = -8.18 kcal/mol -> Ki ~ 1.0 μM
ki_res = labplanner.prediksi_ki_ic50(-8.18)
print(f"dG = -8.18 kcal/mol -> Ki: {ki_res['ki_teks'].replace(chr(956), 'u')}, IC50: {ki_res['ic50_teks'].replace(chr(956), 'u')}")
if not (0.8 <= ki_res["ki_uM"] <= 1.2):
    print("GAGAL: Nilai Ki untuk -8.18 kcal/mol seharusnya ~1.0 uM")
    gagal += 1
else:
    print("OK   Prediksi Ki akurat (~1.0 uM)")

# 2. Uji seri konsentrasi pengenceran bertingkat (faktor 3)
seri = labplanner.hitung_seri_konsentrasi(kons_maks_uM=100.0, faktor_pengenceran=3.0, jumlah_titik=8)
print("Seri konsentrasi (faktor 3):", seri)
if len(seri) != 8 or seri[0] != 100.0 or seri[1] != round(100.0 / 3.0, 4):
    print("GAGAL: Seri pengenceran tidak sesuai")
    gagal += 1
else:
    print("OK   Seri pengenceran bertingkat terhitung benar")

# 3. Uji protokol pemipetan
prot = labplanner.buat_protokol_pipet(stok_mM=10.0, seri_kons_uM=seri, volume_sumur_uL=100.0, dmso_maks_persen=0.5)
if len(prot["langkah"]) != 8 or prot["dmso_maks_persen"] != 0.5:
    print("GAGAL: Protokol pemipetan tidak sesuai")
    gagal += 1
else:
    print("OK   Protokol pemipetan mikro terhitung benar")

# 4. Uji denah pelat 96-well
denah = labplanner.rancang_denah_pelat(
    format_pelat="96",
    daftar_sampel=[{"nama": "Senyawa_1", "konsentrasi": seri}],
    replikasi=3
)
grid = denah["grid"]
# Cek apakah kontrol positif dan blanko terpasang
if "A12" not in grid or grid["A12"]["jenis"] != "blanko":
    print("GAGAL: Sumur A12 bukan blanko")
    gagal += 1
elif grid["A1"]["jenis"] != "sampel" or grid["A1"]["kons_uM"] != 100.0:
    print("GAGAL: Sumur A1 bukan sampel 100 μM")
    gagal += 1
else:
    print("OK   Denah pelat mikro 96-well terpetakan lengkap (sampel, triplo, kontrol)")

# 5. Uji format teks protokol
teks_lapor = labplanner.buat_teks_protokol("Aspirin", -8.18, ki_res, prot)
if "PROTOKOL PENGUJIAN IN VITRO" not in teks_lapor or "Aspirin" not in teks_lapor:
    print("GAGAL: Format teks protokol tidak lengkap")
    gagal += 1
else:
    print("OK   Teks protokol siap cetak terformat rapi")

print(f"\nTotal gagal: {gagal}")
sys.exit(gagal)
