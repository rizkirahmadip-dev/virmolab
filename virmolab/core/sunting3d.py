"""Sunting ligan di dalam kantong: tumbuhkan atau ganti gugus pada pose, lalu nilai langsung di tempat.

Alur kerjanya seperti papan gambar SeeSAR/Maestro versi kecil: pose yang sudah ada dipertahankan sebagai inti,
gugus baru hanya ditambahkan pada satu atom yang dipilih, konformasi anak dibuat dengan embedding terkekang
(ConstrainedEmbed) sehingga atom inti tetap di tempatnya, lalu Vina --local_only meminimisasi gugus baru dan
memberi skor. Yang berubah dengan cepat hanyalah gugus barunya, jadi perbandingan ΔG antar usulan masuk akal
walau tidak sekuat docking ulang penuh.

Yang dilaporkan per usulan: ΔG Vina lokal, selisihnya terhadap induk (ΔΔG), efisiensi ligan, jumlah atom yang
menabrak protein sebelum minimisasi, dan sifat dasar (MW, logP, QED, SAScore). Skor lokal ini bukan afinitas
terukur; usulan terbaik tetap perlu didocking ulang dan diuji.
"""
import time
from dataclasses import dataclass, field

TITIK_TUMBUH = "[H]"            # gugus menggantikan satu hidrogen pada atom terpilih
# (label, SMILES gugus, singkatan). Gugus kecil yang lazim dipakai saat mengoptimalkan hit.
GUGUS = [
    ("Metil (–CH₃)", "C", "Me"),
    ("Etil (–C₂H₅)", "CC", "Et"),
    ("Isopropil", "C(C)C", "iPr"),
    ("Siklopropil", "C1CC1", "cPr"),
    ("Fluoro (–F)", "F", "F"),
    ("Kloro (–Cl)", "Cl", "Cl"),
    ("Bromo (–Br)", "Br", "Br"),
    ("Hidroksi (–OH)", "O", "OH"),
    ("Metoksi (–OCH₃)", "OC", "OMe"),
    ("Trifluorometil (–CF₃)", "C(F)(F)F", "CF3"),
    ("Amino (–NH₂)", "N", "NH2"),
    ("Metilamino", "NC", "NHMe"),
    ("Dimetilamino", "N(C)C", "NMe2"),
    ("Asetamido", "NC(C)=O", "NHAc"),
    ("Karboksamida (–CONH₂)", "C(N)=O", "CONH2"),
    ("Karboksilat (–COOH)", "C(O)=O", "COOH"),
    ("Ester metil", "C(=O)OC", "CO2Me"),
    ("Siano (–CN)", "C#N", "CN"),
    ("Nitro (–NO₂)", "[N+]([O-])=O", "NO2"),
    ("Sulfonamida (–SO₂NH₂)", "S(N)(=O)=O", "SO2NH2"),
    ("Metilsulfonil", "S(C)(=O)=O", "SO2Me"),
    ("Fenil", "c1ccccc1", "Ph"),
    ("4-Fluorofenil", "c1ccc(F)cc1", "4F-Ph"),
    ("4-Piridil", "c1ccncc1", "4-Py"),
    ("Morfolino", "N1CCOCC1", "morfolin"),
    ("Piperazinil", "N1CCNCC1", "piperazin"),
    ("Imidazolil", "n1ccnc1", "imidazol"),
    ("Tetrazolil", "c1nnn[nH]1", "tetrazol"),
    ("Hidroksimetil", "CO", "CH2OH"),
    ("Aminometil", "CN", "CH2NH2"),
]
# Penggantian seluruh gugus fungsi (bioisoster) pada pose: SMARTS reaksi dijalankan di tempat.
BIOISOSTER = [
    ("Karboksilat → tetrazol", "[*:1]C(=O)[OH]>>[*:1]c1nnn[nH]1"),
    ("Karboksilat → amida primer", "[*:1]C(=O)[OH]>>[*:1]C(N)=O"),
    ("Karboksilat → asilsulfonamida", "[*:1]C(=O)[OH]>>[*:1]C(=O)NS(C)(=O)=O"),
    ("Amida → sulfonamida", "[*:1]C(=O)N([H])[*:2]>>[*:1]S(=O)(=O)N([H])[*:2]"),
    ("Ester → amida", "[*:1]C(=O)O[C:2]>>[*:1]C(=O)N[C:2]"),
    ("Fenil → 4-piridil", "[*:1]c1ccccc1>>[*:1]c1ccncc1"),
    ("Fenil → 3-piridil", "[*:1]c1ccccc1>>[*:1]c1cccnc1"),
    ("Kloro → trifluorometil", "[c:1]Cl>>[c:1]C(F)(F)F"),
    ("Metil → trifluorometil", "[c:1]C([H])([H])[H]>>[c:1]C(F)(F)F"),
    ("Fenol → anilin", "[c:1][OH]>>[c:1]N"),
    ("Eter → tioeter", "[*:1]O[C:2]>>[*:1]S[C:2]"),
    ("Metilena → eter", "[*:1][CH2][*:2]>>[*:1]O[*:2]"),
]
JARAK_TABRAK = 1.7              # atom berat ligan sedekat ini ke protein dihitung sebagai tabrakan


