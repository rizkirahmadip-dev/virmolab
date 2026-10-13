"""Uji mandiri modul deteksi terowongan dan saluran akses ligan."""
import sys
from pathlib import Path

# Pastikan import dari root proyek
sys.path.insert(0, str(Path(__file__).parent.parent))

from virmolab.core import terowongan


def uji_deteksi_terowongan():
    gagal = 0
    pdb_path = Path(__file__).parent.parent / "virmolab" / "aset" / "contoh" / "1HSG.pdb"
    if not pdb_path.exists():
        print("FAIL 1HSG.pdb tidak ditemukan")
        return 1

    # Uji cari terowongan dari pusat aktif protease HIV-1 (~ 16, 25, 4)
    titik_pusat = (13.1, 22.5, 5.6)
    hasil = terowongan.cari_terowongan(str(pdb_path), titik_awal=titik_pusat, radius_probe=0.8)

    if not hasil:
        print("FAIL Tidak ada terowongan yang terdeteksi")
        gagal += 1
    else:
        top = hasil[0]
        print(f"OK   cari_terowongan mendeteksi {len(hasil)} jalur akses lorong pelarut")
        print(f"     Terowongan Utama #{top['id']}: Panjang={top['panjang']} A, Bottleneck={top['bottleneck_radius']} A")
        print(f"     Gatekeeper: {top['gatekeeper']}")
        print(f"     Residu dinding ({len(top['residu_dinding'])} residu): {top['residu_dinding'][:5]}...")
        if top['bottleneck_radius'] <= 0 or top['panjang'] <= 0:
            print("FAIL Metrik terowongan tidak valid")
            gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(uji_deteksi_terowongan())
