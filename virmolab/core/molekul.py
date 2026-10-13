"""Objek molekul, impor berkas, dan unduhan RCSB/PubChem.

Sebuah berkas struktur dipecah menjadi beberapa objek (protein, ligan, air,
ion) supaya masing-masing bisa ditampilkan/disembunyikan dan diwarnai
terpisah, seperti di PyMOL atau Discovery Studio.
"""
import itertools
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import gemmi

AIR = {"HOH", "WAT", "H2O", "DOD", "TIP", "TIP3", "SOL"}
ION = {"NA", "CL", "K", "MG", "CA", "ZN", "FE", "FE2", "MN", "CU", "CU1", "CO", "NI", "CD", "HG", "SR", "BA", "CS",
       "IOD", "BR", "LI", "RB", "AL", "PT", "AU", "AG", "PB", "SO4", "PO4"}
# aditif kristalisasi / pelarut / buffer umum: bukan ligan asli (tidak dipakai untuk pusat grid & redocking)
ADITIF = {"GOL", "EDO", "PEG", "PGE", "PG4", "1PE", "P6G", "DMS", "ACT", "ACE", "FMT", "MPD", "MRD", "TRS", "EPE",
          "MES", "BME", "DTT", "IMD", "CIT", "FLC", "TAR", "MLI", "SCN", "NO3", "NH4", "AZI", "BU3", "IPA", "EOH",
          "MOH", "DOX", "BTB", "HEZ", "PEO", "SIN", "ACY", "CO3", "BCT", "OXY", "IOD", "2PE", "12P", "15P", "PE4",
          "PE8", "7PE", "XPE", "CXS", "TLA", "SUC", "LMT", "BOG", "HED", "POL", "NHE", "MPO", "CAC", "PO4", "SO4"}
MASSA = {"H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "S": 32.06, "P": 30.974, "F": 18.998, "Cl": 35.45,
         "Br": 79.904, "I": 126.904, "B": 10.81, "Si": 28.085, "Se": 78.97, "Fe": 55.845, "Zn": 65.38, "Mg": 24.305,
         "Ca": 40.078, "Na": 22.99, "K": 39.098, "Mn": 54.938, "Cu": 63.546, "Co": 58.933, "Ni": 58.693}
WARNA_KARBON = ["#2fb3a0", "#d98a1c", "#c25bb5", "#4f9a3a", "#d4594a", "#3f7fd0", "#a0763a", "#7a6fd0"]
_id = itertools.count(1)
_warna = itertools.cycle(WARNA_KARBON)


def id_baru():
    return f"o{next(_id)}"


class GalatImpor(Exception):
    pass


@dataclass
class Objek:
    nama: str
    jenis: str                 # protein | ligan | air | ion | pose | kompleks
    teks: str                  # isi untuk viewer
    fmt: str = "pdb"           # pdb | pdbqt | sdf | mol2
    sumber: str = ""
    id: str = field(default_factory=lambda: f"o{next(_id)}")
    tampil: bool = True
    rantai: dict = field(default_factory=dict)   # rantai -> [(resn, resi, n_atom)]
    info: dict = field(default_factory=dict)
    gaya: dict = field(default_factory=dict)     # reps, warna, permukaan, khusus
    induk: str = ""            # id objek asal (mis. pose -> ligan)
    grup: str = ""             # grup di panel Objek (mis. "Ligan siap docking", "Hasil J...")

    def __post_init__(self):
        if not self.gaya:
            self.gaya = gaya_bawaan(self.jenis)


def gaya_bawaan(jenis):
    if jenis == "protein":
        return {"reps": ["cartoon"], "warna": {"mode": "chain"}, "opacity": 1.0, "permukaan": None, "khusus": []}
    if jenis in ("ligan", "pose"):
        return {"reps": ["sticks"], "warna": {"mode": "element", "carbon": next(_warna)}, "opacity": 1.0,
                "permukaan": None, "khusus": []}
    if jenis == "air":
        return {"reps": ["spheres_kecil"], "warna": {"mode": "solid", "val": "#e04a4a"}, "opacity": 1.0,
                "permukaan": None, "khusus": []}
    if jenis == "ion":
        return {"reps": ["spheres"], "warna": {"mode": "element"}, "opacity": 1.0, "permukaan": None, "khusus": []}
    return {"reps": ["lines"], "warna": {"mode": "element"}, "opacity": 1.0, "permukaan": None, "khusus": []}


