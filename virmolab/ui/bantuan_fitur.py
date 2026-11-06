"""Bantuan kontekstual: dari dialog fitur langsung ke bagian panduan yang membahasnya.

Tanpa ini F1 selalu membuka panduan dari halaman awal, dan pengguna yang berhenti di satu dialog harus
mencari sendiri bagiannya di dokumen 25 bagian. Pemetaannya satu arah dan sengaja berupa data: kelas
dialog tidak perlu tahu apa pun tentang dokumentasi.
"""

# nama kelas dialog -> (berkas panduan, anchor). Anchor mengacu ke id <h2>/<h3> di docs/_sumber/panduan.html.
PETA = {
    "DialogAdmet": ("panduan", "peta-tubuh"),
    "DialogAsisten": ("panduan", "interpretasi"),
    "DialogFarmakofor": ("panduan", "farmakofor"),
    "DialogFarmakologi": ("panduan", "farmakologi"),
    "DialogFBDD": ("panduan", "fbdd"),
    "DialogGeneratif": ("panduan", "generatif"),
    "DialogGlikosida": ("panduan", "glikosida"),
    "DialogKantong": ("panduan", "kantong-geo"),
    "DialogKemiripan": ("panduan", "mmp"),
    "DialogKinetika": ("panduan", "kinetika"),
    "DialogKomposer": ("panduan", "komposer"),
    "DialogKonsensus": ("panduan", "konsensus"),
    "DialogKovalen": ("panduan", "area"),
    "DialogLabPlanner": ("panduan", "lab"),
    "DialogLigan": ("panduan", "ligan"),
    "DialogMD": ("panduan", "md"),
    "DialogMetabolisme": ("panduan", "metabolisme"),
    "DialogMMP": ("panduan", "mmp"),
    "DialogMPO": ("panduan", "mpo"),
    "DialogPembelajaranAktif": ("panduan", "penapisan-bertahap"),
    "DialogPenapisan": ("panduan", "penapisan"),
    "DialogPenelitian": ("panduan", "hipotesis"),
    "DialogPeptida": ("panduan", "peptida"),
    "DialogPPI": ("panduan", "ppi"),
    "DialogPROTAC": ("panduan", "protac"),
    "DialogQSAR": ("panduan", "qsar"),
    "DialogRbfe": ("panduan", "rbfe"),
    "DialogReseptor": ("panduan", "protein"),
    "DialogSelektivitas": ("panduan", "selektivitas"),
    "DialogSkripPublikasi": ("panduan", "skrip-figur"),
    "DialogSunting3D": ("panduan", "sunting-kantong-3d"),
    "DialogTargetBalik": ("panduan", "target-balik"),
    "DialogTerowongan": ("panduan", "saluran"),
    "DialogValidasiProtokol": ("panduan", "validasi-protokol"),
    "DialogXtb": ("panduan", "xtb"),
    "DialogRescoreML": ("panduan", "konsensus"),
    "DialogLapor": ("panduan", "ekspor"),
    "DialogEkspor": ("panduan", "ekspor"),
    "DialogFleksibel": ("panduan", "area"),
    "DialogAlatWsl": ("instalasi", "alat-lanjutan"),
    "DialogPengaturan": ("panduan", "privasi"),
}

# Daftar untuk submenu Bantuan › Panduan fitur: (judul tampil, berkas, anchor).
# Satu baris per fitur, supaya panduan tiap alat dapat dibuka tanpa membuka dialognya lebih dulu.
DAFTAR = [
    ("Deteksi kantong pengikatan", "panduan", "kantong-geo"),
    ("Saluran akses ligan", "panduan", "saluran"),
    ("Residu fleksibel & docking kovalen", "panduan", "area"),
    ("Kontak atom pose", "panduan", "kontak-pose"),
    ("Validasi protokol docking", "panduan", "validasi-protokol"),
    ("Konsensus skor", "panduan", "konsensus"),
    ("Sifat ligan & BOILED-Egg", "panduan", "sifat"),
    ("Peta organ ADMET", "panduan", "peta-tubuh"),
    ("Optimasi multi-parameter (MPO)", "panduan", "mpo"),
    ("Titik metabolisme CYP450", "panduan", "metabolisme"),
    ("Kinetika dan waktu tinggal", "panduan", "kinetika"),
    ("Sifat elektronik (xTB)", "panduan", "xtb"),
    ("Pasangan molekul berpadanan (MMP)", "panduan", "mmp"),
    ("Desain berbasis fragmen (FBDD)", "panduan", "fbdd"),
    ("Perancang PROTAC", "panduan", "protac"),
    ("Penapisan farmakofor & bentuk 3D", "panduan", "farmakofor"),
    ("QSAR & model prediksi", "panduan", "qsar"),
    ("Desain generatif", "panduan", "generatif"),
    ("Sunting di kantong (3D)", "panduan", "sunting-kantong-3d"),
    ("Glikosida dan aglikon", "panduan", "glikosida"),
    ("Dasbor penapisan virtual", "panduan", "penapisan"),
    ("Penapisan pustaka besar (pembelajaran aktif)", "panduan", "penapisan-bertahap"),
    ("Penargetan balik", "panduan", "target-balik"),
    ("Jaringan & jalur", "panduan", "jaringan-jalur"),
    ("Konservasi residu kantong", "panduan", "konservasi"),
    ("Selektivitas multi-target", "panduan", "selektivitas"),
    ("Antarmuka protein–protein (PPI)", "panduan", "ppi"),
    ("Farmakologi jaringan (7 tahap)", "panduan", "farmakologi"),
    ("Docking peptida", "panduan", "peptida"),
    ("Co-folding Boltz-2", "panduan", "kofolding"),
    ("Energi bebas relatif (RBFE)", "panduan", "rbfe"),
    ("MD & MM/GBSA", "panduan", "md"),
    ("Rencana uji lab basah", "panduan", "lab"),
    ("Pelacak hipotesis", "panduan", "hipotesis"),
    ("Interpretasi hasil docking", "panduan", "interpretasi"),
    ("Skrip figur publikasi", "panduan", "skrip-figur"),
    ("Komposer figur", "panduan", "komposer"),
    ("Ekspor & laporan", "panduan", "ekspor"),
]


def untuk(dialog):
    """(berkas, anchor) untuk sebuah dialog, atau None bila belum dipetakan."""
    return PETA.get(type(dialog).__name__)
