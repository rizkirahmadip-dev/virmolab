"""Uji unit dan integrasi Pelacak Hipotesis -> Uji Laboratorium (F12).

Memverifikasi:
1. Korelasi sintetis diketahui (Spearman ρ, Kendall τ, bootstrap 1000×, n, n_dilewati).
2. Peringatan statistik untuk sampel kecil n < 8.
3. Penanganan ligan tanpa pasangan (dilewati dan dihitung).
4. Konversi pIC50 dari nilai dan satuan terukur.
5. Parsing CSV hasil laboratorium: tabel IC50, dan matriks plate reader -> IC50 (normalisasi + 4PL).
6. Migrasi data proyek lama secara round-trip tanpa kehilangan isi.
7. Pembuatan grafik Prediksi vs Terukur (SVG).
"""
import math
import shutil
import sys
import tempfile
from pathlib import Path

# Atur path dan encoding
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from virmolab.core import hipotesis, labplanner
from virmolab.core.proyek import Proyek, migrasi_proyek


def uji_korelasi_sintetis():
    print("--- 1. Uji Korelasi Sintetis Diketahui ---")
    # Kasus A: Korelasi positif sempurna (n = 10 >= 8)
    x_pos = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    y_pos = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    res_pos = hipotesis.bandingkan(x_pos, y_pos, n_bootstrap=1000, seed=42)

    assert res_pos["n"] == 10, f"n salah: {res_pos['n']}"
    assert res_pos["n_dilewati"] == 0, f"n_dilewati salah: {res_pos['n_dilewati']}"
    assert abs(res_pos["spearman"] - 1.0) < 1e-4, f"Spearman rho salah: {res_pos['spearman']}"
    assert abs(res_pos["kendall"] - 1.0) < 1e-4, f"Kendall tau salah: {res_pos['kendall']}"
    assert res_pos["ci_spearman"] is not None
    assert abs(res_pos["ci_spearman"][0] - 1.0) < 1e-3, f"CI Spearman bawah salah: {res_pos['ci_spearman']}"
    assert abs(res_pos["ci_spearman"][1] - 1.0) < 1e-3, f"CI Spearman atas salah: {res_pos['ci_spearman']}"
    assert res_pos["peringatan"] is None, f"Harusnya tidak ada peringatan: {res_pos['peringatan']}"
    print("OK    Korelasi positif sempurna rho=1.0, tau=1.0, CI bootstrap valid.")

    # Kasus B: Korelasi negatif sempurna (n = 10)
    y_neg = [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0, 20.0, 10.0]
    res_neg = hipotesis.bandingkan(x_pos, y_neg, n_bootstrap=1000, seed=42)
    assert abs(res_neg["spearman"] - (-1.0)) < 1e-4, f"Spearman negatif salah: {res_neg['spearman']}"
    assert abs(res_neg["kendall"] - (-1.0)) < 1e-4, f"Kendall negatif salah: {res_neg['kendall']}"
    print("OK    Korelasi negatif sempurna rho=-1.0, tau=-1.0 valid.")

    # Kasus C: Sampel kecil (n = 5 < 8) harus memicu peringatan
    x_kecil = [1.0, 2.0, 3.0, 4.0, 5.0]
    y_kecil = [1.5, 2.8, 3.2, 4.9, 5.5]
    res_kecil = hipotesis.bandingkan(x_kecil, y_kecil, n_bootstrap=500, seed=42)
    assert res_kecil["n"] == 5
    assert res_kecil["peringatan"] is not None, "Peringatan sampel n < 8 tidak muncul!"
    assert "kurang dari 8" in res_kecil["peringatan"]
    print(f"OK    Peringatan sampel n < 8 aktif: '{res_kecil['peringatan']}'")

    # Kasus D: Pasangan data tidak lengkap (None / NaN) dilewati dan dihitung
    x_bolong = [1.0, None, 3.0, 4.0, None, 6.0, 7.0, 8.0, 9.0, 10.0]
    y_bolong = [10.0, 20.0, None, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, None]
    res_bolong = hipotesis.bandingkan(x_bolong, y_bolong, n_bootstrap=500, seed=42)
    assert res_bolong["n"] == 6, f"n salah pada data bolong: {res_bolong['n']}"
    assert res_bolong["n_dilewati"] == 4, f"n_dilewati salah: {res_bolong['n_dilewati']}"
    print("OK    Pasangan tidak lengkap dilewati (n=6, dilewati=4).")


