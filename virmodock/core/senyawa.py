"""Enumerasi dan pemeriksaan ligan yang masih di RDKit: umpan, regangan, tautomer,
stereoisomer, gugus R, bioisoster, bentuk 3D, makrosiklus, dan sunting di dalam kantong.
"""
from rdkit import Chem
from rdkit.Chem import AllChem, Crippen, Descriptors, rdMolDescriptors, rdShapeHelpers

BIOISOSTER = [
    ("asam karboksilat → tetrazol", "[*:1]C(=O)[OH]>>[*:1]c1nnn[nH]1"),
    ("asam karboksilat → amida", "[*:1]C(=O)[OH]>>[*:1]C(N)=O"),
    ("fenil → 4-piridil", "c1ccc([*:1])cc1>>c1ccncc1[*:1]"),
    ("kloro → trifluorometil", "[c:1]Cl>>[c:1]C(F)(F)F"),
    ("hidroksil aromatik → amino", "[c:1]O>>[c:1]N"),
    ("metilena → eter", "[*:1]C[*:2]>>[*:1]O[*:2]"),
]
REAKSI_UMPAN = [
    "[c:1][H]>>[c:1]C",
    "[c:1][H]>>[c:1]F",
    "[c:1][H]>>[c:1]Cl",
    "[c:1][H]>>[c:1]OC",
    "[C:1](=O)[OH]>>[C:1](N)=O",
    "[cH:1]>>[n:1]",
    "[*:1]C[*:2]>>[*:1][*:2]",
]


def _berat(mol):
    m = Chem.RemoveHs(mol)
    return {
        "mw": Descriptors.MolWt(m),
        "logp": Crippen.MolLogP(m),
        "hbd": rdMolDescriptors.CalcNumHBD(m),
        "hba": rdMolDescriptors.CalcNumHBA(m),
        "muatan": Chem.GetFormalCharge(m),
    }


def _fp(mol):
    return rdMolDescriptors.GetMorganFingerprintAsBitVect(Chem.RemoveHs(mol), 2, nBits=2048)


def mirip(a, b):
    from rdkit import DataStructs
    return DataStructs.TanimotoSimilarity(_fp(a), _fp(b))


def ada_makrosiklus(mol):
    """True bila ada cincin ≥ 7 atom. Meeko membuat cincin itu fleksibel (kecuali opsi 'Makrosiklik kaku')."""
    mol = Chem.RemoveHs(mol)
    return any(len(r) >= 7 for r in mol.GetRingInfo().AtomRings())


def regangan(mol):
    """Energi MMFF pose sekarang dikurangi energi setelah minimisasi bebas (kkal/mol).

    Angka besar berarti pose docking meregangkan ligan. Bukan ΔG ikatan.
    """
    m = Chem.AddHs(Chem.Mol(mol), addCoords=True)
    if m.GetNumConformers() == 0 or not m.GetConformer().Is3D():
        prm = AllChem.ETKDGv3()
        prm.randomSeed = 1
        if AllChem.EmbedMolecule(m, prm) != 0:
            raise ValueError("Konformer 3D gagal dibuat.")
    if not AllChem.MMFFHasAllMoleculeParams(m):
        raise ValueError("Parameter MMFF tidak lengkap untuk ligan ini.")
    ff = AllChem.MMFFGetMoleculeForceField(m, AllChem.MMFFGetMoleculeProperties(m))
    terikat = ff.CalcEnergy()
    ff.Minimize(maxIts=500)
    return round(terikat - ff.CalcEnergy(), 2)


def bentuk(mol_a, mol_b):
    """Kemiripan bentuk 3D (1 − jarak Shape-Tanimoto RDKit) setelah penyejajaran."""
    a, b = Chem.AddHs(Chem.Mol(mol_a)), Chem.AddHs(Chem.Mol(mol_b))
    for m in (a, b):
        if m.GetNumConformers() == 0:
            AllChem.EmbedMolecule(m, AllChem.ETKDGv3())
    AllChem.AlignMol(a, b)
    jarak = rdShapeHelpers.ShapeTanimotoDist(a, b)
    return round(1.0 - float(jarak), 3)