class GalatSunting(Exception):
    pass


@dataclass
class Usulan:
    nama: str
    smiles: str = ""
    perubahan: str = ""
    energi: float = None            # ΔG Vina lokal (kkal/mol)
    d_energi: float = None          # selisih terhadap induk
    le: float = None                # efisiensi ligan
    tabrakan: int = 0               # atom berat yang menabrak protein sebelum minimisasi
    mw: float = None
    logp: float = None
    qed: float = None
    sascore: float = None
    atom: int = 0
    status: str = "ok"              # ok | gagal
    alasan: str = ""
    sdf: str = ""                   # pose hasil minimisasi lokal (SDF)
    detik: float = 0.0
    catatan: list = field(default_factory=list)

    def ke_dict(self):
        d = dict(self.__dict__)
        d.pop("sdf")
        return d


# ------------------------------------------------------------------ titik tumbuh
def titik_tumbuh(mol):
    """Atom berat yang masih punya hidrogen -> [(indeks atom berat, label 'C7', jumlah H)].

    Indeks mengacu pada molekul tanpa hidrogen eksplisit, sama seperti yang dipakai gambar 2D."""
    from rdkit import Chem
    m = Chem.RemoveHs(mol)
    hasil = []
    for a in m.GetAtoms():
        if a.GetAtomicNum() > 1 and a.GetTotalNumHs() > 0:
            hasil.append((a.GetIdx(), f"{a.GetSymbol()}{a.GetIdx() + 1}", a.GetTotalNumHs()))
    return hasil


def _sambung(mol_tanpa_h, idx, smiles_gugus):
    """Sambungkan gugus pada atom idx (menggantikan satu H implisit) -> Mol 2D tanpa koordinat."""
    from rdkit import Chem
    gugus = Chem.MolFromSmiles(smiles_gugus)
    if gugus is None:
        raise GalatSunting(f"SMILES gugus tidak valid: {smiles_gugus}")
    rw = Chem.RWMol(mol_tanpa_h)
    peta = {}
    for a in gugus.GetAtoms():
        baru = Chem.Atom(a.GetAtomicNum())
        baru.SetFormalCharge(a.GetFormalCharge())
        baru.SetIsAromatic(a.GetIsAromatic())
        baru.SetNoImplicit(a.GetNoImplicit())
        baru.SetNumExplicitHs(a.GetNumExplicitHs())
        peta[a.GetIdx()] = rw.AddAtom(baru)
    for b in gugus.GetBonds():
        rw.AddBond(peta[b.GetBeginAtomIdx()], peta[b.GetEndAtomIdx()], b.GetBondType())
        if b.GetIsAromatic():
            rw.GetBondBetweenAtoms(peta[b.GetBeginAtomIdx()], peta[b.GetEndAtomIdx()]).SetIsAromatic(True)
    a_induk = rw.GetAtomWithIdx(idx)
    if a_induk.GetNumExplicitHs():
        a_induk.SetNumExplicitHs(a_induk.GetNumExplicitHs() - 1)
    rw.AddBond(idx, peta[0], Chem.BondType.SINGLE)
    m = rw.GetMol()
    Chem.SanitizeMol(m)
    return m


def _reaksi(mol_tanpa_h, smarts):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    rxn = AllChem.ReactionFromSmarts(smarts)
    if rxn is None:
        raise GalatSunting(f"SMARTS reaksi tidak valid: {smarts}")
    produk = rxn.RunReactants((mol_tanpa_h,))
    keluar, terlihat = [], set()
    for p in produk:
        m = p[0]
        try:
            Chem.SanitizeMol(m)
        except Exception:
            continue
        smi = Chem.MolToSmiles(m)
        if smi in terlihat:
            continue
        terlihat.add(smi)
        keluar.append(m)
    return keluar


