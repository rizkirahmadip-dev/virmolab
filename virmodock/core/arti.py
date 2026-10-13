"""Arti angka yang tampil di aplikasi, laporan, dan draf skripsi.

Satuan tidak boleh tertukar: CNNaffinity bukan kcal/mol, skor kovalen bukan ΔG eksperimen,
dan RMSD Boltz hanya sah setelah struktur disejajarkan.
"""

BUTIR = (
    ("ΔG Vina, Vinardo, atau AutoDock", "kcal/mol",
     "Perkiraan fungsi skor itu. Makin negatif, makin disukai fungsi skor. Bukan ΔG eksperimen."),
    ("Skor kovalen", "kcal/mol",
     "Energi aduk terhadap reseptor pada metode tethered. Bukan ΔG ikatan. "
     "Bandingkan hanya antar-ligan kovalen pada residu yang sama."),
    ("Ki perkiraan", "konsentrasi",
     "Dihitung dari ΔG fungsi skor. Kosong pada docking kovalen. Bukan Ki laboratorium."),
    ("GNINA Affinity", "kcal/mol",
     "Skor ulang pada pose yang sudah ada. Bukan pencarian pose baru."),
    ("CNNscore", "0-1",
     "Keyakinan model bahwa pose itu mirip pose yang disukai. Bukan energi."),
    ("CNNaffinity", "pK",
     "Perkiraan afinitas model CNN. Bukan kcal/mol."),
    ("RMSD redocking", "Å",
     "Jarak pose hasil pencarian terhadap ligan kristal, dalam kerangka koordinat yang sama. "
     "Di bawah atau sama dengan 2 Å dianggap lolos."),
    ("RMSD Boltz", "Å",
     "Hanya sah setelah struktur prediksi disejajarkan ke kristal. "
     "Tanpa penjajaran, angka itu hanya selisih kerangka koordinat."),
    ("MM/GBSA", "kcal/mol",
     "Energi setelah minimisasi. Bukan skor docking, dan entropi tidak dihitung."),
)


def paragraf():
    """Satu blok teks untuk draf dan catatan."""
    return "\n".join(f"- {nama} ({satuan}): {makna}" for nama, satuan, makna in BUTIR)


def html():
    return " ".join(f"<b>{nama}</b> ({satuan}): {makna}" for nama, satuan, makna in BUTIR)


def arti_skor(kovalen):
    if kovalen:
        return BUTIR[1][0] + " (" + BUTIR[1][1] + "): " + BUTIR[1][2]
    return BUTIR[0][0] + " (" + BUTIR[0][1] + "): " + BUTIR[0][2]


CATATAN_GNINA = (
    "Affinity dalam kcal/mol. CNNscore antara 0 dan 1 (bukan energi). "
    "CNNaffinity dalam satuan pK, bukan kcal/mol."
)
CATATAN_BOLTZ = (
    "RMSD terhadap kristal hanya sah setelah kedua struktur disejajarkan. "
    "Tanpa penjajaran, angka itu hanya selisih kerangka koordinat."
)

# Petunjuk kolom tab Hasil, indeks mengikuti panel_hasil.KOLOM.
PETUNJUK_KOLOM = {
    2: arti_skor(False) + " Pada baris docking kovalen, angka ini adalah skor aduk, bukan ΔG.",
    3: BUTIR[2][0] + ": " + BUTIR[2][2],
    4: "Efisiensi ligan: minus ΔG dibagi jumlah atom berat. Kosong pada docking kovalen.",
    6: BUTIR[6][0] + " (" + BUTIR[6][1] + "): " + BUTIR[6][2],
    16: BUTIR[8][0] + " (" + BUTIR[8][1] + "): " + BUTIR[8][2],
    17: BUTIR[3][0] + " (" + BUTIR[3][1] + "): " + BUTIR[3][2],
    18: BUTIR[4][0] + " (" + BUTIR[4][1] + "): " + BUTIR[4][2],
    19: BUTIR[5][0] + " (" + BUTIR[5][1] + "): " + BUTIR[5][2],
    20: "Jarak terdekat (Å) atom berat pose ke salah satu residu yang disyaratkan. "
         "Baris ligan memakai pose berenergi terbaik yang lolos. Pose lain tetap di bawahnya. "
         "Pencarian docking tidak dipaksa mendekat. Sel kosong berarti syarat belum diatur.",
}

POLA_GALAT_EDUKATIF = [
    (r"outside receptor|grid.*outside|di luar reseptor",
     "Pusat atau batas kotak area docking (grid box) berada di luar batas koordinat struktur protein.",
     "Klik tombol 'Kotak ke ligan' atau 'Deteksi kantong (P2Rank)' di panel langkah untuk memusatkan kotak ke kantong aktif."),
    (r"atom type.*not supported|unknown element|tipe atom tidak didukung",
     "Ligan mengandung tipe atom atau unsur yang tidak memiliki parameter medan gaya baku di AutoDock4/Vina.",
     "Periksa rumus molekul ligan, pastikan atom organik baku (C, H, N, O, S, P, halogen), atau gunakan mesin AutoDock-GPU."),
    (r"CUDA out of memory|CL_MEM_OBJECT_ALLOCATION_FAILURE|out of memory|kehabisan memori",
     "Memori video GPU (VRAM) penuh saat mengalokasikan peta grid docking.",
     "Tutup aplikasi grafis lain, perkecil ukuran kotak grid, atau alihkan mesin docking ke AutoDock Vina (CPU)."),
    (r"no polar hydrogens|tidak ada hidrogen",
     "Struktur protein reseptor belum memiliki atom hidrogen polar yang diperlukan untuk perhitungan ikatan hidrogen.",
     "Jalankan langkah 'Preparasi Reseptor' (pilih templat baku atau PROPKA) sebelum menjalankan penambatan."),
    (r"failed to embed|konformasi 3D gagal",
     "Algoritma pembangun konformasi 3D (ETKDG) tidak dapat menghasilkan koordinat berjarak realistis untuk molekul ini.",
     "Periksa valensi kimiawi struktur SMILES ligan atau aktifkan opsi koordinat acak."),
    (r"vina.exe tidak ada|autodock.*tidak ditemukan",
     "Biner mesin docking tidak ditemukan di folder instalasi atau PATH sistem.",
     "Jalankan menu Alat › Uji mandiri komponen atau unduh ulang paket biner dari menu Bantuan."),
    (r"Permission denied|akses ditolak",
     "VirmoLab tidak memiliki izin untuk menulis berkas ke folder kerja yang dipilih.",
     "Simpan proyek di folder dengan izin tulis penuh pengguna (misal Dokumen atau folder kerja lokal, bukan Program Files)."),
]


def edukasi_galat(teks: str) -> str:
    """Ubah galat teknis mentah menjadi format edukatif berorientasi solusi (Penyebab + Tindakan)."""
    if not teks:
        return ""
    import re
    t = str(teks).strip()
    for pola, sebab, solusi in POLA_GALAT_EDUKATIF:
        if re.search(pola, t, re.IGNORECASE):
            return f"{t}\n\n💡 Penyebab: {sebab}\n🛠 Tindakan: {solusi}"
    return t
