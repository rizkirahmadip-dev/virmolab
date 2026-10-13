"""Pelacak hipotesis ke uji laboratorium (F12) dan validasi in vitro.

Menghubungkan prediksi in silico (skor ΔG docking, MM/GBSA, pIC50 estimasi dari ΔG)
dengan data terukur dari uji laboratorium basah:
1. Normalisasi entri eksperimen {id, ligan_id, assay, nilai, satuan, pIC50, tanggal, catatan, status_hipotesis}.
2. Perbandingan prediksi vs terukur: korelasi Spearman ρ, Kendall τ, serta bootstrap CI 95% (1000×).
3. Peringatan statistik untuk sampel kecil (n < 8) dan penanganan ligan tanpa pasangan.
4. Pengurai berkas CSV: tabel IC50 per ligan, atau matriks bacaan plate reader yang diubah
   menjadi IC50 lewat normalisasi kontrol pelat dan fit dosis-respons 4PL.
"""
import csv
import io
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import stats

from . import grafik, labplanner

STATUS_HIPOTESIS = ("diajukan", "diuji", "didukung", "ditolak")
STATUS_BAWAAN = "diajukan"

SATUAN_KE_MOLAR = {
    "M": 1.0,
    "mM": 1e-3,
    "uM": 1e-6,
    "µM": 1e-6,
    "μM": 1e-6,
    "nM": 1e-9,
    "pM": 1e-12,
}


def ke_pic50(nilai: Optional[float], satuan: str = "uM") -> Optional[float]:
    """Hitung pIC50 = -log10(konsentrasi molar) dari nilai dan satuan terukur.

    Bila nilai <= 0, None, atau satuan tidak dikenal, kembalikan None.
    """
    if nilai is None:
        return None
    try:
        val = float(nilai)
    except (ValueError, TypeError):
        return None
    if val <= 0:
        return None
    faktor = SATUAN_KE_MOLAR.get((satuan or "").strip())
    if faktor is None:
        return None
    molar = val * faktor
    if molar <= 0:
        return None
    return round(-math.log10(molar), 4)


def normalisasi_entri(d: Dict[str, Any], indeks: int = 1) -> Dict[str, Any]:
    """Pastikan struktur entri eksperimen valid dan lengkap."""
    if not isinstance(d, dict):
        d = {}

    entri_id = str(d.get("id") or f"EXP{indeks:03d}").strip()
    ligan_id = str(d.get("ligan_id") or d.get("ligan") or d.get("nama") or "").strip()
    assay = str(d.get("assay") or "Inhibisi Enzim").strip()

    nilai_mentah = d.get("nilai")
    nilai_float = None
    if nilai_mentah not in (None, "", "-"):
        try:
            nilai_float = float(nilai_mentah)
        except (ValueError, TypeError):
            nilai_float = None

    satuan = str(d.get("satuan") or "uM").strip()

    pic50_mentah = d.get("pIC50") if "pIC50" in d else d.get("pic50")
    pic50_float = None
    if pic50_mentah not in (None, "", "-"):
        try:
            pic50_float = float(pic50_mentah)
        except (ValueError, TypeError):
            pic50_float = None

    if pic50_float is None and nilai_float is not None:
        pic50_float = ke_pic50(nilai_float, satuan)

    tanggal = str(d.get("tanggal") or datetime.now().strftime("%Y-%m-%d")).strip()
    catatan = str(d.get("catatan") or "").strip()

    status = str(d.get("status_hipotesis") or STATUS_BAWAAN).strip().lower()
    if status not in STATUS_HIPOTESIS:
        status = STATUS_BAWAAN

    return {
        "id": entri_id,
        "ligan_id": ligan_id,
        "assay": assay,
        "nilai": nilai_float,
        "satuan": satuan,
        "pIC50": pic50_float,
        "tanggal": tanggal,
        "catatan": catatan,
        "status_hipotesis": status,
    }


