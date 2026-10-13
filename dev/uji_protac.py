"""Uji mandiri modul perancang molekul PROTAC."""
import sys
from pathlib import Path

# Pastikan import dari root proyek
sys.path.insert(0, str(Path(__file__).parent.parent))

from virmolab.core import protac


def uji_protac():
    gagal = 0
    # Contoh warhead: JQ1 inhibitor BRD4 (atau molekul sederhana teraktivasi)
    warhead_smi = "Cc1c(sc2c1-c1ccc(Cl)cc1C(=NC2)C)C"
    
    hasil = protac.rakit_protac(warhead_smi, kunci_e3="CRBN_Pomalidomide", kunci_linker="PEG3")
    print("=== Uji Perakitan PROTAC ===")
    print(f"OK   SMILES PROTAC terbuat: {hasil['smiles'][:60]}...")
    print(f"OK   MW={hasil['mw']} Da, LogP={hasil['logp']}, TPSA={hasil['tpsa']} A^2")
    print(f"OK   Panjang Linker={hasil['panjang_linker_est']} A, Rotatable={hasil['n_rot']}")
    print(f"OK   Status bRo5: {hasil['evaluasi_bro5']}")
    
    if hasil["mw"] <= 400 or not hasil["smiles"]:
        print("FAIL Hasil perakitan PROTAC tidak valid")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(uji_protac())
