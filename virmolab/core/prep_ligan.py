"""Preparasi ligan (batch): protonasi pH, 3D, minimisasi, torsi, PDBQT (Meeko).

Satu ligan gagal tidak menghentikan yang lain: setiap hasil membawa status
dan alasan yang bisa dibaca pengguna.
"""
import io
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import redirect_stderr
from dataclasses import asdict, dataclass, field

MAKS_TORSI_GPU = 32
MAKS_ATOM_GPU = 256
TIPE_DIDUKUNG = {"C", "A", "N", "NA", "NS", "OA", "OS", "SA", "S", "HD", "HS", "H", "P", "F", "Cl", "CL", "Br", "BR",
                 "I", "Si", "Fe", "Zn", "Mg", "Mn", "Ca", "Cu"}


@dataclass
class OpsiLigan:
    ph: float = 7.4
    protonasi: bool = True
    metode_ph: str = "obabel"      # obabel | dimorphite
    varian: int = 1                 # Dimorphite-DL: >1 = enumerasi keadaan protonasi pada pH ± 1 (ligan terpisah)
    minimisasi: bool = True
    langkah: int = 500
    makrosiklik_kaku: bool = False


@dataclass
class HasilLigan:
    nama: str
    status: str = "gagal"          # siap | peringatan | gagal
    alasan: str = ""
    pdbqt: str = ""
    sdf: str = ""                   # struktur 3D setelah preparasi (untuk viewer & referensi)
    rumus: str = ""
    mw: float = 0.0
    torsi: int = 0
    atom: int = 0
    muatan: int = 0
    tipe: list = field(default_factory=list)
    asal: int = -1                  # indeks masukan (enumerasi varian: beberapa hasil per masukan)

    def ke_dict(self):
        d = asdict(self)
        d.pop("pdbqt")
        d.pop("sdf")
        d.pop("asal")
        return d


def _dari_pdb(teks):
    """Ligan kristal (PDB tanpa orde ikatan) -> RDKit lewat Open Babel."""
    from rdkit import Chem
    from . import obabel
    blok = obabel.konversi(teks, "pdb", "mol")
    mol = Chem.MolFromMolBlock(blok, removeHs=False)
    if mol is None:
        mol = Chem.MolFromMolBlock(blok, removeHs=False, sanitize=False)
        if mol is None:
            raise ValueError("Struktur ligan dari PDB tidak bisa dibaca.")
        Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
    return mol


def mol_dari(teks, fmt):
    from rdkit import Chem
    if fmt in ("sdf", "mol"):
        mol = Chem.MolFromMolBlock(teks, removeHs=False)
    elif fmt == "mol2":
        mol = Chem.MolFromMol2Block(teks, removeHs=False)
    elif fmt == "smiles":
        mol = Chem.MolFromSmiles(teks)
    else:
        mol = _dari_pdb(teks)
    if mol is None:
        raise ValueError("Molekul tidak valid (gagal dibaca RDKit).")
    return mol


def _protonasi(mol, ph):
    """Protonasi pada pH tertentu lewat Open Babel, koordinat atom berat dipertahankan."""
    from rdkit import Chem
    from . import obabel
    blok = Chem.MolToMolBlock(Chem.RemoveHs(mol))
    try:
        baru = Chem.MolFromMolBlock(obabel.konversi(blok, "mol", "mol", ["-d", "-p", f"{ph:g}"]), removeHs=False)
    except obabel.GalatObabel:
        baru = None
    if baru is None:
        return mol, "protonasi pH gagal, memakai struktur asli"
    return baru, ""


def dimorphite_tersedia():
    try:
        import dimorphite_dl
        _ = dimorphite_dl
        return True
    except Exception:
        return False


def _muatan_dari(mol, smiles_varian):
    """Salin muatan formal varian (SMILES Dimorphite-DL) ke molekul asli: koordinat atom berat dipertahankan."""
    from rdkit import Chem
    asli = Chem.RemoveHs(mol)
    var = Chem.MolFromSmiles(smiles_varian)
    if var is None:
        return None

    def netral(m):
        q = Chem.RWMol(m)
        for a in q.GetAtoms():
            a.SetFormalCharge(0)
            a.SetNumExplicitHs(0)
            a.SetNoImplicit(False)
        q.UpdatePropertyCache(strict=False)
        return q
    pasang = netral(asli).GetSubstructMatch(netral(var), useChirality=False)
    if len(pasang) != var.GetNumAtoms() or var.GetNumAtoms() != asli.GetNumAtoms():
        return None
    baru = Chem.RWMol(asli)
    for i_var, i_asli in enumerate(pasang):
        q = var.GetAtomWithIdx(i_var).GetFormalCharge()
        a = baru.GetAtomWithIdx(i_asli)
        if a.GetFormalCharge() != q:
            a.SetFormalCharge(q)
            a.SetNumExplicitHs(0)
            a.SetNoImplicit(False)
    Chem.SanitizeMol(baru)
    return baru.GetMol()


