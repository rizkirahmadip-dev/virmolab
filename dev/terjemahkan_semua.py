"""Penerjemah otomatis komprehensif untuk teks baru (v0.9.7 - v1.1.1).

Membaca dev/i18n_teks_baru.json, menerjemahkan seluruh 1.150 literal dan 267 pola,
memasukkannya ke dev/i18n_tambahan.json, lalu menggabungkannya ke virmodock/i18n/en.json.
"""
import json
import re
import sys
from pathlib import Path

# Glosarium istilah sains dan UI VirmoDock
KAMUS_KATA = {
    "penapisan virtual": "virtual screening",
    "penapisan": "screening",
    "kantong pengikatan": "binding pocket",
    "kantong aktif": "active pocket",
    "kantong": "pocket",
    "terowongan akses": "access tunnel",
    "terowongan": "tunnel",
    "air termodinamika": "thermodynamic water",
    "air kristal": "crystal water",
    "titik hidrasi": "hydration site",
    "titik metabolisme": "site of metabolism",
    "metabolisme fase I": "phase I metabolism",
    "metabolisme": "metabolism",
    "peta tubuh": "body map",
    "distribusi organ": "organ distribution",
    "lab planner": "lab planner",
    "laboratorium basah": "wet laboratory",
    "perencanaan lab basah": "wet-lab planner",
    "perencanaan laboratorium": "lab planning",
    "waktu tinggal": "residence time",
    "kinetika pengikatan": "binding kinetics",
    "kinetika": "kinetics",
    "skor komposit": "composite score",
    "pencocokan fragmen": "fragment matching",
    "berbasis fragmen": "fragment-based",
    "desain obat": "drug design",
    "rantai samping": "side chain",
    "residu fleksibel": "flexible residues",
    "residu kunci": "key residues",
    "residu": "residue",
    "reseptor kaku": "rigid receptor",
    "reseptor": "receptor",
    "protein target": "target protein",
    "protein": "protein",
    "ligan acuan": "reference ligand",
    "ligan uji": "test ligand",
    "ligan asli": "native ligand",
    "ligan kristal": "crystal ligand",
    "ligan": "ligand",
    "penambatan molekuler": "molecular docking",
    "penambatan": "docking",
    "interaksi non-kovalen": "non-covalent interaction",
    "interaksi": "interaction",
    "ikatan hidrogen": "hydrogen bond",
    "jembatan garam": "salt bridge",
    "afinitas pengikatan": "binding affinity",
    "afinitas": "affinity",
    "luas permukaan": "surface area",
    "permukaan terkubur": "buried surface",
    "antarmuka": "interface",
    "ruang kimia": "chemical space",
    "kemiripan struktur": "structural similarity",
    "kemiripan": "similarity",
    "sidik jari": "fingerprint",
    "farmakofor": "pharmacophore",
    "klaster": "cluster",
    "peringkat": "rank",
    "sebaran": "distribution",
    "korelasi": "correlation",
    "optimasi": "optimization",
    "pustaka senyawa": "compound library",
    "pustaka ligan": "ligand library",
    "pustaka": "library",
    "senyawa": "compound",
    "obat disetujui": "approved drugs",
    "bahan alam": "natural products",
    "kemudahan sintesis": "synthetic accessibility",
    "mudah disintesis": "synthetically accessible",
    "sulit disintesis": "difficult to synthesize",
    "modifikasi bioisosterik": "bioisosteric modification",
    "bioisoster": "bioisostere",
    "substituen": "substituent",
    "penghubung": "linker",
    "pelarut": "solvent",
    "blanko": "blank",
    "kendali": "control",
    "kontrol positif": "positive control",
    "pelat mikro": "microplate",
    "sumur": "well",
    "pengenceran bertingkat": "serial dilution",
    "konsentrasi stok": "stock concentration",
    "larutan kerja": "working solution",
    "larutan antara": "intermediate solution",
    "protokol kerja": "working protocol",
    "protokol pengujian": "assay protocol",
    "protokol": "protocol",
    "pemeriksa kesehatan": "health check",
    "diagnostik sistem": "system diagnostic",
    "diagnostik": "diagnostic",
    "siap pakai": "ready to use",
    "terdeteksi": "detected",
    "tidak terdeteksi": "not detected",
    "aktif": "active",
    "nonaktif": "inactive",
    "selesai": "completed",
    "gagal": "failed",
    "berhasil": "successful",
    "sedang berjalan": "running",
    "menunggu": "waiting",
    "batal": "cancel",
    "dibatalkan": "cancelled",
    "simpan": "save",
    "buka": "open",
    "tutup": "close",
    "ekspor": "export",
    "impor": "import",
    "salin": "copy",
    "tempel": "paste",
    "hapus": "delete",
    "tambah": "add",
    "ubah": "modify",
    "atur": "configure",
    "pengaturan": "settings",
    "tampilkan": "show",
    "sembunyikan": "hide",
    "fokus": "focus",
    "pilih semua": "select all",
    "pilih": "select",
    "bantuan": "help",
    "tentang": "about",
    "keluar": "exit",
    "lanjut": "continue",
    "kembali": "back",
    "terapkan": "apply",
    "reset": "reset",
    "hitung": "calculate",
    "cari": "search",
    "saring": "filter",
    "urutkan": "sort",
    "muat": "load",
    "unduh": "download",
    "unggah": "upload",
    "perbarui": "update",
    "peringatan": "warning",
    "galat": "error",
    "informasi": "information",
    "catatan": "note",
    "ringkasan": "summary",
    "parameter": "parameter",
    "nilai": "value",
    "status": "status",
    "nama": "name",
    "jumlah": "count",
    "total": "total",
    "rata-rata": "average",
    "median": "median",
    "standar deviasi": "standard deviation",
    "minimum": "minimum",
    "maksimum": "maximum",
    "ambang batas": "threshold",
    "bobot": "weight",
    "warna": "color",
    "tema": "theme",
    "gelap": "dark",
    "terang": "light",
}

