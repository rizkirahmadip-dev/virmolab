"""Pengujian mandiri Modul Protein-Protein Docking & Antarmuka (Fitur 5)."""
import os
import sys

# Tambahkan direktori kerja ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from virmodock.core import ppi

# Mock PDB dimer mini (Rantai A dan Rantai B berdekatan)
PDB_DIMER_MINI = """ATOM      1  N   ASP A   1      10.000  10.000  10.000  1.00 20.00           N
ATOM      2  CA  ASP A   1      11.000  10.000  10.000  1.00 20.00           C
ATOM      3  C   ASP A   1      12.000  10.000  10.000  1.00 20.00           C
ATOM      4  O   ASP A   1      12.500  10.000  11.000  1.00 20.00           O
ATOM      5  CB  ASP A   1      11.000  11.500  10.000  1.00 20.00           C
ATOM      6  CG  ASP A   1      11.000  12.500  11.000  1.00 20.00           C
ATOM      7  OD1 ASP A   1      10.500  12.500  12.100  1.00 20.00           O
ATOM      8  OD2 ASP A   1      11.500  13.500  10.800  1.00 20.00           O
TER
ATOM      9  N   ARG B   1      10.500  12.500  15.000  1.00 20.00           N
ATOM     10  CA  ARG B   1      11.000  12.500  16.000  1.00 20.00           C
ATOM     11  C   ARG B   1      12.000  12.500  16.000  1.00 20.00           C
ATOM     12  O   ARG B   1      12.500  12.500  15.000  1.00 20.00           O
ATOM     13  CB  ARG B   1      11.000  11.000  16.500  1.00 20.00           C
ATOM     14  CG  ARG B   1      11.000  11.000  18.000  1.00 20.00           C
ATOM     15  CD  ARG B   1      11.000  12.200  18.800  1.00 20.00           C
ATOM     16  NE  ARG B   1      10.800  12.200  20.200  1.00 20.00           N
ATOM     17  CZ  ARG B   1      10.500  12.500  21.300  1.00 20.00           C
ATOM     18  NH1 ARG B   1      10.500  12.500  14.500  1.00 20.00           N
TER
END
"""


def run_tests():
    print("=== Menguji Modul Protein-Protein Docking (PPI) ===")
    gagal = 0

    # Uji 1: prediksi_antarmuka
    res_sasa = ppi.prediksi_antarmuka(PDB_DIMER_MINI, ambang_relatif=0.15)
    if len(res_sasa) == 2 and any(r["kandidat"] for r in res_sasa):
        print(f"OK   prediksi_antarmuka berhasil menghitung SASA ({res_sasa[0]['label']}: {res_sasa[0]['sasa']} A^2)")
    else:
        print(f"FAIL prediksi_antarmuka gagal: {res_sasa}")
        gagal += 1

    # Uji 2: skor_antarmuka
    skor = ppi.skor_antarmuka(PDB_DIMER_MINI, rantai_a="A", rantai_b="B", cutoff_jarak=5.0)
    if "error" not in skor and skor.get("kontak_total", 0) > 0 and skor.get("bsa_luas", 0) > 0:
        print(f"OK   skor_antarmuka berhasil (Kontak: {skor['kontak_total']}, BSA: {skor['bsa_luas']} A^2, H-Bond: {skor['ikatan_h']})")
    else:
        print(f"FAIL skor_antarmuka gagal: {skor}")
        gagal += 1

    # Uji 3: klaster_pose
    model2 = PDB_DIMER_MINI.replace("10.000", "10.500")  # Model mirip (< 1 Å RMSD)
    model3 = PDB_DIMER_MINI.replace("10.000", "25.000")  # Model berbeda jauh (> 10 Å RMSD)
    klaster = ppi.klaster_pose([PDB_DIMER_MINI, model2, model3], rmsd_ambang=3.0)
    # Harus terbagi menjadi 2 klaster: klaster 1 (model 0 & 1), klaster 2 (model 2)
    if len(klaster) == 2 and klaster[0]["ukuran"] == 2 and klaster[1]["ukuran"] == 1:
        print(f"OK   klaster_pose berhasil mengelompokkan model (Klaster 1: {klaster[0]['ukuran']} model, Klaster 2: {klaster[1]['ukuran']} model)")
    else:
        print(f"FAIL klaster_pose gagal: {klaster}")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(run_tests())
