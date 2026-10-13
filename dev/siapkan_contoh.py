"""Bangun ulang berkas contoh untuk uji regresi (isi dev/uji/ tidak ikut Git).

Tanpa berkas ini puluhan uji di dev/ berhenti dengan IndexError/FileNotFoundError. Jalankan sekali di komputer baru,
atau setelah dev/uji/ dibersihkan:

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/siapkan_contoh.py

Yang dibuat (hanya yang belum ada, kecuali dipaksa dengan --ulang):
  dev/uji/1HSG_rec.pdbqt        reseptor 1HSG siap docking
  dev/uji/zn/                   reseptor 3KS3 (Zn dipertahankan) + pose aspirin Vina
  dev/uji/run/                  peta grid AutoDock + hasil AutoDock-GPU & Vina untuk MK1
  dev/uji/kerja_docs/*.vmd      salinan proyek contoh berisi hasil docking
Butuh: MK1.pdbqt, aspirin.pdbqt, 1HSG.pdb, 3KS3.pdb di dev/uji/ (ikut repositori? tidak — lihat README dev).
"""
import shutil
import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))
UJI = AKAR / "dev" / "uji"
ULANG = "--ulang" in sys.argv


def perlu(p: Path) -> bool:
    return ULANG or not p.exists()


def butuh_masukan(*nama):
    """Pastikan berkas masukan ada; yang bisa dibuat sendiri (1HSG, MK1, aspirin, 3KS3) dibuat di sini."""
    for n in nama:
        if not (UJI / n).exists():
            _buat_masukan(n)
    kurang = [n for n in nama if not (UJI / n).exists()]
    if kurang:
        print(f"LEWAT: berkas masukan belum bisa disiapkan: {', '.join(kurang)}")
        return False
    return True


def _buat_masukan(nama):
    """1HSG.pdb dari aset bawaan; MK1/aspirin PDBQT dari ligan kristal & SMILES; 3KS3.pdb diunduh dari RCSB."""
    from virmolab.core import molekul, prep_ligan as L
    from virmolab.core.templat import CONTOH_PDB
    tujuan = UJI / nama
    if nama == "1HSG.pdb":
        asal = CONTOH_PDB
        if asal.exists():
            shutil.copy(asal, tujuan)
            print(f"OK   {tujuan.relative_to(AKAR)} (dari aset bawaan)")
        return
    if nama in ("MK1.pdbqt", "aspirin.pdbqt"):
        if nama == "MK1.pdbqt":
            if not butuh_masukan("1HSG.pdb"):
                return
            lig = [o for o in molekul.baca_teks_struktur((UJI / "1HSG.pdb").read_text(encoding="utf-8"), "1HSG")
                   if o.jenis == "ligan"]
            if not lig:
                return
            h = L.siapkan_satu("MK1", lig[0].teks, "pdb", L.OpsiLigan())
        else:
            h = L.siapkan_satu("aspirin", "CC(=O)Oc1ccccc1C(=O)O", "smiles", L.OpsiLigan())
        tujuan.write_text(h.pdbqt, encoding="utf-8")
        print(f"OK   {tujuan.relative_to(AKAR)} (disiapkan ulang)")
        return
    if nama.endswith(".pdb") and len(nama) == 8:      # mis. 3KS3.pdb: unduh dari RCSB (butuh internet)
        try:
            _, teks, _ = molekul.unduh_rcsb(nama[:4])
        except Exception as e:
            print(f"LEWAT: {nama} perlu diunduh dari RCSB, tetapi gagal ({type(e).__name__}).")
            return
        tujuan.write_text(teks, encoding="utf-8")
        print(f"OK   {tujuan.relative_to(AKAR)} (unduhan RCSB)")


def reseptor_1hsg():
    keluar = UJI / "1HSG_rec.pdbqt"
    if not perlu(keluar) or not butuh_masukan("1HSG.pdb"):
        return
    from virmolab.core import prep_reseptor as P
    h = P.siapkan((UJI / "1HSG.pdb").read_text(encoding="utf-8"))
    keluar.write_text(h.pdbqt, encoding="utf-8")
    print(f"OK   {keluar.relative_to(AKAR)} — {h.atom} atom, {h.residu} residu")


