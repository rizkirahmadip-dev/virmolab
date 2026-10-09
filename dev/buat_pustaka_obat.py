"""Buat snapshot pustaka 'Obat disetujui' dari ChEMBL (max_phase = 4, molekul kecil) -> virmodock/aset/obat_disetujui.tsv.gz

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/buat_pustaka_obat.py
Data ChEMBL CC BY-SA 3.0 (atribusi di LISENSI_PIHAK_KETIGA.txt). Kolom: chembl, nama, smiles, tahun_setuju, oral,
topikal, parenteral, atc (kode level 1, dipisah koma).
"""
import gzip
import json
import time
import urllib.request
from pathlib import Path

API = "https://www.ebi.ac.uk/chembl/api/data"
KELUAR = Path("virmodock/aset/obat_disetujui.tsv.gz")


def get(url):
    for coba in range(4):
        try:
            r = urllib.request.Request(url, headers={"User-Agent": "VirmoDock/1.0", "Accept": "application/json"})
            return json.loads(urllib.request.urlopen(r, timeout=120).read().decode("utf-8"))
        except Exception as e:
            print("ulang:", e)
            time.sleep(3 * (coba + 1))
    raise RuntimeError(url)


kol = ("molecule_chembl_id,pref_name,molecule_structures,first_approval,oral,topical,parenteral,"
       "atc_classifications,molecule_type,natural_product")
url = (f"{API}/molecule.json?max_phase=4&molecule_type=Small%20molecule&molecule_structures__isnull=false"
       f"&only={kol}&limit=1000")
baris, t0 = [], time.time()
while url:
    d = get(url)
    for m in d["molecules"]:
        s = (m.get("molecule_structures") or {}).get("canonical_smiles")
        if not s:
            continue
        atc = sorted({a[0] for a in (m.get("atc_classifications") or []) if a})
        baris.append([m["molecule_chembl_id"], (m.get("pref_name") or "").replace("\t", " "), s,
                      str(m.get("first_approval") or ""), "1" if m.get("oral") else "",
                      "1" if m.get("topical") else "", "1" if m.get("parenteral") else "", ",".join(atc),
                      "1" if m.get("natural_product") == 1 else ""])
    nxt = d["page_meta"].get("next")
    url = ("https://www.ebi.ac.uk" + nxt) if nxt else None
    print(f"{len(baris)} / {d['page_meta']['total_count']}  {time.time() - t0:.0f} s", flush=True)

# saring: ion/garam kecil, logam, campuran tanpa karbon
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")
from rdkit.Chem.MolStandardize import rdMolStandardize

bersih = []
for b in baris:
    m = Chem.MolFromSmiles(b[2])
    if m is None:
        continue
    m = rdMolStandardize.FragmentParent(m)
    if m.GetNumHeavyAtoms() < 5 or not any(a.GetSymbol() == "C" for a in m.GetAtoms()):
        continue
    b[2] = Chem.MolToSmiles(m)
    bersih.append(b)
kepala = "chembl\tnama\tsmiles\ttahun_setuju\toral\ttopikal\tparenteral\tatc\tbahan_alam"
teks = kepala + "\n" + "\n".join("\t".join(b) for b in bersih) + "\n"
with gzip.open(KELUAR, "wt", encoding="utf-8", compresslevel=9) as f:
    f.write(f"# ChEMBL approved small molecules (max_phase=4), diambil {time.strftime('%Y-%m-%d')}, CC BY-SA 3.0\n")
    f.write(teks)
print(KELUAR, len(bersih), "obat,", KELUAR.stat().st_size // 1024, "KB")
