"""Fragment-Based Drug Design (FBDD) - Fragment Growing & Linking.

Modul desain obat berbasis fragmen:
1. Fragment Growing: Mengembangkan fragmen awal dengan penambahan substituen farmakoforik
   (metil, hidroksi, fluoro, kloro, amino, metoksi, siano, karboksamida, fenil, heterosiklik).
2. Fragment Linking: Menyambungkan dua fragmen kecil yang mengikat sub-kantong berbeda
   menggunakan rantai penghubung (linker alkil, eter, amida, dll.).
3. Evaluasi instan profil sifat fisikokimia, QED, dan kemudahan sintesis (SAScore).
"""
from typing import Any, Dict, List
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, QED, rdMolDescriptors
from . import catat, sascore


# Pustaka substituen baku untuk Fragment Growing
SUBSTITUEN_GROWING = [
    ("Metil (-CH3)", "[H]", "C", "CH3"),
    ("Fluoro (-F)", "[H]", "F", "F"),
    ("Kloro (-Cl)", "[H]", "Cl", "Cl"),
    ("Hidroksi (-OH)", "[H]", "O", "OH"),
    ("Amino (-NH2)", "[H]", "N", "NH2"),
    ("Trifluorometil (-CF3)", "[H]", "C(F)(F)F", "CF3"),
    ("Metoksi (-OCH3)", "[H]", "OC", "OCH3"),
    ("Siano (-CN)", "[H]", "C#N", "CN"),
    ("Karboksamida (-CONH2)", "[H]", "C(=O)N", "CONH2"),
    ("Karboksilat (-COOH)", "[H]", "C(=O)O", "COOH"),
    ("Sulfonamida (-SO2NH2)", "[H]", "S(=O)(=O)N", "SO2NH2"),
    ("Siklopropil", "[H]", "C1CC1", "c-Pr"),
    ("Fenil (-Ph)", "[H]", "c1ccccc1", "Ph"),
    ("4-Piridil", "[H]", "c1ccncc1", "Pyr"),
    ("2-Tiazolil", "[H]", "c1nccs1", "Tz"),
]

# Pustaka linker baku untuk Fragment Linking
LINKER_LIST = [
    ("Metilen (-CH2-)", "C"),
    ("Etilen (-CH2CH2-)", "CC"),
    ("Propilen (-CH2CH2CH2-)", "CCC"),
    ("Eter (-CH2-O-CH2-)", "COC"),
    ("Amida (-CONH-)", "C(=O)N"),
    ("Metilen Amida (-CH2CONH-)", "CC(=O)N"),
    ("Vinil (-CH=CH-)", "C=C"),
]


def _evaluasi_molekul(mol: Chem.Mol, nama: str, modifikasi: str) -> Dict[str, Any]:
    """Hitung sifat fisikokimia dan drug-likeness molekul hasil turunan FBDD."""
    smi = Chem.MolToSmiles(mol)
    mw = round(Descriptors.MolWt(mol), 1)
    wlogp = round(Crippen.MolLogP(mol), 2)
    tpsa = round(rdMolDescriptors.CalcTPSA(mol), 1)
    hbd = rdMolDescriptors.CalcNumHBD(mol)
    hba = rdMolDescriptors.CalcNumHBA(mol)
    rotb = rdMolDescriptors.CalcNumRotatableBonds(mol)
    qed_val = round(QED.qed(mol), 2)
    sa_val = round(sascore.hitung_sascore(mol) or 3.0, 2)

    # Lipinski rule
    lip_pelanggaran = sum((mw > 500, wlogp > 5, hbd > 5, hba > 10))

    return {
        "nama": nama,
        "smiles": smi,
        "modifikasi": modifikasi,
        "mw": mw,
        "wlogp": wlogp,
        "tpsa": tpsa,
        "hbd": hbd,
        "hba": hba,
        "rotb": rotb,
        "qed": qed_val,
        "sascore": sa_val,
        "lipinski_lolos": (lip_pelanggaran <= 1),
        "lipinski_pelanggaran": lip_pelanggaran,
    }


