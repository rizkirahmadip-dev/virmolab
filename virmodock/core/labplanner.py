"""Kalkulator Perencanaan Uji Laboratorium Basah (Wet-Lab Planner).

Menjembatani hasil penambatan molekuler (in silico) ke protokol eksperimen in vitro:
1. Konversi ΔG docking ke prediksi Ki dan perkiraan IC50.
2. Perhitungan seri pengenceran bertingkat (serial dilution).
3. Kalkulasi batas toleransi pelarut DMSO dan volume pemipetan mikro.
4. Pemetaan denah pelat mikro (96-well / 384-well / 48-well / 24-well) dengan replikasi
   (triplo/duplo) serta kontrol positif, kendali pelarut, dan blanko.
5. Panduan protokol pemipetan langkah-demi-langkah siap cetak.
"""
import math
from typing import Any, Dict, List, Optional, Tuple

R_KAL = 1.987207e-3   # kcal / (mol * K)
SUHU_K = 298.15       # 25 °C


def prediksi_ki_ic50(dg_kkal: float, km_uM: Optional[float] = None, s_uM: Optional[float] = None) -> Dict[str, Any]:
    """Hitung prediksi Ki dan IC50 perkiraan dari skor docking ΔG (kcal/mol).

    Ki = exp(ΔG / (R * T)) = 10^(ΔG / -1.364) molar.
    IC50 = Ki * (1 + [S] / Km) menurut persamaan Cheng-Prusoff (bila [S] = Km -> IC50 ~ 2 * Ki).
    """
    if dg_kkal is None or dg_kkal >= 0:
        return {"ki_M": None, "ki_uM": None, "ki_teks": "-", "ic50_uM": None, "ic50_teks": "-"}

    ki_M = math.exp((dg_kkal) / (R_KAL * SUHU_K))
    ki_uM = ki_M * 1e6

    # Format teks Ki terbaca
    if ki_M < 1e-9:
        ki_teks = f"{ki_M * 1e12:.2f} pM"
    elif ki_M < 1e-6:
        ki_teks = f"{ki_M * 1e9:.2f} nM"
    elif ki_M < 1e-3:
        ki_teks = f"{ki_M * 1e6:.2f} μM"
    else:
        ki_teks = f"{ki_M * 1e3:.2f} mM"

    # IC50 Cheng-Prusoff
    faktor_cp = (1.0 + (s_uM / km_uM)) if (km_uM and s_uM and km_uM > 0) else 2.0
    ic50_uM = ki_uM * faktor_cp
    ic50_M = ki_M * faktor_cp

    if ic50_M < 1e-9:
        ic50_teks = f"{ic50_M * 1e12:.2f} pM"
    elif ic50_M < 1e-6:
        ic50_teks = f"{ic50_M * 1e9:.2f} nM"
    elif ic50_M < 1e-3:
        ic50_teks = f"{ic50_M * 1e6:.2f} μM"
    else:
        ic50_teks = f"{ic50_M * 1e3:.2f} mM"

    return {
        "ki_M": ki_M,
        "ki_uM": ki_uM,
        "ki_teks": ki_teks,
        "ic50_uM": ic50_uM,
        "ic50_teks": ic50_teks,
        "faktor_cp": faktor_cp,
    }


def hitung_seri_konsentrasi(kons_maks_uM: float, faktor_pengenceran: float = 3.0,
                            jumlah_titik: int = 8, mode: str = "faktor") -> List[float]:
    """Hasilkan daftar konsentrasi uji (μM) berurutan dari tertinggi ke terendah."""
    if mode == "semi_log":
        # Seri semi-logaritmik standar (1000, 300, 100, 30, 10, 3, 1, 0.3, ...)
        dasar = [1000.0, 300.0, 100.0, 30.0, 10.0, 3.0, 1.0, 0.3, 0.1, 0.03]
        # Cari titik awal terdekat dengan kons_maks
        titik_awal = min(dasar, key=lambda x: abs(x - kons_maks_uM))
        idx = dasar.index(titik_awal)
        return dasar[idx:idx + jumlah_titik]

    seri = []
    c = float(kons_maks_uM)
    for _ in range(jumlah_titik):
        seri.append(round(c, 4))
        c /= faktor_pengenceran
    return seri


