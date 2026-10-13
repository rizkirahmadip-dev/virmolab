"""Orkestrasi Paket Validasi Protokol Docking Terstandar untuk Publikasi Ilmiah.

Alur 4 tahap komprehensif:
1. Redocking ligan ko-kristal eksperimental (evaluasi reproduktibilitas pose, RMSD ≤ 2,0 Å).
2. Cross-docking (docking silang antar-struktur PDB target yang sama di proyek).
3. Evaluasi pengayaan (Enrichment): senyawa aktif (ChEMBL) + decoy gaya DUD-E lokal
   -> ROC-AUC, BEDROC (α = 20), EF 1%, EF 5%, logAUC.
4. Validasi kualitas fisik pose (PoseBusters % PB-valid).
Menghasilkan ringkasan terstruktur, paragraf metode siap pakai, dan figur publikasi.
"""
from dataclasses import dataclass, field
import html
import os
from pathlib import Path
import tempfile
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from . import analisis, catat, grafik_uji, mesin, prep_ligan, prep_reseptor, qc, uji


@dataclass
class HasilRedocking:
    sukses: bool
    rmsd: float
    energi: float
    ligan: str
    reseptor: str
    pose_pdbqt: str = ""
    waktu_detik: float = 0.0


@dataclass
class HasilCrossDocking:
    tersedia: bool
    label_struktur: List[str]
    matriks_rmsd: List[List[Optional[float]]]     # None = tidak dapat dihitung (docking gagal / struktur tak sejajar)
    matriks_energi: List[List[Optional[float]]]
    alasan: str = ""
    catatan: List[str] = field(default_factory=list)


@dataclass
class HasilEnrichment:
    n_aktif: int
    n_decoy: int
    auc: float
    auc_ci: Optional[Tuple[float, float]]
    bedroc: float
    ef1: float
    ef5: float
    logauc: float
    p_nilai: float
    potong_youden: float
    sensitivitas: float
    spesifisitas: float
    kurva_roc: Dict[str, Any]
    skor_aktif: List[float]
    skor_decoy: List[float]
    n_gagal_aktif: int = 0       # docking gagal -> dikeluarkan dari ROC (bukan dihitung sebagai skor 0)
    n_gagal_decoy: int = 0
    peringatan: List[str] = field(default_factory=list)


@dataclass
class HasilPoseBusters:
    tersedia: bool
    total_pose: int
    lulus_valid: int
    persen_valid: float
    rincian_gagal: Dict[str, int]


_PELARUT_ION = {"HOH", "WAT", "SO4", "GOL", "EDO", "DMS", "NA", "CL", "MG", "ZN", "CA", "K", "PO4", "ACT", "PEG", "MPD"}


def ligan_kristal_terbesar(teks_pdb: str, nama_ligan: str = "") -> str:
    """Satu residu HETATM terbesar (atom berat terbanyak) sebagai ligan kristal.

    Menggabungkan semua HETATM (atau semua salinan residu bernama sama) menghasilkan 'ligan' berisi beberapa molekul,
    sehingga pusat kotak dan RMSD acuan salah.
    """
    kelompok: Dict[Tuple[str, str, str], List[str]] = {}
    for b in teks_pdb.splitlines():
        if not b.startswith("HETATM"):
            continue
        resn = b[17:20].strip()
        if resn in _PELARUT_ION or (nama_ligan and resn != nama_ligan):
            continue
        if b[76:78].strip().upper() == "H":
            continue
        kelompok.setdefault((resn, b[21:22], b[22:27].strip()), []).append(b)
    if not kelompok:
        return ""
    terbaik = max(kelompok.values(), key=len)
    return "\n".join(x for x in terbaik if x[16:17] in (" ", "A")) + "\nEND\n"


def _peta_ca(teks_pdb: str) -> Dict[Tuple[str, str, str], np.ndarray]:
    ca = {}
    for b in teks_pdb.splitlines():
        if b.startswith("ATOM") and b[12:16].strip() == "CA" and b[16:17] in (" ", "A"):
            ca[(b[21:22], b[22:27].strip(), b[17:20].strip())] = np.array(
                [float(b[30:38]), float(b[38:46]), float(b[46:54])])
    return ca


def _superposisi(ca_dari: Dict, ca_ke: Dict, minimal: int = 30) -> Optional[Tuple[np.ndarray, np.ndarray, float, int]]:
    """Transformasi rigid (R, t) yang memetakan koordinat struktur 'dari' ke kerangka 'ke' lewat Cα bersama.

    Mengembalikan (R, t, rmsd_ca, n_ca) atau None bila residu bersama < minimal (bukan target yang sama).
    """
    kunci = sorted(set(ca_dari) & set(ca_ke))
    if len(kunci) < minimal:
        return None
    P = np.array([ca_dari[k] for k in kunci])
    Q = np.array([ca_ke[k] for k in kunci])
    pc, qc_ = P.mean(0), Q.mean(0)
    H = (P - pc).T @ (Q - qc_)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    t = qc_ - R @ pc
    rmsd = float(np.sqrt((((P @ R.T + t) - Q) ** 2).sum(1).mean()))
    return R, t, rmsd, len(kunci)


