"""Cross-Target Selectivity Matrix & Ensemble Docking.

Membandingkan hasil docking ligan ke beberapa protein target sekaligus,
memetakan profil selektivitas versus promiskuitas, menghitung Z-score normalisasi,
dan indeks selektivitas afinitas (ΔΔG).
"""
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
import math
from rdkit import Chem
from . import catat, ekspor
from .proyek import Proyek


def _kanonikal_smiles(smi: str) -> str:
    """Ubah string SMILES menjadi bentuk kanonikal untuk pencocokan ligan lintas target."""
    if not smi:
        return ""
    try:
        m = Chem.MolFromSmiles(smi.strip().split()[0])
        if m:
            return Chem.MolToSmiles(m)
    except Exception:
        pass
    return smi.strip()


def muat_proyek_ganda(daftar_jalur: List[Union[str, Path, Proyek]]) -> List[Tuple[str, Proyek]]:
    """Muat beberapa proyek VirmoDock dari direktori atau objek proyek.

    Kembalikan list of (nama_target, proyek_obj).
    """
    hasil = []
    for item in daftar_jalur:
        if isinstance(item, Proyek):
            pr = item
        else:
            try:
                pr = Proyek.buka(item)
            except Exception as err:
                catat.log.warning(f"Gagal membuka proyek '{item}' untuk analisis selektivitas: {err}")
                continue

        # Tentukan nama target
        nama_target = ""
        if pr.reseptor and isinstance(pr.reseptor, dict):
            nama_target = pr.reseptor.get("nama") or ""
        if not nama_target:
            nama_target = pr.nama or "Target"
        hasil.append((nama_target, pr))

    return hasil


def matriks_selektivitas(
    proyek_list: List[Tuple[str, Proyek]], variabel: str = "energi"
) -> Tuple[List[str], List[str], List[List[Optional[float]]], Dict[str, Dict[str, Any]]]:
    """Ekstraksi matriks selektivitas Ligan (baris) x Target (kolom).

    proyek_list: list of (nama_target, Proyek)
    variabel: 'energi' (ΔG), 'le' (Ligand Efficiency), 'ki'

    Pencocokan ligan antar proyek dilakukan berbasis SMILES kanonik (jika tersedia)
    atau nama ligan.

    Kembalikan:
      - label_ligan: list nama ligan unik
      - label_target: list nama target
      - matriks: 2D list berukuran len(label_ligan) x len(label_target)
      - meta_ligan: dict info per ligan {id: {nama, smiles, count_target}}
    """
    if not proyek_list:
        return [], [], [], {}

    label_target = [t[0] for t in proyek_list]

    # Kumpulkan hasil per proyek: map {id_kanon: nilai}
    data_per_target = []
    kamus_ligan = {}  # {id_kanon: {'nama': str, 'smiles': str}}

    for _, pr in proyek_list:
        skor_target = {}
        baris = ekspor.baris_hasil(pr)
        for b in baris:
            nama = b.get("ligan") or "Ligan"
            smi = b.get("smiles") or ""
            id_kanon = _kanonikal_smiles(smi) if smi else nama.strip().lower()

            if id_kanon not in kamus_ligan:
                kamus_ligan[id_kanon] = {
                    "nama": nama,
                    "smiles": smi,
                }

            val = b.get(variabel)
            if val is not None:
                try:
                    val = float(val)
                    # Simpan nilai terbaik (paling negatif untuk ΔG/LE)
                    if id_kanon not in skor_target or val < skor_target[id_kanon]:
                        skor_target[id_kanon] = val
                except (ValueError, TypeError):
                    pass
        data_per_target.append(skor_target)

    # Urutkan ligan berdasarkan jumlah target yang tercakup lalu nama
    semua_ligan = list(kamus_ligan.keys())
    semua_ligan.sort(
        key=lambda k: (
            -sum(1 for tgt in data_per_target if k in tgt),
            kamus_ligan[k]["nama"].lower()
        )
    )

    label_ligan = [kamus_ligan[k]["nama"] for k in semua_ligan]

    # Susun matriks
    matriks = []
    for k in semua_ligan:
        baris_val = []
        for tgt in data_per_target:
            baris_val.append(tgt.get(k))
        matriks.append(baris_val)

    return label_ligan, label_target, matriks, kamus_ligan


