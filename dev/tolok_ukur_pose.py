"""Tolok ukur prediksi pose VirmoLab pada Astex Diverse Set (85) dan PoseBusters Benchmark Set (428).

Data: Zenodo 10.5281/zenodo.8278563 (CC BY 4.0), diekstrak ke <akar>/posebusters/. Tiap kompleks
disiapkan dan di-docking dengan pipeline VirmoLab sendiri, bukan berkas siap pakai:
  reseptor  prep_reseptor.siapkan (PROPKA pH 7,4, kofaktor dipertahankan, semua ion logam dipertahankan)
  ligan     prep_ligan.siapkan_satu dari konformer RDKit <id>_ligand_start_conf.sdf (BUKAN pose kristal)
  kotak     pusat = rerata atom berat ligan kristal, sisi = maks(20, bentang + 10) Å (aturan "Pusat di ligan asli")
  docking   preset Standar: AutoDock-GPU nrun 50 + heuristik, atau Vina exhaustiveness 16; benih 42
Penilaian: RMSD simetri atom berat pose teratas terhadap <id>_ligand.sdf (tanpa penjajaran), sukses <= 2 Å;
validitas fisik pose teratas dengan PoseBusters (konfigurasi "dock").

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/tolok_ukur_pose.py siapkan --set astex --pekerja 6
  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/tolok_ukur_pose.py docking --set astex --mesin adgpu
  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/tolok_ukur_pose.py ringkas
Akar data: variabel VIRMOLAB_TOLOK (bawaan C:/VirmoLab-tolok-ukur). Hasil per kompleks ditambahkan ke
<akar>/hasil/pose_<set>_<mesin>.csv sehingga run yang terputus bisa dilanjutkan.
"""
import argparse
import csv
import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

AKAR = Path(os.environ.get("VIRMOLAB_TOLOK", "C:/VirmoLab-tolok-ukur"))
DATA = AKAR / "posebusters"
KERJA = AKAR / "kerja_pose"
HASIL = AKAR / "hasil"
SET = {"astex": "astex_diverse_set", "posebusters": "posebusters_benchmark_set"}
KOLOM = ["id", "set", "mesin", "status", "alasan", "n_berat", "n_torsi", "dg", "rmsd_top1", "rmsd_terbaik",
         "pb_lulus", "pb_gagal", "detik_docking"]


def daftar_id(nama_set):
    teks = (DATA / f"{SET[nama_set]}_ids.txt").read_text().split()
    return [t.strip() for t in teks if t.strip()]


def folder(nama_set, i):
    return DATA / SET[nama_set] / i


def kerja(nama_set, i):
    d = KERJA / nama_set / i
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mol_sdf(path):
    from rdkit import Chem
    m = Chem.MolFromMolFile(str(path), removeHs=False)
    if m is None:
        m = Chem.MolFromMolFile(str(path), removeHs=False, sanitize=False)
        if m is not None:
            m.UpdatePropertyCache(strict=False)
    return m


def kotak_ligan(mol):
    import numpy as np
    from virmolab.core import mesin
    xyz = np.array([mol.GetConformer().GetAtomPosition(a.GetIdx()) for a in mol.GetAtoms()
                    if a.GetAtomicNum() > 1])
    pusat = xyz.mean(0).tolist()
    bentang = (xyz.max(0) - xyz.min(0)).tolist()
    return mesin.Kotak(pusat=pusat, ukuran=[max(20.0, b + 10.0) for b in bentang])


def siapkan_satu(nama_set, i):
    """Preparasi reseptor + ligan satu kompleks; hasil disimpan di folder kerja (dipakai semua mesin)."""
    from virmolab.core import prep_ligan, prep_reseptor
    d = kerja(nama_set, i)
    tanda = d / "siap.json"
    if tanda.exists():
        return json.loads(tanda.read_text(encoding="utf-8"))
    src = folder(nama_set, i)
    info = {"id": i, "status": "gagal"}
    t0 = time.time()
    try:
        teks = (src / f"{i}_protein.pdb").read_text(encoding="utf-8", errors="replace")
        opsi = prep_reseptor.OpsiReseptor(protonasi="propka", ph=7.4, kofaktor=True, radius_logam=0.0)
        hr = prep_reseptor.siapkan(teks, opsi)
        (d / "reseptor.pdbqt").write_text(hr.pdbqt, encoding="utf-8")
        (d / "reseptor_bersih.pdb").write_text(hr.pdb_bersih, encoding="utf-8")
        hl = prep_ligan.siapkan_satu(i, (src / f"{i}_ligand_start_conf.sdf").read_text(encoding="utf-8"), "sdf",
                                     prep_ligan.OpsiLigan())
        if hl.status == "gagal":
            raise RuntimeError("ligan: " + hl.alasan)
        (d / "ligan.pdbqt").write_text(hl.pdbqt, encoding="utf-8")
        info.update(status="siap", metode_reseptor=hr.metode, atom_reseptor=hr.atom, torsi=hl.torsi,
                    peringatan=hr.peringatan[:5], detik=round(time.time() - t0, 1))
    except Exception as e:
        info.update(alasan=f"{type(e).__name__}: {e}"[:300], detik=round(time.time() - t0, 1))
    tanda.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


