"""Pengujian mandiri Matriks Selektivitas Multi-Target (Fitur 3)."""
import os
import sys

# Tambahkan direktori kerja ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from virmodock.core import selektivitas


class MockProyek:
    def __init__(self, nama, reseptor_nama, data_hasil):
        self.nama = nama
        self.reseptor = {"nama": reseptor_nama}
        self.ligan = [{"id": str(i), "nama": b["ligan"], "smiles": b.get("smiles", "")} for i, b in enumerate(data_hasil)]
        self.job = [
            {
                "id": "job_1",
                "mesin": "vina",
                "ligan": [
                    {
                        "id": str(i),
                        "nama": b["ligan"],
                        "status": "selesai",
                        "energi": b["energi"],
                        "pose": [{"peringkat": 1, "energi": b["energi"]}],
                    }
                    for i, b in enumerate(data_hasil)
                ],
            }
        ]

    def cari_ligan(self, lid):
        for l in self.ligan:
            if l["id"] == lid:
                return l
        return None


def run_tests():
    print("=== Menguji Modul Selektivitas Multi-Target ===")
    gagal = 0

    # Dua target: Target_A (misal COX-1) dan Target_B (misal COX-2)
    # L1 (Celecoxib-like): selektif COX-2
    # L2 (Aspirin-like): non-selektif / promiskuitas
    # L3 (Indomethacin-like): selektif COX-1
    data_target1 = [
        {"ligan": "Senyawa_1", "smiles": "CC1=CC=CC=C1O", "energi": -6.0},
        {"ligan": "Senyawa_2", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "energi": -6.5},
        {"ligan": "Senyawa_3", "smiles": "ClC1=CC=CC=C1", "energi": -8.8},
    ]

    data_target2 = [
        {"ligan": "Senyawa_1", "smiles": "CC1=CC=CC=C1O", "energi": -8.4},
        {"ligan": "Senyawa_2", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "energi": -6.6},
        {"ligan": "Senyawa_3", "smiles": "ClC1=CC=CC=C1", "energi": -6.9},
    ]

    pr1 = MockProyek("Proyek_COX1", "COX-1", data_target1)
    pr2 = MockProyek("Proyek_COX2", "COX-2", data_target2)

    proyek_list = [("COX-1", pr1), ("COX-2", pr2)]

    # Uji 1: matriks_selektivitas
    label_ligan, label_target, mat, _ = selektivitas.matriks_selektivitas(proyek_list, variabel="energi")
    if len(label_ligan) == 3 and len(label_target) == 2 and len(mat) == 3:
        print(f"OK   matriks_selektivitas menghasilkan matriks {len(mat)}x{len(mat[0])}")
    else:
        print(f"FAIL matriks_selektivitas gagal: ligan={len(label_ligan)}, target={len(label_target)}")
        gagal += 1

    # Uji 2: zscore_normalisasi
    mat_z = selektivitas.zscore_normalisasi(mat)
    if len(mat_z) == 3 and len(mat_z[0]) == 2:
        print(f"OK   zscore_normalisasi berhasil (contoh Z: {mat_z[0]})")
    else:
        print("FAIL zscore_normalisasi gagal")
        gagal += 1

    # Uji 3: klasifikasi_selektivitas
    klas = selektivitas.klasifikasi_selektivitas(mat, label_target, ambang_ddg=1.5)
    # Senyawa_1: COX-1 = -6.0, COX-2 = -8.4 -> Gap = 2.4 kcal/mol -> Selektif COX-2
    # Senyawa_2: COX-1 = -6.5, COX-2 = -6.6 -> Gap = 0.1 kcal/mol -> Promiskuitas
    # Senyawa_3: COX-1 = -8.8, COX-2 = -6.9 -> Gap = 1.9 kcal/mol -> Selektif COX-1
    cek_s1 = any("Selektif (COX-2)" in k["kelas"] for k in klas)
    cek_s2 = any(k["kelas"] == "Promiskuitas" for k in klas)
    cek_s3 = any("Selektif (COX-1)" in k["kelas"] for k in klas)

    if cek_s1 and cek_s2 and cek_s3:
        print("OK   klasifikasi_selektivitas berhasil mendeteksi Selektif & Promiskuitas dengan tepat")
    else:
        print(f"FAIL klasifikasi_selektivitas tidak sesuai: {[k['kelas'] for k in klas]}")
        gagal += 1

    # Uji 4: indeks_selektivitas
    idx_sel = selektivitas.indeks_selektivitas(mat, target_utama_idx=1, target_pembanding_idx=0)
    # Target utama = COX-2, pembanding = COX-1: ddG = dG(COX-1) - dG(COX-2)
    # Senyawa_1: -6.0 - (-8.4) = +2.4 (positif = selektif COX-2)
    if idx_sel[0] == 2.4:
        print(f"OK   indeks_selektivitas berhasil dihitung (ddG = {idx_sel[0]} kcal/mol)")
    else:
        print(f"FAIL indeks_selektivitas gagal: {idx_sel}")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(run_tests())
