"""Docking kovalen (metode tethered / flexible side chain, Bianco dkk. 2016) untuk AutoDock-GPU.

Ligan direaksikan secara kimia dengan rantai samping residu sasaran (Cys/Ser/Lys) menjadi satu aduk
"residu + ligan". Aduk dijadikan residu fleksibel (akar = CA, CA-CB disejajarkan dengan struktur kristal),
reseptor kaku kehilangan rantai samping residu tsb, lalu AutoDock-GPU dijalankan dengan --flexres saja
(tanpa --lfile). Divalidasi pada 6OIM (KRAS G12C-sotorasib): pose kristal terulang, RMSD 1,11 Å
(dev/uji/kovalen/eksperimen.py).

Skor yang dilaporkan AutoDock-GPU untuk pose kovalen = energi internal residu fleksibel (aduk-reseptor + intra-aduk)
tanpa penalti torsi; bukan ΔG ikatan dan tidak sebanding dengan docking non-kovalen.
"""
import numpy as np

# atom rantai samping (urut dari CA ke atom nukleofil) dan fragmen SMILES yang sama urutannya
RESIDU = {
    "CYS": (("CA", "CB", "SG"), "CCS"),
    "SER": (("CA", "CB", "OG"), "CCO"),
    "LYS": (("CA", "CB", "CG", "CD", "CE", "NZ"), "CCCCCN"),
}
ALIAS = {"CYX": "CYS", "CYM": "CYS", "LYN": "LYS"}
PENANDA = "REMARK VIRMODOCK KOVALEN"     # baris penanda pada blok pose: "<PENANDA> <n atom residu>"

# gugus reaktif (warhead), urut prioritas. jenis:
#   adisi       : orde ikatan a1-a2 turun satu, nukleofil terikat ke a1 (akseptor Michael, nitril, aldehida)
#   substitusi  : atom a3 (gugus pergi) dibuang, nukleofil terikat ke a1
#   imina       : a2 (O) dibuang, nukleofil terikat rangkap ke a1 (basa Schiff Lys + aldehida)
WARHEAD = [
    ("michael", "akseptor Michael (akrilamida/enon/vinil sulfon)", "[CX3:1]=[CX3:2]-[$([CX3]=O),$([SX4](=O)=O),$(C#N)]",
     "adisi", ("CYS", "LYS")),
    ("propiolamida", "alkuna teraktivasi (propiolamida)", "[CX2:1]#[CX2:2]-[$([CX3]=O),$([SX4](=O)=O)]",
     "adisi", ("CYS",)),
    ("haloasetamida", "α-haloketon/haloasetamida", "[Cl,Br,I;X1:3]-[CH2X4:1]-[$([CX3]=O),$([SX4](=O)=O),$(c)]",
     "substitusi", ("CYS", "LYS")),
    ("sulfonil_fluorida", "sulfonil fluorida (SuFEx)", "[SX4:1](=O)(=O)-[F:3]", "substitusi", ("SER", "LYS")),
    ("nitril", "nitril (tioimidat/imidat reversibel)", "[CX2:1]#[NX1:2]", "adisi", ("CYS", "SER")),
    ("aldehida_imina", "aldehida → basa Schiff", "[CX3H1:1](=[OX1:2])[#6]", "imina", ("LYS",)),
    ("aldehida", "aldehida (hemitioasetal/hemiasetal)", "[CX3H1:1](=[OX1:2])[#6]", "adisi", ("CYS", "SER")),
    ("isotiosianat", "isotiosianat", "[NX2:2]=[CX2:1]=[SX1]", "adisi", ("CYS", "LYS")),
    ("ester_aktif", "ester aktif pada alkena (vinil ester/akrilat)", "[CX3:1]=[CX3:2]-[#8]-[#6]=O",
     "adisi", ("CYS",)),
]