def tautomer(mol, maks=8):
    from rdkit.Chem.MolStandardize import rdMolStandardize
    en = rdMolStandardize.TautomerEnumerator()
    en.SetMaxTautomers(maks)
    hasil = []
    for t in en.Enumerate(Chem.RemoveHs(mol)):
        smi = Chem.MolToSmiles(t)
        if smi not in hasil:
            hasil.append(smi)
        if len(hasil) >= maks:
            break
    return hasil


def stereoisomer(mol, maks=8):
    from rdkit.Chem.EnumerateStereoisomers import EnumerateStereoisomers, StereoEnumerationOptions
    opsi = StereoEnumerationOptions(maxIsomers=maks, tryEmbedding=False)
    hasil = []
    for m in EnumerateStereoisomers(Chem.RemoveHs(mol), options=opsi):
        smi = Chem.MolToSmiles(m, isomericSmiles=True)
        if smi not in hasil:
            hasil.append(smi)
    return hasil


def _diam_rdkit():
    from rdkit import rdBase
    rdBase.DisableLog("rdApp.error")
    rdBase.DisableLog("rdApp.warning")


def _jalan_reaksi(mol, smarts):
    _diam_rdkit()
    rxn = AllChem.ReactionFromSmarts(smarts)
    out = []
    for produk in rxn.RunReactants((Chem.RemoveHs(mol),)):
        m = produk[0]
        try:
            Chem.SanitizeMol(m)
        except Exception:
            continue
        smi = Chem.MolToSmiles(m)
        if smi:
            out.append(smi)
    return out


def bioisoster(mol, maks=12):
    """[(nama pengganti, SMILES)] dari tabel reaksi tetap. Bukan ramalan afinitas."""
    lihat, hasil = set(), []
    for nama, smarts in BIOISOSTER:
        for smi in _jalan_reaksi(mol, smarts):
            if smi in lihat:
                continue
            lihat.add(smi)
            hasil.append((nama, smi))
            if len(hasil) >= maks:
                return hasil
    return hasil


def enumerasi_gugus(inti_smiles, gugus):
    """Inti beratom * (dummy) + daftar SMILES substituen → SMILES produk.

    Contoh inti: ``*c1ccccc1``. Substituen tanpa bintang dipasang utuh (``Cl``, ``O``, ``C``).
    """
    inti = Chem.MolFromSmiles(inti_smiles)
    if inti is None or not any(a.GetAtomicNum() == 0 for a in inti.GetAtoms()):
        raise ValueError("Inti harus SMILES yang mengandung * pada titik tempel, misalnya *c1ccccc1.")
    rxn = AllChem.ReactionFromSmarts("[*:1][#0:2].[#0:3][*:4]>>[*:1][*:4]")
    hasil = []
    for g in gugus:
        g = g.strip()
        if not g:
            continue
        frag = Chem.MolFromSmiles(g if "*" in g else "*" + g)
        if frag is None or not any(a.GetAtomicNum() == 0 for a in frag.GetAtoms()):
            hasil.append((g, "", "SMILES substituen tidak sah"))
            continue
        produk = rxn.RunReactants((inti, frag))
        if not produk:
            hasil.append((g, "", "tidak bisa dipasang"))
            continue
        m = produk[0][0]
        try:
            Chem.SanitizeMol(m)
            hasil.append((g, Chem.MolToSmiles(m), ""))
        except Exception as e:
            hasil.append((g, "", str(e).splitlines()[0][:80]))
    return hasil


