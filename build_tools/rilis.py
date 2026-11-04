"""Buat rilis VirmoLab: dokumentasi -> PyInstaller -> uji mandiri -> installer Inno Setup -> zip portable -> SHA-256.

  .venv\\Scripts\\python.exe build_tools\\rilis.py            (semua)
  .venv\\Scripts\\python.exe build_tools\\rilis.py --tanpa-build   (pakai dist\\ yang ada)
  .venv\\Scripts\\python.exe build_tools\\rilis.py --wajib-tanda-tangan   (berhenti bila sertifikat belum diatur)
Hasil di folder rilis\\. Tanda tangan kode aktif bila VIRMOLAB_TANDA_PFX / VIRMOLAB_TANDA_SHA1 diatur
(lihat build_tools\\tanda_tangan.ps1 dan dev\\dokumen\\TANDA_TANGAN_KODE.md).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
PY = AKAR / ".venv" / "Scripts" / "python.exe"
ISCC = AKAR / "vendor" / "innosetup" / "ISCC.exe"
VERSI = re.search(r'__version__ = "([^"]+)"', (AKAR / "virmolab" / "__init__.py").read_text()).group(1)
DIST = AKAR / "dist" / "VirmoLab"
RILIS = AKAR / "rilis"

README_PORTABLE = f"""VirmoLab {VERSI} — versi portable
=====================================

1. Ekstrak seluruh isi zip ini ke folder mana saja (mis. D:\\VirmoLab atau flashdisk).
   Hindari C:\\Program Files.
2. Jalankan VirmoLab.exe.

Pengaturan disimpan di data\\pengaturan.ini, log di data\\log, proyek bawaan di Proyek\\ — semuanya di
dalam folder ini (tidak menyentuh registry). Jangan hapus berkas portable.flag.

Panduan: _internal\\docs\\panduan.html (juga Help › Panduan pengguna, F1).
Uji komponen: VirmoLab.exe --uji-mandiri hasil.json  (atau: VirmoLab-cli.exe uji)
Baris perintah (docking batch/skrip): VirmoLab-cli.exe -h
Lisensi: GPL-3.0-or-later (LICENSE); komponen pihak ketiga: _internal\\LISENSI_PIHAK_KETIGA.txt
"""


def langkah(t):
    print(f"\n=== {t}", flush=True)


def jalan(cmd, **kw):
    print(" ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=AKAR, **kw)


TANDA = AKAR / "build_tools" / "tanda_tangan.ps1"


def tanda_tangan_aktif():
    """Sertifikat diatur lewat variabel lingkungan sesi build (lihat build_tools/tanda_tangan.ps1)."""
    return bool(os.environ.get("VIRMOLAB_TANDA_PFX") or os.environ.get("VIRMOLAB_TANDA_SHA1"))


def tandatangani(*berkas):
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(TANDA)] + [str(b) for b in berkas]
    p = subprocess.run(cmd, cwd=AKAR)
    if p.returncode != 0:
        sys.exit(f"Penandatanganan gagal (kode {p.returncode}); rilis dihentikan.")


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
    ttd = tanda_tangan_aktif()
    if not ttd and "--wajib-tanda-tangan" in sys.argv:
        sys.exit("--wajib-tanda-tangan: VIRMOLAB_TANDA_PFX atau VIRMOLAB_TANDA_SHA1 belum diatur.")
    print("Tanda tangan kode:", "aktif" if ttd else
          "TIDAK aktif - Windows SmartScreen akan memperingatkan pengguna (lihat dev/dokumen/TANDA_TANGAN_KODE.md)")
    langkah("Dokumentasi")
    jalan([PY, "dev/buat_docs.py"])
    jalan([PY, "dev/buat_tutorial_pdf.py"])
    if "--tanpa-build" not in sys.argv:
        langkah("PyInstaller")
        shutil.rmtree(AKAR / "dist", ignore_errors=True)
        jalan([PY, "-m", "PyInstaller", "build_tools/virmolab.spec", "--noconfirm", "--distpath", "dist",
               "--workpath", "build", "--log-level", "WARN"])
    (DIST / "portable.flag").unlink(missing_ok=True)
    if ttd:
        # Ditandatangani SEBELUM uji mandiri, supaya yang diuji adalah biner yang benar-benar dirilis.
        langkah("Tanda tangan kode (exe)")
        tandatangani(DIST / "VirmoLab.exe", DIST / "VirmoLab-cli.exe")

    langkah("Uji mandiri hasil build")
    hasil = AKAR / "build" / "uji_mandiri.json"
    # Hasil build sebelumnya harus dibuang: pernah terbaca sebagai hasil build ini ketika uji
    # mandiri menggantung dan tidak sempat menulis berkas, sehingga log rilis memuat angka lama.
    hasil.unlink(missing_ok=True)
    p = subprocess.run([str(DIST / "VirmoLab.exe"), "--uji-mandiri", str(hasil)], cwd=DIST)
    if not hasil.exists():
        sys.exit(f"Uji mandiri tidak menulis {hasil.name} (kode {p.returncode}); rilis dihentikan.")
    data = json.loads(hasil.read_text(encoding="utf-8"))
    if data.get("versi") != VERSI:
        sys.exit(f"Hasil uji mandiri bukan dari versi {VERSI} (tertulis {data.get('versi')}); rilis dihentikan.")
    for h in data["hasil"]:
        print(("  OK    " if h["ok"] else "  GAGAL ") + h["uji"] + " — " + h["detail"])
    if p.returncode != 0:
        sys.exit("Uji mandiri gagal; rilis dihentikan.")
    ukuran = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"  ukuran terpasang: {ukuran / 2**20:.0f} MB")

    langkah("Installer (Inno Setup)")
    iscc = [ISCC, f"/DVersi={VERSI}", "/Q"]
    if ttd:
        # $q = tanda kutip versi Inno (jalur berspasi); $f = berkas yang ditandatangani (setup & uninstaller).
        iscc += ["/DTandaTangan=1",
                 f"/Svirmolab=powershell.exe -NoProfile -ExecutionPolicy Bypass -File $q{TANDA}$q $f"]
    jalan(iscc + ["installer/virmolab.iss"])
    setup = RILIS / f"VirmoLab-Setup-{VERSI}.exe"

    langkah("Portable (zip)")
    portable = RILIS / f"VirmoLab-Portable-{VERSI}.zip"
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(DIST.rglob("*")):
            if f.is_file():
                z.write(f, f"VirmoLab/{f.relative_to(DIST).as_posix()}")
        z.writestr("VirmoLab/portable.flag", "VirmoLab portable: pengaturan & data disimpan di folder ini.\n")
        z.writestr("VirmoLab/BACA_SAYA.txt", README_PORTABLE.replace("\n", "\r\n"))
        z.write(AKAR / "LICENSE", "VirmoLab/LICENSE.txt")

    langkah("SHA-256")
    baris = [f"{sha256(f)}  {f.name}" for f in (setup, portable)]
    # LF tegas: write_text di Windows menulis CRLF, dan `sha256sum -c` di Linux/WSL lantas mencari
    # berkas bernama "...exe\r" (ditemukan saat memverifikasi unduhan rilis v1.8.0)
    (RILIS / f"SHA256SUMS-{VERSI}.txt").write_text("\n".join(baris) + "\n", newline="\n")
    for b, f in zip(baris, (setup, portable)):
        print(f"  {f.stat().st_size / 2**20:7.1f} MB  {b}")


if __name__ == "__main__":
    main()