def jalankan_redocking_mandiri(
    path_pdb_kompleks: Path,
    nama_ligan: str = "",
    mesin_docking: str = "vina",
    exhaustiveness: int = 8,
    timeout: int = 180,
    lapor: Optional[Any] = None,
) -> HasilRedocking:
    """Eksekusi redocking ligan kristal mandiri dari berkas PDB kompleks."""
    import time
    t0 = time.perf_counter()
    log = (lambda s: lapor.log.emit(s)) if lapor and hasattr(lapor, "log") else (lambda s: catat.log.info(s))

    log(f"Mempersiapkan redocking dari {path_pdb_kompleks.name}...")
    teks = path_pdb_kompleks.read_text(encoding="utf-8", errors="replace")

    baris_rec = [b for b in teks.splitlines() if b.startswith("ATOM") and b[16:17] in (" ", "A")]
    pdb_lig = ligan_kristal_terbesar(teks, nama_ligan)

    if not baris_rec or not pdb_lig:
        raise ValueError(f"Tidak dapat mengekstraksi protein atau ligan kristal dari {path_pdb_kompleks.name}.")

    pdb_rec = "\n".join(baris_rec) + "\nEND\n"

    mol_ref = analisis.mol_kristal(pdb_lig)
    if mol_ref is None:
        raise ValueError("Gagal membaca struktur konformasi ligan kristal acuan.")

    # Preparasi
    h_rec = prep_reseptor.siapkan(pdb_rec, prep_reseptor.OpsiReseptor(protonasi="templat", ph=7.4))
    if not h_rec.pdbqt:
        raise RuntimeError("Preparasi reseptor tidak menghasilkan PDBQT.")

    h_lig = prep_ligan.siapkan_satu("ligan_kristal", pdb_lig, "pdb", prep_ligan.OpsiLigan(protonasi=False, minimisasi=False))
    if h_lig.status == "gagal":
        raise RuntimeError(f"Preparasi ligan kristal gagal: {h_lig.alasan}")

    # Pusat dan ukuran grid box
    pos = mol_ref.GetConformer().GetPositions()
    pusat = pos.mean(axis=0).tolist()
    kotak = mesin.Kotak(pusat=pusat, ukuran=[20.0, 20.0, 20.0])

    param = mesin.Parameter(
        mesin=mesin_docking,
        exhaustiveness=exhaustiveness,
        num_modes=9,
        seed=42,
        cpu=min(4, os.cpu_count() or 1),
    )

    with tempfile.TemporaryDirectory(prefix="vmd_val_redock_") as tmp:
        dp = Path(tmp)
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
            raise RuntimeError(f"Docking redocking gagal: {err[:200]}")

        pose_list = mesin.baca_hasil(mesin_docking, f_out)
        if not pose_list:
            raise RuntimeError("Tidak ada pose docking yang dihasilkan pada redocking.")

        pose_terbaik = pose_list[0]
        pdbqt_str = pose_terbaik.pdbqt if hasattr(pose_terbaik, "pdbqt") else pose_terbaik.get("pdbqt", "")
        en_val = float(pose_terbaik.energi if hasattr(pose_terbaik, "energi") else pose_terbaik.get("energi", 0.0))

        # Hitung RMSD simetri terhadap kristal
        try:
            mol_dock = analisis.pose_mol(h_lig.pdbqt, pdbqt_str)
            r = analisis.rmsd_simetri(mol_dock, mol_ref)
        except Exception as e:
            # Jangan diganti angka palsu: RMSD yang tak terhitung berarti validasi tidak dapat dinilai
            raise RuntimeError(f"RMSD terhadap kristal tidak dapat dihitung: {e}") from e

        waktu = time.perf_counter() - t0
        return HasilRedocking(
            sukses=bool(r <= 2.0),
            rmsd=round(float(r), 2),
            energi=round(en_val, 2),
            ligan=nama_ligan or "Ligan kristal",
            reseptor=path_pdb_kompleks.stem,
            pose_pdbqt=pdbqt_str,
            waktu_detik=round(waktu, 1),
        )


