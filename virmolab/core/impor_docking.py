"""Impor hasil docking dari program lain agar dianalisis seperti hasil docking VirmoLab.

Dibaca: PDBQT keluaran AutoDock Vina, QuickVina, Smina, GNINA, dan Uni-Dock (multi-MODEL, termasuk residu
fleksibel), DLG AutoDock4/AutoDock-GPU, SDF dan MOL2 multi-pose (GNINA, Smina, GOLD, Glide, rDock, MOE,
Discovery Studio, DiffDock), serta PDB kompleks atau multi-MODEL.

Setiap pose dibangun ulang menjadi RDKit Mol ber-H dengan orde ikatan benar, lalu disimpan sebagai job proyek
berformat PDBQT gaya Vina (Meeko). Tabel hasil, interaksi, diagram 2D, PoseBusters, MD, dan ekspor
memakai jalur yang sama dengan hasil docking internal.

Skor asli program disimpan apa adanya. Kolom ΔG hanya diisi skor berdimensi energi (kcal/mol). Bila program tidak
memberi energi (fitness GOLD, CNNscore, confidence DiffDock), ΔG diisi skor ulang Vina di tempat (--score_only)
dan sumbernya dicatat; fitness tidak pernah disamakan dengan ΔG.
"""
import io
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from . import catat

NOWIN = 0x08000000
EKSTENSI = (".pdbqt", ".dlg", ".sdf", ".sd", ".mol", ".mol2", ".pdb", ".ent")
EKSTENSI_RESEPTOR = (".pdbqt", ".pdb", ".ent", ".cif", ".mmcif", ".mol2")


class GalatImporDocking(Exception):
    pass


# ------------------------------------------------------------------ katalog skor
@dataclass(frozen=True)
class JenisSkor:
    tag: str
    label: str
    satuan: str = ""
    rendah: bool = True        # nilai kecil = pose lebih baik
    energi: bool = False       # setara ΔG docking (kcal/mol) sehingga boleh mengisi kolom ΔG
    program: str = ""
    faktor: float = 1.0        # pengali ke kcal/mol (ChemScore ΔG GOLD dilaporkan dalam kJ/mol)


KATALOG = [
    JenisSkor("vina", "Afinitas Vina", "kcal/mol", True, True, "AutoDock Vina"),
    JenisSkor("ad4", "ΔG AutoDock", "kcal/mol", True, True, "AutoDock4"),
    JenisSkor("minimizedAffinity", "Afinitas (minimized)", "kcal/mol", True, True, "Smina"),
    JenisSkor("CNNscore", "CNNscore", "", False, False, "GNINA"),
    JenisSkor("CNNaffinity", "CNNaffinity", "pK", False, False, "GNINA"),
    JenisSkor("CNN_VS", "CNN_VS", "", False, False, "GNINA"),
    JenisSkor("r_i_docking_score", "Docking score", "kcal/mol", True, True, "Glide"),
    JenisSkor("r_i_glide_gscore", "GlideScore", "kcal/mol", True, True, "Glide"),
    JenisSkor("r_i_glide_emodel", "Emodel", "kcal/mol", True, False, "Glide"),
    JenisSkor("Gold.PLP.Fitness", "ChemPLP fitness", "", False, False, "GOLD"),
    JenisSkor("Gold.Goldscore.Fitness", "GoldScore fitness", "", False, False, "GOLD"),
    JenisSkor("Gold.Chemscore.Fitness", "ChemScore fitness", "", False, False, "GOLD"),
    JenisSkor("Gold.ASP.Fitness", "ASP fitness", "", False, False, "GOLD"),
    JenisSkor("Gold.Chemscore.DG", "ChemScore ΔG", "kcal/mol", True, True, "GOLD", 1 / 4.184),
    JenisSkor("SCORE", "SCORE", "", True, False, "rDock"),
    JenisSkor("SCORE.INTER", "SCORE.INTER", "", True, False, "rDock"),
    JenisSkor("S", "Skor S", "kcal/mol", True, True, "MOE"),
    JenisSkor("E_refine", "E_refine", "kcal/mol", True, False, "MOE"),
    JenisSkor("-CDOCKER_ENERGY", "-CDOCKER energy", "kcal/mol", False, False, "Discovery Studio"),
    JenisSkor("-CDOCKER_INTERACTION_ENERGY", "-CDOCKER interaction energy", "kcal/mol", False, False,
              "Discovery Studio"),
    JenisSkor("LibDockScore", "LibDock score", "", False, False, "Discovery Studio"),
    JenisSkor("confidence", "Confidence", "", False, False, "DiffDock"),
    JenisSkor("docking_score", "Docking score", "kcal/mol", True, True, ""),
    JenisSkor("affinity", "Affinity", "kcal/mol", True, True, ""),
]
_KATALOG = {s.tag: s for s in KATALOG}
# skor utama bawaan per program (urutan prioritas)
UTAMA = ["vina", "ad4", "r_i_docking_score", "r_i_glide_gscore", "Gold.PLP.Fitness", "Gold.Goldscore.Fitness",
         "Gold.Chemscore.Fitness", "Gold.ASP.Fitness", "minimizedAffinity", "SCORE", "S",
         "-CDOCKER_INTERACTION_ENERGY", "-CDOCKER_ENERGY", "LibDockScore", "confidence", "docking_score",
         "affinity", "CNNscore"]
# tag SDF yang menandai berkas sebagai hasil docking (bukan sekadar pustaka ligan)
TAG_DOCKING = {"minimizedAffinity", "CNNscore", "r_i_docking_score", "r_i_glide_gscore", "Gold.PLP.Fitness",
               "Gold.Goldscore.Fitness", "Gold.Chemscore.Fitness", "Gold.ASP.Fitness", "SCORE", "SCORE.INTER",
               "-CDOCKER_ENERGY", "-CDOCKER_INTERACTION_ENERGY", "LibDockScore", "docking_score"}


def jenis_skor(tag):
    """Metadata skor; tag yang tidak dikenal dianggap skor tanpa satuan, kecil = baik, bukan energi."""
    return _KATALOG.get(tag) or JenisSkor(tag, tag)


def label_skor(tag):
    s = jenis_skor(tag)
    return f"{s.label} ({s.satuan})" if s.satuan else s.label


