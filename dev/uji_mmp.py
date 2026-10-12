"""Pengujian mandiri Molecular Matched Pair (MMP) Analysis (Fitur 2)."""
import os
import sys

# Tambahkan direktori kerja ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from virmodock.core import mmp


def run_tests():
    print("=== Menguji Modul Molecular Matched Pair (MMP) ===")
    gagal = 0

    # Molekul analog deret (Benzene core dengan substitusi berbeda)
    # L1: Toluena (C)
    # L2: Fenol (OH)
    # L3: Klorobenzena (Cl)
    # L4: Asam benzoat (C(=O)O)
    ligan_uji = [
        ("Toluena", "Cc1ccccc1"),
        ("Fenol", "Oc1ccccc1"),
        ("Klorobenzena", "Clc1ccccc1"),
        ("Asam_Benzoat", "O=C(O)c1ccccc1"),
    ]

    data_docking = {
        "Toluena": {"energi": -5.2, "qed": 0.45, "sascore": 1.2},
        "Fenol": {"energi": -6.8, "qed": 0.62, "sascore": 1.5},
        "Klorobenzena": {"energi": -5.5, "qed": 0.50, "sascore": 1.4},
        "Asam_Benzoat": {"energi": -7.1, "qed": 0.70, "sascore": 1.8},
    }

    # Uji 1: cari_pasangan
    pasangan = mmp.cari_pasangan(ligan_uji)
    if len(pasangan) >= 3:
        print(f"OK   cari_pasangan berhasil mendeteksi {len(pasangan)} pasangan MMP berinti sama")
    else:
        print(f"FAIL cari_pasangan hanya menemukan {len(pasangan)} pasangan")
        gagal += 1

    # Uji 2: tabel_rgroup
    tabel = mmp.tabel_rgroup(pasangan, data_docking)
    if len(tabel) == len(pasangan) and all("ddg" in row for row in tabel):
        print(f"OK   tabel_rgroup berhasil menghitung ddG (pasangan terbesar: {tabel[0]['id_a']} vs {tabel[0]['id_b']}, |ddG|={tabel[0]['abs_ddg']})")
    else:
        print("FAIL tabel_rgroup gagal menyusun data")
        gagal += 1

    # Uji 3: sar_cliff
    # Pasangan Toluena (-5.2) vs Fenol (-6.8) memiliki |ddG| = 1.6 kcal/mol
    cliffs = mmp.sar_cliff(tabel, ambang_ddg=1.4, ambang_sim=0.35)
    if len(cliffs) >= 1:
        print(f"OK   sar_cliff berhasil mendeteksi {len(cliffs)} Activity Cliff (top: {cliffs[0]['id_a']} vs {cliffs[0]['id_b']})")
    else:
        print(f"FAIL sar_cliff tidak mendeteksi cliff yang diharapkan")
        gagal += 1

    # Uji 4: saran_modifikasi
    saran = mmp.saran_modifikasi(tabel)
    if len(saran) >= 1:
        trans_teks = saran[0]['transformasi'].replace("\u2192", "->")
        print(f"OK   saran_modifikasi menemukan substitusi penguat: {trans_teks} (rerata ddG {saran[0]['rata_rata_ddg']} kcal/mol)")
    else:
        print("FAIL saran_modifikasi tidak menghasilkan rekomendasi")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(run_tests())
