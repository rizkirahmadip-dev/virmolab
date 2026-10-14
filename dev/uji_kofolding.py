"""Uji konsensus docking dan co-folding Boltz-2 (F6).

Dijalankan atas fixture SINTETIS di dev/data/boltz_1hsg (lihat dev/buat_fixture_boltz.py): yang diuji
adalah pembacaan berkas, penyelarasan, dan pelabelan, BUKAN ketepatan prediksi Boltz-2. Jalur Boltz
sungguhan lewat WSL hanya diuji dengan argumen --daring dan dilewati bila Boltz belum terpasang.

Uji ini mencakup:
1. Pembacaan berkas keluaran resmi Boltz-2 (PDB, affinity JSON, confidence JSON).
2. Penyelarasan koordinat Kabsch Cα kompleks ke kerangka reseptor proyek.
3. Komputasi RMSD simetris atom berat pose docking vs co-folding.
4. Evaluasi PoseBusters dan sidik jari interaksi (IFP Tanimoto).
5. Aturan label kesepakatan konsensus: Sepakat, Sebagian, Bertentangan.
6. Pengecekan kebaruan ligan terhadap data latih PDB.
7. Alur terintegrasi analisis_kofolding pada data riil 1HSG.
"""

from pathlib import Path
import sys
import unittest

from rdkit import Chem

from virmolab.core import kofolding, lanjutan

DARING = "--daring" in sys.argv

AKAR = Path(__file__).resolve().parents[1]
FOLDER_FIXTURE = AKAR / "dev" / "data" / "boltz_1hsg" / "predictions" / "boltz_1hsg"
PDB_RESEPTOR = AKAR / "virmolab" / "aset" / "uji_1hsg.pdb"
SDF_DOCKING = AKAR / "dev" / "uji" / "cli" / "vina" / "pose" / "MK1_902_B_terbaik.sdf"


