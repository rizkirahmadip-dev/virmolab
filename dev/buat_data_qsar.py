#!/usr/bin/env python3
"""Alat pengembang: unduh set data QSAR kecil dari ChEMBL untuk uji (dev/data/qsar_<gen>.csv).

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/buat_data_qsar.py [CHEMBL_ID gen]

Data ChEMBL berlisensi CC BY-SA 3.0 (EMBL-EBI); berkas turunan ini juga CC BY-SA 3.0 — atribusi ada di baris komentar
pertama berkas dan di LISENSI_PIHAK_KETIGA.txt. Hanya aktivitas IC50 dengan pChEMBL dan relasi '=' yang disimpan.
"""
import csv
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from virmolab.core import chembl  # noqa: E402

TARGET = sys.argv[1] if len(sys.argv) > 1 else "CHEMBL220"      # asetilkolinesterase manusia
GEN = sys.argv[2] if len(sys.argv) > 2 else "ache"
MAKS = 2000
N_SIMPAN = 600          # subsampel acak berbenih agar uji cepat dan berkas kecil
KELUAR = AKAR / "dev" / "data" / f"qsar_{GEN}.csv"

baris = chembl.aktivitas(TARGET, jenis=["IC50"], maks=MAKS)
pakai = [b for b in baris if b.get("pchembl") and b.get("relasi") == "=" and b.get("smiles")]
import random
pakai.sort(key=lambda b: b["molekul"])
random.Random(20261013).shuffle(pakai)
pakai = pakai[:N_SIMPAN]
print(f"{len(baris)} aktivitas diambil, {len(pakai)} disimpan (IC50, relasi '=', ada pChEMBL, subsampel berbenih)")

KELUAR.parent.mkdir(parents=True, exist_ok=True)
with open(KELUAR, "w", encoding="utf-8", newline="") as f:
    f.write(f"# Data ChEMBL ({TARGET}, IC50) CC BY-SA 3.0 - EMBL-EBI; kutip Zdrazil dkk. 2024, "
            f"Nucleic Acids Res 52:D1180. Berkas turunan juga CC BY-SA 3.0.\n")
    w = csv.writer(f)
    w.writerow(["smiles", "nama", "nilai", "satuan", "relasi", "pchembl"])
    for b in pakai:
        w.writerow([b["smiles"], b["molekul"], b["nilai"], b["satuan"], b["relasi"], b["pchembl"]])
print("ditulis:", KELUAR, KELUAR.stat().st_size // 1024, "KB")