def tumbuhkan_fragmen(
    smiles_fragmen: str,
    nama_awal: str = "Fragmen",
    maks_hasil: int = 30
) -> List[Dict[str, Any]]:
    """Fragment Growing: kembangkan fragmen awal dengan penambahan substituen bioaktif."""
    m_induk = Chem.MolFromSmiles(smiles_fragmen.strip().split()[0])
    if not m_induk:
        return []

    hasil = []
    # Masukkan fragmen induk sebagai baris referensi (baris 0)
    hasil.append(_evaluasi_molekul(m_induk, f"{nama_awal} (Induk)", "Struktur Awal"))

    smiles_unik = {Chem.MolToSmiles(m_induk)}

    # Temukan atom karbon/nitrogen yang memiliki valensi terbuka (implicit/explicit H)
    atom_substitusi = []
    for atom in m_induk.GetAtoms():
        if atom.GetSymbol() in ("C", "N") and atom.GetTotalNumHs() > 0:
            atom_substitusi.append(atom.GetIdx())

    counter = 1
    for a_idx in atom_substitusi:
        simbol_atom = m_induk.GetAtomWithIdx(a_idx).GetSymbol()
        nomor_atom = a_idx + 1

        for label_gugus, _, smi_gugus, singkatan in SUBSTITUEN_GROWING:
            gugus_m = Chem.MolFromSmiles(smi_gugus)
            if not gugus_m:
                continue

            # Sambungkan gugus ke atom_idx via edMol
            rw = Chem.RWMol(m_induk)
            g_rw = Chem.RWMol(gugus_m)

            # Tambahkan atom-atom gugus ke molekul induk
            map_idx = {}
            for g_atom in g_rw.GetAtoms():
                new_idx = rw.AddAtom(Chem.Atom(g_atom.GetSymbol()))
                map_idx[g_atom.GetIdx()] = new_idx

            for g_bond in g_rw.GetBonds():
                rw.AddBond(
                    map_idx[g_bond.GetBeginAtomIdx()],
                    map_idx[g_bond.GetEndAtomIdx()],
                    g_bond.GetBondType()
                )

            # Sambungkan atom attachment gugus (atom 0) ke atom induk terpilih
            try:
                rw.AddBond(a_idx, map_idx[0], Chem.BondType.SINGLE)
                mol_baru = rw.GetMol()
                Chem.SanitizeMol(mol_baru)
                smi_baru = Chem.MolToSmiles(mol_baru)

                if smi_baru not in smiles_unik:
                    smiles_unik.add(smi_baru)
                    desc_mod = f"+{label_gugus} pada {simbol_atom}{nomor_atom}"
                    hasil.append(_evaluasi_molekul(mol_baru, f"{nama_awal}_G{counter}", desc_mod))
                    counter += 1
                    if len(hasil) >= maks_hasil:
                        return hasil
            except Exception as e:
                catat.log.debug(f"Gagal menumbuhkan fragmen dengan {label_gugus}: {e}")
                continue

    return hasil


def sambung_fragmen(
    smiles_a: str,
    smiles_b: str,
    nama_a: str = "Fragmen_A",
    nama_b: str = "Fragmen_B",
    maks_hasil: int = 25
) -> List[Dict[str, Any]]:
    """Fragment Linking: hubungkan dua fragmen dengan berbagai jenis rantai linker."""
    ma = Chem.MolFromSmiles(smiles_a.strip().split()[0])
    mb = Chem.MolFromSmiles(smiles_b.strip().split()[0])
    if not ma or not mb:
        return []

    hasil = []
    smiles_unik = set()

    # Cari kandidat atom penyambung pada masing-masing fragmen
    cand_a = [a.GetIdx() for a in ma.GetAtoms() if a.GetSymbol() in ("C", "N") and a.GetTotalNumHs() > 0]
    cand_b = [b.GetIdx() for b in mb.GetAtoms() if b.GetSymbol() in ("C", "N") and b.GetTotalNumHs() > 0]

    # Batasi kombinasi agar tetap cepat dan relevan
    cand_a = cand_a[:3]
    cand_b = cand_b[:3]

    counter = 1
    for label_l, smi_l in LINKER_LIST:
        m_link = Chem.MolFromSmiles(smi_l)
        if not m_link:
            continue

        for idx_a in cand_a:
            for idx_b in cand_b:
                rw = Chem.RWMol()

                # 1. Salin fragmen A
                map_a = {}
                for at in ma.GetAtoms():
                    map_a[at.GetIdx()] = rw.AddAtom(Chem.Atom(at.GetSymbol()))
                for b in ma.GetBonds():
                    rw.AddBond(map_a[b.GetBeginAtomIdx()], map_a[b.GetEndAtomIdx()], b.GetBondType())

                # 2. Salin Linker
                map_l = {}
                for at in m_link.GetAtoms():
                    map_l[at.GetIdx()] = rw.AddAtom(Chem.Atom(at.GetSymbol()))
                for b in m_link.GetBonds():
                    rw.AddBond(map_l[b.GetBeginAtomIdx()], map_l[b.GetEndAtomIdx()], b.GetBondType())

                # 3. Salin fragmen B
                map_b = {}
                for at in mb.GetAtoms():
                    map_b[at.GetIdx()] = rw.AddAtom(Chem.Atom(at.GetSymbol()))
                for b in mb.GetBonds():
                    rw.AddBond(map_b[b.GetBeginAtomIdx()], map_b[b.GetEndAtomIdx()], b.GetBondType())

                # 4. Buat ikatan A <-> Linker <-> B
                try:
                    ujung_l_1 = map_l[0]
                    ujung_l_2 = map_l[m_link.GetNumAtoms() - 1]
                    rw.AddBond(map_a[idx_a], ujung_l_1, Chem.BondType.SINGLE)
                    rw.AddBond(ujung_l_2, map_b[idx_b], Chem.BondType.SINGLE)

                    mol_hybrid = rw.GetMol()
                    Chem.SanitizeMol(mol_hybrid)
                    smi_res = Chem.MolToSmiles(mol_hybrid)

                    if smi_res not in smiles_unik:
                        smiles_unik.add(smi_res)
                        desc_link = f"Jembatan {label_l}"
                        hasil.append(_evaluasi_molekul(mol_hybrid, f"Linked_{counter}", desc_link))
                        counter += 1
                        if len(hasil) >= maks_hasil:
                            return hasil
                except Exception as e:
                    catat.log.debug(f"Gagal menyambung fragmen dengan linker {label_l}: {e}")
                    continue

    return hasil