def tebak_program(tag):
    """Nama program dari kumpulan tag skor yang ada di berkas."""
    t = set(tag)
    if t & {"CNNscore", "CNNaffinity", "CNN_VS"}:
        return "GNINA"
    if any(x.startswith("Gold.") for x in t):
        return "GOLD"
    if any(x.startswith("r_i_") for x in t):
        return "Glide"
    if t & {"SCORE", "SCORE.INTER"}:
        return "rDock"
    if any("CDOCKER" in x for x in t) or "LibDockScore" in t:
        return "Discovery Studio"
    if "confidence" in t:
        return "DiffDock"
    if "minimizedAffinity" in t:
        return "Smina"
    if "S" in t:
        return "MOE"
    if "vina" in t:
        return "AutoDock Vina"
    if "ad4" in t:
        return "AutoDock4"
    return "Program lain"


def skor_utama_bawaan(tag):
    """Tag skor utama (urutan pose) yang lazim untuk kumpulan tag ini."""
    for k in UTAMA:
        if k in tag:
            return k
    return next(iter(tag), None)


def energi_bawaan(tag):
    """Tag pertama yang berdimensi energi (pengisi kolom ΔG); None = perlu skor ulang Vina."""
    for k in UTAMA + [s.tag for s in KATALOG]:
        if k in tag and jenis_skor(k).energi:
            return k
    return None


# ------------------------------------------------------------------ struktur data
@dataclass
class PoseImpor:
    mol: object                        # RDKit Mol ber-H, satu konformer 3D
    skor: dict = field(default_factory=dict)
    flex: str = ""                     # blok residu fleksibel PDBQT (Vina --flex)
    urutan: int = 0                    # urutan di berkas asal (1 = pertama)
    klaster: int = 0                   # ukuran klaster (AutoDock)
    rmsd_ref: float = -1.0             # RMSD ke ligan masukan (AutoDock)


@dataclass
class LiganImpor:
    nama: str
    program: str
    berkas: list = field(default_factory=list)
    pose: list = field(default_factory=list)
    catatan: list = field(default_factory=list)

    @property
    def tag(self):
        out = []
        for p in self.pose:
            for k in p.skor:
                if k not in out:
                    out.append(k)
        return out


# ------------------------------------------------------------------ utilitas
_AKHIRAN = re.compile(r"(?:[_\-.](?:out|docked|docking|dock|vina|qvina|gnina|smina|unidock|poses?|results?|hasil|"
                      r"ligand_out|best|top\d*|ranked|kompleks|complex))+$", re.I)
_UMUM = {"dock", "docking", "out", "output", "result", "results", "hasil", "ligand", "ligan", "lig", "poses", "pose",
         "complex", "kompleks", "docked", "vina", "gnina", "smina", "all", "ranked", "rank1"}


def _nama_berkas(path):
    p = Path(path)
    stem = _AKHIRAN.sub("", p.stem) or p.stem
    if stem.lower() in _UMUM and p.parent.name:
        return p.parent.name
    return stem


def _angka(teks):
    try:
        v = float(str(teks).strip().split()[0].replace(",", "."))
    except (ValueError, IndexError):
        return None
    return v if np.isfinite(v) else None


def _kunci_nama(nama):
    """GOLD menulis judul 'ligan|berkas|sdf|1|dock3': poses satu ligan berbagi segmen pertama."""
    n = (nama or "").strip()
    if "|" in n:
        n = n.split("|")[0].strip()
    return re.sub(r"[_\s]+(?:pose|model|conf|rank)[_\s]*\d+$", "", n, flags=re.I) or n


def _lengkapi_h(mol):
    from rdkit import Chem
    if mol is None:
        return None
    try:
        mol = Chem.AddHs(mol, addCoords=True)
    except Exception:
        pass
    try:
        Chem.AssignStereochemistryFrom3D(mol)
    except Exception:
        pass
    return mol


def _mol_blok(blok):
    """MolBlock -> Mol ber-H; sanitasi bertahap bila valensi tidak lazim."""
    from rdkit import Chem, rdBase
    with rdBase.BlockLogs():
        mol = Chem.MolFromMolBlock(blok, removeHs=False, sanitize=False)
        if mol is None:
            return None
        # Open Babel mengisi kolom valensi molfile sehingga RDKit mengunci H implisit (H non-polar PDBQT hilang).
        # Kunci dilepas agar AddHs melengkapi H; atom yang H-nya sudah eksplisit tidak berubah.
        for a in mol.GetAtoms():
            a.SetNoImplicit(False)
        # PDBQT tidak membawa muatan formal: N amina terprotonasi (4 ikatan) dan O oksonium jadi +1
        mol.UpdatePropertyCache(strict=False)
        for a in mol.GetAtoms():
            if a.GetFormalCharge() == 0 and (a.GetSymbol(), a.GetExplicitValence()) in (("N", 4), ("O", 3)):
                a.SetFormalCharge(1)
        try:
            Chem.SanitizeMol(mol)
            return mol
        except Exception:
            pass
        try:
            Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
        except Exception:
            return None
    return mol


def _koordinat_baris(baris):
    return np.array([[float(b[30:38]), float(b[38:46]), float(b[46:54])] for b in baris], dtype=float)


def _atom(baris):
    return [b for b in baris if b.startswith(("ATOM", "HETATM"))]


# ------------------------------------------------------------------ PDBQT (Vina, QuickVina, Smina, GNINA, Uni-Dock)
_RE_VINA = re.compile(r"REMARK VINA RESULT:\s+(\S+)\s+(\S+)\s+(\S+)")
_RE_REMARK_SKOR = re.compile(r"REMARK\s+(minimizedAffinity|CNNscore|CNNaffinity|CNN_VS|CNNaffinity_variance)\s+(\S+)")
_RE_AD4 = re.compile(r"Estimated Free Energy of Binding\s*[=:]\s*([-+]?\d+\.?\d*)")


_TOKEN_POSE = ("ATOM", "HETATM", "ROOT", "ENDROOT", "BRANCH", "ENDBRANCH", "TORSDOF", "BEGIN_RES")


