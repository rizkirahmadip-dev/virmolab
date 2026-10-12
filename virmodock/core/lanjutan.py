"""GNINA dan Boltz lewat WSL, film trajektori, serta paket OpenMM dan topologi GROMACS.

Biner GNINA (~2 GB) dan lingkungan Boltz tinggal di folder rumah WSL (`~/virmodock-alat`),
bukan di dalam installer. Bila programnya belum ada, fungsi status mengembalikan petunjuk.
"""
import shlex
import shutil
import subprocess
from pathlib import Path

ALAT = "$HOME/virmodock-alat"


def cari_program(nama):
    ketemu = shutil.which(nama) or shutil.which(nama + ".exe")
    if ketemu:
        return ketemu
    from . import paths
    calon = paths.BIN / (nama if nama.endswith(".exe") else nama + ".exe")
    return str(calon) if calon.exists() else ""


def _wsl(perintah, timeout=120):
    try:
        return subprocess.run(["wsl", "-e", "bash", "-lc", perintah], capture_output=True,
                              text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise TimeoutError("Perintah di WSL melewati batas waktu.") from e
    except FileNotFoundError as e:
        raise RuntimeError("WSL tidak terpasang di komputer ini.") from e


def _wsl_ada(uji):
    """uji: perintah bash yang mencetak ADA bila berkasnya siap."""
    try:
        p = _wsl(uji, timeout=40)
    except (RuntimeError, TimeoutError):
        return False
    return p.returncode == 0 and "ADA" in (p.stdout or "")


def ke_wsl(jalur):
    p = _wsl("wslpath -u " + shlex.quote(str(Path(jalur).resolve())), timeout=40)
    if p.returncode != 0 or not (p.stdout or "").strip():
        raise RuntimeError((p.stderr or "wslpath gagal").strip()[-400:])
    return p.stdout.strip()


def status_gnina():
    if _wsl_ada(f'test -x {ALAT}/gnina && echo ADA'):
        return {"ada": True, "jalur": "~/virmodock-alat/gnina",
                "pesan": "GNINA 1.3.3 siap di WSL (skor CNN). "
                         "Tombol di bawah menilai ulang pose yang sedang dipilih. "
                         "Nilai CNN bukan ΔG dan tidak menggantikan skor Vina."}
    p = cari_program("gnina")
    if p:
        return {"ada": True, "jalur": p,
                "pesan": "GNINA ada di PATH Windows. Skor ulang dari jendela ini memakai salinan WSL."}
    return {"ada": False, "jalur": "",
            "pesan": "GNINA belum ada di WSL. Pasang dengan build_tools/pasang_gnina_boltz_wsl.sh. "
                     "Binernya Linux (CUDA 12.8), lisensi GPL-2.0, dan tidak dimasukkan ke installer."}


def status_boltz():
    if _wsl_ada(f'test -x {ALAT}/boltz/bin/boltz && echo ADA'):
        return {"ada": True, "jalur": "~/virmodock-alat/boltz/bin/boltz",
                "pesan": "Boltz 2.2.1 siap di WSL (Python 3.12, terpisah dari aplikasi). "
                         "Prediksi memakai GPU bila dipilih. RTX 3060 6 GB sering kehabisan memori; "
                         "bila gagal, jalankan dengan CPU. MSA ColabFold hanya bila kotaknya dicentang."}
    return {"ada": False, "jalur": "",
            "pesan": "Boltz belum terpasang di WSL. Pasang dengan build_tools/pasang_gnina_boltz_wsl.sh. "
                     "Paket dan bobotnya berlisensi MIT dan tidak dibundel."}


def _tanpa_jalur(teks):
    """Ganti jalur komputer supaya nama pengguna tidak ikut ke catatan."""
    import re
    t = teks or ""
    t = re.sub(r"/mnt/[A-Za-z]/\S+", "[jalur]", t)
    t = re.sub(r"/home/\S+", "[jalur]", t)
    t = re.sub(r"[A-Za-z]:\\[^\s]+", "[jalur]", t)
    return t.strip()


def ringkas_gnina(teks):
    kunci = ("affinity", "cnnscore", "cnnaffinity", "cnn affinity")
    baris = [b.strip() for b in _tanpa_jalur(teks).splitlines()
             if any(k in b.lower() for k in kunci)]
    return "\n".join(baris)


def batasi_gnina(daftar, n=10, semua=False):
    """Ligan yang akan dinilai GNINA. Bawaan: n energi terbaik. semua=True mengambil seluruh daftar."""
    urut = sorted(daftar, key=lambda l: l.get("energi") if isinstance(l.get("energi"), (int, float)) else 1e9)
    if semua or len(urut) <= n:
        return urut
    return urut[:n]


def angka_gnina(teks):
    """Affinity (kcal/mol), CNNscore (0-1), CNNaffinity (pK). None bila barisnya tidak ada."""
    import re
    def ambil(pola):
        m = re.search(pola, teks or "", re.I)
        return float(m.group(1)) if m else None
    return {
        "affinity": ambil(r"affinity:\s*(-?\d+(?:\.\d+)?)"),
        "cnnscore": ambil(r"cnn\s*score:\s*(-?\d+(?:\.\d+)?)"),
        "cnnaffinity": ambil(r"cnn\s*affinity:\s*(-?\d+(?:\.\d+)?)"),
    }


def skor_gnina(teks_pdb, sdf, folder, pdbqt=False):
    """Nilai ulang satu pose. sdf adalah teks berkas SDF (sudah berisi koordinat)."""
    st = status_gnina()
    if not st["ada"]:
        raise RuntimeError(st["pesan"])
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rec = folder / ("reseptor_gnina.pdbqt" if pdbqt else "reseptor_gnina.pdb")
    lig, out = folder / "ligan_gnina.sdf", folder / "skor_gnina.sdf"
    teks_pdb = (teks_pdb or "").replace("\x00", "")
    sdf = (sdf or "").replace("\x00", "")
    rec.write_text(teks_pdb if teks_pdb.endswith("\n") else teks_pdb + "\n", encoding="utf-8")
    lig.write_text(sdf if sdf.endswith("\n") else sdf + "\n", encoding="utf-8")
    # cuDNN 9 ikut roda PyTorch di lingkungan Boltz; biner GNINA tidak membawanya.
    cmd = " ".join([
        'CUDA_LIBS=$(find "$HOME/virmodock-alat/boltz/lib" -type d -name lib -path "*/nvidia/*" 2>/dev/null | paste -sd:);',
        'if [ -n "$CUDA_LIBS" ]; then export LD_LIBRARY_PATH="${CUDA_LIBS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; fi;',
        f"{ALAT}/gnina",
        "-r", shlex.quote(ke_wsl(rec)),
        "-l", shlex.quote(ke_wsl(lig)),
        "--score_only", "--cnn_scoring", "rescore",
        "-o", shlex.quote(ke_wsl(out)),
    ])
    p = _wsl(cmd, timeout=900)
    ringkas = ringkas_gnina(p.stdout) or ringkas_gnina(p.stderr)
    if p.returncode != 0 or "affinity" not in ringkas.lower():
        ekor = _tanpa_jalur((p.stderr or "") + "\n" + (p.stdout or ""))[-800:] or "GNINA tidak menulis skor."
        raise RuntimeError(ekor)
    proton = any(b.startswith(("ATOM", "HETATM")) and len(b) >= 78 and b[76:78].strip().upper() == "H"
                 for b in teks_pdb.splitlines())
    catatan = "" if proton else ("\n\nReseptor belum berisi hidrogen. Skor ini tidak untuk dikutip; "
                                 "siapkan reseptor di wizard (protonasi) lalu nilai ulang pose itu.")
    from .arti import CATATAN_GNINA
    return ringkas + "\n\n" + CATATAN_GNINA + "\nSkor CNN ditulis di skor_gnina.sdf pada folder yang dipilih." + catatan


def nilai_gnina_pose(teks_reseptor_pdbqt, teks_ligan_pdbqt, pose_pdbqt, folder):
    """Tiga angka GNINA untuk satu pose. Gagal bila programnya tidak ada atau tidak menulis afinitas."""
    from rdkit import Chem
    from .analisis import pose_mol
    mol = pose_mol(teks_ligan_pdbqt, (pose_pdbqt or "").replace("\x00", ""))
    return angka_gnina(skor_gnina(teks_reseptor_pdbqt, Chem.MolToMolBlock(mol), folder, pdbqt=True))


def _yaml_boltz(sekuens_rantai, smiles, msa_kosong=True):
    import yaml
    urut = []
    for i, (rantai, seq) in enumerate(sekuens_rantai):
        if seq:
            entri = {"id": rantai or chr(ord("A") + i), "sequence": seq}
            if msa_kosong:
                entri["msa"] = "empty"
            urut.append({"protein": entri})
    if not urut:
        raise ValueError("Protein tidak punya sekuens asam amino.")
    if not smiles:
        raise ValueError("Ligan tidak punya SMILES.")
    urut.append({"ligand": {"id": "L", "smiles": smiles}})
    return yaml.safe_dump({"version": 1, "sequences": urut}, sort_keys=False, allow_unicode=True)


def _langkah_boltz(penuh):
    """(daur ulang, langkah difusi). Penuh mengikuti bawaan Boltz; ringkas supaya muat di GPU 6 GB."""
    return ("3", "200") if penuh else ("1", "50")


def prediksi_boltz(sekuens_rantai, smiles, folder, gpu=True, msa_server=False, penuh=False):
    st = status_boltz()
    if not st["ada"]:
        raise RuntimeError(st["pesan"])
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    yaml_path = folder / "boltz.yaml"
    yaml_path.write_text(_yaml_boltz(sekuens_rantai, smiles, msa_kosong=not msa_server), encoding="utf-8")
    keluar = folder / "boltz_out"
    aks = "gpu" if gpu else "cpu"
    daur, langkah = _langkah_boltz(penuh)
    cmd = " ".join([
        f"{ALAT}/boltz/bin/boltz", "predict", shlex.quote(ke_wsl(yaml_path)),
        "--out_dir", shlex.quote(ke_wsl(keluar)),
        "--accelerator", aks,
        "--model", "boltz2",
        "--diffusion_samples", "1",
        "--recycling_steps", daur,
        "--sampling_steps", langkah,
        "--diffusion_samples_affinity", "1",
        "--sampling_steps_affinity", langkah,
        "--max_parallel_samples", "1",
        "--output_format", "pdb",
        "--num_workers", "0",
        "--preprocessing-threads", "1",
        "--no_kernels",
        "--override",
    ] + (["--use_msa_server"] if msa_server else []))
    p = _wsl(cmd, timeout=14400 if penuh else 7200)
    bersih = _tanpa_jalur((p.stdout or "") + "\n" + (p.stderr or ""))
    struktur = list(keluar.rglob("*.pdb")) + list(keluar.rglob("*.cif")) + list(keluar.rglob("*.mmcif"))
    gagal = p.returncode != 0 or not struktur or "Failed to process" in ((p.stdout or "") + (p.stderr or ""))
    if gagal:
        raise RuntimeError(bersih[-1500:] or "Boltz tidak menulis struktur.")
    cara = ("MSA diminta ke peladen ColabFold; sekuens ikut terkirim." if msa_server
            else "MSA satu sekuens, tanpa peladen. Jangan dikutip sebagai struktur pembanding kristal.")
    from .arti import CATATAN_BOLTZ
    pengaturan = (f"Pengaturan penuh: {daur} daur ulang, {langkah} langkah, "
                  f"{len(sekuens_rantai)} rantai protein." if penuh else
                  "Pengaturan diringkas supaya muat di GPU 6 GB (1 daur ulang, 50 langkah).")
    return ("Prediksi Boltz-2 selesai. " + pengaturan + " " + cara + " " + CATATAN_BOLTZ
            + " Hasil ada di folder boltz_out.\n" + bersih[-600:])


def film_pdb(folder, n=12):
    """Gabungkan frames.npy + topologi.pdb menjadi PDB multi-MODEL (cuplikan merata)."""
    import io
    import numpy as np
    from openmm import app, unit
    folder = Path(folder)
    f_frame, f_top = folder / "frames.npy", folder / "topologi.pdb"
    if not f_frame.exists() or not f_top.exists():
        raise FileNotFoundError("Folder MD belum berisi frames.npy dan topologi.pdb. Jalankan MD dulu.")
    frames = np.load(f_frame)
    if len(frames) == 0:
        raise ValueError("frames.npy kosong.")
    idx = [int(round(i)) for i in np.linspace(0, len(frames) - 1, min(n, len(frames)))]
    pdb = app.PDBFile(str(f_top))
    potong = []
    for k, i in enumerate(dict.fromkeys(idx), start=1):
        buf = io.StringIO()
        app.PDBFile.writeFile(pdb.topology, unit.Quantity(frames[i], unit.nanometer), buf, keepIds=True)
        isi = "\n".join(b for b in buf.getvalue().splitlines() if not b.startswith("END"))
        potong.append(f"MODEL     {k:4d}\n{isi}\nENDMDL")
    return "\n".join(potong) + "\nEND\n", len(potong)


def tulis_gro(topologi, posisi, jalur):
    """Koordinat GROMACS (.gro) dalam nanometer, tanpa topologi."""
    import numpy as np
    from openmm import unit
    nm = posisi.value_in_unit(unit.nanometer) if hasattr(posisi, "value_in_unit") else posisi
    baris = ["Kompleks VirmoDock", str(topologi.getNumAtoms())]
    for i, (atom, p) in enumerate(zip(topologi.atoms(), nm), start=1):
        res = atom.residue
        try:
            nres = int(str(res.id).strip())
        except ValueError:
            nres = 1
        baris.append(f"{nres % 100000:5d}{(res.name or 'UNK')[:5]:<5}{atom.name[:5]:>5}{i % 100000:5d}"
                     f"{p[0]:8.3f}{p[1]:8.3f}{p[2]:8.3f}")
    arr = np.asarray(nm, dtype=float)
    span = (arr.max(axis=0) - arr.min(axis=0)) + 1.0
    baris.append(f"{span[0]:10.5f}{span[1]:10.5f}{span[2]:10.5f}")
    Path(jalur).write_text("\n".join(baris) + "\n", encoding="utf-8")


def tulis_topologi_gromacs(sistem, topologi, posisi, folder):
    """Tulis kompleks.gro dan, bila ParmEd bisa, kompleks.top (vakum, parameter tersalin).

    Suku OBC2 dibuang: GROMACS tidak memakai gaya implisit yang sama. Pelarut implisit tetap di XML OpenMM.
    """
    import openmm as mm
    from openmm import XmlSerializer
    folder = Path(folder)
    tulis_gro(topologi, posisi, folder / "kompleks.gro")
    try:
        import parmed as pmd
    except ImportError:
        return "kompleks.gro tertulis. ParmEd tidak terpasang, jadi kompleks.top tidak dibuat."
    salinan = XmlSerializer.deserialize(XmlSerializer.serialize(sistem))
    for i in range(salinan.getNumForces() - 1, -1, -1):
        if isinstance(salinan.getForce(i), mm.GBSAOBCForce):
            salinan.removeForce(i)
    struktur = pmd.openmm.load_topology(topologi, salinan, xyz=posisi)
    struktur.save(str(folder / "kompleks.top"), overwrite=True)
    return ("kompleks.top adalah topologi vakum (ff14SB + OpenFF, parameter di dalam berkas). "
            "Suku OBC2 tidak ikut; untuk pelarut implisit pakai sistem_obc2.xml.")


def paket_server(folder, teks_reseptor, teks_pdbqt, mol):
    """Tulis sistem OpenMM (XML) + PDB + GRO/TOP GROMACS. Butuh OpenMM."""
    from openmm import XmlSerializer
    from . import md
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    ff, modeller, info = md.siapkan_kompleks(teks_reseptor, teks_pdbqt, mol)
    sistem = md.sistem_implisit(ff, modeller.topology, grup=False)
    (folder / "sistem_obc2.xml").write_text(XmlSerializer.serialize(sistem), encoding="utf-8")
    md.tulis_pdb(modeller.topology, modeller.positions, folder / "kompleks.pdb")
    try:
        catatan = tulis_topologi_gromacs(sistem, modeller.topology, modeller.positions, folder)
    except Exception as e:
        catatan = "Topologi GROMACS tidak lengkap: " + str(e)[:400]
        try:
            tulis_gro(modeller.topology, modeller.positions, folder / "kompleks.gro")
        except Exception:
            pass
    (folder / "BACA.txt").write_text(
        "Paket ini untuk dijalankan di komputer lain.\n"
        "sistem_obc2.xml  : sistem OpenMM pelarut implisit OBC2 (ff14SB + OpenFF pada ligan).\n"
        "kompleks.pdb     : koordinat awal, format PDB.\n"
        "kompleks.gro     : koordinat yang sama, nanometer, format GROMACS.\n"
        "kompleks.top     : topologi GROMACS vakum bila ParmEd berhasil.\n"
        + catatan + "\n"
        f"Jumlah atom ligan: {len(info.get('idx_ligan') or [])}\n", encoding="utf-8")
    return folder
