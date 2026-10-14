"""Uji docking peptida (F10).

Fixture dev/data/boltz_1ycr memakai koordinat NYATA dari struktur kristal 1YCR (MDM2-p53) dengan
peptida digeser rigid; lihat dev/buat_fixture_peptida.py. Yang diuji di sini adalah validasi sekuens,
pembacaan kompleks, penentuan rantai peptida, RMSD Ca terhadap kristal, dan analisis antarmuka.
Ketepatan prediksi Boltz-2 TIDAK diuji di sini; jalur WSL sungguhan hanya berjalan dengan --daring.

Dijalankan: PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_peptida.py [--daring]
"""
from pathlib import Path
import sys
import unittest

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from virmolab.core import kofolding, peptida            # noqa: E402

DARING = "--daring" in sys.argv
FOLDER_FIXTURE = AKAR / "dev" / "data" / "boltz_1ycr"
PDB_KRISTAL = AKAR / "dev" / "data" / "1YCR.pdb"
SEKUENS_P53 = "ETFSDLWKLLPEN"
AMBANG_RMSD = 3.0


class UjiValidasiSekuens(unittest.TestCase):
    def test_sekuens_baku_diterima(self):
        v = peptida.validasi_sekuens(SEKUENS_P53)
        self.assertTrue(v["sah"], v["pesan"])
        self.assertEqual(v["panjang"], 13)
        self.assertEqual(v["posisi_galat"], [])
        self.assertEqual(v["peringatan"], "")

    def test_spasi_dan_baris_baru_dibersihkan(self):
        v = peptida.validasi_sekuens(" etf sdl\nwkllpen ")
        self.assertTrue(v["sah"])
        self.assertEqual(v["sekuens"], SEKUENS_P53)

    def test_huruf_tak_dikenal_ditandai_posisinya(self):
        v = peptida.validasi_sekuens("ETJSDLWK")
        self.assertFalse(v["sah"])
        self.assertEqual(v["posisi_galat"], [2])
        self.assertIn("J", v["pesan"])

    def test_batas_panjang_ditegakkan(self):
        v = peptida.validasi_sekuens("A" * (peptida.PANJANG_MAKS + 5))
        self.assertFalse(v["sah"])
        self.assertIn(str(peptida.PANJANG_MAKS), v["pesan"])
        self.assertEqual(v["posisi_galat"][0], peptida.PANJANG_MAKS)
        self.assertFalse(peptida.validasi_sekuens("A")["sah"])
        self.assertFalse(peptida.validasi_sekuens("")["sah"])

    def test_residu_tak_baku_diterima_dengan_peringatan(self):
        v = peptida.validasi_sekuens("ETFSDXWKLLP")
        self.assertTrue(v["sah"])
        self.assertIn("tidak baku", v["peringatan"])


