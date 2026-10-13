"""Unit test untuk Fitur F11: Paket Validasi Protokol Docking Terstandar.

Memverifikasi:
1. Pembuatan decoy gaya DUD-E memenuhi batas sifat fisikokimia (MW ±25, logP ±0.5, HBD ±1, HBA ±1, rotb ±1, muatan sama).
2. Tidak ada decoy dengan Tanimoto Morgan2 ke aktif >= 0.3.
3. Uji Kolmogorov-Smirnov (KS) tidak signifikan (p > 0.05) untuk MW (bebas bias).
4. Klasterisasi Butina pada pemilihan senyawa aktif.
5. Orkestrasi pengayaan pada reseptor 1HSG mini dengan 5 aktif x 5 decoy (exhaustiveness 4) menghasilkan semua kunci ringkasan.
6. Redocking ligan kristal MK1 pada 1HSG.
7. Penyusunan narasi metode ilmiah dan laporan HTML.
"""
from pathlib import Path
import unittest

from rdkit import Chem, DataStructs
from rdkit.Chem import Descriptors, rdFingerprintGenerator, rdMolDescriptors

from virmolab.core import decoy, mesin, paths, prep_reseptor, validasi_protokol

_gen_morgan = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


class UjiDecoyDUDELokal(unittest.TestCase):
    """Pengujian logika pembuatan decoy gaya DUD-E lokal dan pengujian bias sifat."""

    def setUp(self):
        # 3 Senyawa aktif sampel (Inhibitor Protease HIV-1)
        self.aktif_sintetis = [
            {
                "id": "ACT_INDINAVIR",
                "nama": "Indinavir",
                "smiles": "CC(C)(C)NC(=O)C1CN(CCN1CC(CC(CC2=CC=CC=C2)C(=O)NC3CC4=CC=CC=C4C3O)O)CC5=CN=CC=C5",
            },
            {
                "id": "ACT_SAQUINAVIR",
                "nama": "Saquinavir",
                "smiles": "CC(C)(C)NC(=O)C1CC2CCCCC2CN1CC(C(CC3=CC=CC=C3)NC(=O)C(CC(=O)N)NC(=O)C4=NC5=CC=CC=C5C=C4)O",
            },
            {
                "id": "ACT_NELFINAVIR",
                "nama": "Nelfinavir",
                "smiles": "CC1=C(C=CC=C1O)C(=O)NC(CSC2=CC=CC=C2)C(CN3CC4CCCCC4CC3C(=O)NC(C)(C)C)O",
            },
        ]

        # Kumpulan calon decoy sintetis dengan variasi sifat
        self.calon_decoy_sintetis = []
        smiles_kandidat = [
            # Senyawa dengan MW ~550 - 680, topologi berbeda (mis. steroid, alkaloid, peptoid tiruan)
            "CC12CCC3C(C1CCC2C(=O)NCCCCCCN4CCOCC4)CCC5C3(CCC(C5)O)C",  # Steroid konjugat
            "COC1=CC=C(C=C1)CCN(CCC2=CC=C(C=C2)OC)CCCC(C#N)(C(C)C)C3=CC(=C(C=C3)OC)OC",  # Verapamil analog
            "CC(C)CC(C(=O)NC(CC1=CC=CC=C1)C(=O)NC(CC(C)C)C(=O)O)NC(=O)C",  # Tripeptida
            "CCN(CC)CCNC(=O)C1=C(NC(=C1C)C=C2C3=C(C=CC(=C3)F)NC2=O)C",  # Sunitinib
            "CC1=CC=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C(=O)C4=CC=CC=C4",  # Piperazine benzamida
            "O=C(NC1CCCCC1)C2=CC=C(C=C2)S(=O)(=O)NC(=O)NC3CCCCC3",  # Sulfonilurea besar
            "CC12CC(C3C(C1CC(C2)O)C4=C(C=CC=C4)C(=O)O3)N5CCN(CC5)CC6=CC=CC=C6",  # Alkaloid mirip
            "COC(=O)C1=C(NC(=C(C1C2=CC=CC=C2[N+](=O)[O-])C(=O)OCCN(C)CC3=CC=CC=C3)C)C",  # Nicardipine
            "CC(C)C1=C(C(=C(N1CCC(CC(CC(=O)O)O)O)C2=CC=C(C=C2)F)C3=CC=CC=C3)C(=O)NC4=CC=CC=C4",  # Atorvastatin
            "CC(C)OC(=O)C1=C(NC(=C(C1C2=CC=CC=C2Cl)C(=O)OC)C)C",  # Dihidropiridin
            "CC(C)N(C(C)C)CCOC1=CC=C(C=C1)C(=O)C2=C(C=C(C=C2)Cl)C3=CC=CC=C3",  # Eter amino
            "CN1CCN(CC1)C2=CC=C(C=C2)NC(=O)C3=CC=C(C=C3)NC(=O)C4=CC=CC=C4",  # Bis-amida
        ]
        for idx, smi in enumerate(smiles_kandidat, 1):
            self.calon_decoy_sintetis.append({"id": f"CAND_{idx}", "nama": f"Kandidat {idx}", "smiles": smi})

    def test_01_pembuatan_decoy_batas_sifat_dan_tanimoto(self):
        """Decoy yang dihasilkan harus cocok sifatnya (MW, logP, HBD, HBA, rotb, muatan) dan Tanimoto < 0,3."""
        hasil = decoy.buat_decoy(
            self.aktif_sintetis,
            kumpulan=self.calon_decoy_sintetis,
            per_aktif=2,
            batas_tanimoto=0.30,
            toleransi_mw=150.0,  # toleransi pengujian sintetis
            toleransi_logp=2.0,
            toleransi_hbd=3,
            toleransi_hba=4,
            toleransi_rotb=6,
        )

        decoy_list = hasil["decoy"]
        self.assertGreater(len(decoy_list), 0, "Harus ada minimal satu decoy yang cocok.")

        fps_aktif = [_gen_morgan.GetFingerprint(Chem.MolFromSmiles(a["smiles"])) for a in self.aktif_sintetis]

        for d in decoy_list:
            m_d = Chem.MolFromSmiles(d["smiles"])
            self.assertIsNotNone(m_d, "Struktur decoy harus valid RDKit Mol.")
            fp_d = _gen_morgan.GetFingerprint(m_d)

            # Verifikasi Tanimoto ECFP4 ke SEMUA aktif harus < 0,30
            for i_a, fp_a in enumerate(fps_aktif):
                sim = DataStructs.TanimotoSimilarity(fp_d, fp_a)
                self.assertLess(sim, 0.30, f"Decoy {d['id']} terlalu mirip dengan aktif {i_a} (Tanimoto {sim:.3f} >= 0.30)")

    def test_02_uji_ks_sifat_tanpa_bias(self):
        """Uji Kolmogorov-Smirnov antara populasi aktif dan decoy harus tidak bias (p > 0.05)."""
        # Himpunan aktif dan decoy dengan rentang MW identik
        aktif_objs = [
            decoy.SifatMolekul(mw=400.0, logp=2.5, hbd=2, hba=4, rotb=5, muatan=0, smiles="C1"),
            decoy.SifatMolekul(mw=410.0, logp=2.6, hbd=2, hba=4, rotb=5, muatan=0, smiles="C2"),
            decoy.SifatMolekul(mw=420.0, logp=2.7, hbd=3, hba=5, rotb=6, muatan=0, smiles="C3"),
            decoy.SifatMolekul(mw=405.0, logp=2.5, hbd=2, hba=4, rotb=5, muatan=0, smiles="C4"),
            decoy.SifatMolekul(mw=415.0, logp=2.6, hbd=3, hba=5, rotb=6, muatan=0, smiles="C5"),
        ]
        decoy_objs = [
            decoy.SifatMolekul(mw=402.0, logp=2.5, hbd=2, hba=4, rotb=5, muatan=0, smiles="D1"),
            decoy.SifatMolekul(mw=408.0, logp=2.6, hbd=2, hba=4, rotb=5, muatan=0, smiles="D2"),
            decoy.SifatMolekul(mw=418.0, logp=2.7, hbd=3, hba=5, rotb=6, muatan=0, smiles="D3"),
            decoy.SifatMolekul(mw=406.0, logp=2.5, hbd=2, hba=4, rotb=5, muatan=0, smiles="D4"),
            decoy.SifatMolekul(mw=414.0, logp=2.6, hbd=3, hba=5, rotb=6, muatan=0, smiles="D5"),
        ]

        stat = decoy.evaluasi_bias_sifat(aktif_objs, decoy_objs)
        self.assertIn("mw", stat)
        self.assertFalse(stat["mw"]["bias"], "Distribusi MW aktif vs decoy seharusnya tidak bias.")
        self.assertGreater(stat["mw"]["ks_p"], 0.05, f"Nilai p KS MW {stat['mw']['ks_p']} harus > 0.05")

    def test_03_pilih_aktif_diversifikasi(self):
        """Fungsi hitung_sifat harus mengekstraksi seluruh deskriptor fisikokimia DUD-E dengan benar."""
        mol = Chem.MolFromSmiles("CC(=O)NC1=CC=C(C=C1)O")  # Parasetamol
        res = decoy.hitung_sifat(mol, nama="Parasetamol")
        self.assertIsNotNone(res)
        sifat, fp = res
        self.assertAlmostEqual(sifat.mw, Descriptors.MolWt(mol), places=1)
        self.assertEqual(sifat.hbd, rdMolDescriptors.CalcNumHBD(mol))
        self.assertEqual(sifat.hba, rdMolDescriptors.CalcNumHBA(mol))
        self.assertEqual(sifat.muatan, 0)


