"""Telaah air kristal di sisi aktif (hydration site, berbasis aturan geometri).

PENTING: modul ini TIDAK menghitung termodinamika air sungguhan. Metode sebenarnya (WaterMap, GIST, 3D-RISM, SZMAP)
memerlukan simulasi pelarut eksplisit. Di sini tiap air kristal hanya digolongkan dari lingkungannya: jumlah
pasangan polar (N/O ≤ 3,2 Å) dan jumlah kontak karbon (≤ 3,8 Å). "skor_gusur" adalah angka heuristik tanpa satuan
(negatif = kandidat air yang layak digusur gugus hidrofobik ligan), bukan ΔG dalam kkal/mol.

Menganalisis molekul air (HOH / TIP3P) di sekitar sisi aktif reseptor dan pose docking:
1. Menghitung jaringan ikatan hidrogen air-protein.
2. Memprediksi stabilitas termodinamika molekul air:
   - Terstabilisasi / Terkonservasi: Menguntungkan dipertahankan (menjadi air penjembatan).
   - Berenergi Tinggi / Tidak Stabil: Terjebak di lingkungan hidrofobik; sangat menguntungkan
     bila digusur oleh gugus hidrofobik ligan untuk meningkatkan afinitas (ΔG gusur < 0).
"""
from typing import Any, Dict, List, Optional
import numpy as np

from .ppi import _uraikan_pdb


def _uraikan_air(pdb_teks: str) -> List[Dict[str, Any]]:
    """Ekstraksi koordinat oksigen molekul air dari string PDB."""
    air_list = []
    for baris in (pdb_teks or "").splitlines():
        if baris.startswith("HETATM") or baris.startswith("ATOM  "):
            resn = baris[17:20].strip().upper()
            nama_atom = baris[12:16].strip().upper()
            if resn in ("HOH", "WAT", "TIP", "H2O") and (nama_atom.startswith("O") or nama_atom == "OA"):
                try:
                    resi = int(baris[22:26].strip())
                    x = float(baris[30:38].strip())
                    y = float(baris[38:46].strip())
                    z = float(baris[46:54].strip())
                    air_list.append({
                        "id": f"HOH_{resi}",
                        "resi": resi,
                        "pos": np.array([x, y, z], dtype=np.float64),
                    })
                except (ValueError, IndexError):
                    continue
    return air_list


def analisis_termodinamika_air(
    pdb_kompleks_teks: str,
    titik_pusat: Optional[Dict[str, float]] = None,
    radius_kantong: float = 8.0
) -> List[Dict[str, Any]]:
    """Evaluasi stabilitas dan profil energi molekul air di sisi aktif.

    Kembalikan daftar dict per molekul air:
      - id: str, misal 'HOH_402'
      - pos: {'x': float, 'y': float, 'z': float}
      - n_hbond_protein: int
      - n_kontak_hidrofobik: int
      - kategori: 'Stabil (Pertahankan)' | 'Tidak Stabil (Gusur untuk Afinitas)' | 'Netral/Bulk'
      - skor_gusur: float (heuristik tanpa satuan; negatif = kandidat digusur)
      - residu_tetangga: list of str
    """
    atom_protein = _uraikan_pdb(pdb_kompleks_teks)
    air_list = _uraikan_air(pdb_kompleks_teks)
    if not air_list or not atom_protein:
        return []

    # Pisahkan atom protein (non-air)
    atom_prot = [a for a in atom_protein if a["resn"] not in ("HOH", "WAT", "TIP", "H2O")]
    if not atom_prot:
        return []

    pos_prot = np.array([a["pos"] for a in atom_prot], dtype=np.float64)
    simbol_prot = [a["simbol"] for a in atom_prot]
    res_prot = [f"{a['resn']} {a['resi']} ({a['rantai']})" for a in atom_prot]

    hasil = []
    pusat_arr = np.array([titik_pusat["x"], titik_pusat["y"], titik_pusat["z"]]) if titik_pusat else None

    for w in air_list:
        pos_w = w["pos"]
        # Filter jika dibatasi radius kantong
        if pusat_arr is not None:
            if np.linalg.norm(pos_w - pusat_arr) > radius_kantong:
                continue

        # Jarak ke semua atom protein
        diff = pos_prot - pos_w
        dist = np.sqrt(np.sum(diff * diff, axis=1))

        # 1. Ikatan hidrogen polar (N, O dalam jarak <= 3.2 Å)
        mask_hb = (dist <= 3.2)
        idx_hb = np.where(mask_hb)[0]
        n_hb = sum(1 for i in idx_hb if simbol_prot[i] in ("N", "O"))

        # 2. Kontak dengan atom karbon non-polar (C dalam jarak <= 3.8 Å)
        mask_c = (dist <= 3.8)
        idx_c = np.where(mask_c)[0]
        n_c = sum(1 for i in idx_c if simbol_prot[i] == "C")

        # 3. Residu di sekitarnya
        tetangga_idx = np.where(dist <= 4.0)[0]
        residu_dekat = sorted(list({res_prot[i] for i in tetangga_idx}))

        # 4. Prediksi stabilitas & Delta G penggusuran
        # Air terstabilisasi: memiliki banyak H-bond polar (>= 2) dan sedikit kontak C hidrofobik
        # Air berenergi tinggi (unstable/frustrated): kontak H-bond minim (<= 1) dikelilingi banyak C (>= 3)
        if n_hb >= 2 and n_c <= 2:
            kat = "Stabil (Pertahankan)"
            dg_gusur = round(1.5 + 0.8 * n_hb, 2)   # positif = sebaiknya dipertahankan (skor, tanpa satuan)
            rekomendasi = "Pertahankan sebagai air penjembatan ligan-protein"
        elif n_hb <= 1 and n_c >= 3:
            kat = "Tidak Stabil (Gusur untuk Afinitas)"
            dg_gusur = round(-1.2 - 0.4 * n_c, 2)   # negatif = kandidat digusur (skor, tanpa satuan)
            rekomendasi = "Kandidat digusur gugus hidrofobik ligan; perlu dipastikan dengan MD/MM-GBSA"
        else:
            kat = "Netral / Pelarut Terbuka"
            dg_gusur = 0.0
            rekomendasi = "Pengaruh substitusi moderat"

        hasil.append({
            "id": w["id"],
            "pos": {"x": round(pos_w[0], 2), "y": round(pos_w[1], 2), "z": round(pos_w[2], 2)},
            "n_hbond": n_hb,
            "n_kontak_c": n_c,
            "kategori": kat,
            "skor_gusur": dg_gusur,
            "dg_gusur": dg_gusur,          # nama lama, dipertahankan agar skrip lama tetap jalan
            "rekomendasi": rekomendasi,
            "residu_tetangga": residu_dekat,
        })

    # Urutkan berdasarkan potensi peningkatan afinitas (dg_gusur paling negatif)
    hasil.sort(key=lambda x: x["dg_gusur"])
    return hasil
