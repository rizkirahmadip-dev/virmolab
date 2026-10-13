"""Uji mandiri modul prediksi kinetika pengikatan dan waktu tinggal."""
import sys
from pathlib import Path

# Pastikan import dari root proyek
sys.path.insert(0, str(Path(__file__).parent.parent))

from virmolab.core import kinetika


def uji_kinetika():
    gagal = 0
    
    # 1. Kasus ligan kuat dengan banyak H-bond terkubur (misal MK1 HIV-1 protease, dG ~ -11.0)
    res_kuat = kinetika.estimasi_kinetika(energi_vina=-11.0, jum_hbond_terkubur=4, jum_kontak_hidrofobik=16)
    print("=== Uji Ligan Kuat ===")
    print(f"OK   dG={res_kuat['dG']} kcal/mol, Kd={res_kuat['Kd_nM']} nM")
    print(f"OK   k_off={res_kuat['k_off']} s^-1, Tau={res_kuat['tau_teks']}, t_1/2={res_kuat['t_setengah_teks']}")
    print(f"OK   Kategori: {res_kuat['kategori']}")
    
    if res_kuat["k_off"] <= 0 or res_kuat["tau_detik"] <= 0:
        print("FAIL Nilai k_off atau tau tidak valid")
        gagal += 1
        
    # 2. Kasus ligan lemah (dG ~ -5.5)
    res_lemah = kinetika.estimasi_kinetika(energi_vina=-5.5, jum_hbond_terkubur=0, jum_kontak_hidrofobik=4)
    print("\n=== Uji Ligan Lemah ===")
    print(f"OK   dG={res_lemah['dG']} kcal/mol, Tau={res_lemah['tau_teks']}, Kategori={res_lemah['kategori']}")
    
    if res_lemah["tau_detik"] >= res_kuat["tau_detik"]:
        print("FAIL Waktu tinggal ligan lemah seharusnya lebih kecil dari ligan kuat")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(uji_kinetika())