def spek_viewer(o):
    """Ubah gaya objek menjadi spesifikasi lapisan untuk VM.tampil()."""
    g = o.gaya
    lap = []
    for rep in g["reps"]:
        if rep == "spheres_kecil":
            lap.append({"sel": {}, "rep": "spheres", "color": g["warna"], "opacity": g["opacity"], "tambah": True,
                        "scale": 0.3})
        elif rep not in ("surface", "mesh"):
            lap.append({"sel": {}, "rep": rep, "color": g["warna"], "opacity": g["opacity"], "tambah": True})
    for k in g.get("khusus", []):
        if k["rep"] != "hide":
            lap.append({"sel": k["sel"], "rep": k["rep"], "color": k.get("warna", g["warna"]), "opacity": 1.0,
                        "tambah": True})
    for k in g.get("khusus", []):  # sembunyikan diterapkan terakhir
        if k["rep"] == "hide":
            lap.append({"sel": k["sel"], "rep": "hide", "color": {}, "tambah": False})
    if o.jenis == "protein" and "spectrum" == g["warna"].get("mode"):
        resi = [r[1] for rs in o.rantai.values() for r in rs]
        if resi:
            for l in lap:
                l["color"] = dict(l["color"], min=min(resi), max=max(resi))
    surf = []
    if g.get("permukaan"):
        surf.append(g["permukaan"])
    return {"visible": o.tampil, "layers": lap, "surfaces": surf}


# ------------------------------------------------------------- pembacaan
def _hierarki(st):
    rantai = {}
    for ch in st[0]:
        rs = [(r.name, r.seqid.num, len(r)) for r in ch]
        if rs:
            rantai.setdefault(ch.name, []).extend(rs)
    return rantai


def _rumus(elemen):
    hit = {}
    for e in elemen:
        e = e.capitalize() if len(e) > 1 else e.upper()
        hit[e] = hit.get(e, 0) + 1
    urut = sorted(hit, key=lambda e: (e != "C", e != "H", e))
    rumus = "".join(f"{e}{hit[e] if hit[e] > 1 else ''}" for e in urut)
    mw = sum(MASSA.get(e, 0) * n for e, n in hit.items())
    return rumus, round(mw, 2), sum(n for e, n in hit.items() if e != "H")


def _pdb_dari(st):
    st.setup_entities()
    opt = gemmi.PdbWriteOptions()
    opt.minimal_file = False
    return st.make_pdb_string(opt)


def pecah_struktur(st, nama, sumber=""):
    """Pisahkan struktur menjadi protein, ligan, air, ion."""
    st.remove_empty_chains()
    if len(st) > 1:  # NMR: ambil model pertama
        for i in range(len(st) - 1, 0, -1):
            del st[i]
    st.remove_alternative_conformations()
    hasil = []
    # protein / polimer
    prot = st.clone()
    prot.remove_ligands_and_waters()
    prot.remove_empty_chains()
    if sum(len(ch) for ch in prot[0]):
        o = Objek(nama=nama, jenis="protein", teks=_pdb_dari(prot), sumber=sumber)
        o.rantai = _hierarki(prot)
        o.info = {"atom": prot[0].count_atom_sites(), "rantai": len(o.rantai),
                  "residu": sum(len(v) for v in o.rantai.values()), "resolusi": st.resolution or None}
        hasil.append(o)
    # ligan, ion, air
    lig, air, ion = {}, [], []
    for ch in st[0]:
        for r in ch:
            if r.het_flag != "H" and r.name not in AIR:
                continue
            if r.name in AIR:
                air.append((ch.name, r))
            elif r.name.upper() in ION or len(r) == 1:
                ion.append((ch.name, r))
            else:
                lig[(ch.name, r.name, r.seqid.num)] = r
    for (c, resn, resi), r in lig.items():
        s = gemmi.Structure()
        s.cell, s.spacegroup_hm = st.cell, st.spacegroup_hm
        m = gemmi.Model("1")
        ch = gemmi.Chain(c)
        ch.add_residue(r)
        m.add_chain(ch)
        s.add_model(m)
        o = Objek(nama=f"{resn} {resi} {c}", jenis="ligan", teks=s.make_pdb_string(), sumber=sumber)
        rumus, mw, berat = _rumus([a.element.name for a in r])
        o.info = {"resn": resn, "resi": resi, "rantai": c, "atom": len(r), "atom_berat": berat, "rumus": rumus,
                  "mw": mw, "ligan_asli": resn.upper() not in ADITIF}
        if resn.upper() in ADITIF:
            o.info["aditif"] = True
            o.tampil = False
        o.rantai = {c: [(resn, resi, len(r))]}
        hasil.append(o)
    for daftar, jenis, label in ((ion, "ion", "Ion"), (air, "air", "Air")):
        if not daftar:
            continue
        s = gemmi.Structure()
        m = gemmi.Model("1")
        rantai = {}
        for c, r in daftar:
            if c not in rantai:
                rantai[c] = gemmi.Chain(c)
            rantai[c].add_residue(r)
        for ch in rantai.values():
            m.add_chain(ch)
        s.add_model(m)
        o = Objek(nama=f"{label} ({len(daftar)})", jenis=jenis, teks=s.make_pdb_string(), sumber=sumber)
        o.info = {"jumlah": len(daftar)}
        o.tampil = jenis == "ion"
        hasil.append(o)
    return hasil