def _model_pdbqt(teks):
    """(kepala, [(remark, atom, flex)]) per MODEL; berkas tanpa MODEL = satu model. Kepala = baris sebelum
    pose pertama (REMARK SMILES dan Name dari Meeko/Open Babel)."""
    kepala, model, cur, di_flex = [], [], None, False
    ada_model = "\nMODEL" in "\n" + teks
    for b in teks.replace("\x00", "").splitlines():
        if b.startswith("MODEL"):
            cur, di_flex = ([], [], []), False
            continue
        if b.startswith("ENDMDL"):
            if cur is not None and (cur[1] or cur[2]):
                model.append(cur)
            cur = None
            continue
        if cur is None:
            if ada_model or not b.startswith(_TOKEN_POSE):
                kepala.append(b)
                continue
            cur = ([], [], [])
        if b.startswith("BEGIN_RES"):
            di_flex = True
            cur[2].append(b)
        elif b.startswith("END_RES"):
            cur[2].append(b)
            di_flex = False
        elif di_flex:
            cur[2].append(b)
        elif b.startswith(("REMARK", "USER")):
            cur[0].append(b)
        elif b.startswith(_TOKEN_POSE):
            cur[1].append(b)
    if cur is not None and (cur[1] or cur[2]):
        model.append(cur)
    return kepala, model


def _skor_remark(baris):
    skor = {}
    for b in baris:
        m = _RE_VINA.search(b)
        if m:
            skor["vina"] = _angka(m.group(1))
            skor["_rmsd_lb"], skor["_rmsd_ub"] = _angka(m.group(2)), _angka(m.group(3))
            continue
        m = _RE_REMARK_SKOR.search(b)
        if m and _angka(m.group(2)) is not None:
            skor[m.group(1)] = _angka(m.group(2))
            continue
        m = _RE_AD4.search(b)
        if m:
            skor["ad4"] = _angka(m.group(1))
    return {k: v for k, v in skor.items() if v is not None}


def _remark_smiles(baris):
    return [b for b in baris if b.startswith(("REMARK SMILES", "REMARK H PARENT", "REMARK Flexibility Score"))]


def _nama_remark(baris):
    for b in baris:
        m = re.match(r"REMARK\s+Name\s*=\s*(.+)", b)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return ""


def mol_dari_pdbqt(pose_baris, remark=(), templat=None):
    """Satu pose PDBQT -> RDKit Mol ber-H.

    REMARK SMILES (Meeko) memberi orde ikatan dan muatan pasti. Tanpa itu, topologi dibaca Open Babel dari pose
    pertama (templat) lalu koordinat pose lain dipasang pada atom yang sama urutannya, supaya semua pose satu
    ligan berbagi orde ikatan yang identik."""
    teks = "\n".join(pose_baris)
    rem = _remark_smiles(remark)
    if any(b.startswith("REMARK SMILES ") and not b.startswith("REMARK SMILES IDX") for b in rem):
        from .analisis import pose_mol
        try:
            return pose_mol("\n".join(rem), teks), None
        except Exception as e:
            catat.log.debug(f"Meeko gagal membaca pose impor: {e}")
    atom = _atom(pose_baris)
    if templat is not None and templat.GetNumAtoms() == len(atom):
        from rdkit import Chem
        m = Chem.Mol(templat)
        conf = m.GetConformer()
        for i, p in enumerate(_koordinat_baris(atom)):
            conf.SetAtomPosition(i, p.tolist())
        return _lengkapi_h(m), templat
    from . import obabel
    blok = obabel.konversi("\n".join(b for b in pose_baris if not b.startswith(("BEGIN_RES", "END_RES")))
                           + "\n", "pdbqt", "mol")
    mol = _mol_blok(blok.split("$$$$")[0])
    if mol is None:
        raise GalatImporDocking("Open Babel tidak bisa membangun molekul dari pose PDBQT.")
    if mol.GetNumAtoms() != len(atom):
        return _lengkapi_h(mol), None
    return _lengkapi_h(mol), mol


def _baca_pdbqt(teks, path):
    kepala, model = _model_pdbqt(teks)
    if not model:
        raise GalatImporDocking("Tidak ada pose (MODEL/ATOM) di berkas PDBQT.")
    nama = _nama_remark(kepala) or next((_nama_remark(m[0]) for m in model if _nama_remark(m[0])), "") \
        or _nama_berkas(path)
    pose, templat, catatan = [], None, []
    for i, (rem, atom, flex) in enumerate(model, 1):
        if not _atom(atom):
            continue
        try:
            mol, templat_baru = mol_dari_pdbqt(atom, kepala + rem, templat)
        except Exception as e:
            catatan.append(f"Pose {i} dilewati: {e}")
            continue
        templat = templat or templat_baru
        skor = _skor_remark(rem) or (_skor_remark(kepala) if len(model) == 1 else {})
        p = PoseImpor(mol=mol, skor={k: v for k, v in skor.items() if not k.startswith("_")},
                      flex="\n".join(flex), urutan=i)
        pose.append(p)
    if not pose:
        raise GalatImporDocking("Tidak satu pose pun bisa dibaca dari berkas PDBQT. " + " ".join(catatan[:2]))
    tag = {k for p in pose for k in p.skor}
    program = "GNINA" if tag & {"CNNscore", "CNNaffinity"} else (
        "Smina" if "minimizedAffinity" in tag and "vina" not in tag else (
            "AutoDock Vina" if "vina" in tag else ("AutoDock4" if "ad4" in tag else "Program lain")))
    return [LiganImpor(nama=nama, program=program, berkas=[str(path)], pose=pose, catatan=catatan)]


