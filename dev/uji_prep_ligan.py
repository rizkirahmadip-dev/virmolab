"""Uji core/prep_ligan.py: pembacaan SMILES/SDF/PDB, protonasi pH, pembuatan 3D, PDBQT Meeko, dan
pelaporan ligan yang gagal disiapkan.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_prep_ligan.py
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from virmodock.app import siapkan_kimia

siapkan_kimia()
from virmodock.core import prep_ligan as L

gagal = []
ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
LISIN = "NCCCC[C@H](N)C(=O)O"        # punya gugus asam dan basa: uji protonasi pH


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


# ------------------------------------------------------------------ pembacaan berbagai format
mol = L.mol_dari(ASPIRIN, "smiles")
cek(mol is not None and mol.GetNumAtoms() >= 13, f"SMILES terbaca ({mol.GetNumAtoms()} atom dengan H)")

h = L.siapkan_satu("aspirin", ASPIRIN, "smiles", L.OpsiLigan())
cek(h.status in ("siap", "peringatan"), f"aspirin disiapkan: status {h.status} {h.alasan or ''}")
cek(h.pdbqt and "ROOT" in h.pdbqt and "ATOM" in h.pdbqt, "PDBQT berisi blok ROOT dan atom")
cek("REMARK SMILES" in h.pdbqt, "PDBQT menyimpan REMARK SMILES untuk rekonstruksi pose")
from rdkit import Chem as _C
cek(bool(h.sdf) and _C.MolFromMolBlock(h.sdf, removeHs=False) is not None,
    "blok molekul 3D ikut dihasilkan dan bisa dibaca ulang RDKit")
# pada pH 7,4 gugus karboksilat aspirin terdeprotonasi, jadi rumusnya anion — ini perilaku yang benar
cek(h.rumus == "C9H7O4-" and h.muatan == -1, f"aspirin pada pH 7,4 berupa anion: {h.rumus} muatan {h.muatan}")
netral_asp = L.siapkan_satu("aspirin_netral", ASPIRIN, "smiles", L.OpsiLigan(protonasi=False))
cek(netral_asp.rumus == "C9H8O4" and netral_asp.muatan == 0,
    f"tanpa protonasi pH, aspirin tetap netral: {netral_asp.rumus}")
cek(7 <= h.atom <= 14, f"jumlah atom berat wajar: {h.atom}")
cek(h.torsi >= 2, f"ikatan berputar terhitung: {h.torsi}")
cek(abs(h.mw - 179.15) < 0.2 and abs(netral_asp.mw - 180.16) < 0.2,
    f"massa anion {h.mw} dan bentuk netral {netral_asp.mw} sesuai")

# koordinat 3D harus benar-benar tiga dimensi, bukan datar di satu bidang
z = {b[46:54].strip() for b in h.pdbqt.splitlines() if b.startswith(("ATOM", "HETATM"))}
cek(len(z) > 3, f"koordinat z beragam ({len(z)} nilai berbeda) — struktur 3D, bukan datar")

# ------------------------------------------------------------------ SDF bolak-balik
h2 = L.siapkan_satu("aspirin_sdf", h.sdf, "sdf", L.OpsiLigan())
cek(h2.status in ("siap", "peringatan") and h2.rumus == h.rumus, "SDF hasil langkah sebelumnya bisa disiapkan ulang")

# ------------------------------------------------------------------ protonasi pH
if L.dimorphite_tersedia():
    op_ph = L.OpsiLigan(protonasi=True, ph=7.4)
    hp = L.siapkan_satu("lisin", LISIN, "smiles", op_ph)
    netral = L.siapkan_satu("lisin_netral", LISIN, "smiles", L.OpsiLigan(protonasi=False))
    cek(hp.status in ("siap", "peringatan"), f"lisin pada pH 7,4 disiapkan: {hp.status}")
    cek(hp.muatan != netral.muatan or hp.smiles != netral.smiles,
        f"protonasi pH mengubah bentuk ion (muatan {netral.muatan} → {hp.muatan})")
else:
    print("LEWAT: dimorphite-dl tidak terpasang, uji protonasi dilewati", flush=True)

# ------------------------------------------------------------------ tanpa minimisasi
cepat = L.siapkan_satu("aspirin_cepat", ASPIRIN, "smiles", L.OpsiLigan(minimisasi=False))
cek(cepat.status in ("siap", "peringatan"), "mode tanpa minimisasi tetap menghasilkan struktur")

# ------------------------------------------------------------------ masukan rusak dilaporkan, bukan diam
rusak = L.siapkan_satu("rusak", "ini bukan smiles(((", "smiles", L.OpsiLigan())
cek(rusak.status == "gagal", f"SMILES rusak berstatus gagal: {rusak.status}")
cek(bool(rusak.alasan), f"alasan kegagalan diisi: {rusak.alasan[:60] if rusak.alasan else '-'}")
cek(not rusak.pdbqt, "ligan gagal tidak menghasilkan PDBQT setengah jadi")

# ------------------------------------------------------------------ banyak ligan sekaligus
daftar = [("aspirin", ASPIRIN, "smiles"), ("rusak", "@@@", "smiles"), ("lisin", LISIN, "smiles")]
hasil = L.siapkan_banyak(daftar, L.OpsiLigan(minimisasi=False))
cek(len(hasil) == 3, f"siapkan_banyak mengembalikan satu hasil per masukan: {len(hasil)}")
status = [x.status for x in hasil]
cek("gagal" in status and sum(s in ("siap", "peringatan") for s in status) == 2,
    f"satu ligan rusak tidak menggagalkan yang lain: {status}")

print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
sys.exit(1 if gagal else 0)
