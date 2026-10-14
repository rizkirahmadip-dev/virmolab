"""Uji energi bebas relatif alkimia (F9, eksperimental).

1. Pemetaan atom benzena ke toluena: enam atom cincin terpetakan, satu atom berubah.
2. Jaringan perturbasi bintang dan pohon rentang minimum tersusun benar.
3. MBAR memulihkan selisih energi bebas yang jawabannya diketahui secara analitis.
4. Penutupan siklus menandai jaringan yang tidak konsisten.
5. Estimasi waktu tidak menebak bila kecepatan mesin belum diukur.
6. Status mesin simulasi dilaporkan apa adanya di Windows.

Dijalankan: PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_rbfe.py [--daring --gpu]
"""
from pathlib import Path
import sys
import unittest

import numpy as np

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from rdkit import RDLogger            # noqa: E402

from virmolab.core import rbfe        # noqa: E402

RDLogger.DisableLog("rdApp.*")
DARING = "--daring" in sys.argv and "--gpu" in sys.argv

SERI = [("benzena", "c1ccccc1"), ("toluena", "Cc1ccccc1"),
        ("etilbenzena", "CCc1ccccc1"), ("klorobenzena", "Clc1ccccc1")]


class UjiPemetaanAtom(unittest.TestCase):
    def test_benzena_ke_toluena(self):
        """Cincin benzena utuh terpetakan; hanya gugus metil yang berubah."""
        pm = rbfe.peta_atom("c1ccccc1", "Cc1ccccc1")
        self.assertEqual(pm["n_bersama"], 6, f"cincin tidak terpetakan penuh: {pm}")
        self.assertEqual(pm["n_berubah"], 1, "hanya satu atom berat yang berbeda")
        self.assertEqual(len(pm["peta"]), 6)
        self.assertTrue(pm["mcs_smarts"])

    def test_pemetaan_simetris_untuk_molekul_sama(self):
        pm = rbfe.peta_atom("Cc1ccccc1", "Cc1ccccc1")
        self.assertEqual(pm["n_berubah"], 0)
        self.assertEqual(pm["n_bersama"], 7)

    def test_struktur_tak_valid_tidak_mengarang(self):
        pm = rbfe.peta_atom("bukan smiles", "Cc1ccccc1")
        self.assertEqual(pm["peta"], {})
        self.assertTrue(pm["pesan"])


class UjiJaringan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasangan = rbfe.pasangan_dari_mmp(SERI)

    def test_pasangan_punya_jumlah_atom_berubah(self):
        self.assertTrue(self.pasangan)
        for p in self.pasangan:
            self.assertGreaterEqual(p.n_berubah, 0)
            self.assertTrue(p.peta or p.pesan, "pasangan tanpa peta harus menyebut sebabnya")

    def test_mst_menghubungkan_semua_simpul(self):
        j = rbfe.jaringan(self.pasangan, "mst")
        self.assertEqual(j["mode"], "mst")
        self.assertGreaterEqual(len(j["tepi"]), len(j["simpul"]) - 1)
        self.assertEqual(j["pesan"], "", "jaringan seri kongenerik seharusnya terhubung")

    def test_bintang_berpusat_pada_satu_senyawa(self):
        j = rbfe.jaringan(self.pasangan, "bintang")
        self.assertEqual(j["mode"], "bintang")
        pusat = j["pusat"]
        for t in j["tepi"]:
            self.assertIn(pusat, (t.a, t.b), "setiap tepi bintang harus menyentuh pusat")

    def test_perturbasi_di_atas_batas_ditandai_dan_dikeluarkan(self):
        """Batas 0 atom berubah menolak semua pasangan nyata; tepi bertanda tidak masuk jaringan."""
        ketat = rbfe.pasangan_dari_mmp(SERI, maks_berubah=0)
        ditandai = [p for p in ketat if p.pesan]
        self.assertTrue(ditandai, "perubahan di atas batas harus ditandai, bukan diam-diam dipakai")
        for p in ditandai:
            self.assertIn("melebihi batas", p.pesan)
        j = rbfe.jaringan(ketat, "mst")
        self.assertEqual(j["tepi"], [], "tepi bermasalah tidak boleh masuk jaringan")
        self.assertIn("layak", j["pesan"])