def ambil_entri_proyek(proyek: Any) -> List[Dict[str, Any]]:
    """Ambil daftar entri eksperimen dari model Proyek."""
    if not proyek:
        return []
    eks = getattr(proyek, "eksperimen", None)
    if not eks:
        return []
    if isinstance(eks, list):
        daftar = eks
    elif isinstance(eks, dict):
        daftar = eks.get("entri") or []
    else:
        return []
    return [normalisasi_entri(x, i + 1) for i, x in enumerate(daftar)]


def simpan_entri_proyek(proyek: Any, entri_list: List[Dict[str, Any]]) -> None:
    """Simpan daftar entri eksperimen ke model Proyek tanpa merusak metadata lain."""
    if not proyek:
        return
    norm = [normalisasi_entri(x, i + 1) for i, x in enumerate(entri_list)]
    if getattr(proyek, "eksperimen", None) is None:
        proyek.eksperimen = {"entri": norm}
    elif isinstance(proyek.eksperimen, dict):
        proyek.eksperimen["entri"] = norm
    elif isinstance(proyek.eksperimen, list):
        proyek.eksperimen = {"entri": norm}
    else:
        proyek.eksperimen = {"entri": norm}


def bandingkan(prediksi: Sequence[Optional[float]],
               terukur: Sequence[Optional[float]],
               n_bootstrap: int = 1000,
               seed: int = 42) -> Dict[str, Any]:
    """Bandingkan nilai prediksi in silico vs nilai terukur laboratorium.

    Menghitung:
    - n: jumlah sampel berpasangan lengkap
    - n_dilewati: jumlah entri yang dilewati karena data tidak lengkap
    - Spearman ρ, p-value
    - Kendall τ, p-value
    - CI bootstrap 95% untuk ρ dan τ (1000×)
    - Peringatan bila n < 8

    Parameter:
    - prediksi: deret angka prediksi (mis. -ΔG, pIC50_pred, skor)
    - terukur: deret angka eksperimen (mis. pIC50 terukur)
    - n_bootstrap: jumlah replika bootstrap (bawaan 1000)
    - seed: seed acak numpy untuk hasil deterministik
    """
    total_input = max(len(prediksi), len(terukur))
    pairs: List[Tuple[float, float]] = []

    for p, t in zip(prediksi, terukur):
        if p is None or t is None:
            continue
        try:
            pf = float(p)
            tf = float(t)
        except (ValueError, TypeError):
            continue
        if math.isnan(pf) or math.isnan(tf) or math.isinf(pf) or math.isinf(tf):
            continue
        pairs.append((pf, tf))

    n = len(pairs)
    n_dilewati = total_input - n

    hasil: Dict[str, Any] = {
        "n": n,
        "n_dilewati": n_dilewati,
        "spearman": None,
        "p_spearman": None,
        "kendall": None,
        "p_kendall": None,
        "ci_spearman": None,
        "ci_kendall": None,
        "peringatan": None,
    }

    if n < 3:
        hasil["peringatan"] = f"Jumlah sampel terpasang (n = {n}) kurang dari 3 untuk evaluasi korelasi."
        return hasil

    p_arr = np.array([x[0] for x in pairs], dtype=float)
    t_arr = np.array([x[1] for x in pairs], dtype=float)

    # Deteksi bila nilai konstan (tidak ada varians)
    if float(np.ptp(p_arr)) == 0.0 or float(np.ptp(t_arr)) == 0.0:
        hasil["peringatan"] = "Varians salah satu variabel adalah nol (seluruh nilai identik)."
        return hasil

    # Spearman & Kendall
    sp = stats.spearmanr(p_arr, t_arr)
    kd = stats.kendalltau(p_arr, t_arr)

    hasil["spearman"] = round(float(sp.statistic), 4) if not math.isnan(sp.statistic) else None
    hasil["p_spearman"] = float(sp.pvalue) if not math.isnan(sp.pvalue) else None
    hasil["kendall"] = round(float(kd.statistic), 4) if not math.isnan(kd.statistic) else None
    hasil["p_kendall"] = float(kd.pvalue) if not math.isnan(kd.pvalue) else None

    # Bootstrap 1000x untuk Confidence Interval 95%
    rng = np.random.default_rng(seed)
    boot_idx = rng.choice(n, size=(n_bootstrap, n), replace=True)

    rho_list = []
    tau_list = []

    for idxs in boot_idx:
        xb = p_arr[idxs]
        yb = t_arr[idxs]
        if np.ptp(xb) == 0.0 or np.ptp(yb) == 0.0:
            continue
        try:
            r_sp = stats.spearmanr(xb, yb).statistic
            if not math.isnan(r_sp):
                rho_list.append(float(r_sp))
        except Exception:
            pass

        try:
            r_kd = stats.kendalltau(xb, yb).statistic
            if not math.isnan(r_kd):
                tau_list.append(float(r_kd))
        except Exception:
            pass

    if len(rho_list) >= 20:
        ci_sp = (round(float(np.percentile(rho_list, 2.5)), 4),
                 round(float(np.percentile(rho_list, 97.5)), 4))
        hasil["ci_spearman"] = ci_sp

    if len(tau_list) >= 20:
        ci_kd = (round(float(np.percentile(tau_list, 2.5)), 4),
                 round(float(np.percentile(tau_list, 97.5)), 4))
        hasil["ci_kendall"] = ci_kd

    # Peringatan ukuran sampel
    if n < 8:
        hasil["peringatan"] = (
            f"Jumlah sampel terpasang (n = {n}) kurang dari 8. "
            "Estimasi korelasi dan interval kepercayaan bootstrap mungkin tidak stabil."
        )

    return hasil