def varian_dimorphite(mol, ph, maks=1):
    """Keadaan protonasi Dimorphite-DL (Apache-2.0). maks=1: satu keadaan pada pH tepat (presisi 0);
    maks>1: semua keadaan pada pH ± 1 (presisi 1 SD), dibatasi `maks`. Kembalikan list Mol (koordinat asli)."""
    from rdkit import Chem
    from dimorphite_dl import protonate_smiles
    import logging
    try:
        from loguru import logger
        logger.disable("dimorphite_dl")
    except Exception:
        pass   # loguru opsional: kalau tidak ada, cukup diamkan lewat logging bawaan di baris berikut
    logging.getLogger("dimorphite_dl").setLevel(logging.ERROR)
    smi = Chem.MolToSmiles(Chem.RemoveHs(mol))
    if maks <= 1:
        hasil = protonate_smiles(smi, ph_min=ph, ph_max=ph, precision=0.0)[:1]   # max_variants=1 memotong ke masukan netral
    else:
        hasil = protonate_smiles(smi, ph_min=ph - 1, ph_max=ph + 1, precision=1.0, max_variants=maks)
    out = []
    for s in hasil or []:
        m = _muatan_dari(mol, s)
        if m is None:   # tidak bisa dipetakan: bangun ulang dari SMILES (koordinat dibuat ETKDG)
            m = Chem.MolFromSmiles(s)
        if m is not None:
            out.append(m)
    return out


def _3d(mol, minimisasi, langkah):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    catatan = []
    mol = Chem.AddHs(mol, addCoords=True)
    perlu = mol.GetNumConformers() == 0 or not mol.GetConformer().Is3D()
    if not perlu:  # SDF bertanda 3D tetapi datar (z = 0)
        zs = [p[2] for p in mol.GetConformer().GetPositions()]
        perlu = max(zs) - min(zs) < 1e-3
    if perlu:
        prm = AllChem.ETKDGv3()
        prm.randomSeed = 42
        Chem.GetSymmSSSR(mol)
        cincin = mol.GetRingInfo().AtomRings()
        if any(len(r) >= 7 for r in cincin):
            prm.useMacrocycleTorsions = True
            catatan.append("torsi makrosiklus (cincin ≥ 7)")
        if AllChem.EmbedMolecule(mol, prm) != 0:
            prm.useRandomCoords = True
            if AllChem.EmbedMolecule(mol, prm) != 0:
                raise ValueError("Gagal membuat koordinat 3D.")
        catatan.append("koordinat 3D dibuat (ETKDG)")
    if minimisasi:
        try:
            if AllChem.MMFFHasAllMoleculeParams(mol):
                AllChem.MMFFOptimizeMolecule(mol, maxIters=langkah)
                catatan.append("minimisasi MMFF94")
            else:
                AllChem.UFFOptimizeMolecule(mol, maxIters=langkah)
                catatan.append("minimisasi UFF (parameter MMFF tidak lengkap)")
        except Exception:
            catatan.append("minimisasi dilewati")
    return mol, catatan


