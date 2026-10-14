"""Uji desain generatif terpandu docking (F8).

1. Dari MK1 (indinavir), generasi pertama menghasilkan >= 50 analog yang lolos sanitasi RDKit
   dan tidak ada InChIKey ganda.
2. Penyaringan menolak dengan alasan yang terbaca, dan ambang relatif induk bekerja.
3. Front Pareto benar pada data sintetis yang jawabannya sudah diketahui.
4. Silsilah menghubungkan induk ke anak.
5. Kandidat tanpa ΔG tidak ikut diperingkat, bukan diberi skor pengganti.

LEWAT bila paket crem atau basis data fragmen tidak ada.

Dijalankan: PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_generatif.py
"""
from pathlib import Path
import sys
import unittest

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from rdkit import Chem, RDLogger          # noqa: E402

from virmolab.core import generatif as G  # noqa: E402

RDLogger.DisableLog("rdApp.*")

INFO = G.tersedia()
MK1 = "CC(C)(C)NC(=O)[C@@H]1CN(Cc2cccnc2)CCN1C[C@@H](O)C[C@@H](Cc1ccccc1)C(=O)N[C@H]1c2ccccc2C[C@H]1O"


class UjiPareto(unittest.TestCase):
    """Berlaku tanpa crem: hanya aritmetika peringkat."""

    @staticmethod
    def k(smiles, dg, qed, sa):
        return G.Kandidat(smiles=smiles, dg=dg, qed=qed, sascore=sa)

    def test_front_pareto_pada_data_sintetis(self):
        a = self.k("A", -10.0, 0.8, 2.0)     # terbaik di semua sumbu
        b = self.k("B", -9.0, 0.5, 3.0)      # didominasi A
        c = self.k("C", -11.0, 0.3, 3.5)     # ΔG terbaik, QED terburuk
        d = self.k("D", -8.0, 0.9, 1.5)      # QED dan SA terbaik
        front = G.pareto([a, b, c, d])
        nama = {x.smiles for x in front}
        self.assertEqual(nama, {"A", "C", "D"}, f"front salah: {nama}")
        self.assertNotIn("B", nama, "B didominasi A dan tidak boleh masuk front")
        self.assertEqual(front[0].smiles, "C", "front diurutkan menurut ΔG terendah")

    def test_tanpa_dg_tidak_diperingkat(self):
        a = self.k("A", -10.0, 0.8, 2.0)
        tanpa = self.k("B", None, 0.9, 1.0)
        front = G.pareto([a, tanpa])
        self.assertEqual([x.smiles for x in front], ["A"],
                         "kandidat tanpa ΔG tidak boleh masuk front atau diberi nilai pengganti")

    def test_silsilah_menghubungkan_induk_ke_anak(self):
        anak = [G.Kandidat(smiles="anak1", induk="induk", operasi="mutate", generasi=1),
                G.Kandidat(smiles="anak2", induk="anak1", operasi="grow", generasi=2)]
        s = G.silsilah(anak)
        self.assertEqual(len(s["tepi"]), 2)
        self.assertIn({"dari": "induk", "ke": "anak1", "operasi": "mutate"}, s["tepi"])
        self.assertEqual(len(s["simpul"]), 3)

    def test_paragraf_metode_kosong_tanpa_kandidat(self):
        self.assertEqual(G.paragraf_metode({"kandidat": []}), "")

    def test_operasi_tak_dikenal_ditolak(self):
        with self.assertRaises(ValueError):
            G.generasi("CCO", operasi="acak")


@unittest.skipUnless(INFO["ada"], f"CReM tidak siap: {INFO['pesan']}")
class UjiGenerasiNyata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anak = G.generasi(MK1, operasi="mutate", radius=2, maks=300)

    def test_minimal_50_analog_valid(self):
        self.assertGreaterEqual(len(self.anak), 50, f"hanya {len(self.anak)} analog")

    def test_semua_lolos_sanitasi_rdkit(self):
        for k in self.anak:
            m = Chem.MolFromSmiles(k.smiles)
            self.assertIsNotNone(m, f"SMILES tidak dapat diurai: {k.smiles}")
            Chem.SanitizeMol(m)

    def test_tanpa_duplikat_inchikey(self):
        kunci = [k.inchikey for k in self.anak]
        self.assertTrue(all(kunci), "setiap kandidat harus punya InChIKey")
        self.assertEqual(len(kunci), len(set(kunci)), "ada InChIKey ganda")

    def test_induk_tidak_ikut_sebagai_anak(self):
        induk_kanon = Chem.MolToSmiles(Chem.MolFromSmiles(MK1))
        self.assertNotIn(induk_kanon, [k.smiles for k in self.anak])

    def test_saringan_memberi_alasan_yang_terbaca(self):
        lolos, ditolak = G.saring(self.anak[:60])
        self.assertTrue(ditolak, "sebagian analog seharusnya tertolak")
        for k in ditolak:
            self.assertTrue(k.alasan_tolak, "setiap penolakan harus menyimpan alasannya")
        for k in lolos:
            self.assertIsNotNone(k.qed)
            self.assertIsNotNone(k.sascore)
            self.assertLessEqual(k.kemiripan_induk, G.KEBARUAN_MAKS)

    def test_ambang_relatif_induk_dipakai_untuk_induk_ber_qed_rendah(self):
        """Indinavir ber-QED sekitar 0,24; ambang mutlak 0,4 akan menolak seluruh turunannya."""
        longgar, _ = G.saring(self.anak[:120], relatif_induk=True)
        ketat, _ = G.saring(self.anak[:120], relatif_induk=False)
        self.assertEqual(len(ketat), 0, "ambang mutlak seharusnya menolak semua turunan indinavir")
        self.assertGreater(len(longgar), 0, "ambang relatif induk harus menyisakan kandidat")

    def test_siklus_tanpa_docking_tetap_jujur(self):
        """Tanpa fungsi docking, ΔG tetap kosong dan front Pareto kosong."""
        h = G.siklus(MK1, dock=None, n_generasi=1, maks=120)
        self.assertTrue(h["kandidat"])
        self.assertEqual(h["pareto"], [])
        self.assertTrue(all(k.dg is None for k in h["kandidat"]))
        self.assertIn("basis data fragmen", h["catatan_db"].lower())

    def test_siklus_dengan_docking_palsu_menghitung_kegagalan(self):
        """Kandidat yang gagal di-docking dihitung terpisah, bukan diberi ΔG pengganti."""
        def dock(kandidat, penuh):
            for i, k in enumerate(kandidat):
                k.dg = None if i % 5 == 0 else -7.0 - (i % 7) * 0.3

        h = G.siklus(MK1, dock=dock, n_generasi=1, maks=120)
        self.assertGreater(h["n_gagal_docking"], 0)
        self.assertTrue(all(k.dg is not None for k in h["pareto"]))
        teks = G.paragraf_metode(h)
        self.assertIn("gagal di-docking", teks)
        self.assertIn("CReM", teks)


if __name__ == "__main__":
    if not INFO["ada"]:
        print(f"LEWAT: {INFO['pesan']}")
    unittest.main()
