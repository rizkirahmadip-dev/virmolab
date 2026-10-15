"""Ambil SMILES Chemical Component Dictionary (CCD, wwPDB) untuk kofaktor umum -> virmolab/data/kofaktor_ccd.json.

SMILES dipakai core/kofaktor.py sebagai templat orde ikatan: koordinat kofaktor dari berkas PDB tidak membawa
orde ikatan, sehingga tipe atom AD4 dan muatan Gasteiger akan keliru tanpa templat. Data CCD bebas dipakai
(wwPDB, CC0). Jalankan ulang bila daftar KOFAKTOR di virmolab/core/molekul.py berubah.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/buat_smiles_kofaktor.py
"""
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from virmolab.core.molekul import KOFAKTOR  # noqa: E402

KELUAR = Path("virmolab/data/kofaktor_ccd.json")
hasil = {"_sumber": "wwPDB Chemical Component Dictionary lewat data.rcsb.org/rest/v1/core/chemcomp (CC0)",
         "_diambil": date.today().isoformat()}
gagal = []
for kode in sorted(KOFAKTOR):
    url = f"https://data.rcsb.org/rest/v1/core/chemcomp/{kode}"
    for coba in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VirmoLab-dev"})
            d = json.loads(urllib.request.urlopen(req, timeout=60).read())
            desk = d.get("rcsb_chem_comp_descriptor") or {}
            smi = desk.get("SMILES_stereo") or desk.get("SMILES")
            if not smi:
                raise ValueError("tanpa SMILES")
            hasil[kode] = {"smiles": smi, "nama": (d.get("chem_comp") or {}).get("name", ""),
                           "rumus": (d.get("chem_comp") or {}).get("formula", "")}
            print(f"{kode}: {hasil[kode]['nama'][:60]}", flush=True)
            break
        except Exception as e:
            if coba == 2:
                gagal.append(f"{kode} ({e})")
            time.sleep(2)
KELUAR.write_text(json.dumps(hasil, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(hasil) - 2} kofaktor ditulis ke {KELUAR}; gagal: {gagal or '-'}")
