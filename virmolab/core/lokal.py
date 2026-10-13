"""Minimisasi pose di dalam kotak (Vina --local_only), tanpa docking ulang dari awal."""
import re
import subprocess
import tempfile
from pathlib import Path

from . import paths

NOWIN = 0x08000000


def baca_afinitas(teks):
    """Ambil ΔG (kcal/mol) dari keluaran Vina. None bila tidak ada angka."""
    m = re.search(r"Affinity:\s*(-?\d+(?:\.\d+)?)", teks or "")
    if not m:
        m = re.search(r"Estimated Free Energy of Binding\s*:\s*(-?\d+(?:\.\d+)?)", teks or "")
    if m:
        return float(m.group(1))
    for b in (teks or "").splitlines():
        p = b.split()
        if len(p) >= 2 and p[0] == "1":
            try:
                return float(p[1])
            except ValueError:
                continue
    return None


def pdbqt_pose(mol):
    """PDBQT dari konformer yang sudah ada. Koordinat pose tidak dibuat ulang."""
    import io
    from contextlib import redirect_stderr
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from rdkit import Chem
    m = Chem.Mol(mol)
    if m.GetNumConformers() == 0:
        raise ValueError("Pose tidak punya koordinat 3D.")
    m = Chem.AddHs(m, addCoords=True)
    prep = MoleculePreparation(rigid_macrocycles=False)
    with redirect_stderr(io.StringIO()):
        setups = prep.prepare(m)
    if not setups:
        raise ValueError("Meeko tidak bisa membaca pose ini.")
    teks, ok, pesan = PDBQTWriterLegacy.write_string(setups[0])
    if not ok:
        raise ValueError(pesan.strip() or "Gagal menulis PDBQT.")
    return teks


def _model_pertama(pdbqt):
    """Blok pose pertama. Vina menulis MODEL; berkas tanpa MODEL dikembalikan apa adanya."""
    baris, dalam, ada = [], False, False
    for b in (pdbqt or "").replace("\x00", "").splitlines():
        if b.startswith("MODEL"):
            ada, dalam, baris = True, True, []
            continue
        if b.startswith("ENDMDL") and dalam:
            break
        if not ada or dalam:
            baris.append(b)
    return "\n".join(baris)


def minimisasi_lokal(teks_reseptor, teks_ligan, timeout=180, kembalikan=False):
    """Jalankan Vina --local_only --autobox. Kembalikan ΔG (kcal/mol).

    kembalikan=True juga mengembalikan PDBQT pose yang sudah diminimisasi.
    """
    exe = paths.program("vina.exe")
    if not exe:
        raise FileNotFoundError("vina.exe tidak ditemukan.")
    if not teks_reseptor.strip():
        raise ValueError("Reseptor belum disiapkan, jadi skor Vina lokal tidak bisa dihitung.")
    with tempfile.TemporaryDirectory(prefix="vmd_lokal_") as d:
        rec, lig, keluar = Path(d, "rec.pdbqt"), Path(d, "lig.pdbqt"), Path(d, "out.pdbqt")
        rec.write_text(teks_reseptor if teks_reseptor.endswith("\n") else teks_reseptor + "\n", encoding="utf-8")
        lig.write_text(teks_ligan if teks_ligan.endswith("\n") else teks_ligan + "\n", encoding="utf-8")
        p = subprocess.run(
            [exe, "--receptor", str(rec), "--ligand", str(lig), "--local_only", "--autobox", "--out", str(keluar)],
            capture_output=True, timeout=timeout, creationflags=NOWIN)
        pose = ""
        if kembalikan and keluar.exists():
            pose = _model_pertama(keluar.read_text(encoding="utf-8", errors="replace"))
    teks = (p.stdout + p.stderr).decode("utf-8", "replace")
    energi = baca_afinitas(teks)
    if energi is None:
        ekor = teks.strip().splitlines()[-1] if teks.strip() else "Vina tidak memberi skor."
        raise RuntimeError(ekor)
    return (energi, pose) if kembalikan else energi


