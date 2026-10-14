"""Buat fixture SINTETIS keluaran Boltz-2 untuk 1HSG + MK1 di dev/data/boltz_1hsg.

PENTING: berkas ini BUKAN hasil menjalankan Boltz-2. Angka afinitas dan keyakinan di bawah
ditulis tangan; yang diuji dengan fixture ini hanyalah pembacaan berkas, penyelarasan Kabsch,
dan pelabelan kesepakatan, BUKAN ketepatan prediksi Boltz-2. Nama kunci JSON mengikuti skema
yang terdokumentasi dan belum dicocokkan dengan keluaran nyata (Boltz belum terpasang di WSL
pada mesin ini). Setelah Boltz terpasang, jalankan sekali dengan data sungguhan dan bandingkan
nama kuncinya; `baca_keluaran_boltz` mencatat peringatan bila kuncinya tidak cocok.

Struktur folder dan skema JSON yang ditiru:
  - dev/data/boltz_1hsg/predictions/boltz_1hsg/boltz_1hsg_model_0.pdb
  - dev/data/boltz_1hsg/predictions/boltz_1hsg/affinity_boltz_1hsg.json
  - dev/data/boltz_1hsg/predictions/boltz_1hsg/confidence_boltz_1hsg_model_0.json

Struktur kompleks PDB memuat rantai A, B, dan rantai ligan L (MK1) yang diputar/ditranslasi
secara rigid agar algoritma penyelarasan Kabsch Cα benar-benar diuji.
"""
import json
import math
from pathlib import Path
import numpy as np

AKAR = Path(__file__).resolve().parents[1]
FOLDER_KELUAR = AKAR / "dev" / "data" / "boltz_1hsg" / "predictions" / "boltz_1hsg"
PDB_SUMBER = AKAR / "virmolab" / "aset" / "contoh" / "1HSG.pdb"

def main():
    FOLDER_KELUAR.mkdir(parents=True, exist_ok=True)
    
    # 1. Tulis affinity_boltz_1hsg.json
    afinitas = {
        "affinity_pred_value": -2.145,
        "affinity_probability_binary": 0.9852,
        "affinity_pred_value1": -2.2104,
        "affinity_probability_binary1": 0.9912,
        "affinity_pred_value2": -2.0796,
        "affinity_probability_binary2": 0.9792
    }
    (FOLDER_KELUAR / "affinity_boltz_1hsg.json").write_text(json.dumps(afinitas, indent=2), encoding="utf-8")

    # 2. Tulis confidence_boltz_1hsg_model_0.json
    keyakinan = {
        "confidence_score": 0.892,
        "ptm": 0.924,
        "iptm": 0.865,
        "ligand_iptm": 0.851,
        "complex_plddt": 88.42
    }
    (FOLDER_KELUAR / "confidence_boltz_1hsg_model_0.json").write_text(json.dumps(keyakinan, indent=2), encoding="utf-8")

    # 3. Buat PDB kompleks model_0 dari 1HSG.pdb dengan transformasi rigid
    # Rotasi 35 derajat sumbu Z + translasi (12.0, -8.0, 15.0)
    sudut = math.radians(35)
    cos_s, sin_s = math.cos(sudut), math.sin(sudut)
    R = np.array([
        [cos_s, -sin_s, 0.0],
        [sin_s,  cos_s, 0.0],
        [0.0,    0.0,   1.0]
    ])
    T = np.array([12.0, -8.0, 15.0])

    teks_sumber = PDB_SUMBER.read_text(encoding="utf-8", errors="replace")
    baris_pdb = []
    
    for baris in teks_sumber.splitlines():
        if baris.startswith("ATOM"):
            rantai = baris[21:22]
            if rantai not in ("A", "B"):
                continue
            x = float(baris[30:38])
            y = float(baris[38:46])
            z = float(baris[46:54])
            xyz_baru = R @ np.array([x, y, z]) + T
            baris_baru = f"{baris[:30]}{xyz_baru[0]:8.3f}{xyz_baru[1]:8.3f}{xyz_baru[2]:8.3f}{baris[54:]}"
            baris_pdb.append(baris_baru)
        elif baris.startswith("HETATM"):
            resn = baris[17:20].strip()
            if resn == "MK1":
                x = float(baris[30:38])
                y = float(baris[38:46])
                z = float(baris[46:54])
                xyz_baru = R @ np.array([x, y, z]) + T
                # Di Boltz, ligan biasanya diberi chain L dan residue LIG / MK1
                baris_baru = (f"HETATM{baris[6:17]}MK1 L   1    "
                              f"{xyz_baru[0]:8.3f}{xyz_baru[1]:8.3f}{xyz_baru[2]:8.3f}{baris[54:]}")
                baris_pdb.append(baris_baru)
                
    baris_pdb.append("END")
    pdb_keluar = FOLDER_KELUAR / "boltz_1hsg_model_0.pdb"
    pdb_keluar.write_text("\n".join(baris_pdb) + "\n", encoding="utf-8")
    print(f"Fixture Boltz 1HSG berhasil dibuat di: {FOLDER_KELUAR}")
    print(f"Total baris PDB: {len(baris_pdb)}")

if __name__ == "__main__":
    main()
