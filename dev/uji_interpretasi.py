"""Pengujian mandiri AI-Powered Docking Interpretation (Fitur 4)."""
import os
import sys

# Tambahkan direktori kerja ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from virmodock.core import asisten


class MockProyek:
    def __init__(self):
        self.nama = "Proyek_Uji_HIV1_Protease"
        self.reseptor = {"nama": "HIV-1 Protease", "pdb_id": "1HSG"}
        self.kotak = {
            "pusat": {"x": 16.0, "y": 25.0, "z": 4.0},
            "ukuran": {"x": 20.0, "y": 20.0, "z": 20.0},
        }
        self.validasi = {"rmsd": 1.15}
        self.ligan = [
            {"id": "1", "nama": "Ritonavir", "smiles": "CC(C)..."},
            {"id": "2", "nama": "Lopinavir", "smiles": "CC1..."},
            {"id": "3", "nama": "Darunavir", "smiles": "CC2..."},
        ]
        self.job = [
            {
                "id": "job_1",
                "mesin": "vina",
                "ligan": [
                    {
                        "id": "1",
                        "nama": "Ritonavir",
                        "status": "selesai",
                        "energi": -11.4,
                        "ki": "4.5 nM",
                        "le": -0.42,
                        "interaksi": {"hbond": 4, "hidrofobik": 6, "pi": 2},
                        "pose": [{"peringkat": 1, "energi": -11.4}],
                    },
                    {
                        "id": "2",
                        "nama": "Lopinavir",
                        "status": "selesai",
                        "energi": -10.2,
                        "ki": "32 nM",
                        "le": -0.38,
                        "interaksi": {"hbond": 3, "hidrofobik": 5, "pi": 1},
                        "pose": [{"peringkat": 1, "energi": -10.2}],
                    },
                    {
                        "id": "3",
                        "nama": "Darunavir",
                        "status": "selesai",
                        "energi": -9.8,
                        "ki": "65 nM",
                        "le": -0.36,
                        "interaksi": {"hbond": 5, "hidrofobik": 4, "pi": 0},
                        "pose": [{"peringkat": 1, "energi": -9.8}],
                    },
                ],
            }
        ]

    def cari_ligan(self, lid):
        for l in self.ligan:
            if l["id"] == lid:
                return l
        return None


def run_tests():
    print("=== Menguji Modul Interpretasi Docking AI ===")
    gagal = 0

    pr = MockProyek()

    # Uji 1: buat_konteks_docking
    teks, data = asisten.buat_konteks_docking(pr)
    if "HIV-1 Protease" in teks and "Ritonavir" in teks and len(data.get("top5", [])) == 3:
        print("OK   buat_konteks_docking menyusun teks dan data terstruktur dengan benar")
    else:
        print("FAIL buat_konteks_docking gagal")
        gagal += 1

    # Uji 2: prompt_ringkasan & prompt_hasil_pembahasan
    p_ringkas = asisten.prompt_ringkasan(teks)
    p_skripsi = asisten.prompt_hasil_pembahasan(teks)
    if "kcal/mol" in p_ringkas and "Hasil dan Pembahasan" in p_skripsi:
        print("OK   Template prompt mengandung instruksi spesifik yang valid")
    else:
        print("FAIL template prompt tidak sesuai")
        gagal += 1

    # Uji 3: interpretasi mode fallback (Pakar Lokal / tanpa Ollama eksternal)
    out_ringkas = asisten.interpretasi(pr, mode="ringkasan")
    if "Ritonavir" in out_ringkas and "-11.4" in out_ringkas and "kcal/mol" in out_ringkas:
        print("OK   interpretasi mode 'ringkasan' menghasilkan narasi akurat")
    else:
        print(f"FAIL interpretasi ringkasan gagal: {out_ringkas[:100]}")
        gagal += 1

    out_pembahasan = asisten.interpretasi(pr, mode="hasil_pembahasan")
    if "Hasil dan Pembahasan" in out_pembahasan and "RMSD" in out_pembahasan and "1.15" in out_pembahasan:
        print("OK   interpretasi mode 'hasil_pembahasan' menyusun draf karya ilmiah lengkap")
    else:
        print(f"FAIL interpretasi hasil_pembahasan gagal: {out_pembahasan[:100]}")
        gagal += 1

    print(f"\nTotal gagal: {gagal}")
    return gagal


if __name__ == "__main__":
    sys.exit(run_tests())
