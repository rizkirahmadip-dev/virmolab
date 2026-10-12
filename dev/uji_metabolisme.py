"""Uji mandiri modul prediksi titik metabolisme."""
import sys
from pathlib import Path

# Pastikan import dari root proyek
sys.path.insert(0, str(Path(__file__).parent.parent))

from virmodock.core import metabolisme


def uji_metabolisme():
    gagal = 0
    # Contoh ligan dengan beberapa titik metabolisme: metoksi, metil benzilik, dan cincin aromatik
    # Anisol dengan rantai metil: 4-metilmetoksibenzena (Cc1ccc(OC)cc1)
    smi = "Cc1ccc(OC)cc1"
    hasil = metabolisme.prediksi_titik_metabolisme(smi)
    
    print("=== Uji Prediksi Titik Metabolisme ===")
    print(f"OK   Ditemukan {hasil['jumlah_som']} titik rawan metabolisme")
    print(f"OK   Skor Stabilitas Metabolik: {hasil['skor_stabilitas']} / 100")
    print(f"OK   Klasifikasi: {hasil['klasifikasi']}")
    for i, s in enumerate(hasil['daftar_som']):
        print(f"     - SoM #{i+1} [Atom {s['simbol']}{s['indeks_atom']}]: {s['tipe_reaksi']} ({s['tingkat_kerentanan']})")
        print(f"       Saran: {s['rekomendasi_bioisosterik']}")

    if hasil["jumlah_som"] == 0 or hasil["skor_stabilitas"] <= 0:
        print("FAIL Deteksi SoM gagal")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(uji_metabolisme())