class UjiKofolding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FOLDER_FIXTURE.exists():
            from dev import buat_fixture_boltz
            buat_fixture_boltz.main()

    def test_01_cari_dan_baca_keluaran_boltz(self):
        """Memastikan pembacaan struktur koordinat dan metrik afinitas/keyakinan Boltz-2."""
        berkas = kofolding.cari_berkas_boltz(FOLDER_FIXTURE)
        self.assertIsNotNone(berkas["pdb"], "Berkas PDB tidak ditemukan")
        self.assertIsNotNone(berkas["affinity"], "Berkas affinity JSON tidak ditemukan")
        self.assertIsNotNone(berkas["confidence"], "Berkas confidence JSON tidak ditemukan")

        data = kofolding.baca_keluaran_boltz(FOLDER_FIXTURE)
        self.assertTrue(len(data["teks_pdb"]) > 0)
        self.assertIsNotNone(data["afinitas_pred_value"])
        self.assertAlmostEqual(data["afinitas_pred_value"], -2.145, places=2)
        self.assertIsNotNone(data["afinitas_probabilitas"])
        self.assertAlmostEqual(data["afinitas_probabilitas"], 0.985, places=2)
        self.assertIsNotNone(data["complex_plddt"])
        self.assertGreater(data["complex_plddt"], 80.0)

    def test_02_superposisi_kabsch_ca(self):
        """Memastikan transformasi koordinat Kabsch memulihkan koordinat ke sistem reseptor."""
        rec_teks = PDB_RESEPTOR.read_text(encoding="utf-8")
        data_boltz = kofolding.baca_keluaran_boltz(FOLDER_FIXTURE)

        kompleks_align, ligan_align, rmsd_ca, n_ca = kofolding.sejajarkan_ke_reseptor(
            data_boltz["teks_pdb"], rec_teks
        )
        self.assertGreater(n_ca, 50, "Jumlah atom Cα bersama harus memadai")
        self.assertLess(rmsd_ca, 1.0, f"RMSD Cα harus rendah, terukur: {rmsd_ca:.3f} Å")
        self.assertTrue(len(ligan_align) > 0, "Ligan harus terdeteksi di koordinat terselaraskan")

    def test_03_rmsd_simetri_ligan(self):
        """Memastikan RMSD atom berat simetris terhadap pose docking terhitung secara presisi."""
        rec_teks = PDB_RESEPTOR.read_text(encoding="utf-8")
        data_boltz = kofolding.baca_keluaran_boltz(FOLDER_FIXTURE)
        _, ligan_align, _, _ = kofolding.sejajarkan_ke_reseptor(data_boltz["teks_pdb"], rec_teks)

        m_cofold = Chem.MolFromPDBBlock(ligan_align)
        m_dock = Chem.SDMolSupplier(str(SDF_DOCKING))[0]

        rmsd = kofolding.hitung_rmsd_pose(m_dock, m_cofold)
        self.assertIsNotNone(rmsd)
        self.assertLess(rmsd, 2.0, f"RMSD MK1 ter-align harus < 2 Å, terukur: {rmsd:.3f} Å")

    def test_04_klasifikasi_label_kesepakatan(self):
        """Memastikan penentuan label konsensus jujur sesuai kriteria tertulis."""
        # Sepakat: RMSD < 2 Å dan kedua QC lolos
        lbl1 = kofolding.label_kesepakatan(1.2, pb_docking_lulus=True, pb_cofold_lulus=True, ifp_tanimoto=0.8)
        self.assertEqual(lbl1, "Sepakat")

        # Sebagian: RMSD < 2 Å tapi salah satu QC gagal
        lbl2 = kofolding.label_kesepakatan(1.2, pb_docking_lulus=True, pb_cofold_lulus=False, ifp_tanimoto=0.8)
        self.assertEqual(lbl2, "Sebagian")

        # Sebagian: RMSD >= 2 Å tapi kontak IFP mirip (≥ 0.6)
        lbl3 = kofolding.label_kesepakatan(2.8, pb_docking_lulus=True, pb_cofold_lulus=True, ifp_tanimoto=0.75)
        self.assertEqual(lbl3, "Sebagian")

        # Bertentangan: RMSD >= 2 Å dan IFP < 0.6
        lbl4 = kofolding.label_kesepakatan(3.5, pb_docking_lulus=True, pb_cofold_lulus=True, ifp_tanimoto=0.2)
        self.assertEqual(lbl4, "Bertentangan")

        # Data kosong / belum dihitung
        lbl5 = kofolding.label_kesepakatan(None)
        self.assertEqual(lbl5, "–")

    def test_05_kebaruan_ligan_pdb(self):
        """Memastikan deteksi kebaruan ligan memberikan nilai Tanimoto dan peringatan bila < 0,3."""
        # Molekul cubane (kebaruan tinggi / kemiripan rendah ke ligan obat PDB)
        smi_aneh = "C12C3C4C1C5C2C3C45"
        skor, per = kofolding.kebaruan_ligan_pdb(smi_aneh)
        self.assertIsNotNone(skor)
        self.assertLessEqual(skor, 0.3)
        self.assertTrue("keyakinan co-folding rendah" in per)

        # Ligan MK1 / Indinavir (ada di PDB -> kemiripan tinggi)
        m_dock = Chem.SDMolSupplier(str(SDF_DOCKING))[0]
        smi_mk1 = Chem.MolToSmiles(Chem.RemoveHs(m_dock))
        skor_mk1, per_mk1 = kofolding.kebaruan_ligan_pdb(smi_mk1)
        self.assertIsNotNone(skor_mk1)

    def test_06_alur_utuh_analisis_kofolding(self):
        """Memastikan alur analisis_kofolding menghasilkan dataclass HasilKofolding yang lengkap."""
        rec_teks = PDB_RESEPTOR.read_text(encoding="utf-8")
        m_dock = Chem.SDMolSupplier(str(SDF_DOCKING))[0]
        smiles = Chem.MolToSmiles(Chem.RemoveHs(m_dock))

        hasil = kofolding.analisis_kofolding(
            folder_atau_berkas_boltz=FOLDER_FIXTURE,
            reseptor_pdb=rec_teks,
            mol_docking=m_dock,
            smiles=smiles,
            path_reseptor_pdb=PDB_RESEPTOR,
        )

        self.assertTrue(hasil.tersedia)
        self.assertIsNotNone(hasil.rmsd)
        self.assertLess(hasil.rmsd, 2.0)
        self.assertIsNotNone(hasil.afinitas_pred_value)
        self.assertIsNotNone(hasil.afinitas_probabilitas)
        self.assertIn(hasil.kesepakatan, ("Sepakat", "Sebagian"))
        self.assertTrue(len(hasil.pdb_ligan_terselaraskan) > 0)

        # Uji serialisasi ke dict
        d = hasil.to_dict()
        self.assertTrue(isinstance(d, dict))
        self.assertEqual(d["kesepakatan"], hasil.kesepakatan)

    def test_07_penanganan_kegagalan_tanpa_data_karangan(self):
        """Memastikan folder rusak atau keluaran kosong menghasilkan status gagal yang jelas tanpa angka karangan."""
        folder_palsu = AKAR / "dev" / "data" / "folder_tidak_ada_123"
        rec_teks = PDB_RESEPTOR.read_text(encoding="utf-8")
        m_dock = Chem.SDMolSupplier(str(SDF_DOCKING))[0]

        hasil = kofolding.analisis_kofolding(
            folder_atau_berkas_boltz=folder_palsu,
            reseptor_pdb=rec_teks,
            mol_docking=m_dock,
        )
        self.assertFalse(hasil.tersedia)
        self.assertIn("Gagal membaca", hasil.pesan)
        self.assertIsNone(hasil.rmsd, "RMSD harus None bila gagal, bukan 0.0 atau 99")
        self.assertEqual(hasil.kesepakatan, "–")