# catatan untuk dialog, bukan ramalan laju reaksi
REAKTIVITAS = {
    "michael": "tinggi pada Cys; sering diperlakukan ireversibel",
    "propiolamida": "tinggi, khas inhibitor KRAS G12C",
    "haloasetamida": "tinggi; alfa-halokarbonil reaktif terhadap Cys dan Lys",
    "sulfonil_fluorida": "sedang-tinggi (SuFEx), lebih memilih Ser/Lys",
    "nitril": "rendah-sedang, sering reversibel",
    "aldehida_imina": "reversibel (basa Schiff) pada Lys",
    "aldehida": "reversibel (hemiacetal) pada Cys/Ser",
    "isotiosianat": "tinggi terhadap Cys; produk tiourea",
    "ester_aktif": "sedang; pastikan bukan ester biasa yang ikut tercocok",
}


def catatan_warhead(kunci):
    return REAKTIVITAS.get(kunci, "")


class GalatKovalen(Exception):
    pass


def resn_baku(resn):
    resn = (resn or "").upper()
    return ALIAS.get(resn, resn)


def calon_residu(teks_pdb, pusat, ukuran):
    """[(rantai, resi, resn, jarak_nukleofil_ke_pusat)] residu Cys/Ser/Lys yang atom nukleofilnya di dalam kotak."""
    hasil = []
    for b in teks_pdb.splitlines():
        if not b.startswith(("ATOM", "HETATM")):
            continue
        resn = resn_baku(b[17:20].strip())
        if resn not in RESIDU or b[12:16].strip() != RESIDU[resn][0][-1]:
            continue
        try:
            xyz = np.array([float(b[30:38]), float(b[38:46]), float(b[46:54])])
            resi = int(b[22:26])
        except ValueError:
            continue
        if all(abs(xyz[i] - pusat[i]) <= ukuran[i] / 2 for i in range(3)):
            hasil.append((b[21].strip(), resi, resn, float(np.linalg.norm(xyz - np.asarray(pusat)))))
    return sorted(hasil, key=lambda x: x[3])


def koordinat_residu(teks_pdb, rantai, resi):
    """{nama_atom: xyz} residu (rantai, resi) dari teks PDB; resn baku ikut dikembalikan."""
    atom, resn = {}, None
    for b in teks_pdb.splitlines():
        if not b.startswith(("ATOM", "HETATM")) or b[21].strip() != rantai:
            continue
        try:
            if int(b[22:26]) != int(resi):
                continue
            atom[b[12:16].strip()] = [float(b[30:38]), float(b[38:46]), float(b[46:54])]
        except ValueError:
            continue
        resn = resn_baku(b[17:20].strip())
    return atom, resn


def deteksi(mol, resn):
    """[(kunci, nama, jenis, peta{1: idx, 2: idx, 3: idx})] gugus reaktif pada ligan yang cocok untuk residu ini."""
    from rdkit import Chem
    resn = resn_baku(resn)
    m = Chem.RemoveHs(mol)
    hasil, dipakai = [], set()
    for kunci, nama, smarts, jenis, untuk in WARHEAD:
        if resn not in untuk:
            continue
        q = Chem.MolFromSmarts(smarts)
        peta_q = {a.GetAtomMapNum(): a.GetIdx() for a in q.GetAtoms() if a.GetAtomMapNum()}
        for cocok in m.GetSubstructMatches(q):
            peta = {k: cocok[i] for k, i in peta_q.items()}
            if peta[1] in dipakai:
                continue
            dipakai.add(peta[1])
            hasil.append((kunci, nama, jenis, peta))
    return hasil


