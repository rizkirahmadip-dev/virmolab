"""Pengujian mandiri Generator Skrip Publikasi PyMOL & ChimeraX."""
import os
import sys

# Tambahkan direktori kerja ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from virmolab.core import skrip_publikasi


def run_tests():
    print("=== Menguji Modul Generator Skrip Publikasi ===")
    gagal = 0

    p_pml = skrip_publikasi.buat_skrip_pymol("reseptor.pdb", "pose_1.sdf", ["ASP 25", "GLY 27"])
    p_cxc = skrip_publikasi.buat_skrip_chimerax("reseptor.pdb", "pose_1.sdf", ["ASP 25", "GLY 27"])

    if "bg_color white" in p_pml and "ray 2400, 1800" in p_pml and "ASP 25" in p_pml:
        print("OK   buat_skrip_pymol menghasilkan skrip PyMOL lengkap dengan ray-tracing")
    else:
        print("FAIL buat_skrip_pymol gagal")
        gagal += 1

    if "set bgColor white" in p_cxc and "hbonds" in p_cxc:
        print("OK   buat_skrip_chimerax menghasilkan skrip ChimeraX lengkap")
    else:
        print("FAIL buat_skrip_chimerax gagal")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(run_tests())
