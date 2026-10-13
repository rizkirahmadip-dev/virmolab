"""Pengujian mandiri Batch Virtual Screening Dashboard (Fitur 1)."""
import os
import sys

# Tambahkan direktori kerja ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from virmolab.core import penapisan, grafik


def run_tests():
    print("=== Menguji Modul Penapisan Virtual ===")
    gagal = 0

    # 1. Mock Data Penapisan
    dummy_data = [
        {
            "nama": "Ligan_A",
            "lid": "1",
            "energi": -8.5,
            "le": -0.42,
            "ki": "60 nM",
            "mw": 320.0,
            "wlogp": 2.5,
            "tpsa": 65.0,
            "qed": 0.82,
            "sascore": 2.8,
            "interaksi_total": 7,
            "lipinski_lolos": True,
            "veber_lolos": True,
            "pains": False,
            "brenk": False,
            "gi": True,
            "bbb": False,
            "mpo_skor": 85.0,
        },
        {
            "nama": "Ligan_B",
            "lid": "2",
            "energi": -6.0,
            "le": -0.25,
            "ki": "40 uM",
            "mw": 520.0,
            "wlogp": 5.5,
            "tpsa": 150.0,
            "qed": 0.35,
            "sascore": 6.8,
            "interaksi_total": 2,
            "lipinski_lolos": False,
            "veber_lolos": False,
            "pains": True,
            "brenk": True,
            "gi": False,
            "bbb": False,
            "mpo_skor": 35.0,
        },
        {
            "nama": "Ligan_C",
            "lid": "3",
            "energi": -7.4,
            "le": -0.35,
            "ki": "3.5 uM",
            "mw": 390.0,
            "wlogp": 3.1,
            "tpsa": 78.0,
            "qed": 0.68,
            "sascore": 3.4,
            "interaksi_total": 5,
            "lipinski_lolos": True,
            "veber_lolos": True,
            "pains": False,
            "brenk": False,
            "gi": True,
            "bbb": True,
            "mpo_skor": 72.0,
        },
    ]

    # Uji 1: filter_data
    terfilter = penapisan.filter_data(dummy_data, {"energi_maks": -7.0, "lipinski_lolos": True, "pains_bebas": True})
    if len(terfilter) == 2 and {d["nama"] for d in terfilter} == {"Ligan_A", "Ligan_C"}:
        print("OK   filter_data berhasil menyaring ligan")
    else:
        print(f"FAIL filter_data gagal: {[d['nama'] for d in terfilter]}")
        gagal += 1

    # Uji 2: flag_top_hits
    scored = penapisan.flag_top_hits(dummy_data, n=1)
    if len(scored) == 3 and scored[0]["nama"] == "Ligan_A" and scored[0]["flag_top"] is True and scored[1]["flag_top"] is False:
        print(f"OK   flag_top_hits berhasil: juara = {scored[0]['nama']} (skor {scored[0]['skor_komposit']})")
    else:
        print("FAIL flag_top_hits gagal menentukan top hits")
        gagal += 1

    # Uji 3: statistik_ringkas
    stat = penapisan.statistik_ringkas(dummy_data, terfilter)
    if stat["total_ligan"] == 3 and stat["jumlah_lolos"] == 2 and stat["persentase_lolos"] == 66.7:
        print(f"OK   statistik_ringkas valid: lolos = {stat['jumlah_lolos']}/{stat['total_ligan']} ({stat['persentase_lolos']}%)")
    else:
        print(f"FAIL statistik_ringkas tidak sesuai: {stat}")
        gagal += 1

    # Uji 4: matriks_heatmap
    mat, rows, cols = penapisan.matriks_heatmap(dummy_data)
    if len(mat) == 3 and len(rows) == 3 and len(cols) == 6:
        print("OK   matriks_heatmap menghasilkan dimensi yang benar")
    else:
        print(f"FAIL matriks_heatmap gagal: rows={len(rows)}, cols={len(cols)}")
        gagal += 1

    # Uji 5: heatmap_svg
    svg_hm = grafik.heatmap_svg(mat, rows, cols, judul="Uji Heatmap")
    if "<svg" in svg_hm and "</svg>" in svg_hm and "Ligan_A" in svg_hm:
        print(f"OK   heatmap_svg menghasilkan SVG valid ({len(svg_hm)} karakter)")
    else:
        print("FAIL heatmap_svg menghasilkan output tidak valid")
        gagal += 1

    # Uji 6: scatter_multi_svg
    svg_sc = grafik.scatter_multi_svg(scored, "energi", "sascore", warna_kunci="mpo_skor", sorot_flag="flag_top")
    if "<svg" in svg_sc and "</svg>" in svg_sc and "Top Hit" in svg_sc:
        print(f"OK   scatter_multi_svg menghasilkan SVG valid dengan sorotan bintang ({len(svg_sc)} karakter)")
    else:
        print("FAIL scatter_multi_svg menghasilkan output tidak valid")
        gagal += 1

    # Uji 7: histogram_distribusi_svg
    svg_hi = grafik.histogram_distribusi_svg(dummy_data, kunci="energi", bins=5)
    if "<svg" in svg_hi and "</svg>" in svg_hi and "Rata-rata" in svg_hi:
        print(f"OK   histogram_distribusi_svg menghasilkan SVG valid ({len(svg_hi)} karakter)")
    else:
        print("FAIL histogram_distribusi_svg menghasilkan output tidak valid")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(run_tests())