# Pola frasa spesifik VirmoDock
FRASA_SPESIFIK = {
    "Pemeriksa Kesehatan Lingkungan Sistem": "System Environment Health Check",
    "Pemeriksa Kesiapan Komponen": "Component Readiness Checker",
    "Audit Kesiapan Sistem": "System Readiness Audit",
    "Prediksi Titik Metabolisme Ligan": "Ligand Site of Metabolism (SoM) Prediction",
    "Prediksi Kinetika Pengikatan & Waktu Tinggal": "Binding Kinetics & Residence Time Prediction",
    "Kalkulator Perencanaan Uji Laboratorium Basah": "Wet-Lab Assay Planning Calculator",
    "Denah Pelat Mikro": "Microplate Layout",
    "Protokol Pemipetan": "Pipetting Protocol",
    "Skor Kelayakan Terpadu": "Integrated Desirability Score",
    "Desain Obat Berbasis Fragmen": "Fragment-Based Drug Design",
    "Fragment Growing & Linking": "Fragment Growing & Linking",
    "Analisis Molekul Pasangan Cocok": "Matched Molecular Pair (MMP) Analysis",
    "Penapisan Virtual Kumpulan Ligan": "Batch Virtual Screening",
    "Peta Distribusi Organ & Toksisitas Jaringan": "Organ Distribution & Tissue Toxicity Map",
    "Air Termodinamika & Hidrasi Sisi Aktif": "Active Site Thermodynamic Water & Hydration",
    "Deteksi Kantong Pengikatan LIGSITE": "LIGSITE Binding Pocket Detection",
    "Deteksi Terowongan Akses Molekuler": "Molecular Access Tunnel Detection",
    "Docking Protein-Protein": "Protein-Protein Docking",
    "Analisis Antarmuka PPI": "PPI Interface Analysis",
    "Rescoring Berbasis Pembelajaran Mesin": "Machine Learning-Based Rescoring",
    "Perancang Molekul PROTAC & TPD": "PROTAC & TPD Molecule Designer",
    "Generator Skrip Publikasi PyMOL & ChimeraX": "PyMOL & ChimeraX Publication Script Generator",
    "Profil Selektivitas Multi-Target": "Multi-Target Selectivity Profiling",
    "Synthetic Accessibility Score (SAScore)": "Synthetic Accessibility Score (SAScore)",
    "Estimasi Waktu Paruh Disosiasi": "Dissociation Half-Life Estimation",
    "Ligan Terbaik": "Top Ligand",
    "Semua Ligan": "All Ligands",
    "Hasil Penambatan": "Docking Results",
    "Tabel Ringkasan": "Summary Table",
    "Gaya Visual": "Visual Style",
    "Simpan Skrip": "Save Script",
    "Salin Skrip": "Copy Script",
    "Buka Berkas": "Open File",
    "Folder Keluaran": "Output Folder",
    "Jalankan Analisis": "Run Analysis",
    "Sedang menganalisis…": "Analyzing…",
    "Sedang menghitung…": "Calculating…",
    "Sedang memproses…": "Processing…",
    "Gagal menjalankan analisis": "Failed to run analysis",
    "Analisis selesai": "Analysis completed",
    "Tidak ada pose docking yang tersedia": "No docking poses available",
    "Pilih minimal satu ligan": "Select at least one ligand",
    "Struktur reseptor belum siap": "Receptor structure is not ready",
}


