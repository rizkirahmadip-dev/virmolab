"""ChEMBL (EMBL-EBI) lewat REST API publik: cari target, ambil aktivitas (pChEMBL), cocokkan dengan hasil docking.

Data ChEMBL berlisensi CC BY-SA 3.0 - kutip: Zdrazil et al. 2024, Nucleic Acids Res 52:D1180 (ChEMBL 2023).
Tidak ada paket tambahan (urllib + RDKit). Semua fungsi jaringan dipanggil dari thread latar (ui.kerja).
"""
import json
import statistics
import urllib.parse
import urllib.request

API = "https://www.ebi.ac.uk/chembl/api/data"
RCSB = "https://data.rcsb.org/rest/v1/core"
JENIS_AKTIVITAS = ["IC50", "Ki", "Kd", "EC50"]
SITASI = ("Zdrazil B, Felix E, Hunter F, et al. The ChEMBL Database in 2023: a drug discovery platform spanning "
          "multiple bioactivity data types and time periods. Nucleic Acids Res. 2024;52(D1):D1180-D1192. "
          "doi:10.1093/nar/gkad1004")


def _json(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "VirmoDock/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


UMUM = {"protein", "chain", "domain", "subunit", "fragment", "type", "alpha", "beta", "isoform", "receptor",
        "kinase", "family", "member", "factor", "putative", "uncharacterized"}


def entitas_pdb(kode):
    """Entitas polimer sebuah ID PDB (RCSB Data API): [{uniprot: [...], nama, taxid}]."""
    kode = kode.strip().upper()[:4]
    ent = _json(f"{RCSB}/entry/{kode}").get("rcsb_entry_container_identifiers", {}).get("polymer_entity_ids", [])
    hasil = []
    for e in ent:
        try:
            d = _json(f"{RCSB}/polymer_entity/{kode}/{e}")
        except Exception:
            continue
        org = d.get("rcsb_entity_source_organism") or [{}]
        hasil.append({"uniprot": d.get("rcsb_polymer_entity_container_identifiers", {}).get("uniprot_ids") or [],
                      "nama": (d.get("rcsb_polymer_entity") or {}).get("pdbx_description") or "",
                      "taxid": org[0].get("ncbi_taxonomy_id")})
    return hasil


def uniprot_dari_pdb(kode):
    """UniProt accession semua entitas polimer sebuah ID PDB."""
    out = []
    for e in entitas_pdb(kode):
        out += [u for u in e["uniprot"] if u not in out]
    return out


def _kata_kunci(nama):
    """Kata paling khas dari nama entitas (mis. 'HIV-1 PROTEASE' -> 'protease')."""
    import re
    kata = [k for k in re.split(r"[^A-Za-z]+", nama.lower()) if len(k) > 3 and k not in UMUM]
    return max(kata, key=len) if kata else ""


def jumlah_aktivitas(target):
    try:
        d = _json(f"{API}/activity.json?target_chembl_id={target}&pchembl_value__isnull=false&limit=1&only="
                  "activity_id", timeout=30)
        return int((d.get("page_meta") or {}).get("total_count") or 0)
    except Exception:
        return None


def cari_target(teks, lapor=None):
    """Cari target ChEMBL dari teks bebas, ID PDB (4 karakter), UniProt, atau CHEMBLxxxx.

    Kembalikan [{chembl, nama, organisme, jenis, uniprot}]."""
    t = teks.strip()
    log = (lambda s: lapor.log.emit(s)) if lapor else (lambda s: None)
    hasil = []
    if t.upper().startswith("CHEMBL"):
        hasil = [_json(f"{API}/target/{t.upper()}.json")]
    else:
        if len(t) == 4 and t[0].isdigit() and t.isalnum():
            log(f"Mencari entitas PDB {t.upper()} (RCSB)…")
            for e in entitas_pdb(t):
                for a in e["uniprot"]:
                    d = _json(f"{API}/target.json?target_components__accession={urllib.parse.quote(a)}&limit=20")
                    hasil += d.get("targets", [])
                # UniProt PDB sering berupa poliprotein (mis. Gag-Pol); target ChEMBL utama ditemukan lewat
                # organisme (taxid) + kata khas nama entitas
                k = _kata_kunci(e["nama"])
                if e["taxid"] and k:
                    hasil += _json(f"{API}/target.json?tax_id={e['taxid']}&pref_name__icontains="
                                   f"{urllib.parse.quote(k)}&limit=20").get("targets", [])
        elif len(t) in (6, 10) and t[0].isalpha() and t[1].isdigit():
            hasil = _json(f"{API}/target.json?target_components__accession={t.upper()}&limit=20").get("targets", [])
        if not hasil:
            hasil = _json(f"{API}/target/search.json?q={urllib.parse.quote(t)}&limit=25").get("targets", [])
    out, sudah = [], set()
    for x in hasil:
        cid = x.get("target_chembl_id")
        if not cid or cid in sudah:
            continue
        sudah.add(cid)
        komp = x.get("target_components") or []
        out.append({"chembl": cid, "nama": x.get("pref_name") or "", "organisme": x.get("organism") or "",
                    "jenis": x.get("target_type") or "",
                    "uniprot": ", ".join(c.get("accession") or "" for c in komp if c.get("accession"))})
    # urutkan menurut jumlah aktivitas ber-pChEMBL (target utama punya data terbanyak)
    log("Menghitung jumlah data aktivitas per target…")
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as ex:
        for r, n in zip(out[:16], ex.map(lambda r: jumlah_aktivitas(r["chembl"]), out[:16])):
            r["aktivitas"] = n
    out.sort(key=lambda r: (-(r.get("aktivitas") or 0), r["jenis"] != "SINGLE PROTEIN", r["nama"]))
    return out


def aktivitas(target, jenis=None, maks=3000, lapor=None):
    """Aktivitas dengan pChEMBL untuk satu target. Kembalikan baris mentah [{molekul, nama, smiles, jenis, nilai,
    satuan, pchembl, assay}] (berhalaman, dibatasi maks)."""
    jenis = jenis or JENIS_AKTIVITAS
    log = (lambda s: lapor.log.emit(s)) if lapor else (lambda s: None)
    kol = ("molecule_chembl_id,molecule_pref_name,canonical_smiles,standard_type,standard_value,standard_units,"
           "pchembl_value,assay_chembl_id,standard_relation")
    url = (f"{API}/activity.json?target_chembl_id={target}&pchembl_value__isnull=false"
           f"&standard_type__in={','.join(jenis)}&only={kol}&limit=1000")
    baris = []
    while url and len(baris) < maks:
        d = _json(url, timeout=90)
        for a in d.get("activities", []):
            if not a.get("canonical_smiles") or a.get("pchembl_value") is None:
                continue
            baris.append({"molekul": a["molecule_chembl_id"], "nama": a.get("molecule_pref_name") or "",
                          "smiles": a["canonical_smiles"], "jenis": a.get("standard_type") or "",
                          "nilai": a.get("standard_value"), "satuan": a.get("standard_units") or "",
                          "relasi": a.get("standard_relation") or "=", "pchembl": float(a["pchembl_value"]),
                          "assay": a.get("assay_chembl_id") or ""})
        nxt = (d.get("page_meta") or {}).get("next")
        url = ("https://www.ebi.ac.uk" + nxt) if nxt else None
        if lapor:
            log(f"ChEMBL: {len(baris)} aktivitas diambil…")
            if hasattr(lapor, "progres"):
                total = (d.get("page_meta") or {}).get("total_count") or 1
                lapor.progres.emit(min(len(baris), min(total, maks)), min(total, maks), "")
    return baris


def ringkas_senyawa(baris):
    """Satukan aktivitas per senyawa: median pChEMBL, jumlah pengukuran, jenis. Urut pChEMBL tertinggi."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    per = {}
    for b in baris:
        per.setdefault(b["molekul"], []).append(b)
    out = []
    for cid, bs in per.items():
        smi = bs[0]["smiles"]
        m = Chem.MolFromSmiles(smi)
        if m is None or m.GetNumHeavyAtoms() < 8 or not any(a.GetSymbol() == "C" for a in m.GetAtoms()):
            continue        # ion/garam/fragmen kecil (mis. MAGNESIUM) bukan ligan
        ik = Chem.MolToInchiKey(m) if m is not None else ""
        p = [x["pchembl"] for x in bs]
        out.append({"chembl": cid, "nama": bs[0]["nama"] or cid, "smiles": smi, "inchikey": ik,
                    "pchembl": round(statistics.median(p), 2), "n": len(p),
                    "sd": round(statistics.stdev(p), 2) if len(p) > 1 else None,
                    "jenis": "/".join(sorted({x["jenis"] for x in bs})),
                    "berat": round(Descriptors.MolWt(m), 1) if m is not None else None})
    out.sort(key=lambda r: -r["pchembl"])
    return out


def kunci_struktur(mol):
    """Blok pertama InChIKey (konektivitas, tanpa stereo/protonasi) untuk mencocokkan lintas sumber."""
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    try:
        m = rdMolStandardize.FragmentParent(mol)
        m = rdMolStandardize.Uncharger().uncharge(m)
        return Chem.MolToInchiKey(m).split("-")[0]
    except Exception:
        return ""


def cocokkan(senyawa, ligan):
    """senyawa: ringkas_senyawa(); ligan: [(nama, mol RDKit, ΔG)]. Kembalikan [(nama, ΔG, pChEMBL, chembl)]."""
    peta = {}
    for s in senyawa:
        if s["inchikey"]:
            peta.setdefault(s["inchikey"].split("-")[0], s)
    hasil = []
    for nama, mol, dg in ligan:
        if mol is None or dg is None:
            continue
        s = peta.get(kunci_struktur(mol))
        if s:
            hasil.append((nama, dg, s["pchembl"], s["chembl"]))
    return hasil


def pchembl_ke_dg(p, suhu=298.15):
    """ΔG eksperimen (kcal/mol) dari pChEMBL (≈ −log10 Ki/IC50 molar): ΔG = −RT ln(10) · p."""
    import math
    return -0.0019872 * suhu * math.log(10) * p
