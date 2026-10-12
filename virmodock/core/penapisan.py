"""Batch Virtual Screening: filter, peringkat multi-kriteria, auto-flag top hits, dan ringkasan data."""
from typing import Any, Dict, List, Optional, Tuple
import math
from . import ekspor
from . import mpo
from . import sifat as sifat_mod


def gabung_data(proyek, jobs=None) -> List[Dict[str, Any]]:
    """Gabungkan data docking, sifat fisikokimia, dan MPO ke dalam satu list dict flat per ligan.

    Setiap dict mencakup:
      - nama, lid, job, mesin
      - energi (ΔG), ki, le, mmgbsa
      - hbond, hidrofobik, pi, interaksi_total
      - mw, wlogp, tpsa, qed, sascore, rotb, hbd, hba
      - lipinski_lolos, veber_lolos, pains, brenk, gi, bbb
      - mpo_skor, mpo_kategori
      - smiles
    """
    if not proyek:
        return []

    # Kumpulkan baris hasil docking (pose terbaik per ligan)
    baris_docking = ekspor.baris_hasil(proyek, jobs=jobs)
    if not baris_docking:
        return []

    hasil = []
    for b in baris_docking:
        lid = b.get("lid")
        lig = proyek.cari_ligan(lid) if lid else None
        s = (lig.get("sifat") if lig else None) or {}

        # Bila sifat belum ada di lig tapi ada SMILES / berkas, coba hitung jika mungkin
        if not s and lig:
            try:
                teks = lig.get("mol") or lig.get("pdbqt") or lig.get("smiles") or ""
                fmt = "smiles" if lig.get("smiles") else ("pdbqt" if lig.get("pdbqt") else "sdf")
                if teks:
                    s = sifat_mod.dari_teks(teks, fmt)
                    if isinstance(s, dict):
                        lig["sifat"] = s
            except Exception:
                s = {}

        if not isinstance(s, dict):
            s = {}

        dg = b.get("energi")
        le = b.get("le")
        mmgbsa = b.get("mmgbsa")

        # Hitung skor MPO
        mpo_res = mpo.hitung_mpo(s, dg=dg, preset="oral")

        # Interaksi
        hb = int(b.get("hbond") or 0)
        hf = int(b.get("hidrofobik") or 0)
        pi = int(b.get("pi") or 0)
        pik = int(b.get("pikation") or 0)
        garam = int(b.get("garam") or 0)
        hal = int(b.get("halogen") or 0)
        logam = int(b.get("logam") or 0)
        tot_inter = hb + hf + pi + pik + garam + hal + logam

        # Aturan kelayakan
        lip_pelanggaran = s.get("lipinski")
        lipinski_lolos = (lip_pelanggaran is not None and int(lip_pelanggaran) <= 1)
        veber_lolos = bool(s.get("veber", True))
        pains_ada = bool(s.get("pains"))
        brenk_ada = bool(s.get("brenk"))
        gi_tinggi = bool(s.get("gi", True))
        bbb_lolos = bool(s.get("bbb", False))

        item = {
            "nama": b.get("ligan") or (lig.get("nama") if lig else "Ligan"),
            "lid": lid,
            "job": b.get("job"),
            "mesin": b.get("mesin"),
            "energi": dg,
            "ki": b.get("ki", ""),
            "le": le,
            "mmgbsa": mmgbsa,
            "hbond": hb,
            "hidrofobik": hf,
            "pi": pi,
            "interaksi_total": tot_inter,
            "mw": s.get("mw"),
            "wlogp": s.get("wlogp"),
            "tpsa": s.get("tpsa"),
            "qed": s.get("qed"),
            "sascore": s.get("sascore"),
            "rotb": s.get("rotb"),
            "hbd": s.get("hbd"),
            "hba": s.get("hba"),
            "lipinski_lolos": lipinski_lolos,
            "lipinski_pelanggaran": lip_pelanggaran,
            "veber_lolos": veber_lolos,
            "pains": pains_ada,
            "brenk": brenk_ada,
            "gi": gi_tinggi,
            "bbb": bbb_lolos,
            "mpo_skor": mpo_res.get("skor", 50.0),
            "mpo_kategori": mpo_res.get("kategori", "Cukup"),
            "smiles": b.get("smiles") or (lig.get("smiles") if lig else ""),
        }
        hasil.append(item)

    return hasil