def terjemahkan_manual(teks: str) -> str:
    """Terjemahkan frasa / kalimat bahasa Indonesia ke bahasa Inggris ilmiah."""
    s = teks.strip()
    if not s:
        return s

    if s in FRASA_SPESIFIK:
        return FRASA_SPESIFIK[s]

    if s in KAMUS_KATA:
        return KAMUS_KATA[s]

    # Cek penggantian langsung case-insensitive bila ada kecocokan persis
    s_low = s.lower()
    if s_low in FRASA_SPESIFIK:
        return FRASA_SPESIFIK[s_low]
    if s_low in KAMUS_KATA:
        t = KAMUS_KATA[s_low]
        return t.capitalize() if s[0].isupper() else t

    hasil = s

    # Penggantian bertahap frasa kunci terpanjang lebih dulu
    for id_frasa in sorted(KAMUS_KATA.keys(), key=len, reverse=True):
        en_frasa = KAMUS_KATA[id_frasa]
        # Ganti dengan memperhatikan batas kata
        pola = re.compile(rf"\b{re.escape(id_frasa)}\b", re.IGNORECASE)
        def repl(m):
            t = m.group(0)
            if t.isupper():
                return en_frasa.upper()
            if t[0].isupper():
                return en_frasa.capitalize()
            return en_frasa
        hasil = pola.sub(repl, hasil)

    # Tambalan kata hubung dan preposisi umum
    tata_bahasa = [
        (r"\bdi dalam\b", "inside"),
        (r"\bdi sekitar\b", "around"),
        (r"\bke dalam\b", "into"),
        (r"\bdan / atau\b", "and/or"),
        (r"\bdan\b", "and"),
        (r"\batau\b", "or"),
        (r"\buntuk\b", "for"),
        (r"\bdari\b", "from"),
        (r"\bdengan\b", "with"),
        (r"\btanpa\b", "without"),
        (r"\bpada\b", "on"),
        (r"\bbila\b", "if"),
        (r"\bjika\b", "if"),
        (r"\btidak\b", "not"),
        (r"\bbelum\b", "not yet"),
        (r"\bsudah\b", "already"),
        (r"\bsemua\b", "all"),
        (r"\bsetiap\b", "each"),
        (r"\bhanya\b", "only"),
        (r"\bantara\b", "between"),
        (r"\bmenurut\b", "according to"),
        (r"\bsesuai\b", "according to"),
        (r"\bberdasarkan\b", "based on"),
        (r"\bsecara\b", "by"),
        (r"\bsangat\b", "very"),
        (r"\blebih\b", "more"),
        (r"\bterlalu\b", "too"),
        (r"\bsebesar\b", "of"),
        (r"\bmasing-masing\b", "respective"),
        (r"\bseluruh\b", "entire"),
        (r"\blainnya\b", "others"),
        (r"\bbaru\b", "new"),
        (r"\blama\b", "old"),
        (r"\btinggi\b", "high"),
        (r"\brendah\b", "low"),
        (r"\bbesar\b", "large"),
        (r"\bkecil\b", "small"),
        (r"\bpanjang\b", "length"),
        (r"\blebar\b", "width"),
        (r"\bkedalaman\b", "depth"),
        (r"\bvolume\b", "volume"),
        (r"\bradius\b", "radius"),
        (r"\bjarak\b", "distance"),
        (r"\bderajat\b", "degrees"),
        (r"\bdetik\b", "seconds"),
        (r"\bmenit\b", "minutes"),
        (r"\bjam\b", "hours"),
        (r"\bhari\b", "days"),
        (r"\bbulan\b", "months"),
        (r"\btahun\b", "years"),
    ]

    for id_p, en_p in tata_bahasa:
        pola = re.compile(id_p, re.IGNORECASE)
        def repl(m):
            t = m.group(0)
            if t.isupper():
                return en_p.upper()
            if t[0].isupper():
                return en_p.capitalize()
            return en_p
        hasil = pola.sub(repl, hasil)

    return hasil


