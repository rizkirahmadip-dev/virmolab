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


def minimisasi_lokal(teks_reseptor, teks_ligan, timeout=180):
    """Jalankan Vina --local_only --autobox. Kembalikan ΔG (kcal/mol)."""
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
    teks = (p.stdout + p.stderr).decode("utf-8", "replace")
    energi = baca_afinitas(teks)
    if energi is None:
        ekor = teks.strip().splitlines()[-1] if teks.strip() else "Vina tidak memberi skor."
        raise RuntimeError(ekor)
    return energi
