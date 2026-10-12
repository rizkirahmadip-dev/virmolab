"""Perancang Molekul PROTAC (Proteolysis Targeting Chimera) & TPD Modality.

Merancang senyawa bivalen chimera penarget degradasi protein:
  [Warhead Ligan Target] - [Linker] - [E3 Ligase Binder (VHL / CRBN / IAP)]
Menghitung parameter fisiko-kimia bRo5 (Beyond Rule of 5), panjang rentang linker (Å),
dan kompatibilitas konformasi degradasi.
"""
from typing import Any, Dict
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors

# Koleksi E3 Ligase Binders standar industri dengan attachment point [*:1]
E3_BINDERS = {
    "VHL_VH032": {
        "nama": "VHL Binder (VH032 derivative)",
        "deskripsi": "Pengikat E3 ligase Von Hippel-Lindau paling umum dalam uji klinis.",
        "smiles": "Cc1nc(cs1)c1ccc(CNC(=O)[C@@H]2C[C@@H](O)CN2C(=O)[C@@H](NC(=O)[*:1])C(C)(C)C)cc1",
    },
    "CRBN_Pomalidomide": {
        "nama": "Cereblon (Pomalidomide 4-amino)",
        "deskripsi": "Pengikat Cereblon (CRBN) klasik dengan afinitas nanomolar.",
        "smiles": "O=C1CCC(N2C(=O)c3cccc(N[*:1])c3C2=O)C(=O)N1",
    },
    "CRBN_Thalidomide": {
        "nama": "Cereblon (Thalidomide 5-hydroxy/ether)",
        "deskripsi": "Varian CRBN berbasis jembatan eter posisi-5.",
        "smiles": "O=C1CCC(N2C(=O)c3ccc(O[*:1])cc3C2=O)C(=O)N1",
    },
}

# Koleksi Linker Modular dengan dua ujung penyambung [*:1] dan [*:2]
LINKER_PRESETS = {
    "PEG2": {
        "nama": "PEG-2 Linker (-CH2-CH2-O-CH2-CH2-)",
        "smiles": "[*:1]CCOCCOCC[*:2]",
        "panjang_est": 8.5,
    },
    "PEG3": {
        "nama": "PEG-3 Linker (-CH2-CH2-(O-CH2-CH2)2-)",
        "smiles": "[*:1]CCOCCOCCOCC[*:2]",
        "panjang_est": 12.0,
    },
    "PEG4": {
        "nama": "PEG-4 Linker (Panjang Optimal Standar)",
        "smiles": "[*:1]CCOCCOCCOCCOCC[*:2]",
        "panjang_est": 15.5,
    },
    "Alkil_C4": {
        "nama": "Alkil Butil C4 (Lipofilik Fleksibel)",
        "smiles": "[*:1]CCCCC[*:2]",
        "panjang_est": 6.3,
    },
    "Alkil_C6": {
        "nama": "Alkil Heksil C6 (Lipofilik Sedang)",
        "smiles": "[*:1]CCCCCCC[*:2]",
        "panjang_est": 8.8,
    },
    "Alkil_C8": {
        "nama": "Alkil Oktil C8 (Panjang)",
        "smiles": "[*:1]CCCCCCCCC[*:2]",
        "panjang_est": 11.3,
    },
    "Piperazin_Alkil": {
        "nama": "Piperazin Semikaku (Rigidified Linker)",
        "smiles": "[*:1]CCN1CCN(CC[*:2])CC1",
        "panjang_est": 9.2,
    },
}


def daftar_e3_binders() -> Dict[str, Dict[str, str]]:
    """Daftar E3 ligase binder bawaan."""
    return E3_BINDERS


def daftar_linkers() -> Dict[str, Dict[str, Any]]:
    """Daftar linker bawaan."""
    return LINKER_PRESETS


def _beri_titik_lekat(mol) -> str:
    """SMILES warhead dengan satu [*:9] menggantikan H pada karbon terbuka (prioritas: CH3 alifatik, lalu CH aromatik)."""
    from rdkit import Chem
    for smarts in ("[CH3;!$(C=O)]", "[cH]", "[CH2;R0]", "[NH1;!$(N=*)]"):
        patt = Chem.MolFromSmarts(smarts)
        cocok = mol.GetSubstructMatches(patt)
        if cocok:
            rw = Chem.RWMol(mol)
            idx = cocok[-1][0]
            d = rw.AddAtom(Chem.AtomFromSmiles("*"))
            rw.GetAtomWithIdx(d).SetAtomMapNum(9)
            a = rw.GetAtomWithIdx(idx)
            if a.GetNumExplicitHs():
                a.SetNumExplicitHs(a.GetNumExplicitHs() - 1)
            a.SetNoImplicit(False)
            rw.AddBond(idx, d, Chem.BondType.SINGLE)
            keluar = Chem.MolToSmiles(rw)
            if Chem.MolFromSmiles(keluar.replace("[*:9]", "[H]")) is not None:
                return keluar
    raise ValueError("Warhead tidak punya posisi terbuka untuk disambung ke linker.")


