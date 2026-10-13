#!/usr/bin/env python3
"""Alat pengembang: bangun panel target penargetan balik dari struktur RCSB sungguhan (dapat dilanjutkan).

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/susun_panel.py bangun <kelas> [--kerja N] [--cpu N] [--umpan N]
  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/susun_panel.py rangkum <kelas>

Masukan : dev/panel_kandidat/<kelas>.csv  (pdb, rantai, ligan, gen, uniprot, alasan) — tanpa angka hasil.
Keluaran: virmolab/data/panel_target/<kelas>.json + <kelas>/<PDB>.pdbqt, dev/panel_kandidat/log_<kelas>.jsonl.
Semua angka (resolusi, tanggal, RMSD redocking, pusat/ukuran kotak, z_rata, z_sd) dihitung atau diambil dari API di sini.
Satu target = satu langkah yang disimpan; menjalankan ulang melewati target yang sudah selesai (di log).
"""
import csv
import gzip
import hashlib
import json
import random
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from virmolab.core import analisis, mesin, prep_ligan, prep_reseptor  # noqa: E402

DIR_KAND = AKAR / "dev" / "panel_kandidat"
DIR_PANEL = AKAR / "virmolab" / "data" / "panel_target"
CACHE_PDB = DIR_KAND / "pdb"
UMPAN_TSV = DIR_KAND / "umpan.tsv"
SEED_UMPAN = 20261013
EXH, N_MODES, SEED_DOCK = 8, 9, 42
RMSD_MAKS, RES_MAKS = 2.0, 2.5
KOFAKTOR = {"HEM", "COH", "NAD", "NAP", "NDP", "FAD", "FMN", "SAM", "ATP", "ADP", "GSH", "UD1", "ORO"}
NOWIN = 0x08000000


