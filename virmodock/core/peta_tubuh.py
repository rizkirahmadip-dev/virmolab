"""Peta tubuh ADMET: mengelompokkan prediksi ADMET-AI menjadi penilaian per organ.

Tiap organ hanya memakai endpoint yang benar-benar ada di `core/admet.py`. Organ yang tidak punya model sama sekali
(paru, pankreas, dan sebagainya) tidak dibuat-buat — ditandai "tidak ada model" supaya petanya tetap jujur.

Skor organ 0–100: makin tinggi makin menguntungkan (hijau). Untuk endpoint probabilitas, nilainya diambil langsung
(dibalik bila arahnya merugikan). Untuk endpoint regresi (jam, L/kg, log) dipakai fungsi kelayakan sederhana yang
rentangnya tertulis di tabel di bawah — bukan ambang resmi, melainkan patokan kasar agar warnanya bisa dibandingkan.

Catatan: semua angka adalah prediksi model pembelajaran mesin (Chemprop-RDKit, dataset TDC), bukan hasil uji.
"""
from typing import Any, Dict, List, Optional

from .admet import LABEL, SIFAT

# rentang kelayakan endpoint non-probabilitas: (nilai_skor_0, nilai_skor_1) — di antaranya ditarik lurus
RENTANG = {
    "Caco2_Wang": (-6.5, -4.7),                 # log cm/s: < −6,5 buruk, > −4,7 baik
    "Solubility_AqSolDB": (-6.0, -2.0),         # log mol/L
    "Lipophilicity_AstraZeneca": (5.5, 2.0),    # logD: makin rendah makin aman (dibalik)
    "PPBR_AZ": (99.5, 85.0),                    # % terikat: sangat tinggi menyulitkan (dibalik)
    "VDss_Lombardo": (0.04, 0.7),               # L/kg
    "Half_Life_Obach": (0.5, 8.0),              # jam
    "Clearance_Hepatocyte_AZ": (120.0, 10.0),   # µL/min/10⁶ sel: tinggi = cepat habis (dibalik)
    "Clearance_Microsome_AZ": (80.0, 5.0),      # mL/min/g (dibalik)
    "LD50_Zhu": (1.5, 3.5),                     # −log mol/kg: makin besar makin aman
}

# organ -> (label, endpoint penentu, keterangan singkat, posisi relatif di siluet 0–1)
ORGAN = [
    ("otak", "Otak dan sistem saraf", ["BBB_Martins"],
     "Peluang menembus sawar darah otak. Baik untuk target saraf, risiko efek pusat untuk target perifer.",
     (0.50, 0.072)),
    ("jantung", "Jantung", ["hERG"],
     "Penghambatan kanal hERG, penanda utama risiko pemanjangan QT.", (0.455, 0.285)),
    ("hati", "Hati", ["DILI", "Clearance_Hepatocyte_AZ", "Half_Life_Obach", "CYP3A4_Veith", "CYP2D6_Veith",
                      "CYP2C9_Veith", "CYP1A2_Veith", "CYP2C19_Veith"],
     "Cedera hati, kecepatan pembersihan, dan penghambatan enzim CYP (sumber interaksi antarobat).",
     (0.565, 0.375)),
    ("cerna", "Saluran cerna", ["HIA_Hou", "Bioavailability_Ma", "Caco2_Wang", "PAMPA_NCATS",
                                "Solubility_AqSolDB", "Pgp_Broccatelli"],
     "Penyerapan di usus: permeabilitas, kelarutan, dan pengaruh pompa P-gp.", (0.50, 0.475)),
    ("ginjal", "Ginjal dan pembuangan", ["Clearance_Microsome_AZ", "VDss_Lombardo", "PPBR_AZ"],
     "Laju pembersihan mikrosom, sebaran ke jaringan, dan ikatan protein plasma. "
     "Tidak ada model transporter ginjal (OCT2) di VirmoLab.", (0.50, 0.565)),
    ("kulit", "Kulit", ["Skin_Reaction"], "Peluang reaksi kulit (sensitisasi).", (0.305, 0.30)),
    ("sel", "Inti sel dan genotoksisitas", ["AMES", "Carcinogens_Lagunin", "SR-p53", "NR-AhR"],
     "Mutagenisitas Ames, karsinogenisitas, respons stres p53, dan reseptor AhR (panel Tox21).", (0.695, 0.30)),
    ("sistemik", "Seluruh tubuh", ["LD50_Zhu", "ClinTox", "Lipophilicity_AstraZeneca"],
     "Toksisitas akut, riwayat kegagalan uji klinis karena toksisitas, dan lipofilisitas keseluruhan.",
     (0.50, 0.685)),
]
TANPA_MODEL = [("paru", "Paru"), ("pankreas", "Pankreas"), ("tiroid", "Tiroid")]
# urutan perjalanan obat untuk animasi: saluran cerna -> darah -> hati -> ginjal
ALUR = ["cerna", "hati", "ginjal"]


