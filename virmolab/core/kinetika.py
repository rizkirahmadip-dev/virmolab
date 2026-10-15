"""Prediksi Kinetika Pengikatan & Waktu Tinggal (Residence Time & k_off Estimator).

Memprediksi parameter kinetika interaksi obat-reseptor:
  - k_off (laju disosiasi, s^-1)
  - k_on (laju asosiasi, M^-1 s^-1)
  - Residence time (tau = 1 / k_off)
  - Waktu paruh kompleks obat-target (t_1/2 = ln(2) / k_off)
  - Klasifikasi kinetik (Transient, Moderate, Sustained/Long-Acting)
berdasarkan afinitas termodinamika (dG), ikatan hidrogen terlindung/terkubur,
kontak hidrofobik, dan fleksibilitas konformasi ligan.
"""
import math
from typing import Any, Dict


def estimasi_kinetika(
    energi_vina: float,
    jum_hbond_terkubur: int = 2,
    jum_kontak_hidrofobik: int = 12,
    n_rotatable: int = 4,
    suhu_kelvin: float = 310.15,
) -> Dict[str, Any]:
    """Hitung perkiraan kinetika pengikatan obat-target.
    
    Args:
        energi_vina: Energi afinitas docking Vina (kcal/mol, misal -9.5)
        jum_hbond_terkubur: Jumlah ikatan hidrogen yang terlindung dari pelarut
        jum_kontak_hidrofobik: Jumlah atom berat ligan yang kontak hidrofobik
        n_rotatable: Jumlah ikatan yang dapat berputar (rotatable bonds)
        suhu_kelvin: Suhu fisiologis (default 310.15 K / 37 °C)
        
    Returns:
        Kamus berisi parameter kinetika lengkap.
    """
    R = 1.987204e-3  # kcal / (mol * K)
    RT = R * suhu_kelvin

    # 1. Baseline Kd termodinamika dari delta G
    # Kd = exp(dG / RT) dalam Molar
    dG = min(-1.0, float(energi_vina))
    kd_molar = math.exp(dG / RT)
    
    # 2. Estimasi laju konon asosiasi (k_on)
    # Rerata k_on untuk molekul kecil yang berdifusi ke kantong protein berkisar 10^5 hingga 10^7 M^-1 s^-1
    # Dihambat sedikit oleh tingginya fleksibilitas konformasi ligan
    log_kon = 6.0 - 0.05 * min(15, n_rotatable)
    k_on = 10.0 ** log_kon  # M^-1 s^-1

    # 3. Estimasi laju disosiasi (k_off = Kd * k_on) yang dimodulasi barrier kinetik
    # Barrier disosiasi aktivasi (dG_ddagger) meningkat secara signifikan bila terdapat:
    # - Ikatan hidrogen terkubur yang terlindung dari molekul air (shielded H-bonds)
    # - Kantong hidrofobik tertutup
    faktor_hbond = 1.0 / (1.0 + 1.2 * jum_hbond_terkubur)
    faktor_hidrofobik = 1.0 / (1.0 + 0.08 * jum_kontak_hidrofobik)
    
    # Baseline k_off murni termodinamika
    k_off_dasar = kd_molar * k_on
    # Efek pelambatan disosiasi akibat shielded binding pocket
    k_off = max(1e-7, k_off_dasar * faktor_hbond * faktor_hidrofobik)

    # 4. Residence time tau (detik) dan Half-life t_1/2
    tau_detik = 1.0 / k_off
    t_setengah_detik = math.log(2.0) / k_off

    # Konversi waktu ke unit yang manusiawi
    def _format_waktu(detik: float) -> str:
        # Ligan transien bisa ber-τ di bawah satu milidetik; '0.0 detik' menyembunyikan besarnya.
        if detik < 1e-3:
            return f"{detik * 1e6:.1f} µs"
        if detik < 1:
            return f"{detik * 1e3:.1f} ms"
        if detik < 60:
            return f"{detik:.1f} detik"
        elif detik < 3600:
            return f"{detik / 60.0:.1f} menit"
        elif detik < 86400:
            return f"{detik / 3600.0:.1f} jam"
        else:
            return f"{detik / 86400.0:.1f} hari"

    # 5. Klasifikasi profil kinetik
    if tau_detik < 60:
        kategori = "Transient (Sangat Singkat)"
        penjelasan = "Ligan cepat lepas dari reseptor (< 1 menit). Rentan membutuhkan dosis tinggi untuk mempertahankan okupansi."
    elif tau_detik < 1800:
        kategori = "Moderate (Sedang)"
        penjelasan = "Waktu tinggal berkisar beberapa menit hingga setengah jam. Cocok untuk target fisiologis yang membutuhkan reversibilitas cepat."
    elif tau_detik < 14400:
        kategori = "Sustained / Long Residence Time (Panjang)"
        penjelasan = "Waktu tinggal > 30 menit hingga beberapa jam. Okupansi reseptor bertahan lama bahkan saat kadar obat di plasma mulai menurun."
    else:
        kategori = "Ultra-Sustained (Sangat Panjang / Pseudo-irreversible)"
        penjelasan = "Waktu tinggal berjam-jam hingga harian. Efek farmakodinamik berpotensi melampaui waktu paruh farmakokinetik (PK/PD decoupling)."

    return {
        "dG": round(dG, 2),
        "Kd_nM": round(kd_molar * 1e9, 2),
        "k_on": float(f"{k_on:.2e}"),
        "k_off": float(f"{k_off:.2e}"),
        "tau_detik": round(tau_detik, 2),
        "tau_teks": _format_waktu(tau_detik),
        "t_setengah_detik": round(t_setengah_detik, 2),
        "t_setengah_teks": _format_waktu(t_setengah_detik),
        "kategori": kategori,
        "penjelasan": penjelasan,
        "hbond_terkubur": jum_hbond_terkubur,
        "kontak_hidrofobik": jum_kontak_hidrofobik,
    }