def _embed_terkekang(anak, induk_3d, seed=42):
    """Konformasi anak dengan atom inti dipaku pada koordinat pose induk."""
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdFMCS
    from rdkit.Chem import rdMolAlign
    induk = Chem.RemoveHs(Chem.Mol(induk_3d))
    anak = Chem.AddHs(Chem.Mol(anak))
    res = rdFMCS.FindMCS([Chem.RemoveHs(Chem.Mol(anak)), induk], timeout=10,
                         ringMatchesRingOnly=True, completeRingsOnly=True)
    if res.canceled or res.numAtoms < 4:
        raise GalatSunting("Inti bersama dengan pose induk terlalu kecil untuk mempertahankan pose.")
    pola = Chem.MolFromSmarts(res.smartsString)
    cocok_anak = anak.GetSubstructMatch(pola)
    cocok_induk = induk.GetSubstructMatch(pola)
    if not cocok_anak or not cocok_induk:
        raise GalatSunting("Inti bersama tidak bisa dipetakan ke pose induk.")
    koordinat = {ia: induk.GetConformer().GetAtomPosition(ii) for ia, ii in zip(cocok_anak, cocok_induk)}
    prm = AllChem.ETKDGv3()
    prm.randomSeed = seed
    prm.useRandomCoords = True
    prm.SetCoordMap({k: v for k, v in koordinat.items()})
    if AllChem.EmbedMolecule(anak, prm) != 0:
        prm.SetCoordMap({})
        if AllChem.EmbedMolecule(anak, prm) != 0:
            raise GalatSunting("Konformasi 3D gugus baru gagal dibuat.")
    ff = AllChem.MMFFGetMoleculeForceField(anak, AllChem.MMFFGetMoleculeProperties(anak))
    if ff is not None:
        for ia in cocok_anak:                       # atom inti dipaku, gugus baru bebas dioptimasi
            ff.AddFixedPoint(ia)
        ff.Minimize(maxIts=500)
    rdMolAlign.AlignMol(anak, induk, atomMap=list(zip(cocok_anak, cocok_induk)))
    return anak, len(cocok_anak)


# ------------------------------------------------------------------ penilaian
def _sifat(mol):
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, QED
    m = Chem.RemoveHs(mol)
    d = {"mw": round(Descriptors.MolWt(m), 1), "logp": round(Crippen.MolLogP(m), 2),
         "qed": round(QED.qed(m), 3), "atom": m.GetNumHeavyAtoms()}
    try:
        from . import sascore
        d["sascore"] = round(sascore.hitung_sascore(m), 2)
    except Exception:
        d["sascore"] = None
    return d


def nilai(mol_3d, pdbqt_reseptor, teks_pdb_reseptor="", timeout=180):
    """Minimisasi lokal Vina pada pose -> (energi, Mol hasil minimisasi, tabrakan sebelum minimisasi)."""
    from rdkit import Chem
    from . import lokal, senyawa
    tabrak = senyawa.tabrakan(mol_3d, teks_pdb_reseptor, JARAK_TABRAK) if teks_pdb_reseptor else 0
    energi, pose = lokal.minimisasi_lokal(pdbqt_reseptor, lokal.pdbqt_pose(mol_3d), timeout=timeout,
                                          kembalikan=True)
    mol_baru = None
    if pose:
        try:
            from . import analisis
            mol_baru = analisis.pose_mol(lokal.pdbqt_pose(mol_3d), pose)
        except Exception:
            mol_baru = None
    return energi, (mol_baru if mol_baru is not None else Chem.Mol(mol_3d)), tabrak


def induk(mol_3d, pdbqt_reseptor, teks_pdb_reseptor="", nama="Pose induk"):
    """Skor acuan: pose yang sedang dipakai, diminimisasi lokal dengan cara yang sama seperti usulan."""
    from rdkit import Chem
    t0 = time.time()
    u = Usulan(nama=nama, smiles=Chem.MolToSmiles(Chem.RemoveHs(mol_3d)), perubahan="induk")
    u.__dict__.update(_sifat(mol_3d))
    try:
        e, mol, tabrak = nilai(mol_3d, pdbqt_reseptor, teks_pdb_reseptor)
        u.energi, u.tabrakan, u.d_energi = round(e, 2), tabrak, 0.0
        u.le = round(-e / u.atom, 3) if u.atom else None
        u.sdf = _sdf(mol, nama)
    except Exception as ex:
        u.status, u.alasan = "gagal", str(ex).splitlines()[0][:200]
    u.detik = round(time.time() - t0, 1)
    return u


def _sdf(mol, nama):
    from rdkit import Chem
    m = Chem.Mol(mol)
    m.SetProp("_Name", nama)
    return Chem.MolToMolBlock(m)