def zscore_normalisasi(
    matriks: List[List[Optional[float]]]
) -> List[List[Optional[float]]]:
    """Hitung Z-Score kolom-per-kolom (per target) untuk melihat selektivitas relatif.

    Z = (X - μ) / σ
    Nilai Z negatif menandakan afinitas lebih kuat dari rata-rata ligan pada target tersebut.
    """
    if not matriks or not matriks[0]:
        return []

    n_baris = len(matriks)
    n_kolom = len(matriks[0])

    # Hitung rata-rata dan deviasi standar per kolom
    mu_list = []
    sigma_list = []

    for c in range(n_kolom):
        vals = [matriks[r][c] for r in range(n_baris) if matriks[r][c] is not None]
        if len(vals) >= 2:
            mu = sum(vals) / len(vals)
            var = sum((x - mu) ** 2 for x in vals) / (len(vals) - 1)
            sigma = math.sqrt(var) if var > 1e-9 else 1.0
        elif len(vals) == 1:
            mu = vals[0]
            sigma = 1.0
        else:
            mu, sigma = 0.0, 1.0
        mu_list.append(mu)
        sigma_list.append(sigma)

    matriks_z = []
    for r in range(n_baris):
        baris_z = []
        for c in range(n_kolom):
            v = matriks[r][c]
            if v is not None and sigma_list[c] > 1e-9:
                z = (v - mu_list[c]) / sigma_list[c]
                baris_z.append(round(z, 2))
            else:
                baris_z.append(None)
        matriks_z.append(baris_z)

    return matriks_z


def klasifikasi_selektivitas(
    matriks: List[List[Optional[float]]],
    label_target: List[str],
    ambang_ddg: float = 1.5,
) -> List[Dict[str, Any]]:
    """Klasifikasi profil selektivitas per ligan lintas target.

    Kategori:
      - 'Selektif': ΔG pada target terbaik lebih kuat ≥ ambang_ddg dari target kedua.
      - 'Semi-selektif': 0.5 ≤ ΔΔG < ambang_ddg.
      - 'Promiskuitas': Mengikat semua target dengan afinitas relatif sebanding (|ΔΔG| < 0.5).
      - 'Data Parsial': Ligan hanya diuji pada satu target.
    """
    hasil = []
    for r, baris in enumerate(matriks):
        # Kumpulkan nilai target yang terukur
        terukur = [(baris[c], label_target[c], c) for c in range(len(baris)) if baris[c] is not None]
        if not terukur:
            hasil.append({"kelas": "Kosong", "target_utama": "-", "ddg": 0.0, "cakupan": 0})
            continue

        if len(terukur) == 1:
            hasil.append({
                "kelas": "Data Parsial",
                "target_utama": terukur[0][1],
                "ddg": 0.0,
                "cakupan": 1,
            })
            continue

        # Urutkan nilai ΔG (paling negatif = terkuat)
        terukur.sort(key=lambda x: x[0])
        val_terbaik, target_terbaik, _ = terukur[0]
        val_kedua, target_kedua, _ = terukur[1]

        # ΔΔG = ΔG_kedua - ΔG_terbaik (positif menandakan target terbaik lebih kuat)
        gap = val_kedua - val_terbaik

        if gap >= ambang_ddg:
            kelas = f"Selektif ({target_terbaik})"
        elif gap >= 0.5:
            kelas = f"Semi-selektif ({target_terbaik})"
        else:
            kelas = "Promiskuitas"

        hasil.append({
            "kelas": kelas,
            "target_utama": target_terbaik,
            "target_kedua": target_kedua,
            "ddg": round(gap, 2),
            "cakupan": len(terukur),
        })

    return hasil


def indeks_selektivitas(
    matriks: List[List[Optional[float]]],
    target_utama_idx: int,
    target_pembanding_idx: int,
) -> List[Optional[float]]:
    """Hitung indeks selektivitas spesifik antara dua target: ΔΔG = ΔG_pembanding - ΔG_utama.

    Nilai positif = lebih selektif ke target utama.
    Nilai negatif = lebih selektif ke target pembanding.
    """
    hasil = []
    for baris in matriks:
        v_ut = baris[target_utama_idx] if target_utama_idx < len(baris) else None
        v_pb = baris[target_pembanding_idx] if target_pembanding_idx < len(baris) else None
        if v_ut is not None and v_pb is not None:
            hasil.append(round(v_pb - v_ut, 2))
        else:
            hasil.append(None)
    return hasil