# ------------------------------------------------------------------ DLG (AutoDock4, AutoDock-GPU)
def _baca_dlg(teks, path):
    from . import mesin as M
    pose_dlg = M.baca_dlg(path)
    if not pose_dlg:
        raise GalatImporDocking("Tidak ada pose DOCKED di berkas DLG (docking belum selesai?).")
    rem = []
    for b in teks.splitlines():
        for awal in ("INPUT-LIGAND-PDBQT: ", "DOCKED: "):
            if b.startswith(awal + "REMARK SMILES") or b.startswith(awal + "REMARK H PARENT"):
                isi = b[len(awal):]
                if isi not in rem:
                    rem.append(isi)
    nama = ""
    for b in teks.splitlines():
        m = re.search(r"(?:INPUT-LIGAND-PDBQT: |DOCKED: )REMARK\s+Name\s*=\s*(.+)", b)
        if m:
            nama = m.group(1).strip()
            break
    if not nama:
        m = re.search(r"^(?:move|Ligand file name:?)\s+(\S+)\.pdbqt", teks, re.M)
        nama = _nama_berkas(m.group(1)) if m and Path(m.group(1)).stem.lower() not in _UMUM else _nama_berkas(path)
    program = "AutoDock-GPU" if "AutoDock-GPU" in teks[:20000] else "AutoDock4"
    pose, templat, catatan = [], None, []
    for i, p in enumerate(pose_dlg, 1):
        baris = p.pdbqt.splitlines()
        try:
            mol, t_baru = mol_dari_pdbqt(baris, rem, templat)
        except Exception as e:
            catatan.append(f"Pose {i} dilewati: {e}")
            continue
        templat = templat or t_baru
        pose.append(PoseImpor(mol=mol, skor={"ad4": p.energi}, flex=p.flex, urutan=i, klaster=p.klaster,
                              rmsd_ref=p.rmsd_ref))
    if not pose:
        raise GalatImporDocking("Pose DLG tidak bisa dibangun menjadi molekul. " + " ".join(catatan[:2]))
    return [LiganImpor(nama=nama, program=program, berkas=[str(path)], pose=pose, catatan=catatan)]


# ------------------------------------------------------------------ SDF / MOL2 (GNINA, Smina, GOLD, Glide, ...)
_RE_DIFFDOCK = re.compile(r"rank(\d+)_confidence(-?\d+(?:\.\d+)?)", re.I)


def _skor_prop(mol):
    skor = {}
    for k in mol.GetPropNames():
        if k.startswith("_"):
            continue
        v = _angka(mol.GetProp(k))
        if v is None:
            continue
        nama = k.strip()
        if nama.lower() in ("minimizedaffinity", "minimized_affinity"):
            nama = "minimizedAffinity"
        if nama in ("r_i_docking_score", "r_i_glide_gscore", "r_i_glide_emodel") or nama in _KATALOG or \
                not re.search(r"(?:^|_)(?:id|idx|index|cid|mw|weight|atoms?|charge|rotb|hb[ad]|tpsa|logp|clogp|"
                              r"rank|run|seed|conformer|i_|s_|b_)", nama, re.I):
            skor[nama] = v
    return skor


def _sdf_rekaman(teks):
    from rdkit import Chem
    sup = Chem.SDMolSupplier()
    sup.SetData(teks, removeHs=False, sanitize=False)
    out = []
    for i in range(len(sup)):
        mol = sup[i]
        if mol is None:
            out.append(None)
            continue
        try:
            Chem.SanitizeMol(mol)
        except Exception:
            try:
                Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
            except Exception:
                out.append(None)
                continue
        out.append(mol)
    return out


def _kelompokkan(rekaman, path, program_bawaan=None):
    """[(nama, mol, skor)] -> [LiganImpor]; pose ligan yang sama digabung (urutan tetap)."""
    grup = {}
    for i, (nama, mol, skor) in enumerate(rekaman, 1):
        k = _kunci_nama(nama) or _nama_berkas(path)
        g = grup.setdefault(k, LiganImpor(nama=k, program="", berkas=[str(path)]))
        g.pose.append(PoseImpor(mol=mol, skor=skor, urutan=len(g.pose) + 1))
    for g in grup.values():
        g.program = program_bawaan or tebak_program(g.tag)
    return list(grup.values())


def _baca_sdf(teks, path):
    from rdkit import Chem
    rekaman, gagal = [], 0
    m_dd = _RE_DIFFDOCK.search(Path(path).stem)
    for mol in _sdf_rekaman(teks):
        if mol is None:
            gagal += 1
            continue
        if mol.GetNumConformers() == 0 or not mol.GetConformer().Is3D():
            gagal += 1
            continue
        nama = mol.GetProp("_Name").strip() if mol.HasProp("_Name") else ""
        skor = _skor_prop(mol)
        if m_dd and "confidence" not in skor:
            skor["confidence"] = float(m_dd.group(2))
        rekaman.append((nama or (_nama_berkas(path) if not m_dd else Path(path).parent.name or "ligan"),
                        _lengkapi_h(Chem.Mol(mol)), skor))
    if not rekaman:
        raise GalatImporDocking("Tidak ada pose 3D yang valid di berkas SDF.")
    hasil = _kelompokkan(rekaman, path, "DiffDock" if m_dd else None)
    if gagal:
        hasil[0].catatan.append(f"{gagal} rekaman SDF tidak terbaca atau tanpa koordinat 3D.")
    return hasil


def _baca_mol2(teks, path):
    from rdkit import Chem
    rekaman = []
    for blok in ["@<TRIPOS>MOLECULE" + b for b in teks.split("@<TRIPOS>MOLECULE")[1:]]:
        mol = Chem.MolFromMol2Block(blok, removeHs=False)
        if mol is None:
            from . import obabel
            try:
                mol = _mol_blok(obabel.konversi(blok, "mol2", "mol"))
            except Exception:
                mol = None
        if mol is None:
            continue
        judul = blok.splitlines()[1].strip() if len(blok.splitlines()) > 1 else ""
        skor = {}
        for m in re.finditer(r"^\s*(?:#\s*)?(Gold\.\S+|SCORE(?:\.\S+)?|Score|score)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*$",
                             blok, re.M):
            skor[m.group(1)] = float(m.group(2))
        rekaman.append((judul, _lengkapi_h(mol), skor))
    if not rekaman:
        raise GalatImporDocking("Tidak ada molekul valid di berkas MOL2.")
    return _kelompokkan(rekaman, path)


# ------------------------------------------------------------------ PDB (kompleks / multi-MODEL)
def _pisah_model_pdb(teks):
    model, cur = [], None
    for b in teks.splitlines():
        if b.startswith("MODEL"):
            cur = []
            continue
        if b.startswith("ENDMDL"):
            if cur is not None:
                model.append("\n".join(cur))
            cur = None
            continue
        if cur is not None:
            cur.append(b)
    return model or [teks]