def impor_csv_hasil(jalur_atau_teks: Union[str, Path],
                    denah_pelat: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Baca data hasil laboratorium basah dari berkas CSV atau teks CSV.

    Mendukung dua format:
    1. Tabel baris CSV standar berkolom: ligan_id / ligan / nama, nilai / ic50, satuan, pic50, assay, status, catatan.
    2. Format plate reader mikro (96-well) baris A..H dan kolom 1..12 yang dipetakan ke denah pelat.
    """
    if isinstance(jalur_atau_teks, Path) or (isinstance(jalur_atau_teks, str) and "\n" not in jalur_atau_teks and Path(jalur_atau_teks).is_file()):
        teks = Path(jalur_atau_teks).read_text(encoding="utf-8-sig", errors="replace")
    else:
        teks = str(jalur_atau_teks)

    baris_mentah = [b.strip() for b in teks.splitlines() if b.strip() and not b.lstrip().startswith("#")]
    if not baris_mentah:
        return []

    # Deteksi pemisah
    sampel = "\n".join(baris_mentah[:10])
    try:
        dialek = csv.Sniffer().sniff(sampel, delimiters=",;\t")
        sep = dialek.delimiter
    except Exception:
        sep = "," if "," in baris_mentah[0] else ("\t" if "\t" in baris_mentah[0] else ";")

    reader = list(csv.reader(io.StringIO("\n".join(baris_mentah)), delimiter=sep))
    if not reader:
        return []

    header = [h.strip().lower() for h in reader[0]]

    # Cek apakah ini format matriks plate reader 96-well: Header berupa kolom 1..12
    angka_kolom = [c for c in header if c.isdigit()]
    if len(angka_kolom) >= 6 and len(reader) >= 2:
        # Matriks plate reader (baris A-H, kolom 1-12) berisi sinyal mentah, BUKAN IC50.
        # IC50 diturunkan lewat normalisasi kontrol + fit 4PL sesuai denah pelat.
        sinyal = _baca_matriks_pelat(reader)
        if sinyal:
            return analisis_pelat(sinyal, denah_pelat)["entri"]

    # Format tabel kolom standar
    kolom_map = {}
    for idx, h in enumerate(header):
        hl = h.replace(" ", "_").replace("-", "_").lower()
        if hl in ("ligan_id", "ligan", "nama", "nama_ligan", "compound", "id", "sample"):
            kolom_map.setdefault("ligan_id", idx)
        elif hl in ("nilai", "value", "ic50", "ec50", "ki", "kd", "hasil"):
            kolom_map.setdefault("nilai", idx)
        elif hl in ("satuan", "unit", "units"):
            kolom_map.setdefault("satuan", idx)
        elif hl in ("pic50", "pchembl", "pic50_terukur", "pactivity"):
            kolom_map.setdefault("pIC50", idx)
        elif hl in ("assay", "pengujian", "metode"):
            kolom_map.setdefault("assay", idx)
        elif hl in ("status", "status_hipotesis", "kesimpulan"):
            kolom_map.setdefault("status_hipotesis", idx)
        elif hl in ("catatan", "notes", "keterangan"):
            kolom_map.setdefault("catatan", idx)
        elif hl in ("tanggal", "date"):
            kolom_map.setdefault("tanggal", idx)

    entri_list = []
    for r_idx, baris in enumerate(reader[1:]):
        if not any(baris):
            continue
        d = {}
        for k, col_i in kolom_map.items():
            if col_i < len(baris):
                d[k] = baris[col_i].strip()

        # Fallback jika ligan_id tidak ditentukan lewat header eksplisit
        if "ligan_id" not in d and len(baris) > 0:
            d["ligan_id"] = baris[0].strip()
        if "nilai" not in d and len(baris) > 1:
            d["nilai"] = baris[1].strip()

        entri_list.append(normalisasi_entri(d, r_idx + 1))

    return entri_list


def _baca_matriks_pelat(reader: List[List[str]]) -> Dict[str, float]:
    """Bacaan mentah per sumur {'A1': sinyal, ...} dari matriks plate reader (baris huruf, kolom angka)."""
    header = [h.strip() for h in reader[0]]
    kolom = [(i, h) for i, h in enumerate(header) if h.isdigit()]
    sinyal: Dict[str, float] = {}
    for baris in reader[1:]:
        if not baris:
            continue
        huruf = baris[0].strip().upper()
        if not huruf or len(huruf) > 2 or not huruf.isalpha():
            continue
        for col_idx, no_kol in kolom:
            if col_idx >= len(baris):
                continue
            teks = baris[col_idx].strip().replace(",", ".")
            if not teks:
                continue
            try:
                sinyal[f"{huruf}{no_kol}"] = float(teks)
            except ValueError:
                continue
    return sinyal


def _logistik4(x, bawah, atas, log_ic50, hill):
    """Model 4PL: % inhibisi naik terhadap konsentrasi (x dalam µM)."""
    return bawah + (atas - bawah) / (1.0 + 10.0 ** ((log_ic50 - np.log10(x)) * hill))


def fit_dosis_respons(kons_uM: Sequence[float], inhibisi: Sequence[float]) -> Dict[str, Any]:
    """Fit 4PL ke titik (konsentrasi µM, % inhibisi) termasuk semua replikat.

    IC50 hanya dilaporkan bila jatuh di dalam rentang konsentrasi yang diuji; di luar itu
    nilainya tersensor ('>' konsentrasi tertinggi atau '<' terendah) karena ekstrapolasi 4PL
    tidak ditopang data. Kembalikan {ic50_uM, sensor, hill, r2, n, pesan}.
    """
    from scipy.optimize import curve_fit

    x = np.asarray(kons_uM, dtype=float)
    y = np.asarray(inhibisi, dtype=float)
    ok = (x > 0) & np.isfinite(y)
    x, y = x[ok], y[ok]
    hasil = {"ic50_uM": None, "sensor": None, "hill": None, "r2": None, "n": int(len(x)), "pesan": ""}
    if len(np.unique(x)) < 4:
        hasil["pesan"] = "butuh minimal 4 konsentrasi berbeda untuk fit 4PL"
        return hasil
    lo, hi = float(x.min()), float(x.max())
    if float(np.max(y)) < 50.0:
        hasil.update(sensor=">", ic50_uM=hi, pesan=f"inhibisi maksimum {np.max(y):.0f} % < 50 %")
        return hasil
    if float(np.min(y)) > 50.0:
        hasil.update(sensor="<", ic50_uM=lo, pesan=f"inhibisi minimum {np.min(y):.0f} % > 50 %")
        return hasil
    p0 = [max(-20.0, float(np.min(y))), min(120.0, float(np.max(y))), float(np.median(np.log10(x))), 1.0]
    batas = ([-30.0, 50.0, math.log10(lo) - 2, 0.2], [30.0, 130.0, math.log10(hi) + 2, 5.0])
    try:
        par, _ = curve_fit(_logistik4, x, y, p0=p0, bounds=batas, maxfev=20000)
    except (RuntimeError, ValueError) as e:
        hasil["pesan"] = f"fit 4PL gagal: {e}"
        return hasil
    pred = _logistik4(x, *par)
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    ic50 = 10.0 ** par[2]
    hasil.update(hill=round(float(par[3]), 2), r2=round(r2, 3) if r2 is not None else None)
    if ic50 > hi:
        hasil.update(sensor=">", ic50_uM=hi, pesan="IC50 di atas konsentrasi tertinggi")
    elif ic50 < lo:
        hasil.update(sensor="<", ic50_uM=lo, pesan="IC50 di bawah konsentrasi terendah")
    else:
        hasil["ic50_uM"] = round(float(ic50), 4)
    return hasil


def analisis_pelat(sinyal: Dict[str, float], denah_pelat: Optional[Dict[str, Any]],
                   sinyal_turun: bool = True) -> Dict[str, Any]:
    """Ubah bacaan mentah plate reader menjadi IC50 per sampel memakai denah pelat.

    % aktivitas = (S - rerata blanko) / (rerata pelarut - rerata blanko) x 100; % inhibisi =
    100 - % aktivitas (sinyal_turun=True: inhibitor menurunkan sinyal, mis. uji enzim kolorimetri).
    Z' = 1 - 3(sd pelarut + sd kontrol positif) / |rerata pelarut - rerata kontrol positif|
    bila kontrol positif ada. Kembalikan {entri, zprime, peringatan}.
    """
    grid = (denah_pelat or {}).get("grid") or {}
    if not any(g.get("jenis") == "sampel" for g in grid.values()):
        raise ValueError("Bacaan pelat butuh denah berisi sumur sampel: susun dulu denah di tab "
                         "Denah Pelat Mikro untuk ligan yang diuji.")

    def _nilai(jenis):
        return np.array([sinyal[p] for p, g in grid.items() if g.get("jenis") == jenis and p in sinyal])

    blanko, pelarut, pos = _nilai("blanko"), _nilai("pelarut"), _nilai("kontrol_pos")
    if len(blanko) == 0 or len(pelarut) == 0:
        raise ValueError("Sumur blanko dan kendali pelarut (DMSO) tidak terbaca; normalisasi tidak mungkin.")
    rentang = float(pelarut.mean() - blanko.mean())
    if abs(rentang) < 1e-12:
        raise ValueError("Sinyal kendali pelarut sama dengan blanko; jendela uji nol.")

    peringatan = []
    zprime = None
    if len(pos) >= 2 and len(pelarut) >= 2:
        beda = abs(float(pelarut.mean() - pos.mean()))
        if beda > 0:
            zprime = round(1.0 - 3.0 * (float(pelarut.std(ddof=1)) + float(pos.std(ddof=1))) / beda, 3)
            if zprime < 0.5:
                peringatan.append(f"Z′ = {zprime:.2f} < 0,5: jendela uji sempit, IC50 kurang andal.")

    per_sampel: Dict[str, List[Tuple[float, float]]] = {}
    for posisi, g in grid.items():
        if g.get("jenis") != "sampel" or posisi not in sinyal or not g.get("kons_uM"):
            continue
        aktivitas = (sinyal[posisi] - blanko.mean()) / rentang * 100.0
        inhib = 100.0 - aktivitas if sinyal_turun else aktivitas
        nama = g.get("sampel") or g.get("label") or posisi
        per_sampel.setdefault(nama, []).append((float(g["kons_uM"]), float(inhib)))

    entri = []
    for nama, titik in per_sampel.items():
        fit = fit_dosis_respons([t[0] for t in titik], [t[1] for t in titik])
        bagian = [f"4PL dari {fit['n']} sumur"]
        if fit["hill"] is not None:
            bagian.append(f"Hill {fit['hill']:.2f}")
        if fit["r2"] is not None:
            bagian.append(f"R² {fit['r2']:.3f}")
        if zprime is not None:
            bagian.append(f"Z′ {zprime:.2f}")
        if fit["pesan"]:
            bagian.append(fit["pesan"])
        tersensor = fit["sensor"] is not None or fit["ic50_uM"] is None
        if fit["sensor"]:
            bagian.insert(0, f"IC50 {fit['sensor']} {fit['ic50_uM']:g} µM")
        entri.append(normalisasi_entri({
            "id": f"PELAT_{nama}",
            "ligan_id": nama,
            "assay": "Uji pelat mikro (4PL)",
            # Nilai tersensor tidak dijadikan angka agar tidak ikut dikorelasikan seolah terukur
            "nilai": None if tersensor else fit["ic50_uM"],
            "satuan": "uM",
            "catatan": "; ".join(bagian),
            "status_hipotesis": "diuji",
        }))
    return {"entri": entri, "zprime": zprime, "peringatan": peringatan}


def _mmgbsa_proyek(proyek: Any) -> Dict[str, float]:
    """ΔG MM/GBSA per ligan dari run MD selesai (rerata replika bila ada; run terakhir menang)."""
    hasil: Dict[str, float] = {}
    for run in getattr(proyek, "md", None) or []:
        if not isinstance(run, dict):
            continue
        for d in run.get("ligan") or []:
            if not isinstance(d, dict) or not d.get("selesai"):
                continue
            agregat = (d.get("replika_agregat") or {}).get("mmgbsa_dG")
            mm = d.get("mmgbsa") or {}
            nilai = agregat[0] if agregat and d.get("replika") and len(d["replika"]) > 1 else mm.get("dG")
            if d.get("lid") and nilai is not None:
                try:
                    hasil[str(d["lid"])] = float(nilai)
                except (TypeError, ValueError):
                    pass
    return hasil


def ada_prediksi(proyek: Any, jenis_prediksi: str) -> bool:
    """Apakah proyek punya setidaknya satu nilai prediksi jenis ini (untuk menonaktifkan pilihan kosong)."""
    if not proyek:
        return False
    if jenis_prediksi in ("dg", "pic50_pred"):
        return any(p.get("energi") is not None
                   for j in getattr(proyek, "job", []) for l in j.get("ligan", []) for p in (l.get("pose") or []))
    if jenis_prediksi == "mmgbsa":
        return bool(_mmgbsa_proyek(proyek))
    return False


def kumpulkan_data_tabel(proyek: Any, jenis_prediksi: str = "dg") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Kumpulkan baris gabungan ligan x prediksi x terukur untuk tabel UI dan grafik.

    jenis_prediksi:
    - 'dg': energi bebas pengikatan docking (kcal/mol) -> -ΔG untuk korelasi positif
    - 'mmgbsa': energi bebas MM/GBSA (kcal/mol)
    - 'pic50_pred': pIC50 estimasi dari ΔG (Ki -> IC50; monoton terhadap ΔG)
    """
    if not proyek:
        return [], bandingkan([], [])

    ligan_dict: Dict[str, Dict[str, Any]] = {}
    # Ambil ligan yang ada di proyek
    for lig in getattr(proyek, "ligan", []):
        lid = str(lig.get("id") or "")
        nama = str(lig.get("nama") or lid)
        ligan_dict[lid] = {
            "ligan_id": lid,
            "nama": nama,
            "smiles": str((proyek.smiles_ligan(lig) if hasattr(proyek, "smiles_ligan") else lig.get("smiles")) or ""),
            "dg": None,
            "mmgbsa": None,
            "pic50_pred": None,
            "entri_exp": None,
        }

    # Ambil pose terbaik dari job docking
    for j in getattr(proyek, "job", []):
        for l_res in j.get("ligan", []):
            lid = str(l_res.get("id") or "")
            if lid not in ligan_dict:
                ligan_dict[lid] = {
                    "ligan_id": lid,
                    "nama": str(l_res.get("nama") or lid),
                    "smiles": "",
                    "dg": None,
                    "mmgbsa": None,
                    "pic50_pred": None,
                    "entri_exp": None,
                }
            poses = l_res.get("pose") or []
            if poses:
                energi_list = [p.get("energi") for p in poses if p.get("energi") is not None]
                if energi_list:
                    terbaik_dg = min(energi_list)
                    if ligan_dict[lid]["dg"] is None or terbaik_dg < ligan_dict[lid]["dg"]:
                        ligan_dict[lid]["dg"] = terbaik_dg
                        pred_ki = labplanner.prediksi_ki_ic50(terbaik_dg)
                        if pred_ki.get("ic50_uM"):
                            ligan_dict[lid]["pic50_pred"] = ke_pic50(pred_ki["ic50_uM"], "uM")

    # MM/GBSA dari run MD proyek: proyek.md = [{..., "ligan": [{"lid", "mmgbsa": {"dG"}, ...}]}]
    for lid, dg in _mmgbsa_proyek(proyek).items():
        if lid in ligan_dict:
            ligan_dict[lid]["mmgbsa"] = dg

    # Ambil entri eksperimen dari proyek
    entri_eks = ambil_entri_proyek(proyek)
    entri_per_ligan: Dict[str, Dict[str, Any]] = {}
    for ent in entri_eks:
        target_lid = ent["ligan_id"]
        # Cocokkan berdasarkan ID persis atau nama
        cocok_key = None
        if target_lid in ligan_dict:
            cocok_key = target_lid
        else:
            for k_id, item in ligan_dict.items():
                if item["nama"].lower() == target_lid.lower():
                    cocok_key = k_id
                    break
        if cocok_key:
            entri_per_ligan[cocok_key] = ent
        else:
            # Ligan eksperimen belum ada di docking proyek, tetap daftarkan
            ligan_dict[target_lid] = {
                "ligan_id": target_lid,
                "nama": target_lid,
                "smiles": "",
                "dg": None,
                "mmgbsa": None,
                "pic50_pred": None,
                "entri_exp": ent,
            }
            entri_per_ligan[target_lid] = ent

    # Pasangkan entri eksperimen ke ligan_dict
    for lid, ent in entri_per_ligan.items():
        if lid in ligan_dict:
            ligan_dict[lid]["entri_exp"] = ent

    baris_tabel: List[Dict[str, Any]] = []
    prediksi_vals: List[Optional[float]] = []
    terukur_vals: List[Optional[float]] = []

    for lid, item in sorted(ligan_dict.items(), key=lambda x: (x[1]["dg"] is None, x[1]["dg"] or 0)):
        ent = item["entri_exp"] or {}
        # Nilai prediksi terpilih
        if jenis_prediksi == "dg":
            pred_tampil = item["dg"]
            # Dalam korelasi vs pIC50 terukur: makin negatif ΔG = makin aktif
            # Untuk grafik yang intuitif dengan korelasi positif searah pIC50, gunakan -ΔG atau ΔG langsung
            pred_korelasi = -item["dg"] if item["dg"] is not None else None
        elif jenis_prediksi == "mmgbsa":
            pred_tampil = item["mmgbsa"]
            pred_korelasi = -item["mmgbsa"] if item["mmgbsa"] is not None else None
        elif jenis_prediksi == "pic50_pred":
            pred_tampil = item["pic50_pred"]
            pred_korelasi = item["pic50_pred"]
        else:
            pred_tampil = item["dg"]
            pred_korelasi = -item["dg"] if item["dg"] is not None else None

        pic50_terukur = ent.get("pIC50")

        baris_tabel.append({
            "ligan_id": lid,
            "nama": item["nama"],
            "smiles": item["smiles"],
            "prediksi_tampil": pred_tampil,
            "prediksi_korelasi": pred_korelasi,
            "nilai_terukur": ent.get("nilai"),
            "satuan_terukur": ent.get("satuan", "uM"),
            "pic50_terukur": pic50_terukur,
            "status_hipotesis": ent.get("status_hipotesis", "diajukan"),
            "assay": ent.get("assay", "Inhibisi"),
            "catatan": ent.get("catatan", ""),
            "id_exp": ent.get("id", ""),
            "tanggal": ent.get("tanggal", ""),
        })

        prediksi_vals.append(pred_korelasi)
        terukur_vals.append(pic50_terukur)

    stats_hasil = bandingkan(prediksi_vals, terukur_vals)
    return baris_tabel, stats_hasil


def buat_grafik_prediksi_vs_terukur(baris_tabel: List[Dict[str, Any]],
                                    jenis_prediksi: str = "dg",
                                    gelap: bool = False,
                                    lebar: int = 580,
                                    tinggi: int = 480) -> str:
    """Bangun representasi SVG grafik sebar Prediksi vs Terukur dengan regresi linear dan pita CI 95%."""
    pasangan_valid = [
        (b["nama"], float(b["prediksi_tampil"]), float(b["pic50_terukur"]))
        for b in baris_tabel
        if b.get("prediksi_tampil") is not None and b.get("pic50_terukur") is not None
    ]

    label_pred_map = {
        "dg": "ΔG Docking (kcal/mol)",
        "mmgbsa": "MM/GBSA (kcal/mol)",
        "pic50_pred": "pIC50 estimasi dari ΔG",
    }
    lbl_x = label_pred_map.get(jenis_prediksi, "Prediksi In Silico")
    lbl_y = "pIC50 terukur"
    judul = "Prediksi in silico vs aktivitas terukur"

    if len(pasangan_valid) < 3:
        # Ambang sama dengan bandingkan(): korelasi dan garis regresi butuh minimal 3 pasang
        k = grafik.Kanvas(lebar, tinggi, gelap, judul=judul)
        k.teks(lebar / 2, tinggi / 2, f"{len(pasangan_valid)} pasang prediksi–terukur; grafik butuh minimal 3",
               12, "middle")
        return k.selesai()

    nama_list = [p[0] for p in pasangan_valid]
    x_list = [p[1] for p in pasangan_valid]
    y_list = [p[2] for p in pasangan_valid]

    from .statistik import korelasi
    reg = korelasi(x_list, y_list, pita=True)

    return grafik.sebar(
        x_list, y_list, nama=nama_list,
        label_x=lbl_x, label_y=lbl_y,
        judul=judul, regresi=reg,
        gelap=gelap, lebar=lebar, tinggi=tinggi,
        label=len(pasangan_valid) <= 15,
        catatan=""
    )
