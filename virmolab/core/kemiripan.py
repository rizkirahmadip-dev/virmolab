"""Kemiripan ligan, ruang kimia, klaster, dan farmakofor (RDKit saja, tanpa paket baru).

Sidik jari: Morgan/ECFP4, FeatMorgan (FCFP4), MACCS, pasangan atom, farmakofor 2D Gobbi. Kemiripan Tanimoto.
Klaster Butina (Taylor-Butina). Peta ruang kimia: PCA dari bit sidik jari atau dari deskriptor fisikokimia.
Farmakofor 3D: fitur kimia RDKit (BaseFeatures.fdef) pada pose; farmakofor bersama = fitur yang muncul
berdekatan (≤ radius) di sebagian besar pose teratas.
"""
import numpy as np

SIDIK = [("morgan", "Morgan r=2 (ECFP4)"), ("featmorgan", "Morgan fitur (FCFP4)"), ("maccs", "MACCS 166 kunci"),
         ("atompair", "Pasangan atom"), ("gobbi", "Farmakofor 2D (Gobbi)")]
NAMA_SIDIK = dict(SIDIK)

# famili fitur RDKit -> (nama Indonesia, warna, radius bola viewport)
FITUR = {"Donor": ("Donor ikatan H", "#2e9e5b", 0.55), "Acceptor": ("Akseptor ikatan H", "#d0473a", 0.55),
         "Aromatic": ("Cincin aromatik", "#7b5cd6", 0.75), "Hydrophobe": ("Hidrofobik", "#c98a12", 0.65),
         "LumpedHydrophobe": ("Hidrofobik", "#c98a12", 0.65), "PosIonizable": ("Muatan positif", "#2f6fd6", 0.7),
         "NegIonizable": ("Muatan negatif", "#cf3f3f", 0.7)}
URUT_FITUR = ["Donor", "Acceptor", "PosIonizable", "NegIonizable", "Aromatic", "Hydrophobe"]


def mol_dari(teks, fmt="sdf"):
    """Mol RDKit tanpa H dari teks SDF/MOL/MOL2/PDB atau SMILES (fmt='smi')."""
    from rdkit import Chem
    if fmt in ("smi", "smiles"):
        m = Chem.MolFromSmiles(teks.strip().split()[0])
    elif fmt in ("sdf", "mol"):
        m = Chem.MolFromMolBlock(teks.split("$$$$")[0], removeHs=False, sanitize=True)
    else:
        from .prep_ligan import mol_dari as _m
        m = _m(teks, fmt)
    if m is None:
        raise ValueError("struktur tidak terbaca")
    return Chem.RemoveHs(m)


def sidik_jari(mol, jenis="morgan"):
    from rdkit import DataStructs
    from rdkit.Chem import MACCSkeys, rdFingerprintGenerator as G
    if jenis == "morgan":
        return G.GetMorganGenerator(radius=2, fpSize=2048).GetFingerprint(mol)
    if jenis == "featmorgan":
        return G.GetMorganGenerator(radius=2, fpSize=2048,
                                    atomInvariantsGenerator=G.GetMorganFeatureAtomInvGen()).GetFingerprint(mol)
    if jenis == "maccs":
        return MACCSkeys.GenMACCSKeys(mol)
    if jenis == "atompair":
        return G.GetAtomPairGenerator(fpSize=2048).GetFingerprint(mol)
    if jenis == "gobbi":
        from rdkit.Chem.Pharm2D import Generate, Gobbi_Pharm2D
        fp = Generate.Gen2DFingerprint(mol, Gobbi_Pharm2D.factory)
        bv = DataStructs.ExplicitBitVect(fp.GetNumBits())   # SparseBitVect -> Explicit agar seragam
        bv.SetBitsFromList(list(fp.GetOnBits()))
        return bv
    raise ValueError(jenis)


def tanimoto(a, b):
    from rdkit import DataStructs
    return DataStructs.TanimotoSimilarity(a, b)


def matriks(fps):
    from rdkit import DataStructs
    n = len(fps)
    m = np.eye(n)
    for i in range(n):
        if i + 1 < n:
            m[i, i + 1:] = DataStructs.BulkTanimotoSimilarity(fps[i], fps[i + 1:])
            m[i + 1:, i] = m[i, i + 1:]
    return m