def _baca_pdb(teks, path):
    """PDB kompleks (protein + ligan) atau ligan multi-MODEL. Protein menjadi kandidat reseptor."""
    from . import molekul
    from .prep_ligan import _dari_pdb
    model = _pisah_model_pdb(teks)
    pertama = molekul.baca_teks_struktur(model[0], Path(path).stem, "pdb", str(path))
    reseptor = next((o.teks for o in pertama if o.jenis == "protein"), "")
    lig = [o for o in pertama if o.jenis == "ligan" and not o.info.get("aditif")
           and (o.info.get("atom_berat") or 0) >= 4]
    utama = [o for o in lig if o.info.get("ligan_asli")] or lig
    if not utama:
        raise GalatImporDocking("Tidak ada ligan (HETATM) di berkas PDB.")
    hasil = []
    for o in utama:
        kunci = (o.info["rantai"], o.info["resn"], o.info["resi"])
        lg = LiganImpor(nama=o.info["resn"] if len(utama) == 1 and not reseptor else
                        (_nama_berkas(path) if len(utama) == 1 else f"{_nama_berkas(path)} {o.nama}"),
                        program="", berkas=[str(path)])
        if len(utama) == 1:
            lg.nama = _nama_berkas(path)
        templat = None
        for i, mt in enumerate(model, 1):
            baris = [b for b in mt.splitlines() if b.startswith(("ATOM", "HETATM")) and len(b) >= 54
                     and (b[21].strip(), b[17:20].strip(), _int(b[22:26])) == (kunci[0].strip(), kunci[1], kunci[2])]
            if not baris:
                continue
            try:
                if templat is None:
                    mol = _dari_pdb("\n".join(baris) + "\nEND\n")
                    templat = mol
                    mol = _lengkapi_h(mol)
                else:
                    from rdkit import Chem
                    if templat.GetNumAtoms() != len(baris):
                        mol = _lengkapi_h(_dari_pdb("\n".join(baris) + "\nEND\n"))
                    else:
                        mol = Chem.Mol(templat)
                        conf = mol.GetConformer()
                        for k, p in enumerate(_koordinat_baris(baris)):
                            conf.SetAtomPosition(k, p.tolist())
                        mol = _lengkapi_h(mol)
            except Exception as e:
                lg.catatan.append(f"Model {i} dilewati: {e}")
                continue
            lg.pose.append(PoseImpor(mol=mol, skor=_skor_remark(mt.splitlines()), urutan=i))
        if lg.pose:
            lg.program = tebak_program(lg.tag)
            hasil.append(lg)
    if not hasil:
        raise GalatImporDocking("Ligan di berkas PDB tidak bisa dibangun menjadi molekul.")
    return hasil, reseptor


def _int(s):
    try:
        return int(s)
    except ValueError:
        return None


# ------------------------------------------------------------------ pintu masuk
def baca_berkas(path):
    """Berkas hasil docking -> ([LiganImpor], teks PDB reseptor bila berkas memuat protein, atau '')."""
    p = Path(path)
    ext = p.suffix.lower()
    teks = p.read_text(encoding="utf-8", errors="replace")
    if ext == ".dlg":
        return _baca_dlg(teks, p), ""
    if ext == ".pdbqt":
        if _tampak_reseptor_pdbqt(teks):
            raise GalatImporDocking("Berkas ini tampak sebagai reseptor (protein), bukan pose ligan.")
        return _baca_pdbqt(teks, p), ""
    if ext in (".sdf", ".sd", ".mol"):
        return _baca_sdf(teks, p), ""
    if ext == ".mol2":
        return _baca_mol2(teks, p), ""
    if ext in (".pdb", ".ent"):
        return _baca_pdb(teks, p)
    raise GalatImporDocking(f"Format {ext} bukan berkas hasil docking yang dikenali.")


def _tampak_reseptor_pdbqt(teks):
    """PDBQT protein: banyak residu standar dan tanpa pohon torsi ligan."""
    if "\nROOT" in "\n" + teks or "VINA RESULT" in teks or "minimizedAffinity" in teks:
        return False
    res = {b[17:20] for b in teks.splitlines() if b.startswith("ATOM")}
    return len(res & {"ALA", "GLY", "LEU", "SER", "VAL", "LYS", "GLU", "ASP", "THR", "ILE"}) >= 4


def tampak_hasil_docking(path):
    """Untuk seret-lepas: True bila berkas jelas keluaran program docking (bukan sekadar struktur)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".dlg":
        return True
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            kepala = f.read(400_000)
    except OSError:
        return False
    if ext == ".pdbqt":
        return "VINA RESULT" in kepala or "minimizedAffinity" in kepala or kepala.count("\nMODEL") >= 1
    if ext in (".sdf", ".sd"):
        return any(f"<{t}>" in kepala for t in TAG_DOCKING) or bool(_RE_DIFFDOCK.search(p.stem))
    return False


def tampak_reseptor(path):
    """True bila berkas berisi protein tanpa ligan (dipakai sebagai reseptor, bukan pose)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in (".pdbqt", ".pdb", ".ent", ".cif", ".mmcif"):
        return False
    try:
        teks = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if ext == ".pdbqt":
        return _tampak_reseptor_pdbqt(teks)
    if ext in (".cif", ".mmcif"):
        return True
    from . import molekul
    ca = sum(1 for b in teks.splitlines() if b.startswith("ATOM") and b[12:16].strip() == "CA")
    het = {(b[21], b[17:20].strip(), b[22:27]) for b in teks.splitlines() if b.startswith("HETATM")
           and b[17:20].strip().upper() not in molekul.AIR | molekul.ION | molekul.ADITIF | molekul.KOFAKTOR}
    return ca >= 20 and not het


def gabung(kelompok):
    """[[LiganImpor] per berkas] -> [LiganImpor]; pose ligan bernama sama (dan berstruktur sama) dari berkas
    berbeda digabung, misalnya GOLD yang menulis satu berkas per pose. Masukan tidak diubah."""
    from dataclasses import replace
    hasil = {}
    for daftar in kelompok:
        for asal in daftar:
            lg = replace(asal, pose=[replace(p) for p in asal.pose], berkas=list(asal.berkas),
                         catatan=list(asal.catatan))
            ada = hasil.get(lg.nama)
            if ada and ada.program == lg.program and _topologi_sama(ada.pose[0].mol, lg.pose[0].mol):
                n = len(ada.pose)
                for p in lg.pose:
                    p.urutan += n
                ada.pose += lg.pose
                ada.berkas += [b for b in lg.berkas if b not in ada.berkas]
                ada.catatan += lg.catatan
                continue
            k, n = lg.nama, 2
            while k in hasil:
                k, n = f"{lg.nama} ({n})", n + 1
            lg.nama = k
            hasil[k] = lg
    for lg in hasil.values():
        _seragamkan(lg)
    return list(hasil.values())


