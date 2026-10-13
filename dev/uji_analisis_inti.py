"""Uji core/analisis.py pada kompleks nyata 1HSG: deteksi interaksi ligan MK1 dengan protease HIV-1,
sidik jari interaksi, Tanimoto IFP, dan efisiensi ligan.

Acuan biologis: MK1 (indinavir) mengikat sisi aktif dua rantai; ASP 25 katalitik dan ILE 50 pada flap adalah
kontak yang terdokumentasi luas. Uji ini menjaga agar perubahan kode tidak diam-diam menghilangkan kontak itu.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_analisis_inti.py
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from virmolab.app import siapkan_kimia

siapkan_kimia()
from virmolab.core import analisis as A, molekul as M

PDB = AKAR / "virmolab" / "aset" / "contoh" / "1HSG.pdb"
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


if not PDB.exists():
    print("LEWAT: 1HSG.pdb bawaan tidak ada")
    raise SystemExit(0)

teks = PDB.read_text(encoding="utf-8")
objek = M.baca_teks_struktur(teks, "1HSG", "pdb", "uji")
prot = next(o for o in objek if o.jenis == "protein")
lig = next(o for o in objek if o.jenis == "ligan" and "MK1" in o.nama)

rec = A.baca_reseptor(prot.teks)
cek(len(rec.xyz) > 1500, f"reseptor terbaca: {len(rec.xyz)} atom")

mol = A.mol_kristal(lig.teks)
cek(mol is not None and mol.GetNumAtoms() > 30, f"ligan kristal MK1 terbaca: {mol.GetNumAtoms()} atom")

daftar = A.interaksi(rec, mol)
cek(len(daftar) > 10, f"{len(daftar)} interaksi terdeteksi")

n = A.hitung(daftar)
cek(n.get("hbond", 0) >= 3, f"ikatan hidrogen MK1–protease: {n.get('hbond')}")
cek(n.get("hidrofobik", 0) >= 5, f"kontak hidrofobik: {n.get('hidrofobik')}")
cek("vdw" not in n, "hitung() tidak memasukkan kontak van der Waals ke ringkasan jenis")

residu = A.residu_kontak(daftar)
nama_residu = {r.split()[0] for r in residu}
cek("ASP" in nama_residu, f"residu katalitik ASP terdeteksi di antarmuka ({sorted(nama_residu)[:6]})")
cek(any(r.startswith("ASP 25") for r in residu), f"ASP 25 katalitik terdeteksi: {[r for r in residu if '25' in r]}")
cek(any("ILE 50" in r for r in residu), f"ILE 50 (flap) terdeteksi: {[r for r in residu if 'ILE 50' in r]}")
cek(len(residu) >= 8, f"{len(residu)} residu kontak — kantong terisi, bukan sentuhan sesaat")

# setiap interaksi punya bentuk data yang utuh untuk panel dan laporan
contoh = daftar[0]
for kunci in ("jenis", "resn", "resi", "rantai", "residu"):
    cek(kunci in contoh, f"data interaksi memuat kunci '{kunci}'")

# ------------------------------------------------------------------ sidik jari interaksi
ifp = A.sidik_jari(daftar)
cek(ifp == sorted(ifp) and len(ifp) == len(set(ifp)), "IFP terurut dan tanpa duplikat (stabil di proyek.json)")
cek(all("|" in b for b in ifp), "tiap bit IFP berbentuk 'residu|jenis'")
cek(not any(b.endswith("|vdw") for b in ifp), "kontak van der Waals tidak masuk IFP")

cek(A.tanimoto(ifp, ifp) == 1.0, "Tanimoto IFP dengan dirinya sendiri = 1")
cek(A.tanimoto(ifp, []) is None and A.tanimoto([], []) is None, "Tanimoto menolak IFP kosong dengan None, bukan 0")
separuh = ifp[: max(1, len(ifp) // 2)]
t = A.tanimoto(ifp, separuh)
cek(0 < t < 1, f"Tanimoto sebagian tumpang tindih berada di antara 0 dan 1: {t}")

# ------------------------------------------------------------------ efisiensi ligan
cek(A.efisiensi_ligan(-11.18, 45) == round(11.18 / 45, 3), "efisiensi ligan = -ΔG / atom berat")
cek(A.efisiensi_ligan(-10.0, 0) is None, "efisiensi ligan tanpa atom berat mengembalikan None, bukan pembagian nol")

print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
sys.exit(1 if gagal else 0)