def uji_konversi_dan_entri():
    print("\n--- 2. Uji Konversi pIC50 dan Normalisasi Entri ---")
    # 10 uM = 1e-5 M -> pIC50 = 5.0
    p1 = hipotesis.ke_pic50(10.0, "uM")
    assert abs(p1 - 5.0) < 1e-4, f"pIC50 10 uM salah: {p1}"

    # 1 nM = 1e-9 M -> pIC50 = 9.0
    p2 = hipotesis.ke_pic50(1.0, "nM")
    assert abs(p2 - 9.0) < 1e-4, f"pIC50 1 nM salah: {p2}"

    # 100 nM = 1e-7 M -> pIC50 = 7.0
    p3 = hipotesis.ke_pic50(100.0, "nM")
    assert abs(p3 - 7.0) < 1e-4, f"pIC50 100 nM salah: {p3}"

    # Nilai tak sah
    assert hipotesis.ke_pic50(None, "uM") is None
    assert hipotesis.ke_pic50(-5.0, "uM") is None
    assert hipotesis.ke_pic50(10.0, "satuan_aneh") is None
    print("OK    Konversi satuan ke pIC50 tepat secara kimia/farmakologi.")

    # Uji status hipotesis
    for st in ("diajukan", "diuji", "didukung", "ditolak"):
        ent = hipotesis.normalisasi_entri({"ligan_id": "L1", "status_hipotesis": st})
        assert ent["status_hipotesis"] == st

    ent_aneh = hipotesis.normalisasi_entri({"ligan_id": "L1", "status_hipotesis": "ngawur"})
    assert ent_aneh["status_hipotesis"] == "diajukan"
    print("OK    Status hipotesis ternormalisasi sesuai 4 status baku.")


def uji_impor_csv():
    print("\n--- 3. Uji Parsing CSV Plate Reader & Tabel ---")
    # Kasus A: Format Tabel CSV Standar
    csv_tabel = """ligan_id,nilai,satuan,assay,status_hipotesis,catatan
LIG001,1.5,uM,Inhibisi Protease,didukung,Uji triplo
LIG002,12.0,uM,Inhibisi Protease,diuji,Konsentrasi intermediat
LIG003,250.0,nM,Inhibisi Protease,didukung,Aktivitas sangat kuat
LIG004,150.0,uM,Inhibisi Protease,ditolak,Inaktif
"""
    entri_tabel = hipotesis.impor_csv_hasil(csv_tabel)
    assert len(entri_tabel) == 4
    assert entri_tabel[0]["ligan_id"] == "LIG001"
    assert entri_tabel[0]["nilai"] == 1.5
    assert entri_tabel[0]["pIC50"] is not None
    assert entri_tabel[0]["status_hipotesis"] == "didukung"
    assert entri_tabel[2]["satuan"] == "nM"
    assert abs(entri_tabel[2]["pIC50"] - 6.6021) < 1e-3
    print("OK    CSV format tabel baris berhasil diuraikan.")

    # Kasus B: matriks plate reader 96-well = sinyal mentah. IC50 harus diturunkan dari denah
    # (blanko, kendali pelarut, seri konsentrasi) lewat fit 4PL, bukan dibaca langsung dari sel.
    seri = labplanner.hitung_seri_konsentrasi(100.0, 3.0, 8)
    denah = labplanner.rancang_denah_pelat("96", [
        {"nama": "LIG_AKTIF", "konsentrasi": seri},
        {"nama": "LIG_INAKTIF", "konsentrasi": seri},
    ], replikasi=3)
    rng = np.random.default_rng(7)
    blanko, vc, pc = 0.05, 1.00, 0.10

    def _sinyal(inhib):
        return blanko + (vc - blanko) * (1 - inhib / 100.0) + rng.normal(0, 0.01)

    nilai = {}
    for pos, g in denah["grid"].items():
        if g["jenis"] == "blanko":
            nilai[pos] = blanko + rng.normal(0, 0.005)
        elif g["jenis"] == "pelarut":
            nilai[pos] = vc + rng.normal(0, 0.02)
        elif g["jenis"] == "kontrol_pos":
            nilai[pos] = pc + rng.normal(0, 0.02)
        elif g["jenis"] == "sampel":
            x = g["kons_uM"]
            if g["sampel"] == "LIG_AKTIF":   # 4PL nyata: IC50 2 µM, Hill 1
                nilai[pos] = _sinyal(100.0 / (1 + (2.0 / x) ** 1.0))
            else:                            # maksimal ~20 % inhibisi
                nilai[pos] = _sinyal(20.0 * x / (x + 10.0))
    kolom = denah["label_kolom"]
    baris_csv = ["," + ",".join(kolom)]
    for r in denah["label_baris"]:
        baris_csv.append(r + "," + ",".join(f"{nilai[r + c]:.4f}" if r + c in nilai else "" for c in kolom))
    csv_pelat = "\n".join(baris_csv) + "\n"

    entri_pelat = {e["ligan_id"]: e for e in hipotesis.impor_csv_hasil(csv_pelat, denah)}
    akt, inakt = entri_pelat["LIG_AKTIF"], entri_pelat["LIG_INAKTIF"]
    print(f"      LIG_AKTIF: IC50 {akt['nilai']} µM ({akt['catatan']})")
    print(f"      LIG_INAKTIF: nilai {inakt['nilai']} ({inakt['catatan']})")
    assert akt["nilai"] is not None and abs(akt["nilai"] - 2.0) / 2.0 < 0.15, akt
    assert abs(akt["pIC50"] - (6 - math.log10(2.0))) < 0.07, akt["pIC50"]
    assert inakt["nilai"] is None and inakt["pIC50"] is None and "IC50 >" in inakt["catatan"], inakt
    print("OK    Matriks plate reader -> IC50 lewat normalisasi kontrol + 4PL (2 µM pulih ±15 %).")
    print("OK    Senyawa tak mencapai 50 % inhibisi ditandai tersensor, tidak dikorelasikan.")

    try:
        hipotesis.impor_csv_hasil(csv_pelat, None)
        raise AssertionError("Matriks tanpa denah seharusnya ditolak")
    except ValueError as e:
        assert "denah" in str(e)
    print("OK    Matriks pelat tanpa denah ditolak (bacaan mentah bukan IC50).")


