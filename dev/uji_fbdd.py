"""Pengujian mandiri Fragment-Based Drug Design (FBDD)."""
import os
import sys

# Tambahkan direktori kerja ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from virmolab.core import fbdd


def run_tests():
    print("=== Menguji Modul Fragment-Based Drug Design (FBDD) ===")
    gagal = 0

    # Uji 1: tumbuhkan_fragmen (Growing fenol)
    frag_smi = "c1ccccc1O"
    turunan_g = fbdd.tumbuhkan_fragmen(frag_smi, nama_awal="Fenol", maks_hasil=15)
    if len(turunan_g) >= 5 and turunan_g[0]["nama"].startswith("Fenol"):
        print(f"OK   tumbuhkan_fragmen berhasil menghasilkan {len(turunan_g)} analog turunan")
        print(f"     Contoh: {turunan_g[1]['nama']} ({turunan_g[1]['modifikasi']}): {turunan_g[1]['smiles']}, QED={turunan_g[1]['qed']}")
    else:
        print("FAIL tumbuhkan_fragmen gagal")
        gagal += 1

    # Uji 2: sambung_fragmen (Linking benzene + pyridine)
    smi_a = "c1ccccc1"
    smi_b = "c1ccncc1"
    turunan_l = fbdd.sambung_fragmen(smi_a, smi_b, maks_hasil=10)
    if len(turunan_l) >= 3:
        print(f"OK   sambung_fragmen berhasil menghasilkan {len(turunan_l)} molekul hibrida")
        print(f"     Contoh: {turunan_l[0]['nama']} ({turunan_l[0]['modifikasi']}): {turunan_l[0]['smiles']}")
    else:
        print("FAIL sambung_fragmen gagal")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(run_tests())