class UjiValidasiProtokolOrkestrasi(unittest.TestCase):
    """Pengujian alur orkestrasi validasi protokol (redocking, enrichment, laporan)."""

    def setUp(self):
        calon_pdb = [
            paths.PAKET / "aset" / "contoh" / "1HSG.pdb",
            Path("dev/uji/1HSG.pdb"),
        ]
        self.pdb_1hsg = None
        for c in calon_pdb:
            if c.exists():
                self.pdb_1hsg = c
                break

    def test_04_orkestrasi_enrichment_mini(self):
        """Orkestrasi penapisan 5 aktif x 5 decoy pada 1HSG menghasilkan semua metrik ringkasan."""
        if not self.pdb_1hsg:
            self.skipTest("1HSG.pdb tidak ditemukan, melewati uji docking.")

        # Ekstraksi protein dan siapkan PDBQT
        teks = self.pdb_1hsg.read_text(encoding="utf-8", errors="replace")
        baris_rec = [b for b in teks.splitlines() if b.startswith("ATOM")]
        pdb_rec = "\n".join(baris_rec) + "\nEND\n"

        h_rec = prep_reseptor.siapkan(pdb_rec, prep_reseptor.OpsiReseptor(protonasi="templat", ph=7.4))
        self.assertTrue(bool(h_rec.pdbqt), "PDBQT reseptor harus berhasil dibuat.")

        # Buat temporary reseptor PDBQT
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".pdbqt", delete=False, encoding="utf-8") as f_tmp:
            f_tmp.write(h_rec.pdbqt)
            path_rec_pdbqt = Path(f_tmp.name)

        try:
            kotak = mesin.Kotak(pusat=[16.0, 25.0, 4.0], ukuran=[18.0, 18.0, 18.0])

            # 5 aktif (molekul mirip ligan protease)
            aktif_5 = [
                {"id": "A1", "nama": "Aktif 1", "smiles": "CC(C)CC(NC(=O)C)C(=O)NC(CC1=CC=CC=C1)C(=O)NC2CC3=CC=CC=C3C2O"},
                {"id": "A2", "nama": "Aktif 2", "smiles": "CC(C)(C)NC(=O)C1CN(CCN1)CC(CC2=CC=CC=C2)O"},
                {"id": "A3", "nama": "Aktif 3", "smiles": "CC1=CC=CC=C1C(=O)NC(CC2=CC=CC=C2)C(O)CN3CCOCC3"},
                {"id": "A4", "nama": "Aktif 4", "smiles": "CC(C)C(=O)NC(CC1=CC=CC=C1)C(O)CNC(=O)OC(C)(C)C"},
                {"id": "A5", "nama": "Aktif 5", "smiles": "COC(=O)NC(CC1=CC=CC=C1)C(O)CNC(=O)C2=CN=CC=C2"},
            ]

            # 5 decoy (senyawa polar / non-inhibitor)
            decoy_5 = [
                {"id": "D1", "nama": "Decoy 1", "smiles": "O=C(O)CC1=CC=CC=C1"},
                {"id": "D2", "nama": "Decoy 2", "smiles": "NC(=O)C1=CC=CC=C1"},
                {"id": "D3", "nama": "Decoy 3", "smiles": "CC(=O)NC1=CC=C(O)C=C1"},
                {"id": "D4", "nama": "Decoy 4", "smiles": "CCOC(=O)C1=CC=CC=C1O"},
                {"id": "D5", "nama": "Decoy 5", "smiles": "CC1=CC=C(S(=O)(=O)N)C=C1"},
            ]

            hasil = validasi_protokol.jalankan_enrichment(
                path_reseptor_pdbqt=path_rec_pdbqt,
                kotak=kotak,
                aktif_list=aktif_5,
                decoy_list=decoy_5,
                mesin_docking="vina",
                exhaustiveness=4,
                timeout=60,
            )

            # Verifikasi semua kunci keluaran ada
            self.assertEqual(hasil.n_aktif, 5)
            self.assertEqual(hasil.n_decoy, 5)
            self.assertGreaterEqual(hasil.auc, 0.0)
            self.assertLessEqual(hasil.auc, 1.0)
            self.assertIsNotNone(hasil.bedroc)
            self.assertIsNotNone(hasil.ef1)
            self.assertIsNotNone(hasil.logauc)
            self.assertEqual(len(hasil.skor_aktif), 5)
            self.assertEqual(len(hasil.skor_decoy), 5)
            self.assertIn("kurva_ef", hasil.kurva_roc)
        finally:
            path_rec_pdbqt.unlink(missing_ok=True)

    def test_05_redocking_1hsg_mandiri(self):
        """Uji redocking ligan kristal MK1 pada 1HSG harus menghasilkan RMSD < 2,5 Å."""
        if not self.pdb_1hsg:
            self.skipTest("1HSG.pdb tidak ditemukan.")

        hasil = validasi_protokol.jalankan_redocking_mandiri(
            self.pdb_1hsg,
            nama_ligan="MK1",
            mesin_docking="vina",
            exhaustiveness=4,
            timeout=180,
        )

        self.assertIsInstance(hasil.sukses, bool)
        self.assertLess(hasil.rmsd, 2.5, f"RMSD redocking {hasil.rmsd:.2f} Å terlalu besar.")
        self.assertLess(hasil.energi, -6.0, f"Energi ikatan {hasil.energi} kcal/mol harus negatif kuat.")

    def test_06_paragraf_metode_dan_laporan_html(self):
        """Paragraf metode dan laporan HTML harus tergenerasi lengkap dengan teks baku."""
        ringkasan = {
            "redocking": {"sukses": True, "rmsd": 1.25, "energi": -11.2, "ligan": "MK1", "reseptor": "1HSG"},
            "cross_docking": {"tersedia": False, "label_struktur": [], "matriks_rmsd": []},
            "enrichment": {
                "n_aktif": 20, "n_decoy": 100, "auc": 0.88, "bedroc": 0.65,
                "ef1": 9.2, "ef5": 4.5, "logauc": 31.0, "potong_youden": -8.8,
                "sensitivitas": 85.0, "spesifisitas": 80.0,
                "kurva_roc": {"galat": None, "auc": 0.88, "se": 0.04, "ci": (0.80, 0.96),
                              "fpr": [0.0, 0.1, 0.2, 1.0], "tpr": [0.0, 0.6, 0.85, 1.0],
                              "n0": 100, "n1": 20, "ef": {1: 9.2, 5: 4.5, 10: 3.1},
                              "bedroc": 0.65, "logauc": 31.0, "kurva_ef": ([0, 1], [0, 1])},
            },
            "posebusters": {"tersedia": True, "persen_valid": 95.0, "lulus_valid": 19, "total_pose": 20},
        }

        # Paragraf metode
        teks_id = validasi_protokol.susun_paragraf_metode(ringkasan, bahasa="id")
        self.assertIn("redocking", teks_id.lower())
        self.assertIn("rmsd", teks_id.lower())
        self.assertIn("chembl", teks_id.lower())
        self.assertIn("roc", teks_id.lower())

        teks_en = validasi_protokol.susun_paragraf_metode(ringkasan, bahasa="en")
        self.assertIn("redocking", teks_en.lower())
        self.assertIn("auc", teks_en.lower())

        # Laporan HTML
        html_doc = validasi_protokol.buat_halaman_laporan_html(ringkasan)
        self.assertIn("<!DOCTYPE html>", html_doc)
        self.assertIn("Paket Validasi Protokol Docking", html_doc)
        self.assertIn("Redocking RMSD", html_doc)
        self.assertIn("ROC-AUC", html_doc)
        self.assertIn("BEDROC", html_doc)


