"""Sidik jari kontak atom pose (gaya RF-Score) dan skor pembanding sederhana.

Menghitung jumlah pasangan kontak protein–ligan (atom berat, d ≤ 4,0 Å) per kombinasi unsur, seperti deskriptor
RF-Score (Ballester & Mitchell 2010). Dari deskriptor itu dihitung skor pembanding linier dan beberapa ukuran
kualitas kontak (kerapatan kontak per atom berat, pangsa kontak polar) untuk menandai pose yang skor dockingnya
kuat tetapi kontak atomnya tipis.

PENTING: bobot di bawah adalah bobot linier sederhana, bukan model Random Forest terlatih PDBbind. Skornya dipakai
untuk membandingkan pose dalam satu proyek, bukan untuk dilaporkan sebagai afinitas absolut.
"""
import math
from pathlib import Path
from typing import Any, Dict, Optional

CUTOFF = 4.0          # Å, jarak kontak RF-Score
UNSUR = ("C", "N", "O", "S", "HAL")
# bobot linier per akar jumlah kontak (ditala agar pose protein–ligan tipikal jatuh di pKd 4–9; bukan hasil pelatihan)
BOBOT = {("C", "C"): 0.052, ("C", "N"): 0.038, ("C", "O"): 0.041, ("C", "HAL"): 0.065,
         ("N", "C"): 0.035, ("N", "N"): -0.015, ("N", "O"): 0.082, ("N", "HAL"): 0.020,
         ("O", "C"): 0.042, ("O", "N"): 0.088, ("O", "O"): -0.025, ("O", "HAL"): 0.031,
         ("S", "C"): 0.045, ("S", "N"): 0.028, ("S", "O"): 0.034, ("S", "HAL"): 0.050}
INTERSEP = 4.15
POLAR = {("N", "O"), ("O", "N"), ("O", "O"), ("N", "N")}
KT = 1.363            # kcal/mol per satuan pKd pada 298 K (2,303 RT)


def _kelas(simbol: str) -> str:
    s = (simbol or "").strip().upper()
    if s in ("C", "N", "O"):
        return s
    if s in ("S", "P", "SE"):
        return "S"
    if s in ("F", "CL", "BR", "I"):
        return "HAL"
    return ""


def _atom(sumber: str):
    """[(x, y, z, kelas unsur)] atom berat dari teks atau berkas PDB/PDBQT."""
    teks = sumber if "\n" in sumber else (Path(sumber).read_text(encoding="utf-8", errors="replace")
                                          if Path(sumber).exists() else "")
    keluar = []
    for b in teks.splitlines():
        if not b.startswith(("ATOM  ", "HETATM")):
            continue
        try:
            x, y, z = float(b[30:38]), float(b[38:46]), float(b[46:54])
        except ValueError:
            continue
        el = b[76:78].strip() if len(b) >= 78 else ""
        if not el or not el.isalpha():
            el = b[12:16].strip()[:1]
        k = _kelas(el)
        if k:
            keluar.append((x, y, z, k))
    return keluar


def hitung_rescore_ml(jalur_reseptor: str, jalur_pose_ligan: str, energi_vina: Optional[float] = None,
                      cutoff_jarak: float = CUTOFF) -> Dict[str, Any]:
    """Sidik jari kontak + skor pembanding satu pose.

    jalur_reseptor / jalur_pose_ligan: teks atau berkas PDB/PDBQT. energi_vina: ΔG docking untuk dibandingkan.

    Kembalian: pKd, dG_ml, dG_vina, total_kontak, kontak_per_atom, pangsa_polar, matriks_kontak,
    peringatan_false_positive, evaluasi.
    """
    import numpy as np
    rec, lig = _atom(jalur_reseptor), _atom(jalur_pose_ligan)
    if not rec or not lig:
        raise ValueError("Koordinat reseptor atau pose ligan tidak terbaca.")
    xr = np.array([(a[0], a[1], a[2]) for a in rec])
    xl = np.array([(a[0], a[1], a[2]) for a in lig])
    kr = np.array([a[3] for a in rec])
    kl = np.array([a[3] for a in lig])
    # hanya atom reseptor di sekitar ligan yang perlu dihitung
    kotak = (xr >= xl.min(0) - cutoff_jarak).all(1) & (xr <= xl.max(0) + cutoff_jarak).all(1)
    xr, kr = xr[kotak], kr[kotak]
    if not len(xr):
        raise ValueError("Tidak ada atom reseptor di sekitar pose; periksa apakah pose dan reseptor sepadan.")
    d = np.sqrt(((xr[:, None, :] - xl[None, :, :]) ** 2).sum(-1))
    dekat = d <= cutoff_jarak
    matriks, total = {}, int(dekat.sum())
    for a in UNSUR:
        ma = kr == a
        for b in UNSUR:
            n = int(dekat[np.ix_(ma, kl == b)].sum())
            if n:
                matriks[(a, b)] = n
    skor = sum(BOBOT.get(k, 0.0) * math.sqrt(n) for k, n in matriks.items())
    pkd = max(2.0, min(12.0, INTERSEP + skor))
    dg_ml = round(-KT * pkd, 2)
    per_atom = total / max(1, len(lig))
    polar = sum(n for k, n in matriks.items() if k in POLAR)
    pangsa_polar = polar / max(1, total)

    peringatan, catatan = False, []
    if per_atom < 1.5:
        peringatan = True
        catatan.append(f"Kontak sangat tipis ({kontak_teks(per_atom)}): pose kemungkinan menggantung di mulut "
                       "kantong, bukan terkubur di dalamnya.")
    if energi_vina is not None:
        if energi_vina <= -9.0 and per_atom < 2.5:
            peringatan = True
            catatan.append("ΔG docking kuat tetapi kontak atom sedikit — periksa ulang pose sebelum dipakai.")
        elif abs(energi_vina - dg_ml) <= 1.5:
            catatan.append("Skor docking dan skor kontak sejalan (selisih ≤ 1,5 kcal/mol).")
        else:
            from .laporan import id_angka
            catatan.append(f"Selisih skor docking dan skor kontak {id_angka(f'{abs(energi_vina - dg_ml):.1f}')} "
                           "kcal/mol; "
                           "keduanya memakai asumsi berbeda, perbedaan sebesar ini masih lazim.")
    if not catatan:
        catatan.append("Kerapatan kontak wajar untuk kompleks protein–ligan.")
    return {
        "pKd": round(pkd, 2),
        "dG_ml": dg_ml,
        "dG_vina": energi_vina,
        "total_kontak": total,
        "atom_ligan": len(lig),
        "kontak_per_atom": round(per_atom, 2),
        "pangsa_polar": round(pangsa_polar, 3),
        "matriks_kontak": {f"{a}-{b}": n for (a, b), n in sorted(matriks.items(), key=lambda x: -x[1])},
        "peringatan_false_positive": peringatan,
        "evaluasi": " ".join(catatan),
    }


def kontak_teks(per_atom: float) -> str:
    from .laporan import id_angka
    return f"{id_angka(f'{per_atom:.2f}')} kontak per atom berat ligan"
