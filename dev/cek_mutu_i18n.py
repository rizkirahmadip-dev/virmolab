"""Skrip deteksi entri terjemahan bermasalah di virmolab/i18n/en.json.

Kriteria:
(a) Nilai Inggris berisi >= 2 kata Indonesia umum setelah tag HTML dan {placeholder} dibuang.
(b) Spasi/newline di awal atau akhir kunci != nilai.
(c) Nilai == kunci padahal kunci berbahasa Indonesia.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN_PATH = ROOT / "virmolab" / "i18n" / "en.json"
OUT_PATH = ROOT / "dev" / "i18n_perbaiki.json"

# Daftar kata Indonesia umum (kata tugas, verba, nomina khas)
KATA_INDO_UMUM = {
    # Kata tugas & penghubung
    "yang", "dan", "tidak", "bisa", "dengan", "untuk", "ke", "di", "bila", "pada",
    "adalah", "sudah", "belum", "hanya", "oleh", "dari", "atau", "juga", "akan",
    "dalam", "sebagai", "lebih", "semua", "harus", "saat", "setelah", "sebelum",
    "antara", "sampai", "saja", "jika", "maka", "tanpa", "ada", "karena", "terhadap",
    "bukan", "tetapi", "namun", "sehingga", "agar", "supaya", "terlalu", "sangat",
    "kurang", "sedikit", "banyak", "makin", "paling", "seluruh", "setiap", "tiap",
    
    # Kata benda & istilah umum
    "berkas", "ligan", "reseptor", "kantong", "ditemukan", "residu", "rantai",
    "kotak", "laporan", "ikatan", "interaksi", "kemiripan", "pengaturan", "terpilih",
    "acuan", "pustaka", "baris", "tombol", "tahap", "waktu", "detik", "menit",
    "urutan", "ambang", "jumlah", "rerata", "muatan", "medan", "kaku", "fleksibel",
    "penyiapan", "optimasi", "minimasi", "penapisan", "skrining", "tampilan", "jendela",
    "pesan", "kesalahan", "petunjuk", "panduan", "tentang", "pengembang", "lisensi",
    "kredit", "ekspor", "impor", "unduh", "unggah", "tambah", "tambahkan", "hapus",
    "ubah", "atur", "setel", "bersihkan", "muat", "keluar", "aduk", "kurangi",
    "dilampirkan", "sendiri", "dicentang", "berotasi", "pencarian", "membesar",
    "bergantung", "gugus", "reaktif", "diikat", "dilaporkan", "sebanding", "sasaran",
    "mencakup", "pindahkan", "perbesar", "pasangan", "jurang", "saringan", "permukaan",
    "selektivitas", "pusatkan", "perjalanan", "obat", "pembuangan", "penyerapan",
    "peredaran", "peta", "organ", "menumbuhkan", "fragmen", "menyambung", "mencari",
    "menerapkan", "penjembatan", "masih", "memeriksa", "nomor", "tersimpan", "menabrak",
    "tabrakan", "komplementaritas", "pangsa", "titik", "sempit", "tersempit", "digambar",
    "saluran", "perangkat", "lunak", "dikutip", "rentang", "diskrining", "dipertahankan",
    "tipe", "keadaan", "baku", "difokuskan", "antrean", "bilah", "siap", "memulai",
    "penelitian", "umpan", "kosong", "makrosiklus", "terpisah", "gaya", "kembalikan",
    "bawaan", "deskriptif", "selisih", "terkoreksi", "halaman", "baca", "tulis", "ulang",
    "ruang", "dekat", "didukung", "pertama", "kedua", "ketiga", "terakhir", "contoh",
    "angka", "bawah", "atas", "kiri", "kanan", "tengah", "luar", "bebas", "tetap",
    "sekarang", "dulu", "cocok", "sesuai", "sama", "beda", "lain", "kriteria",
    
    # Kata kerja tindakan
    "menampilkan", "memilih", "menghitung", "membuat", "pilih", "salin", "buka",
    "simpan", "tutup", "lanjut", "kembali", "batal", "jalankan", "siapkan", "alat",
    "bantuan", "peringatan", "galat", "gagal", "berhasil", "selesai", "sedang",
    "dibuat", "dipakai", "diatur"
}

def bersihkan(teks: str) -> str:
    """Hapus tag HTML, entitas HTML, format placeholder, dan inisial all-caps."""
    # Hapus komentar HTML
    s = re.sub(r"<!--.*?-->", " ", teks, flags=re.DOTALL)
    # Hapus tag HTML
    s = re.sub(r"<[^>]+>", " ", s)
    # Hapus placeholder {name}, {0}, dsb
    s = re.sub(r"\{[^}]*\}", " ", s)
    # Hapus placeholder gaya printf (%s, %d, %.2f, dll)
    s = re.sub(r"%[0-9.-]*[sdfgxX%]", " ", s)
    # Hapus inisial nama/akronim All-Caps 2-huruf (mis. Hauser KE, MD, SD, SE, ID)
    s = re.sub(r"\b[A-Z]{2}\b", " ", s)
    return s

def cari_kata_indo(teks: str) -> list[str]:
    bersih = bersihkan(teks).lower()
    kata_kata = re.findall(r"\b[a-z]{2,}\b", bersih)
    return [k for k in kata_kata if k in KATA_INDO_UMUM]

def beda_whitespace(k: str, v: str) -> bool:
    """Cek apakah prefix atau suffix whitespace (spasi, newline, tab) berbeda."""
    k_pre = k[:len(k) - len(k.lstrip(" \t\n\r"))]
    v_pre = v[:len(v) - len(v.lstrip(" \t\n\r"))]
    if k_pre != v_pre:
        return True
    k_suf = k[len(k.rstrip(" \t\n\r")):]
    v_suf = v[len(v.rstrip(" \t\n\r")):]
    if k_suf != v_suf:
        return True
    return False

def kunci_adalah_indo(k: str) -> bool:
    """Deteksi apakah kunci berbahasa Indonesia."""
    indo = cari_kata_indo(k)
    return len(indo) >= 1

def deteksi_masalah():
    with open(EN_PATH, "r", encoding="utf-8") as f:
        kamus = json.load(f)

    bermasalah_teks = {}
    bermasalah_pola = {}

    count_a = 0
    count_b = 0
    count_c = 0

    for kategori, wadah in [("teks", bermasalah_teks), ("pola", bermasalah_pola)]:
        for k, v in kamus.get(kategori, {}).items():
            alasan = []
            
            # (a) Nilai Inggris berisi >= 2 kata Indonesia umum
            kata_indo = cari_kata_indo(v)
            if len(kata_indo) >= 2:
                alasan.append(f"(a) {len(kata_indo)} kata indo: {kata_indo[:5]}")
                count_a += 1

            # (b) Spasi/\n awal atau akhir berbeda
            if beda_whitespace(k, v):
                alasan.append("(b) beda whitespace")
                count_b += 1

            # (c) Nilai == kunci padahal kunci berbahasa Indonesia
            if k == v and kunci_adalah_indo(k):
                alasan.append("(c) nilai == kunci (indo)")
                count_c += 1

            if alasan:
                wadah[k] = {
                    "kunci": k,
                    "nilai": v,
                    "alasan": alasan
                }

    hasil = {
        "ringkasan": {
            "total_unik_bermasalah": len(bermasalah_teks) + len(bermasalah_pola),
            "kriteria_a": count_a,
            "kriteria_b": count_b,
            "kriteria_c": count_c,
            "total_teks": len(bermasalah_teks),
            "total_pola": len(bermasalah_pola),
        },
        "teks": {k: info["nilai"] for k, info in bermasalah_teks.items()},
        "pola": {k: info["nilai"] for k, info in bermasalah_pola.items()},
        "_detail": {
            "teks": bermasalah_teks,
            "pola": bermasalah_pola
        }
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(hasil, f, ensure_ascii=False, indent=2)

    return hasil["ringkasan"]

if __name__ == "__main__":
    ringkasan = deteksi_masalah()
    print(f"Total unik bermasalah : {ringkasan['total_unik_bermasalah']}")
    print(f"  (a) Campur kata Indo: {ringkasan['kriteria_a']}")
    print(f"  (b) Beda spasi/\\n   : {ringkasan['kriteria_b']}")
    print(f"  (c) Belum diterjemah: {ringkasan['kriteria_c']}")
    print(f"  Kategori teks       : {ringkasan['total_teks']}")
    print(f"  Kategori pola       : {ringkasan['total_pola']}")