def baca_teks_struktur(teks, nama, fmt="pdb", sumber=""):
    if fmt == "cif":
        doc = gemmi.cif.read_string(teks)
        st = gemmi.make_structure_from_block(doc.sole_block())
    else:
        st = gemmi.read_pdb_string(teks)
    st.setup_entities()
    hasil = pecah_struktur(st, nama, sumber)
    if not hasil:
        raise GalatImpor("Tidak ada atom yang bisa dibaca dari berkas ini.")
    return hasil


def _molekul_rdkit(mol, nama, sumber=""):
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    blok = Chem.MolToMolBlock(mol)
    o = Objek(nama=nama, jenis="ligan", teks=blok, fmt="sdf", sumber=sumber)
    o.info = {"rumus": rdMolDescriptors.CalcMolFormula(mol), "mw": round(Descriptors.MolWt(mol), 2),
              "atom_berat": mol.GetNumHeavyAtoms(), "atom": mol.GetNumAtoms(),
              "torsi": rdMolDescriptors.CalcNumRotatableBonds(mol),
              "donor": rdMolDescriptors.CalcNumHBD(mol), "akseptor": rdMolDescriptors.CalcNumHBA(mol),
              "logp": round(Descriptors.MolLogP(mol), 2), "tpsa": round(rdMolDescriptors.CalcTPSA(mol), 1),
              "smiles": Chem.MolToSmiles(Chem.RemoveHs(mol))}
    return o


def dari_smiles(smiles, nama=None):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        raise GalatImpor("SMILES tidak valid.")
    mol = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol, randomSeed=42) != 0:
        AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    nm = nama or "SMILES_" + str(next(_id))
    mol.SetProp("_Name", nm)
    return [_molekul_rdkit(mol, nm, "SMILES")]


def baca_sdf(teks, nama_dasar, sumber=""):
    from rdkit import Chem
    hasil = []
    sup = Chem.SDMolSupplier()
    sup.SetData(teks, removeHs=False, sanitize=True)
    for i, mol in enumerate(sup, 1):
        if mol is None:
            continue
        nm = mol.GetProp("_Name").strip() if mol.HasProp("_Name") and mol.GetProp("_Name").strip() else f"{nama_dasar}_{i}"
        if mol.GetNumConformers() == 0 or not mol.GetConformer().Is3D():
            from rdkit.Chem import AllChem
            mol = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol, randomSeed=42)
            AllChem.MMFFOptimizeMolecule(mol)
        hasil.append(_molekul_rdkit(mol, nm, sumber))
    if not hasil:
        raise GalatImpor("Tidak ada molekul valid di berkas SDF.")
    return hasil


def baca_mol2(teks, nama_dasar, sumber=""):
    from rdkit import Chem
    blok = ["@<TRIPOS>MOLECULE" + b for b in teks.split("@<TRIPOS>MOLECULE")[1:]]
    hasil = []
    for i, b in enumerate(blok, 1):
        mol = Chem.MolFromMol2Block(b, removeHs=False)
        if mol is None:  # cadangan: Open Babel (program terpisah)
            from . import obabel
            try:
                mol = Chem.MolFromMolBlock(obabel.konversi(b, "mol2", "mol"), removeHs=False)
            except obabel.GalatObabel:
                mol = None
        if mol is None:
            continue
        judul = b.split("\n")[1].strip() if len(b.split("\n")) > 1 else ""
        hasil.append(_molekul_rdkit(mol, judul or f"{nama_dasar}_{i}", sumber))
    if not hasil:
        raise GalatImpor("Tidak ada molekul valid di berkas MOL2.")
    return hasil


