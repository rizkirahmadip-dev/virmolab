"""Uji core/mpo.py dan grafik.radar_svg: Multi-Parameter Optimization dan Radar Chart.

PYTHONPATH=. .venv/Scripts/python.exe dev/uji_mpo.py
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
if str(AKAR) not in sys.path:
    sys.path.insert(0, str(AKAR))

from virmolab.core import grafik, mpo, sifat

# Buat data sifat uji untuk Aspirin dan Diazepam
s_asp = sifat.dari_teks("CC(=O)Oc1ccccc1C(=O)O", "smiles")
s_diaz = sifat.dari_teks("CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21", "smiles")

gagal = 0

# 1. Hitung MPO Oral untuk Aspirin dengan ΔG = -6.5
res_oral = mpo.hitung_mpo(s_asp, dg=-6.5, preset="oral")
print(f"Aspirin Oral MPO: Skor {res_oral['skor']} ({res_oral['kategori']})")
if not (50.0 <= res_oral["skor"] <= 100.0):
    print("GAGAL: Skor MPO Aspirin di luar rentang yang diharapkan")
    gagal += 1
else:
    print("OK   Skor MPO Oral Aspirin wajar")

# 2. Hitung CNS-MPO untuk Diazepam (obat CNS terkenal)
res_cns = mpo.hitung_mpo(s_diaz, dg=-8.2, preset="cns")
print(f"Diazepam CNS-MPO: Skor {res_cns['skor']} ({res_cns['kategori']})")
if not (60.0 <= res_cns["skor"] <= 100.0):
    print("GAGAL: Skor CNS-MPO Diazepam seharusnya tinggi (menembus BBB)")
    gagal += 1
else:
    print("OK   Skor CNS-MPO Diazepam sesuai harapan (tinggi)")

# 3. Uji radar_svg
label = [komp["label"] for komp in res_oral["komponen"].values()]
nilai = [komp["skor"] for komp in res_oral["komponen"].values()]
svg_teks = grafik.radar_svg(label, nilai, judul="Aspirin - Oral MPO", subjudul=f"Skor Total: {res_oral['skor']}/100")

if "<svg" not in svg_teks or "</svg>" not in svg_teks or "Aspirin - Oral MPO" not in svg_teks:
    print("GAGAL: radar_svg tidak menghasilkan SVG yang valid")
    gagal += 1
else:
    print(f"OK   radar_svg berhasil menghasilkan SVG ({len(svg_teks)} karakter)")

# Simpan SVG uji
out = Path("dev/uji/mpo")
out.mkdir(parents=True, exist_ok=True)
(out / "radar_aspirin.svg").write_text(svg_teks, encoding="utf-8")
(out / "radar_diazepam_gelap.svg").write_text(
    grafik.radar_svg([k["label"] for k in res_cns["komponen"].values()],
                    [k["skor"] for k in res_cns["komponen"].values()],
                    gelap=True, judul="Diazepam - CNS MPO"),
    encoding="utf-8"
)

print(f"\nTotal gagal: {gagal}")
sys.exit(gagal)