def usulan_tumbuh(mol_3d, idx_atom, gugus=None, maks=None):
    """[(label, perubahan, Mol 2D)] untuk tiap gugus yang disambungkan pada atom idx_atom."""
    from rdkit import Chem
    m = Chem.RemoveHs(Chem.Mol(mol_3d))
    if idx_atom >= m.GetNumAtoms():
        raise GalatSunting("Atom yang dipilih tidak ada pada ligan ini.")
    a = m.GetAtomWithIdx(idx_atom)
    if a.GetTotalNumHs() < 1:
        raise GalatSunting(f"Atom {a.GetSymbol()}{idx_atom + 1} tidak punya hidrogen untuk diganti.")
    label_atom = f"{a.GetSymbol()}{idx_atom + 1}"
    keluar, terlihat = [], {Chem.MolToSmiles(m)}
    for label, smi, singkat in (gugus or GUGUS)[:maks or len(GUGUS)]:
        try:
            baru = _sambung(m, idx_atom, smi)
        except Exception as e:
            keluar.append((label, f"+{singkat} pada {label_atom}", None, str(e).splitlines()[0][:150]))
            continue
        kanonik = Chem.MolToSmiles(baru)
        if kanonik in terlihat:
            continue
        terlihat.add(kanonik)
        keluar.append((label, f"+{singkat} pada {label_atom}", baru, ""))
    return keluar


def usulan_bioisoster(mol_3d, daftar=None):
    """[(label, perubahan, Mol 2D)] untuk tiap penggantian bioisosterik yang mengenai ligan."""
    from rdkit import Chem
    m = Chem.RemoveHs(Chem.Mol(mol_3d))
    keluar, terlihat = [], {Chem.MolToSmiles(m)}
    for label, smarts in (daftar or BIOISOSTER):
        try:
            produk = _reaksi(m, smarts)
        except GalatSunting:
            continue
        for i, p in enumerate(produk[:3], 1):
            kanonik = Chem.MolToSmiles(p)
            if kanonik in terlihat:
                continue
            terlihat.add(kanonik)
            keluar.append((label + (f" ({i})" if i > 1 else ""), label, p, ""))
    return keluar


def jalankan(mol_3d, usulan, pdbqt_reseptor, teks_pdb_reseptor="", energi_induk=None, lapor=None, batal=None,
             seed=42):
    """Bangun konformasi tiap usulan (inti dipaku pada pose induk) lalu nilai dengan Vina lokal.
    usulan: keluaran usulan_tumbuh / usulan_bioisoster. -> [Usulan]"""
    from rdkit import Chem
    hasil = []
    for i, (label, perubahan, mol2d, galat) in enumerate(usulan, 1):
        if batal is not None and batal():
            break
        u = Usulan(nama=label, perubahan=perubahan)
        if mol2d is None:
            u.status, u.alasan = "gagal", galat or "gugus tidak bisa disambungkan"
            hasil.append(u)
            continue
        t0 = time.time()
        u.smiles = Chem.MolToSmiles(Chem.RemoveHs(mol2d))
        u.__dict__.update(_sifat(mol2d))
        try:
            anak, n_inti = _embed_terkekang(mol2d, mol_3d, seed)
            u.catatan.append(f"{n_inti} atom inti dipertahankan dari pose induk")
            e, mol, tabrak = nilai(anak, pdbqt_reseptor, teks_pdb_reseptor)
            u.energi, u.tabrakan = round(e, 2), tabrak
            u.le = round(-e / u.atom, 3) if u.atom else None
            if energi_induk is not None:
                u.d_energi = round(e - energi_induk, 2)
            u.sdf = _sdf(mol, label)
        except Exception as ex:
            u.status, u.alasan = "gagal", str(ex).splitlines()[0][:200]
        u.detik = round(time.time() - t0, 1)
        hasil.append(u)
        if lapor is not None:
            lapor(i, len(usulan), u)
    return hasil


def teks_metode(n_usulan, n_ok, en=False):
    """Paragraf metode untuk naskah."""
    if en:
        return (f"Candidate analogues were generated directly on the docked pose: a substituent was attached to the "
                f"selected atom (or a functional group was replaced by a bioisostere), the analogue was embedded "
                f"with the shared core constrained to the parent pose coordinates (RDKit ETKDGv3 with a coordinate "
                f"map, followed by MMFF94 minimisation of the new group only), and the pose was then minimised in "
                f"place and scored with AutoDock Vina (--local_only). Of {n_usulan} analogues, {n_ok} were scored "
                f"successfully. These local scores rank suggestions against the parent pose; they are not binding "
                f"affinities, and promising analogues were redocked from scratch before any further conclusion.")
    return (f"Analog kandidat dibuat langsung pada pose docking: satu gugus disambungkan pada atom yang dipilih "
            f"(atau satu gugus fungsi diganti bioisosternya), konformasi analog dibuat dengan inti bersama dipaku "
            f"pada koordinat pose induk (RDKit ETKDGv3 dengan peta koordinat, lalu minimisasi MMFF94 hanya pada "
            f"gugus baru), kemudian pose diminimisasi di tempat dan dinilai dengan AutoDock Vina (--local_only). "
            f"Dari {n_usulan} analog, {n_ok} berhasil dinilai. Skor lokal ini memeringkat usulan terhadap pose "
            f"induk, bukan afinitas ikatan; analog yang menjanjikan didocking ulang dari awal sebelum ditarik "
            f"kesimpulan lebih jauh.")