def umpan(smiles_aktif, n=20, seed=1):
    """Umpan berpadanan sifat (MW, logP, donor, akseptor) tetapi Tanimoto ECFP4 < 0,40.

    Untuk kurva ROC/AUC skrining. Bukan decoy DUD-E; sebutkan sumbernya di metode.
    """
    import random
    _diam_rdkit()
    acak = random.Random(seed)
    aktif = [Chem.MolFromSmiles(s) for s in smiles_aktif]
    aktif = [m for m in aktif if m is not None]
    if not aktif:
        raise ValueError("Tidak ada SMILES aktif yang sah.")
    sifat = [_berat(m) for m in aktif]
    fp = [_fp(m) for m in aktif]
    dari = set(Chem.MolToSmiles(m) for m in aktif)
    calon = []
    reaksi = [AllChem.ReactionFromSmarts(s) for s in REAKSI_UMPAN]
    for m in aktif:
        for rxn in reaksi:
            for produk in rxn.RunReactants((Chem.AddHs(m),)):
                try:
                    Chem.SanitizeMol(produk[0])
                    calon.append(Chem.MolToSmiles(produk[0]))
                except Exception:
                    pass
    acak.shuffle(calon)
    # putaran kedua: reaksi di atas calon baru, supaya ragamnya cukup
    tambahan = []
    for smi in calon[:40]:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        for rxn in reaksi:
            for produk in rxn.RunReactants((Chem.AddHs(m),)):
                try:
                    Chem.SanitizeMol(produk[0])
                    tambahan.append(Chem.MolToSmiles(produk[0]))
                except Exception:
                    pass
    calon.extend(tambahan)
    from rdkit import DataStructs
    terima, lihat = [], set()
    for smi in calon:
        if smi in dari or smi in lihat:
            continue
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        lihat.add(smi)
        p = _berat(m)
        bit = _fp(m)
        if any(DataStructs.TanimotoSimilarity(bit, f) >= 0.40 for f in fp):
            continue
        if not any(abs(p["mw"] - a["mw"]) <= 60 and abs(p["logp"] - a["logp"]) <= 1.5
                   and abs(p["hbd"] - a["hbd"]) <= 2 and abs(p["hba"] - a["hba"]) <= 2
                   and p["muatan"] == a["muatan"] for a in sifat):
            continue
        terima.append(smi)
        if len(terima) >= n:
            break
    return terima


def tabrakan(mol, teks_pdb, jarak=1.7):
    """Jumlah atom berat ligan yang lebih dekat dari `jarak` Å ke atom berat protein."""
    import numpy as np
    m = Chem.RemoveHs(mol)
    if m.GetNumConformers() == 0:
        return 0
    lig = m.GetConformer().GetPositions()
    rec = []
    for b in teks_pdb.splitlines():
        if b.startswith("ATOM") and len(b) >= 54 and b[76:78].strip() not in ("H", "D", ""):
            try:
                rec.append([float(b[30:38]), float(b[38:46]), float(b[46:54])])
            except ValueError:
                pass
        elif b.startswith("ATOM") and len(b) >= 54 and not b[76:78].strip():
            if b[12:16].strip()[:1] not in ("H", "D"):
                try:
                    rec.append([float(b[30:38]), float(b[38:46]), float(b[46:54])])
                except ValueError:
                    pass
    if not rec:
        return 0
    d = np.linalg.norm(lig[:, None, :] - np.asarray(rec)[None, :, :], axis=2)
    return int((d.min(axis=1) < jarak).sum())


def sunting_kantong(mol, smarts_reaksi, teks_reseptor=""):
    """Jalankan satu reaksi bioisoster/pengganti pada pose, kembalikan (mol baru, SMILES, jumlah tabrakan)."""
    daftar = _jalan_reaksi(mol, smarts_reaksi)
    if not daftar:
        raise ValueError("Reaksi tidak mengenai ligan ini.")
    baru = Chem.AddHs(Chem.MolFromSmiles(daftar[0]))
    prm = AllChem.ETKDGv3()
    prm.randomSeed = 2
    AllChem.EmbedMolecule(baru, prm)
    if mol.GetNumConformers():
        try:
            AllChem.AlignMol(baru, Chem.RemoveHs(mol))
        except Exception:
            pass
    n = tabrakan(baru, teks_reseptor) if teks_reseptor else 0
    return baru, daftar[0], n