def baca_banyak(berkas, lapor=None):
    """Banyak berkas -> (daftar LiganImpor tergabung, {berkas: teks PDB reseptor}, [galat])."""
    kelompok, reseptor, galat = [], {}, []
    for i, f in enumerate(berkas, 1):
        if lapor:
            lapor.progres.emit(int(100 * (i - 1) / max(1, len(berkas))), 100, f"Membaca {Path(f).name}")
        try:
            daftar, rec = baca_berkas(f)
        except Exception as e:
            galat.append(f"{Path(f).name}: {e}")
            continue
        if rec:
            reseptor[str(f)] = rec
        kelompok.append(daftar)
    return gabung(kelompok), reseptor, galat


def _smiles_berat(mol):
    from rdkit import Chem
    try:
        return Chem.MolToSmiles(Chem.RemoveHs(mol))
    except Exception:
        return ""


def _topologi_sama(a, b):
    return _smiles_berat(a) == _smiles_berat(b)


def _seragamkan(lg):
    """Semua pose satu ligan memakai urutan atom pose pertama (syarat PDBQT pose = templat masukan).
    Pose dengan topologi lain dipisah jadi catatan, bukan dicampur."""
    from rdkit import Chem
    if not lg.pose:
        return
    acuan = lg.pose[0].mol
    smi = _smiles_berat(acuan)
    tetap = [lg.pose[0]]
    for p in lg.pose[1:]:
        m = p.mol
        if m.GetNumAtoms() == acuan.GetNumAtoms() and all(
                x.GetAtomicNum() == y.GetAtomicNum() for x, y in zip(m.GetAtoms(), acuan.GetAtoms())) and \
                _smiles_berat(m) == smi:
            tetap.append(p)
            continue
        if _smiles_berat(m) == smi:
            cocok = m.GetSubstructMatch(acuan)
            if cocok and len(cocok) == m.GetNumAtoms():
                p.mol = Chem.RenumberAtoms(m, list(cocok))
                tetap.append(p)
                continue
        lg.catatan.append(f"Pose {p.urutan} memiliki struktur berbeda dari pose pertama dan dilewati.")
    lg.pose = tetap


# ------------------------------------------------------------------ reseptor
def siapkan_reseptor(path=None, teks=None, fmt=None):
    """Berkas/teks reseptor -> (PDB untuk tampilan & analisis, PDBQT untuk skor Vina).

    Air dan aditif kristalisasi dibuang; ion logam, kofaktor, dan gugus prostetik dipertahankan. Ligan lain
    di dalam berkas dibuang agar tidak terbaca sebagai bagian dari kantong."""
    from . import molekul, obabel
    if path is not None:
        p = Path(path)
        fmt = fmt or p.suffix.lower().lstrip(".")
        teks = p.read_text(encoding="utf-8", errors="replace")
    fmt = (fmt or "pdb").replace("ent", "pdb").replace("mmcif", "cif")
    if fmt == "pdbqt":
        baris = [b for b in teks.splitlines() if b.startswith(("ATOM", "HETATM", "TER"))]
        pdbqt = "\n".join(baris) + "\n"
        from .prep_reseptor import pdbqt_ke_pdb
        return pdbqt_ke_pdb(pdbqt), pdbqt
    if fmt == "mol2":
        teks = obabel.konversi(teks, "mol2", "pdb")
        fmt = "pdb"
    objek = molekul.baca_teks_struktur(teks, "reseptor", fmt)
    simpan = [o for o in objek if o.jenis in ("protein", "ion")
              or (o.jenis == "ligan" and (o.info.get("kofaktor") or
                                          (o.info.get("resn", "").upper() in molekul.PROSTETIK)))]
    if not any(o.jenis == "protein" for o in simpan):
        raise GalatImporDocking("Berkas reseptor tidak berisi protein.")
    baris = []
    for o in simpan:
        baris += [b for b in o.teks.splitlines() if b.startswith(("ATOM", "HETATM"))]
        if o.jenis == "protein":
            baris.append("TER")
    pdb = "\n".join(baris) + "\nEND\n"
    from .prep_reseptor import _openbabel
    pdbqt = _openbabel(pdb)
    pdbqt = "\n".join(b for b in pdbqt.splitlines() if b.startswith(("ATOM", "HETATM", "TER"))) + "\n"
    return pdb, pdbqt


# ------------------------------------------------------------------ skor ulang Vina
def skor_vina(rec_pdbqt_path, pose_pdbqt, timeout=120):
    """Skor fungsi Vina untuk pose apa adanya (--score_only, tanpa minimisasi). kcal/mol."""
    from . import paths
    from .lokal import baca_afinitas
    exe = paths.program("vina.exe")
    if not exe:
        raise GalatImporDocking("vina.exe tidak ditemukan; skor ulang Vina tidak bisa dihitung.")
    with tempfile.TemporaryDirectory(prefix="vmd_impor_") as d:
        lig = Path(d, "lig.pdbqt")
        lig.write_text(pose_pdbqt if pose_pdbqt.endswith("\n") else pose_pdbqt + "\n", encoding="utf-8")
        p = subprocess.run([exe, "--receptor", str(rec_pdbqt_path), "--ligand", str(lig), "--score_only",
                            "--autobox"], capture_output=True, timeout=timeout, creationflags=NOWIN)
    teks = (p.stdout + p.stderr).decode("utf-8", "replace")
    e = baca_afinitas(teks)
    if e is None:
        ekor = teks.strip().splitlines()[-1] if teks.strip() else "Vina tidak memberi skor."
        raise GalatImporDocking(f"Skor ulang Vina gagal: {ekor}")
    return e


# ------------------------------------------------------------------ tulis ke proyek
def _pdbqt_meeko(mol):
    from .lokal import pdbqt_pose
    return pdbqt_pose(mol)


def _blok_pose(pdbqt):
    """PDBQT Meeko -> blok pose (tanpa REMARK; REMARK tetap di berkas ligan masukan)."""
    return "\n".join(b for b in pdbqt.splitlines() if not b.startswith("REMARK") and b.strip())


