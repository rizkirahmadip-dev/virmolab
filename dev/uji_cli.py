"""Uji baris perintah (0.9.3, offline): reseptor/ligan/dock dengan berkas lokal 1HSG.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_cli.py
Keluaran: dev/uji/cli/
"""
import csv
import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path("dev/uji/cli").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
gagal = []


def cli(*arg, kode=0):
    p = subprocess.run([sys.executable, "-m", "virmolab.cli", *map(str, arg)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    keluaran = p.stdout + (p.stderr.replace("GALAT:", "galat (diharapkan):") if kode else p.stderr)
    print(f"$ VirmoLab-cli {' '.join(map(str, arg))}\n{keluaran}".rstrip(), flush=True)
    if p.returncode != kode:
        gagal.append(f"kode keluar {p.returncode} (harap {kode}): {' '.join(map(str, arg))[:80]}")
    return p


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


pdb = Path("dev/uji/1HSG.pdb").resolve()
cli("reseptor", pdb, "-o", OUT / "rec.pdbqt", "--protonasi", "templat", "--flex", "A:25,B:25")
cek((OUT / "rec.pdbqt").exists() and "BEGIN_RES" in (OUT / "rec_flex.pdbqt").read_text(), "reseptor + flex")
cli("ligan", Path("dev/uji/MK1.sdf").resolve(), "CC(=O)Oc1ccccc1C(=O)O", "-o", OUT / "lig")
cek(len(list((OUT / "lig").glob("*.pdbqt"))) == 2, "ligan: 2 PDBQT")
# dock kaku Vina dari PDB (acuan auto) + dock flex AD-GPU dari PDBQT siap
cli("dock", "-r", pdb, "-l", OUT / "lig", "--acuan", "auto", "--mesin", "vina", "--exhaustiveness", "4",
    "--protonasi", "templat", "-o", OUT / "vina")
cli("dock", "-r", OUT / "rec.pdbqt", "--berkas-flex", OUT / "rec_flex.pdbqt", "-l", next((OUT / "lig").glob("MK1*.pdbqt")),
    "--pusat", "13.073", "22.467", "5.557", "--ukuran", "22", "22", "22", "--mesin", "adgpu", "--run", "10",
    "-o", OUT / "gpu_flex")
for nama, n, flex in (("vina", 2, False), ("gpu_flex", 1, True)):
    f = OUT / nama / "ringkasan.csv"
    baris = list(csv.DictReader(open(f, encoding="utf-8-sig"))) if f.exists() else []
    cek(len(baris) == n and all(b["status"] == "selesai" for b in baris), f"{nama}: {[(b['ligan'], b['dG_kcal_mol']) for b in baris]}")
    if flex and baris:
        cek(baris[0]["residu_fleksibel"].count(" ") >= 1, f"  residu fleksibel di CSV: {baris[0]['residu_fleksibel']}")
    cek((OUT / nama / "metode.txt").exists(), f"  metode.txt ada")
# galat yang diharapkan: area docking tidak diberikan, folder tidak kosong
cli("dock", "-r", OUT / "rec.pdbqt", "-l", OUT / "lig", "-o", OUT / "x", kode=1)
cli("dock", "-r", OUT / "rec.pdbqt", "-l", OUT / "lig", "--pusat", "0", "0", "0", "-o", OUT / "vina", kode=1)
print("GAGAL" if gagal else "LULUS", len(gagal), gagal[:3])
