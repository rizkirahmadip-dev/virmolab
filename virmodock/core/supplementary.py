"""Paket Supplementary (.zip) untuk publikasi - rencana C6.

Struktur:
  README.txt                 isi tiap folder, cara membuka, versi
  reseptor/                  PDBQT siap docking, PDB bersih, laporan preparasi, pKa, residu fleksibel
  ligan/                     PDBQT masukan tiap ligan (setelah preparasi)
  pose/terbaik.sdf           pose terbaik semua ligan (tag ΔG, Ki, LE, interaksi, MM/GBSA)
  pose/semua/                semua pose per ligan (SDF bertag)
  kompleks/                  kompleks reseptor-ligan PDB (n teratas)
  tabel/hasil.csv            tabel hasil lengkap (pemisah ; dan koma desimal) + hasil_titik.csv (pemisah , titik)
  parameter/                 parameter tiap job (JSON: mesin, grid box, seed, residu fleksibel) + proyek.json ringkas
  mmgbsa/                    hasil MD & MM/GBSA (hasil.json; tanpa trajektori besar)
  versi_perangkat_lunak.txt  versi VirmoDock, mesin, dan pustaka
  SHA256SUMS.txt             checksum semua berkas
"""
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from importlib import metadata
from pathlib import PureWindowsPath

from . import analisis
from . import ekspor as E
from . import mesin as M
from .prep_reseptor import pdbqt_ke_pdb
from .proyek import nama_aman

PUSTAKA = ["rdkit", "meeko", "gemmi", "numpy", "scipy", "posebusters", "propka", "pdb2pqr", "dimorphite-dl",
           "openmm", "pdbfixer", "openmmforcefields", "openff-toolkit", "openff-nagl", "openforcefields", "admet-ai"]


def _versi_teks(versi_app, info_mesin=None):
    baris = [f"VirmoDock {versi_app}", f"Dibuat: {datetime.now():%Y-%m-%d %H:%M}", ""]
    for k, v in (info_mesin or {}).items():
        baris.append(f"{k}: {v}")
    baris.append("")
    for p in PUSTAKA:
        try:
            baris.append(f"{p} {metadata.version(p)}")
        except metadata.PackageNotFoundError:
            pass
    return "\n".join(baris) + "\n"


def _readme(pr, versi_app, n_ligan, n_kompleks, ada_mm):
    return f"""Paket Supplementary - {pr.nama}
Dibuat dengan VirmoDock {versi_app} pada {datetime.now():%Y-%m-%d %H:%M}

Isi
  reseptor/        Reseptor siap docking (reseptor.pdbqt), struktur bersih (bersih.pdb), laporan preparasi,
                   tabel pKa (bila PROPKA dipakai), residu fleksibel (bila dipakai).
  ligan/           Ligan setelah preparasi (PDBQT masukan docking), {n_ligan} berkas.
  pose/terbaik.sdf Pose terbaik setiap ligan; tag SDF memuat ΔG (kcal/mol), Ki perkiraan, LE, jumlah interaksi,
                   ΔG MM/GBSA (bila dihitung).
  pose/semua/      Semua pose per ligan (SDF).
  kompleks/        Kompleks reseptor-ligan (PDB) untuk {n_kompleks} ligan teratas.
  tabel/           hasil.csv (pemisah ;, koma desimal - Excel Indonesia) dan hasil_titik.csv (pemisah ,, titik desimal).
  parameter/       Parameter tiap job (mesin, grid box, ketelitian, seed, residu fleksibel) dan ringkasan proyek.
{"  mmgbsa/         Hasil MD & MM/GBSA (hasil.json per proses)." + chr(10) if ada_mm else ""}  versi_perangkat_lunak.txt   Versi VirmoDock, mesin docking, dan pustaka.
  SHA256SUMS.txt   Checksum SHA-256 untuk memeriksa keutuhan berkas.

Cara membuka
  SDF/PDB/PDBQT: PyMOL, UCSF ChimeraX, Discovery Studio Visualizer, atau VirmoDock (Berkas › Buka).
  CSV: Excel / LibreOffice / R / Python. JSON: editor teks.
  Memeriksa checksum (Windows PowerShell): Get-FileHash <berkas> -Algorithm SHA256

Catatan: ΔG docking dan Ki adalah perkiraan komputasi, bukan bukti aktivitas biologis.
"""