def peringkat(acuan, fps):
    """Tanimoto setiap fp terhadap acuan (urut sama dengan fps)."""
    from rdkit import DataStructs
    return DataStructs.BulkTanimotoSimilarity(acuan, list(fps))


def butina(m, ambang=0.6):
    """Klaster Taylor-Butina pada matriks kemiripan m; ambang = kemiripan minimum dalam klaster.

    Kembalikan list nomor klaster per ligan (1 = klaster terbesar) dan list pusat klaster (indeks)."""
    from rdkit.ML.Cluster import Butina
    n = len(m)
    jarak = [1 - m[i][j] for i in range(1, n) for j in range(i)]
    kl = Butina.ClusterData(jarak, n, 1 - ambang, isDistData=True, reordering=True)
    kl = sorted(kl, key=lambda c: -len(c))
    nomor = [0] * n
    for k, c in enumerate(kl, 1):
        for i in c:
            nomor[i] = k
    return nomor, [c[0] for c in kl]


def pca(X, n=2):
    """Proyeksi PCA (SVD) -> (koordinat n×2, fraksi variansi dijelaskan per komponen)."""
    X = np.asarray(X, float)
    if len(X) < 2:
        return np.zeros((len(X), n)), [0.0] * n
    sd = X.std(0)
    X = (X - X.mean(0)) / np.where(sd > 1e-12, sd, 1)
    U, S, _ = np.linalg.svd(X, full_matrices=False)
    k = min(n, len(S))
    xy = U[:, :k] * S[:k]
    if k < n:
        xy = np.hstack([xy, np.zeros((len(X), n - k))])
    var = (S ** 2) / max((S ** 2).sum(), 1e-12)
    return xy, [float(v) for v in var[:n]] + [0.0] * (n - k)


def mds(m, n=2):
    """MDS klasik dari matriks kemiripan (jarak = 1 − Tanimoto) -> koordinat n×2 + fraksi variansi."""
    D2 = (1 - np.asarray(m, float)) ** 2
    k = len(D2)
    if k < 2:
        return np.zeros((k, n)), [0.0] * n
    J = np.eye(k) - np.ones((k, k)) / k
    B = -0.5 * J @ D2 @ J
    w, V = np.linalg.eigh(B)
    idx = np.argsort(w)[::-1]
    w, V = w[idx], V[:, idx]
    pos = np.clip(w[:n], 0, None)
    xy = V[:, :n] * np.sqrt(pos)
    tot = np.clip(w, 0, None).sum() or 1
    return xy, [float(v / tot) for v in pos]


DESKRIPTOR = ["MolWt", "MolLogP", "TPSA", "NumHDonors", "NumHAcceptors", "NumRotatableBonds", "RingCount",
              "NumAromaticRings", "FractionCSP3", "HeavyAtomCount"]


def deskriptor(mol):
    from rdkit.Chem import Descriptors
    return [float(getattr(Descriptors, d)(mol)) for d in DESKRIPTOR]


def bit_array(fp):
    from rdkit import DataStructs
    a = np.zeros((fp.GetNumBits(),), dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(fp, a)
    return a


# ------------------------------------------------------------------ farmakofor 3D
_PABRIK = None


def _pabrik():
    global _PABRIK
    if _PABRIK is None:
        import os
        from rdkit import RDConfig
        from rdkit.Chem import ChemicalFeatures
        # lewat Python: pembuka berkas C++ RDKit gagal pada folder aplikasi ber-huruf non-ASCII
        with open(os.path.join(RDConfig.RDDataDir, "BaseFeatures.fdef"), encoding="utf-8") as f:
            _PABRIK = ChemicalFeatures.BuildFeatureFactoryFromString(f.read())
    return _PABRIK


def fitur(mol, gabung=1.6):
    """Fitur farmakofor 3D sebuah konformer: [{famili, nama, warna, radius, xyz, atom}].

    Hidrofobik yang bertumpuk (pusat ≤ gabung Å) dilebur; 'LumpedHydrophobe' dipetakan ke 'Hydrophobe'."""
    if mol.GetNumConformers() == 0:
        raise ValueError("molekul tidak punya koordinat 3D")
    f = _pabrik().GetFeaturesForMol(mol)
    out = []
    for x in f:
        fam = x.GetFamily()
        if fam not in FITUR:
            continue
        if fam == "LumpedHydrophobe":
            fam = "Hydrophobe"
        # atom hidrofobik di cincin aromatik sudah diwakili fitur 'Aromatic'
        if fam == "Hydrophobe" and all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in x.GetAtomIds()):
            continue
        p = x.GetPos()
        xyz = [round(p.x, 3), round(p.y, 3), round(p.z, 3)]
        if fam == "Hydrophobe" and any(o["famili"] == fam and _jarak(o["xyz"], xyz) <= gabung for o in out):
            continue
        nama, warna, r = FITUR[fam]
        out.append({"famili": fam, "nama": nama, "warna": warna, "radius": r, "xyz": xyz,
                    "atom": list(x.GetAtomIds())})
    # hidrofobik yang sangat dekat cincin aromatik tak menambah informasi
    aro = [o["xyz"] for o in out if o["famili"] == "Aromatic"]
    out = [o for o in out if not (o["famili"] == "Hydrophobe" and any(_jarak(o["xyz"], a) < 0.6 for a in aro))]
    out.sort(key=lambda o: URUT_FITUR.index(o["famili"]) if o["famili"] in URUT_FITUR else 99)
    return out