def _bangun_aduk(lig, resn, wh):
    """Ligan tanpa H + fragmen residu -> Mol aduk (atom 0..n-1 = residu, CA dulu). Belum ber-H, belum 3D."""
    from rdkit import Chem
    _nama, smi = RESIDU[resn]
    frag = Chem.MolFromSmiles(smi)
    n = frag.GetNumAtoms()
    kunci, _n, jenis, peta = wh
    m = Chem.RWMol(Chem.CombineMols(frag, lig))
    nu, a1 = n - 1, n + peta[1]
    ubah, buang = {nu, a1}, None
    if jenis == "adisi":
        a2 = n + peta[2]
        ik = m.GetBondBetweenAtoms(a1, a2)
        ik.SetBondType({Chem.BondType.TRIPLE: Chem.BondType.DOUBLE,
                        Chem.BondType.DOUBLE: Chem.BondType.SINGLE}[ik.GetBondType()])
        ik.SetStereo(Chem.BondStereo.STEREONONE)
        ubah.add(a2)
        m.AddBond(nu, a1, Chem.BondType.SINGLE)
    elif jenis == "substitusi":
        m.AddBond(nu, a1, Chem.BondType.SINGLE)
        buang = n + peta[3]
    else:                                    # imina: C=O + H2N-R -> C=N-R + H2O
        m.AddBond(nu, a1, Chem.BondType.DOUBLE)
        buang = n + peta[2]
    for i in ubah:
        a = m.GetAtomWithIdx(i)
        a.SetNumExplicitHs(0)
        a.SetNoImplicit(False)
        a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
    ubah_ik = [m.GetBondBetweenAtoms(x, y) for x in ubah for y in range(m.GetNumAtoms())
               if m.GetBondBetweenAtoms(x, y) is not None]
    for ik in ubah_ik:                       # stereo ikatan rangkap di sekitar pusat reaksi tidak lagi sahih
        if ik.GetBondType() == Chem.BondType.DOUBLE:
            ik.SetStereo(Chem.BondStereo.STEREONONE)
    if buang is not None:
        for a in m.GetAtomWithIdx(buang).GetNeighbors():   # tetangga gugus pergi (selain a1 & nukleofil) ikut disegarkan
            a.SetNoImplicit(False)
        m.RemoveAtom(buang)
    m = m.GetMol()
    Chem.SanitizeMol(m)
    Chem.AssignStereochemistry(m, cleanIt=True, force=True)
    return m, n


