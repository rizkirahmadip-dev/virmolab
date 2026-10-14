"""Uji sifat elektronik xTB (F7).

Memeriksa kebenaran kimia, bukan sekadar "tidak crash":
1. Celah HOMO-LUMO benzena > anilin (gugus amino menaikkan HOMO sehingga celah menyempit).
2. f(-) anilin terbesar di posisi orto dan para, bukan meta (anilin pengarah orto/para).
3. Benzena simetris: momen dipolnya nol dan semua karbonnya punya Fukui yang sama.
4. Deskriptor turunan (kekerasan, potensial kimia, elektrofilisitas) konsisten dengan HOMO dan LUMO.
5. Kegagalan mengembalikan None beserta sebab, bukan angka.

LEWAT seluruhnya bila xtb tidak terpasang.

Dijalankan: PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_xtb.py
"""
from pathlib import Path
import sys
import unittest

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from rdkit import Chem                       # noqa: E402
from rdkit.Chem import AllChem               # noqa: E402

from virmolab.core import xtb                # noqa: E402

INFO = xtb.tersedia()
ADA = INFO["ada"]


def mol3d(smiles, benih=42):
    m = Chem.AddHs(Chem.MolFromSmiles(smiles))
    if AllChem.EmbedMolecule(m, randomSeed=benih) != 0:
        AllChem.EmbedMolecule(m, useRandomCoords=True, randomSeed=benih)
    AllChem.MMFFOptimizeMolecule(m)
    return m