def geser_atom(teks, fmt, info, teks_reseptor=""):
    """Geser satu atom berat, rapikan ikatan di sekitarnya, lalu nilai dengan Vina lokal bila reseptor ada.

    info memuat koordinat baru (x, y, z) dan koordinat asal (ox, oy, oz).
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem

    class _O:
        pass

    o = _O()
    o.teks, o.fmt = teks, fmt
    from .analisis import mol_dari_objek, pose_mol
    mol = mol_dari_objek(o)
    if mol is None or mol.GetNumConformers() == 0:
        raise ValueError("Ligan ini tidak punya koordinat yang bisa digeser.")
    conf = mol.GetConformer()
    ox, oy, oz = float(info["ox"]), float(info["oy"]), float(info["oz"])
    terbaik, jarak = None, 0.75
    for a in mol.GetAtoms():
        if a.GetAtomicNum() <= 1:
            continue
        p = conf.GetAtomPosition(a.GetIdx())
        d = ((p.x - ox) ** 2 + (p.y - oy) ** 2 + (p.z - oz) ** 2) ** 0.5
        if d < jarak:
            jarak, terbaik = d, a.GetIdx()
    if terbaik is None:
        raise ValueError("Atom yang digeser tidak cocok dengan ligan di layar.")
    conf.SetAtomPosition(terbaik, (float(info["x"]), float(info["y"]), float(info["z"])))
    try:
        mh = Chem.AddHs(mol, addCoords=True)
        props = AllChem.MMFFGetMoleculeProperties(mh, mmffVariant="MMFF94")
        if props:
            ff = AllChem.MMFFGetMoleculeForceField(mh, props)
            ff.MMFFAddPositionConstraint(terbaik, 0.25, 200.0)
            ff.Minimize(maxIts=200)
            mol = Chem.RemoveHs(mh)
    except Exception:
        mol = Chem.RemoveHs(mol) if any(a.GetAtomicNum() == 1 for a in mol.GetAtoms()) else mol
    energi = None
    pesan = "Atom digeser. Skor Vina belum dihitung karena reseptor belum disiapkan."
    if (teks_reseptor or "").strip():
        try:
            masukan = pdbqt_pose(mol)
            energi, pose = minimisasi_lokal(teks_reseptor, masukan, kembalikan=True)
            mol = pose_mol(masukan, pose)
            pesan = f"Atom digeser, lalu Vina meminimisasi di tempat: {energi:.2f} kcal/mol. Angka ini bukan ΔG docking."
        except Exception as e:
            pesan = f"Atom digeser. Skor Vina lokal tidak jadi: {e}"
    blok = Chem.MolToMolBlock(mol)
    if not blok or ("V2000" not in blok and "V3000" not in blok):
        raise ValueError("Koordinat baru tidak bisa ditulis.")
    return {"teks": blok, "fmt": "sdf", "energi": energi, "pesan": pesan}


def geser_utuh(teks, fmt, info, teks_reseptor=""):
    """Geser seluruh ligan dengan vektor yang sama, lalu nilai dengan Vina lokal bila reseptor ada."""
    from rdkit import Chem
    from rdkit.Geometry import Point3D

    class _O:
        pass

    o = _O()
    o.teks, o.fmt = teks, fmt
    from .analisis import mol_dari_objek, pose_mol
    mol = mol_dari_objek(o)
    if mol is None or mol.GetNumConformers() == 0:
        raise ValueError("Ligan ini tidak punya koordinat yang bisa digeser.")
    dx, dy, dz = float(info["dx"]), float(info["dy"]), float(info["dz"])
    conf = mol.GetConformer()
    for i in range(mol.GetNumAtoms()):
        p = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, Point3D(p.x + dx, p.y + dy, p.z + dz))
    energi = None
    pesan = "Ligan digeser utuh. Skor Vina belum dihitung karena reseptor belum disiapkan."
    if (teks_reseptor or "").strip():
        try:
            masukan = pdbqt_pose(mol)
            energi, pose = minimisasi_lokal(teks_reseptor, masukan, kembalikan=True)
            mol = pose_mol(masukan, pose)
            pesan = f"Ligan digeser utuh, lalu Vina meminimisasi di tempat: {energi:.2f} kcal/mol. Angka ini bukan ΔG docking."
        except Exception as e:
            pesan = f"Ligan digeser utuh. Skor Vina lokal tidak jadi: {e}"
    blok = Chem.MolToMolBlock(mol)
    if not blok or ("V2000" not in blok and "V3000" not in blok):
        raise ValueError("Koordinat baru tidak bisa ditulis.")
    return {"teks": blok, "fmt": "sdf", "energi": energi, "pesan": pesan}
