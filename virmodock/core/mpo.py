"""Multi-Parameter Optimization (MPO) & Desirability Score.

Mengintegrasikan berbagai parameter fisikokimia, drug-likeness, kemudahan sintesis,
dan afinitas docking menjadi satu skor terpadu (0 - 100).

Mendukung preset:
1. 'oral': Oral Drug-Like MPO (Lipinski, Veber, SAScore, QED, afinitas ΔG).
2. 'cns': CNS-MPO parsial (4 dari 6 suku Wager et al. 2010; ClogD dan pKa tidak dihitung).
3. 'kustom': Bobot dan rentang dapat diatur bebas oleh pengguna.
"""
from typing import Any, Dict, Optional


def _turun(x: float, batas_bawah: float, batas_atas: float) -> float:
    """Makin kecil makin baik: <= batas_bawah -> 1.0, >= batas_atas -> 0.0."""
    if x <= batas_bawah:
        return 1.0
    if x >= batas_atas:
        return 0.0
    return (batas_atas - x) / (batas_atas - batas_bawah)


def _naik(x: float, batas_bawah: float, batas_atas: float) -> float:
    """Makin besar makin baik: >= batas_atas -> 1.0, <= batas_bawah -> 0.0."""
    if x >= batas_atas:
        return 1.0
    if x <= batas_bawah:
        return 0.0
    return (x - batas_bawah) / (batas_atas - batas_bawah)


def _rentang(x: float, min_terima: float, opt_bawah: float, opt_atas: float, maks_terima: float) -> float:
    """Trapezoid: 1.0 di rentang optimal [opt_bawah, opt_atas], menurun ke tepi."""
    if opt_bawah <= x <= opt_atas:
        return 1.0
    if x < opt_bawah:
        if x <= min_terima:
            return 0.0
        return (x - min_terima) / (opt_bawah - min_terima)
    else:
        if x >= maks_terima:
            return 0.0
        return (maks_terima - x) / (maks_terima - opt_atas)


# Konfigurasi preset bawaan:
# Setiap item: (kunci, label, fungsi_hitung_desirability(val, dg), bobot_bawaan)
PRESET_ORAL = [
    ("dg", "Afinitas (ΔG)", lambda v, dg: _naik(-dg, 5.0, 9.0) if dg is not None else 0.5, 1.5),
    ("mw", "Massa (MW)", lambda v, dg: _rentang(v["mw"], 150, 200, 450, 550) if v.get("mw") else 0.5, 1.0),
    ("wlogp", "Lipofilisitas (WLOGP)", lambda v, dg: _rentang(v["wlogp"], -1.0, 0.5, 3.5, 5.0) if v.get("wlogp") is not None else 0.5, 1.0),
    ("tpsa", "Polaritas (TPSA)", lambda v, dg: _rentang(v["tpsa"], 20, 40, 120, 140) if v.get("tpsa") is not None else 0.5, 1.0),
    ("sascore", "Kemudahan Sintesis (SA)", lambda v, dg: _turun(v["sascore"], 2.5, 6.0) if v.get("sascore") is not None else 0.5, 1.2),
    ("qed", "Kemiripan Obat (QED)", lambda v, dg: _naik(v["qed"], 0.3, 0.75) if v.get("qed") is not None else 0.5, 1.0),
    ("rotb", "Fleksibilitas (RotB)", lambda v, dg: _turun(v["rotb"], 5, 10) if v.get("rotb") is not None else 0.5, 0.8),
]

# CNS-MPO Pfizer (Wager et al., ACS Chem Neurosci 2010; ditinjau ulang 2016) memakai enam suku:
# MW, ClogP, ClogD(7,4), TPSA, HBD, dan pKa basa terkuat. VirmoLab hanya menghitung empat di antaranya
# (ClogP didekati dengan WLOGP RDKit); ClogD dan pKa butuh prediktor berbayar sehingga tidak disertakan.
# Jadi skor di sini adalah CNS-MPO parsial — jangan dilaporkan sebagai nilai CNS-MPO 0–6 Pfizer.
PRESET_CNS = [
    ("mw", "Massa (MW ≤ 360)", lambda v, dg: _turun(v["mw"], 360, 500) if v.get("mw") else 0.5, 1.0),
    ("wlogp", "Lipofilisitas (WLOGP ≤ 3)",
     lambda v, dg: _turun(v["wlogp"], 3.0, 5.0) if v.get("wlogp") is not None else 0.5, 1.0),
    ("tpsa", "Polaritas (TPSA 40–90)",
     lambda v, dg: _rentang(v["tpsa"], 20, 40, 90, 120) if v.get("tpsa") is not None else 0.5, 1.0),
    ("hbd", "Donor H (≤ 1)", lambda v, dg: _turun(v["hbd"], 0.5, 3.5) if v.get("hbd") is not None else 0.5, 1.0),
]


def hitung_mpo(sifat: Dict[str, Any], dg: Optional[float] = None, preset: str = "oral",
               bobot_kustom: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Hitung skor MPO (0.0 - 100.0) untuk satu ligan.

    Kembalikan dict:
      - 'skor': float 0.0 - 100.0 (dibulatkan 1 desimal)
      - 'kategori': 'Sangat Baik' (>= 75), 'Baik' (>= 60), 'Cukup' (>= 40), 'Kurang' (< 40)
      - 'komponen': {kunci: {'label': str, 'nilai': float, 'desirability': float, 'skor': float (0-100), 'bobot': float}}
    """
    if preset == "cns":
        aturan = PRESET_CNS
    else:
        aturan = PRESET_ORAL

    total_bobot = 0.0
    total_skor = 0.0
    komponen = {}

    for kunci, label, fn, bobot_bawaan in aturan:
        bobot = bobot_kustom.get(kunci, bobot_bawaan) if bobot_kustom else bobot_bawaan
        if bobot <= 0:
            continue
        try:
            d = fn(sifat, dg)
            d = max(0.0, min(1.0, float(d)))
        except Exception:
            d = 0.5

        skor_item = round(d * 100.0, 1)
        # Ambil nilai asli untuk ditampilkan di tabel/tooltip
        val_asli = dg if kunci == "dg" else sifat.get(kunci)

        komponen[kunci] = {
            "label": label,
            "nilai": val_asli,
            "desirability": round(d, 3),
            "skor": skor_item,
            "bobot": bobot,
        }
        total_skor += d * bobot
        total_bobot += bobot

    skor_akhir = round((total_skor / total_bobot) * 100.0, 1) if total_bobot > 0 else 50.0

    if skor_akhir >= 75.0:
        kat = "Sangat Baik"
        warna = "ok"
    elif skor_akhir >= 60.0:
        kat = "Baik"
        warna = "ok"
    elif skor_akhir >= 40.0:
        kat = "Cukup"
        warna = "warn"
    else:
        kat = "Kurang"
        warna = "bad"

    return {
        "skor": skor_akhir,
        "kategori": kat,
        "warna": warna,
        "komponen": komponen,
    }


def daftar_preset():
    """Kembalikan daftar preset MPO yang tersedia."""
    return [
        ("oral", "Oral Drug-like MPO (Lipinski, SAScore, QED, ΔG)"),
        ("cns", "CNS-MPO (Pfizer Blood-Brain Penetration)"),
    ]