def _jalan(cmd, cwd=None, batas=1800):
    import subprocess
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, timeout=batas,
                       creationflags=0x08000000 if os.name == "nt" else 0)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def docking_satu(nama_set, i, nama_mesin, devnum=None):
    from virmolab.core import analisis, mesin, qc
    from virmolab.ui.panel_docking import PRESET
    d = kerja(nama_set, i)
    src = folder(nama_set, i)
    baris = {"id": i, "set": nama_set, "mesin": nama_mesin, "status": "gagal"}
    siap = json.loads((d / "siap.json").read_text(encoding="utf-8")) if (d / "siap.json").exists() else {}
    if siap.get("status") != "siap":
        baris.update(alasan="preparasi: " + siap.get("alasan", "belum disiapkan"))
        return baris
    kristal = _mol_sdf(src / f"{i}_ligand.sdf")
    kotak = kotak_ligan(kristal)
    p = mesin.Parameter(mesin=nama_mesin, seed=42, **{k: v for k, v in PRESET["Standar"].items()})
    rec, lig = d / "reseptor.pdbqt", d / "ligan.pdbqt"
    teks_lig = lig.read_text(encoding="utf-8")
    t0 = time.time()
    try:
        if nama_mesin == "vina":
            keluar = d / "vina_out.pdbqt"
            kode, log = _jalan(mesin.perintah_vina(rec, lig, keluar, kotak, p))
        elif nama_mesin == "unidock":
            from virmolab.core import unidock as U
            ud = d / "ud"
            if ud.exists():
                for f in ud.glob("u*_out.pdbqt"):
                    f.unlink()
            skrip, _peta = U.tulis_skrip(rec, [lig], ud, kotak, mode="balance", num_modes=p.num_modes, seed=p.seed)
            kode, log = _jalan(U.perintah_wsl(skrip))
            keluar = U.keluaran_ligan(ud, "u00001")
        else:
            g = d / "grid"
            g.mkdir(exist_ok=True)
            gpf = mesin.tulis_gpf(rec.read_text(encoding="utf-8"), mesin.tipe_atom(teks_lig), kotak)
            if not mesin.grid_siap(g, gpf):
                (g / "reseptor.pdbqt").write_text(rec.read_text(encoding="utf-8"), encoding="utf-8")
                (g / "reseptor.gpf").write_text(gpf)
                cmd, cwd = mesin.perintah_autogrid(g)
                kode, log = _jalan(cmd, cwd=cwd)
                if kode != 0:
                    raise RuntimeError("autogrid: " + mesin.ringkas_galat(log, 300))
            keluar = d / "adgpu.dlg"
            kode, log = _jalan(mesin.perintah_adgpu(g / "reseptor.maps.fld", lig, d / "adgpu", p, devnum=devnum),
                               cwd=d)
        detik = time.time() - t0
        pose = mesin.baca_hasil(nama_mesin, keluar) if keluar.exists() else []
        if not pose:
            raise RuntimeError("tidak ada pose; " + mesin.ringkas_galat(log, 300))
        rmsd = []
        mols = []
        for ps in pose:
            try:
                m = analisis.pose_mol(teks_lig, ps.pdbqt)
                mols.append(m)
                rmsd.append(analisis.rmsd_simetri(m, kristal))
            except Exception:
                mols.append(None)
                rmsd.append(float("nan"))
        import math
        ok = [r for r in rmsd if not math.isnan(r)]
        baris.update(status="selesai", dg=round(pose[0].energi, 2), detik_docking=round(detik, 1),
                     n_berat=kristal.GetNumHeavyAtoms(), n_torsi=siap.get("torsi"),
                     rmsd_top1=round(rmsd[0], 3) if not math.isnan(rmsd[0]) else "",
                     rmsd_terbaik=round(min(ok), 3) if ok else "")
        if mols[0] is not None and qc.tersedia():
            q = qc.periksa(mols[0], src / f"{i}_protein.pdb")
            baris.update(pb_lulus=int(q["lulus"]), pb_gagal="; ".join(q["gagal"]))
    except Exception as e:
        baris.update(alasan=f"{type(e).__name__}: {e}"[:300], detik_docking=round(time.time() - t0, 1))
    return baris


def _csv(nama_set, nama_mesin):
    HASIL.mkdir(parents=True, exist_ok=True)
    return HASIL / f"pose_{nama_set}_{nama_mesin}.csv"


def sudah(path):
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        return {r["id"] for r in csv.DictReader(f)}