def buat_protokol_pipet(stok_mM: float, seri_kons_uM: List[float], volume_sumur_uL: float = 100.0,
                        dmso_maks_persen: float = 0.5) -> Dict[str, Any]:
    """Hitung skema pengenceran bertingkat dan volume pemipetan.

    Standar industri:
    1. Buat intermediate working stock (misal 200x) dalam DMSO sehingga penambahan
       ke sumur (0.5% volume) langsung menghasilkan DMSO 0.5%.
    2. Atau pengenceran 2 langkah (stok DMSO -> larutan antara dalam buffer -> sumur uji).
    """
    stok_uM = stok_mM * 1000.0
    c_maks = seri_kons_uM[0]

    # Faktor konsentrasi di sumur (100% / DMSO%)
    # Contoh jika DMSO maks = 0.5%, maka larutan senyawa ditambahkan sebesar 0.5% volume sumur
    # (misal 0.5 μL per 100 μL sumur, atau larutan antara 10x ditambahkan 10 μL per 100 μL sumur dengan DMSO 5%).
    vol_senyawa_uL = volume_sumur_uL * (dmso_maks_persen / 100.0)
    vol_buffer_uL = volume_sumur_uL - vol_senyawa_uL

    # Bila volume penambahan langsung terlalu kecil (< 1 μL), buat working stock 10x
    butuh_larutan_antara = vol_senyawa_uL < 1.0
    if butuh_larutan_antara:
        vol_tambah_sumur_uL = volume_sumur_uL * 0.10  # 10 μL per 100 μL (10x larutan kerja)
        vol_buffer_sumur_uL = volume_sumur_uL - vol_tambah_sumur_uL
        dmso_di_larutan_kerja = dmso_maks_persen * 10.0  # misal 5.0% DMSO
    else:
        vol_tambah_sumur_uL = vol_senyawa_uL
        vol_buffer_sumur_uL = vol_buffer_uL
        dmso_di_larutan_kerja = 100.0

    langkah_pipet = []
    # Seri pengenceran larutan kerja
    for i, c_target in enumerate(seri_kons_uM):
        c_kerja = c_target * (volume_sumur_uL / vol_tambah_sumur_uL)
        langkah_pipet.append({
            "titik": i + 1,
            "kons_sumur_uM": c_target,
            "kons_kerja_uM": round(c_kerja, 2),
            "vol_ke_sumur_uL": round(vol_tambah_sumur_uL, 2),
            "vol_buffer_sumur_uL": round(vol_buffer_sumur_uL, 2),
            "dmso_akhir_persen": dmso_maks_persen,
        })

    return {
        "stok_mM": stok_mM,
        "volume_sumur_uL": volume_sumur_uL,
        "dmso_maks_persen": dmso_maks_persen,
        "butuh_larutan_antara": butuh_larutan_antara,
        "vol_tambah_uL": vol_tambah_sumur_uL,
        "vol_buffer_uL": vol_buffer_sumur_uL,
        "langkah": langkah_pipet,
    }


