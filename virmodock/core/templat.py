"""Templat proyek & proyek contoh (rencana A9/B4): titik mulai siap pakai untuk alur docking yang umum.

Tiap templat = preset parameter + dialog langkah pertama + daftar langkah (ditulis ke panel Pesan dan disimpan di
proyek.templat). Proyek contoh HIV-1 protease bisa dibuka sepenuhnya offline: 1HSG (RCSB PDB, CC0) dibundel dan
SMILES inhibitor diambil dari pustaka obat disetujui (ChEMBL, dibundel).
"""
from .paths import PAKET

CONTOH_PDB = PAKET / "aset" / "contoh" / "1HSG.pdb"
CONTOH_HOMOLOG = PAKET / "aset" / "contoh" / "1HSG_homolog.fasta"
# nama persis di pustaka obat disetujui (aset/obat_disetujui.tsv.gz)
INHIBITOR_HIV = ["Saquinavir", "Ritonavir", "Indinavir Anhydrous", "Nelfinavir", "Amprenavir", "Lopinavir",
                 "Atazanavir", "Tipranavir", "Darunavir"]
KONTROL_NEGATIF = ("Aspirin", "CC(=O)Oc1ccccc1C(=O)O")

TEMPLAT = [
    {"kunci": "contoh", "judul": "Contoh: HIV-1 protease (offline)", "preset": "Standar",
     "ket": "1HSG + 9 inhibitor protease yang disetujui + aspirin sebagai kontrol negatif. Untuk latihan tanpa internet.",
     "langkah": ["Redocking buta MK1 yang sudah diukur (dari SMILES, Vina exhaustiveness 16, seed 42): "
                 "RMSD 1,39 Å, ΔG −11,18 kcal/mol, GNINA Affinity −11,56 kcal/mol. "
                 "Angka ini bukan docking baru di proyek ini.",
                 "Protein 1HSG dan 10 ligan sudah dimuat; grid box otomatis di ligan kristal MK1.",
                 "Langkah 1: Siapkan reseptor (PROPKA pH 7,4 disarankan).",
                 "Langkah 2: Siapkan ligan (semua 10 ligan).",
                 "Langkah 4: Jalankan docking (AD-GPU bila ada GPU).",
                 "Bandingkan: inhibitor seharusnya ΔG jauh lebih negatif daripada aspirin.",
                 "Opsional: Docking › Validasi redocking (MK1) dan Analisis › MD & MM/GBSA untuk 3 teratas."]},
    {"kunci": "satu", "judul": "Docking satu ligan", "preset": "Standar",
     "ket": "Satu protein + satu ligan, ketelitian Standar, lengkap dengan validasi dan analisis interaksi.",
     "langkah": ["Ambil protein (RCSB PDB / AlphaFold DB) lalu Siapkan reseptor.",
                 "Ambil ligan (PubChem / SMILES / Ketcher) lalu Siapkan ligan.",
                 "Atur grid box (ligan asli, residu, atau Deteksi kantong).",
                 "Jalankan docking; periksa pose, interaksi 3D/2D, dan PoseBusters.",
                 "Bila ada ligan kristal: Docking › Validasi redocking (RMSD ≤ 2 Å)."]},
    {"kunci": "skrining", "judul": "Virtual screening", "preset": "Cepat",
     "ket": "Banyak ligan (pustaka obat, COCONUT, berkas SDF), ketelitian Cepat, lalu penyempurnaan teratas.",
     "langkah": ["Ambil protein lalu Siapkan reseptor; atur grid box.",
                 "Ambil ligan: Siapkan › Pustaka ligan (obat disetujui / COCONUT) atau Buka berkas SDF.",
                 "Siapkan ligan (batch) lalu jalankan docking dengan preset Cepat.",
                 "Urutkan hasil; docking ulang 10-20 teratas dengan preset Teliti atau mesin lain.",
                 "Konsensus skor dan MD & MM/GBSA (tingkat Ringan) untuk teratas; periksa sifat ligan/ADMET."]},
    {"kunci": "redocking", "judul": "Validasi redocking", "preset": "Standar",
     "ket": "Membuktikan protokol docking mampu mengulang pose kristal (RMSD ≤ 2 Å) sebelum dipakai untuk ligan uji.",
     "langkah": ["Ambil struktur kompleks protein-ligan dari RCSB PDB (pakai saran ★ di pencarian).",
                 "Siapkan reseptor (ligan asli otomatis dihapus dari reseptor).",
                 "Grid box: Pusat di ligan asli.",
                 "Docking › Validasi redocking: ligan kristal didocking ulang lalu RMSD dihitung.",
                 "Laporkan RMSD di metode; bila > 2 Å, ubah ukuran kotak/ketelitian lalu ulangi."]},
    {"kunci": "pembanding", "judul": "Perbandingan dengan obat standar", "preset": "Standar",
     "ket": "Ligan uji dibandingkan dengan obat standar/ligan kristal pada protokol yang sama.",
     "langkah": ["Ambil protein lalu Siapkan reseptor; atur grid box di ligan asli.",
                 "Tambahkan obat standar: Siapkan › Pustaka ligan › Obat disetujui (cari nama obat).",
                 "Tambahkan ligan uji (PubChem/SMILES/berkas).",
                 "Siapkan semua ligan lalu jalankan docking dalam satu job.",
                 "Bandingkan ΔG, LE, dan pola interaksi (Bandingkan ligan, peta IFP); uji statistik bila ada replikasi."]},
    {"kunci": "repurposing", "judul": "Repurposing obat", "preset": "Cepat",
     "ket": "Mendocking obat yang sudah disetujui ke target baru, lalu memeringkat dan membandingkan dengan data ChEMBL.",
     "langkah": ["Ambil protein target lalu Siapkan reseptor; atur grid box (ligan asli atau Deteksi kantong).",
                 "Siapkan › Pustaka ligan › Obat disetujui: saring (mis. rute oral), centang semua, Impor.",
                 "Siapkan ligan lalu jalankan docking preset Cepat (AD-GPU; ±1-3 detik per ligan dengan GPU).",
                 "Docking ulang 20 teratas dengan preset Teliti; MD & MM/GBSA tingkat Ringan untuk 10 teratas.",
                 "Analisis › Korelasi dengan data eksperimen (ChEMBL) untuk aktivitas yang sudah diketahui."]},
    {"kunci": "bahan_alam", "judul": "Bahan alam dari satu kelompok", "preset": "Cepat",
     "ket": "Senyawa bahan alam (COCONUT) disaring lalu didocking ke satu protein, dengan obat standar sebagai pembanding.",
     "langkah": ["Ambil protein target lalu Siapkan reseptor; atur grid box di ligan asli atau kantong.",
                 "Siapkan › Pustaka ligan › COCONUT: saring kemiripan atau sifat, impor puluhan senyawa.",
                 "Tambahkan satu obat standar dari pustaka obat disetujui sebagai pembanding.",
                 "Siapkan ligan, jalankan docking preset Cepat, lalu ulang 15 teratas dengan preset Teliti.",
                 "Analisis › Penelitian lanjutan: regangan pose, energi per residu, dan draf skripsi."]},
]


def cari(kunci):
    return next((t for t in TEMPLAT if t["kunci"] == kunci), None)


def ligan_contoh():
    """[(nama, smiles)] 9 inhibitor HIV-1 protease (pustaka offline) + kontrol negatif."""
    from . import pustaka
    obat = {o["nama"]: o["smiles"] for o in pustaka.obat()}
    out = []
    for n in INHIBITOR_HIV:
        if obat.get(n):
            out.append((n.replace(" Anhydrous", ""), obat[n]))
    out.append(KONTROL_NEGATIF)
    return out