def perintah_siapkan(a):
    ids = daftar_id(a.set)[:a.n] if a.n else daftar_id(a.set)
    t0 = time.time()
    n_siap = 0
    with ProcessPoolExecutor(max_workers=a.pekerja) as ex:
        fut = {ex.submit(siapkan_satu, a.set, i): i for i in ids}
        for k, f in enumerate(as_completed(fut), 1):
            try:
                r = f.result()
            except Exception as e:
                r = {"id": fut[f], "status": "gagal", "alasan": str(e)}
            n_siap += r.get("status") == "siap"
            print(f"[{k}/{len(ids)}] {r['id']}: {r['status']} {r.get('alasan', '')[:120]}", flush=True)
    print(f"siap {n_siap}/{len(ids)} dalam {time.time() - t0:.0f} s", flush=True)


def perintah_docking(a):
    ids = daftar_id(a.set)[:a.n] if a.n else daftar_id(a.set)
    path = _csv(a.set, a.mesin)
    ada = sudah(path)
    baru = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM, extrasaction="ignore")
        if baru:
            w.writeheader()
        for k, i in enumerate(ids, 1):
            if i in ada:
                continue
            try:
                r = docking_satu(a.set, i, a.mesin, a.devnum)
            except Exception as e:
                r = {"id": i, "set": a.set, "mesin": a.mesin, "status": "gagal",
                     "alasan": f"{type(e).__name__}: {e}"[:300]}
                traceback.print_exc()
            w.writerow(r)
            f.flush()
            print(f"[{k}/{len(ids)}] {i} {a.mesin}: {r['status']} RMSD {r.get('rmsd_top1', '')} "
                  f"PB {r.get('pb_lulus', '')} {r.get('alasan', '')[:100]}", flush=True)


def ringkas_csv(path):
    import math
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = len(rows)
    sel = [r for r in rows if r["status"] == "selesai" and r["rmsd_top1"] != ""]
    r1 = [float(r["rmsd_top1"]) for r in sel]
    rb = [float(r["rmsd_terbaik"]) for r in sel if r["rmsd_terbaik"] != ""]
    pb = [r for r in sel if r.get("pb_lulus") in ("0", "1")]
    sukses = sum(x <= 2.0 for x in r1)
    sukses_pb = sum(float(r["rmsd_top1"]) <= 2.0 and r["pb_lulus"] == "1" for r in pb)
    med = sorted(r1)[len(r1) // 2] if r1 else math.nan

    def wilson(k, m, z=1.96):
        if not m:
            return (math.nan, math.nan)
        p = k / m
        d = 1 + z * z / m
        c = (p + z * z / (2 * m)) / d
        h = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d
        return (c - h, c + h)
    return {"n": n, "dinilai": len(sel), "gagal": n - len(sel),
            "sukses_rmsd2": sukses, "persen_rmsd2": 100 * sukses / n if n else math.nan,
            "ci95_rmsd2": [100 * x for x in wilson(sukses, n)],
            "sukses_rmsd2_pb": sukses_pb, "persen_rmsd2_pb": 100 * sukses_pb / n if n else math.nan,
            "ci95_rmsd2_pb": [100 * x for x in wilson(sukses_pb, n)],
            "persen_terbaik_rmsd2": 100 * sum(x <= 2.0 for x in rb) / n if n else math.nan,
            "median_rmsd_top1": med,
            "detik_median": sorted(float(r["detik_docking"]) for r in sel)[len(sel) // 2] if sel else math.nan}


def perintah_ringkas(a):
    out = {}
    for p in sorted(HASIL.glob("pose_*.csv")):
        out[p.stem] = ringkas_csv(p)
        r = out[p.stem]
        print(f"{p.stem}: n={r['n']} dinilai={r['dinilai']} RMSD<=2: {r['persen_rmsd2']:.1f}% "
              f"(95% CI {r['ci95_rmsd2'][0]:.1f}-{r['ci95_rmsd2'][1]:.1f}); RMSD<=2 & PB-valid: "
              f"{r['persen_rmsd2_pb']:.1f}%; terbaik-dari-N: {r['persen_terbaik_rmsd2']:.1f}%; "
              f"median RMSD {r['median_rmsd_top1']:.2f} Å", flush=True)
    (HASIL / "ringkasan_pose.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("perintah", choices=["siapkan", "docking", "ringkas"])
    ap.add_argument("--set", choices=list(SET), default="astex")
    ap.add_argument("--mesin", choices=["adgpu", "vina", "unidock"], default="adgpu")
    ap.add_argument("--pekerja", type=int, default=4)
    ap.add_argument("--n", type=int, default=0, help="hanya n kompleks pertama (uji cepat)")
    ap.add_argument("--devnum", type=int, default=None)
    a = ap.parse_args()
    {"siapkan": perintah_siapkan, "docking": perintah_docking, "ringkas": perintah_ringkas}[a.perintah](a)


if __name__ == "__main__":
    main()