def siapkan_satu(nama, teks, fmt, opsi):
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    h = HasilLigan(nama=nama)
    try:
        mol = mol_dari(teks, fmt)
        frag = Chem.GetMolFrags(mol, asMols=True)
        catatan = []
        if len(frag) > 1:  # garam/pelarut: ambil fragmen terbesar
            mol = max(frag, key=lambda m: m.GetNumHeavyAtoms())
            catatan.append("fragmen kecil (garam/pelarut) dibuang")
        if opsi.protonasi and opsi.metode_ph == "dimorphite" and getattr(opsi, "_mol_varian", None) is not None:
            mol = opsi._mol_varian       # varian Dimorphite-DL yang sudah dipilih di siapkan_banyak
            catatan.append(f"protonasi Dimorphite-DL pH {opsi.ph:g}")
        elif opsi.protonasi and opsi.metode_ph == "dimorphite":
            try:
                v = varian_dimorphite(mol, opsi.ph, 1)
                if v:
                    mol = v[0]
                    catatan.append(f"protonasi Dimorphite-DL pH {opsi.ph:g}")
                else:
                    catatan.append("Dimorphite-DL tanpa hasil, memakai struktur asli")
            except Exception as e:
                catatan.append(f"Dimorphite-DL gagal ({type(e).__name__}), memakai struktur asli")
        elif opsi.protonasi:
            mol, c = _protonasi(mol, opsi.ph)
            if c:
                catatan.append(c)
        Chem.SanitizeMol(mol)
        mol, c = _3d(mol, opsi.minimisasi, opsi.langkah)
        catatan += c
        prep = MoleculePreparation(rigid_macrocycles=opsi.makrosiklik_kaku)
        err = io.StringIO()
        with redirect_stderr(err):
            setups = prep.prepare(mol)
        pdbqt, ok, pesan = PDBQTWriterLegacy.write_string(setups[0])
        if not ok:
            raise ValueError(f"Meeko: {pesan.strip() or 'gagal menulis PDBQT'}")
        h.pdbqt = pdbqt
        mol.SetProp("_Name", nama)
        h.sdf = Chem.MolToMolBlock(mol)
        h.rumus = rdMolDescriptors.CalcMolFormula(mol)
        h.mw = round(Descriptors.MolWt(mol), 2)
        h.muatan = Chem.GetFormalCharge(mol)
        m = re.search(r"TORSDOF\s+(\d+)", pdbqt)
        h.torsi = int(m.group(1)) if m else 0
        baris = [b for b in pdbqt.splitlines() if b.startswith(("ATOM", "HETATM"))]
        h.atom = len(baris)
        h.tipe = sorted({b[77:].split()[0] for b in baris if b[77:].split()})
        masalah = []
        if h.torsi > MAKS_TORSI_GPU:
            masalah.append(f"{h.torsi} torsi > {MAKS_TORSI_GPU} (batas AutoDock-GPU; pakai Vina)")
        if h.atom > MAKS_ATOM_GPU:
            masalah.append(f"{h.atom} atom > {MAKS_ATOM_GPU} (batas AutoDock-GPU; pakai Vina)")
        aneh = [t for t in h.tipe if t not in TIPE_DIDUKUNG and not re.match(r"^C?G\d$", t)]
        if aneh:
            masalah.append("tipe atom tidak didukung AutoDock: " + ", ".join(aneh))
        h.status = "peringatan" if masalah else "siap"
        h.alasan = "; ".join(masalah + catatan)
    except Exception as e:
        h.status = "gagal"
        h.alasan = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    return h


def _uraikan_varian(daftar, opsi):
    """Enumerasi Dimorphite-DL: satu masukan -> beberapa (nama [vN], teks, fmt, opsi varian)."""
    from copy import copy
    from rdkit import Chem
    out = []
    for i, (n, t, f) in enumerate(daftar):
        try:
            mol = mol_dari(t, f)
            frag = Chem.GetMolFrags(mol, asMols=True)
            if len(frag) > 1:
                mol = max(frag, key=lambda m: m.GetNumHeavyAtoms())
            vs = varian_dimorphite(mol, opsi.ph, opsi.varian)
        except Exception:
            vs = []
        if len(vs) <= 1:
            o = copy(opsi)
            o._mol_varian = vs[0] if vs else None
            if not vs:
                o.metode_ph = "dimorphite"
            out.append((n, t, f, o, i))
            continue
        for k, m in enumerate(vs, 1):
            o = copy(opsi)
            o._mol_varian = m
            out.append((f"{n} [v{k}]", t, f, o, i))
    return out


def siapkan_banyak(daftar, opsi=None, lapor=None, pekerja=None):
    """daftar: [(nama, teks, fmt)]. Kembalikan list HasilLigan sesuai urutan masukan
    (enumerasi Dimorphite-DL dapat menambah baris: 'nama [v1]', 'nama [v2]', …)."""
    opsi = opsi or OpsiLigan()
    pekerja = pekerja or max(1, (os.cpu_count() or 2) // 2)
    if opsi.protonasi and opsi.metode_ph == "dimorphite":   # Dimorphite-DL tidak aman di thread: hitung di sini
        tugas = _uraikan_varian(daftar, opsi)
    else:
        tugas = [(n, t, f, opsi, i) for i, (n, t, f) in enumerate(daftar)]
    daftar = tugas
    hasil = [None] * len(daftar)
    with ThreadPoolExecutor(max_workers=pekerja) as ex:
        fut = {ex.submit(siapkan_satu, n, t, f, o): i for i, (n, t, f, o, _a) in enumerate(daftar)}
        for k, f in enumerate(as_completed(fut), 1):
            i = fut[f]
            hasil[i] = f.result()
            hasil[i].asal = daftar[i][4]
            if lapor:
                lapor.progres.emit(k, len(daftar), hasil[i].nama)
                lapor.log.emit(f"Ligan {hasil[i].nama}: {hasil[i].status}"
                               + (f" - {hasil[i].alasan}" if hasil[i].alasan else ""))
    return hasil