def _rmsd_pasangan(a, b):
    """(RMSD simetri, RMSD langsung) atom berat antar dua pose satu ligan (Å)."""
    from .analisis import rmsd_simetri
    from rdkit import Chem
    pa, pb = Chem.RemoveHs(a), Chem.RemoveHs(b)
    xa, xb = pa.GetConformer().GetPositions(), pb.GetConformer().GetPositions()
    lang = float(np.sqrt(((xa - xb) ** 2).sum(1).mean())) if len(xa) == len(xb) else 0.0
    try:
        sim = rmsd_simetri(a, b)
    except Exception:
        sim = lang
    return round(sim, 3), round(lang, 3)


def opsi_bawaan(daftar):
    """Skor utama & sumber ΔG yang disarankan untuk kumpulan ligan impor."""
    tag = []
    for lg in daftar:
        for t in lg.tag:
            if t not in tag:
                tag.append(t)
    return {"skor_utama": skor_utama_bawaan(tag), "energi": energi_bawaan(tag) or "vina_ulang", "tag": tag}


def simpan_ke_proyek(proyek, daftar, reseptor_pdb, reseptor_pdbqt, opsi=None, lapor=None, maks_pose=20):
    """Tulis ligan impor sebagai satu job selesai. Kembalikan dict job (sudah ditambahkan ke proyek.job).

    opsi: {skor_utama: tag|None, urut: "skor"|"berkas", energi: tag|"vina_ulang", program: label,
           sumber_berkas: [...], sumber_reseptor: str}"""
    from rdkit import Chem
    from . import analisis
    from . import mesin as M
    from .antrean import SIMPAN_POSE
    opsi = dict(opsi or {})
    if not daftar:
        raise GalatImporDocking("Tidak ada ligan untuk diimpor.")
    proyek.siapkan_folder()
    jid = proyek.job_baru_id()
    folder_job = proyek.p("hasil", jid)
    folder_job.mkdir(parents=True, exist_ok=True)
    folder_rec = proyek.p("impor", jid)
    folder_rec.mkdir(parents=True, exist_ok=True)
    f_pdb, f_pdbqt = folder_rec / "reseptor.pdb", folder_rec / "reseptor.pdbqt"
    f_pdb.write_text(reseptor_pdb, encoding="utf-8")
    f_pdbqt.write_text(reseptor_pdbqt, encoding="utf-8")
    rec_analisis = analisis.baca_reseptor(reseptor_pdb)
    utama = opsi.get("skor_utama")
    sumber_e = opsi.get("energi") or "vina_ulang"
    urut = opsi.get("urut", "skor")
    program = opsi.get("program") or ", ".join(dict.fromkeys(lg.program for lg in daftar))
    # --- tahap 1: PDBQT per pose (Meeko) dan urutan pose
    kerja = []
    n_total = sum(min(len(lg.pose), maks_pose) for lg in daftar)
    k_prog = 0
    for lg in daftar:
        pose = list(lg.pose)
        # impor campuran (mis. Vina + GOLD): ligan tanpa skor utama terpilih diurutkan dengan skor program sendiri
        u_lg = utama if utama and all(utama in p.skor for p in pose) else skor_utama_bawaan(lg.tag)
        urut_utama = urut == "skor" and bool(u_lg) and all(u_lg in p.skor for p in pose)
        if urut_utama:
            rendah = jenis_skor(u_lg).rendah
            pose.sort(key=lambda p: p.skor[u_lg] if rendah else -p.skor[u_lg])
        pose = pose[:maks_pose]
        item = {"lg": lg, "pose": [], "catatan": list(lg.catatan), "urut_utama": urut_utama}
        for p in pose:
            k_prog += 1
            if lapor:
                lapor.progres.emit(int(5 + 45 * k_prog / max(1, n_total)), 100, f"Menyiapkan pose {lg.nama}")
            try:
                with redirect_stderr(io.StringIO()):
                    pq = _pdbqt_meeko(p.mol)
            except Exception as e:
                item["catatan"].append(f"Pose {p.urutan} dilewati (Meeko): {e}")
                continue
            item["pose"].append((p, pq))
        if not item["pose"]:
            item["catatan"].append("Tidak ada pose yang bisa ditulis sebagai PDBQT.")
        kerja.append(item)
    # --- tahap 2: ΔG (skor asli berdimensi energi atau skor ulang Vina)
    perlu_vina = [(it, i) for it in kerja for i, (p, _) in enumerate(it["pose"])
                  if sumber_e == "vina_ulang" or sumber_e not in p.skor]
    nilai_vina = {}
    if perlu_vina:
        if lapor:
            lapor.progres.emit(52, 100, f"Skor ulang Vina untuk {len(perlu_vina)} pose")

        def satu(arg):
            it, i = arg
            try:
                return (id(it), i), skor_vina(f_pdbqt, _blok_pose(it["pose"][i][1])), None
            except Exception as e:
                return (id(it), i), None, str(e)
        n_selesai = 0
        with ThreadPoolExecutor(max_workers=max(1, min(8, (os.cpu_count() or 2) - 1))) as ex:
            for kunci, v, gal in ex.map(satu, perlu_vina):
                n_selesai += 1
                nilai_vina[kunci] = (v, gal)
                if lapor and n_selesai % 5 == 0:
                    lapor.progres.emit(int(52 + 30 * n_selesai / len(perlu_vina)), 100,
                                       f"Skor ulang Vina {n_selesai}/{len(perlu_vina)}")
    # --- tahap 3: tulis berkas & isi job
    job = {"id": jid, "nama": f"Impor {program} · {sum(1 for it in kerja if it['pose'])} ligan", "mesin": "vina",
           "mesin_asal": "vina", "label_mesin": f"{program} (impor)", "perangkat": "-", "parameter": {},
           "kotak": {}, "status": "selesai", "dibuat": datetime.now().isoformat(timespec="seconds"),
           "mulai": None, "selesai": datetime.now().isoformat(timespec="seconds"), "catatan": [],
           "reseptor": proyek.rel(f_pdbqt), "reseptor_pdb": proyek.rel(f_pdb), "ligan": [],
           "impor": {"program": program, "berkas": list(dict.fromkeys(opsi.get("sumber_berkas") or
                                                                       [b for it in kerja for b in it["lg"].berkas])),
                     "reseptor": opsi.get("sumber_reseptor", ""), "skor_utama": utama,
                     "energi": sumber_e, "urut": urut,
                     "tanggal": datetime.now().isoformat(timespec="seconds")}}
    semua_xyz = []
    for n_it, it in enumerate(kerja, 1):
        lg = it["lg"]
        if lapor:
            lapor.progres.emit(int(82 + 17 * n_it / max(1, len(kerja))), 100, f"Analisis interaksi {lg.nama}")
        if not it["pose"]:
            job["catatan"].append(f"{lg.nama}: " + "; ".join(it["catatan"][-2:]))
            continue
        lid = proyek.id_ligan_baru(lg.nama)
        while any(l["id"] == lid for jj in proyek.job for l in jj["ligan"]):
            lid = proyek.id_ligan_baru(lid + "_impor")
        energi, catatan = [], it["catatan"]
        for i, (p, _) in enumerate(it["pose"]):
            if sumber_e != "vina_ulang" and sumber_e in p.skor:
                energi.append(round(p.skor[sumber_e] * jenis_skor(sumber_e).faktor, 3))
                continue
            v, gal = nilai_vina.get((id(it), i), (None, "tidak dihitung"))
            if v is None:
                catatan.append(f"Pose {p.urutan}: {gal}")
            energi.append(v)
        pasang = [(p, pq, e) for (p, pq), e in zip(it["pose"], energi) if e is not None]
        if not pasang:
            job["catatan"].append(f"{lg.nama}: ΔG tidak tersedia untuk pose mana pun ({catatan[-1] if catatan else ''}).")
            continue
        if urut == "skor" and not it["urut_utama"]:     # skor utama tidak ada di semua pose: urut menurut ΔG
            pasang.sort(key=lambda x: x[2])
        # berkas ligan masukan (templat REMARK SMILES) dan SDF sumber
        p0 = pasang[0][0]
        f_lig = proyek.p("ligan", "pdbqt", f"{lid}.pdbqt")
        f_lig.parent.mkdir(parents=True, exist_ok=True)
        f_lig.write_text(pasang[0][1], encoding="utf-8")
        f_sdf = proyek.p("ligan", "sumber", f"{lid}.sdf")
        f_sdf.parent.mkdir(parents=True, exist_ok=True)
        w = Chem.SDWriter(str(f_sdf))
        for k, (p, _, e) in enumerate(pasang, 1):
            m = Chem.Mol(p.mol)
            m.SetProp("_Name", lg.nama)
            m.SetProp("VirmoLab_pose", str(k))
            m.SetProp("VirmoLab_dG", f"{e:.3f}")
            for t, v in p.skor.items():
                m.SetProp(t, f"{v:g}")
            w.write(m)
        w.close()
        # keluaran gaya Vina: REMARK VINA RESULT berisi ΔG terpilih + RMSD l.b./u.b. terhadap pose 1
        blok, ringkas = [], []
        for k, (p, pq, e) in enumerate(pasang, 1):
            lb, ub = (0.0, 0.0) if k == 1 else _rmsd_pasangan(p.mol, p0.mol)
            blok += [f"MODEL {k}", f"REMARK VINA RESULT: {e:9.3f} {lb:10.3f} {ub:10.3f}",
                     "REMARK VIRMOLAB IMPOR " + json.dumps({"skor": p.skor, "urutan": p.urutan,
                                                            "klaster": p.klaster}, ensure_ascii=False),
                     _blok_pose(pq)]
            if p.flex.strip():
                blok.append(p.flex.strip())
            blok.append("ENDMDL")
            ringkas.append({"peringkat": k, "energi": e, "rmsd_lb": lb, "rmsd_ub": ub, "klaster": p.klaster,
                            "rmsd_ref": p.rmsd_ref, "skor": dict(p.skor), "urutan_asal": p.urutan})
            semua_xyz.append(p.mol.GetConformer().GetPositions())
        f_out = folder_job / f"{lid}.pdbqt"
        f_out.write_text("\n".join(blok) + "\n", encoding="utf-8")
        smi = _smiles_berat(p0.mol)
        from rdkit.Chem import Descriptors, rdMolDescriptors
        info_lig = {"id": lid, "nama": lg.nama, "status": "impor", "sumber": "; ".join(lg.berkas),
                    "sdf": proyek.rel(f_sdf), "pdbqt": proyek.rel(f_lig), "smiles": smi, "impor": jid,
                    "rumus": rdMolDescriptors.CalcMolFormula(p0.mol), "mw": round(Descriptors.MolWt(p0.mol), 2),
                    "atom": p0.mol.GetNumAtoms(), "torsi": rdMolDescriptors.CalcNumRotatableBonds(p0.mol)}
        proyek.ligan.append(info_lig)
        l = {"id": lid, "nama": lg.nama, "pdbqt": proyek.rel(f_lig), "status": "selesai", "progres": 100,
             "keluaran": proyek.rel(f_out), "energi": pasang[0][2], "ki": M.ki_terbaca(pasang[0][2]),
             "rmsd_ref": p0.rmsd_ref if p0.rmsd_ref >= 0 else None, "n_pose": len(pasang),
             "pose": ringkas[:SIMPAN_POSE], "pesan": "; ".join(catatan[-3:]), "detik": None,
             "skor_impor": dict(p0.skor), "program": lg.program,
             "energi_sumber": "Skor ulang Vina (--score_only)" if sumber_e == "vina_ulang" or
             sumber_e not in p0.skor else label_skor(sumber_e)}
        try:
            pose_obj = M.baca_vina(f_out)
            analisis.ringkas_ligan(proyek, l, pose_obj, rec_analisis)
        except Exception as e:
            catat.log.warning(f"Analisis impor {lg.nama} gagal: {e}")
            l["pesan"] = (l["pesan"] + "; " if l["pesan"] else "") + f"analisis interaksi gagal: {e}"
        job["ligan"].append(l)
    if not job["ligan"]:
        raise GalatImporDocking("Tidak ada ligan yang berhasil diimpor. " + " ".join(job["catatan"][:3]))
    if semua_xyz:
        xyz = np.vstack(semua_xyz)
        lo, hi = xyz.min(0), xyz.max(0)
        job["kotak"] = {"pusat": [round(float(v), 3) for v in (lo + hi) / 2],
                        "ukuran": [round(float(v) + 8.0, 2) for v in hi - lo], "spasi": 0.375}
    job["nama"] = f"Impor {program} · {len(job['ligan'])} ligan"
    proyek.job.append(job)
    return job
