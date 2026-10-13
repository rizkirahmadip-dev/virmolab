"""Pengujian mandiri Analisis Termodinamika Air Sisi Aktif."""
import os
import sys

# Tambahkan direktori kerja ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from virmolab.core import air_termo

# Mock PDB dengan 2 molekul air:
# Water 1 (HOH 101): dekat dengan 2 atom O/N (Stabil)
# Water 2 (HOH 102): dikelilingi atom C (Tidak Stabil / Frustrated)
PDB_AIR_MOCK = """ATOM      1  N   ASP A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  OD1 ASP A   1       2.500   0.000   0.000  1.00 20.00           O
ATOM      3  CB  LEU A   2      10.000   0.000   0.000  1.00 20.00           C
ATOM      4  CG  LEU A   2      12.000   0.000   0.000  1.00 20.00           C
ATOM      5  CD1 LEU A   2      11.000   2.000   0.000  1.00 20.00           C
ATOM      6  CD2 LEU A   2      11.000  -2.000   0.000  1.00 20.00           C
HETATM    7  O   HOH A 101       1.200   0.000   1.500  1.00 20.00           O
HETATM    8  O   HOH A 102      11.000   0.000   1.200  1.00 20.00           O
END
"""


def run_tests():
    print("=== Menguji Modul Analisis Termodinamika Air ===")
    gagal = 0

    res = air_termo.analisis_termodinamika_air(PDB_AIR_MOCK)
    if len(res) == 2:
        w_frust = [w for w in res if "Tidak Stabil" in w["kategori"]]
        w_stab = [w for w in res if "Stabil" in w["kategori"]]
        if w_frust and w_stab:
            print(f"OK   analisis_termodinamika_air berhasil mengklasifikasikan air stabil vs tidak stabil")
            print(f"     Air Stabil: {w_stab[0]['id']} (skor gusur {w_stab[0]['skor_gusur']})")
            print(f"     Air Tidak Stabil: {w_frust[0]['id']} (skor gusur {w_frust[0]['skor_gusur']}, rekomendasi: {w_frust[0]['rekomendasi'][:35]}...)")
        else:
            print(f"FAIL klasifikasi kategori air tidak lengkap: {[w['kategori'] for w in res]}")
            gagal += 1
    else:
        print(f"FAIL jumlah air tidak sesuai: {len(res)}")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(run_tests())
