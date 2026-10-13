"""Uji core/proyek.py: simpan–buka pulang-pergi, penulisan atomik + cadangan, migrasi format lawas,
id ligan unik, SMILES dari PDBQT, dan penolakan folder yang bukan proyek.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_proyek.py
"""
import json
import shutil
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from virmodock.core.proyek import Proyek, VERSI_FORMAT, migrasi_proyek, nama_aman

OUT = AKAR / "dev" / "uji" / "proyek"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


# ------------------------------------------------------------------ nama aman
cek(nama_aman("1HSG / uji baru") == "1HSG_uji_baru", f"nama_aman membersihkan tanda baca: {nama_aman('1HSG / uji baru')}")
cek(nama_aman("   ") == "x", "nama kosong tidak menghasilkan nama folder kosong")
cek(len(nama_aman("x" * 200)) <= 80, "nama panjang dipotong")

# ------------------------------------------------------------------ simpan dan buka kembali
pr = Proyek.baru(OUT, "Uji Proyek")
pr.reseptor = {"nama": "1HSG", "pdbqt": "reseptor/reseptor.pdbqt", "atom": 1842}
pr.ligan = [{"id": "MK1", "nama": "MK1", "status": "siap", "pdbqt": "ligan/pdbqt/MK1.pdbqt"}]
pr.kotak = {"pusat": [13.0, 22.5, 5.6], "ukuran": [22.5, 22.5, 22.5], "spasi": 0.375}
pr.catatan = "catatan uji — koma, kutip \" dan unicode Å"
pr.simpan()

pr2 = Proyek.buka(pr.folder)
cek(pr2.nama == pr.nama and pr2.reseptor["nama"] == "1HSG", "nama dan reseptor pulih setelah dibuka ulang")
cek(pr2.kotak["pusat"] == [13.0, 22.5, 5.6], "kotak docking pulih persis")
cek(pr2.catatan == pr.catatan, "catatan dengan tanda kutip dan karakter Å pulih utuh")
cek(len(pr2.ligan) == 1 and pr2.ligan[0]["id"] == "MK1", "daftar ligan pulih")

data = json.loads((pr.folder / "proyek.json").read_text(encoding="utf-8"))
cek(data.get("format") == VERSI_FORMAT and data.get("aplikasi") == "VirmoDock",
    f"berkas menyimpan penanda format {data.get('format')} dan aplikasi")

# ------------------------------------------------------------------ cadangan dan penulisan atomik
for i in range(3):
    pr.catatan = f"revisi {i}"
    pr.simpan()
cadangan = sorted((pr.folder / ".cadangan").glob("*.json")) if (pr.folder / ".cadangan").exists() else []
cek(bool(cadangan), f"cadangan dibuat tiap simpan ({len(cadangan)} berkas)")
cek(not list(pr.folder.glob("*.tmp")) and not list(pr.folder.glob("*.part")),
    "tidak ada berkas sementara tertinggal setelah penulisan atomik")

# ------------------------------------------------------------------ id ligan unik
pr.ligan.append({"id": pr.id_ligan_baru("MK1"), "nama": "MK1"})
cek(pr.ligan[-1]["id"] != "MK1", f"id ligan kedua dibuat unik: {pr.ligan[-1]['id']}")
cek(pr.cari_ligan("MK1") is not None and pr.cari_ligan("tidak ada") is None, "cari_ligan menemukan dan menolak dengan benar")

pr.ligan = [{"id": "a", "status": "siap", "pdbqt": "x.pdbqt"}, {"id": "b", "status": "gagal", "pdbqt": "y.pdbqt"},
            {"id": "c", "status": "siap"}]
siap = [l["id"] for l in pr.ligan_siap()]
cek(siap == ["a"], f"ligan_siap hanya yang berstatus siap dan punya PDBQT: {siap}")

# ------------------------------------------------------------------ migrasi format lawas
lawas = {"nama": "Proyek 0.9", "reseptor": {"nama": "3KS3"}}
baru = migrasi_proyek(dict(lawas))
cek(baru.get("format") == VERSI_FORMAT, "migrasi menetapkan versi format terkini")
for kunci in ("ligan", "job", "objek", "uji_grafik", "komposer"):
    cek(kunci in baru, f"migrasi menambahkan kunci yang hilang: {kunci}")
cek(baru["nama"] == "Proyek 0.9" and baru["reseptor"]["nama"] == "3KS3", "migrasi tidak mengubah data yang sudah ada")
cek(migrasi_proyek(None) == {} and migrasi_proyek("bukan dict") == {}, "migrasi menolak masukan yang bukan dict")

folder_lawas = OUT / "Lawas.vmd"
folder_lawas.mkdir()
(folder_lawas / "proyek.json").write_text(json.dumps(lawas), encoding="utf-8")
pr3 = Proyek.buka(folder_lawas)
cek(pr3.nama == "Proyek 0.9" and pr3.ligan == [] and pr3.job == [],
    "proyek lawas tanpa daftar ligan/job tetap bisa dibuka")

# ------------------------------------------------------------------ folder yang bukan proyek
bukan = OUT / "bukan_proyek"
bukan.mkdir()
try:
    Proyek.buka(bukan)
    cek(False, "folder tanpa proyek.json seharusnya ditolak")
except FileNotFoundError as e:
    cek("proyek.json" in str(e), f"folder bukan proyek ditolak dengan pesan jelas: {str(e)[:60]}")

# ------------------------------------------------------------------ SMILES ligan dari PDBQT
smi_mk1 = "CC(C)(C)NC(=O)[C@@H]1C[NH+](Cc2cccnc2)CC[NH+]1C"
pr4 = Proyek.baru(OUT, "SMILES")
pr4.siapkan_folder()
pdbqt = pr4.p("ligan", "pdbqt", "L1.pdbqt")
pdbqt.parent.mkdir(parents=True, exist_ok=True)
pdbqt.write_text(f"REMARK  Name = L1\nREMARK SMILES {smi_mk1}\nREMARK SMILES IDX 1 1\nATOM\n", encoding="utf-8")
lig = {"id": "L1", "nama": "L1", "pdbqt": "ligan/pdbqt/L1.pdbqt"}
pr4.ligan = [lig]
smi = pr4.smiles_ligan(lig)
cek(bool(smi) and "+" not in smi, f"SMILES dibaca dari REMARK PDBQT dan dinetralkan: {smi[:48]}")
cek(pr4.smiles_ligan({"id": "x"}) == "" and pr4.smiles_ligan(None) == "",
    "ligan tanpa sumber struktur mengembalikan SMILES kosong, bukan galat")

print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
sys.exit(1 if gagal else 0)