def uji_migrasi_proyek_lama():
    print("\n--- 4. Uji Migrasi Proyek Lama (Round-Trip) ---")
    tmp = Path(tempfile.mkdtemp(prefix="virmo_uji_hipotesis_"))
    try:
        folder_proyek = tmp / "ProyekLama.vmd"
        folder_proyek.mkdir(parents=True)

        # Simulasikan proyek lawas VirmoLab yang sudah memiliki data aktivitas ChEMBL
        data_lama = {
            "format": 1,
            "aplikasi": "VirmoLab",
            "nama": "ProyekLama",
            "dibuat": "2026-01-01T10:00:00",
            "reseptor": {"nama": "1hsg"},
            "ligan": [
                {"id": "MK1", "nama": "Indinavir", "smiles": "CC(C)(C)NC(=O)..."},
                {"id": "L02", "nama": "Kandidat2", "smiles": "c1ccccc1"}
            ],
            "job": [
                {
                    "id": "job_1", "mesin": "vina",
                    "ligan": [
                        {"id": "MK1", "pose": [{"energi": -11.4}]},
                        {"id": "L02", "pose": [{"energi": -6.2}]}
                    ]
                }
            ],
            "eksperimen": {
                "target": {"chembl": "CHEMBL240", "nama": "Human immunodeficiency virus type 1 protease"},
                "jenis": "IC50",
                "senyawa": [
                    {"chembl": "CHEMBL1", "nama": "Indinavir", "pchembl": 8.7, "smiles": "CC(C)..."}
                ],
                "sumber": "ChEMBL",
                "waktu": "01-01-2026 10:00"
            }
        }

        # 1. Jalankan migrasi proyek
        data_migrasi = migrasi_proyek(dict(data_lama))

        # Verifikasi data lama ChEMBL TIDAK HILANG
        assert "target" in data_migrasi["eksperimen"], "Data target ChEMBL hilang saat migrasi!"
        assert data_migrasi["eksperimen"]["target"]["chembl"] == "CHEMBL240"
        assert len(data_migrasi["eksperimen"]["senyawa"]) == 1
        assert "entri" in data_migrasi["eksperimen"], "Kunci 'entri' belum terbentuk!"
        print("OK    Migrasi format: metadata lama ChEMBL tetap 100% utuh.")

        # 2. Tulis file proyek.json dan buka melalui Proyek.buka()
        import json
        (folder_proyek / "proyek.json").write_text(json.dumps(data_migrasi, indent=2), encoding="utf-8")
        pr = Proyek.buka(folder_proyek)
        assert pr.eksperimen["target"]["chembl"] == "CHEMBL240"
        assert isinstance(pr.eksperimen["entri"], list)

        # 3. Tambahkan entri hipotesis baru
        entri_baru = [
            {
                "id": "EXP001",
                "ligan_id": "MK1",
                "assay": "Inhibisi Enzim HIV-1",
                "nilai": 2.5,
                "satuan": "nM",
                "pIC50": 8.6021,
                "tanggal": "2026-10-14",
                "catatan": "Validasi pose kristal",
                "status_hipotesis": "didukung"
            },
            {
                "id": "EXP002",
                "ligan_id": "L02",
                "assay": "Inhibisi Enzim HIV-1",
                "nilai": 15.0,
                "satuan": "uM",
                "pIC50": 4.8239,
                "tanggal": "2026-10-14",
                "catatan": "Aktivitas rendah",
                "status_hipotesis": "ditolak"
            }
        ]
        hipotesis.simpan_entri_proyek(pr, entri_baru)
        pr.simpan()

        # 4. Buka kembali (round-trip) dan verifikasi integritas penuh
        pr2 = Proyek.buka(folder_proyek)
        assert pr2.eksperimen["target"]["chembl"] == "CHEMBL240", "Target ChEMBL hilang setelah simpan-buka!"
        assert len(pr2.eksperimen["senyawa"]) == 1, "Senyawa ChEMBL hilang!"
        assert len(pr2.eksperimen["entri"]) == 2, "Entri eksperimen baru tidak tersimpan!"
        assert pr2.eksperimen["entri"][0]["ligan_id"] == "MK1"
        assert pr2.eksperimen["entri"][0]["status_hipotesis"] == "didukung"
        assert pr2.eksperimen["entri"][1]["status_hipotesis"] == "ditolak"
        print("OK    Uji pulang-pergi (round-trip) proyek berhasil sempurna tanpa kehilangan data.")

        # 5. Uji ekstraksi tabel & pembuatan grafik SVG
        baris_tabel, stats_tabel = hipotesis.kumpulkan_data_tabel(pr2, jenis_prediksi="dg")
        assert len(baris_tabel) >= 2
        svg_out = hipotesis.buat_grafik_prediksi_vs_terukur(baris_tabel, jenis_prediksi="dg")
        assert "<svg" in svg_out and "</svg>" in svg_out
        assert "Prediksi in silico vs aktivitas terukur" in svg_out
        print("OK    Grafik SVG Prediksi vs Terukur berhasil digenerate.")

        # 6. MM/GBSA dibaca dari struktur run MD nyata (proyek.md[i]["ligan"][j]["mmgbsa"]["dG"])
        lid0 = baris_tabel[0]["ligan_id"]
        pr2.md = [{"status": "selesai", "ligan": [
            {"lid": lid0, "selesai": True, "mmgbsa": {"dG": -31.5}},
            {"lid": "TAK_SELESAI", "selesai": False, "mmgbsa": {"dG": -99.0}},
        ]}]
        assert hipotesis.ada_prediksi(pr2, "mmgbsa")
        baris_mm, _ = hipotesis.kumpulkan_data_tabel(pr2, jenis_prediksi="mmgbsa")
        mm = {b["ligan_id"]: b["prediksi_tampil"] for b in baris_mm}
        assert mm[lid0] == -31.5 and mm.get("TAK_SELESAI") is None, mm
        pr2.md = []
        assert not hipotesis.ada_prediksi(pr2, "mmgbsa")
        print("OK    MM/GBSA terbaca dari run MD selesai; pilihan tanpa data terdeteksi kosong.")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("UJI PELACAK HIPOTESIS -> UJI LAB (F12)")
    print("=" * 60)

    uji_korelasi_sintetis()
    uji_konversi_dan_entri()
    uji_impor_csv()
    uji_migrasi_proyek_lama()

    print("\n" + "=" * 60)
    print("SEMUA UJI HIPOTESIS DAN VALIDASI LAB (F12) LULUS!")
    print("=" * 60)


if __name__ == "__main__":
    main()