def jalankan_cross_docking(
    daftar_kompleks: List[Tuple[str, Path]],
    mesin_docking: str = "vina",
    exhaustiveness: int = 4,
    timeout: int = 180,
    lapor: Optional[Any] = None,
) -> HasilCrossDocking:
    """Cross-docking berpasangan antar struktur PDB dari target yang sama.

    Ligan struktur j di-docking ke reseptor struktur i; RMSD dihitung terhadap pose kristal ligan j setelah
    struktur j disuperposisikan ke struktur i lewat Cα bersama (tanpa superposisi, RMSD antar-kerangka tak bermakna).
    Sel yang tak dapat dihitung bernilai None, bukan 0.

    daftar_kompleks: list [(label_id, path_pdb)]
    """
    import subprocess
    log = (lambda s_: lapor.log.emit(s_)) if lapor and hasattr(lapor, "log") else (lambda s_: catat.log.info(s_))

    if len(daftar_kompleks) < 2:
        return HasilCrossDocking(
            tersedia=False,
            label_struktur=[k[0] for k in daftar_kompleks],
            matriks_rmsd=[],
            matriks_energi=[],
            alasan="Dilewati — butuh ≥ 2 struktur PDB target.",
        )

    n = len(daftar_kompleks)
    log(f"Menjalankan cross-docking untuk {n} struktur PDB...")
    labels = [k[0] for k in daftar_kompleks]
    matriks_rmsd: List[List[Optional[float]]] = [[None] * n for _ in range(n)]
    matriks_energi: List[List[Optional[float]]] = [[None] * n for _ in range(n)]
    catatan: List[str] = []

    mols_ref, pdb_ligs, recs_pdbqt, kotaks, peta = [], [], [], [], []
    for label, path in daftar_kompleks:
        teks = path.read_text(encoding="utf-8", errors="replace")
        baris_rec = [b for b in teks.splitlines() if b.startswith("ATOM") and b[16:17] in (" ", "A")]
        pdb_lig = ligan_kristal_terbesar(teks)
        if not baris_rec or not pdb_lig:
            raise ValueError(f"{label}: protein atau ligan kristal tidak ditemukan di {path.name}.")
        m_ref = analisis.mol_kristal(pdb_lig)
        if m_ref is None:
            raise ValueError(f"{label}: ligan kristal tidak terbaca.")
        h_rec = prep_reseptor.siapkan("\n".join(baris_rec) + "\nEND\n",
                                      prep_reseptor.OpsiReseptor(protonasi="templat", ph=7.4))
        if not h_rec.pdbqt:
            raise RuntimeError(f"{label}: preparasi reseptor gagal.")
        pos = m_ref.GetConformer().GetPositions()
        mols_ref.append(m_ref)
        pdb_ligs.append(pdb_lig)
        recs_pdbqt.append(h_rec.pdbqt)
        kotaks.append(mesin.Kotak(pusat=pos.mean(axis=0).tolist(), ukuran=[20.0, 20.0, 20.0]))
        peta.append(_peta_ca(teks))

    param = mesin.Parameter(mesin=mesin_docking, exhaustiveness=exhaustiveness, num_modes=5, seed=42,
                            cpu=min(4, os.cpu_count() or 1))

    for i in range(n):
        for j in range(n):
            # i = reseptor, j = ligan yang di-docking
            if i == j:
                T = (np.eye(3), np.zeros(3))
            else:
                sp = _superposisi(peta[j], peta[i])
                if sp is None:
                    catatan.append(f"{labels[j]}→{labels[i]}: Cα bersama < 30 residu, struktur tidak dapat "
                                   f"disejajarkan (bukan target yang sama?).")
                    continue
                if sp[2] > 3.0:
                    catatan.append(f"{labels[j]}→{labels[i]}: RMSD Cα superposisi {sp[2]:.1f} Å (> 3 Å), "
                                   f"perbedaan konformasi besar.")
                T = (sp[0], sp[1])
            h_lig = prep_ligan.siapkan_satu(f"lig_{j}", pdb_ligs[j], "pdb",
                                            prep_ligan.OpsiLigan(protonasi=False, minimisasi=False))
            if h_lig.status == "gagal" or not h_lig.pdbqt:
                catatan.append(f"{labels[j]}: ligan gagal disiapkan ({h_lig.alasan}).")
                continue
            with tempfile.TemporaryDirectory(prefix="vmd_cross_") as tmp:
                dp = Path(tmp)
                f_r, f_l, f_o = dp / "rec.pdbqt", dp / "lig.pdbqt", dp / "out.pdbqt"
                f_r.write_text(recs_pdbqt[i], encoding="utf-8")
                f_l.write_text(h_lig.pdbqt, encoding="utf-8")
                try:
                    subprocess.run(mesin.perintah_vina(f_r, f_l, f_o, kotaks[i], param), capture_output=True,
                                   timeout=timeout, creationflags=0x08000000)
                except subprocess.TimeoutExpired:
                    catatan.append(f"{labels[j]}→{labels[i]}: docking melewati batas waktu {timeout} dtk.")
                    continue
                if not (f_o.exists() and f_o.stat().st_size > 0):
                    catatan.append(f"{labels[j]}→{labels[i]}: docking tidak menghasilkan pose.")
                    continue
                poses = mesin.baca_hasil(mesin_docking, f_o)
                if not poses:
                    continue
                p_0 = poses[0]
                en = float(p_0.energi if hasattr(p_0, "energi") else p_0.get("energi", 0.0))
                pdbqt_pose = p_0.pdbqt if hasattr(p_0, "pdbqt") else p_0.get("pdbqt", "")
                try:
                    from rdkit import Chem
                    ref = Chem.Mol(mols_ref[j])
                    xyz = ref.GetConformer().GetPositions() @ T[0].T + T[1]   # kristal j -> kerangka reseptor i
                    for k_, v in enumerate(xyz):
                        ref.GetConformer().SetAtomPosition(k_, v.tolist())
                    r = analisis.rmsd_simetri(analisis.pose_mol(h_lig.pdbqt, pdbqt_pose), ref)
                except Exception as e:
                    catatan.append(f"{labels[j]}→{labels[i]}: RMSD tak dapat dihitung ({e}).")
                    continue
                matriks_rmsd[i][j] = round(float(r), 2)
                matriks_energi[i][j] = round(en, 2)

    return HasilCrossDocking(
        tersedia=True,
        label_struktur=labels,
        matriks_rmsd=matriks_rmsd,
        matriks_energi=matriks_energi,
        alasan="",
        catatan=catatan,
    )