def filter_data(data: List[Dict[str, Any]], kriteria: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filter ligan berdasar dict kriteria multi-parameter.

    Contoh kriteria:
      - energi_maks: float (misal -6.5 -> ΔG <= -6.5)
      - qed_min: float (misal 0.5)
      - sascore_maks: float (misal 5.0)
      - mw_min, mw_maks: float
      - wlogp_min, wlogp_maks: float
      - tpsa_min, tpsa_maks: float
      - lipinski_lolos: bool
      - veber_lolos: bool
      - pains_bebas: bool (bila True, ligan ber-PAINS disaring keluar)
      - brenk_bebas: bool (bila True, ligan ber-Brenk disaring keluar)
      - gi_harus: bool
      - mpo_min: float
    """
    if not data:
        return []

    hasil = []
    for d in data:
        # Filter energi (makin negatif makin baik)
        if "energi_maks" in kriteria and kriteria["energi_maks"] is not None:
            if d.get("energi") is None or d["energi"] > float(kriteria["energi_maks"]):
                continue

        # Filter QED
        if "qed_min" in kriteria and kriteria["qed_min"] is not None:
            if d.get("qed") is None or d["qed"] < float(kriteria["qed_min"]):
                continue

        # Filter SAScore (makin kecil makin mudah)
        if "sascore_maks" in kriteria and kriteria["sascore_maks"] is not None:
            if d.get("sascore") is None or d["sascore"] > float(kriteria["sascore_maks"]):
                continue

        # Filter MW
        if "mw_min" in kriteria and kriteria["mw_min"] is not None:
            if d.get("mw") is None or d["mw"] < float(kriteria["mw_min"]):
                continue
        if "mw_maks" in kriteria and kriteria["mw_maks"] is not None:
            if d.get("mw") is None or d["mw"] > float(kriteria["mw_maks"]):
                continue

        # Filter WLOGP
        if "wlogp_min" in kriteria and kriteria["wlogp_min"] is not None:
            if d.get("wlogp") is None or d["wlogp"] < float(kriteria["wlogp_min"]):
                continue
        if "wlogp_maks" in kriteria and kriteria["wlogp_maks"] is not None:
            if d.get("wlogp") is None or d["wlogp"] > float(kriteria["wlogp_maks"]):
                continue

        # Filter TPSA
        if "tpsa_min" in kriteria and kriteria["tpsa_min"] is not None:
            if d.get("tpsa") is None or d["tpsa"] < float(kriteria["tpsa_min"]):
                continue
        if "tpsa_maks" in kriteria and kriteria["tpsa_maks"] is not None:
            if d.get("tpsa") is None or d["tpsa"] > float(kriteria["tpsa_maks"]):
                continue

        # Filter MPO
        if "mpo_min" in kriteria and kriteria["mpo_min"] is not None:
            if d.get("mpo_skor") is None or d["mpo_skor"] < float(kriteria["mpo_min"]):
                continue

        # Filter aturan kualitatif
        if kriteria.get("lipinski_lolos") and not d.get("lipinski_lolos"):
            continue
        if kriteria.get("veber_lolos") and not d.get("veber_lolos"):
            continue
        if kriteria.get("pains_bebas") and d.get("pains"):
            continue
        if kriteria.get("brenk_bebas") and d.get("brenk"):
            continue
        if kriteria.get("gi_harus") and not d.get("gi"):
            continue

        hasil.append(d)

    return hasil


def flag_top_hits(data: List[Dict[str, Any]], n: int = 20,
                  bobot: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """Hitung skor komposit multi-kriteria dan beri flag 'flag_top' pada N ligan terbaik.

    Bobot default:
      - energi (ΔG): 0.40 (makin negatif makin baik)
      - mpo: 0.30 (skor 0-100)
      - le: 0.15 (makin negatif makin baik)
      - interaksi: 0.15 (jumlah interaksi non-kovalen)
    """
    if not data:
        return []

    b = bobot or {"energi": 0.40, "mpo": 0.30, "le": 0.15, "interaksi": 0.15}
    w_dg = b.get("energi", 0.4)
    w_mpo = b.get("mpo", 0.3)
    w_le = b.get("le", 0.15)
    w_int = b.get("interaksi", 0.15)

    # Cari rentang nilai untuk normalisasi min-max
    dgs = [d["energi"] for d in data if d.get("energi") is not None]
    les = [d["le"] for d in data if d.get("le") is not None]
    mpos = [d["mpo_skor"] for d in data if d.get("mpo_skor") is not None]
    ints = [d["interaksi_total"] for d in data if d.get("interaksi_total") is not None]

    min_dg, max_dg = (min(dgs), max(dgs)) if dgs else (-10.0, -4.0)
    range_dg = (max_dg - min_dg) if (max_dg - min_dg) > 1e-9 else 1.0

    min_le, max_le = (min(les), max(les)) if les else (-0.6, -0.1)
    range_le = (max_le - min_le) if (max_le - min_le) > 1e-9 else 1.0

    min_int, max_int = (min(ints), max(ints)) if ints else (0, 10)
    range_int = (max_int - min_int) if (max_int - min_int) > 1e-9 else 1.0

    hasil = []
    for d in data:
        item = dict(d)
        # Normalisasi ke [0.0, 1.0], makin baik makin mendekati 1.0
        # ΔG makin negatif makin baik -> (max_dg - val) / range_dg
        val_dg = d.get("energi")
        norm_dg = ((max_dg - val_dg) / range_dg) if val_dg is not None else 0.5

        # MPO (0-100) -> mpo / 100.0
        val_mpo = d.get("mpo_skor")
        norm_mpo = (val_mpo / 100.0) if val_mpo is not None else 0.5

        # LE makin negatif makin baik
        val_le = d.get("le")
        norm_le = ((max_le - val_le) / range_le) if val_le is not None else 0.5

        # Interaksi makin banyak makin baik
        val_int = d.get("interaksi_total", 0)
        norm_int = ((val_int - min_int) / range_int) if val_int is not None else 0.5

        skor_komposit = (norm_dg * w_dg + norm_mpo * w_mpo + norm_le * w_le + norm_int * w_int)
        item["skor_komposit"] = round(skor_komposit * 100.0, 2)
        hasil.append(item)

    # Urutkan berdasarkan skor_komposit terbesar
    hasil.sort(key=lambda x: x.get("skor_komposit", 0.0), reverse=True)

    # Tandai top N
    for i, it in enumerate(hasil):
        it["flag_top"] = (i < n)

    return hasil


def statistik_ringkas(data: List[Dict[str, Any]], terfilter: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Kembalikan ringkasan statistik komprehensif penapisan virtual."""
    total = len(data)
    lolos = len(terfilter) if terfilter is not None else total
    persen = (lolos / total * 100.0) if total > 0 else 0.0

    populasi = terfilter if terfilter is not None else data
    dgs = [d["energi"] for d in populasi if d.get("energi") is not None]
    mpos = [d["mpo_skor"] for d in populasi if d.get("mpo_skor") is not None]
    qeds = [d["qed"] for d in populasi if d.get("qed") is not None]

    rerata_dg = sum(dgs) / len(dgs) if dgs else None
    if dgs:
        s_dgs = sorted(dgs)
        med_dg = s_dgs[len(s_dgs) // 2]
        terbaik_dg = min(dgs)
    else:
        med_dg, terbaik_dg = None, None

    lipinski_n = sum(1 for d in populasi if d.get("lipinski_lolos"))
    veber_n = sum(1 for d in populasi if d.get("veber_lolos"))
    pains_bebas_n = sum(1 for d in populasi if not d.get("pains"))
    brenk_bebas_n = sum(1 for d in populasi if not d.get("brenk"))

    rerata_mpo = sum(mpos) / len(mpos) if mpos else 50.0
    rerata_qed = sum(qeds) / len(qeds) if qeds else 0.5

    return {
        "total_ligan": total,
        "jumlah_lolos": lolos,
        "persentase_lolos": round(persen, 1),
        "rata_rata_energi": round(rerata_dg, 2) if rerata_dg is not None else None,
        "median_energi": round(med_dg, 2) if med_dg is not None else None,
        "energi_terbaik": round(terbaik_dg, 2) if terbaik_dg is not None else None,
        "lipinski_lolos": lipinski_n,
        "veber_lolos": veber_n,
        "pains_bebas": pains_bebas_n,
        "brenk_bebas": brenk_bebas_n,
        "rata_rata_mpo": round(rerata_mpo, 1),
        "rata_rata_qed": round(rerata_qed, 3),
    }


def matriks_heatmap(data: List[Dict[str, Any]], kolom_variabel: Optional[List[Tuple[str, str]]] = None,
                    maks_baris: int = 50) -> Tuple[List[List[float]], List[str], List[str]]:
    """Buat matriks numerik N x M untuk visualisasi heatmap penapisan virtual.

    Kembalikan: (matriks, label_baris, label_kolom)
    """
    if not data:
        return [], [], []

    # Kolom standar penapisan
    cols = kolom_variabel or [
        ("energi", "ΔG"),
        ("le", "LE"),
        ("qed", "QED"),
        ("sascore", "SAScore"),
        ("mpo_skor", "MPO"),
        ("interaksi_total", "Interaksi"),
    ]

    label_kolom = [lbl for _, lbl in cols]
    cuplikan = data[:maks_baris]
    label_baris = [d.get("nama", f"Ligan {i+1}") for i, d in enumerate(cuplikan)]

    matriks = []
    for d in cuplikan:
        baris = []
        for k, _ in cols:
            val = d.get(k)
            try:
                baris.append(float(val) if val is not None else 0.0)
            except (ValueError, TypeError):
                baris.append(0.0)
        matriks.append(baris)

    return matriks, label_baris, label_kolom
