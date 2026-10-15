"""Validasi protokol induced fit (dev/eksperimen/induced_fit.py) dengan kasus cross-docking Sherman dkk. (2006).

Tiap kasus: ligan kristal struktur B didocking ke reseptor struktur A (rantai samping kantong A berbeda dengan B,
jadi docking kaku meleset). Diukur RMSD pose terhadap ligan kristal B setelah disuperposisikan ke kerangka A.
Dibandingkan: docking kaku biasa vs induced fit. Angka acuan makalah ada di ACUAN.

  PYTHONPATH=. .venv/Scripts/python.exe dev/uji_induced_fit.py            (semua kasus)
  PYTHONPATH=. .venv/Scripts/python.exe dev/uji_induced_fit.py 1kim 2acr  (reseptor tertentu)

Struktur PDB diunduh sekali ke C:/VirmoLab-tolok-ukur/unduhan/pdb, hasil ke C:/VirmoLab-tolok-ukur/hasil/if_*.json
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

sys.path.insert(0, str(AKAR / "dev" / "eksperimen"))
import induced_fit as IF                                              # noqa: E402
from virmolab.core import analisis, mesin as M                        # noqa: E402
from virmolab.core import prep_ligan, prep_reseptor, validasi_protokol as VP   # noqa: E402

UNDUH = Path("C:/VirmoLab-tolok-ukur/unduhan/pdb")
HASIL = Path("C:/VirmoLab-tolok-ukur/hasil")
# (reseptor, sumber ligan, nama residu ligan, RMSD kaku & RMSD induced fit menurut Tabel 1 Sherman dkk. 2006)
KASUS = [
    ("Aldose reductase", "2acr", "1ah3", "TOL", 6.5, 0.9),
    ("CDK2", "1dm2", "1aq1", "STU", 6.2, 0.8),
    ("Estrogen receptor", "1err", "3ert", "OHT", 5.3, 1.0),
    ("Thymidine kinase", "1kim", "1ki4", "BTD", 4.7, 0.4),
    ("Neuraminidase", "1nsc", "1a4q", "DPC", 3.9, 0.8),
]


def unduh(kode):
    UNDUH.mkdir(parents=True, exist_ok=True)
    f = UNDUH / f"{kode.lower()}.pdb"
    if not f.exists():
        with urllib.request.urlopen(f"https://files.rcsb.org/download/{kode.upper()}.pdb", timeout=60) as r:
            f.write_bytes(r.read())
    return f.read_text(encoding="utf-8", errors="replace")


def siapkan(kode):
    """Reseptor PDB -> (PDBQT, PDB untuk Meeko/relaksasi)."""
    h = prep_reseptor.siapkan(unduh(kode), prep_reseptor.OpsiReseptor(kofaktor=True))
    return h.pdbqt, (h.pdb_meeko or h.pdb_bersih)


def ligan_di_kerangka(kode_ligan, kode_reseptor, resn):
    """Ligan kristal struktur B dipindahkan ke kerangka struktur A lewat superposisi Cα. -> (teks PDB, Mol)"""
    teks_b, teks_a = unduh(kode_ligan), unduh(kode_reseptor)
    lig = VP.ligan_kristal_terbesar(teks_b, resn)
    if not lig:
        raise RuntimeError(f"{kode_ligan}: ligan {resn} tidak ditemukan.")
    sp = VP._superposisi(VP._peta_ca(teks_b), VP._peta_ca(teks_a))
    if sp is None:
        raise RuntimeError(f"{kode_ligan}->{kode_reseptor}: Cα bersama terlalu sedikit.")
    R, t, rmsd_ca, n_ca = sp
    baris = []
    for b in lig.splitlines():
        if b.startswith(("ATOM", "HETATM")):
            xyz = np.array([float(b[30:38]), float(b[38:46]), float(b[46:54])]) @ R.T + t
            baris.append(f"{b[:30]}{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}{b[54:]}")
        else:
            baris.append(b)
    return "\n".join(baris) + "\n", rmsd_ca, n_ca


def kotak_dari(teks_lig_pdb, tepi=5.0, minimum=18.0):
    xyz = np.array([[float(b[30:38]), float(b[38:46]), float(b[46:54])] for b in teks_lig_pdb.splitlines()
                    if b.startswith(("ATOM", "HETATM"))])
    pusat = ((xyz.max(0) + xyz.min(0)) / 2).round(3).tolist()
    ukuran = [max(minimum, round(float(v), 1)) for v in (xyz.max(0) - xyz.min(0) + 2 * tepi)]
    return M.Kotak(pusat=pusat, ukuran=ukuran, spasi=0.375)


def satu_kasus(nama, rec, lig_kode, resn, acuan_kaku, acuan_if, opsi):
    t0 = time.time()
    print(f"\n=== {nama}: ligan {resn} dari {lig_kode.upper()} -> reseptor {rec.upper()} "
          f"(acuan makalah: kaku {acuan_kaku} Å, IFD {acuan_if} Å)", flush=True)
    rec_pdbqt, rec_pdb = siapkan(rec)
    lig_pdb, rmsd_ca, n_ca = ligan_di_kerangka(lig_kode, rec, resn)
    print(f"superposisi Cα: {rmsd_ca:.2f} Å atas {n_ca} residu", flush=True)
    kristal = analisis.mol_kristal(lig_pdb)
    h_lig = prep_ligan.siapkan_satu(resn, lig_pdb, "pdb", prep_ligan.OpsiLigan(protonasi=True, minimisasi=True))
    if h_lig.status == "gagal" or not h_lig.pdbqt:
        print("LEWAT: ligan gagal disiapkan -", h_lig.alasan, flush=True)
        return None
    kotak = kotak_dari(lig_pdb)

    def rmsd(pose):
        return round(float(analisis.rmsd_simetri(analisis.pose_mol(h_lig.pdbqt, pose), kristal)), 2)

    import tempfile
    with tempfile.TemporaryDirectory(prefix="if_kaku_") as tmp:
        pose, _o = IF._vina(rec_pdbqt, h_lig.pdbqt, kotak, opsi, Path(tmp))
    r_kaku = rmsd(pose[0].pdbqt)
    print(f"docking kaku : {pose[0].energi:6.2f} kkal/mol, RMSD {r_kaku} Å", flush=True)
    h = IF.jalankan(rec_pdb, rec_pdbqt, h_lig.pdbqt, kotak, opsi=opsi,
                    lapor=lambda s: print("  " + s, flush=True), banding_kaku=False)
    h.energi_kaku = pose[0].energi
    r_if = rmsd(h.pose_pdbqt)
    r_lunak = rmsd(h.pose_lunak_pdbqt) if h.pose_lunak_pdbqt else None
    if r_lunak is not None:
        print(f"docking lunak: {h.energi_lunak:6.2f} kkal/mol, RMSD {r_lunak} Å", flush=True)
    print(f"induced fit  : {h.energi:6.2f} kkal/mol, RMSD {r_if} Å, rantai samping bergeser "
          f"{h.rmsd_sisi} Å, {h.n_pose_relaks} pose direlaksasi, titik awal {h.asal_pose}, "
          f"{h.detik:.0f} s", flush=True)
    return {"nama": nama, "reseptor": rec.upper(), "ligan": lig_kode.upper(), "resn": resn,
            "rmsd_ca_superposisi": round(rmsd_ca, 2), "rmsd_kaku": r_kaku, "rmsd_if": r_if,
            "acuan_kaku": acuan_kaku, "acuan_if": acuan_if, "energi_kaku": round(pose[0].energi, 2),
            "energi_if": round(h.energi, 2), "energi_lunak": round(h.energi_lunak, 2), "rmsd_lunak": r_lunak,
            "rmsd_sisi": h.rmsd_sisi, "n_residu": len(h.residu), "n_pose_relaks": h.n_pose_relaks, "asal_pose": h.asal_pose, "detik": round(time.time() - t0, 1),
            "residu": h.residu}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("kasus", nargs="*", help="kode reseptor (kosong = semua)")
    ap.add_argument("--ps-anil", type=float, default=10.0)
    ap.add_argument("--n-pose", type=int, default=3)
    ap.add_argument("--exhaustiveness", type=int, default=16)
    a = ap.parse_args()
    pilih = {x.lower() for x in a.kasus}
    opsi = IF.OpsiIF(exhaustiveness=a.exhaustiveness, radius=5.0, maks_residu=20, ps_anil=a.ps_anil,
                     n_pose=a.n_pose)
    hasil = []
    for nama, rec, lig, resn, ak, ai in KASUS:
        if pilih and rec not in pilih:
            continue
        try:
            h = satu_kasus(nama, rec, lig, resn, ak, ai, opsi)
            if h:
                hasil.append(h)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"GAGAL {rec}: {e}", flush=True)
    if not hasil:
        return
    HASIL.mkdir(parents=True, exist_ok=True)
    f = HASIL / "induced_fit.json"
    lama = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    lama.update({"tanggal": time.strftime("%Y-%m-%d %H:%M"), "opsi": vars(opsi)})
    lama.setdefault("kasus", {}).update({h["reseptor"]: h for h in hasil})
    f.write_text(json.dumps(lama, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n== Ringkasan (RMSD Å terhadap ligan kristal)")
    print(f"{'kasus':22s} {'kaku':>6s} {'IFD':>6s} {'makalah kaku':>13s} {'makalah IFD':>12s}")
    for h in hasil:
        print(f"{h['reseptor'] + '<-' + h['ligan']:22s} {h['rmsd_kaku']:6.2f} {h['rmsd_if']:6.2f} "
              f"{h['acuan_kaku']:13.1f} {h['acuan_if']:12.1f}")
    baik = sum(1 for h in hasil if h["rmsd_if"] <= 2.0)
    baik_kaku = sum(1 for h in hasil if h["rmsd_kaku"] <= 2.0)
    print(f"RMSD ≤ 2 Å: induced fit {baik}/{len(hasil)}, docking kaku {baik_kaku}/{len(hasil)}")
    print("tersimpan", f)


if __name__ == "__main__":
    main()