def _sambung(warhead_lekat: str, linker: str, e3: str) -> str:
    """Gabung warhead-[*:9] + [*:1]linker[*:2] + e3-[*:1] menjadi satu molekul kovalen."""
    from rdkit import Chem
    from rdkit.Chem import rdmolops
    gabung = Chem.MolFromSmiles(f"{warhead_lekat}.{linker.replace('[*:1]', '[*:9]').replace('[*:2]', '[*:8]')}."
                                f"{e3.replace('[*:1]', '[*:8]')}")
    if gabung is None:
        return ""
    for nomor in (9, 8):
        rw = Chem.RWMol(gabung)
        dummy = [a.GetIdx() for a in rw.GetAtoms() if a.GetAtomMapNum() == nomor]
        if len(dummy) != 2:
            return ""
        tetangga = [rw.GetAtomWithIdx(d).GetNeighbors()[0].GetIdx() for d in dummy]
        rw.AddBond(tetangga[0], tetangga[1], Chem.BondType.SINGLE)
        for d in sorted(dummy, reverse=True):
            rw.RemoveAtom(d)
        gabung = rw.GetMol()
        Chem.SanitizeMol(gabung)
    if len(rdmolops.GetMolFrags(gabung)) != 1:
        return ""
    return Chem.MolToSmiles(gabung)


def rakit_protac(
    smiles_warhead: str,
    kunci_e3: str = "VHL_VH032",
    kunci_linker: str = "PEG3",
) -> Dict[str, Any]:
    """Rakit molekul PROTAC bivalen dari warhead ligan target, linker, dan E3 binder.
    
    Args:
        smiles_warhead: SMILES ligan penarget (jika mengandung [*:1] gunakan itu, jika tidak sambung di atom polar/ujung)
        kunci_e3: Kunci dari E3_BINDERS
        kunci_linker: Kunci dari LINKER_PRESETS
        
    Returns:
        Kamus data PROTAC lengkap:
 - smiles_protac: str
 - mw: float
 - logp: float
 - tpsa: float
 - hbd: int
 - hba: int
 - n_rot: int
 - panjang_linker: float (Å)
 - evaluasi_bro5: str
    """
    mol_w = Chem.MolFromSmiles(smiles_warhead)
    if not mol_w:
        raise ValueError(f"SMILES warhead tidak valid: {smiles_warhead}")
    e3_info = E3_BINDERS.get(kunci_e3, E3_BINDERS["VHL_VH032"])
    linker_info = LINKER_PRESETS.get(kunci_linker, LINKER_PRESETS["PEG3"])

    # Warhead disambung lewat satu atom hidrogen pada karbon alifatik/aromatik terbuka (titik lekat eksoterik);
    # linker dan E3 binder punya titik lekat [*:1] / [*:2] yang dipetakan satu-satu.
    warhead_lekat = _beri_titik_lekat(mol_w)
    rakitan = _sambung(warhead_lekat, linker_info["smiles"], e3_info["smiles"])
    mol_protac = Chem.MolFromSmiles(rakitan) if rakitan else None
    if mol_protac is None:
        raise ValueError("Rakitan PROTAC tidak membentuk molekul yang sah. Coba warhead atau linker lain.")
    final_smi = Chem.MolToSmiles(mol_protac)

    # Kalkulasi Deskriptor Beyond Rule of 5 (bRo5)
    mw = round(Descriptors.MolWt(mol_protac), 1)
    logp = round(Descriptors.MolLogP(mol_protac), 2)
    tpsa = round(Descriptors.TPSA(mol_protac), 1)
    hbd = Lipinski.NumHDonors(mol_protac)
    hba = Lipinski.NumHAcceptors(mol_protac)
    n_rot = rdMolDescriptors.CalcNumRotatableBonds(mol_protac)

    # Evaluasi bRo5 Drug-Likeness untuk modalitas PROTAC
    # Menurut DeGoey et al. (J. Med. Chem. 2018), PROTAC oral umumnya: MW < 1000 Da, PSA < 250 Å², HBD <= 5
    if mw <= 1000 and tpsa <= 220 and hbd <= 5:
        bro5_status = "Optimal bRo5 (Potensi Bioavailabilitas Oral)"
    elif mw <= 1200:
        bro5_status = "Tipikal PROTAC (Cocok untuk Formulasi Injeksi / IV)"
    else:
        bro5_status = "Molekul Besar (> 1200 Da, Diperlukan Optimasi Pemendekan Linker)"

    return {
        "smiles": final_smi,
        "nama_e3": e3_info["nama"],
        "nama_linker": linker_info["nama"],
        "panjang_linker_est": linker_info["panjang_est"],
        "mw": mw,
        "logp": logp,
        "tpsa": tpsa,
        "hbd": hbd,
        "hba": hba,
        "n_rot": n_rot,
        "evaluasi_bro5": bro5_status,
    }
