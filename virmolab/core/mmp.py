"""Molecular Matched Pair (MMP) Analysis.

Mendeteksi pasangan molekul yang berbeda hanya pada satu substituen (R-group),
menganalisis dampak perubahan terhadap afinitas docking (ΔΔG), sifat fisikokimia,
dan mendeteksi SAR activity cliffs.
"""
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from rdkit import Chem
from rdkit.Chem import rdMMPA
from . import kemiripan


def _pecah_fragmen(smiles_pecahan: str) -> Optional[Tuple[str, str, int]]:
    """Pecah string 'frag1.frag2' menjadi (core_smiles, rgroup_smiles, rgroup_heavy_atoms).

    Core adalah fragmen dengan jumlah atom berat lebih banyak.
    """
    if "." not in smiles_pecahan:
        return None
    bagian = smiles_pecahan.split(".")
    if len(bagian) != 2:
        return None

    m0 = Chem.MolFromSmiles(bagian[0])
    m1 = Chem.MolFromSmiles(bagian[1])
    if not m0 or not m1:
        return None

    n0 = m0.GetNumHeavyAtoms()
    n1 = m1.GetNumHeavyAtoms()

    # Yang lebih besar adalah core
    if n0 >= n1:
        core_smi = Chem.MolToSmiles(m0)
        r_smi = Chem.MolToSmiles(m1)
        r_atoms = n1
    else:
        core_smi = Chem.MolToSmiles(m1)
        r_smi = Chem.MolToSmiles(m0)
        r_atoms = n0

    return core_smi, r_smi, r_atoms


def cari_pasangan(daftar_mol_atau_smiles: List[Any], ambang_atom: int = 13) -> List[Dict[str, Any]]:
    """Cari semua pasangan MMP dari daftar molekul / SMILES.

    daftar_mol_atau_smiles: list of (id/nama, Chem.Mol | smiles_str)
    ambang_atom: batas ukuran atom berat maksimum untuk R-group substituen.

    Kembalikan list dict pasangan MMP:
      - id_a, id_b: identifier molekul
      - inti: SMILES core
      - r_a: SMILES R-group molekul A
      - r_b: SMILES R-group molekul B
      - mol_a, mol_b: objek Chem.Mol
    """
    mols = []
    for item in daftar_mol_atau_smiles:
        if isinstance(item, tuple) or isinstance(item, list):
            kunci, obj = item[0], item[1]
        elif isinstance(item, dict):
            kunci = item.get("nama") or item.get("lid") or "Ligan"
            obj = item.get("smiles") or item.get("mol")
        else:
            kunci = str(item)
            obj = item

        if isinstance(obj, str):
            m = Chem.MolFromSmiles(obj.strip().split()[0])
        elif isinstance(obj, Chem.Mol):
            m = obj
        else:
            m = None

        if m is not None:
            mols.append((kunci, m))

    if len(mols) < 2:
        return []

    # Fragmentasi tiap molekul dan simpan ke dalam index inti -> list of (id, rgroup_smiles, mol)
    indeks_inti = defaultdict(list)
    for kunci, m in mols:
        try:
            frags = rdMMPA.FragmentMol(m, maxCuts=1, maxCutBonds=25)
        except Exception:
            frags = []

        inti_tercatat_per_mol = set()
        for _, s_mol in frags:
            if not s_mol:
                continue
            s_teks = Chem.MolToSmiles(s_mol)
            res = _pecah_fragmen(s_teks)
            if not res:
                continue
            core_smi, r_smi, r_heavy = res
            if r_heavy > ambang_atom:
                continue
            if core_smi in inti_tercatat_per_mol:
                continue
            inti_tercatat_per_mol.add(core_smi)
            indeks_inti[core_smi].append((kunci, r_smi, m))

    # Bangun pasangan untuk inti yang dimiliki oleh >= 2 molekul dengan R-group berbeda
    pasangan_ditemukan = []
    pasangan_kunci_unik = set()

    for core_smi, ligan_list in indeks_inti.items():
        if len(ligan_list) < 2:
            continue
        n_lig = len(ligan_list)
        for i in range(n_lig):
            id_a, r_a, mol_a = ligan_list[i]
            for j in range(i + 1, n_lig):
                id_b, r_b, mol_b = ligan_list[j]
                if id_a == id_b:
                    continue
                if r_a == r_b:
                    # Substituen identik, bukan pasangan transformasional
                    continue

                pair_key = tuple(sorted([id_a, id_b])) + (core_smi,)
                if pair_key in pasangan_kunci_unik:
                    continue
                pasangan_kunci_unik.add(pair_key)

                pasangan_ditemukan.append({
                    "id_a": id_a,
                    "id_b": id_b,
                    "inti": core_smi,
                    "r_a": r_a,
                    "r_b": r_b,
                    "mol_a": mol_a,
                    "mol_b": mol_b,
                })

    return pasangan_ditemukan


