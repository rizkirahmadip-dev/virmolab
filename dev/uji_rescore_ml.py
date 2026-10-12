"""Uji mandiri modul re-scoring machine learning kontak atom."""
import sys
from pathlib import Path

# Pastikan import dari root proyek
sys.path.insert(0, str(Path(__file__).parent.parent))

from virmodock.core import rescore_ml


def uji_rescore_ml():
    gagal = 0
    pdb_path = Path(__file__).parent.parent / "virmodock" / "aset" / "contoh" / "1HSG.pdb"
    if not pdb_path.exists():
        print("FAIL 1HSG.pdb tidak ditemukan")
        return 1

    # Buat file sementara protein dan ligan MK1
    tmp_dir = Path(__file__).parent / "tmp_test"
    tmp_dir.mkdir(exist_ok=True)
    rec_file = tmp_dir / "rec_test.pdb"
    lig_file = tmp_dir / "lig_test.pdb"

    with open(pdb_path, "r") as f:
        lines = f.readlines()

    rec_lines = [l for l in lines if l.startswith("ATOM  ")]
    lig_lines = [l for l in lines if l.startswith("HETATM") and "MK1" in l]

    rec_file.write_text("".join(rec_lines), encoding="utf-8")
    lig_file.write_text("".join(lig_lines), encoding="utf-8")

    hasil = rescore_ml.hitung_rescore_ml(str(rec_file), str(lig_file), energi_vina=-11.18)

    print("=== Uji Re-scoring Machine Learning (RF-Score) ===")
    print(f"OK   pKd Terprediksi: {hasil['pKd']}")
    print(f"OK   dG_ML: {hasil['dG_ml']} kcal/mol (Vina: {hasil['dG_vina']} kcal/mol)")
    print(f"OK   Total Kontak Atomik Intermolekuler (<4.0 A): {hasil['total_kontak']}")
    print(f"OK   Evaluasi: {hasil['evaluasi']}")
    print(f"OK   Peringatan False Positive: {hasil['peringatan_false_positive']}")

    if hasil["total_kontak"] <= 0 or hasil["pKd"] <= 0:
        print("FAIL Hasil rescoring tidak valid")
        gagal += 1

    # Bersihkan file sementara
    try:
        rec_file.unlink()
        lig_file.unlink()
        tmp_dir.rmdir()
    except Exception:
        pass

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(uji_rescore_ml())
