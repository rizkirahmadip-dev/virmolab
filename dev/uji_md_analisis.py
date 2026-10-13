"""Uji komprehensif analisis MD tingkat lanjut (F2).

Menguji:
1. RLE encode/decode lossless (pulang-pergi).
2. Radius girasi (Rg) konstan (± 0,01 Å) pada rotasi benda kaku.
3. PCA Cα: varians rasio PC1 > 90% pada osilasi 1 sumbu.
4. SASA: Luas permukaan bola analitik 4π(r+r_probe)² ± 2%.
5. SASA: rdFreeSASA vs Shrake-Rupley NumPy selisih < 3%.
6. FEL: Lanskap energi bebas minimum di posisi pusat Gaussian.
7. Klaster konformasi ligan: 2 kelompok terpisah terdeteksi tepat 2 klaster.
8. Block averaging konvergensi: rata-rata dan galat standar.
9. Trajektori nyata dari dev/uji/md_gui/proyek_md.vmd (bila ada; bila tidak, LEWAT dengan pesan).
"""
import math
import unittest
from pathlib import Path

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem

from virmolab.core import md_analisis


class UjiMDAnalisisSintetis(unittest.TestCase):
    def test_01_rle_pulang_pergi(self):
        """RLE encode & decode harus mengembalikan array biner identik."""
        # 1D
        np.random.seed(42)
        arr1 = np.random.choice([0, 1], size=100, p=[0.7, 0.3])
        rle1 = md_analisis.encode_rle(arr1)
        dec1 = md_analisis.decode_rle(rle1)
        np.testing.assert_array_equal(arr1, dec1)

        # 2D matriks
        arr2 = np.random.choice([0, 1], size=(20, 50), p=[0.8, 0.2])
        rle2 = md_analisis.encode_rle(arr2)
        dec2 = md_analisis.decode_rle(rle2)
        np.testing.assert_array_equal(arr2, dec2)

    def test_02_radius_girasi_rotasi_kaku(self):
        """Benda kaku berotasi harus memiliki Rg konstan ± 0,01 Å."""
        # 4 titik piramida dalam nm
        titik = np.array([
            [0.0, 0.0, 0.0],
            [0.2, 0.0, 0.0],
            [0.0, 0.2, 0.0],
            [0.0, 0.0, 0.2],
        ], dtype=float)

        frames = []
        np.random.seed(123)
        for _ in range(50):
            # Matriks rotasi acak
            q = np.random.randn(4)
            q /= np.linalg.norm(q)
            w, x, y, z = q
            R = np.array([
                [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
                [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
                [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y]
            ])
            t = np.random.randn(3) * 0.1  # translasi
            frames.append((titik @ R.T) + t)

        frames = np.array(frames)
        rg_list, warn = md_analisis.radius_girasi(frames, ke_angstrom=10.0)
        self.assertIsNone(warn)
        self.assertEqual(len(rg_list), 50)
        std_rg = float(np.std(rg_list))
        self.assertLess(std_rg, 0.01, f"Rg fluktuasi terlalu besar: {std_rg:.6f} Å")

    def test_03_pca_gerak_satu_sumbu(self):
        """Gerak harmonik satu sumbu harus ditangkap oleh PC1 > 90% varians."""
        n_frame = 60
        n_atom = 10
        t = np.linspace(0, 4 * np.pi, n_frame)

        # Posisi dasar dalam nm
        base = np.zeros((n_atom, 3))
        base[:, 0] = np.linspace(0, 1.0, n_atom)

        frames = []
        for ti in t:
            f = base.copy()
            # Osilasi murni pada sumbu X
            f[:, 0] += 0.2 * np.sin(ti)
            # Noise sangat kecil pada Y dan Z
            f[:, 1] += 0.001 * np.cos(ti)
            frames.append(f)

        frames = np.array(frames)
        hasil_pca = md_analisis.pca(frames, n_komponen=2, ke_angstrom=10.0)
        self.assertIn("varians_rasio", hasil_pca)
        pc1_ratio = hasil_pca["varians_rasio"][0]
        self.assertGreater(pc1_ratio, 0.90, f"PC1 varians rasio {pc1_ratio:.3f} <= 0.90")

    def test_04_sasa_bola_analitik(self):
        """SASA bola tunggal harus mendekati 4π(r + r_probe)² ± 2%."""
        r_atom = 1.70  # Å (Bondi C)
        r_probe = 1.40  # Å (Air)
        r_tot = r_atom + r_probe
        luas_analitik = 4.0 * math.pi * (r_tot ** 2)

        coords_satu = np.array([[0.0, 0.0, 0.0]], dtype=float)
        radii = np.array([r_atom], dtype=float)

        sasa_hitung = md_analisis.sasa_shrake_rupley_numpy(coords_satu, radii, n_titik=360, probe=r_probe)[0]
        selisih_persen = abs(sasa_hitung - luas_analitik) / luas_analitik * 100.0
        self.assertLess(selisih_persen, 2.0, f"Selisih SASA analitik {selisih_persen:.2f}% >= 2%")

    def test_05_sasa_rdfreesasa_vs_numpy(self):
        """Validasi silang rdFreeSASA vs Shrake-Rupley NumPy harus selisih < 3%."""
        mol = Chem.MolFromSmiles("CCO")
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, randomSeed=42)
        conf = mol.GetConformer()
        n_atoms = mol.GetNumAtoms()
        pos = np.array([list(conf.GetAtomPosition(i)) for i in range(n_atoms)], dtype=float)

        radii = np.array([md_analisis.BONDI_VDW.get(a.GetSymbol().upper(), 1.70)
                          for a in mol.GetAtoms()], dtype=float)

        sasa_np = md_analisis.sasa_shrake_rupley_numpy(pos, radii, n_titik=96, probe=1.4)[0]

        if md_analisis.ADA_FREESASA:
            from rdkit.Chem import rdFreeSASA
            opts = rdFreeSASA.SASAOpts(rdFreeSASA.SASAAlgorithm.ShrakeRupley,
                                      rdFreeSASA.SASAClassifier.Protor)
            sasa_rd = rdFreeSASA.CalcSASA(mol, radii.tolist(), -1, None, opts)
            selisih_persen = abs(sasa_np - sasa_rd) / sasa_rd * 100.0
            self.assertLess(selisih_persen, 3.0, f"Selisih rdFreeSASA vs NumPy {selisih_persen:.2f}% >= 3%")
        else:
            self.skipTest("rdFreeSASA tidak tersedia di modul RDKit.")

    def test_06_fel_minimum_di_pusat(self):
        """Distribusi Gaussian 2D berpusat di (0,0) harus memiliki minimum FEL di pusat."""
        np.random.seed(42)
        # 1000 titik berpusat di (0.0, 0.0) dengan simpangan baku 1.0
        proyeksi = np.random.randn(1000, 2)
        hasil_fel = md_analisis.fel(proyeksi, T=300.0, bin=25)

        self.assertIn("min_pos", hasil_fel)
        min_x, min_y = hasil_fel["min_pos"]
        # Jarak minimum dari (0,0) harus kecil (< 0.6)
        dist_pusat = math.hypot(min_x, min_y)
        self.assertLess(dist_pusat, 0.6, f"Minimum FEL ({min_x:.2f}, {min_y:.2f}) jauh dari pusat: dist={dist_pusat:.2f}")

    def test_07_klaster_dua_kelompok_terpisah(self):
        """Dua kelompok konformasi terpisah sejauh 5 Å (ambang 2,0 Å) harus terbagi menjadi 2 klaster."""
        # 1 ligan dengan 3 atom
        konf_a = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.0, 0.1, 0.0]])
        konf_b = konf_a + np.array([0.5, 0.0, 0.0])  # Geser 0.5 nm = 5 Å

        frames = []
        for _ in range(10):
            frames.append(konf_a + np.random.randn(*konf_a.shape) * 0.005)
        for _ in range(10):
            frames.append(konf_b + np.random.randn(*konf_b.shape) * 0.005)

        frames = np.array(frames)
        hasil_klaster = md_analisis.klaster_ligan(frames, idx_ligan=[0, 1, 2], ambang=2.0, ke_angstrom=10.0)

        self.assertEqual(len(hasil_klaster), 2, f"Terdeteksi {len(hasil_klaster)} klaster, diharapkan 2")
        self.assertEqual(hasil_klaster[0]["ukuran"] + hasil_klaster[1]["ukuran"], 20)

    def test_08_blok_rata_konvergensi(self):
        """Block averaging harus menghitung rata-rata tepat dan estimasi galat blok."""
        nilai = [2.0, 2.1, 1.9, 2.0, 2.0, 2.1, 1.9, 2.0, 2.0, 2.0]
        rata, gs = md_analisis.blok_rata(nilai, n_blok=5)
        self.assertAlmostEqual(rata, float(np.mean(nilai)), places=5)
        self.assertGreater(gs, 0.0)

    def test_09_peringatan_data_sedikit(self):
        """Fungsi-fungsi analisis harus memberikan peringatan bila data frame terlalu sedikit."""
        proyeksi_sedikit = np.random.randn(50, 2)
        hasil_fel = md_analisis.fel(proyeksi_sedikit, bin=20)
        self.assertIn("peringatan", hasil_fel)
        self.assertIn("< 500 frame", hasil_fel["peringatan"])