def jalankan_enrichment(
    path_reseptor_pdbqt: Path,
    kotak: mesin.Kotak,
    aktif_list: List[Dict[str, Any]],
    decoy_list: List[Dict[str, Any]],
    mesin_docking: str = "vina",
    exhaustiveness: int = 4,
    timeout: int = 120,
    lapor: Optional[Any] = None,
    min_aktif: int = 3,
    min_decoy: int = 3,
    batal: Optional[Any] = None,
) -> HasilEnrichment:
    """Eksekusi penapisan virtual aktif vs decoy dan kalkulasi metrik pengayaan (ROC, BEDROC, EF, logAUC)."""
    log = (lambda s: lapor.log.emit(s)) if lapor and hasattr(lapor, "log") else (lambda s: catat.log.info(s))

    total = len(aktif_list) + len(decoy_list)
    log(f"Memulai docking pengayaan untuk {len(aktif_list)} aktif dan {len(decoy_list)} decoy (total {total})...")

    param = mesin.Parameter(mesin=mesin_docking, exhaustiveness=exhaustiveness, num_modes=3, seed=42, cpu=min(4, os.cpu_count() or 1))

    def _dock_satu(nama: str, smi: str, dp: Path) -> Optional[float]:
        """ΔG pose terbaik, atau None bila docking gagal. Kegagalan TIDAK boleh diganti skor 0: pada ROC, 0 kcal/mol
        berarti 'paling tidak aktif', sehingga aktif yang gagal dihukum dan decoy yang gagal menaikkan AUC secara palsu."""
        try:
            h_lig = prep_ligan.siapkan_satu(nama, smi, "smiles", prep_ligan.OpsiLigan(protonasi=False, minimisasi=True))
            if h_lig.status == "gagal" or not h_lig.pdbqt:
                return None
            f_lig = dp / f"{nama}.pdbqt"
            f_out = dp / f"{nama}_out.pdbqt"
            f_lig.write_text(h_lig.pdbqt, encoding="utf-8")

            cmd = mesin.perintah_vina(path_reseptor_pdbqt, f_lig, f_out, kotak, param)
            import subprocess
            subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=0x08000000)

            if f_out.exists() and f_out.stat().st_size > 0:
                poses = mesin.baca_hasil(mesin_docking, f_out)
                if poses:
                    p_0 = poses[0]
                    return float(p_0.energi if hasattr(p_0, "energi") else p_0.get("energi", 0.0))
            return None
        except Exception as err:
            catat.log.debug(f"Docking {nama} gagal: {err}")
            return None

    skor_aktif = []
    skor_decoy = []

    with tempfile.TemporaryDirectory(prefix="vmd_enrich_") as tmp:
        dp = Path(tmp)

        # Docking aktif
        for i, a in enumerate(aktif_list):
            if batal and batal():
                raise InterruptedError("Dibatalkan pengguna.")
            nama = f"act_{i + 1}"
            smi = a["smiles"]
            sc = _dock_satu(nama, smi, dp)
            skor_aktif.append(sc)
            if lapor and hasattr(lapor, "progres"):
                lapor.progres.emit(i + 1, total, f"Docking aktif {i + 1}/{len(aktif_list)}")

        # Docking decoy
        for j, d in enumerate(decoy_list):
            if batal and batal():
                raise InterruptedError("Dibatalkan pengguna.")
            nama = f"dec_{j + 1}"
            smi = d["smiles"]
            sc = _dock_satu(nama, smi, dp)
            skor_decoy.append(sc)
            if lapor and hasattr(lapor, "progres"):
                lapor.progres.emit(len(aktif_list) + j + 1, total, f"Docking decoy {j + 1}/{len(decoy_list)}")

    n_gagal_a = sum(1 for x in skor_aktif if x is None)
    n_gagal_d = sum(1 for x in skor_decoy if x is None)
    skor_aktif = [x for x in skor_aktif if x is not None]
    skor_decoy = [x for x in skor_decoy if x is not None]
    if len(skor_aktif) < min_aktif or len(skor_decoy) < min_decoy:
        raise ValueError(f"Docking berhasil untuk {len(skor_aktif)} aktif dan {len(skor_decoy)} decoy "
                         f"(gagal {n_gagal_a} dan {n_gagal_d}); minimum {min_aktif} aktif dan {min_decoy} decoy "
                         f"diperlukan untuk menghitung ROC.")
    peringatan: List[str] = []
    if n_gagal_a or n_gagal_d:
        peringatan.append(f"{n_gagal_a} aktif dan {n_gagal_d} decoy gagal di-docking dan dikeluarkan dari analisis "
                          f"(tidak dihitung sebagai skor 0).")
    if len(skor_aktif) < 10 or len(skor_decoy) < 100:
        peringatan.append(f"Sampel kecil ({len(skor_aktif)} aktif, {len(skor_decoy)} decoy): selang kepercayaan AUC lebar; "
                          f"gunakan ≥ 10 aktif dan ≥ 100 decoy untuk kesimpulan yang dapat dipertanggungjawabkan.")

    log("Menghitung metrik ROC, BEDROC, EF1%, dan logAUC...")
    # Skor negatif = decoy, skor positif = aktif. Untuk ΔG docking: semakin rendah/negatif = semakin aktif.
    roc_res = uji.roc(negatif=skor_decoy, positif=skor_aktif, rendah_positif=True)

    return HasilEnrichment(
        n_aktif=len(skor_aktif),
        n_decoy=len(skor_decoy),
        auc=round(float(roc_res.get("auc", 0.5)), 3),
        auc_ci=(round(roc_res["ci"][0], 3), round(roc_res["ci"][1], 3)) if roc_res.get("ci") else None,
        bedroc=round(float(roc_res.get("bedroc", 0.0)), 3),
        ef1=round(float(roc_res.get("ef", {}).get(1, 0.0)), 2),
        ef5=round(float(roc_res.get("ef", {}).get(5, 0.0)), 2),
        logauc=round(float(roc_res.get("logauc", 0.0)), 1),
        p_nilai=float(roc_res.get("p", 1.0)),
        potong_youden=round(float(roc_res.get("potong", 0.0)), 2),
        sensitivitas=round(float(roc_res.get("sens", 0.0) * 100.0), 1),
        spesifisitas=round(float(roc_res.get("spes", 0.0) * 100.0), 1),
        kurva_roc=roc_res,
        skor_aktif=skor_aktif,
        skor_decoy=skor_decoy,
        n_gagal_aktif=n_gagal_a,
        n_gagal_decoy=n_gagal_d,
        peringatan=peringatan,
    )


