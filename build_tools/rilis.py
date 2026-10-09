"""Buat rilis VirmoDock: dokumentasi -> PyInstaller -> uji mandiri -> installer Inno Setup -> zip portable -> SHA-256.

  .venv\\Scripts\\python.exe build_tools\\rilis.py            (semua)
  .venv\\Scripts\\python.exe build_tools\\rilis.py --tanpa-build   (pakai dist\\ yang ada)
Hasil di folder rilis\\.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
PY = AKAR / ".venv" / "Scripts" / "python.exe"
ISCC = AKAR / "vendor" / "innosetup" / "ISCC.exe"
VERSI = re.search(r'__version__ = "([^"]+)"', (AKAR / "virmodock" / "__init__.py").read_text()).group(1)
DIST = AKAR / "dist" / "VirmoDock"
RILIS = AKAR / "rilis"

README_PORTABLE = f"""VirmoDock {VERSI} — versi portable
=====================================

1. Ekstrak seluruh isi zip ini ke folder mana saja (mis. D:\\VirmoDock atau flashdisk).
   Hindari C:\\Program Files.
2. Jalankan VirmoDock.exe.

Pengaturan disimpan di data\\pengaturan.ini, log di data\\log, proyek bawaan di Proyek\\ — semuanya di
dalam folder ini (tidak menyentuh registry). Jangan hapus berkas portable.flag.

Panduan: _internal\\docs\\panduan.html (juga Help › Panduan pengguna, F1).
Uji komponen: VirmoDock.exe --uji-mandiri hasil.json  (atau: VirmoDock-cli.exe uji)
Baris perintah (docking batch/skrip): VirmoDock-cli.exe -h
Lisensi: GPL-3.0-or-later (LICENSE); komponen pihak ketiga: _internal\\LISENSI_PIHAK_KETIGA.txt
"""


def langkah(t):
    print(f"\n=== {t}", flush=True)


def jalan(cmd, **kw):
    print(" ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=AKAR, **kw)


def sha256(f):
    h = hashlib.sha256()
    with open(f, "rb") as b:
        for blok in iter(lambda: b.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def main():
    # Konsol/berkas log Windows bisa cp1252; detail uji memuat karakter seperti '−' (U+2212).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    RILIS.mkdir(exist_ok=True)
    langkah("Dokumentasi")
    jalan([PY, "dev/buat_docs.py"])
    jalan([PY, "dev/buat_tutorial_pdf.py"])
    if "--tanpa-build" not in sys.argv:
        langkah("PyInstaller")
        shutil.rmtree(AKAR / "dist", ignore_errors=True)
        jalan([PY, "-m", "PyInstaller", "build_tools/virmodock.spec", "--noconfirm", "--distpath", "dist",
               "--workpath", "build", "--log-level", "WARN"])
    (DIST / "portable.flag").unlink(missing_ok=True)

    langkah("Uji mandiri hasil build")
    hasil = AKAR / "build" / "uji_mandiri.json"
    p = subprocess.run([str(DIST / "VirmoDock.exe"), "--uji-mandiri", str(hasil)], cwd=DIST)
    data = json.loads(hasil.read_text(encoding="utf-8"))
    for h in data["hasil"]:
        print(("  OK    " if h["ok"] else "  GAGAL ") + h["uji"] + " — " + h["detail"])
    if p.returncode != 0:
        sys.exit("Uji mandiri gagal; rilis dihentikan.")
    ukuran = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"  ukuran terpasang: {ukuran / 2**20:.0f} MB")

    langkah("Installer (Inno Setup)")
    jalan([ISCC, f"/DVersi={VERSI}", "/Q", "installer/virmodock.iss"])
    setup = RILIS / f"VirmoDock-Setup-{VERSI}.exe"

    langkah("Portable (zip)")
    portable = RILIS / f"VirmoDock-Portable-{VERSI}.zip"
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(DIST.rglob("*")):
            if f.is_file():
                z.write(f, f"VirmoDock/{f.relative_to(DIST).as_posix()}")
        z.writestr("VirmoDock/portable.flag", "VirmoDock portable: pengaturan & data disimpan di folder ini.\n")
        z.writestr("VirmoDock/BACA_SAYA.txt", README_PORTABLE.replace("\n", "\r\n"))
        z.write(AKAR / "LICENSE", "VirmoDock/LICENSE.txt")

    langkah("SHA-256")
    baris = [f"{sha256(f)}  {f.name}" for f in (setup, portable)]
    (RILIS / f"SHA256SUMS-{VERSI}.txt").write_text("\n".join(baris) + "\n")
    for b, f in zip(baris, (setup, portable)):
        print(f"  {f.stat().st_size / 2**20:7.1f} MB  {b}")


if __name__ == "__main__":
    main()