def buat(f_zip, pr, baris, cari_job, versi_app, info_mesin=None, n_kompleks=20, lapor=None):
    """Tulis paket Supplementary ke f_zip. cari_job(jid) -> dict job. Kembalikan jumlah berkas."""
    log = (lambda s: lapor.log.emit(s)) if lapor else (lambda s: None)
    isi = {}       # jalur dalam zip -> bytes

    def tambah(jalur, data):
        isi[jalur] = data.encode("utf-8") if isinstance(data, str) else data

    rec = pr.reseptor or {}
    for k, nama in (("pdbqt", "reseptor.pdbqt"), ("bersih", "bersih.pdb")):
        if rec.get(k) and pr.p(rec[k]).exists():
            tambah(f"reseptor/{nama}", pr.p(rec[k]).read_bytes())
    for nama in ("laporan_prep.txt", "pka.csv", "flex.pdbqt", "reseptor_kaku.pdbqt"):
        if pr.p("reseptor", nama).exists():
            tambah(f"reseptor/{nama}", pr.p("reseptor", nama).read_bytes())
    rec_pdb = pdbqt_ke_pdb(pr.p(rec["pdbqt"]).read_text()) if rec.get("pdbqt") and pr.p(rec["pdbqt"]).exists() else ""
    sudah = set()
    terbaik = []
    for i, b in enumerate(baris):
        j = cari_job(b["job"])
        l = next(x for x in j["ligan"] if x["id"] == b["lid"])
        teks_in = pr.p(l["pdbqt"]).read_text()
        if l["pdbqt"] not in sudah:
            tambah(f"ligan/{nama_aman(l['id'])}.pdbqt", teks_in)
            sudah.add(l["pdbqt"])
        pose = M.baca_hasil(j["mesin"], pr.p(l["keluaran"]))
        tag = {"Ligan": b["ligan"], "Peringkat": b["peringkat"], "dG_kcal_mol": b["energi"], "Ki_perkiraan": b["ki"],
               "LE": b["le"], "Ikatan_H": b["hbond"], "Hidrofobik": b["hidrofobik"], "Mesin": b["mesin"],
               "Job": b["job"], "RMSD_kristal_A": b.get("rmsd_kristal"), "MMGBSA_dG_kcal_mol": b.get("mmgbsa"),
               "SMILES": b["smiles"]}
        semua = []
        for p, pd in zip(pose, l.get("pose") or [{}] * len(pose)):
            try:
                m = analisis.pose_mol(teks_in, p.pdbqt)
            except Exception:
                continue
            semua.append((m, f"{b['ligan']}_pose{p.peringkat}", dict(tag, Pose=p.peringkat, dG_kcal_mol=p.energi)))
        if semua:
            terbaik.append(semua[0])
            tambah(f"pose/semua/{b['peringkat']:03d}_{nama_aman(b['ligan'])}_{nama_aman(b['job'])}.sdf",
                   E.sdf_bertag(semua))
            if i < n_kompleks and rec_pdb:
                rem = [f"Ligan {b['ligan']} pose 1 dG {b['energi']:.2f} kcal/mol ({b['mesin']}, job {b['job']})"]
                if pose and pose[0].flex:
                    rec_i = M.terapkan_flex(rec_pdb, pose[0].flex)
                else:
                    rec_i = rec_pdb
                tambah(f"kompleks/{b['peringkat']:03d}_{nama_aman(b['ligan'])}_kompleks.pdb",
                       E.kompleks_pdb(rec_i, semua[0][0], rem))
        if lapor and i % 10 == 0:
            lapor.progres.emit(i + 1, len(baris), b["ligan"])
    if terbaik:
        tambah("pose/terbaik.sdf", E.sdf_bertag(terbaik))
    tambah("tabel/hasil.csv", E.csv_teks(baris, ";", True))
    tambah("tabel/hasil_titik.csv", E.csv_teks(baris, ",", False))
    for j in pr.job:
        ring = {k: j.get(k) for k in ("id", "nama", "mesin", "mesin_asal", "perangkat", "parameter", "kotak", "status",
                                      "dibuat", "mulai", "selesai", "reseptor", "flex", "fleksibel", "kovalen",
                                      "catatan")}
        ring["ligan"] = [{k: l.get(k) for k in ("id", "nama", "status", "energi", "ki", "detik", "pesan")}
                         for l in j["ligan"]]
        tambah(f"parameter/job_{nama_aman(j['id'])}.json", json.dumps(ring, ensure_ascii=False, indent=1))
    rec_aman = dict(rec)       # jalur berkas asal bisa memuat nama pengguna Windows -> cukup nama berkas
    if isinstance(rec_aman.get("sumber"), str) and re.match(r"^[A-Za-z]:[\\/]", rec_aman["sumber"]):
        rec_aman["sumber"] = PureWindowsPath(rec_aman["sumber"]).name
    tambah("parameter/proyek.json", json.dumps({
        "nama": pr.nama, "dibuat": pr.dibuat, "reseptor": rec_aman, "validasi": getattr(pr, "validasi", {}),
        "templat": getattr(pr, "templat", ""), "md": getattr(pr, "md", [])}, ensure_ascii=False, indent=1))
    ada_mm = False
    for r in getattr(pr, "md", []) or []:
        f = pr.p(r.get("folder", ""), "hasil.json")
        if r.get("folder") and f.exists():
            tambah(f"mmgbsa/{nama_aman(r['id'])}/hasil.json", f.read_bytes())
            ada_mm = True
    tambah("versi_perangkat_lunak.txt", _versi_teks(versi_app, info_mesin))
    tambah("README.txt", _readme(pr, versi_app, len(sudah), min(n_kompleks, len(baris)), ada_mm))
    sha = "\n".join(f"{hashlib.sha256(d).hexdigest()}  {p}" for p, d in sorted(isi.items())) + "\n"
    with zipfile.ZipFile(f_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p, d in sorted(isi.items()):
            z.writestr(f"{nama_aman(pr.nama)}_supplementary/{p}", d)
        z.writestr(f"{nama_aman(pr.nama)}_supplementary/SHA256SUMS.txt", sha)
    log(f"Paket Supplementary: {len(isi) + 1} berkas")
    return len(isi) + 1
