"""Buat fixture keluaran co-folding peptida MDM2-p53 (1YCR) di dev/data/boltz_1ycr.

Koordinatnya NYATA: diambil dari struktur kristal 1YCR (RCSB, dev/data/1YCR.pdb). Yang sintetis hanya
berkas metrik JSON dan perlakuan terhadap peptida: rantai p53 diputar dan digeser secara rigid sejauh
beberapa angstrom supaya penyelarasan dan perhitungan RMSD benar-benar teruji, bukan membandingkan
berkas dengan dirinya sendiri. Jadi fixture ini menguji alur baca, selaraskan, dan nilai, BUKAN
ketepatan prediksi Boltz-2. Prediksi sungguhan hanya diuji dengan --daring setelah Boltz terpasang.

Keluaran mengikuti tata letak folder Boltz-2:
  dev/data/boltz_1ycr/predictions/boltz_1ycr/boltz_1ycr_model_0.pdb
  dev/data/boltz_1ycr/predictions/boltz_1ycr/confidence_boltz_1ycr_model_0.json
"""
import json
import math
from pathlib import Path

import numpy as np

AKAR = Path(__file__).resolve().parents[1]
SUMBER = AKAR / "dev" / "data" / "1YCR.pdb"
KELUAR = AKAR / "dev" / "data" / "boltz_1ycr" / "predictions" / "boltz_1ycr"

RANTAI_PEPTIDA = "B"
SUDUT_DERAJAT = 8.0          # rotasi rigid peptida
GESER_ANGSTROM = (1.2, -0.8, 0.6)


def _rotasi(sudut_derajat):
    """Matriks rotasi kecil terhadap sumbu z, cukup untuk menguji superposisi."""
    t = math.radians(sudut_derajat)
    return np.array([[math.cos(t), -math.sin(t), 0.0],
                     [math.sin(t), math.cos(t), 0.0],
                     [0.0, 0.0, 1.0]])


def main():
    if not SUMBER.exists():
        raise SystemExit(f"{SUMBER} tidak ada. Unduh 1YCR dari RCSB terlebih dahulu.")
    KELUAR.mkdir(parents=True, exist_ok=True)

    baris = [b for b in SUMBER.read_text(encoding="utf-8").splitlines() if b.startswith("ATOM")]
    pep = np.array([[float(b[30:38]), float(b[38:46]), float(b[46:54])]
                    for b in baris if b[21] == RANTAI_PEPTIDA])
    pusat = pep.mean(axis=0)
    R = _rotasi(SUDUT_DERAJAT)
    geser = np.asarray(GESER_ANGSTROM)

    keluar = []
    for b in baris:
        if b[21] == RANTAI_PEPTIDA:
            xyz = np.array([float(b[30:38]), float(b[38:46]), float(b[46:54])])
            xyz = (R @ (xyz - pusat)) + pusat + geser
            b = f"{b[:30]}{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}{b[54:]}"
        keluar.append(b)
    (KELUAR / "boltz_1ycr_model_0.pdb").write_text("\n".join(keluar) + "\nEND\n", encoding="utf-8")

    # Metrik keyakinan: angka ini DITULIS TANGAN, bukan keluaran model
    (KELUAR / "confidence_boltz_1ycr_model_0.json").write_text(
        json.dumps({"confidence_score": 0.8302, "ptm": 0.8713, "iptm": 0.7904,
                    "ligand_iptm": 0.0, "protein_iptm": 0.8688,
                    "complex_plddt": 0.8410, "complex_iplddt": 0.8122,
                    "complex_pde": 0.5908, "complex_ipde": 0.6731}, indent=1), encoding="utf-8")

    sisi = np.linalg.norm(pep - pep.mean(axis=0), axis=1).max()
    print(f"Fixture ditulis ke {KELUAR}")
    print(f"Peptida rantai {RANTAI_PEPTIDA}: {len(pep)} atom, radius {sisi:.1f} A, "
          f"digeser {np.linalg.norm(geser):.2f} A dan diputar {SUDUT_DERAJAT:g} derajat.")


if __name__ == "__main__":
    main()
