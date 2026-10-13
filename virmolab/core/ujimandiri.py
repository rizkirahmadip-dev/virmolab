"""Uji mandiri instalasi: semua komponen penting bisa dimuat dan dijalankan di laptop ini.

Dipakai dari menu Alat › Uji mandiri komponen dan baris perintah `VirmoLab.exe --uji-mandiri hasil.json`.
"""
import json
import subprocess
import tempfile
import time
from pathlib import Path

from . import paths

NOWIN = 0x08000000


def _jalan(cmd, timeout=60):
    p = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NOWIN)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def uji(lapor=None):
    hasil = []

    def cek(nama, fn):
        t = time.time()
        try:
            detail = fn() or "ok"
            hasil.append({"uji": nama, "ok": True, "detail": str(detail)[:200], "detik": round(time.time() - t, 2)})
        except Exception as e:
            hasil.append({"uji": nama, "ok": False, "detail": f"{type(e).__name__}: {e}"[:300],
                          "detik": round(time.time() - t, 2)})
        if lapor:
            h = hasil[-1]
            lapor.log.emit(f"{'OK   ' if h['ok'] else 'GAGAL'} {nama}: {h['detail']}")

    def program(nama, arg):
        def f():
            exe = paths.program(nama)
            if not exe:
                raise FileNotFoundError(f"{nama} tidak ada di {paths.BIN}")
            kode, out = _jalan([exe] + arg)
            baris = [b for b in out.splitlines() if b.strip()]
            return (baris[0] if baris else f"kode {kode}")
        return f

    cek("AutoDock Vina", program("vina.exe", ["--version"]))
    cek("AutoGrid4", program("autogrid4.exe", ["--version"]))
    cek("AutoDock4", program("autodock4.exe", ["--version"]))
    cek("AutoDock-GPU", program("autodock_gpu.exe", ["--version"]))

    def ob():
        from . import obabel
        return obabel.konversi("CC(=O)Oc1ccccc1C(=O)O\n", "smi", "smi", ["-p", "7.4"]).split()[0]
    cek("Open Babel (obabel)", ob)

    def lig():
        from . import prep_ligan
        h = prep_ligan.siapkan_satu("aspirin", "CC(=O)Oc1ccccc1C(=O)O", "smiles", prep_ligan.OpsiLigan())
        if h.status == "gagal":
            raise RuntimeError(h.alasan)
        return f"RDKit + Meeko: {h.rumus}, {h.torsi} torsi, {h.atom} atom PDBQT"
    cek("Preparasi ligan (RDKit, Meeko)", lig)

    def gem():
        import gemmi
        st = gemmi.read_pdb_string("ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00  0.00           N\nEND\n")
        return f"gemmi {gemmi.__version__}, {st[0].count_atom_sites()} atom"
    cek("gemmi", gem)

    def fitur():
        from rdkit import Chem
        from . import analisis
        f = analisis._fitur(Chem.AddHs(Chem.MolFromSmiles("NCC(=O)O")))
        return "fitur: " + ", ".join(sorted(f))
    cek("Fitur kimia RDKit (interaksi)", fitur)

    def penelitian():
        from rdkit import Chem
        from . import senyawa
        mol = Chem.AddHs(Chem.MolFromSmiles("CC(=O)O"))
        from rdkit.Chem import AllChem
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        umpan = senyawa.umpan(["CC(=O)Oc1ccccc1C(=O)O"], 5, seed=1)
        if len(umpan) < 1:
            raise RuntimeError("umpan kosong")
        return f"regangan {senyawa.regangan(mol):.1f}; umpan {len(umpan)}; makro {senyawa.ada_makrosiklus(Chem.MolFromSmiles('C1CCCCCC1'))}"
    cek("Penelitian (umpan, regangan, makrosiklus)", penelitian)

    def vina_dock():
        from . import prep_ligan
        h = prep_ligan.siapkan_satu("asetat", "CC(=O)O", "smiles", prep_ligan.OpsiLigan(protonasi=False))
        rec = ("ATOM      1  CA  ALA A   1       2.000   0.000   0.000  1.00  0.00     0.000 C \n"
               "ATOM      2  O   ALA A   1      -2.000   0.000   0.000  1.00  0.00    -0.300 OA\n")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "r.pdbqt").write_text(rec)
            (d / "l.pdbqt").write_text(h.pdbqt)
            kode, out = _jalan([paths.program("vina.exe"), "--receptor", str(d / "r.pdbqt"), "--ligand",
                                str(d / "l.pdbqt"), "--center_x", "0", "--center_y", "0", "--center_z", "0",
                                "--size_x", "12", "--size_y", "12", "--size_z", "12", "--exhaustiveness", "1",
                                "--num_modes", "1", "--seed", "1", "--cpu", "1", "--out", str(d / "o.pdbqt")], 120)
            if not (d / "o.pdbqt").exists():
                raise RuntimeError(out.strip().splitlines()[-1] if out.strip() else f"kode {kode}")
            return "docking kecil berhasil"
    cek("Docking Vina mini", vina_dock)

    def flex_dock():
        """Tripeptida Gly-Ser-Gly: Ser2 fleksibel (Meeko) -> Vina --flex -> pose ligan + rantai samping terpisah."""
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from . import mesin as M
        from . import prep_ligan
        from . import prep_reseptor as R
        m = Chem.AddHs(Chem.MolFromSequence("GSG"), addCoords=True)
        AllChem.EmbedMolecule(m, randomSeed=7)
        AllChem.MMFFOptimizeMolecule(m)
        h = R.siapkan(Chem.MolToPDBBlock(Chem.RemoveHs(m)), R.OpsiReseptor(protonasi="templat"))
        kaku, flex, ok, _g = R.buat_fleksibel(h.pdb_meeko, h.pdbqt, ["A:2"])
        lig = prep_ligan.siapkan_satu("asetat", "CC(=O)O", "smiles", prep_ligan.OpsiLigan(protonasi=False))
        xyz = [(float(b[30:38]), float(b[38:46]), float(b[46:54])) for b in flex.splitlines() if b.startswith("ATOM")]
        c = [sum(p[i] for p in xyz) / len(xyz) for i in range(3)]
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for n, t in (("r", kaku), ("f", flex), ("l", lig.pdbqt)):
                (d / f"{n}.pdbqt").write_text(t)
            p = M.Parameter(mesin="vina", exhaustiveness=1, num_modes=1, seed=1, cpu=1)
            kode, out = _jalan(M.perintah_vina(d / "r.pdbqt", d / "l.pdbqt", d / "o.pdbqt",
                                               M.Kotak(pusat=c, ukuran=[14, 14, 14]), p, flex=d / "f.pdbqt"), 120)
            pose = M.baca_vina(d / "o.pdbqt") if (d / "o.pdbqt").exists() else []
            if not pose or not pose[0].flex:
                raise RuntimeError(out.strip().splitlines()[-1] if out.strip() else f"kode {kode}")
            return f"Meeko {', '.join(ok)} ({R.torsi_flex(flex)} torsi) + Vina --flex: {', '.join(M.residu_flex(pose[0].flex))}"
    cek("Residu fleksibel (Meeko + Vina)", flex_dock)

    def kovalen_aduk():
        """Akrilamida + Cys: deteksi gugus reaktif, aduk 3D disejajarkan ke CA/CB, PDBQT flexres (Meeko)."""
        from rdkit import Chem
        from . import kovalen as K
        ca, cb = [0.0, 0.0, 0.0], [1.52, 0.0, 0.0]
        mol = Chem.MolFromSmiles("C=CC(=O)Nc1ccccc1")
        wh = K.deteksi(mol, "CYS")
        if not wh:
            raise RuntimeError("gugus reaktif akrilamida tidak terdeteksi")
        aduk, n, nama = K.buat_aduk(mol, "CYS", ca, cb)
        setup = __import__("meeko", fromlist=["MoleculePreparation"]).MoleculePreparation().prepare(
            aduk, root_atom_index=0, not_terminal_atoms=[0])[0]
        from meeko import PDBQTWriterLegacy
        pdbqt, ok, err = PDBQTWriterLegacy.write_string(setup)
        if not ok:
            raise RuntimeError(str(err)[:150])
        flex = PDBQTWriterLegacy.adapt_pdbqt_for_autodock4_flexres(pdbqt, "CYS", "A", "1")
        if not flex.startswith("BEGIN_RES") or "END_RES" not in flex:
            raise RuntimeError("blok flexres tidak terbentuk")
        return f"{nama}: aduk {aduk.GetNumHeavyAtoms()} atom berat ({n} dari residu) → flexres Meeko"
    cek("Docking kovalen (aduk + Meeko flexres)", kovalen_aduk)

    def md_uji():
        """Tripeptida GSG + etanol: OpenMM (platform terbaik) + ff14SB + OpenFF Sage/NAGL -> minimisasi + MM/GBSA."""
        import math
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from . import md as MD
        from . import prep_reseptor as R
        m = Chem.AddHs(Chem.MolFromSequence("GSG"), addCoords=True)
        AllChem.EmbedMolecule(m, randomSeed=7)
        AllChem.MMFFOptimizeMolecule(m)
        h = R.siapkan(Chem.MolToPDBBlock(Chem.RemoveHs(m)), R.OpsiReseptor(protonasi="templat"))
        lig = Chem.AddHs(Chem.MolFromSmiles("CCO"))
        AllChem.EmbedMolecule(lig, randomSeed=1)
        c = m.GetConformer().GetPositions().mean(0)
        conf = lig.GetConformer()
        for i in range(lig.GetNumAtoms()):
            p = conf.GetAtomPosition(i)
            conf.SetAtomPosition(i, (p.x + c[0] + 4.5, p.y + c[1], p.z + c[2]))
        hasil, (ff, mdl, info, _pos) = MD.mmgbsa_pose(h.pdb_meeko, h.pdbqt, lig)
        if not math.isfinite(hasil["dG"]):
            raise RuntimeError(f"ΔG tidak valid: {hasil['dG']}")
        # air eksplisit: kotak TIP3P + ion + sistem PME (data tip3p.pdb/xml harus ikut terbundel)
        _s, m_air, _n = MD.siapkan_md(ff, mdl, info, MD.OpsiMD(pelarut="eksplisit", padding_nm=0.6))
        n_air = m_air.topology.getNumAtoms() - mdl.topology.getNumAtoms()
        if n_air < 150:
            raise RuntimeError(f"solvasi eksplisit gagal ({n_air} atom air)")
        return (f"OpenMM {MD._versi().get('OpenMM', '')} ({hasil['platform']}), Sage 2.3 + NAGL, OBC2: "
                f"ΔG {hasil['dG']:.1f} kkal/mol, {hasil['detik']:.0f} s; TIP3P/PME +{n_air} atom air")
    cek("MD & MM/GBSA (OpenMM + OpenFF)", md_uji)

    def cli_uji():
        import sys
        if getattr(sys, "frozen", False):
            exe = paths.FOLDER_APP / "VirmoLab-cli.exe"
            if not exe.exists():
                raise RuntimeError("VirmoLab-cli.exe tidak ada di folder aplikasi")
            kode, out = _jalan([exe, "--help"], 60)
        else:
            kode, out = _jalan([sys.executable, "-m", "virmolab.cli", "--help"], 60)
        if kode != 0 or "dock" not in out:
            raise RuntimeError(out.strip().splitlines()[-1] if out.strip() else f"kode {kode}")
        return "VirmoLab-cli: info, uji, reseptor, ligan, kantong, alphafold, dock, mmgbsa"
    cek("Baris perintah (VirmoLab-cli)", cli_uji)

    def gpu():
        from . import env
        e = env.deteksi({})
        g = e.gpu_utama
        return (f"{g.nama} · OpenCL {'ya' if g.opencl else 'tidak'}" if g else "tanpa GPU") + f" · mode {e.mode_bawaan}"
    cek("Deteksi GPU/OpenCL", gpu)

    def xlsx():
        import openpyxl
        return f"openpyxl {openpyxl.__version__}"
    cek("Ekspor Excel", xlsx)

    def sifat_lig():
        from . import sifat
        s = sifat.dari_teks("CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21", "smiles")   # diazepam: GI & BBB
        if not (s["gi"] and s["bbb"] and s["qed"]):
            raise RuntimeError("hasil BOILED-Egg/QED diazepam tidak sesuai")
        kat = sifat._filter("PAINS").GetNumEntries()
        return f"WLOGP {s['wlogp']}, TPSA {s['tpsa']}, PAINS {kat} pola"
    cek("Sifat ligan (QED, PAINS, BOILED-Egg)", sifat_lig)

    def sas_uji():
        from . import sascore
        s_asp = sascore.hitung_sascore("CC(=O)Oc1ccccc1C(=O)O")
        if s_asp is None or not (1.0 <= s_asp <= 2.5):
            raise RuntimeError(f"SAScore aspirin tidak wajar: {s_asp}")
        return f"aspirin {s_asp:.2f} ({sascore.kategori(s_asp)}), RDKit Contrib SA_Score"
    cek("Kemudahan sintesis (SAScore)", sas_uji)

    def stat():
        from . import statistik
        k = statistik.korelasi([1, 2, 3, 4, 5], [2.1, 3.9, 6.2, 8.1, 9.8])
        if not (k["r"] > 0.99 and k["p"] < 0.01):
            raise RuntimeError("korelasi uji tidak sesuai")
        import scipy
        return f"scipy {scipy.__version__}, r {k['r']:.4f}"
    cek("Statistik (scipy)", stat)

    def posebusters():
        import tempfile
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from . import qc
        m = Chem.AddHs(Chem.MolFromSmiles("CC(=O)O"))
        AllChem.EmbedMolecule(m, randomSeed=7)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.pdb"
            f.write_text("ATOM      1  CA  ALA A   1       2.500   2.500   2.500  1.00  0.00           C\nEND\n")
            h = qc.periksa_proses(m, f)          # lewat proses pekerja (--qc-pekerja)
            pek = qc._pek is not None
            qc.tutup()
        geo = {n: ok for _k, n, g, ok in h["uji"] if g == "Geometri"}
        if not geo or not all(geo.values()):
            raise RuntimeError(f"uji geometri asam asetat gagal: {h['gagal']}")
        import posebusters
        return f"posebusters {posebusters.__version__}, {h['n_uji']} uji, proses pekerja {'ya' if pek else 'TIDAK'}"
    cek("Kontrol kualitas pose (PoseBusters)", posebusters)

    def dimorphite():
        from rdkit import Chem
        from . import prep_ligan
        v = prep_ligan.varian_dimorphite(Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O"), 7.4, 1)
        if not v or Chem.GetFormalCharge(v[0]) != -1:
            raise RuntimeError("aspirin pH 7,4 seharusnya bermuatan −1")
        import dimorphite_dl
        return f"dimorphite_dl {getattr(dimorphite_dl, '__version__', '?')}, aspirin −1"
    cek("Protonasi Dimorphite-DL", dimorphite)

    def p2rank_uji():
        import tempfile
        from . import p2rank
        if not p2rank.tersedia():
            raise RuntimeError("bin/p2rank atau bin/jre tidak ada")
        teks = (Path(__file__).resolve().parents[1] / "aset" / "uji_1hsg.pdb")
        if not teks.exists():
            return "terpasang (struktur uji tidak dibawa, prediksi tidak dijalankan)"
        with tempfile.TemporaryDirectory() as d:
            k = p2rank.prediksi(teks.read_text(), d)
        if not k:
            raise RuntimeError("tidak ada kantong")
        return f"P2Rank 2.5.1 + Java 21, kantong #1 skor {k[0]['skor']:.1f}"
    cek("Deteksi kantong (P2Rank)", p2rank_uji)

    def video():
        # FFmpeg (Qt Multimedia) terbundel & encoder H.264 Windows tersedia untuk ekspor video MP4
        from PySide6.QtCore import QCoreApplication
        if QCoreApplication.instance() is None:
            video._app = QCoreApplication([])
        from PySide6.QtMultimedia import QMediaFormat
        f = QMediaFormat(QMediaFormat.FileFormat.MPEG4)
        kodek = f.supportedVideoCodecs(QMediaFormat.ConversionMode.Encode)
        if QMediaFormat.VideoCodec.H264 not in kodek:
            raise RuntimeError("encoder H.264 tidak tersedia (video MP4 tidak bisa dibuat; GIF/WebP tetap bisa)")
        return "MP4 H.264 siap (Qt Multimedia + FFmpeg)"
    cek("Perekam video (MP4 H.264)", video)

    def propka_uji():
        from . import prep_reseptor as R
        teks = Path(__file__).resolve().parents[1] / "aset" / "uji_1hsg.pdb"
        if not teks.exists():
            raise RuntimeError("struktur uji tidak ada")
        h = R.siapkan(teks.read_text(), R.OpsiReseptor(protonasi="propka"))
        if not h.protonasi:
            raise RuntimeError("; ".join(h.peringatan) or "PROPKA tidak berjalan")
        return f"{len(h.protonasi.pka)} gugus pKa, {len(h.protonasi.keadaan)} keadaan tak-baku, {h.atom} atom"
    cek("Protonasi reseptor PROPKA/PDB2PQR", propka_uji)

    def kemiripan_uji():
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from . import kemiripan as K
        m = [K.mol_dari(s, "smi") for s in ("CC(=O)Oc1ccccc1C(=O)O", "OC(=O)c1ccccc1O", "Cn1cnc2c1c(=O)n(C)c(=O)n2C")]
        M = K.matriks([K.sidik_jari(x, "gobbi") for x in m])
        h = Chem.AddHs(m[0])
        AllChem.EmbedMolecule(h, randomSeed=1)
        return f"Tanimoto aspirin-salisilat {M[0][1]:.2f}; farmakofor: {K.ringkas_fitur(K.fitur(h))}"
    cek("Kemiripan & farmakofor (RDKit)", kemiripan_uji)

    def pustaka_uji():
        from . import pustaka
        n = len(pustaka.obat())
        if n < 1000:
            raise RuntimeError(f"pustaka obat hanya {n}")
        return f"{n} obat disetujui; COCONUT {'terpasang' if pustaka.coconut_ada() else 'belum diunduh'}"
    cek("Pustaka ligan", pustaka_uji)

    def ketcher_uji():
        f = paths.KETCHER / "index.html"
        js = list((paths.KETCHER / "static" / "js").glob("609.*.js"))
        if not f.exists() or not js:
            raise RuntimeError(f"Ketcher tidak lengkap di {paths.KETCHER}")
        return "Ketcher 3.18.0 standalone"
    cek("Editor struktur (Ketcher)", ketcher_uji)

    def admet_uji():
        from . import admet
        r = admet.prediksi(["CC(=O)Oc1ccccc1C(=O)O"])
        return f"aspirin HIA {r[0]['HIA_Hou']:.2f}, hERG {r[0]['hERG']:.2f}"
    cek("Prediksi ADMET (ADMET-AI, proses terpisah)", admet_uji)

    def air_termo_uji():
        from . import air_termo
        pdb_mock = ("ATOM      1  N   ASP A   1       0.000   0.000   0.000  1.00 20.00           N\n"
                    "ATOM      2  OD1 ASP A   1       2.500   0.000   0.000  1.00 20.00           O\n"
                    "ATOM      3  CB  LEU A   2      10.000   0.000   0.000  1.00 20.00           C\n"
                    "HETATM    7  O   HOH A 101       1.200   0.000   1.500  1.00 20.00           O\n"
                    "HETATM    8  O   HOH A 102      11.000   0.000   1.200  1.00 20.00           O\nEND\n")
        res = air_termo.analisis_termodinamika_air(pdb_mock)
        if len(res) < 2:
            raise RuntimeError("analisis air gagal")
        return f"{len(res)} molekul air dianalisis (stabil & tidak stabil)"
    cek("Termodinamika air sisi aktif", air_termo_uji)

    def fbdd_uji():
        from . import fbdd
        tg = fbdd.tumbuhkan_fragmen("c1ccccc1O", "Fenol", maks_hasil=5)
        tl = fbdd.sambung_fragmen("c1ccccc1", "c1ccncc1", maks_hasil=5)
        if not tg or not tl:
            raise RuntimeError("FBDD growing/linking gagal")
        return f"growing {len(tg)} analog, linking {len(tl)} hibrida"
    cek("Desain obat berbasis fragmen (FBDD)", fbdd_uji)

    def ppi_uji():
        from . import ppi
        mock_dimer = ("ATOM      1  N   ASP A   1      10.000  10.000  10.000  1.00 20.00           N\n"
                      "ATOM      2  CA  ASP A   1      11.000  10.000  10.000  1.00 20.00           C\n"
                      "TER\n"
                      "ATOM      3  N   ARG B   1      10.500  10.500  12.000  1.00 20.00           N\n"
                      "ATOM      4  CA  ARG B   1      11.000  10.500  13.000  1.00 20.00           C\n"
                      "TER\nEND\n")
        skor = ppi.skor_antarmuka(mock_dimer, "A", "B", cutoff_jarak=5.0)
        return f"kontak {skor.get('kontak_total', 0)}, BSA {skor.get('bsa_luas', 0):.1f} A2"
    cek("Antarmuka protein-protein (PPI)", ppi_uji)

    def protac_uji():
        from . import protac
        hasil = protac.rakit_protac("c1ccccc1C(=O)O", "CRBN_Pomalidomide", "PEG3")
        if not hasil.get("smiles"):
            raise RuntimeError("perakitan PROTAC gagal")
        return f"MW {hasil['mw']} Da, linker {hasil['panjang_linker_est']} A"
    cek("Perancang PROTAC & linker E3", protac_uji)

    def metabolisme_uji():
        from . import metabolisme
        h = metabolisme.prediksi_titik_metabolisme("Cc1ccc(OC)cc1")
        if h.get("jumlah_som", 0) == 0:
            raise RuntimeError("deteksi SoM gagal")
        return f"{h['jumlah_som']} titik SoM, stabilitas {h['skor_stabilitas']}/100"
    cek("Titik metabolisme CYP450 (SoM)", metabolisme_uji)

    def mmp_uji():
        from . import mmp
        lig = [("Toluena", "Cc1ccccc1"), ("Fenol", "Oc1ccccc1")]
        d = {"Toluena": {"energi": -5.2}, "Fenol": {"energi": -6.8}}
        p = mmp.cari_pasangan(lig)
        t = mmp.tabel_rgroup(p, d)
        if not t:
            raise RuntimeError("analisis MMP gagal")
        return f"{len(t)} pasangan matched pair"
    cek("Molecular Matched Pair (MMP)", mmp_uji)

    def kinetika_uji():
        from . import kinetika
        k = kinetika.estimasi_kinetika(-9.5, jum_hbond_terkubur=2, jum_kontak_hidrofobik=10)
        return f"k_off {k['k_off']:.2e} s^-1, tau {k['tau_teks']}"
    cek("Kinetika pengikatan (koff & residence time)", kinetika_uji)

    def labplanner_uji():
        from . import labplanner
        p = labplanner.prediksi_ki_ic50(-8.18)
        return f"Ki {p['ki_teks']}, IC50 {p['ic50_teks']}"
    cek("Perencana uji lab basah (LabPlanner)", labplanner_uji)

    def skrip_publikasi_uji():
        from . import skrip_publikasi
        teks_p = skrip_publikasi.buat_skrip_pymol("rec.pdbqt", "lig.pdbqt", ["ASP25"], "uji_pymol")
        teks_c = skrip_publikasi.buat_skrip_chimerax("rec.pdbqt", "lig.pdbqt", ["ASP25"], "uji_chimerax")
        if not teks_p or not teks_c:
            raise RuntimeError("pembuatan skrip gagal")
        return "PyMOL .pml + ChimeraX .cxc"
    cek("Skrip visualisasi publikasi (PyMOL/ChimeraX)", skrip_publikasi_uji)

    def konsensus_uji():
        from . import konsensus
        kolom = {
            "adgpu": {"l1": -9.0, "l2": -7.0, "l3": -6.0},
            "vina": {"l1": -8.5, "l2": -7.2, "l3": -6.1},
        }
        nama = {"l1": "Ligan 1", "l2": "Ligan 2", "l3": "Ligan 3"}
        r = konsensus.hitung(kolom, nama)
        if len(r.get("baris", [])) < 3:
            raise RuntimeError(r.get("galat") or "perhitungan konsensus gagal")
        w_val = r["W"][0] if r.get("W") else 0.0
        return f"Kendall W {w_val:.2f}, {len(r['baris'])} ligan"
    cek("Konsensus docking & perankingan", konsensus_uji)

    def mpo_uji():
        from . import mpo
        s = {"mw": 250.0, "logp": 2.1, "tpsa": 45.0, "hbd": 1, "hba": 3, "rotb": 2, "qed": 0.82, "sascore": 2.1}
        r = mpo.hitung_mpo(s, dg=-8.2, preset="cns")
        if r.get("skor", 0) <= 0:
            raise RuntimeError("perhitungan MPO gagal")
        return f"skor MPO {r['skor']:.1f}/100 ({r['kategori']})"
    cek("Multi-Parameter Optimization (MPO)", mpo_uji)

    def sanitasi_uji():
        from . import sanitasi_struktur
        dummy_pdbqt = (
            "ATOM      1  C1  LIG A   1       0.000   0.000   0.000  0.00  0.00     0.000 C \n"
            "ATOM      2  C2  LIG A   1       1.500   0.000   0.000  0.00  0.00     0.000 C \n"
        )
        ok, bersih, cat = sanitasi_struktur.validasi_sanitasi_pdbqt(dummy_pdbqt, jenis="ligan")
        if not ok or "ROOT" not in bersih:
            raise RuntimeError("sanitasi PDBQT gagal menambahkan pohon ROOT")
        return f"validasi PDBQT & auto-sanitizer OK ({len(cat)} catatan perbaikan)"
    cek("Sanitasi & integritas PDBQT", sanitasi_uji)

    return hasil


def tulis(path):
    from .. import __version__
    h = uji()
    data = {"versi": __version__, "portable": paths.PORTABLE, "bin": str(paths.BIN), "hasil": h,
            "semua_ok": all(x["ok"] for x in h)}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data["semua_ok"]