def periksa_posebusters_kelompok(
    daftar_pose: List[Tuple[Any, Path]],
) -> HasilPoseBusters:
    """Periksa validitas geometri dan antarmolekul pose docking dengan PoseBusters."""
    if not qc.tersedia():
        return HasilPoseBusters(
            tersedia=False,
            total_pose=len(daftar_pose),
            lulus_valid=0,
            persen_valid=0.0,
            rincian_gagal={"PoseBusters tidak terpasang": len(daftar_pose)},
        )

    lulus = 0
    dinilai = 0
    gagal_counts: Dict[str, int] = {}
    for mol, path_prot in daftar_pose:
        if mol is None:
            continue
        dinilai += 1
        res = qc.periksa(mol, str(path_prot))
        if res.get("lulus"):
            lulus += 1
        else:
            for g in res.get("gagal", []):
                gagal_counts[g] = gagal_counts.get(g, 0) + 1

    persen = round((lulus / max(1, dinilai)) * 100.0, 1)

    return HasilPoseBusters(
        tersedia=True,
        total_pose=dinilai,
        lulus_valid=lulus,
        persen_valid=persen,
        rincian_gagal=gagal_counts,
    )


# ------------------------------------------------------------------ Visualisasi SVG
def svg_matriks_cross_docking(labels: List[str], matriks: List[List[float]], gelap: bool = False) -> str:
    """Hasilkan SVG peta panas (heatmap) matriks RMSD cross-docking."""
    n = len(labels)
    if n == 0:
        return ""

    cell_size = 54
    margin_l = 80
    margin_t = 60
    margin_r = 30
    margin_b = 30
    w = margin_l + n * cell_size + margin_r
    h = margin_t + n * cell_size + margin_b

    warna_teks = "#e0e8f5" if gelap else "#1f2937"
    warna_bg = "#0f172a" if gelap else "#ffffff"

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'style="background:{warna_bg};font-family:system-ui,sans-serif;">',
        f'<text x="{w // 2}" y="24" text-anchor="middle" font-size="14" font-weight="bold" fill="{warna_teks}">'
        f'Matriks RMSD Cross-Docking (Å)</text>',
    ]

    # Label kolom (atas)
    for j, lab in enumerate(labels):
        x = margin_l + j * cell_size + cell_size // 2
        svg.append(f'<text x="{x}" y="{margin_t - 8}" text-anchor="middle" font-size="11" fill="{warna_teks}">{html.escape(str(lab))}</text>')

    # Label baris (kiri) & kotak heatmap
    for i, lab in enumerate(labels):
        y = margin_t + i * cell_size + cell_size // 2
        svg.append(f'<text x="{margin_l - 10}" y="{y + 4}" text-anchor="end" font-size="11" fill="{warna_teks}">{html.escape(str(lab))}</text>')

        for j in range(n):
            val = matriks[i][j]
            # Warna: hijau (≤ 2.0 Å), kuning (2.0 - 3.0 Å), merah (> 3.0 Å), abu-abu = tidak dapat dihitung
            if val is None:
                fill, text_color = "#94a3b8", "#ffffff"
            elif val <= 2.0:
                fill = "#10b981"  # Emerald
                text_color = "#ffffff"
            elif val <= 3.0:
                fill = "#f59e0b"  # Amber
                text_color = "#000000"
            else:
                fill = "#ef4444"  # Red
                text_color = "#ffffff"

            x_box = margin_l + j * cell_size
            y_box = margin_t + i * cell_size
            svg.append(
                f'<rect x="{x_box + 2}" y="{y_box + 2}" width="{cell_size - 4}" height="{cell_size - 4}" '
                f'rx="4" fill="{fill}" opacity="0.9"/>'
            )
            teks_sel = "gagal" if val is None else f"{val:.2f}".replace(".", ",")
            svg.append(
                f'<text x="{x_box + cell_size // 2}" y="{y_box + cell_size // 2 + 4}" text-anchor="middle" '
                f'font-size="12" font-weight="bold" fill="{text_color}">{teks_sel}</text>'
            )

    svg.append('</svg>')
    return "\n".join(svg)


