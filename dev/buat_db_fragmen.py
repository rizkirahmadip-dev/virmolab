"""Bangun basis data fragmen CReM dari pustaka lokal VirmoLab.

CReM menyediakan basis data ChEMBL siap pakai berukuran beberapa gigabyte. Alih-alih mengunduhnya,
basis data dibangun sendiri dari senyawa yang SUDAH ada di paket: obat disetujui (snapshot ChEMBL)
dan, bila terpasang, bahan alam COCONUT. Ukurannya jauh lebih kecil dan asal fragmennya tercatat.

Fragmen yang dihasilkan tetap berasal dari senyawa nyata, jadi analog yang dibangun darinya masih
masuk akal untuk disintesis. Karena jumlah senyawanya jauh lebih sedikit daripada ChEMBL penuh,
keragaman fragmennya juga lebih sempit; itu disebut apa adanya di dialog dan paragraf metode.

Jalankan: PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/buat_db_fragmen.py [--coconut]
"""
from pathlib import Path
import subprocess
import sys
import time

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

TUJUAN = AKAR / "virmolab" / "data" / "crem"
RADII = ("1", "2", "3")          # radius konteks yang dipakai core/generatif.py
MAKS_ATOM_INTI = "12"            # inti besar jarang berguna dan membengkakkan basis data


def kumpulkan_smiles(pakai_coconut: bool) -> list:
    from rdkit import Chem, RDLogger

    from virmolab.core import pustaka

    RDLogger.DisableLog("rdApp.*")
    sumber = [("obat", pustaka.obat())]
    if pakai_coconut and pustaka.coconut_ada():
        sumber.append(("coconut", pustaka.cari_coconut(batas=20000)))

    keluar, terlihat = [], set()
    for nama, daftar in sumber:
        n0 = len(keluar)
        for d in daftar:
            smi = d.get("smiles") or d.get("canonical_smiles") or ""
            m = Chem.MolFromSmiles(smi) if smi else None
            if m is None or m.GetNumHeavyAtoms() < 6 or m.GetNumHeavyAtoms() > 70:
                continue
            kanon = Chem.MolToSmiles(m)
            if kanon in terlihat:
                continue
            terlihat.add(kanon)
            keluar.append(kanon)
        print(f"  {nama}: {len(keluar) - n0} senyawa unik")
    return keluar


def main():
    pakai_coconut = "--coconut" in sys.argv
    TUJUAN.mkdir(parents=True, exist_ok=True)
    print("Mengumpulkan senyawa dari pustaka lokal…")
    smiles = kumpulkan_smiles(pakai_coconut)
    if len(smiles) < 100:
        raise SystemExit(f"Hanya {len(smiles)} senyawa terkumpul; basis data fragmen tidak dibangun.")

    masukan = TUJUAN / "senyawa_sumber.smi"
    masukan.write_text("\n".join(smiles) + "\n", encoding="utf-8")
    db = TUJUAN / "fragmen_lokal.db"
    if db.exists():
        db.unlink()

    exe = AKAR / ".venv" / "Scripts" / "cremdb_create.exe"
    if not exe.exists():
        raise SystemExit(f"{exe} tidak ada; pasang paket crem terlebih dahulu.")
    perintah = [str(exe), "-i", str(masukan), "-o", str(db), "-s", "lokal",
                "-r", *RADII, "--max-heavy-atoms", MAKS_ATOM_INTI, "--mode", "1", "-c", "4"]
    print(f"Membangun basis data fragmen dari {len(smiles)} senyawa (radius {' '.join(RADII)})…")
    t0 = time.time()
    p = subprocess.run(perintah, cwd=AKAR)
    if p.returncode != 0 or not db.exists():
        raise SystemExit(f"cremdb_create gagal (kode {p.returncode}).")

    ukuran = db.stat().st_size / 2 ** 20
    print(f"Selesai dalam {time.time() - t0:.0f} detik. {db} = {ukuran:.1f} MB")
    (TUJUAN / "sumber.txt").write_text(
        f"Basis data fragmen CReM dibangun dari {len(smiles)} senyawa pustaka lokal VirmoLab "
        f"(obat disetujui snapshot ChEMBL{', bahan alam COCONUT' if pakai_coconut else ''}).\n"
        f"Radius konteks: {' '.join(RADII)}. Maksimum atom berat inti: {MAKS_ATOM_INTI}.\n"
        f"Dibangun dengan cremdb_create (crem, BSD-3-Clause) pada {time.strftime('%Y-%m-%d')}.\n",
        encoding="utf-8")
    masukan.unlink()


if __name__ == "__main__":
    main()
