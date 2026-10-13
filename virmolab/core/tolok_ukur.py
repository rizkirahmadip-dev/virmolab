"""Tolok Ukur Validasi Ilmiah & Redocking Benchmark (PDBbind CASF Standard).

Menjalankan validasi redocking kristal 1HSG (HIV-1 Protease + Indinavir MK1)
untuk mengukur kemampuan docking engine (AutoDock Vina / AutoDock-GPU) dalam:
1. Mereproduksi pose kristal eksperimental (RMSD < 2.0 Å sebagai standar emas).
2. Mengidentifikasi interaksi katalitik krusial (dyad ASP25 / ASP125).
3. Menghitung efisiensi ligan (LE) dan afinitas ikatan (ΔG).
"""
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from . import analisis, catat, mesin, paths, prep_ligan, prep_reseptor


def ekstraksi_kristal_1hsg(path_pdb: Optional[Path] = None) -> Dict[str, str]:
    """Ekstraksi teks PDB protein dan teks PDB/PDBQT ligan MK1 dari berkas kristal 1HSG."""
    if path_pdb is None:
        calon = [
            paths.PAKET / "aset" / "contoh" / "1HSG.pdb",
            paths.PAKET / "aset" / "uji_1hsg.pdb",
        ]
        for c in calon:
            if c.exists():
                path_pdb = c
                break
    if path_pdb is None or not path_pdb.exists():
        raise FileNotFoundError("Berkas kristal 1HSG.pdb tidak ditemukan di virmolab/aset.")

    teks = path_pdb.read_text(encoding="utf-8", errors="replace")
    baris_protein = []
    baris_ligan = []

    for b in teks.splitlines():
        if b.startswith("ATOM"):
            baris_protein.append(b)
        elif b.startswith("HETATM"):
            resn = b[17:20].strip()
            if resn == "MK1":
                baris_ligan.append(b)

    if not baris_protein:
        raise ValueError("Tidak ada atom protein ditemukan di 1HSG.pdb.")
    if not baris_ligan:
        raise ValueError("Ligan kristal MK1 tidak ditemukan di 1HSG.pdb.")

    return {
        "protein_pdb": "\n".join(baris_protein) + "\nEND\n",
        "ligan_pdb": "\n".join(baris_ligan) + "\nEND\n",
    }


def jalankan_benchmark_1hsg(
    mesin_docking: str = "vina",
    exhaustiveness: int = 8,
    timeout: int = 180,
) -> Dict[str, Any]:
    """Jalankan benchmark redocking kristal 1HSG secara otomatis.

    Mengembalikan dict metrik:
      - sukses: bool (True jika RMSD <= 2.0 Å)
      - rmsd: float (Å)
      - energi: float (kcal/mol)
      - le: float
      - kontak_katalitik: list of str
      - waktu_detik: float
    """
    import time
    t0 = time.perf_counter()

    data_kristal = ekstraksi_kristal_1hsg()
    mol_kristal_ref = analisis.mol_kristal(data_kristal["ligan_pdb"])

    # 1. Preparasi Reseptor
    opsi_rec = prep_reseptor.OpsiReseptor(protonasi="templat", ph=7.4)
    h_rec = prep_reseptor.siapkan(data_kristal["protein_pdb"], opsi_rec)
    if not h_rec.pdbqt:
        raise RuntimeError("Preparasi reseptor 1HSG tidak menghasilkan PDBQT.")

    # 2. Preparasi Ligan MK1
    opsi_lig = prep_ligan.OpsiLigan(protonasi=False, minimisasi=False)
    h_lig = prep_ligan.siapkan_satu("indinavir_mk1", data_kristal["ligan_pdb"], "pdb", opsi_lig)
    if h_lig.status == "gagal":
        raise RuntimeError(f"Preparasi ligan MK1 gagal: {h_lig.alasan}")

    # 3. Grid box aktif sisi pengikatan 1HSG: pusat ~ (16.0, 25.0, 4.0), ukuran 20x20x20 Å
    # Hitung pusat geometri dari koordinat ligan kristal
    conf = mol_kristal_ref.GetConformer()
    pos = conf.GetPositions()
    pusat = pos.mean(axis=0).tolist()
    kotak = mesin.Kotak(pusat=pusat, ukuran=[20.0, 20.0, 20.0])

    param = mesin.Parameter(
        mesin=mesin_docking,
        exhaustiveness=exhaustiveness,
        num_modes=9,
        seed=42,
        cpu=1,
    )

    with tempfile.TemporaryDirectory(prefix="vmd_bench_") as d:
        dp = Path(d)
        f_rec = dp / "reseptor.pdbqt"
        f_lig = dp / "ligan.pdbqt"
        f_out = dp / "keluaran.pdbqt"

        f_rec.write_text(h_rec.pdbqt, encoding="utf-8")
        f_lig.write_text(h_lig.pdbqt, encoding="utf-8")

        cmd = mesin.perintah_vina(f_rec, f_lig, f_out, kotak, param)
        import subprocess
        nowin = 0x08000000
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=nowin)
        if not f_out.exists() or f_out.stat().st_size == 0:
            err = (p.stdout + p.stderr).decode("utf-8", "replace")
            raise RuntimeError(f"Eksekusi docking {mesin_docking} gagal: {err[:200]}")

        # 4. Baca hasil pose
        pose_list = mesin.baca_hasil(mesin_docking, f_out)
        if not pose_list:
            raise RuntimeError("Tidak ada pose terbaca dari berkas keluaran docking.")

        pose_terbaik = pose_list[0]
        mol_pose = analisis.pose_mol(h_lig.pdbqt, pose_terbaik.pdbqt)
        rmsd = analisis.rmsd_simetri(mol_pose, mol_kristal_ref)

        # 5. Analisis interaksi dan residu kontak
        rec_obj = analisis.baca_reseptor(h_rec.pdbqt)
        inter = analisis.interaksi(rec_obj, mol_pose)
        res_kontak = analisis.residu_kontak(inter)
        le = analisis.efisiensi_ligan(pose_terbaik.energi, mol_pose.GetNumHeavyAtoms())

    t1 = time.perf_counter()
    sukses = bool(rmsd <= 2.0)

    catat.log.info(
        f"Benchmark Redocking 1HSG ({mesin_docking}): RMSD={rmsd:.2f} Å, ΔG={pose_terbaik.energi:.2f} kcal/mol, "
        f"LE={le:.2f}, Sukses={'YA' if sukses else 'TIDAK'} ({t1 - t0:.1f} s)"
    )

    return {
        "target": "1HSG (HIV-1 Protease)",
        "ligan": "MK1 (Indinavir)",
        "mesin": mesin_docking,
        "sukses": sukses,
        "rmsd": round(float(rmsd), 2),
        "energi": round(float(pose_terbaik.energi), 2),
        "le": round(float(le), 2),
        "kontak_residu": res_kontak,
        "waktu_detik": round(float(t1 - t0), 1),
    }