def impor_berkas(path):
    p = Path(path)
    ext = p.suffix.lower().lstrip(".")
    teks = p.read_text(errors="replace")
    nama = p.stem
    if ext == "pdbqt" and "\nROOT" in "\n" + teks:
        # ligan PDBQT (punya pohon torsi): baca lewat Open Babel agar ikatan benar
        from . import obabel
        objek = baca_sdf(obabel.konversi(teks, "pdbqt", "sdf"), nama, str(p))
        for o in objek:
            o.nama = nama
        return objek
    if ext in ("pdb", "ent", "pdbqt"):
        if ext == "pdbqt":
            teks = "\n".join(b[:66] + " " * 10 + _elemen_pdbqt(b) if b.startswith(("ATOM", "HETATM")) else b
                             for b in teks.splitlines() if not b.startswith(("ROOT", "ENDROOT", "BRANCH", "ENDBRANCH", "TORSDOF")))
        objek = baca_teks_struktur(teks, nama, "pdb", str(p))
        # PDBQT ligan tunggal (tanpa protein) dianggap ligan
        if ext == "pdbqt" and all(o.jenis != "protein" for o in objek) is False and len(objek) == 1 \
                and objek[0].info.get("residu", 99) <= 1:
            objek[0].jenis = "ligan"
        return objek
    if ext in ("cif", "mmcif"):
        return baca_teks_struktur(teks, nama, "cif", str(p))
    if ext in ("sdf", "mol", "sd"):
        return baca_sdf(teks, nama, str(p))
    if ext == "mol2":
        return baca_mol2(teks, nama, str(p))
    if ext in ("smi", "smiles", "txt"):
        hasil = []
        for i, b in enumerate(teks.splitlines(), 1):
            b = b.strip()
            if b and not b.startswith("#"):
                bag = b.split()
                hasil += dari_smiles(bag[0], bag[1] if len(bag) > 1 else f"{nama}_{i}")
        return hasil
    raise GalatImpor(f"Format .{ext} belum didukung.")


_PDBQT_EL = {"A": "C", "HD": "H", "HS": "H", "NA": "N", "NS": "N", "OA": "O", "OS": "O", "SA": "S", "CL": "Cl", "BR": "Br"}


def _elemen_pdbqt(b):
    t = b[77:].split()[0] if len(b) > 77 and b[77:].split() else "C"
    e = _PDBQT_EL.get(t.upper(), t)
    return e.rjust(2)


# --------------------------------------------------------------- unduhan
def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "VirmoLab/1.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def unduh_rcsb(kode):
    kode = re.sub(r"[^A-Za-z0-9]", "", kode).upper()
    if len(kode) != 4:
        raise GalatImpor("ID PDB harus 4 karakter, contoh: 1HSG")
    try:
        teks = _get(f"https://files.rcsb.org/download/{kode}.pdb").decode("utf-8", "replace")
        return baca_teks_struktur(teks, kode, "pdb", f"RCSB {kode}"), teks, "pdb"
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise GalatImpor(f"RCSB menolak permintaan ({e.code}).")
    try:  # struktur besar hanya tersedia sebagai mmCIF
        teks = _get(f"https://files.rcsb.org/download/{kode}.cif").decode("utf-8", "replace")
        return baca_teks_struktur(teks, kode, "cif", f"RCSB {kode}"), teks, "cif"
    except urllib.error.HTTPError:
        raise GalatImpor(f"ID {kode} tidak ditemukan di RCSB PDB.")


def unduh_pubchem(senyawa):
    senyawa = senyawa.strip()
    jenis = "cid" if senyawa.isdigit() else "name"
    for rec in ("3d", "2d"):
        url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{jenis}/"
               f"{urllib.parse.quote(senyawa)}/SDF?record_type={rec}")
        try:
            data = _get(url).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                continue
            raise GalatImpor(f"PubChem menolak permintaan ({e.code}).")
        if "$$$$" in data:
            blok = data.split("$$$$")[0].lstrip("\r\n") + "$$$$\n"
            nama = f"CID{senyawa}" if senyawa.isdigit() else senyawa
            objek = baca_sdf(blok, nama, f"PubChem {senyawa}")
            for o in objek:
                o.nama = nama
            return objek
    raise GalatImpor(f"'{senyawa}' tidak ditemukan di PubChem.")