@unittest.skipUnless(ADA, f"xtb tidak terpasang: {INFO['pesan']}")
class UjiDeskriptorElektronik(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.benzena = xtb.hitung(mol3d("c1ccccc1"), nama="benzena")
        cls.anilin = xtb.hitung(mol3d("Nc1ccccc1"), nama="anilin")
        for h in (cls.benzena, cls.anilin):
            if not h.tersedia:
                raise unittest.SkipTest(f"xtb gagal: {h.pesan}")

    def test_celah_benzena_lebih_besar_dari_anilin(self):
        """Gugus amino mendonorkan elektron, menaikkan HOMO, sehingga celah anilin menyempit."""
        self.assertIsNotNone(self.benzena.celah_ev)
        self.assertIsNotNone(self.anilin.celah_ev)
        self.assertGreater(self.benzena.celah_ev, self.anilin.celah_ev,
                           f"celah benzena {self.benzena.celah_ev} harus > anilin {self.anilin.celah_ev}")
        self.assertGreater(self.benzena.celah_ev, 3.0)
        self.assertLess(self.benzena.celah_ev, 8.0)

    def test_fukui_anilin_terbesar_di_orto_dan_para(self):
        """f(-) menandai kerentanan terhadap serangan elektrofil; anilin mengarahkan ke orto dan para."""
        m = mol3d("Nc1ccccc1")
        n_idx = next(a.GetIdx() for a in m.GetAtoms() if a.GetSymbol() == "N")
        ipso = next(t.GetIdx() for t in m.GetAtomWithIdx(n_idx).GetNeighbors() if t.GetIsAromatic())
        cincin = [a.GetIdx() for a in m.GetAtoms() if a.GetIsAromatic() and a.GetSymbol() == "C"]
        # GetShortestPath menolak atom ke dirinya sendiri, jadi ipso (jarak 0) dikeluarkan
        jarak = {i: len(Chem.GetShortestPath(m, ipso, i)) - 1 for i in cincin if i != ipso}
        f_minus = {f["indeks"]: f["minus"] for f in self.anilin.fukui}

        orto = [f_minus[i] for i, d in jarak.items() if d == 1]
        meta = [f_minus[i] for i, d in jarak.items() if d == 2]
        para = [f_minus[i] for i, d in jarak.items() if d == 3]
        self.assertTrue(orto and meta and para, f"posisi cincin tidak lengkap: {jarak}")
        self.assertGreater(min(para), max(meta), f"para {para} harus > meta {meta}")
        self.assertGreater(min(orto), max(meta), f"orto {orto} harus > meta {meta}")

    def test_benzena_simetris(self):
        """Molekul simetris: dipol nol dan keenam karbon punya f(-) yang sama."""
        self.assertIsNotNone(self.benzena.dipol_debye)
        self.assertLess(abs(self.benzena.dipol_debye), 0.1)
        karbon = [f["minus"] for f in self.benzena.fukui if f["simbol"].upper() == "C"]
        self.assertEqual(len(karbon), 6)
        self.assertLess(max(karbon) - min(karbon), 0.01, f"karbon benzena tidak setara: {karbon}")

    def test_deskriptor_turunan_konsisten(self):
        h = self.benzena
        self.assertAlmostEqual(h.kekerasan_ev, (h.lumo_ev - h.homo_ev) / 2, places=3)
        self.assertAlmostEqual(h.potensial_kimia_ev, (h.homo_ev + h.lumo_ev) / 2, places=3)
        self.assertAlmostEqual(h.elektrofilisitas_ev,
                               h.potensial_kimia_ev ** 2 / (2 * h.kekerasan_ev), places=3)
        self.assertGreater(h.elektrofilisitas_ev, 0)

    def test_muatan_dan_esp_terbaca(self):
        self.assertEqual(len(self.benzena.muatan), 12)
        self.assertLess(abs(sum(self.benzena.muatan)), 0.05, "jumlah muatan parsial harus mendekati nol")
        self.assertIsNotNone(self.benzena.esp)
        self.assertEqual(self.benzena.esp.shape[1], 4)
        self.assertGreater(len(self.benzena.esp), 50)
        jarak = (self.benzena.esp[:, :3] ** 2).sum(axis=1) ** 0.5
        self.assertLess(jarak.max(), 20.0, "titik ESP harus dalam Angstrom, bukan Bohr")

    def test_paragraf_metode_menyebut_batasan(self):
        t = xtb.paragraf_metode(self.benzena)
        self.assertIn("GFN2-xTB", t)
        self.assertIn("Bukan DFT", t)
        self.assertEqual(xtb.paragraf_metode(xtb.HasilXtb()), "")

    def test_hitung_banyak_paralel(self):
        mols = [(mol3d(s), s) for s in ("c1ccccc1", "CO", "CCO")]
        hasil = xtb.hitung_banyak(mols, esp=False, n_proses=2)
        self.assertEqual(len(hasil), 3)
        self.assertTrue(all(h["tersedia"] for h in hasil), [h.get("pesan") for h in hasil])
        self.assertTrue(all(h["catatan"].endswith("Bukan DFT.") for h in hasil))


class UjiTanpaAngkaKarangan(unittest.TestCase):
    """Berlaku juga ketika xtb tidak terpasang."""

    def test_molekul_tanpa_koordinat_gagal_bersih(self):
        m = Chem.MolFromSmiles("CCO")
        h = xtb.hitung(m, nama="tanpa 3D")
        self.assertFalse(h.tersedia)
        self.assertIsNone(h.celah_ev)
        self.assertIsNone(h.elektrofilisitas_ev)
        self.assertTrue(h.pesan)

    def test_pelarut_tak_dikenal_ditolak(self):
        h = xtb.hitung(mol3d("CCO") if ADA else Chem.MolFromSmiles("CCO"), pelarut="air")
        self.assertFalse(h.tersedia)
        self.assertIn("air", h.pesan)

    def test_korelasi_som_tanpa_data_tidak_menyimpulkan(self):
        r = xtb.korelasi_som(xtb.HasilXtb(), [1, 2])
        self.assertEqual(r["cocok"], [])
        self.assertIn("Belum ada", r["pesan"])

    def test_json_rusak_oleh_jalur_berkutip_tetap_terbaca(self):
        """xtb 6.7.1 menulis program call tanpa melarikan tanda kutip bila jalurnya berspasi."""
        import tempfile

        rusak = ('{\n "total energy": -15.87,\n'
                 ' "program call": ""C:\\Program Files\\xtb.exe" mol.xyz --json",\n'
                 ' "method": "GFN2-xTB"\n}\n')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "xtbout.json"
            p.write_text(rusak, encoding="utf-8")
            d_json = xtb._baca_json_xtb(p)
        self.assertEqual(d_json.get("method"), "GFN2-xTB")
        self.assertAlmostEqual(d_json.get("total energy"), -15.87)


if __name__ == "__main__":
    if not ADA:
        print(f"LEWAT: {INFO['pesan']}")
    unittest.main()