def buat_aduk(mol, resn, ca, cb, kunci_warhead=None, seed=42):
    """Ligan (RDKit Mol) -> (aduk 3D ber-H dengan CA/CB di posisi kristal, n_atom_residu, nama_warhead)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdMolAlign
    resn = resn_baku(resn)
    if resn not in RESIDU:
        raise GalatKovalen(f"Residu {resn} belum didukung untuk docking kovalen (hanya Cys, Ser, Lys).")
    daftar = deteksi(mol, resn)
    if kunci_warhead:
        daftar = [w for w in daftar if w[0] == kunci_warhead] or daftar
    if not daftar:
        raise GalatKovalen(f"tidak ada gugus reaktif yang cocok untuk {resn}")
    wh = daftar[0]
    lig = Chem.RemoveHs(mol)
    aduk, n = _bangun_aduk(lig, resn, wh)
    aduk = Chem.AddHs(aduk)
    ps = AllChem.ETKDGv3()
    ps.randomSeed = seed
    if AllChem.EmbedMolecule(aduk, ps) != 0:
        ps.useRandomCoords = True
        if AllChem.EmbedMolecule(aduk, ps) != 0:
            raise GalatKovalen("konformasi 3D aduk gagal dibuat")
    try:
        AllChem.MMFFOptimizeMolecule(aduk, maxIters=500)
    except Exception:
        pass
    # sejajarkan sumbu CA-CB aduk ke CA-CB kristal (ditambah satu titik semu agar transformasi tertentu penuh)
    acuan = Chem.RWMol()
    for _ in range(2):
        acuan.AddAtom(Chem.Atom(6))
    acuan.AddBond(0, 1, Chem.BondType.SINGLE)
    acuan = acuan.GetMol()
    conf = Chem.Conformer(2)
    conf.SetAtomPosition(0, list(map(float, ca)))
    conf.SetAtomPosition(1, list(map(float, cb)))
    acuan.AddConformer(conf, assignId=True)
    rdMolAlign.AlignMol(aduk, acuan, atomMap=[(0, 0), (1, 1)])
    pos = aduk.GetConformer().GetPositions()
    if np.linalg.norm(pos[0] - np.asarray(ca)) > 0.3:
        raise GalatKovalen("penyejajaran CA-CB gagal")
    return aduk, n, wh[1]


def siapkan_ligan(teks_pdbqt_ligan, resn, rantai, resi, ca, cb, kunci_warhead=None):
    """PDBQT ligan siap docking -> (pdbqt_aduk, pdbqt_flexres, nama_warhead, n_atom_residu).

    pdbqt_aduk  : templat (REMARK SMILES aduk) untuk membangun ulang molekul dari pose.
    pdbqt_flexres: blok BEGIN_RES <resn> <rantai> <resi> … END_RES untuk AutoDock-GPU --flexres.
    """
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from . import analisis
    badan = "\n".join(b for b in teks_pdbqt_ligan.splitlines() if not b.startswith("REMARK"))
    mol = analisis.pose_mol(teks_pdbqt_ligan, badan)
    aduk, n, nama = buat_aduk(mol, resn, ca, cb, kunci_warhead)
    setup = MoleculePreparation().prepare(aduk, root_atom_index=0, not_terminal_atoms=[0])[0]
    pdbqt, ok, err = PDBQTWriterLegacy.write_string(setup)
    if not ok:
        raise GalatKovalen("Meeko gagal menulis aduk: " + str(err)[:200])
    flex = PDBQTWriterLegacy.adapt_pdbqt_for_autodock4_flexres(pdbqt, resn_baku(resn), rantai or " ", str(resi))
    return pdbqt, flex if flex.endswith("\n") else flex + "\n", nama, n


def ubah_pose(flex_baris):
    """Blok BEGIN_RES…END_RES aduk dari DLG -> (badan pose untuk ligan, blok residu fleksibel CA…nukleofil).

    Badan pose diawali baris PENANDA sehingga pose_ke_pdb / pose_mol tahu n atom pertama adalah residu.
    Mengembalikan None bila blok bukan aduk kovalen.
    """
    kepala = next((b for b in flex_baris if b.startswith("BEGIN_RES")), None)
    if kepala is None or not any(b.startswith("REMARK SMILES") for b in flex_baris):
        return None
    s = kepala.split()
    if len(s) < 4 or resn_baku(s[1]) not in RESIDU:
        return None
    nama = RESIDU[resn_baku(s[1])][0]
    resn, rantai = s[1], s[2] if len(s) >= 4 else " "
    try:
        resi = int(s[3])
    except ValueError:
        return None
    badan = [f"{PENANDA} {len(nama)}"] + [b for b in flex_baris if not b.startswith(("BEGIN_RES", "END_RES", "REMARK"))]
    res, k = [kepala], 0
    for b in badan:
        if k < len(nama) and b.startswith(("ATOM", "HETATM")) and not _hidrogen(b):
            nm = nama[k]
            res.append(b[:12] + (f" {nm:<3}" if len(nm) < 4 else nm) + b[16] + f"{resn:>3}" + " " + (rantai or " ")[0]
                       + f"{resi:>4}" + b[26:])
            k += 1
    res.append(f"END_RES {resn} {rantai} {resi}")
    return "\n".join(badan), "\n".join(res)


def _hidrogen(b):
    tipe = b[77:].split()[0] if len(b) > 77 and b[77:].split() else ""
    return tipe.upper() in ("H", "HD", "HS")


def n_residu(pose_pdbqt):
    """Jumlah atom residu di awal blok pose kovalen (0 bila bukan pose kovalen)."""
    for b in pose_pdbqt.splitlines():
        if b.startswith(PENANDA):
            try:
                return int(b.split()[-1])
            except ValueError:
                return 0
        if b.startswith(("ATOM", "HETATM", "ROOT")):
            return 0
    return 0


def atom_residu(pose_pdbqt):
    """Indeks baris ATOM (urut kemunculan) yang merupakan atom residu (n atom berat pertama + H polarnya)."""
    n = n_residu(pose_pdbqt)
    if not n:
        return set()
    idx, k = set(), 0
    for i, b in enumerate(x for x in pose_pdbqt.splitlines() if x.startswith(("ATOM", "HETATM"))):
        if k < n and not _hidrogen(b):
            idx.add(i)
            k += 1
    return idx


def lepas_residu(mol, pose_pdbqt):
    """Mol aduk dari pose -> Mol ligan saja (atom residu dibuang, valensi atom pengikat dilengkapi H)."""
    from rdkit import Chem
    n = n_residu(pose_pdbqt)
    if not n or mol is None:
        return mol
    atom = [b for b in pose_pdbqt.splitlines() if b.startswith(("ATOM", "HETATM"))]
    xyz_res = []
    for i in sorted(atom_residu(pose_pdbqt)):
        b = atom[i]
        xyz_res.append([float(b[30:38]), float(b[38:46]), float(b[46:54])])
    pos = mol.GetConformer().GetPositions()
    buang = set()
    for p in xyz_res:
        d = np.linalg.norm(pos - np.asarray(p), axis=1)
        i = int(d.argmin())
        if d[i] < 0.05:
            buang.add(i)
    if len(buang) != n:
        raise ValueError("Atom residu pada pose kovalen tidak ditemukan.")
    for i in list(buang):
        buang |= {a.GetIdx() for a in mol.GetAtomWithIdx(i).GetNeighbors() if a.GetAtomicNum() == 1}
    pengikat = {a.GetIdx() for i in buang for a in mol.GetAtomWithIdx(i).GetNeighbors()} - buang
    m = Chem.RWMol(mol)
    for i in pengikat:
        a = m.GetAtomWithIdx(i)
        a.SetNoImplicit(False)
        a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
    peta = {}
    sisa = [i for i in range(mol.GetNumAtoms()) if i not in buang]
    for baru, lama in enumerate(sisa):
        peta[lama] = baru
    for i in sorted(buang, reverse=True):
        m.RemoveAtom(i)
    m = m.GetMol()
    Chem.SanitizeMol(m)
    return Chem.AddHs(m, addCoords=True, onlyOnAtoms=[peta[i] for i in pengikat if i in peta] or None)


# ------------------------------------------------------------------ alur proyek
def siapkan_reseptor(teks_meeko, teks_pdbqt, residu):
    """Reseptor kaku tanpa rantai samping residu sasaran + data residu.
    -> {residu, resn, kaku_teks, ca, cb}. residu: 'A:12'."""
    from .prep_reseptor import buat_fleksibel
    rantai, _, resi = residu.partition(":")
    atom, resn = koordinat_residu(teks_meeko, rantai, resi)
    if resn not in RESIDU:
        raise GalatKovalen(f"Residu {residu} ({resn or 'tidak ditemukan'}) bukan Cys, Ser, atau Lys.")
    nama = RESIDU[resn][0]
    hilang = [n for n in nama if n not in atom]
    if hilang:
        raise GalatKovalen(f"Atom {', '.join(hilang)} residu {resn}{resi} {rantai} tidak ada di struktur "
                           "(rantai samping tidak lengkap). Lengkapi residu saat preparasi reseptor.")
    kaku, _flex, ok, gagal = buat_fleksibel(teks_meeko, teks_pdbqt, [residu])
    if residu not in ok:
        raise GalatKovalen("Rantai samping residu sasaran gagal dipisah: " + "; ".join(gagal))
    return {"residu": residu, "resn": resn, "kaku_teks": kaku, "ca": atom["CA"], "cb": atom["CB"]}


def siapkan_ligan_job(proyek, ligan, kv, lapor=None):
    """Buat aduk kovalen tiap ligan -> (salinan ligan dengan pdbqt=aduk & flex_kov, [(nama, alasan) dilewati]).
    Berkas di kovalen/<rantai><resi>/; kv = proyek.reseptor['kovalen']."""
    rantai, _, resi = kv["residu"].partition(":")
    folder = proyek.p("kovalen", f"{rantai}{resi}")
    folder.mkdir(parents=True, exist_ok=True)
    hasil, lewat = [], []
    for i, l in enumerate(ligan):
        if lapor:
            lapor.progres.emit(i, len(ligan), f"Aduk kovalen {l['nama']}")
        try:
            teks = proyek.p(l["pdbqt"]).read_text()
            aduk, flex, nama, _n = siapkan_ligan(teks, kv["resn"], rantai, resi, kv["ca"], kv["cb"])
        except GalatKovalen as e:
            lewat.append((l["nama"], str(e)))
            continue
        except Exception as e:     # ligan aneh tidak boleh menggagalkan seluruh job
            lewat.append((l["nama"], f"aduk gagal dibuat ({str(e).strip().splitlines()[0][:120] if str(e).strip() else type(e).__name__})"))
            continue
        fa, ff = folder / f"{l['id']}_aduk.pdbqt", folder / f"{l['id']}_flex.pdbqt"
        fa.write_text(aduk, encoding="utf-8")
        ff.write_text(flex, encoding="utf-8")
        hasil.append(dict(l, pdbqt=proyek.rel(fa), flex_kov=proyek.rel(ff), warhead=nama))
    return hasil, lewat
