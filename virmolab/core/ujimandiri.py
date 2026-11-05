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
    # Satu QApplication untuk seluruh uji: butir tema butuh widget, sedangkan butir video membuat QCoreApplication
    # bila belum ada, dan satu proses hanya boleh punya satu aplikasi Qt.
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication(["VirmoLab"])          # noqa: F841 - dijaga hidup selama uji

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
        # versi dari metadata, bukan `import posebusters`: impor itu membangun pabrik fitur RDKit dari jalur berkas
        # di proses ini (lihat qc._fdef_lewat_python) dan gagal di folder ber-huruf non-ASCII
        from importlib.metadata import PackageNotFoundError, version
        try:
            versi = version("posebusters")
        except PackageNotFoundError:          # metadata paket tidak ikut dibundel
            versi = "?"
        return f"posebusters {versi}, {h['n_uji']} uji, proses pekerja {'ya' if pek else 'TIDAK'}"
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

    def batal_tanaman_uji():
        """Bendera pembatalan menerima Event maupun fungsi.

        Regresi: ui/dialog_tanaman.py mengirim threading.Event sedangkan core/tanaman.py memanggilnya
        seperti fungsi, sehingga "Ambil senyawa" gagal dengan TypeError: 'Event' object is not callable
        begitu takson punya rujukan artikel (sejak 1.8.0, ketahuan pada Curcuma zedoaria).
        """
        import threading
        from . import tanaman
        e = threading.Event()
        if tanaman.dibatalkan(e) or tanaman.dibatalkan(None) or tanaman.dibatalkan(lambda: False):
            raise RuntimeError("bendera belum di-set tetapi dibaca sebagai batal")
        e.set()
        if not (tanaman.dibatalkan(e) and tanaman.dibatalkan(lambda: True)):
            raise RuntimeError("bendera sudah di-set tetapi tidak dibaca sebagai batal")
        return "Event, fungsi, dan None diterima"
    cek("Pembatalan pengambilan senyawa tanaman", batal_tanaman_uji)

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

    def panel_target_uji():
        """Panel penargetan balik ikut terpasang dan tiap entri punya reseptor + statistik umpan (bukan nilai bawaan)."""
        from . import target_balik
        kelas = target_balik.daftar_kelas_panel()
        if not kelas:
            raise RuntimeError("panel target tidak ikut terpasang")
        rincian = []
        for k in kelas:
            sah, lewat = target_balik.muat_panel_sah(k)
            if not sah:
                raise RuntimeError(f"panel '{k}' tanpa entri sah ({len(lewat)} dilewati)")
            rincian.append(f"{k}: {len(sah)} target" + (f", {len(lewat)} dilewati" if lewat else ""))
        return "; ".join(rincian)
    cek("Panel target penargetan balik", panel_target_uji)

    def pengayaan_uji():
        """Set gen bawaan terpasang dan uji hipergeometrik + BH memberi hasil yang benar pada contoh kecil."""
        import math
        from . import pengayaan
        gmt = pengayaan.gmt_bawaan("reactome")
        if len(gmt) < 500:
            raise RuntimeError(f"berkas GMT Reactome tidak lengkap ({len(gmt)} set)")
        latar = [f"G{i}" for i in range(1, 21)]
        contoh = {"S": {"nama": "set uji", "gen": {"G1", "G2", "G3", "G4", "G5"}}}
        p_hitung = pengayaan.hipergeometrik(["G1", "G2", "G3", "G9"], contoh, latar)[0]["p"]
        p_manual = (math.comb(5, 3) * math.comb(15, 1) + math.comb(5, 4)) / math.comb(20, 4)
        if abs(p_hitung - p_manual) > 1e-9:
            raise RuntimeError(f"p hipergeometrik {p_hitung:.6f} != {p_manual:.6f}")
        return f"{len(gmt)} set Reactome, {len(pengayaan.gmt_bawaan('go_bp'))} set GO; p uji = {p_hitung:.4f}"
    cek("Pengayaan jalur (set gen bawaan)", pengayaan_uji)

    def jaringan_uji():
        """Graf berlapis dirakit benar dari bagian sintetis (tanpa internet)."""
        from . import jaringan
        G = jaringan.bangun({"uji": ["PTGS2", "MAPK14"]},
                            [{"jalur": "R-1", "nama": "radang", "q": 0.01, "n_overlap": 2, "gen": ["PTGS2", "MAPK14"]}],
                            [("PTGS2", "MAPK14", 0.9)], [("PTGS2", "MONDO_1", "artritis", 0.7)])
        d = {n: dd.get("jenis") for n, dd in G.nodes(data=True)}
        if sorted(d.values()).count("target") != 2 or "J:R-1" not in G or "P:MONDO_1" not in G:
            raise RuntimeError("lapisan graf tidak lengkap")
        m = {b["simpul"]: b["derajat"] for b in jaringan.metrik(G)}
        if m.get("T:PTGS2") != 4:
            raise RuntimeError(f"derajat PTGS2 = {m.get('T:PTGS2')}, seharusnya 4")
        return f"{G.number_of_nodes()} simpul, {G.number_of_edges()} tepi, metrik OK"
    cek("Jaringan farmakologi", jaringan_uji)

    def venn_uji():
        """Pembagian wilayah Venn benar dan SVG-nya utuh untuk 2 maupun 3 himpunan."""
        from . import venn
        w2 = venn.hitung2(["TP53", "AKT1", "egfr"], ["TP53", "NFKB1"])
        if w2["AB"] != ["TP53"] or w2["A"] != ["AKT1", "EGFR"] or w2["B"] != ["NFKB1"]:
            raise RuntimeError(f"wilayah Venn 2 himpunan salah: {w2}")
        w3 = venn.hitung3(["A", "B"], ["B", "C"], ["C", "A"])
        if w3["ABC"] or sorted(w3["AB"] + w3["AC"] + w3["BC"]) != ["A", "B", "C"]:
            raise RuntimeError(f"wilayah Venn 3 himpunan salah: {w3}")
        s2 = venn.svg({"Target": ["TP53", "AKT1"], "Penyakit": ["TP53"]}, judul="uji")
        s3 = venn.svg({"A": ["1"], "B": ["2"], "C": ["3"]}, mode="gelap")
        if s2.count("<circle") != 2 or s3.count("<circle") != 3 or not s2.rstrip().endswith("</svg>"):
            raise RuntimeError("SVG Venn tidak utuh")
        return "Venn 2 & 3 himpunan OK"
    cek("Diagram Venn", venn_uji)

    def farmakologi_uji():
        """Alur farmakologi jaringan: penyaringan, irisan, MCC, dan paragraf metode (tanpa internet)."""
        from . import farmakologi as F
        sen = F.senyawa_dari_daftar([{"nama": "kurkumin", "smiles": "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O"},
                                     {"nama": "aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
                                     {"nama": "rusak", "smiles": "bukan-smiles"}])
        if len(sen) != 3:
            raise RuntimeError(f"{len(sen)} senyawa dinormalkan, seharusnya 3")
        F.hitung_sifat(sen)
        sen[1]["admet"] = {"DILI": 0.95}
        r = F.saring(sen)
        if sen[2]["lolos"]:
            raise RuntimeError("SMILES rusak seharusnya gugur")
        if sen[1]["lolos"]:
            raise RuntimeError("DILI 0,95 di atas ambang seharusnya gugur")
        if r["lolos"] != 1:
            raise RuntimeError(f"{r['lolos']} senyawa lolos, seharusnya 1")

        ir = F.irisan({"a": ["TP53", "AKT1"], "b": ["EGFR"]}, [{"gen": "TP53"}, {"gen": "MYC"}])
        if ir["irisan"] != ["TP53"]:
            raise RuntimeError(f"irisan salah: {ir['irisan']}")

        # Segitiga TP53-AKT1-EGFR (klik maksimal 3) + ekor EGFR-SRC (klik maksimal 2):
        # MCC(EGFR) = (3-1)! + (2-1)! = 3; MCC(SRC) = 1.
        G = F.graf_ppi(["TP53", "AKT1", "EGFR", "SRC"],
                       [("TP53", "AKT1", 0.9), ("TP53", "EGFR", 0.8), ("AKT1", "EGFR", 0.75), ("EGFR", "SRC", 0.7)])
        h = {b["gen"]: b["mcc"] for b in F.hub(G, 10)}
        if h.get("EGFR") != 3.0 or h.get("SRC") != 1.0 or h.get("TP53") != 2.0:
            raise RuntimeError(f"MCC salah: {h}")

        k = F.keadaan_baru()
        k.update({"senyawa": sen, "target_senyawa": {"a": ["TP53"]}, "gen_penyakit": [{"gen": "TP53"}],
                  "irisan": ["TP53"], "tepi_ppi": [["TP53", "AKT1", 0.9]]})
        for teks in (F.paragraf_metode(k), F.paragraf_metode(k, inggris=True)):
            if "validasi eksperimental" not in teks and "experimental validation" not in teks:
                raise RuntimeError("paragraf metode kehilangan peringatan validasi")
        if len(F.ringkasan(k)) != 7:
            raise RuntimeError("ringkasan tahap tidak lengkap")
        return f"saring {r['lolos']}/{len(sen)}, irisan 1 gen, MCC & paragraf metode OK"
    cek("Alur farmakologi jaringan", farmakologi_uji)

    def ctd_uji():
        """Pengurai TSV CTD membaca kolom berdasarkan nama dan menyaring spesies (tanpa internet)."""
        from . import ctd
        teks = ("# Batch Query\n"
                "#Input\tChemicalName\tChemicalID\tGeneSymbol\tGeneID\tOrganism\tOrganism ID\t"
                "Interaction Actions\tPubMed IDs\n"
                "curcumin\tCurcumin\tD003474\tPTGS2\t5743\tHomo sapiens\t9606\tdecreases^expression\t111|222\n"
                "curcumin\tCurcumin\tD003474\tTp53\t22059\tMus musculus\t10090\tincreases^expression\t333\n"
                "curcumin\tCurcumin\tD003474\tTP53\t7157\tHomo sapiens\t9606\tincreases^expression\t444\n")
        baris = ctd.urai_tsv(teks)
        if len(baris) != 2:
            raise RuntimeError(f"{len(baris)} baris manusia, seharusnya 2 (baris tikus harus dibuang)")
        if baris[0]["gen"] != "PTGS2" or baris[0]["n_pubmed"] != 2:
            raise RuntimeError(f"kolom salah dibaca: {baris[0]}")
        if ctd.gen_unik(baris) != ["PTGS2", "TP53"]:
            raise RuntimeError("daftar gen unik salah")
        peta = ctd.per_senyawa(baris)
        if peta.get("curcumin") != ["PTGS2", "TP53"]:
            raise RuntimeError(f"pengelompokan per senyawa salah: {peta}")
        return "pengurai TSV CTD OK (2 baris manusia, 2 gen)"
    cek("CTD (pengurai interaksi senyawa-gen)", ctd_uji)

    def qsar_uji():
        """Pipeline QSAR berjalan utuh pada data kecil berhubungan: model harus menemukan hubungan dan menandai domain."""
        from rdkit import Chem
        from rdkit.Chem import Crippen
        from . import qsar
        data = []
        for i in range(60):
            smi = f"{'C' * (1 + i % 8)}c1ccc(cc1)C(=O)N{'C' * (1 + (i // 8) % 5)}"
            m = Chem.MolFromSmiles(smi)
            if m is None:
                continue
            data.append({"smiles": Chem.MolToSmiles(m), "pic50": round(4.0 + 0.6 * Crippen.MolLogP(m), 3),
                         "nama": f"s{i}"})
        unik = {d["smiles"]: d for d in data}
        data = list(unik.values())
        h = qsar.latih(data, "ridge", "deskriptor", "acak", benih=1, konformal=False)
        r2 = h["eksternal"]["r2"]
        if r2 < 0.5:
            raise RuntimeError(f"R2 uji {r2:.2f} terlalu rendah pada data berhubungan")
        p = qsar.prediksi(h, [data[0]["smiles"], "CCCCCCCCCCCCCCCCCCCC"])
        if p[1]["dalam_domain"]:
            raise RuntimeError("senyawa asing tidak ditandai di luar domain aplikabilitas")
        return f"{len(data)} senyawa, R2 uji {r2:.2f}, domain aplikabilitas aktif"
    cek("QSAR (pelatihan & domain)", qsar_uji)

    def konformal_uji():
        """Cakupan konformal mendekati taraf nominal pada data acak yang dapat dipertukarkan."""
        import numpy as np
        from . import konformal
        rng = np.random.default_rng(0)
        y, p = rng.normal(0, 1, 400), None
        p = y + rng.normal(0, 0.5, 400)
        k = konformal.KonformalRegresi(0.1)
        k.kalibrasi(y, p)
        y2 = rng.normal(0, 1, 600)
        c = k.cakupan(y2, y2 + rng.normal(0, 0.5, 600))
        if not 0.84 <= c <= 0.96:
            raise RuntimeError(f"cakupan konformal {c:.3f} jauh dari taraf nominal 0,90")
        return f"cakupan {c:.3f} pada taraf nominal 0,90 (q = {k.q:.3f})"
    cek("Prediksi konformal", konformal_uji)

    def farmakofor_uji():
        """Kueri farmakofor ke dirinya sendiri skor maksimum (serial), lalu 250 senyawa lewat ProcessPoolExecutor.

        Bagian paralel membuktikan multiprocessing.freeze_support() di titik masuk bekerja di build beku:
        tanpanya pekerja menjalankan ulang aplikasi dan kelompok senyawa hilang."""
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from . import farmakofor
        acuan = Chem.AddHs(Chem.MolFromSmiles("CC(C)(C)NC(=O)C1CCCCN1CC(O)Cc1ccccc1"))
        if AllChem.EmbedMolecule(acuan, randomSeed=7) != 0:
            raise RuntimeError("konformer acuan gagal dibangkitkan")
        kueri = farmakofor.kueri_dari_pose(acuan, eksklusi=False)
        diri = farmakofor.cocokkan(kueri, acuan)["skor_akhir"]
        if diri < 0.95:
            raise RuntimeError(f"skor kueri ke dirinya {diri:.3f} < 0,95")
        daftar = [{"nama": f"s{i}", "smiles": f"{'C' * (1 + i % 10)}c1ccc({'O' if i % 2 else 'N'})cc1{'C' * (1 + i // 10 % 5)}O"}
                  for i in range(250)]
        t0 = time.time()
        h = farmakofor.saring_pustaka(kueri, daftar, n_proses=2, konf_per_mol=2)
        if len(h) != 250:
            raise RuntimeError(f"penapisan paralel hanya mengembalikan {len(h)}/250 senyawa")
        if any(a["skor_akhir"] < b["skor_akhir"] for a, b in zip(h, h[1:])):
            raise RuntimeError("hasil penapisan tidak terurut")
        return f"skor diri {diri:.3f}; 250 senyawa paralel dalam {time.time() - t0:.1f} s"
    cek("Penapisan farmakofor (serial & paralel)", farmakofor_uji)

    def hipotesis_uji():
        """Fit 4PL memulihkan IC50 sintetis 2 µM dan menyensor senyawa yang tak mencapai 50 % inhibisi."""
        from . import hipotesis
        kons = [100 / 3 ** k for k in range(8)] * 3
        inhib = [100.0 / (1 + 2.0 / x) for x in kons]
        f = hipotesis.fit_dosis_respons(kons, inhib)
        if f["ic50_uM"] is None or f["sensor"] or abs(f["ic50_uM"] - 2.0) / 2.0 > 0.15:
            raise RuntimeError(f"IC50 4PL {f['ic50_uM']} (sensor {f['sensor']}), seharusnya 2 µM")
        lemah = hipotesis.fit_dosis_respons(kons, [20.0 * x / (x + 10.0) for x in kons])
        if lemah["sensor"] != ">":
            raise RuntimeError("senyawa < 50 % inhibisi tidak ditandai tersensor")
        return f"IC50 {f['ic50_uM']:.2f} µM (Hill {f['hill']:.2f}); senyawa lemah tersensor"
    cek("Pelacak hipotesis (fit dosis-respons 4PL)", hipotesis_uji)

    def xtb_uji():
        """xtb ikut terpasang dan memberi urutan celah HOMO-LUMO yang benar secara kimia.

        Benzena harus bercelah lebih lebar daripada anilin: gugus amino mendonorkan elektron dan
        menaikkan HOMO. Bila xtb tidak ikut dibundel, uji ini melaporkan apa adanya, bukan gagal."""
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from . import xtb as xtb_mod
        info = xtb_mod.tersedia()
        if not info["ada"]:
            return f"dilewati: {info['pesan'][:90]}"

        def siap(smi):
            m = Chem.AddHs(Chem.MolFromSmiles(smi))
            AllChem.EmbedMolecule(m, randomSeed=42)
            AllChem.MMFFOptimizeMolecule(m)
            return m

        b = xtb_mod.hitung(siap("c1ccccc1"), esp=False, nama="benzena")
        a = xtb_mod.hitung(siap("Nc1ccccc1"), esp=False, nama="anilin")
        if not b.tersedia or not a.tersedia:
            raise RuntimeError(b.pesan or a.pesan)
        if not b.celah_ev > a.celah_ev:
            raise RuntimeError(f"celah benzena {b.celah_ev:.2f} eV tidak lebih besar dari anilin {a.celah_ev:.2f} eV")
        return (f"xtb {info['versi']}: celah benzena {b.celah_ev:.2f} eV > anilin {a.celah_ev:.2f} eV; "
                f"{len(b.fukui)} indeks Fukui")
    cek("Sifat elektronik xTB (GFN2)", xtb_uji)

    def generatif_uji():
        """Basis data fragmen CReM ikut terpasang dan menghasilkan analog yang sah."""
        from . import generatif
        info = generatif.tersedia()
        if not info["ada"]:
            raise RuntimeError(info["pesan"])
        anak = generatif.generasi("CC(=O)Oc1ccccc1C(=O)O", "mutate", radius=2, maks=40)
        if len(anak) < 5:
            raise RuntimeError(f"hanya {len(anak)} analog dari basis data fragmen")
        kunci = [k.inchikey for k in anak]
        if len(kunci) != len(set(kunci)):
            raise RuntimeError("analog memuat InChIKey ganda")
        return f"{len(anak)} analog unik dari aspirin; {generatif.catatan_basis_data()[:70]}"
    cek("Desain generatif (basis data fragmen)", generatif_uji)

    def rbfe_uji():
        """Pemetaan atom dan MBAR berjalan; MBAR diuji pada jawaban yang diketahui analitis."""
        import numpy as np
        from . import rbfe
        pm = rbfe.peta_atom("c1ccccc1", "Cc1ccccc1")
        if pm["n_bersama"] != 6 or pm["n_berubah"] != 1:
            raise RuntimeError(f"pemetaan benzena ke toluena salah: {pm['n_bersama']}/{pm['n_berubah']}")
        rng = np.random.default_rng(0)
        x = rng.normal(0.0, 1.0, 600)
        u0 = 0.5 * x ** 2
        geser = 1.25
        h = rbfe.analisis_mbar(np.vstack([u0, u0 + geser]), [300, 300],
                               suhu=1.0 / rbfe.K_BOLTZMANN_KKAL)
        if h["dg"] is None or abs(h["dg"] - geser) > 1e-4:
            raise RuntimeError(f"MBAR memberi {h['dg']}, seharusnya {geser}")
        st = rbfe.status_mesin()
        return (f"pemetaan atom benar; MBAR memulihkan {h['dg']:.3f} dari {geser}; "
                f"mesin simulasi: {'ada' if st['ada'] else 'tidak di platform ini'}")
    cek("Energi bebas relatif (pemetaan & MBAR)", rbfe_uji)

    def peptida_uji():
        """Validasi sekuens peptida menegakkan batas dan menandai huruf yang bukan asam amino."""
        from . import peptida
        sah = peptida.validasi_sekuens("ETFSDLWKLLPEN")
        if not sah["sah"] or sah["panjang"] != 13:
            raise RuntimeError(f"sekuens p53 ditolak: {sah['pesan']}")
        salah = peptida.validasi_sekuens("ETJSDLWK")
        if salah["sah"] or salah["posisi_galat"] != [2]:
            raise RuntimeError("huruf bukan asam amino tidak ditandai pada posisinya")
        panjang = peptida.validasi_sekuens("A" * (peptida.PANJANG_MAKS + 1))
        if panjang["sah"]:
            raise RuntimeError("batas panjang peptida tidak ditegakkan")
        return f"batas {peptida.PANJANG_MAKS} residu ditegakkan; posisi huruf salah ditandai"
    cek("Docking peptida (validasi sekuens)", peptida_uji)

    def kofolding_uji():
        """Label kesepakatan co-folding mengikuti aturan tertulis, termasuk saat RMSD tidak ada."""
        from . import kofolding
        if kofolding.label_kesepakatan(1.0, True, True) != "Sepakat":
            raise RuntimeError("RMSD kecil dengan kedua QC lolos seharusnya Sepakat")
        if kofolding.label_kesepakatan(1.0, True, False) != "Sebagian":
            raise RuntimeError("QC gagal seharusnya menurunkan label menjadi Sebagian")
        if kofolding.label_kesepakatan(5.0, True, True, ifp_tanimoto=0.1) != "Bertentangan":
            raise RuntimeError("RMSD besar dengan kontak berbeda seharusnya Bertentangan")
        if kofolding.label_kesepakatan(None) != "–":
            raise RuntimeError("RMSD yang tidak terhitung tidak boleh diberi label")
        st = kofolding.status_boltz()
        return f"aturan label benar; Boltz: {'siap' if st.get('ada') else 'belum terpasang'}"
    cek("Co-folding (aturan kesepakatan)", kofolding_uji)

    def pembelajaran_aktif_uji():
        """Penapisan bertahap: sidik jari, model pengganti, dan pemilihan batch berjalan di paket terpasang."""
        import numpy as np
        from . import pembelajaran_aktif as pa
        smi = ["CCO", "CCN", "CCC", "c1ccccc1", "c1ccncc1", "CC(=O)O", "CC(=O)N", "CCCl", "CCBr", "CCOC",
               "CC(C)O", "CC(C)N", "CCCCO", "c1ccc(O)cc1", "c1ccc(N)cc1", "CC(=O)OC", "CCS", "CCOCC",
               "CC(C)(C)O", "c1ccc(Cl)cc1", "CCCCCC", "CC(N)=O", "CCC(=O)O", "CCCN", "CCCO"]
        pus = pa.siapkan_pustaka([(s, f"u{i}") for i, s in enumerate(smi)])
        if len(pus) < 20 or pus.fp.shape[1] != pa.NBIT // 8:   # duplikat kanonik boleh terbuang
            raise RuntimeError(f"sidik jari salah bentuk: {len(pus)} senyawa, {pus.fp.shape}")
        kp = pa.Kampanye(len(pus), {"awal": 15, "batch": 5, "putaran": 1, "model": "rf", "akuisisi": "ucb"})
        idx = kp.batch_awal()
        rng = np.random.default_rng(0)
        kp.catat({i: float(-6 - rng.random()) for i in idx})
        pilih, info = kp.pilih_berikut(pus)
        if len(pilih) != 5 or set(pilih) & set(idx):
            raise RuntimeError("batch berikutnya kosong atau mengulang senyawa yang sudah didocking")
        if not info.get("model"):
            raise RuntimeError("model pengganti tidak terlatih")
        return f"{len(pus)} senyawa, sidik jari pasangan atom {pa.NBIT} bit, model {info['model']} memilih {len(pilih)}"
    cek("Penapisan bertahap (pembelajaran aktif)", pembelajaran_aktif_uji)

    def sunting3d_uji():
        """Sunting di kantong: titik tumbuh dikenali dan gugus tersambung tanpa merusak molekul."""
        from rdkit import Chem
        from . import sunting3d
        mol = Chem.AddHs(Chem.MolFromSmiles("c1ccc(O)cc1"))
        from rdkit.Chem import AllChem
        AllChem.EmbedMolecule(mol, randomSeed=42)
        titik = sunting3d.titik_tumbuh(mol)
        if len(titik) < 5:
            raise RuntimeError(f"titik tumbuh fenol hanya {len(titik)}")
        usul = sunting3d.usulan_tumbuh(mol, titik[0][0], sunting3d.GUGUS[:3])
        jadi = [u for u in usul if u[2] is not None]
        if len(jadi) != 3:
            raise RuntimeError(f"hanya {len(jadi)} dari 3 gugus tersambung")
        smi = Chem.MolToSmiles(jadi[0][2])
        if "." in smi:
            raise RuntimeError(f"gugus tidak tersambung: {smi}")
        return f"{len(titik)} titik tumbuh; 3 gugus tersambung (contoh {smi})"
    cek("Sunting di kantong (3D)", sunting3d_uji)

    def unidock_uji():
        """Skrip batch Uni-Dock tersusun benar; keberadaan programnya di WSL dilaporkan apa adanya."""
        import tempfile
        from pathlib import Path as _P
        from . import mesin as _m, unidock
        with tempfile.TemporaryDirectory(prefix="vmd_ud_") as d:
            d = _P(d)
            lig = d / "lig.pdbqt"
            lig.write_text("ROOT\nENDROOT\n", encoding="utf-8")
            rec = d / "rec.pdbqt"
            rec.write_text("ATOM\n", encoding="utf-8")
            skrip, peta = unidock.tulis_skrip(rec, [lig], d / "keluar",
                                              _m.Kotak(pusat=[0, 0, 0], ukuran=[20, 20, 20], spasi=0.375))
            isi = skrip.read_bytes()
        if b"\r\n" in isi:
            raise RuntimeError("skrip bash ditulis dengan CRLF; bash menolaknya")
        if b"--ligand_index" not in isi or list(peta) != ["u00001"]:
            raise RuntimeError("skrip batch tidak memakai daftar ligan lewat symlink")
        st = unidock.status()
        return f"skrip batch benar (LF, symlink); Uni-Dock: {'siap di WSL' if st['ada'] else 'belum terpasang'}"
    cek("Uni-Dock (skrip batch)", unidock_uji)

    def skrip_wsl_uji():
        """Skrip pemasang alat WSL ikut terbundel, berakhiran LF, dan sintaksisnya sah menurut bash (bila WSL ada)."""
        nama = ("pasang_openfe_unidock_wsl.sh", "pasang_gnina_boltz_wsl.sh", "unduh_bobot_boltz.py")
        hilang = [n for n in nama if not (paths.ALAT_WSL / n).exists()]
        if hilang:
            raise FileNotFoundError(f"tidak ada di {paths.ALAT_WSL}: {', '.join(hilang)}")
        crlf = [n for n in nama if b"\r\n" in (paths.ALAT_WSL / n).read_bytes()]
        if crlf:
            raise RuntimeError(f"berakhiran CRLF (bash menolaknya): {', '.join(crlf)}")
        try:
            jalan = [subprocess.run(["wsl", "-e", "bash", "-n"], input=(paths.ALAT_WSL / n).read_bytes(),
                                    capture_output=True, timeout=60) for n in nama if n.endswith(".sh")]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "3 berkas ada, LF; WSL tidak tersedia sehingga sintaksis bash tidak diperiksa"
        from .lanjutan import teks_wsl
        # wsl.exe menulis galatnya sendiri ke stdout (UTF-16), bash menulis galat sintaksis ke stderr
        galat = [teks_wsl(p.stderr or b"") + " " + teks_wsl(p.stdout or b"") for p in jalan]
        # bash menolak skrip -> stderr menyebut "syntax error"; selain itu wsl.exe sendiri yang gagal berjalan
        # (mis. ERROR_NO_SYSTEM_RESOURCES ketika mesin virtual WSL sedang tidak bisa dihidupkan Windows)
        tolak = [t for p, t in zip(jalan, galat) if p.returncode and "syntax error" in t.lower()]
        if tolak:
            raise RuntimeError("bash -n menolak skrip: " + "; ".join(t.strip()[:120] for t in tolak))
        if any(p.returncode for p in jalan):
            sebab = next((t.strip() for p, t in zip(jalan, galat) if p.returncode), "")
            return f"3 berkas ada, LF; WSL tidak dapat dijalankan sekarang: {sebab[:120]}"
        return "3 berkas ada, LF, sintaksis bash sah"
    cek("Skrip alat WSL", skrip_wsl_uji)

    def glikosida_uji():
        """Glikosida dan aglikon: kosmosiin dipotong menjadi apigenin, viteksin (C-glikosida) tidak dipotong."""
        from rdkit import Chem
        from . import glikosida
        h = glikosida.deglikosilasi("C1=CC(=CC=C1C2=CC(=O)C3=C(C=C(C=C3O2)O[C@H]4[C@@H]([C@H]([C@@H]([C@H](O4)CO)O)O)O)O)O")
        apigenin = Chem.MolToSmiles(Chem.MolFromSmiles("C1=CC(=CC=C1C2=CC(=O)C3=C(C=C(C=C3O2)O)O)O"))
        if h.status != "ok" or h.smiles_aglikon != apigenin or [g.jenis for g in h.gula] != ["heksosa"]:
            raise RuntimeError(f"kosmosiin: {h.status} {h.smiles_aglikon} {glikosida.ringkas_gula(h.gula)}")
        v = glikosida.deglikosilasi("C1=CC(=CC=C1C2=CC(=O)C3=C(O2)C(=C(C=C3O)O)[C@H]4[C@@H]([C@H]([C@@H]([C@H](O4)CO)O)O)O)O")
        if v.status != "hanya_c":
            raise RuntimeError(f"viteksin seharusnya C-glikosida, didapat {v.status}")
        le, fq = glikosida.efisiensi(-8.0, h.atom_berat_aglikon)
        return f"kosmosiin -> apigenin ({h.atom_berat} -> {h.atom_berat_aglikon} atom); C-glikosida utuh; FQ {fq:.2f}"
    cek("Glikosida dan aglikon", glikosida_uji)

    def tema_uji():
        """Stylesheet terpasang sungguhan dengan ikon di folder data aplikasi ini. Qt menolak SELURUH stylesheet
        tanpa pesan bila satu url() rusak (dulu: jalur ber-huruf non-ASCII), dan aplikasi tampil polos."""
        from PySide6.QtWidgets import QApplication, QPushButton
        from ..ui import theme
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError("butuh QApplication (uji dijalankan tanpa antarmuka)")
        lama = app.styleSheet()
        hasil_mode = []
        for mode in ("terang", "gelap"):
            app.setStyleSheet(theme.qss_berikon(mode, paths.APPDATA))
            b = QPushButton("uji")
            b.setObjectName("primary")
            b.ensurePolished()
            warna = b.palette().button().color().name()
            if warna != theme.TOKEN[mode]["acc"]:
                raise RuntimeError(f"stylesheet {mode} tidak berlaku (tombol utama {warna}, harap "
                                   f"{theme.TOKEN[mode]['acc']}); folder data: {paths.APPDATA}")
            hasil_mode.append(mode)
        app.setStyleSheet(lama)          # dijalankan dari menu Bantuan: tema aplikasi dikembalikan
        return f"stylesheet {' & '.join(hasil_mode)} berlaku; ikon di {paths.APPDATA}"
    cek("Tema antarmuka (stylesheet)", tema_uji)

    return hasil


class _LaporCetak:
    """Pelapor yang mencetak tiap uji begitu selesai (meniru antarmuka sinyal Qt `lapor.log.emit`).

    Tanpa ini `--uji-mandiri` diam sampai seluruh uji selesai, sehingga uji yang menggantung tidak
    ketahuan namanya: log rilis berhenti tanpa petunjuk. Keluaran di-flush agar urut di berkas log.
    """

    class _Sinyal:
        @staticmethod
        def emit(teks):
            print(teks, flush=True)

    log = _Sinyal()


def tulis(path):
    from .. import __version__
    h = uji(lapor=_LaporCetak())
    data = {"versi": __version__, "portable": paths.PORTABLE, "bin": str(paths.BIN), "hasil": h,
            "semua_ok": all(x["ok"] for x in h)}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data["semua_ok"]