class UjiMDAnalisisNyata(unittest.TestCase):
    def test_10_trajektori_nyata_proyek_vmd(self):
        """Uji trajektori nyata dari dev/uji/md_gui/proyek_md.vmd."""
        folder_vmd = Path("dev/uji/md_gui/proyek_md.vmd")
        if not folder_vmd.exists():
            self.skipTest("dev/uji/md_gui/proyek_md.vmd tidak ditemukan - LEWAT.")

        sub_mk1 = folder_vmd / "md" / "MD20261013_092349" / "MK1_1"
        if not sub_mk1.exists() or not (sub_mk1 / "trajektori_terlarut.dcd").exists():
            self.skipTest("Berkas DCD nyata di dev/uji/md_gui/proyek_md.vmd tidak ditemukan - LEWAT.")

        # Jalankan hitung analisis lanjutan
        hasil = md_analisis.hitung_analisis_lanjutan(sub_mk1, dt_ps=10.0)

        self.assertEqual(hasil.get("versi"), 2)
        self.assertIn("rg", hasil)
        self.assertIn("pca", hasil)
        self.assertIn("fel", hasil)
        self.assertIn("klaster", hasil)
        self.assertIn("konvergensi", hasil)
        self.assertGreater(len(hasil["rg"]), 0)

        # Cek SVG generator
        svg_bc = md_analisis.svg_barcode_interaksi(hasil.get("barcode", {}))
        self.assertTrue(svg_bc.startswith("<svg"))

        svg_f = md_analisis.svg_fel_2d(hasil.get("fel", {}))
        self.assertTrue(svg_f.startswith("<svg"))

        svg_p = md_analisis.svg_pca_sebar(hasil.get("pca", {}))
        self.assertTrue(svg_p.startswith("<svg"))

    def test_11_ikatan_h_dan_okupansi_dengan_mol_ligan(self):
        """Dengan pose ligan ber-ikatan (dari tugas.json), ikatan H MK1–protease harus terdeteksi dan okupansi ≤ 100 %.

        Mengunci dua bug P4: (1) analisis ulang tanpa molekul hanya melihat kontak hidrofobik, (2) jumlah ikatan H
        memakai kode jenis yang salah sehingga selalu 0, dan okupansi dihitung per interaksi sehingga > 100 %.
        """
        import json
        from virmolab.core import md as mdmod
        run = Path("dev/uji/md_gui/proyek_md.vmd/md/MD20261013_092349")
        if not (run / "MK1_1" / "trajektori_terlarut.dcd").exists():
            self.skipTest("Trajektori MK1 nyata tidak ditemukan - LEWAT.")
        tugas = json.loads((run / "tugas.json").read_text(encoding="utf-8"))
        it = next(i for i in tugas["ligan"] if i["nama"] == "MK1")
        if not Path(it["pdbqt_masukan"]).exists():
            self.skipTest("PDBQT masukan MK1 tidak ditemukan - LEWAT.")
        hasil = md_analisis.hitung_analisis_lanjutan(run / "MK1_1", dt_ps=10.0, mol_rdkit=mdmod._mol_pose(it))
        frek = hasil["interaksi_frek"]
        self.assertLessEqual(max(frek.values()), 1.0 + 1e-9, "okupansi melebihi 100 %")
        self.assertTrue(any(k.startswith("ASP 25") and k.endswith("|hbond") for k in frek),
                        f"ikatan H ASP 25 katalitik tidak terdeteksi: {[k for k in frek if 'hbond' in k]}")
        hb = hasil.get("hb_per_frame") or hasil.get("hb") or []
        self.assertGreater(sum(hb) / max(1, len(hb)), 1.0, "rata-rata ikatan H per frame terlalu kecil")


if __name__ == "__main__":
    unittest.main()
