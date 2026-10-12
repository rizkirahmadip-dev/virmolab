"""Pengujian mandiri Pemeriksa Kesehatan Lingkungan (Diagnostik)."""
import os
import sys

# Tambahkan direktori kerja ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from virmodock.core import diagnostik


def run_tests():
    print("=== Menguji Modul Pemeriksa Kesehatan Lingkungan (Diagnostik) ===")
    gagal = 0

    hasil = diagnostik.periksa_semua()
    if len(hasil) >= 6:
        print(f"OK   periksa_semua berhasil mengaudit {len(hasil)} komponen sistem")
        for item in hasil:
            print(f"     - {item['komponen']}: {item['detail']} ({item['status']})")
    else:
        print("FAIL periksa_semua mengembalikan hasil terlalu sedikit")
        gagal += 1

    teks = diagnostik.ringkasan_teks_diagnostik()
    if "LAPORAN DIAGNOSTIK" in teks and "Python" in teks:
        print("OK   ringkasan_teks_diagnostik terformat dengan baik")
    else:
        print("FAIL ringkasan_teks_diagnostik gagal")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(run_tests())