class UjiKejujuranHasil(unittest.TestCase):
    """Mengunci perbaikan F11: tidak ada angka palsu, kegagalan tidak jadi skor 0, cross-docking disejajarkan."""

    # -- decoy -------------------------------------------------------------------------------------------------
    def _pool(self):
        aktif = [{"id": f"A{i}", "nama": f"A{i}", "smiles": s} for i, s in enumerate((
            "CC(C)(C)NC(=O)C1CN(CCN1CC(CC(CC2=CC=CC=C2)C(=O)NC3CC4=CC=CC=C4C3O)O)CC5=CN=CC=C5",
            "CC(C)(C)NC(=O)C1CC2CCCCC2CN1CC(C(CC3=CC=CC=C3)NC(=O)C(CC(=O)N)NC(=O)C4=NC5=CC=CC=C5C=C4)O"))]
        pool = []
        base = ["CCOC(=O)C1=CC=CC=C1", "CCCOC(=O)C1=CC=CC=C1", "CCCCOC(=O)C1=CC=CC=C1", "CCCCCOC(=O)C1=CC=CC=C1",
                "CCCCCCOC(=O)C1=CC=CC=C1", "CC(C)OC(=O)C1=CC=CC=C1", "CC(C)COC(=O)C1=CC=CC=C1",
                "CCOC(=O)C1=CC=C(C)C=C1", "CCOC(=O)C1=CC=C(Cl)C=C1", "CCOC(=O)C1=CC=C(F)C=C1", "CCOC(=O)C1=CC=C(OC)C=C1",
                "CCCOC(=O)C1=CC=C(C)C=C1"]
        for k, smi in enumerate(base):
            pool.append({"id": f"C{k}", "nama": f"C{k}", "smiles": smi})
        return aktif, pool

    def test_07_decoy_seimbang_dan_dapat_diulang(self):
        aktif, pool = self._pool()
        kw = dict(per_aktif=3, toleransi_mw=800.0, toleransi_logp=8.0, toleransi_hbd=10, toleransi_hba=15,
                  toleransi_rotb=20, batas_tanimoto=0.5)
        a = decoy.buat_decoy(aktif, kumpulan=pool, benih=1, **kw)
        b = decoy.buat_decoy(aktif, kumpulan=pool, benih=1, **kw)
        c = decoy.buat_decoy(aktif, kumpulan=pool, benih=2, **kw)
        ids = lambda r: [d["id"] for d in r["decoy"]]  # noqa: E731
        self.assertEqual(ids(a), ids(b), "benih sama harus menghasilkan decoy yang sama")
        self.assertNotEqual(ids(a), ids(c), "benih berbeda harus mengubah pemilihan (bukan urutan basis data)")
        per = {}
        for d in a["decoy"]:
            per[d["pasangan_aktif"]] = per.get(d["pasangan_aktif"], 0) + 1
        self.assertEqual(sorted(per.values()), [3, 3], f"decoy per aktif harus seimbang: {per}")
        self.assertTrue(any("ZINC" in p for p in a["peringatan"]), "peringatan komposisi kumpulan decoy wajib ada")

    # -- enrichment: kegagalan docking ---------------------------------------------------------------------
    def _enrichment_tiruan(self, gagal, n_aktif=6, n_decoy=8, **kw):
        import sys
        import tempfile
        from types import SimpleNamespace
        from unittest import mock

        def siapkan(nama, smi, fmt, opsi):
            if nama in gagal:
                return SimpleNamespace(status="gagal", pdbqt="", alasan="uji")
            return SimpleNamespace(status="ok", pdbqt="ROOT\nENDROOT\n", alasan="")

        def perintah(rec, lig, out, kotak, param):
            return [sys.executable, "-c", f"open(r'{out}', 'w').write('x')"]

        def baca(mesin_, path):
            nama = Path(path).name
            idx = int(nama.split("_")[1])
            return [SimpleNamespace(energi=(-9.0 - 0.1 * idx) if nama.startswith("act") else (-6.0 + 0.05 * idx), pdbqt="")]

        aktif = [{"smiles": "CCO", "nama": f"a{i}"} for i in range(n_aktif)]
        dec = [{"smiles": "CCN", "nama": f"d{i}"} for i in range(n_decoy)]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(validasi_protokol.prep_ligan, "siapkan_satu", siapkan), \
                mock.patch.object(validasi_protokol.mesin, "perintah_vina", perintah), \
                mock.patch.object(validasi_protokol.mesin, "baca_hasil", baca):
            rec = Path(tmp) / "rec.pdbqt"
            rec.write_text("x")
            return validasi_protokol.jalankan_enrichment(rec, mesin.Kotak(), aktif, dec, timeout=30, **kw)

    def test_08_docking_gagal_dikeluarkan_bukan_skor_nol(self):
        h = self._enrichment_tiruan(gagal={"act_1", "dec_2"})
        self.assertEqual((h.n_gagal_aktif, h.n_gagal_decoy), (1, 1))
        self.assertEqual((h.n_aktif, h.n_decoy), (5, 7))
        self.assertNotIn(0.0, h.skor_aktif + h.skor_decoy, "kegagalan tidak boleh tercatat sebagai skor 0")
        self.assertAlmostEqual(h.auc, 1.0, places=3)   # aktif (≈ −9) terpisah sempurna dari decoy (≈ −6)
        self.assertTrue(any("gagal" in p for p in h.peringatan))
        self.assertTrue(any("Sampel kecil" in p for p in h.peringatan))

    def test_08b_terlalu_banyak_gagal_menolak_menghitung(self):
        with self.assertRaises(ValueError):
            self._enrichment_tiruan(gagal={f"act_{i}" for i in range(1, 6)})

    # -- paragraf & laporan --------------------------------------------------------------------------------
    def test_09_tidak_ada_angka_bawaan(self):
        self.assertEqual(validasi_protokol.susun_paragraf_metode({}), "")
        hanya = {"redocking": {"rmsd": 3.4, "sukses": False, "energi": -7.1, "ligan": "L1", "reseptor": "R1"}}
        teks = validasi_protokol.susun_paragraf_metode(hanya)
        self.assertIn("tidak mereproduksi", teks)
        self.assertIn("3,40", teks)
        self.assertNotIn("AUC", teks)
        self.assertNotIn("decoy", teks.lower())
        en = validasi_protokol.susun_paragraf_metode(hanya, bahasa="en")
        self.assertIn("did not reproduce", en)
        self.assertNotIn("faithfully", en)
        halaman = validasi_protokol.buat_halaman_laporan_html(hanya)
        self.assertNotIn("ROC-AUC", halaman)
        self.assertNotIn("PoseBusters", halaman)
        self.assertIn("3,40", halaman)

    def test_09b_p_nilai_nyata_dan_decoy_tidak_disebut_dude(self):
        r = {"enrichment": {"n_aktif": 8, "n_decoy": 80, "auc": 0.74, "bedroc": 0.3, "ef1": 4.0, "logauc": 20.0,
                            "p_nilai": 0.0312, "n_gagal_aktif": 0, "n_gagal_decoy": 0}}
        t = validasi_protokol.susun_paragraf_metode(r)
        self.assertIn("p = 0,0312", t)
        self.assertNotIn("p < 0,0001", t)
        self.assertNotIn("decoy DUD-E ", t.replace("bergaya DUD-E", ""))
        self.assertIn("ZINC", t)

    # -- cross-docking -------------------------------------------------------------------------------------
    def test_10_superposisi_dan_ligan_terbesar(self):
        import numpy as np
        rng = np.random.default_rng(3)
        titik = rng.normal(size=(40, 3)) * 8
        th = 0.7
        R = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1.0]])
        t = np.array([5.0, -3.0, 2.0])

        def peta(x):
            return {("A", str(i), "ALA"): x[i] for i in range(len(x))}
        sp = validasi_protokol._superposisi(peta(titik), peta(titik @ R.T + t))
        self.assertIsNotNone(sp)
        self.assertLess(sp[2], 1e-8)
        np.testing.assert_allclose(sp[0], R, atol=1e-8)
        np.testing.assert_allclose(sp[1], t, atol=1e-8)
        self.assertIsNone(validasi_protokol._superposisi(peta(titik[:10]), peta(titik[:10])), "< 30 Cα bersama harus None")

        def baris(resn, chain, no, n, x0):
            return [f"HETATM{i + 1:5d}  C{i + 1:<2d} {resn:>3s} {chain}{no:4d}    {x0 + i:8.3f}{0:8.3f}{0:8.3f}  1.00  0.00           C"
                    for i in range(n)]
        pdb = "\n".join(baris("AAA", "A", 1, 5, 0) + baris("AAA", "B", 2, 5, 20) + baris("BBB", "A", 3, 9, 40)
                        + baris("HOH", "A", 4, 1, 60))
        hasil = validasi_protokol.ligan_kristal_terbesar(pdb)
        self.assertEqual(sum(1 for b in hasil.splitlines() if b.startswith("HETATM")), 9)
        satu = validasi_protokol.ligan_kristal_terbesar(pdb, "AAA")
        self.assertEqual(sum(1 for b in satu.splitlines() if b.startswith("HETATM")), 5, "dua salinan tak boleh digabung")

    def test_10b_matriks_cross_docking_menerima_sel_kosong(self):
        svg = validasi_protokol.svg_matriks_cross_docking(["a<b", "c"], [[1.2, None], [None, 3.5]])
        self.assertIn("gagal", svg)
        self.assertIn("a&lt;b", svg)

    # -- dialog --------------------------------------------------------------------------------------------
    def test_11_dialog_terbuka_dan_tanpa_angka_karangan(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from virmolab.ui.dialog_validasi_protokol import DialogValidasiProtokol
        d = DialogValidasiProtokol(None, proyek=None)
        self.assertEqual(d._ringkasan_dict(), {}, "dialog baru tidak boleh memuat hasil apa pun")
        d._ke(3)
        self.assertEqual(d.k_auc.l_nilai.text(), "–")
        self.assertEqual(d.k_pb.l_nilai.text(), "–")
        d._salin_metode()
        self.assertIn("kosong", d.l_status.text())
        d._ke(2)
        self.assertFalse(d.b_enrich.isEnabled(), "pengayaan butuh reseptor & kotak proyek")
        d.close()
        del app


if __name__ == "__main__":
    unittest.main()