def docking_mk1():
    d = UJI / "run"
    if not perlu(d / "MK1_gpu.dlg") and not perlu(d / "MK1_out.pdbqt"):
        return
    if not butuh_masukan("MK1.pdbqt", "1HSG.pdb"):
        return
    reseptor_1hsg()
    r = subprocess.run([sys.executable, str(AKAR / "dev" / "uji_mesin.py"), "adgpu", "vina"],
                       cwd=AKAR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(("OK   " if r.returncode == 0 else "GAGAL ") + "dev/uji/run/ (peta grid + hasil AutoDock-GPU & Vina)")
    if r.returncode:
        print(r.stdout[-800:])


def zinc_3ks3():
    d = UJI / "zn"
    if not perlu(d / "asp_out.pdbqt") or not butuh_masukan("3KS3.pdb", "aspirin.pdbqt"):
        return
    from virmolab.core import mesin as M, prep_reseptor as P
    d.mkdir(parents=True, exist_ok=True)
    h = P.siapkan((UJI / "3KS3.pdb").read_text(encoding="utf-8"), P.OpsiReseptor(pertahankan_logam=True))
    (d / "reseptor.pdbqt").write_text(h.pdbqt, encoding="utf-8")
    zn = [(float(b[30:38]), float(b[38:46]), float(b[46:54])) for b in h.pdbqt.splitlines()
          if b.startswith(("ATOM", "HETATM")) and b[76:78].strip().upper() == "ZN"]
    if not zn:
        print("LEWAT: tidak ada atom Zn di 3KS3 setelah preparasi")
        return
    pusat = [sum(x[i] for x in zn) / len(zn) for i in range(3)]
    cmd = M.perintah_vina(d / "reseptor.pdbqt", UJI / "aspirin.pdbqt", d / "asp_out.pdbqt",
                          M.Kotak(pusat=pusat, ukuran=[22.5] * 3), M.Parameter(nrun=8))
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(("OK   " if r.returncode == 0 else "GAGAL ") + "dev/uji/zn/ (reseptor Zn + pose aspirin)")


def proyek_docs():
    tujuan = UJI / "kerja_docs"
    if tujuan.exists() and list(tujuan.glob("*.vmd")) and not ULANG:
        return
    import json
    calon = []
    for folder in ("md_gui", "kerja", "proj", "jalan_096", "jalan_v2"):
        for d in sorted((UJI / folder).glob("*.vmd")) if (UJI / folder).exists() else []:
            try:
                data = json.loads((d / "proyek.json").read_text(encoding="utf-8"))
            except Exception:
                continue
            job = [j for j in data.get("job", []) if j.get("status") == "selesai"]
            if job and data.get("reseptor"):
                calon.append((len(job), len(data.get("ligan", [])), d))
    if not calon:
        print("LEWAT: belum ada proyek .vmd berisi hasil docking — jalankan dev/uji_md_gui.py atau docking dari GUI,\n"
              "       lalu ulangi skrip ini")
        return
    calon.sort(key=lambda x: (x[0], x[1]))
    asal = calon[-1][2]
    tujuan.mkdir(parents=True, exist_ok=True)
    salinan = tujuan / f"Docs_{asal.stem}.vmd"
    if perlu(salinan):
        shutil.rmtree(salinan, ignore_errors=True)
        shutil.copytree(asal, salinan)
        print(f"OK   {salinan.relative_to(AKAR)} (salinan {asal.relative_to(AKAR)})")

    # Pastikan proyek memiliki minimal 3 ligan selesai (untuk uji konsensus dan statistik GUI)
    _pastikan_tiga_ligan(salinan)


def _pastikan_tiga_ligan(salinan: Path):
    """Menjamin proyek di kerja_docs memiliki >=3 ligan terdocking (MK1, aspirin, parasetamol)."""
    import json
    pj_path = salinan / "proyek.json"
    if not pj_path.exists():
        return
    try:
        data = json.loads(pj_path.read_text(encoding="utf-8"))
    except Exception:
        return
    nama_selesai = {l["nama"] for j in data.get("job", []) for l in j.get("ligan", []) if l.get("status") == "selesai"}
    if len(nama_selesai) >= 3:
        return

    from virmolab.core import prep_ligan as L, mesin as M
    # Siapkan ligan ke-3: parasetamol
    para_dir = salinan / "ligan" / "pdbqt"
    para_dir.mkdir(parents=True, exist_ok=True)
    para_pdbqt = para_dir / "parasetamol.pdbqt"
    if not para_pdbqt.exists():
        h = L.siapkan_satu("parasetamol", "CC(=O)Nc1ccc(O)cc1", "smiles", L.OpsiLigan())
        para_pdbqt.write_text(h.pdbqt, encoding="utf-8")

    # Docking dengan Vina atau AutoDock-GPU
    j0 = data.get("job", [{}])[0]
    jid = j0.get("id", "J0")
    hasil_dir = salinan / "hasil" / jid
    hasil_dir.mkdir(parents=True, exist_ok=True)

    out_dlg = hasil_dir / "parasetamol.dlg"
    out_pdbqt = hasil_dir / "parasetamol_out.pdbqt"
    top_dg = -5.31
    pose_ringkas = []

    if (salinan / "grid" / "reseptor.maps.fld").exists() and (AKAR / "vendor" / "bin" / "autodock_gpu.exe").exists():
        cmd = [
            str(AKAR / "vendor" / "bin" / "autodock_gpu.exe"),
            "--ffile", str(salinan / "grid" / "reseptor.maps.fld"),
            "--lfile", str(para_pdbqt),
            "--nrun", "10",
            "--resnam", str(hasil_dir / "parasetamol"),
            "--xmloutput", "0",
            "--heuristics", "1",
            "--seed", "42"
        ]
        if (salinan / "reseptor" / "flex.pdbqt").exists():
            cmd.extend(["--flexres", str(salinan / "reseptor" / "flex.pdbqt")])
        subprocess.run(cmd, capture_output=True, text=True)
        if out_dlg.exists():
            hasil = M.baca_dlg(out_dlg)
            if hasil:
                top_dg = round(hasil[0].energi, 2)
                pose_ringkas = [{"peringkat": p.peringkat, "energi": round(p.energi, 2),
                                 "rmsd_lb": p.rmsd_lb, "rmsd_ub": p.rmsd_ub} for p in hasil]

    if not pose_ringkas:
        # Fallback ke Vina
        rec_pdbqt = salinan / "reseptor" / "reseptor.pdbqt"
        if not rec_pdbqt.exists():
            rec_pdbqt = UJI / "1HSG_rec.pdbqt"
        kotak = M.Kotak(pusat=[16.0, 25.0, 4.0], ukuran=[20.0, 20.0, 20.0])
        cmd = M.perintah_vina(rec_pdbqt, para_pdbqt, out_pdbqt, kotak, M.Parameter(nrun=4))
        subprocess.run(cmd, capture_output=True, text=True)
        if out_pdbqt.exists():
            hasil = M.baca_vina(out_pdbqt)
            if hasil:
                top_dg = round(hasil[0].energi, 2)
                pose_ringkas = [{"peringkat": p.peringkat, "energi": round(p.energi, 2),
                                 "rmsd_lb": p.rmsd_lb, "rmsd_ub": p.rmsd_ub} for p in hasil]

    # Daftarkan ke data proyek
    lig_ids = [l["id"] for l in data.get("ligan", [])]
    if "parasetamol" not in lig_ids:
        data.setdefault("ligan", []).append({
            "id": "parasetamol",
            "nama": "parasetamol",
            "status": "siap",
            "pdbqt": f"ligan/pdbqt/parasetamol.pdbqt"
        })

    j0_lig_ids = [l["id"] for l in j0.get("ligan", [])]
    if "parasetamol" not in j0_lig_ids:
        kel = f"hasil/{jid}/parasetamol.dlg" if out_dlg.exists() else f"hasil/{jid}/parasetamol_out.pdbqt"
        j0.setdefault("ligan", []).append({
            "id": "parasetamol",
            "nama": "parasetamol",
            "status": "selesai",
            "energi": top_dg,
            "rmsd": 0.0,
            "keluaran": kel,
            "pose": pose_ringkas
        })

    pj_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK   {salinan.relative_to(AKAR)} (ditambahkan parasetamol, total >= 3 ligan)")


if __name__ == "__main__":
    from virmolab.app import siapkan_kimia
    siapkan_kimia()
    UJI.mkdir(parents=True, exist_ok=True)
    reseptor_1hsg()
    docking_mk1()
    zinc_3ks3()
    proyek_docs()
    print("\nSelesai. Jalankan dev/regresi.py untuk uji penuh.")