class UjiMbar(unittest.TestCase):
    """MBAR diuji pada sistem yang jawabannya diketahui secara analitis."""

    @staticmethod
    def _data_geser(c, n=400, benih=0):
        """Dua keadaan dengan potensial sama tetapi digeser tetapan c (tanpa satuan).

        Distribusi sampelnya identik, sehingga ΔG analitisnya tepat sama dengan c.
        """
        rng = np.random.default_rng(benih)
        x = rng.normal(0.0, 1.0, 2 * n)
        u0 = 0.5 * x ** 2
        u = np.vstack([u0, u0 + c])
        return u, [n, n]

    def test_memulihkan_selisih_yang_diketahui(self):
        for c in (0.0, 1.5, -2.25):
            u, n = self._data_geser(c)
            h = rbfe.analisis_mbar(u, n, suhu=1.0 / rbfe.K_BOLTZMANN_KKAL)
            self.assertIsNotNone(h["dg"], h["pesan"])
            self.assertAlmostEqual(h["dg"], c, places=6,
                                   msg=f"ΔG {h['dg']} seharusnya {c}")
            self.assertIsNotNone(h["galat"])

    def test_bentuk_matriks_salah_ditolak(self):
        u, n = self._data_geser(1.0)
        h = rbfe.analisis_mbar(u, [10, 10])
        self.assertIsNone(h["dg"])
        self.assertIn("tidak cocok", h["pesan"])


class UjiPenutupanSiklus(unittest.TestCase):
    @staticmethod
    def tepi(a, b, ddg):
        p = rbfe.Perturbasi(a=a, b=b)
        p.ddg = ddg
        return p

    def test_siklus_konsisten(self):
        t = [self.tepi("A", "B", 1.0), self.tepi("B", "C", 0.5), self.tepi("C", "A", -1.5)]
        hasil = rbfe.tutup_siklus(t)
        self.assertEqual(len(hasil), 1)
        self.assertAlmostEqual(hasil[0]["jumlah"], 0.0)
        self.assertTrue(hasil[0]["konsisten"])

    def test_siklus_tidak_konsisten_ditandai(self):
        t = [self.tepi("A", "B", 1.0), self.tepi("B", "C", 0.5), self.tepi("C", "A", 1.5)]
        hasil = rbfe.tutup_siklus(t, toleransi=1.0)
        self.assertEqual(len(hasil), 1)
        self.assertAlmostEqual(hasil[0]["jumlah"], 3.0)
        self.assertFalse(hasil[0]["konsisten"])

    def test_tepi_tanpa_ddg_dilewati(self):
        t = [self.tepi("A", "B", 1.0), self.tepi("B", "C", 0.5), rbfe.Perturbasi(a="C", b="A")]
        self.assertEqual(rbfe.tutup_siklus(t), [])


class UjiEstimasiDanStatus(unittest.TestCase):
    def test_estimasi_tanpa_kecepatan_tidak_menebak(self):
        e = rbfe.estimasi_waktu(5)
        self.assertIsNone(e["jam"])
        self.assertIsNone(e["hari"])
        self.assertGreater(e["total_ns"], 0)
        self.assertIn("belum", e["pesan"])

    def test_estimasi_dengan_kecepatan_terukur(self):
        e = rbfe.estimasi_waktu(2, n_lambda=11, n_replika=3, ns_per_lambda=5.0, ns_per_hari=10.0)
        self.assertAlmostEqual(e["total_ns"], 330.0)
        self.assertAlmostEqual(e["hari"], 33.0)
        self.assertAlmostEqual(e["jam"], 792.0)

    def test_status_mesin_jujur(self):
        st = rbfe.status_mesin()
        self.assertIn("ada", st)
        self.assertTrue(st["pesan"])
        if sys.platform.startswith("win") and not st["ada"]:
            self.assertIn("Windows", st["pesan"])

    def test_paragraf_metode_berlabel_eksperimental(self):
        j = rbfe.jaringan(rbfe.pasangan_dari_mmp(SERI), "mst")
        teks = rbfe.paragraf_metode(j)
        self.assertIn("Eksperimental", teks)
        self.assertIn("substruktur bersama maksimum", teks)
        self.assertEqual(rbfe.paragraf_metode({"tepi": []}), "")


class UjiSimulasiNyata(unittest.TestCase):
    @unittest.skipUnless(DARING, "butuh --daring --gpu dan mesin RBFE yang terpasang")
    def test_jalankan_tepi(self):
        st = rbfe.status_mesin()
        if not st["ada"]:
            self.skipTest(st["pesan"])
        self.skipTest("Belum ada mesin RBFE yang terpasang pada mesin ini untuk diuji.")


if __name__ == "__main__":
    unittest.main(argv=[a for a in sys.argv if a not in ("--daring", "--gpu")])