class UjiParagrafMetode(unittest.TestCase):
    """Paragraf metode harus dirakit dari hitungan nyata dan diam bila belum ada data."""

    @staticmethod
    def _kalimat(peta):
        from virmolab.ui.dialog_konsensus import DialogKonsensus

        class Palsu:
            hasil = {"peta_kofold": peta}

        return DialogKonsensus._kalimat_kofolding(Palsu())

    def test_tanpa_data_tidak_mengklaim_apa_pun(self):
        self.assertEqual(self._kalimat({}), "")
        self.assertEqual(self._kalimat({"a": {"kesepakatan": "–"}}), "")

    def test_jumlah_sesuai_data(self):
        t = self._kalimat({"a": {"kesepakatan": "Sepakat"}, "b": {"kesepakatan": "Sepakat"},
                           "c": {"kesepakatan": "Bertentangan"}, "d": {"kesepakatan": "–"}})
        self.assertIn("3 ligan", t)
        self.assertIn("2 sepakat", t)
        self.assertIn("1 bertentangan", t)
        self.assertNotIn("sebagian", t)
        self.assertIn("kebocoran data latih", t)


class UjiBoltzDaring(unittest.TestCase):
    """Jalur WSL sungguhan. Tanpa --daring uji ini dilewati, bukan dinyatakan lulus."""

    @unittest.skipUnless(DARING, "butuh --daring dan Boltz-2 terpasang di WSL")
    def test_status_boltz_nyata(self):
        st = lanjutan.status_boltz()
        if not st.get("ada"):
            self.skipTest(f"Boltz belum terpasang: {st.get('pesan', '')}")
        self.assertTrue(st.get("jalur"), "status_boltz melaporkan ada tetapi tanpa jalur")

    @unittest.skipUnless(DARING, "butuh --daring dan Boltz-2 terpasang di WSL")
    def test_nama_kunci_afinitas_nyata(self):
        """Cocokkan nama kunci JSON afinitas dengan keluaran Boltz sungguhan.

        Fixture memakai nama kunci dari skema terdokumentasi. Bila rilis Boltz memakai nama lain,
        pembacaan diam-diam kosong, jadi perbedaannya harus ketahuan di sini."""
        st = lanjutan.status_boltz()
        if not st.get("ada"):
            self.skipTest(f"Boltz belum terpasang: {st.get('pesan', '')}")
        self.skipTest("Belum ada keluaran Boltz sungguhan di mesin ini untuk dibandingkan")


if __name__ == "__main__":
    unittest.main(argv=[a for a in sys.argv if a != "--daring"])