def tabel_rgroup(pasangan: List[Dict[str, Any]], data_docking: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gabungkan pasangan MMP dengan data afinitas dan sifat docking.

    data_docking: dict mapping {ligand_id/nama: {energi, qed, sascore, sifat, mw, ...}}

    Kembalikan list dict tabel pasangan dengan ΔΔG, ΔQED, ΔSAS, Tanimoto, dsb.
    """
    if not pasangan:
        return []

    hasil = []
    # Cache sidik jari untuk Tanimoto
    fp_cache = {}

    for p in pasangan:
        id_a = p["id_a"]
        id_b = p["id_b"]
        da = data_docking.get(id_a, {})
        db = data_docking.get(id_b, {})

        dg_a = da.get("energi")
        dg_b = db.get("energi")
        ddg = (dg_b - dg_a) if (dg_a is not None and dg_b is not None) else None

        qed_a = da.get("qed")
        qed_b = db.get("qed")
        dqed = (qed_b - qed_a) if (qed_a is not None and qed_b is not None) else None

        sa_a = da.get("sascore")
        sa_b = db.get("sascore")
        dsa = (sa_b - sa_a) if (sa_a is not None and sa_b is not None) else None

        # Tanimoto similarity
        mol_a = p.get("mol_a")
        mol_b = p.get("mol_b")
        sim = 0.5
        if mol_a and mol_b:
            try:
                if id_a not in fp_cache:
                    fp_cache[id_a] = kemiripan.sidik_jari(mol_a, "morgan")
                if id_b not in fp_cache:
                    fp_cache[id_b] = kemiripan.sidik_jari(mol_b, "morgan")
                sim = round(kemiripan.tanimoto(fp_cache[id_a], fp_cache[id_b]), 3)
            except Exception:
                sim = 0.5

        # Tentukan arah transformasi yang menguntungkan
        # Bila ddg < 0: pergantian R_a -> R_b memperkuat ikatan (ΔG lebih negatif)
        if ddg is not None:
            efek = "Memperkuat" if ddg < -0.3 else ("Memperlemah" if ddg > 0.3 else "Netral")
        else:
            efek = "-"

        item = {
            "id_a": id_a,
            "id_b": id_b,
            "inti": p["inti"],
            "r_a": p["r_a"],
            "r_b": p["r_b"],
            "dg_a": dg_a,
            "dg_b": dg_b,
            "ddg": round(ddg, 2) if ddg is not None else None,
            "abs_ddg": round(abs(ddg), 2) if ddg is not None else 0.0,
            "dqed": round(dqed, 3) if dqed is not None else None,
            "dsa": round(dsa, 2) if dsa is not None else None,
            "tanimoto": sim,
            "efek": efek,
        }
        hasil.append(item)

    # Urutkan berdasarkan |ΔΔG| terbesar
    hasil.sort(key=lambda x: x.get("abs_ddg", 0.0), reverse=True)
    return hasil


def sar_cliff(tabel: List[Dict[str, Any]], ambang_ddg: float = 1.5,
              ambang_sim: float = 0.65) -> List[Dict[str, Any]]:
    """Deteksi 'Activity / Affinity Cliff' pada dataset docking.

    Kriteria: Molekul sangat mirip secara struktur (Tanimoto >= ambang_sim),
    tetapi memiliki perbedaan afinitas besar (|ΔΔG| >= ambang_ddg).
    """
    if not tabel:
        return []

    cliffs = []
    for item in tabel:
        ddg = item.get("ddg")
        sim = item.get("tanimoto", 0.0)
        if ddg is not None and abs(ddg) >= ambang_ddg and sim >= ambang_sim:
            c = dict(item)
            c["cliff_skor"] = round(abs(ddg) / max(0.01, 1.0 - sim + 0.1), 2)
            cliffs.append(c)

    cliffs.sort(key=lambda x: x.get("cliff_skor", 0.0), reverse=True)
    return cliffs


def saran_modifikasi(tabel: List[Dict[str, Any]], n: int = 5) -> List[Dict[str, Any]]:
    """Kompilasi saran substitusi R-group yang konsisten meningkatkan afinitas (ΔΔG < 0).

    Kembalikan daftar transform:
      - transformasi: 'R_a → R_b'
      - rata_rata_ddg: rerata ΔΔG (< 0 artinya rata-rata makin kuat)
      - jumlah_pasangan: int
      - keberhasilan: % peningkatan afinitas
    """
    if not tabel:
        return []

    grup = defaultdict(list)
    for it in tabel:
        ddg = it.get("ddg")
        if ddg is None:
            continue
        ra, rb = it["r_a"], it["r_b"]
        # Bentuk transformasi orientasi A -> B
        grup[(ra, rb)].append(ddg)
        # Bentuk transformasi kebalikan B -> A
        grup[(rb, ra)].append(-ddg)

    saran = []
    for (ra, rb), list_ddg in grup.items():
        if len(list_ddg) < 1:
            continue
        rerata = sum(list_ddg) / len(list_ddg)
        # Hanya sarankan transformasi yang rata-rata menguntungkan (rerata < 0)
        if rerata < -0.1:
            n_menang = sum(1 for v in list_ddg if v < -0.1)
            persen = (n_menang / len(list_ddg)) * 100.0
            saran.append({
                "r_asal": ra,
                "r_tujuan": rb,
                "transformasi": f"{ra} → {rb}",
                "rata_rata_ddg": round(rerata, 2),
                "jumlah_pasangan": len(list_ddg),
                "persen_sukses": round(persen, 1),
            })

    saran.sort(key=lambda x: (x["rata_rata_ddg"], -x["jumlah_pasangan"]))
    return saran[:n]
