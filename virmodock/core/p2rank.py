"""Deteksi kantong pengikatan dengan P2Rank (MIT, Krivák & Hoksza 2018) — proses Java terpisah.

Program: bin/p2rank (p2rank.jar + lib + config + models) dan bin/jre (Eclipse Temurin JRE, GPL-2.0 + CE).
Keluaran <nama>.pdb_predictions.csv: peringkat, skor, probabilitas, pusat, residu kantong.
"""
import csv
import os
import subprocess
from pathlib import Path

from . import paths


def _java():
    j = paths.BIN / "jre" / "bin" / "java.exe"
    return j if j.exists() else None


def _akar():
    a = paths.BIN / "p2rank"
    return a if (a / "bin" / "p2rank.jar").exists() else None


def tersedia():
    return bool(_java() and _akar())


def perintah(pdb, keluar, thread=None):
    akar = _akar()
    cp = os.pathsep.join([str(akar / "bin" / "p2rank.jar"), str(akar / "bin" / "lib" / "*")])
    return [str(_java()), "-Xmx2048m", "-cp", cp, "cz.siret.prank.program.Main", "predict",
            "-f", str(pdb), "-o", str(keluar), "-threads", str(thread or max(1, (os.cpu_count() or 2) // 2)),
            "-visualizations", "0"]


def baca_prediksi(f):
    """[{peringkat, skor, prob, pusat (x,y,z), residu [(rantai, resi)], n_atom}] urut peringkat."""
    out = []
    with open(f, encoding="utf-8") as fh:
        for r in csv.DictReader(fh, skipinitialspace=True):
            r = {k.strip(): (v or "").strip() for k, v in r.items()}
            res = []
            for t in r.get("residue_ids", "").split():
                rantai, _, nomor = t.partition("_")
                res.append((rantai, nomor))
            out.append({"nama": r.get("name", ""), "peringkat": int(r.get("rank", 0)),
                        "skor": float(r.get("score", 0)), "prob": float(r.get("probability", 0) or 0),
                        "pusat": (float(r["center_x"]), float(r["center_y"]), float(r["center_z"])),
                        "residu": res, "n_atom": len(r.get("surf_atom_ids", "").split())})
    return sorted(out, key=lambda x: x["peringkat"])


def prediksi(teks_pdb, folder, thread=None, timeout=600):
    """Jalankan P2Rank untuk teks PDB protein. Kembalikan daftar kantong."""
    folder = Path(folder).resolve()   # P2Rank berjalan dengan cwd = folder P2Rank
    folder.mkdir(parents=True, exist_ok=True)
    pdb = folder / "protein.pdb"
    pdb.write_text("\n".join(b for b in teks_pdb.splitlines() if b.startswith(("ATOM", "TER", "END"))) + "\nEND\n",
                   encoding="utf-8")
    keluar = folder / "p2rank"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(perintah(pdb, keluar, thread), cwd=str(_akar()), capture_output=True, text=True,
                       timeout=timeout, creationflags=flags)
    f = keluar / "protein.pdb_predictions.csv"
    if not f.exists():
        pesan = (r.stderr or r.stdout or "").strip().splitlines()
        raise RuntimeError("P2Rank gagal: " + (pesan[-1] if pesan else f"kode {r.returncode}"))
    return baca_prediksi(f)


def ukuran_kotak(kantong, xyz_residu, margin=4.0, minimum=16.0, maksimum=30.0):
    """Ukuran grid box dari sebaran atom residu kantong (+ 4 Å), dibatasi 16–30 Å per sumbu."""
    import numpy as np
    if not len(xyz_residu):
        return (22.0, 22.0, 22.0)
    a = np.asarray(xyz_residu, float)
    span = a.max(axis=0) - a.min(axis=0) + margin
    return tuple(round(float(min(maksimum, max(minimum, s))), 1) for s in span)