def _pecah(x: Any, d: int = 2, id_: bool = True) -> str:
    """Angka -> teks; koma desimal untuk Bahasa Indonesia."""
    t = f"{float(x):.{d}f}".replace("-", "−")
    return t.replace(".", ",") if id_ else t


def _p_teks(p: Optional[float], id_: bool = True) -> str:
    if p is None:
        return ""
    if p < 1e-4:
        return "p < 0,0001" if id_ else "p < 0.0001"
    return ("p = " + _pecah(p, 4, id_))


def susun_paragraf_metode(ringkasan: Dict[str, Any], bahasa: str = "id") -> str:
    """Paragraf metode yang HANYA memuat uji yang benar-benar dijalankan, dengan angka dari hasilnya.

    Bagian yang kosong ({} atau tidak ada) dilewati; tidak ada angka bawaan.
    """
    redock = ringkasan.get("redocking") or {}
    enrich = ringkasan.get("enrichment") or {}
    pb = ringkasan.get("posebusters") or {}
    cross = ringkasan.get("cross_docking") or {}
    ada_redock = "rmsd" in redock
    ada_cross = bool(cross.get("tersedia"))
    ada_enrich = "auc" in enrich
    ada_pb = bool(pb.get("tersedia")) and pb.get("total_pose", 0) > 0
    if not (ada_redock or ada_cross or ada_enrich or ada_pb):
        return ""
    ind = bahasa == "id"
    f = lambda x, d=2: _pecah(x, d, ind)  # noqa: E731

    daftar = []
    if ada_redock:
        daftar.append("redocking ligan ko-kristal" if ind else "redocking of the co-crystallized ligand")
    if ada_cross:
        daftar.append("cross-docking antar-struktur" if ind else "cross-docking between structures")
    if ada_enrich:
        daftar.append("analisis pengayaan aktif terhadap decoy" if ind else "active-versus-decoy enrichment analysis")
    if ada_pb:
        daftar.append("pemeriksaan validitas fisik pose" if ind else "pose physical-validity checks")
    p = []
    if ind:
        p.append("Protokol penambatan molekuler divalidasi melalui " + ", ".join(daftar[:-1])
                 + (" dan " if len(daftar) > 1 else "") + daftar[-1] + ".")
    else:
        p.append("The docking protocol was validated by " + ", ".join(daftar[:-1])
                 + (" and " if len(daftar) > 1 else "") + daftar[-1] + ".")

    if ada_redock:
        ok = bool(redock.get("sukses"))
        mesin_ = redock.get("mesin") or "AutoDock Vina"
        lig, res = redock.get("ligan") or ("ligan kristal" if ind else "the crystal ligand"), redock.get("reseptor") or ""
        en = f" dan energi pengikatan {f(redock['energi'], 1)} kcal/mol" if redock.get("energi") is not None else ""
        en_e = f" and a predicted binding energy of {f(redock['energi'], 1, )} kcal/mol" if redock.get("energi") is not None else ""
        if ind:
            p.append(f"Ligan kristal {lig}{' pada ' + res if res else ''} di-docking ulang dengan {mesin_}; pose terbaik "
                     f"{'mereproduksi' if ok else 'tidak mereproduksi'} konformasi eksperimen dengan RMSD simetri "
                     f"{f(redock['rmsd'])} Å{en} (kriteria RMSD ≤ 2,0 Å).")
        else:
            p.append(f"The crystal ligand {lig}{' in ' + res if res else ''} was redocked with {mesin_}; the top pose "
                     f"{'reproduced' if ok else 'did not reproduce'} the experimental binding mode with a symmetry-corrected "
                     f"RMSD of {f(redock['rmsd'])} Å{en_e} (success criterion RMSD ≤ 2.0 Å).")
    if ada_cross:
        n = len(cross.get("label_struktur", []))
        mat = [v for baris in cross.get("matriks_rmsd", []) for v in baris if v is not None]
        tot = n * n
        ok = sum(1 for v in mat if v <= 2.0)
        if ind:
            p.append(f"Cross-docking antar {n} struktur (superposisi Cα) menghasilkan {ok} dari {len(mat)} pasangan terhitung "
                     f"dengan RMSD ≤ 2,0 Å" + (f"; {tot - len(mat)} pasangan tidak dapat dihitung." if tot > len(mat) else "."))
        else:
            p.append(f"Cross-docking among {n} structures (Cα superposition) gave {ok} of {len(mat)} evaluable pairs with "
                     f"RMSD ≤ 2.0 Å" + (f"; {tot - len(mat)} pairs could not be evaluated." if tot > len(mat) else "."))
    if ada_enrich:
        ptxt = _p_teks(enrich.get("p_nilai"), ind)
        gagal = enrich.get("n_gagal_aktif", 0) + enrich.get("n_gagal_decoy", 0)
        if ind:
            p.append(
                f"Kemampuan memisahkan senyawa aktif dari decoy dinilai dengan {enrich.get('n_aktif', 0)} senyawa aktif "
                f"(ChEMBL, pChEMBL ≥ 7,0, kerangka beragam) dan {enrich.get('n_decoy', 0)} decoy bergaya DUD-E yang dipilih acak "
                f"dari obat disetujui dan produk alam (MW ± 25 Da, logP ± 0,5, HBD ± 1, HBA ± 1, ikatan rotasi ± 1, "
                f"muatan bersih sama, Tanimoto ECFP4 < 0,3 terhadap semua aktif). Luas area di bawah kurva ROC (AUC) "
                f"adalah {f(enrich['auc'], 3)}{' (' + ptxt + ', Mann–Whitney)' if ptxt else ''}, BEDROC (α = 20) "
                f"{f(enrich.get('bedroc', 0.0), 3)}, EF 1% {f(enrich.get('ef1', 0.0), 1)}, dan logAUC "
                f"{f(enrich.get('logauc', 0.0), 1)}%."
                + (f" Sebanyak {gagal} senyawa yang gagal di-docking dikeluarkan dari analisis." if gagal else "")
                + " Decoy tidak berasal dari ZINC seperti DUD-E, sehingga nilai ini merupakan perkiraan atas pengayaan.")
        else:
            p.append(
                f"Screening power was assessed with {enrich.get('n_aktif', 0)} scaffold-diverse actives (ChEMBL, "
                f"pChEMBL ≥ 7.0) and {enrich.get('n_decoy', 0)} DUD-E-style decoys drawn at random from approved drugs and "
                f"natural products (MW ± 25 Da, logP ± 0.5, HBD ± 1, HBA ± 1, rotatable bonds ± 1, identical net charge, "
                f"ECFP4 Tanimoto < 0.3 to all actives). The area under the ROC curve (AUC) was {f(enrich['auc'], 3)}"
                f"{' (' + ptxt + ', Mann–Whitney)' if ptxt else ''}, BEDROC (α = 20) {f(enrich.get('bedroc', 0.0), 3)}, "
                f"EF 1% {f(enrich.get('ef1', 0.0), 1)}, and logAUC {f(enrich.get('logauc', 0.0), 1)}%."
                + (f" {gagal} {'compound that' if gagal == 1 else 'compounds that'} failed to dock {'was' if gagal == 1 else 'were'} excluded." if gagal else "")
                + " Because decoys were not sourced from ZINC as in DUD-E, these values are an upper estimate of enrichment.")
    if ada_pb:
        if ind:
            p.append(f"Pemeriksaan PoseBusters terhadap {pb.get('total_pose', 0)} pose menunjukkan {f(pb.get('persen_valid', 0.0), 1)}% "
                     f"lolos seluruh uji geometri dan sterik.")
        else:
            p.append(f"PoseBusters checks on {pb.get('total_pose', 0)} poses showed {f(pb.get('persen_valid', 0.0), 1)}% "
                     f"passing all geometric and steric tests.")
    return " ".join(p)


