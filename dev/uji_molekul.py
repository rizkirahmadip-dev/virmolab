"""Uji core/molekul.py: pemecahan struktur PDB jadi objek (protein, ligan, air, ion), pembacaan SDF/MOL2/SMILES,
impor berkas, rumus molekul, dan penolakan masukan rusak.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_molekul.py
"""
import shutil
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from virmodock.app import siapkan_kimia

siapkan_kimia()
from virmodock.core import molekul as M

OUT = AKAR / "dev" / "uji" / "molekul"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
PDB = AKAR / "virmodock" / "aset" / "contoh" / "1HSG.pdb"
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


if not PDB.exists():
    print("LEWAT: 1HSG.pdb bawaan tidak ada")
    raise SystemExit(0)

# ------------------------------------------------------------------ pecah struktur PDB
teks = PDB.read_text(encoding="utf-8")
objek = M.baca_teks_struktur(teks, "1HSG", "pdb", "uji")
jenis = {}
for o in objek:
    jenis.setdefault(o.jenis, []).append(o)
cek("protein" in jenis, f"protein terbaca ({len(jenis.get('protein', []))} objek)")
cek(any("MK1" in o.nama for o in jenis.get("ligan", [])), f"ligan MK1 dikenali: {[o.nama for o in jenis.get('ligan', [])]}")
cek("air" in jenis, "molekul air dipisahkan dari protein")

prot = jenis["protein"][0]
cek(prot.fmt == "pdb" and prot.teks.lstrip().startswith(("ATOM", "HEADER", "CRYST", "REMARK", "TITLE")),
    "objek protein menyimpan teks PDB")
cek(set(prot.rantai) >= {"A", "B"}, f"dua rantai protease HIV-1 terdeteksi: {sorted(prot.rantai)}")
cek(prot.gaya.get("reps"), f"gaya bawaan protein terisi: {prot.gaya.get('reps')}")
cek(prot.id and prot.id != jenis["ligan"][0].id, "tiap objek punya id sendiri")

spek = M.spek_viewer(prot)
cek(isinstance(spek, dict) and spek, "spek_viewer menghasilkan kamus untuk viewer 3D")

# ------------------------------------------------------------------ SMILES
asp = M.dari_smiles("CC(=O)Oc1ccccc1C(=O)O", "aspirin")[0]
cek(asp.jenis == "ligan" and asp.fmt == "sdf", f"SMILES jadi objek ligan SDF ({asp.jenis}/{asp.fmt})")
cek("aspirin" in asp.nama, f"nama ligan dipakai: {asp.nama}")
cek(asp.info.get("rumus") in ("C9H8O4", "C9H8O4"), f"rumus molekul aspirin: {asp.info.get('rumus')}")
cek(len([b for b in asp.teks.splitlines() if b.strip()]) > 10, "blok SDF berisi koordinat 3D")

rusak = 0
try:
    M.dari_smiles("ini bukan smiles(((", "rusak")
except M.GalatImpor:
    rusak = 1
cek(rusak == 1, "SMILES rusak ditolak dengan GalatImpor, bukan diam-diam kosong")

# ------------------------------------------------------------------ SDF dan MOL2 bolak-balik
sdf = asp.teks if asp.teks.rstrip().endswith("$$$$") else asp.teks.rstrip() + "\n$$$$\n"
ulang = M.baca_sdf(sdf, "aspirin_ulang", "uji")
cek(len(ulang) == 1 and ulang[0].jenis == "ligan", f"SDF dibaca kembali jadi 1 ligan ({len(ulang)})")

# ------------------------------------------------------------------ impor berkas
f_pdb = OUT / "struktur.pdb"
f_pdb.write_text(teks, encoding="utf-8")
hasil = M.impor_berkas(f_pdb)
cek(bool(hasil) and any(o.jenis == "protein" for o in hasil), "impor_berkas membaca .pdb")

f_sdf = OUT / "ligan.sdf"
f_sdf.write_text(sdf, encoding="utf-8")
cek(bool(M.impor_berkas(f_sdf)), "impor_berkas membaca .sdf")

f_aneh = OUT / "berkas.xyz"
f_aneh.write_text("bukan struktur apa pun", encoding="utf-8")
try:
    M.impor_berkas(f_aneh)
    cek(False, "berkas tak dikenal seharusnya ditolak")
except Exception as e:
    cek(isinstance(e, M.GalatImpor) or "format" in str(e).lower() or "tidak" in str(e).lower(),
        f"berkas tak dikenal ditolak dengan pesan jelas: {str(e)[:60]}")

# ------------------------------------------------------------------ elemen PDBQT
baris = "ATOM      1  N   LEU A   1      10.000  11.000  12.000  1.00  0.00    -0.347 N "
el = M._elemen_pdbqt(baris)
cek(el.strip() == "N" and len(el) == 2, f"elemen PDBQT dibaca dan ditata rata kanan dua kolom: {el!r}")
cek(M._elemen_pdbqt("ATOM      1  C   LEU A   1       0.0   0.0   0.0  1.00  0.00     0.000 A ").strip() == "C",
    "tipe AutoDock 'A' (karbon aromatik) dipetakan ke unsur C")

print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
sys.exit(1 if gagal else 0)