def _skor_endpoint(kunci: str, nilai: Optional[float]) -> Optional[float]:
    """Skor 0–1 (1 = menguntungkan) untuk satu endpoint, atau None bila nilainya tidak ada."""
    if nilai is None:
        return None
    _k, _label, _kel, jenis, arah = next(x for x in SIFAT if x[0] == kunci)
    if jenis == "p":
        if arah == 0:                      # netral (mis. BBB, substrat CYP): tidak ikut menilai baik/buruk
            return None
        return float(nilai) if arah > 0 else 1.0 - float(nilai)
    batas = RENTANG.get(kunci)
    if not batas:
        return None
    nol, satu = batas
    if satu == nol:
        return None
    return max(0.0, min(1.0, (float(nilai) - nol) / (satu - nol)))


def status(skor: Optional[float]) -> str:
    """'baik' | 'sedang' | 'risiko' | 'kosong' dari skor 0–100."""
    if skor is None:
        return "kosong"
    if skor >= 70:
        return "baik"
    if skor >= 40:
        return "sedang"
    return "risiko"


SINGKAT = {"otak": "Otak", "jantung": "Jantung", "hati": "Hati", "cerna": "Saluran cerna", "ginjal": "Ginjal",
           "kulit": "Kulit", "sel": "Inti sel", "sistemik": "Seluruh tubuh"}


def nilai_organ(hasil: Dict[str, Any]) -> List[Dict[str, Any]]:
    """[{kunci, nama, skor, status, keterangan, posisi, endpoint:[{kunci,label,nilai,skor,netral}]}] per organ.

    `hasil` = satu baris prediksi ADMET-AI ({kolom: nilai}). Organ tanpa satu pun nilai → skor None.
    """
    keluar = []
    for kunci, nama, endpoint, keterangan, posisi in ORGAN:
        rinci, skor_ada = [], []
        for k in endpoint:
            v = hasil.get(k) if hasil else None
            s = _skor_endpoint(k, v)
            rinci.append({"kunci": k, "label": LABEL.get(k, k), "nilai": v, "skor": s, "netral": s is None})
            if s is not None:
                skor_ada.append(s)
        skor = round(100.0 * (sum(skor_ada) / len(skor_ada)), 1) if skor_ada else None
        # satu endpoint sangat buruk tidak boleh tersamarkan rata-rata: skor organ dibatasi oleh yang terburuk + 20
        if skor is not None and skor_ada:
            skor = round(min(skor, 100.0 * min(skor_ada) + 20.0), 1)
        # organ yang endpoint-nya netral (mis. BBB) tetap menampilkan angkanya sebagai informasi, bukan risiko
        info = None
        if skor is None:
            ada = [e for e in rinci if e["nilai"] is not None]
            if ada:
                info = f"{ada[0]['nilai']:.2f}".replace(".", ",")
        keluar.append({"kunci": kunci, "nama": nama, "singkat": SINGKAT.get(kunci, nama),
                       "skor": skor, "status": status(skor), "info": info,
                       "keterangan": keterangan, "posisi": posisi, "endpoint": rinci})
    return keluar


def ringkas(organ: List[Dict[str, Any]]) -> str:
    """Satu kalimat: organ paling berisiko, atau pernyataan bahwa tidak ada yang menonjol."""
    dinilai = [o for o in organ if o["skor"] is not None]
    if not dinilai:
        return "Belum ada prediksi ADMET untuk ligan ini."
    buruk = sorted(dinilai, key=lambda o: o["skor"])[:2]
    if buruk[0]["skor"] >= 70:
        return "Tidak ada organ yang menonjol berisiko pada prediksi ini."
    nama = " dan ".join(o["nama"].lower() for o in buruk if o["skor"] < 70)
    return f"Perhatian terbesar pada {nama}; buka organnya untuk melihat endpoint penyebabnya."


def waktu_alur(hasil: Dict[str, Any]) -> float:
    """Lama satu putaran animasi perjalanan obat (detik), mengikuti waktu paruh prediksi (3–12 detik)."""
    t = (hasil or {}).get("Half_Life_Obach")
    if t is None:
        return 6.0
    return max(3.0, min(12.0, 3.0 + float(t) * 0.6))