def rancang_denah_pelat(format_pelat: str = "96",
                        daftar_sampel: Optional[List[Dict[str, Any]]] = None,
                        replikasi: int = 3) -> Dict[str, Any]:
    """Rancang denah penempatan sumur pada pelat mikro 96-well atau 384-well.

    format_pelat: '96' (8x12), '384' (16x24), '48' (6x8), '24' (4x6).
    replikasi: 3 (triplo) atau 2 (duplo).
    """
    dimensi = {
        "96": (8, 12, [chr(ord('A') + i) for i in range(8)], [str(i + 1) for i in range(12)]),
        "384": (16, 24, [chr(ord('A') + i) for i in range(16)], [str(i + 1) for i in range(24)]),
        "48": (6, 8, [chr(ord('A') + i) for i in range(6)], [str(i + 1) for i in range(8)]),
        "24": (4, 6, [chr(ord('A') + i) for i in range(4)], [str(i + 1) for i in range(6)]),
    }
    n_baris, n_kolom, label_baris, label_kolom = dimensi.get(format_pelat, dimensi["96"])

    grid = {}
    for r in label_baris:
        for c in label_kolom:
            pos = f"{r}{c}"
            grid[pos] = {
                "baris": r, "kolom": c, "jenis": "kosong",
                "label": "", "kons_uM": None, "warna": "#eef1f5"
            }

    # Penempatan kontrol standar pada kolom 12 (untuk 96-well) atau kolom terakhir
    kolom_ctrl = label_kolom[-1]
    # Blanko (B) di baris A-B
    for r in label_baris[:2]:
        grid[f"{r}{kolom_ctrl}"] = {
            "baris": r, "kolom": kolom_ctrl, "jenis": "blanko",
            "label": "Blanko", "kons_uM": 0.0, "warna": "#d6dbe3"
        }
    # Kontrol Negatif / Pelarut (VC) di baris C-E
    for r in label_baris[2:5]:
        grid[f"{r}{kolom_ctrl}"] = {
            "baris": r, "kolom": kolom_ctrl, "jenis": "pelarut",
            "label": "Veh (DMSO)", "kons_uM": 0.0, "warna": "#c4e7f7"
        }
    # Kontrol Positif / Inhibitor Acuan (PC) di baris F-H
    for r in label_baris[5:8]:
        grid[f"{r}{kolom_ctrl}"] = {
            "baris": r, "kolom": kolom_ctrl, "jenis": "kontrol_pos",
            "label": "Inhibitor Ref", "kons_uM": 10.0, "warna": "#f6c6c6"
        }

    # Penempatan sampel pengujian
    # Bila ada sampel dan seri konsentrasi:
    if daftar_sampel:
        cur_kolom_idx = 0
        # pastel: teks gelap tetap terbaca di atasnya, baik pada tema terang maupun gelap
        warna_palette = [
            "#bcd4f5", "#bfe6d2", "#f6e0b4", "#d9ccf2",
            "#f6c9db", "#bfe4ec", "#d8ead0", "#f3c6c6"
        ]

        for s_idx, smp in enumerate(daftar_sampel):
            nama_smp = smp.get("nama", f"Sampel {s_idx + 1}")
            seri_kons = smp.get("konsentrasi", [])
            w_base = warna_palette[s_idx % len(warna_palette)]

            # Isi tiap konsentrasi sebanyak `replikasi` sumur
            for k_idx, kons in enumerate(seri_kons):
                if k_idx >= len(label_baris):
                    break
                r_label = label_baris[k_idx]
                for rep in range(replikasi):
                    target_kolom_idx = cur_kolom_idx + rep
                    if target_kolom_idx >= len(label_kolom) - 1:  # jangan menimpa kolom kontrol
                        break
                    c_label = label_kolom[target_kolom_idx]
                    pos = f"{r_label}{c_label}"
                    grid[pos] = {
                        "baris": r_label,
                        "kolom": c_label,
                        "jenis": "sampel",
                        "sampel": nama_smp,
                        "label": f"{nama_smp}\n{kons:g} μM",
                        "kons_uM": kons,
                        "warna": w_base,
                    }
            cur_kolom_idx += replikasi
            if cur_kolom_idx >= len(label_kolom) - 1:
                break

    return {
        "format": format_pelat,
        "n_baris": n_baris,
        "n_kolom": n_kolom,
        "label_baris": label_baris,
        "label_kolom": label_kolom,
        "grid": grid,
    }


def buat_teks_protokol(nama_ligan: str, dg_kkal: float, ki_info: Dict[str, Any],
                       protokol: Dict[str, Any]) -> str:
    """Hasilkan teks draf protokol laboratorium terformat dalam Bahasa Indonesia."""
    lines = []
    lines.append(f"PROTOKOL PENGUJIAN IN VITRO (WET-LAB PLANNER)")
    lines.append(f"VirmoDock - Penambatan Molekuler ke Uji Laboratorium")
    lines.append("=" * 65)
    lines.append(f"Senyawa Uji     : {nama_ligan}")
    lines.append(f"Skor Docking ΔG : {dg_kkal:.2f} kcal/mol")
    lines.append(f"Prediksi Ki     : {ki_info['ki_teks']}")
    lines.append(f"Prediksi IC50   : {ki_info['ic50_teks']} (estimasi Cheng-Prusoff)")
    lines.append("-" * 65)
    lines.append("PARAMETER PENGUJIAN:")
    lines.append(f"- Konsentrasi Stok : {protokol['stok_mM']} mM dalam DMSO 100%")
    lines.append(f"- Volume Sumur     : {protokol['volume_sumur_uL']:.0f} μL")
    lines.append(f"- Batas DMSO Akhir : ≤ {protokol['dmso_maks_persen']:.1f}%")
    lines.append("-" * 65)
    lines.append("LANGKAH-LANGKAH PEMIPETAN SERI PENGENCERAN:")
    for lk in protokol["langkah"]:
        lines.append(
            f"Titik #{lk['titik']:2d} : Konsentrasi {lk['kons_sumur_uM']:8.4f} μM | "
            f"Pipet {lk['vol_ke_sumur_uL']:5.1f} μL larutan kerja ({lk['kons_kerja_uM']} μM) + "
            f"{lk['vol_buffer_sumur_uL']:5.1f} μL buffer reaksi"
        )
    lines.append("-" * 65)
    lines.append("KONTROL PENGUJIAN:")
    lines.append("- Kontrol Positif (PC) : Inhibitor pembanding / acuan standar.")
    lines.append(f"- Kendali Pelarut (VC) : Buffer + DMSO {protokol['dmso_maks_persen']:.1f}% tanpa senyawa.")
    lines.append("- Blanko (BLK)          : Buffer reaksi saja tanpa enzim / sel.")
    lines.append("=" * 65)
    return "\n".join(lines)
