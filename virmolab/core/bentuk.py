"""Kemiripan bentuk 3D dan warna farmakoforik menggunakan rdShapeAlign (RDKit).

Menghitung Tanimoto bentuk (shape), Tanimoto warna (color/fitur farmakoforik),
dan skor gabungan serta menghasilkan molekul kandidat yang telah diselaraskan ke pose acuan.
"""
from typing import Any, Dict, Union
from rdkit import Chem
from rdkit.Chem import AllChem, rdShapeAlign


def skor_bentuk(ref: Chem.Mol, mol: Union[Chem.Mol, str],
                opt_param: float = 0.5,
                n_konf: int = 10,
                prune_rms: float = 0.5) -> Dict[str, Any]:
    """Hitung keselarasan bentuk dan warna farmakoforik antara ligan acuan (ref) dan kandidat (mol).

    Parameters
    ----------
    ref : Chem.Mol
        Molekul acuan dengan koordinat 3D.
    mol : Chem.Mol atau str
        Molekul probe (kandidat) berupa objek RDKit Mol, teks SDF, atau SMILES.
    opt_param : float, default 0.5
        Keseimbangan optimasi bentuk dan warna (0.0 = hanya warna, 0.5 = seimbang, 1.0 = hanya bentuk).
    n_konf : int, default 10
        Jumlah konformer yang diuji bila mol belum memiliki koordinat 3D.
    prune_rms : float, default 0.5
        Ambang pemangkasan RMSD konformer ETKDGv3.

    Returns
    -------
    dict:
        {
            "tanimoto_bentuk": float (0.0 - 1.0),
            "tanimoto_warna": float (0.0 - 1.0),
            "gabungan": float (0.0 - 1.0),
            "mol": Chem.Mol (molekul terselaraskan dengan konformer terbaik),
            "konformer_terbaik": int
        }
    """
    if ref is None or ref.GetNumConformers() == 0:
        raise ValueError("Molekul acuan (ref) harus memiliki koordinat 3D")

    # Siapkan mol probe
    if isinstance(mol, str):
        teks = mol.strip()
        if "\n" in teks or "$$$$" in teks:
            m = Chem.MolFromMolBlock(teks.split("$$$$")[0], removeHs=False, sanitize=True)
        else:
            m = Chem.MolFromSmiles(teks.split()[0])
            if m:
                m = Chem.AddHs(m)
        if m is None:
            raise ValueError("Struktur kandidat (mol) tidak dapat diurai")
    else:
        m = Chem.Mol(mol)

    if m.GetNumConformers() == 0:
        # Hasilkan konformer dengan ETKDGv3
        m = Chem.AddHs(m)
        params = AllChem.ETKDGv3()
        params.pruneRmsThresh = prune_rms
        params.randomSeed = 42
        cids = list(AllChem.EmbedMultipleConfs(m, numConfs=n_konf, params=params))
        if not cids:
            cid = AllChem.EmbedMolecule(m, AllChem.ETKDGv3())
            cids = [cid] if cid >= 0 else []
        if not cids:
            return {
                "tanimoto_bentuk": 0.0,
                "tanimoto_warna": 0.0,
                "gabungan": 0.0,
                "mol": m,
                "konformer_terbaik": -1
            }

    terbaik_g = -1.0
    terbaik_s = 0.0
    terbaik_c = 0.0
    terbaik_cid = -1
    terbaik_mol = None

    for cid in range(m.GetNumConformers()):
        probe = Chem.Mol(m)
        try:
            s, c = rdShapeAlign.AlignMol(ref, probe, refConfId=-1, probeConfId=cid,
                                         useColors=True, opt_param=opt_param)
        except Exception:
            s, c = 0.0, 0.0

        # Skor gabungan: 0.5 * bentuk + 0.5 * warna (atau sesuai opt_param)
        g = 0.5 * float(s) + 0.5 * float(c)
        if g > terbaik_g:
            terbaik_g = g
            terbaik_s = float(s)
            terbaik_c = float(c)
            terbaik_cid = cid

            # Buat mol tunggal dari konformer terbaik yang sudah diselaraskan
            m_res = Chem.Mol(probe)
            # Pertahankan hanya konformer yang sudah terselaraskan
            conf = probe.GetConformer(cid)
            m_res.RemoveAllConformers()
            m_res.AddConformer(Chem.Conformer(conf), assignId=True)
            terbaik_mol = m_res

    if terbaik_mol is None:
        terbaik_mol = m

    return {
        "tanimoto_bentuk": round(max(0.0, min(1.0, terbaik_s)), 4),
        "tanimoto_warna": round(max(0.0, min(1.0, terbaik_c)), 4),
        "gabungan": round(max(0.0, min(1.0, terbaik_g)), 4),
        "mol": terbaik_mol,
        "konformer_terbaik": terbaik_cid
    }