def log(kelas, **kv):
    kv["waktu"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(DIR_KAND / f"log_{kelas}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(kv, ensure_ascii=False) + "\n")
    print(json.dumps(kv, ensure_ascii=False), flush=True)


def selesai(kelas):
    p = DIR_KAND / f"log_{kelas}.jsonl"
    hasil = {}
    if p.exists():
        for b in p.read_text(encoding="utf-8").splitlines():
            d = json.loads(b)
            if d.get("langkah") in ("selesai", "ditolak"):
                hasil[d["pdb"]] = d
    return hasil


def http(url, data=None, timeout=90):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "VirmoLab-dev/1.0", "Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def meta_rcsb(pdb):
    q = """query($i:String!){entry(entry_id:$i){rcsb_id rcsb_entry_info{resolution_combined}
      rcsb_accession_info{initial_release_date}
      polymer_entities{rcsb_polymer_entity_container_identifiers{auth_asym_ids uniprot_ids}
        rcsb_entity_source_organism{ncbi_scientific_name}}}}"""
    d = json.loads(http("https://data.rcsb.org/graphql", json.dumps({"query": q, "variables": {"i": pdb}}).encode()))["data"]["entry"]
    return d


def unduh_pdb(pdb):
    CACHE_PDB.mkdir(parents=True, exist_ok=True)
    p = CACHE_PDB / f"{pdb}.pdb"
    if not p.exists():
        p.write_bytes(http(f"https://files.rcsb.org/download/{pdb}.pdb"))
    return p.read_text(encoding="utf-8", errors="replace")


def saring_rantai(teks, rantai):
    """ATOM + HETATM rantai terpilih (altloc A/blank); ligan kristal dipilih dari sini."""
    out = []
    for b in teks.splitlines():
        if b.startswith(("ATOM", "HETATM")) and b[21:22] == rantai and b[16:17] in (" ", "A"):
            out.append(b)
    return "\n".join(out) + "\nEND\n"


def ligan_nama(teks, resn, rantai):
    baris = [b for b in teks.splitlines() if b.startswith("HETATM") and b[17:20].strip() == resn and b[21:22] == rantai
             and b[76:78].strip().upper() != "H"]
    return baris


def vina(rec_txt, lig_txt, kotak, cpu, tmp):
    """Satu docking Vina; kembalikan (energi, pose_pdbqt) dari pose terbaik atau galat."""
    tmp = Path(tmp)
    (tmp / "r.pdbqt").write_text(rec_txt, encoding="utf-8")
    (tmp / "l.pdbqt").write_text(lig_txt, encoding="utf-8")
    prm = mesin.Parameter(mesin="vina", exhaustiveness=EXH, num_modes=N_MODES, seed=SEED_DOCK, cpu=cpu)
    cmd = mesin.perintah_vina(tmp / "r.pdbqt", tmp / "l.pdbqt", tmp / "o.pdbqt", kotak, prm)
    p = subprocess.run(cmd, capture_output=True, timeout=900, creationflags=NOWIN)
    o = tmp / "o.pdbqt"
    if not o.exists() or o.stat().st_size == 0:
        raise RuntimeError((p.stdout + p.stderr).decode("utf-8", "replace")[-200:])
    poses = mesin.baca_hasil("vina", o)
    if not poses:
        raise RuntimeError("tanpa pose")
    t = poses[0]
    return float(t.energi if hasattr(t, "energi") else t["energi"]), (t.pdbqt if hasattr(t, "pdbqt") else t["pdbqt"])


def siapkan_umpan(n):
    """n molekul obat disetujui (ChEMBL, snapshot paket) berukuran mirip ligan panel, dipilih acak dengan seed tercatat."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    if UMPAN_TSV.exists():
        baris = [l.split("\t") for l in UMPAN_TSV.read_text(encoding="utf-8").splitlines()]
        if len(baris) == n:
            return [{"chembl": b[0], "nama": b[1], "smiles": b[2]} for b in baris]
    kand = []
    with gzip.open(AKAR / "virmolab" / "aset" / "obat_disetujui.tsv.gz", "rt", encoding="utf-8") as f:
        for r in csv.DictReader((l for l in f if not l.startswith("#")), delimiter="\t"):
            m = Chem.MolFromSmiles(r["smiles"])
            if m is None or len(Chem.GetMolFrags(m)) > 1:
                continue
            if 15 <= m.GetNumHeavyAtoms() <= 35 and rdMolDescriptors.CalcNumRotatableBonds(m) <= 8 and Descriptors.MolWt(m) <= 500 \
                    and all(a.GetSymbol() in {"C", "N", "O", "S", "F", "Cl", "Br", "P", "I"} for a in m.GetAtoms()):
                kand.append(r)
    kand.sort(key=lambda r: r["chembl"])
    random.Random(SEED_UMPAN).shuffle(kand)
    pilih = kand[:n]
    UMPAN_TSV.write_text("\n".join(f"{r['chembl']}\t{r['nama']}\t{r['smiles']}" for r in pilih) + "\n", encoding="utf-8")
    return [{"chembl": r["chembl"], "nama": r["nama"], "smiles": r["smiles"]} for r in pilih]


def pdbqt_umpan(u):
    d = DIR_KAND / "umpan_pdbqt"
    d.mkdir(exist_ok=True)
    p = d / f"{u['chembl']}.pdbqt"
    if p.exists():
        return p.read_text(encoding="utf-8")
    h = prep_ligan.siapkan_satu(u["chembl"], u["smiles"], "smiles", prep_ligan.OpsiLigan(protonasi=True, minimisasi=True))
    if h.status == "gagal" or not h.pdbqt:
        return None
    p.write_text(h.pdbqt, encoding="utf-8")
    return h.pdbqt


def kerjakan_target(kelas, k, umpan, cpu, n_kerja_umpan):
    pdb, rantai, resn = k["pdb"].upper(), k["rantai"], k["ligan"]
    t0 = time.time()

    def tolak(alasan, **kv):
        log(kelas, pdb=pdb, langkah="ditolak", alasan=alasan, **kv)

    m = meta_rcsb(pdb)
    res = (m["rcsb_entry_info"]["resolution_combined"] or [None])[0]
    tgl = m["rcsb_accession_info"]["initial_release_date"][:10]
    unip, org = set(), set()
    for e in m["polymer_entities"]:
        ci = e["rcsb_polymer_entity_container_identifiers"]
        if rantai in (ci["auth_asym_ids"] or []):
            unip |= set(ci["uniprot_ids"] or [])
            org |= {o["ncbi_scientific_name"] for o in (e["rcsb_entity_source_organism"] or [])}
    log(kelas, pdb=pdb, langkah="meta", resolusi=res, uniprot_pdb=sorted(unip), organisme=sorted(org), rilis=tgl)
    if res is None or res > RES_MAKS:
        return tolak(f"resolusi {res} Å > {RES_MAKS} Å")
    if k["uniprot"] not in unip:
        return tolak(f"UniProt rantai {rantai} = {sorted(unip)}, kandidat menyebut {k['uniprot']}")

    teks = unduh_pdb(pdb)
    rantai_txt = saring_rantai(teks, rantai)
    lig_baris = ligan_nama(rantai_txt, resn, rantai)
    if not lig_baris:
        return tolak(f"ligan {resn} tidak ada di rantai {rantai}")
    # satu salinan residu (nomor residu pertama)
    nores = lig_baris[0][22:27]
    lig_baris = [b for b in lig_baris if b[22:27] == nores]
    pdb_lig = "\n".join(lig_baris) + "\nEND\n"
    mol_ref = analisis.mol_kristal(pdb_lig)
    if mol_ref is None:
        return tolak("ligan kristal tidak terbaca RDKit")
    pos = mol_ref.GetConformer().GetPositions()
    pusat = pos.mean(0)
    ukuran = np.maximum(20.0, (pos.max(0) - pos.min(0)) + 12.0)
    kotak = mesin.Kotak(pusat=[round(float(x), 3) for x in pusat], ukuran=[round(float(x), 1) for x in ukuran])

    # reseptor = protein + ion logam dekat kantong (praktik baku aplikasi); ligan kristal dan semua HET lain dibuang.
    # Kofaktor (NAD, heme, ...) TIDAK disertakan: Meeko tidak punya templatnya. Target yang bergantung pada kofaktor
    # akan gagal redocking dan ditolak apa adanya.
    tanpa_lig = "\n".join(b for b in rantai_txt.splitlines() if b[17:20].strip() != resn)
    opsi = prep_reseptor.OpsiReseptor(rantai=[rantai], protonasi="templat", kofaktor=False, hapus_ligan=True)
    h_rec = prep_reseptor.siapkan(tanpa_lig, opsi)
    if not h_rec.pdbqt:
        return tolak("preparasi reseptor tanpa PDBQT")
    n_atom = prep_reseptor.hitung_atom(h_rec.pdbqt)
    h_lig = prep_ligan.siapkan_satu("kristal", pdb_lig, "pdb", prep_ligan.OpsiLigan(protonasi=False, minimisasi=False))
    if h_lig.status == "gagal":
        return tolak(f"preparasi ligan kristal gagal: {h_lig.alasan}")

    with tempfile.TemporaryDirectory(prefix="vmd_panel_") as tmp:
        try:
            en, pose = vina(h_rec.pdbqt, h_lig.pdbqt, kotak, cpu, tmp)
            rmsd = float(analisis.rmsd_simetri(analisis.pose_mol(h_lig.pdbqt, pose), mol_ref))
        except Exception as e:
            return tolak(f"redocking gagal: {str(e)[:160]}")
    log(kelas, pdb=pdb, langkah="redocking", rmsd=round(rmsd, 3), energi=en, atom_reseptor=n_atom, kotak=[kotak.pusat, kotak.ukuran])
    if rmsd > RMSD_MAKS:
        return tolak(f"RMSD redocking {rmsd:.2f} Å > {RMSD_MAKS} Å", rmsd=round(rmsd, 3))

    # umpan: energi pose terbaik tiap umpan pada reseptor ini, parameter sama dengan docking pengguna
    def satu(u):
        lp = pdbqt_umpan(u)
        if lp is None:
            return None
        with tempfile.TemporaryDirectory(prefix="vmd_umpan_") as tmp:
            try:
                return vina(h_rec.pdbqt, lp, kotak, max(1, cpu // n_kerja_umpan), tmp)[0]
            except Exception:
                return None
    with ThreadPoolExecutor(n_kerja_umpan) as ex:
        energi = [e for e in ex.map(satu, umpan)]
    ok = [e for e in energi if e is not None]
    log(kelas, pdb=pdb, langkah="umpan", n_ok=len(ok), n_gagal=len(energi) - len(ok))
    if len(ok) < 30:
        return tolak(f"umpan berhasil hanya {len(ok)} (< 30)")
    z_rata, z_sd = float(np.mean(ok)), float(np.std(ok, ddof=1))

    out = DIR_PANEL / kelas
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{pdb}.pdbqt").write_text(h_rec.pdbqt, encoding="utf-8")
    entri = {"pdb": pdb, "uniprot": k["uniprot"], "gen": k["gen"], "nama": k.get("nama", ""), "rantai": rantai,
             "ligan_kristal": resn, "organisme": sorted(org), "resolusi": res, "tanggal_rilis": tgl,
             "pusat": kotak.pusat, "ukuran": kotak.ukuran, "rmsd_redocking": round(rmsd, 2),
             "z_rata": round(z_rata, 3), "z_sd": round(z_sd, 3), "n_umpan": len(ok),
             "kofaktor_disertakan": False, "alasan": k["alasan"],
             "parameter_docking": {"mesin": "vina", "exhaustiveness": EXH, "num_modes": N_MODES, "seed": SEED_DOCK}}
    log(kelas, pdb=pdb, langkah="selesai", detik=round(time.time() - t0), entri=entri)


def bangun(kelas, kerja, cpu, n_umpan, kerja_umpan):
    kand = list(csv.DictReader(open(DIR_KAND / f"{kelas}.csv", encoding="utf-8")))
    umpan = siapkan_umpan(n_umpan)
    sudah = selesai(kelas)
    log(kelas, langkah="mulai", n_kandidat=len(kand), n_sudah=len(sudah), n_umpan=len(umpan), seed_umpan=SEED_UMPAN,
        hash_umpan=hashlib.sha1(UMPAN_TSV.read_bytes()).hexdigest()[:10])
    sisa = [k for k in kand if k["pdb"].upper() not in sudah]
    with ThreadPoolExecutor(kerja) as ex:
        for f in [ex.submit(kerjakan_target, kelas, k, umpan, cpu, kerja_umpan) for k in sisa]:
            f.result()
    rangkum(kelas)


def rangkum(kelas):
    """Tulis <kelas>.json dari log (hanya entri 'selesai')."""
    s = selesai(kelas)
    panel = [d["entri"] for d in s.values() if d["langkah"] == "selesai"]
    panel.sort(key=lambda e: e["gen"])
    DIR_PANEL.mkdir(parents=True, exist_ok=True)
    (DIR_PANEL / f"{kelas}.json").write_text(json.dumps(panel, indent=2, ensure_ascii=False), encoding="utf-8")
    for d in s.values():
        if d["langkah"] == "ditolak":
            print(f"DITOLAK {d['pdb']}: {d['alasan']}")
    print(f"{kelas}: {len(panel)} lolos, {sum(1 for d in s.values() if d['langkah'] == 'ditolak')} ditolak")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("bangun", "rangkum"):
        sys.exit(__doc__)
    opt = {a[i]: a[i + 1] for i in range(2, len(a) - 1, 2)}
    if a[0] == "bangun":
        bangun(a[1], int(opt.get("--kerja", 2)), int(opt.get("--cpu", 8)), int(opt.get("--umpan", 50)), int(opt.get("--kerja-umpan", 4)))
    else:
        rangkum(a[1])
