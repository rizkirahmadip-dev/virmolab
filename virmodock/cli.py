"""Baris perintah VirmoDock (tanpa jendela) — untuk skrip, batch, dan reproduksibilitas metode.

  VirmoDock-cli.exe <perintah> [opsi]        (dari kode sumber: python -m virmodock.cli <perintah> [opsi])

Perintah:
  info        versi, program mesin, GPU/OpenCL
  uji         uji mandiri komponen (kode keluar 0 = semua lulus)
  reseptor    siapkan reseptor -> PDBQT (berkas PDB/CIF, kode PDB, atau AF-<UniProt>); opsional residu fleksibel
  ligan       siapkan ligan -> PDBQT (SDF/MOL2/PDB/SMI, beberapa berkas)
  kantong     deteksi kantong P2Rank
  alphafold   unduh model AlphaFold DB (PDB) dari kode UniProt
  dock        satu perintah: (siapkan reseptor & ligan bila perlu) -> grid box -> docking -> ringkasan.csv

Contoh:
  VirmoDock-cli dock -r 1HSG -l kandidat.smi --acuan auto -o hasil_1hsg
  VirmoDock-cli dock -r reseptor.pdbqt -l ligan/ --pusat 13.07 22.47 5.56 --ukuran 22 22 22 --mesin vina
  VirmoDock-cli reseptor 1HSG -o rec.pdbqt --protonasi propka --flex A:25,B:25 --keluar-flex flex.pdbqt
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

KODE_GAGAL = 1


def _perintah():
    """Baris perintah yang bisa disalin ulang (untuk log & metode)."""
    return "VirmoDock-cli " + subprocess.list2cmdline(sys.argv[1:])


def _cetak(*a, **kw):
    print(*a, **kw, flush=True)


def _galat(pesan, kode=KODE_GAGAL):
    print(f"GALAT: {pesan}", file=sys.stderr, flush=True)
    sys.exit(kode)


def _nama_berkas(nama):
    s = re.sub(r"[^\w.\-]+", "_", nama.strip(), flags=re.UNICODE).strip("._")
    return s[:80] or "ligan"


def _tiga(nilai, opsi):
    if nilai is None:
        return None
    if len(nilai) != 3:
        _galat(f"{opsi} membutuhkan tiga angka (x y z).")
    return [float(v) for v in nilai]


# ------------------------------------------------------------------ reseptor
def _baca_reseptor_masukan(teks_arg, af_ambang=50.0):
    """-> (teks struktur, fmt, nama, objek-objek molekul) dari berkas / kode PDB / AF-<UniProt>."""
    from .core import molekul
    p = Path(teks_arg)
    if p.exists():
        ext = p.suffix.lower()
        teks = p.read_text(errors="replace")
        fmt = "cif" if ext in (".cif", ".mmcif") else "pdb"
        return teks, fmt, p.stem, molekul.baca_teks_struktur(teks, p.stem, fmt, str(p))
    m = re.fullmatch(r"(?i)(?:af[-:]?)([A-Z0-9]{6,10})", teks_arg.strip())
    if m:
        from .core import alphafold
        objs, teks, meta = alphafold.unduh(m.group(1), ambang=af_ambang, pangkas_aktif=af_ambang > 0)
        _cetak(f"AlphaFold {meta['entri']} v{meta['versi']} — {meta['nama']} ({meta['organisme']}), "
               f"pLDDT rerata {meta['plddt_rerata']}" + (f", dipangkas {meta['dibuang']}" if meta["n_dibuang"] else ""))
        prot = next(o for o in objs if o.jenis == "protein")
        return prot.teks, "pdb", f"AF-{meta['aksesi']}", objs
    if re.fullmatch(r"[A-Za-z0-9]{4}", teks_arg.strip()):
        objs, teks, fmt = molekul.unduh_rcsb(teks_arg)
        return teks, fmt, teks_arg.strip().upper(), objs
    _galat(f"Reseptor '{teks_arg}' bukan berkas, kode PDB (4 karakter), atau AF-<UniProt>.")


def _opsi_reseptor(a):
    from .core.prep_reseptor import OpsiReseptor
    return OpsiReseptor(rantai=[c.strip() for c in a.rantai.split(",")] if a.rantai else None,
                        hapus_air=not a.pertahankan_air, pertahankan_logam=not a.buang_logam,
                        protonasi=a.protonasi, ph=a.ph)


def _siapkan_reseptor(a, folder=None):
    """-> (pdbqt kaku, pdbqt flex|None, info dict, objek-objek struktur masukan)."""
    from .core import prep_reseptor as prep
    if a.reseptor.lower().endswith(".pdbqt") and Path(a.reseptor).exists():
        if getattr(a, "flex", None):
            _galat("--flex butuh reseptor PDB/CIF/kode PDB (bukan PDBQT). Atau berikan --berkas-flex.")
        teks = Path(a.reseptor).read_text(errors="replace")
        flex = Path(a.berkas_flex).read_text(errors="replace") if getattr(a, "berkas_flex", None) else None
        return teks, flex, {"nama": Path(a.reseptor).stem, "metode": "PDBQT disiapkan pengguna"}, []
    teks, fmt, nama, objs = _baca_reseptor_masukan(a.reseptor, getattr(a, "af_ambang", 50.0))
    _cetak(f"Menyiapkan reseptor {nama} ({a.protonasi}, pH {a.ph})…")
    h = prep.siapkan(teks, _opsi_reseptor(a), fmt)
    for p in h.peringatan:
        _cetak("  peringatan: " + p)
    info = {"nama": nama, "metode": h.metode, "atom": h.atom, "residu": h.residu, "logam": h.logam,
            "dibuang": h.dibuang}
    rigid, flex = h.pdbqt, None
    if getattr(a, "flex", None):
        res = [r.strip() for r in a.flex.split(",") if r.strip()]
        rigid, flex, ok, gagal = prep.buat_fleksibel(h.pdb_meeko, h.pdbqt, res)
        info["fleksibel"] = ok
        _cetak(f"  residu fleksibel: {', '.join(ok)} ({prep.torsi_flex(flex)} torsi)"
               + (f"; dilewati: {'; '.join(gagal)}" if gagal else ""))
    if folder:
        Path(folder, "reseptor_laporan.txt").write_text(h.laporan, encoding="utf-8")
        Path(folder, "reseptor_bersih.pdb").write_text(h.pdb_bersih, encoding="utf-8")
    _cetak(f"  {h.atom} atom, {h.residu} residu · {h.metode}")
    return rigid, flex, info, objs


def cmd_reseptor(a):
    keluar = Path(a.keluar or (_nama_berkas(Path(a.reseptor).stem) + ".pdbqt"))
    keluar.parent.mkdir(parents=True, exist_ok=True)
    rigid, flex, info, _ = _siapkan_reseptor(a, keluar.parent)
    keluar.write_text(rigid, encoding="utf-8")
    _cetak(f"Reseptor: {keluar}")
    if flex:
        f = Path(a.keluar_flex or keluar.with_name(keluar.stem + "_flex.pdbqt"))
        f.write_text(flex, encoding="utf-8")
        _cetak(f"Residu fleksibel: {f}")
    return 0


# ------------------------------------------------------------------ ligan
def _baca_ligan(sumber):
    """Berkas/folder/SMILES -> [(nama, teks, fmt)] dan [(nama, pdbqt siap)]."""
    from .core import molekul
    mentah, siap = [], []
    berkas = []
    for s in sumber:
        p = Path(s)
        if p.is_dir():
            berkas += sorted(x for x in p.iterdir() if x.suffix.lower() in
                             (".sdf", ".mol", ".mol2", ".pdb", ".pdbqt", ".smi", ".smiles"))
        elif p.exists():
            berkas.append(p)
        elif re.search(r"[\\/]|\.(sdf|mol2?|pdbqt?|smi|smiles|txt)$", s, re.I):
            _galat(f"Berkas ligan tidak ditemukan: {s}")
        else:
            mentah += [(o.nama, o.teks, o.fmt) for o in molekul.dari_smiles(s, f"smiles_{len(mentah) + 1}")]
    for p in berkas:
        teks = p.read_text(errors="replace")
        if p.suffix.lower() == ".pdbqt" and "TORSDOF" in teks:
            siap.append((p.stem, teks))
            continue
        for o in molekul.impor_berkas(p):
            if o.jenis in ("ligan", "pose"):
                mentah.append((o.nama, o.teks, o.fmt))
    return mentah, siap


def _siapkan_ligan(sumber, a, folder):
    from .core import prep_ligan as pl
    mentah, siap = _baca_ligan(sumber)
    if mentah:
        _cetak(f"Menyiapkan {len(mentah)} ligan (pH {a.ph_ligan}, {a.protonasi_ligan})…")
        opsi = pl.OpsiLigan(ph=a.ph_ligan, protonasi=a.protonasi_ligan != "tidak",
                            metode_ph="dimorphite" if a.protonasi_ligan == "dimorphite" else "obabel",
                            minimisasi=not a.tanpa_minimisasi)
        for h in pl.siapkan_banyak(mentah, opsi):
            if h.status == "gagal":
                _cetak(f"  gagal: {h.nama} — {h.alasan}")
                continue
            if h.alasan:
                _cetak(f"  {h.nama}: {h.alasan}")
            siap.append((h.nama, h.pdbqt))
    hasil, dipakai = [], set()
    Path(folder).mkdir(parents=True, exist_ok=True)
    for nama, teks in siap:
        dasar = _nama_berkas(nama)
        k = 2
        while dasar.lower() in dipakai:
            dasar = f"{_nama_berkas(nama)}_{k}"
            k += 1
        dipakai.add(dasar.lower())
        f = Path(folder, dasar + ".pdbqt")
        f.write_text(teks, encoding="utf-8")
        hasil.append((nama, f))
    return hasil


def cmd_ligan(a):
    hasil = _siapkan_ligan(a.masukan, a, a.keluar)
    _cetak(f"{len(hasil)} ligan siap di {a.keluar}")
    return 0 if hasil else KODE_GAGAL


# ------------------------------------------------------------------ kantong / alphafold
def cmd_kantong(a):
    import tempfile
    from .core import p2rank
    if not p2rank.tersedia():
        _galat("P2Rank/Java tidak ditemukan di folder bin.")
    teks, _fmt, nama, objs = _baca_reseptor_masukan(a.protein)
    prot = next((o for o in objs if o.jenis == "protein"), None)
    af = nama.startswith("AF-") or a.alphafold
    k = p2rank.prediksi(prot.teks if prot else teks, tempfile.mkdtemp(prefix="vd_p2rank_"),
                        konfigurasi="alphafold" if af else None)
    if a.json:
        _cetak(json.dumps(k, ensure_ascii=False, indent=1))
        return 0
    _cetak(f"{len(k)} kantong ({nama}{', konfigurasi alphafold' if af else ''}):")
    for x in k[: a.n]:
        res = " ".join(f"{c}{i}" for c, i in x["residu"][:14])
        _cetak(f"  #{x['peringkat']}  skor {x['skor']:.1f}  prob {x['prob']:.2f}  pusat "
               f"{x['pusat'][0]:.2f} {x['pusat'][1]:.2f} {x['pusat'][2]:.2f}  · {res}{' …' if len(x['residu']) > 14 else ''}")
    return 0


def cmd_alphafold(a):
    from .core import alphafold
    objs, teks, meta = alphafold.unduh(a.aksesi, ambang=a.ambang, pangkas_aktif=a.ambang > 0)
    prot = next(o for o in objs if o.jenis == "protein")
    keluar = Path(a.keluar or f"AF-{meta['aksesi']}.pdb")
    keluar.write_text(prot.teks if a.ambang > 0 else teks, encoding="utf-8")
    fr = meta["fraksi"]
    _cetak(f"{meta['entri']} v{meta['versi']} — {meta['nama']} ({meta['organisme']}) → {keluar}")
    _cetak(f"pLDDT rerata {meta['plddt_rerata']}; >90 {fr.get('sangat tinggi', 0):.0%}, 70–90 {fr.get('yakin', 0):.0%}, "
           f"50–70 {fr.get('rendah', 0):.0%}, <50 {fr.get('sangat rendah', 0):.0%}"
           + (f"; dipangkas {meta['dibuang']}" if meta["n_dibuang"] else ""))
    return 0


# ------------------------------------------------------------------ dock
def _koordinat_teks(teks):
    xs = []
    for b in teks.splitlines():
        if b.startswith(("ATOM", "HETATM")):
            try:
                xs.append((float(b[30:38]), float(b[38:46]), float(b[46:54])))
            except ValueError:
                pass
    return xs


def _koordinat_objek(o):
    xs = _koordinat_teks(o.teks)
    if not xs and o.fmt == "sdf":
        from rdkit import Chem
        m = Chem.MolFromMolBlock(o.teks, removeHs=False)
        xs = [tuple(p) for p in m.GetConformer().GetPositions()] if m else []
    return xs


def _kotak(a, objs, rigid):
    """Grid box dari --pusat/--ukuran, --acuan (berkas ligan atau 'auto' = ligan asli), atau --kantong N."""
    from .core import mesin as M
    pusat, ukuran = _tiga(a.pusat, "--pusat"), _tiga(a.ukuran, "--ukuran")
    sumber = "pusat diberikan pengguna"
    if pusat is None and a.acuan:
        if a.acuan == "auto":
            asli = [o for o in objs if o.jenis == "ligan" and o.info.get("ligan_asli")]
            if not asli:
                _galat("--acuan auto: struktur tidak memuat ligan asli. Beri berkas ligan acuan atau --pusat.")
            o = max(asli, key=lambda o: o.info.get("atom_berat", 0))
            xs, sumber = _koordinat_objek(o), f"ligan asli {o.nama}"
        else:
            from .core import molekul
            o = next(x for x in molekul.impor_berkas(a.acuan))
            xs, sumber = _koordinat_objek(o), f"ligan acuan {Path(a.acuan).name}"
        pusat = [sum(p[i] for p in xs) / len(xs) for i in range(3)]
        if ukuran is None:
            ukuran = [max(20.0, max(p[i] for p in xs) - min(p[i] for p in xs) + 10) for i in range(3)]
    if pusat is None and a.kantong:
        import tempfile
        from .core import p2rank
        teks_pdb = "\n".join(b[:66] for b in rigid.splitlines() if b.startswith("ATOM"))
        af = any(o.info.get("alphafold") for o in objs)
        k = p2rank.prediksi(teks_pdb, tempfile.mkdtemp(prefix="vd_p2rank_"), konfigurasi="alphafold" if af else None)
        if len(k) < a.kantong:
            _galat(f"P2Rank hanya menemukan {len(k)} kantong.")
        x = k[a.kantong - 1]
        pusat = list(x["pusat"])
        sel = {(c, str(i)) for c, i in x["residu"]}
        xyz = [(float(b[30:38]), float(b[38:46]), float(b[46:54])) for b in rigid.splitlines()
               if b.startswith("ATOM") and (b[21].strip(), b[22:26].strip()) in sel]
        if ukuran is None:
            ukuran = list(p2rank.ukuran_kotak(x, xyz))
        sumber = f"kantong P2Rank #{a.kantong} (skor {x['skor']:.1f})"
    if pusat is None:
        _galat("Tentukan area docking: --pusat X Y Z, --acuan BERKAS|auto, atau --kantong N.")
    k = M.Kotak(pusat=pusat, ukuran=ukuran or [22.5, 22.5, 22.5], spasi=a.spasi)
    return k, sumber


def _jalankan(cmd, cwd, log):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd), capture_output=True, text=True, errors="replace",
                       creationflags=flags)
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"$ {' '.join(str(c) for c in cmd)}\n{r.stdout}\n{r.stderr}\n")
    return r


def _mesin_otomatis():
    """AutoDock-GPU bila program ada dan OpenCL terdeteksi; selain itu Vina (CPU)."""
    from .core import env
    from .core import mesin as M
    if not M.tersedia("adgpu"):
        return "vina"
    try:
        return "adgpu" if env.deteksi().opencl_ok else "vina"
    except Exception:
        return "adgpu"


def cmd_dock(a):
    from .core import analisis
    from .core import mesin as M
    from .core import prep_ligan as pl
    out = Path(a.keluar)
    if out.exists() and any(out.iterdir()) and not a.timpa:
        _galat(f"Folder keluaran {out} tidak kosong. Pakai folder lain atau --timpa.")
    out.mkdir(parents=True, exist_ok=True)
    log = out / "log.txt"
    log.write_text(f"VirmoDock CLI {datetime.now().isoformat(timespec='seconds')}\n$ {' '.join(sys.argv)}\n",
                   encoding="utf-8")
    rigid, flex, info_rec, objs = _siapkan_reseptor(a, out)
    (out / "reseptor.pdbqt").write_text(rigid, encoding="utf-8")
    if flex:
        (out / "flex.pdbqt").write_text(flex, encoding="utf-8")
    kotak, sumber_kotak = _kotak(a, objs, rigid)
    _cetak(f"Grid box: {sumber_kotak} · pusat {' '.join(f'{v:.3f}' for v in kotak.pusat)} · ukuran "
           f"{' × '.join(f'{v:.1f}' for v in kotak.ukuran)} Å")
    ligan = _siapkan_ligan(a.ligan, a, out / "ligan")
    if not ligan:
        _galat("Tidak ada ligan yang siap didocking.")
    mesin = _mesin_otomatis() if a.mesin == "auto" else a.mesin
    if not M.tersedia(mesin):
        _galat(f"{M.PROGRAM[mesin]} tidak ditemukan di folder bin.")
    if flex and mesin == "ad4":
        _galat("AutoDock4 belum mendukung residu fleksibel di VirmoDock; pakai --mesin adgpu atau vina.")
    p = M.Parameter(mesin=mesin, nrun=a.run, exhaustiveness=a.exhaustiveness, num_modes=a.pose,
                    energy_range=a.rentang_energi, cpu=a.cpu, seed=a.seed, devnum=a.gpu or 0)
    folder_pose = out / "pose"
    folder_pose.mkdir(exist_ok=True)
    grid = out / "grid"

    def siapkan_grid():
        tipe = set()
        for _n, f in ligan:
            tipe |= M.tipe_atom(f.read_text())
        if flex:
            tipe |= M.tipe_atom(flex)
        gpf = M.tulis_gpf(rigid, tipe, kotak)
        grid.mkdir(exist_ok=True)
        if M.grid_siap(grid, gpf):
            return
        (grid / "reseptor.pdbqt").write_text(rigid)
        (grid / "reseptor.gpf").write_text(gpf)
        _cetak(f"AutoGrid4: {' × '.join(map(str, kotak.npts()))} titik…")
        cmd, cwd = M.perintah_autogrid(grid)
        r = _jalankan(cmd, cwd, log)
        if r.returncode != 0 or not (grid / "reseptor.maps.fld").exists():
            _galat("AutoGrid4 gagal: " + M.ringkas_galat(r.stdout + r.stderr))

    if mesin in ("adgpu", "ad4"):
        siapkan_grid()
    baris, t_awal = [], time.time()
    for k, (nama, f) in enumerate(ligan, 1):
        t0 = time.time()
        dasar = f.stem
        hasil_status, pesan, pose = "gagal", "", []
        mesin_l = mesin
        for _coba in range(2):
            if mesin_l == "vina":
                keluar = folder_pose / f"{dasar}_out.pdbqt"
                r = _jalankan(M.perintah_vina(out / "reseptor.pdbqt", f, keluar, kotak, p,
                                              flex=out / "flex.pdbqt" if flex else None), out, log)
            elif mesin_l == "adgpu":
                keluar = folder_pose / f"{dasar}.dlg"
                r = _jalankan(M.perintah_adgpu(grid / "reseptor.maps.fld", f, folder_pose / dasar, p,
                                               flex=out / "flex.pdbqt" if flex else None), folder_pose, log)
            else:
                shutil.copy2(f, folder_pose / f.name)
                dpf = folder_pose / f"{dasar}.dpf"
                dpf.write_text(M.tulis_dpf(f.read_text(), f.name, "../grid", p))
                keluar = folder_pose / f"{dasar}.dlg"
                r = _jalankan(M.perintah_ad4(dpf.name, keluar.name), folder_pose, log)
            if keluar.exists():
                try:
                    pose = M.baca_hasil(mesin_l, keluar)
                except Exception as e:
                    pesan = f"hasil tidak terbaca: {e}"
            if pose:
                hasil_status = "selesai"
                break
            teks_galat = (r.stdout or "") + (r.stderr or "")
            if mesin_l == "adgpu" and (M.RE_GALAT_OPENCL.search(teks_galat) or r.returncode in M.KODE_GALAT_DLL):
                _cetak("  AutoDock-GPU tidak bisa memakai GPU (OpenCL); beralih ke Vina (CPU) untuk sisa ligan.")
                mesin = mesin_l = "vina"
                continue
            pesan = pesan or M.ringkas_galat(teks_galat, 300) or f"kode keluar {r.returncode}"
            break
        d = {"ligan": nama, "mesin": M.MESIN[mesin_l], "status": hasil_status, "dG_kcal_mol": "", "Ki": "",
             "LE": "", "atom_berat": "", "torsi": "", "n_pose": len(pose), "ikatan_H": "", "hidrofobik": "",
             "residu_kontak": "", "residu_fleksibel": "", "detik": round(time.time() - t0, 1), "pesan": pesan,
             "berkas_pose": str(keluar.relative_to(out)) if pose else ""}
        if pose:
            terbaik = pose[0]
            teks_lig = f.read_text()
            d.update({"dG_kcal_mol": f"{terbaik.energi:.2f}", "Ki": terbaik.ki,
                      "torsi": int((re.search(r"TORSDOF\s+(\d+)", teks_lig) or [0, 0])[1]),
                      "residu_fleksibel": " ".join(M.residu_flex(terbaik.flex))})
            try:
                mol = analisis.pose_mol(teks_lig, terbaik.pdbqt)
                from rdkit import Chem
                w = Chem.SDWriter(str(folder_pose / f"{dasar}_terbaik.sdf"))
                mol.SetProp("_Name", nama)
                mol.SetProp("dG_kcal_mol", f"{terbaik.energi:.2f}")
                w.write(mol)
                w.close()
                d["atom_berat"] = mol.GetNumHeavyAtoms()
                d["LE"] = f"{analisis.efisiensi_ligan(terbaik.energi, mol.GetNumHeavyAtoms()):.3f}"
                rec = analisis.gabung_flex(analisis.baca_reseptor(rigid), terbaik.flex)
                I = analisis.interaksi(rec, mol)
                n = analisis.hitung(I)
                d["ikatan_H"] = n.get("hbond", 0)
                d["hidrofobik"] = n.get("hidrofobik", 0)
                d["residu_kontak"] = "; ".join(list(analisis.residu_kontak(I))[:25])
            except Exception as e:
                d["pesan"] = f"analisis dilewati: {e}"
            if terbaik.flex:
                (folder_pose / f"{dasar}_flex_terbaik.pdb").write_text(M.flex_ke_pdb(terbaik.flex), encoding="utf-8")
            _cetak(f"[{k}/{len(ligan)}] {nama}: {terbaik.energi:.2f} kcal/mol ({d['detik']} s)")
        else:
            _cetak(f"[{k}/{len(ligan)}] {nama}: GAGAL — {pesan}")
        baris.append(d)
    baris.sort(key=lambda x: float(x["dG_kcal_mol"]) if x["dG_kcal_mol"] != "" else 1e9)
    with open(out / "ringkasan.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(baris[0]))
        w.writeheader()
        w.writerows(baris)
    _tulis_metode(out, a, info_rec, kotak, sumber_kotak, p, mesin, len(ligan), flex)
    ok = sum(1 for b in baris if b["status"] == "selesai")
    _cetak(f"Selesai: {ok}/{len(baris)} ligan · {time.time() - t_awal:.0f} s · {out / 'ringkasan.csv'}")
    return 0 if ok else KODE_GAGAL


def _tulis_metode(out, a, rec, kotak, sumber_kotak, p, mesin, n_lig, flex):
    from . import __version__
    from .core import mesin as M
    if mesin == "vina":
        cari = f"exhaustiveness {p.exhaustiveness}, {p.num_modes} pose, rentang energi {p.energy_range:g} kcal/mol"
    elif mesin == "adgpu":
        cari = f"{p.nrun} run LGA, evaluasi heuristik"
    else:
        cari = f"ga_run {p.nrun}, populasi {p.pop}, {p.nev} evaluasi"
    teks = [
        f"VirmoDock {__version__} (baris perintah), {datetime.now():%Y-%m-%d %H:%M}",
        f"Perintah: {_perintah()}",
        "",
        f"Reseptor: {rec.get('nama')} — {rec.get('metode')}"
        + (f"; {rec.get('atom')} atom, {rec.get('residu')} residu" if rec.get("atom") else "")
        + (f"; ion logam: {', '.join(rec['logam'])}" if rec.get("logam") else ""),
        f"Residu fleksibel: {', '.join(rec.get('fleksibel') or []) or ('dari berkas' if flex else 'tidak (reseptor kaku)')}",
        f"Ligan: {n_lig} (pH {a.ph_ligan}, protonasi {a.protonasi_ligan}, "
        f"{'tanpa minimisasi' if a.tanpa_minimisasi else 'minimisasi MMFF94'}; PDBQT oleh Meeko)",
        f"Grid box: {sumber_kotak}; pusat ({', '.join(f'{v:.3f}' for v in kotak.pusat)}) Å; ukuran "
        f"{' × '.join(f'{v:.1f}' for v in kotak.ukuran)} Å; spasi {kotak.spasi} Å",
        f"Mesin: {M.MESIN[mesin]}; {cari}; seed {p.seed or 'acak'}",
    ]
    (out / "metode.txt").write_text("\n".join(teks) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ info / uji
def cmd_info(a):
    from . import __version__
    from .core import env, mesin as M, paths
    _cetak(f"VirmoDock {__version__}")
    _cetak(f"Folder program: {paths.BIN}")
    for k in ("adgpu", "vina", "ad4"):
        _cetak(f"  {M.MESIN[k]:<15} {'ada' if M.tersedia(k) else 'TIDAK ADA'}")
    try:
        e = env.deteksi()
        g = e.gpu_utama
        _cetak(f"GPU: {getattr(g, 'nama', None) or 'tidak terdeteksi'} · OpenCL {'ya' if e.opencl_ok else 'tidak'} "
               f"· mode bawaan {e.mode_bawaan}")
        _cetak(f"CPU: {e.cpu} ({e.inti} inti) · RAM {e.ram_gb:.0f} GB")
    except Exception as ex:
        _cetak(f"GPU: deteksi gagal ({ex})")
    return 0


def cmd_uji(a):
    from .core import ujimandiri
    keluar = a.keluar or "uji_mandiri.json"
    ok = ujimandiri.tulis(keluar)
    data = json.loads(Path(keluar).read_text(encoding="utf-8"))
    for h in data["hasil"]:
        _cetak(("  OK    " if h["ok"] else "  GAGAL ") + h["uji"] + " — " + h["detail"].splitlines()[0][:160])
    _cetak(f"{sum(h['ok'] for h in data['hasil'])}/{len(data['hasil'])} lulus · {keluar}")
    return 0 if ok else KODE_GAGAL


# ------------------------------------------------------------------ argparse
def _opsi_reseptor_arg(p, wajib=True):
    if wajib:
        p.add_argument("reseptor", help="berkas PDB/CIF/PDBQT, kode PDB (1HSG), atau AF-<UniProt> (AF-P00918)")
    p.add_argument("--protonasi", choices=("propka", "templat"), default="propka",
                   help="propka = PROPKA/PDB2PQR pada pH (bawaan); templat = keadaan baku Meeko")
    p.add_argument("--ph", type=float, default=7.4, help="pH protonasi reseptor (bawaan 7.4)")
    p.add_argument("--rantai", help="rantai yang dipakai, mis. A,B (bawaan semua)")
    p.add_argument("--pertahankan-air", action="store_true", help="jangan hapus molekul air")
    p.add_argument("--buang-logam", action="store_true", help="hapus ion logam (bawaan dipertahankan)")
    p.add_argument("--flex", help="residu fleksibel, mis. A:25,B:25 (maks. 8; Vina/AD-GPU)")
    p.add_argument("--af-ambang", type=float, default=50.0,
                   help="AlphaFold: pangkas ujung N/C dengan pLDDT < ambang (0 = tidak dipangkas)")


def _opsi_ligan_arg(p):
    p.add_argument("--ph-ligan", type=float, default=7.4, help="pH protonasi ligan (bawaan 7.4)")
    p.add_argument("--protonasi-ligan", choices=("obabel", "dimorphite", "tidak"), default="obabel")
    p.add_argument("--tanpa-minimisasi", action="store_true", help="lewati minimisasi MMFF94")


def parser():
    ap = argparse.ArgumentParser(prog="VirmoDock-cli", description="VirmoDock tanpa jendela (docking batch & skrip).",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("Contoh:")[1].join(["Contoh:", ""]))
    sub = ap.add_subparsers(dest="perintah", metavar="perintah")

    s = sub.add_parser("info", help="versi, program mesin, GPU")
    s.set_defaults(fn=cmd_info)
    s = sub.add_parser("uji", help="uji mandiri komponen")
    s.add_argument("-o", "--keluar", help="berkas hasil JSON")
    s.set_defaults(fn=cmd_uji)

    s = sub.add_parser("reseptor", help="siapkan reseptor -> PDBQT")
    _opsi_reseptor_arg(s)
    s.add_argument("-o", "--keluar", help="berkas PDBQT keluaran")
    s.add_argument("--keluar-flex", help="berkas PDBQT residu fleksibel (bawaan <keluar>_flex.pdbqt)")
    s.set_defaults(fn=cmd_reseptor)

    s = sub.add_parser("ligan", help="siapkan ligan -> PDBQT")
    s.add_argument("masukan", nargs="+", help="berkas SDF/MOL2/PDB/SMI, folder, atau teks SMILES")
    s.add_argument("-o", "--keluar", default="ligan_pdbqt", help="folder keluaran")
    _opsi_ligan_arg(s)
    s.set_defaults(fn=cmd_ligan)

    s = sub.add_parser("kantong", help="deteksi kantong P2Rank")
    s.add_argument("protein", help="berkas PDB/CIF, kode PDB, atau AF-<UniProt>")
    s.add_argument("-n", type=int, default=5, help="jumlah kantong ditampilkan")
    s.add_argument("--alphafold", action="store_true", help="paksa konfigurasi P2Rank 'alphafold' (model prediksi)")
    s.add_argument("--json", action="store_true", help="keluaran JSON")
    s.set_defaults(fn=cmd_kantong)

    s = sub.add_parser("alphafold", help="unduh model AlphaFold DB")
    s.add_argument("aksesi", help="kode UniProt, mis. P00918")
    s.add_argument("-o", "--keluar", help="berkas PDB keluaran")
    s.add_argument("--ambang", type=float, default=50.0, help="pangkas ujung N/C pLDDT < ambang (0 = tidak)")
    s.set_defaults(fn=cmd_alphafold)

    s = sub.add_parser("dock", help="docking satu perintah -> ringkasan.csv")
    s.add_argument("-r", "--reseptor", required=True,
                   help="PDBQT siap, berkas PDB/CIF, kode PDB, atau AF-<UniProt> (disiapkan otomatis)")
    s.add_argument("-l", "--ligan", nargs="+", required=True, help="berkas/folder ligan (PDBQT/SDF/MOL2/SMI) atau SMILES")
    s.add_argument("-o", "--keluar", required=True, help="folder hasil")
    s.add_argument("--timpa", action="store_true", help="izinkan folder keluaran yang tidak kosong")
    g = s.add_argument_group("area docking (pilih satu)")
    g.add_argument("--pusat", nargs=3, type=float, metavar=("X", "Y", "Z"))
    g.add_argument("--acuan", help="berkas ligan acuan, atau 'auto' = ligan asli di struktur PDB")
    g.add_argument("--kantong", type=int, metavar="N", help="kantong P2Rank peringkat N")
    s.add_argument("--ukuran", nargs=3, type=float, metavar=("SX", "SY", "SZ"), help="ukuran kotak (Å)")
    s.add_argument("--spasi", type=float, default=0.375, help="spasi grid AutoGrid (Å)")
    s.add_argument("--mesin", choices=("auto", "adgpu", "vina", "ad4"), default="auto",
                   help="auto = AutoDock-GPU bila ada, beralih ke Vina bila OpenCL gagal")
    s.add_argument("--run", type=int, default=50, help="jumlah run AD-GPU/AD4")
    s.add_argument("--exhaustiveness", type=int, default=16, help="Vina")
    s.add_argument("--pose", type=int, default=9, help="jumlah pose Vina")
    s.add_argument("--rentang-energi", type=float, default=3.0, help="Vina energy_range")
    s.add_argument("--cpu", type=int, default=0, help="thread Vina (0 = otomatis)")
    s.add_argument("--gpu", type=int, help="nomor perangkat OpenCL AD-GPU (--devnum)")
    s.add_argument("--seed", type=int, default=42, help="seed acak (0 = acak)")
    s.add_argument("--berkas-flex", help="PDBQT residu fleksibel siap (bila reseptor berupa PDBQT kaku)")
    _opsi_reseptor_arg(s, wajib=False)
    _opsi_ligan_arg(s)
    s.set_defaults(fn=cmd_dock)
    return ap


def main(argv=None):
    for aliran in (sys.stdout, sys.stderr):
        try:
            aliran.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    try:
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
    except ImportError:
        pass
    try:
        return a.fn(a) or 0
    except KeyboardInterrupt:
        _galat("dibatalkan pengguna", 130)
    except SystemExit:
        raise
    except Exception as e:
        _galat(str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__)


if __name__ == "__main__":
    sys.exit(main())