class UjiKompleksPeptida(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FOLDER_FIXTURE.exists() or not PDB_KRISTAL.exists():
            raise unittest.SkipTest("Fixture 1YCR belum dibuat (jalankan dev/buat_fixture_peptida.py)")
        cls.pdb = kofolding.baca_keluaran_boltz(FOLDER_FIXTURE)["teks_pdb"]
        cls.kristal = PDB_KRISTAL.read_text(encoding="utf-8")

    def test_sekuens_rantai_terbaca_benar(self):
        rantai = dict(peptida.sekuens_dari_pdb(self.pdb))
        self.assertEqual(rantai["B"], SEKUENS_P53)
        self.assertEqual(len(rantai["A"]), 85)

    def test_rantai_peptida_ditebak_dari_panjang(self):
        self.assertEqual(peptida.tebak_rantai_peptida(self.pdb, len(SEKUENS_P53)), "B")

    def test_rmsd_ca_peptida_di_bawah_ambang(self):
        """Peptida fixture digeser rigid, jadi RMSD-nya kecil tetapi bukan nol."""
        rmsd = peptida.rmsd_ca(self.kristal, self.pdb, "B", "B")
        self.assertIsNotNone(rmsd)
        self.assertGreater(rmsd, 0.1, "Fixture seharusnya digeser, bukan salinan persis")
        self.assertLess(rmsd, AMBANG_RMSD, f"RMSD Ca peptida {rmsd} Å melebihi {AMBANG_RMSD} Å")

    def test_rmsd_jumlah_atom_beda_mengembalikan_none(self):
        self.assertIsNone(peptida.rmsd_ca(self.kristal, self.pdb, "A", "B"))
        self.assertIsNone(peptida.rmsd_ca(self.kristal, self.pdb, "Z", "B"))

    def test_antarmuka_mdm2_p53_masuk_akal(self):
        """Antarmuka MDM2-p53 terkubur luas; angka nol berarti rantai salah dipilih."""
        ant = peptida.analisis_antarmuka(self.pdb, "B")
        self.assertNotIn("error", ant)
        self.assertEqual({ant["rantai_a"], ant["rantai_b"]}, {"A", "B"})
        self.assertGreater(ant["kontak_total"], 50)
        self.assertGreater(ant["bsa_luas"], 300)
        self.assertTrue(any("PHE" in r or "TRP" in r or "LEU" in r for r in ant["residu_b"]),
                        "Tiga residu jangkar p53 (Phe19, Trp23, Leu26) harus muncul di antarmuka")

    def test_pisahkan_rantai(self):
        pep, sisa = peptida.pisahkan_rantai(self.pdb, "B")
        self.assertTrue(all(b[21] == "B" for b in pep.splitlines() if b.startswith("ATOM")))
        self.assertTrue(all(b[21] != "B" for b in sisa.splitlines() if b.startswith("ATOM")))

    def test_analisis_tanpa_pemurnian_tidak_mengarang_angka(self):
        """Tanpa pemurnian, MM/GBSA dan geseran harus kosong, bukan 0,0."""
        h = peptida.analisis_peptida(FOLDER_FIXTURE, SEKUENS_P53, murni=False)
        self.assertTrue(h.tersedia, h.pesan)
        self.assertEqual(h.rantai_peptida, "B")
        self.assertIsNone(h.mmgbsa)
        self.assertIsNone(h.rmsd_minimisasi)
        self.assertIsNotNone(h.antarmuka)

    def test_sekuens_tak_sah_ditolak_sebelum_dijalankan(self):
        h = peptida.analisis_peptida(FOLDER_FIXTURE, "ETJSDL", murni=False)
        self.assertFalse(h.tersedia)
        self.assertIn("J", h.pesan)


class UjiYamlBoltzPeptida(unittest.TestCase):
    def test_peptida_jadi_rantai_protein_bukan_ligan(self):
        from virmolab.core.lanjutan import _yaml_boltz
        y = _yaml_boltz([("A", "MKV")], None, peptida=SEKUENS_P53)
        self.assertIn(SEKUENS_P53, y)
        self.assertNotIn("ligand", y, "Peptida tidak boleh dikirim sebagai ligan bermolekul kecil")

    def test_id_rantai_peptida_tidak_bentrok(self):
        from virmolab.core.lanjutan import _yaml_boltz
        y = _yaml_boltz([("P", "MKV"), ("Q", "GG")], None, peptida="AAA")
        baris_id = [b.strip() for b in y.splitlines() if b.strip().startswith("id:")]
        self.assertEqual(len(baris_id), len(set(baris_id)), f"id rantai bentrok: {baris_id}")

    def test_tanpa_ligan_dan_tanpa_peptida_ditolak(self):
        from virmolab.core.lanjutan import _yaml_boltz
        with self.assertRaises(ValueError):
            _yaml_boltz([("A", "MKV")], None)


class UjiBoltzDaring(unittest.TestCase):
    """Jalur WSL sungguhan; tanpa --daring dilewati, bukan dinyatakan lulus."""

    @unittest.skipUnless(DARING, "butuh --daring dan Boltz-2 terpasang di WSL")
    def test_cofold_peptida_nyata(self):
        import tempfile

        from virmolab.core import lanjutan
        st = lanjutan.status_boltz()
        if not st.get("ada"):
            self.skipTest(f"Boltz belum terpasang: {st.get('pesan', '')}")
        rantai = [(c, s) for c, s in peptida.sekuens_dari_pdb(PDB_KRISTAL.read_text(encoding="utf-8"))
                  if c == "A"]
        with tempfile.TemporaryDirectory() as d:
            peptida.cofold_peptida(rantai, SEKUENS_P53, d)
            h = peptida.analisis_peptida(d, SEKUENS_P53, murni=False)
            self.assertTrue(h.tersedia, h.pesan)
            rmsd = peptida.rmsd_ca(PDB_KRISTAL.read_text(encoding="utf-8"), h.pdb_kompleks, "B",
                                   h.rantai_peptida)
            self.assertIsNotNone(rmsd, "RMSD Ca tidak terhitung terhadap kristal 1YCR")
            self.assertLess(rmsd, AMBANG_RMSD)


if __name__ == "__main__":
    unittest.main(argv=[a for a in sys.argv if a != "--daring"])