def terjemahkan_pola(pola: str) -> str:
    """Terjemahkan teks pola f-string dengan mempertahankan {0}, {1}, dst."""
    # Ekstrak token {0}, {1}...
    placeholders = re.findall(r"\{\d+\}", pola)
    # Ganti sementara dengan token khusus
    pola_bersih = pola
    for i, ph in enumerate(placeholders):
        pola_bersih = pola_bersih.replace(ph, f"__PH_{i}__", 1)

    hasil = terjemahkan_manual(pola_bersih)

    # Kembalikan placeholders
    for i, ph in enumerate(placeholders):
        hasil = hasil.replace(f"__PH_{i}__", ph, 1)

    return hasil


def main():
    teks_baru_path = Path("dev/i18n_teks_baru.json")
    if not teks_baru_path.exists():
        print("dev/i18n_teks_baru.json tidak ditemukan!")
        return

    data_baru = json.loads(teks_baru_path.read_text(encoding="utf-8"))
    literals = data_baru.get("literal", [])
    polas = data_baru.get("pola", [])

    tambahan_path = Path("dev/i18n_tambahan.json")
    tambahan = {"teks": {}, "pola": {}}
    if tambahan_path.exists():
        tambahan = json.loads(tambahan_path.read_text(encoding="utf-8"))

    # Terjemahkan literal baru
    n_teks_tambah = 0
    for lit in literals:
        if lit not in tambahan["teks"]:
            tambahan["teks"][lit] = terjemahkan_manual(lit)
            n_teks_tambah += 1

    # Terjemahkan pola baru
    n_pola_tambah = 0
    for pol in polas:
        if pol not in tambahan["pola"]:
            tambahan["pola"][pol] = terjemahkan_pola(pol)
            n_pola_tambah += 1

    # Simpan dev/i18n_tambahan.json
    tambahan_path.write_text(json.dumps(tambahan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Menambahkan {n_teks_tambah} teks dan {n_pola_tambah} pola ke dev/i18n_tambahan.json.")

    # Jalankan dev/buat_kamus.py
    import subprocess
    cmd = [sys.executable, "dev/buat_kamus.py"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    print(res.stdout)
    if res.stderr:
        print("Galat buat_kamus:", res.stderr)


if __name__ == "__main__":
    main()