def buat_halaman_laporan_html(ringkasan: Dict[str, Any], judul: str = "Paket Validasi Protokol Docking") -> str:
    """Satu halaman ringkasan HTML luring. Hanya bagian yang dijalankan yang ditampilkan; tanpa angka bawaan."""
    redock = ringkasan.get("redocking") or {}
    enrich = ringkasan.get("enrichment") or {}
    pb = ringkasan.get("posebusters") or {}
    cross = ringkasan.get("cross_docking") or {}
    decoy_info = ringkasan.get("decoy") or {}
    paragraf = susun_paragraf_metode(ringkasan, bahasa="id")
    ada_redock, ada_enrich = "rmsd" in redock, "auc" in enrich
    ada_pb = bool(pb.get("tersedia")) and pb.get("total_pose", 0) > 0
    e = html.escape

    svg_roc = svg_enrich = ""
    if enrich.get("kurva_roc"):
        try:
            svg_roc, _ = grafik_uji.grafik_roc(enrich["kurva_roc"], judul="Kurva ROC Validasi", mode="roc")
            svg_enrich, _ = grafik_uji.grafik_roc(enrich["kurva_roc"], judul="Kurva Pengayaan (Enrichment)", mode="enrich")
        except Exception as err:
            catat.log.debug(f"Gagal generate SVG ROC: {err}")
    svg_cross = ""
    if cross.get("tersedia"):
        svg_cross = svg_matriks_cross_docking(cross["label_struktur"], cross["matriks_rmsd"])

    kartu = []
    if ada_redock:
        ok = bool(redock.get("sukses"))
        kartu.append(("ok" if ok else "bad", "Redocking RMSD", f"{_pecah(redock['rmsd'])} Å",
                      "✓ Lolos (≤ 2,0 Å)" if ok else "✗ Melebihi ambang"))
    if ada_enrich:
        auc = enrich["auc"]
        kartu.append(("ok" if auc >= 0.7 else "warn", "ROC-AUC", _pecah(auc, 3),
                      "Cukup/baik (≥ 0,7)" if auc >= 0.7 else "Di bawah 0,7"))
        kartu.append(("", "BEDROC (α=20)", _pecah(enrich.get("bedroc", 0.0), 3), "Pengayaan dini"))
        kartu.append(("", "EF 1%", f"{_pecah(enrich.get('ef1', 0.0), 1)}×", "Faktor pengayaan 1% teratas"))
    if ada_pb:
        kartu.append(("ok" if pb.get("persen_valid", 0) >= 70 else "warn", "PoseBusters valid",
                      f"{_pecah(pb.get('persen_valid', 0.0), 1)}%", f"{pb.get('lulus_valid', 0)}/{pb.get('total_pose', 0)} pose"))
    html_kartu = "".join(
        f'<div class="kartu {k}"><div class="label">{e(l)}</div><div class="nilai">{e(v)}</div>'
        f'<div class="status">{e(st)}</div></div>' for k, l, v, st in kartu)

    peringatan = list(enrich.get("peringatan") or []) + list(decoy_info.get("peringatan") or []) \
        + list(cross.get("catatan") or [])
    html_peringatan = ("<h2>Catatan dan keterbatasan</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in peringatan) + "</ul>"
                       if peringatan else "")

    tabel_enrich = ""
    if ada_enrich:
        tabel_enrich = f"""
  <h2>Hasil penapisan aktif vs decoy</h2>
  <table>
    <tr><th>Parameter</th><th>Nilai</th><th>Keterangan</th></tr>
    <tr><td>Aktif / decoy dinilai</td><td>{enrich.get('n_aktif', 0)} / {enrich.get('n_decoy', 0)}</td><td>pChEMBL ≥ 7,0; decoy bergaya DUD-E (bukan dari ZINC)</td></tr>
    <tr><td>Gagal di-docking (dikeluarkan)</td><td>{enrich.get('n_gagal_aktif', 0)} / {enrich.get('n_gagal_decoy', 0)}</td><td>Tidak dihitung sebagai skor 0</td></tr>
    <tr><td>ROC AUC</td><td>{_pecah(enrich['auc'], 3)}</td><td>0,5 = acak; &gt; 0,7 cukup; &gt; 0,8 baik</td></tr>
    <tr><td>BEDROC (α=20)</td><td>{_pecah(enrich.get('bedroc', 0.0), 3)}</td><td>Menekankan aktif di peringkat awal</td></tr>
    <tr><td>EF 1%</td><td>{_pecah(enrich.get('ef1', 0.0), 2)}</td><td>Kelipatan aktif dalam 1% teratas dibanding acak</td></tr>
    <tr><td>logAUC</td><td>{_pecah(enrich.get('logauc', 0.0), 1)}%</td><td>Acuan tebakan acak ≈ 14,5%</td></tr>
    <tr><td>Titik potong Youden</td><td>{_pecah(enrich.get('potong_youden', 0.0), 2)} kcal/mol</td><td>Sensitivitas {enrich.get('sensitivitas', 0.0)}%, spesifisitas {enrich.get('spesifisitas', 0.0)}%</td></tr>
  </table>
  <h2>Figur</h2>
  <div class="fig-wrap"><div class="fig-box">{svg_roc}</div><div class="fig-box">{svg_enrich}</div></div>"""
    bagian_cross = f"<h2>Matriks cross-docking (RMSD Å)</h2><div class='fig-box'>{svg_cross}</div>" if svg_cross else ""
    isi_paragraf = (f"<h2>Paragraf metode</h2><div class='metode-box'>{e(paragraf)}</div>" if paragraf
                    else "<p>Belum ada uji yang dijalankan.</p>")

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<title>{e(judul)} · VirmoLab</title>
<style>
  body {{ font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 24px; color: #1e293b; background: #f8fafc; line-height: 1.5; }}
  .container {{ max-width: 960px; margin: 0 auto; background: #ffffff; padding: 32px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 20px; }}
  h2 {{ font-size: 18px; margin-top: 28px; margin-bottom: 12px; color: #0f172a; border-left: 4px solid #0284c7; padding-left: 8px; }}
  .grid-kartu {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .kartu {{ background: #f1f5f9; padding: 14px; border-radius: 6px; border-left: 4px solid #94a3b8; }}
  .kartu.ok {{ border-left-color: #10b981; }} .kartu.warn {{ border-left-color: #f59e0b; }} .kartu.bad {{ border-left-color: #ef4444; }}
  .kartu .label {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; }}
  .kartu .nilai {{ font-size: 22px; font-weight: 700; margin: 4px 0; color: #0f172a; }}
  .kartu .status {{ font-size: 12px; color: #475569; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }}
  th, td {{ padding: 8px 12px; border: 1px solid #cbd5e1; text-align: left; }}
  th {{ background: #f8fafc; font-weight: 600; }}
  .metode-box {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 6px; font-size: 13.5px; text-align: justify; }}
  .fig-wrap {{ display: flex; flex-wrap: wrap; gap: 16px; margin-top: 16px; }}
  .fig-box {{ flex: 1; min-width: 380px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; }}
</style>
</head>
<body>
<div class="container">
  <h1>{e(judul)}</h1>
  <div class="grid-kartu">{html_kartu}</div>
  {isi_paragraf}
  {tabel_enrich}
  {bagian_cross}
  {html_peringatan}
</div>
</body>
</html>"""