def _jarak(a, b):
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


def farmakofor_bersama(daftar_fitur, radius=1.5, min_frek=0.5):
    """Gabungkan fitur dari beberapa pose (satu list per pose) menjadi farmakofor bersama.

    Fitur famili sama yang berjarak ≤ radius dikelompokkan (rantai tunggal ke pusat kelompok berjalan).
    Kelompok yang muncul di ≥ min_frek pose dipertahankan. Kembalikan list fitur + 'frek' + 'n'."""
    n = len(daftar_fitur)
    kel = []          # {famili, pusat, anggota:set(indeks pose), titik:list}
    for ip, fs in enumerate(daftar_fitur):
        for f in fs:
            cocok = None
            for k in kel:
                if k["famili"] == f["famili"] and _jarak(k["pusat"], f["xyz"]) <= radius:
                    cocok = k
                    break
            if cocok is None:
                kel.append({"famili": f["famili"], "pusat": list(f["xyz"]), "anggota": {ip}, "titik": [f["xyz"]]})
            else:
                cocok["anggota"].add(ip)
                cocok["titik"].append(f["xyz"])
                cocok["pusat"] = list(np.mean(cocok["titik"], 0))
    out = []
    for k in kel:
        frek = len(k["anggota"]) / max(n, 1)
        if frek + 1e-9 < min_frek:
            continue
        nama, warna, r = FITUR[k["famili"]]
        sebar = float(np.sqrt(np.mean([_jarak(t, k["pusat"]) ** 2 for t in k["titik"]]))) if k["titik"] else 0
        out.append({"famili": k["famili"], "nama": nama, "warna": warna, "radius": max(r, min(1.5, sebar + 0.4)),
                    "xyz": [round(float(v), 3) for v in k["pusat"]], "frek": round(frek, 3), "n": len(k["anggota"]),
                    "sebar": round(sebar, 2)})
    out.sort(key=lambda o: (-o["frek"], URUT_FITUR.index(o["famili"]) if o["famili"] in URUT_FITUR else 99))
    return out


def ringkas_fitur(fs):
    """'2 donor, 3 akseptor, …' untuk bilah status/log."""
    hit = {}
    for f in fs:
        hit[f["nama"]] = hit.get(f["nama"], 0) + 1
    return ", ".join(f"{v} {k[0].lower() + k[1:]}" for k, v in hit.items()) or "tidak ada fitur"


def pml_farmakofor(fs, nama="farmakofor"):
    """Skrip PyMOL (pseudoatom bola berwarna) untuk farmakofor."""
    out = [f"# Farmakofor VirmoLab ({len(fs)} fitur)"]
    for i, f in enumerate(fs, 1):
        x, y, z = f["xyz"]
        h = f["warna"].lstrip("#")
        out.append(f"pseudoatom {nama}_{i}, pos=[{x:.3f}, {y:.3f}, {z:.3f}], label={f['famili']}")
        out.append(f"set_color {nama}_c{i}, [{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}]")
        out.append(f"show spheres, {nama}_{i}")
        out.append(f"set sphere_scale, {f['radius']:.2f}, {nama}_{i}")
        out.append(f"color {nama}_c{i}, {nama}_{i}")
    out.append(f"set sphere_transparency, 0.35, {nama}_*")
    return "\n".join(out) + "\n"
