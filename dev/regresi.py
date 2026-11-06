"""Regresi total: jalankan semua dev/uji_*.py satu per satu, log ke dev/uji/regresi/, ringkasan lulus/gagal.

Gagal bila: kode keluar != 0, ada Traceback / "GAGAL" / "GALAT" / "TIMEOUT" di keluaran, atau melewati batas waktu.
Isi dev/uji/ tidak ikut Git. Di komputer baru (atau sesudah folder itu dibersihkan) jalankan dev/siapkan_contoh.py
lebih dulu, kalau tidak puluhan uji berhenti karena berkas contohnya tidak ada.
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/regresi.py [nama ...]   (tanpa nama = semua kecuali LEWATI)
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
OUT = AKAR / "dev" / "uji" / "regresi"
OUT.mkdir(parents=True, exist_ok=True)
# butuh internet / sangat lama / membuat proyek docking baru (jalankan terpisah bila perlu)
LEWATI = {"uji_pubchem", "uji_alur", "uji_responsif", "uji_chembl", "uji_alphafold",
          "uji_induced_fit"}   # eksperimen: butuh unduhan PDB dan berjam-jam (lihat dev/dokumen/INDUCED_FIT_EKSPERIMEN.md)
LAMA = {"uji_tahap3": 900, "uji_animasi": 600, "uji_laporan": 400, "uji_mesin": 600, "uji_qc_antrean": 600,
        "uji_video": 300, "uji_p2rank": 300, "uji_antrean": 600, "uji_alat_wsl_gui": 900,
        "uji_kontrol": 600, "uji_impor_eksternal_gui": 600, "uji_label_terpotong": 900, "uji_bahasa_lanjut": 900,
        "uji_kemiripan": 300, "uji_admet": 300, "uji_farmakofor": 600, "uji_wizard_reseptor": 300, "uji_fleksibel": 600, "uji_cli": 400, "uji_md_gui": 1200, "uji_kovalen": 600,
        "uji_al_gui": 2400, "uji_rbfe_jalan": 1800, "uji_sunting3d_gui": 900, "uji_rbfe_openfe": 900, "uji_induced_fit": 7200}
ABAIKAN = re.compile(r"GL_INVALID|gl_utils|^js:|DevTools|MFT name|handler_name|vendor_id|\[h264_mf|\[hevc_mf")
BURUK = re.compile(r"Traceback|\bGAGAL\b|\bGALAT\b|\bTIMEOUT\b|fatal exception")

# uji yang memakai keluaran uji lain harus berjalan sesudahnya (urutan abjad saja tidak cukup)
SESUDAH = {"uji_impor_eksternal_gui": "uji_md_gui",    # butuh proyek MD + hasil docking yang dibuat uji_md_gui
           "uji_overlay": "uji_tahap3"}               # butuh proyek berisi job validasi redocking
nama = sys.argv[1:] or [f.stem for f in sorted((AKAR / "dev").glob("uji_*.py")) if f.stem not in LEWATI]
for n_, sesudah_ in SESUDAH.items():
    if n_ in nama and sesudah_ in nama and nama.index(n_) < nama.index(sesudah_):
        nama.insert(nama.index(sesudah_) + 1, nama.pop(nama.index(n_)))
if not (AKAR / "dev" / "uji" / "1HSG_rec.pdbqt").exists():
    print("Catatan: berkas contoh di dev/uji/ belum lengkap — jalankan dev/siapkan_contoh.py dulu "
          "agar uji tidak gagal karena berkasnya tidak ada.\n", flush=True)
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=str(AKAR))
hasil = []
for n in nama:
    t0 = time.time()
    arg = [str(AKAR / ".venv" / "Scripts" / "python.exe"), str(AKAR / "dev" / f"{n}.py")]
    if n == "uji_video":
        arg.append("fhd")
    try:
        p = subprocess.run(arg, cwd=AKAR, env=env, capture_output=True, timeout=LAMA.get(n, 240))
        teks = (p.stdout + p.stderr).decode("utf-8", "replace")
        kode = p.returncode
    except subprocess.TimeoutExpired as e:
        teks = ((e.stdout or b"") + (e.stderr or b"")).decode("utf-8", "replace") + "\nTIMEOUT (runner)"
        kode = -1
    (OUT / f"{n}.log").write_text(teks, encoding="utf-8")
    baris = [b for b in teks.splitlines() if not ABAIKAN.search(b)]
    buruk = [b for b in baris if BURUK.search(b)]
    ok = kode == 0 and not buruk
    hasil.append((n, ok, kode, round(time.time() - t0), buruk[:3]))
    print(f"{'LULUS' if ok else 'GAGAL'}  {n:24s} {round(time.time() - t0):4d} s  kode={kode}"
          + (f"  | {buruk[0][:110]}" if buruk else ""), flush=True)
g = [h for h in hasil if not h[1]]
print(f"\n{len(hasil) - len(g)}/{len(hasil)} lulus" + (f"; gagal: {', '.join(h[0] for h in g)}" if g else ""))
