"""Unduh bobot Boltz-2 dan kamus komponen kimia (CCD) ke ~/.boltz di WSL.

download_boltz2() bawaan Boltz mengandaikan folder ~/.boltz sudah ada (di distro baru belum) dan menulis langsung ke
nama akhir, sehingga unduhan yang putus meninggalkan berkas terpotong yang dianggap lengkap pada percobaan berikutnya.
Di sini tiap berkas diunduh ke <nama>.part, ukurannya dicocokkan dengan Content-Length, baru diganti nama; mols.tar
diekstrak ke folder sementara lalu dipindah, jadi ekstraksi yang terputus juga diulang dari awal. Koneksi yang gagal
(misalnya jabat tangan TLS habis waktu) dicoba ulang hingga empat putaran atas semua URL, seperti curl di skrip
pemasang; baris ULANG_UNDUH ditampilkan dialog sebagai "mencoba lagi".
"""
import shutil
import tarfile
import time
import urllib.request
from pathlib import Path

from boltz import main as B

CACHE = Path.home() / ".boltz"
PUTARAN = 4


def _coba(url, tujuan, part):
    """Satu percobaan unduh; True bila berkas lengkap dan sudah diganti nama."""
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            n, lapor = 0, 0
            while blok := r.read(1 << 20):
                f.write(blok)
                n += len(blok)
                if total and n * 10 // total > lapor:
                    lapor = n * 10 // total
                    print(f"{tujuan.name} {lapor * 10}% dari {total / 2**30:.1f} GB", flush=True)
        if total and part.stat().st_size != total:
            raise OSError(f"unduhan terpotong ({part.stat().st_size} dari {total} bita)")
        part.replace(tujuan)
        return True
    except Exception as e:  # noqa: BLE001 - coba URL cadangan atau putaran berikutnya
        print(f"{tujuan.name}: {url} gagal ({e})", flush=True)
        return False


def unduh(urls, tujuan):
    if tujuan.exists():
        print(f"{tujuan.name} sudah ada", flush=True)
        return
    part = tujuan.with_name(tujuan.name + ".part")
    for putaran in range(1, PUTARAN + 1):
        if putaran > 1:
            print(f"ULANG_UNDUH {putaran}", flush=True)
            time.sleep(10 * (putaran - 1))
        if any(_coba(url, tujuan, part) for url in urls):
            return
    raise SystemExit(f"Gagal mengunduh {tujuan.name} sesudah {PUTARAN} putaran; periksa koneksi internet.")


CACHE.mkdir(parents=True, exist_ok=True)
unduh([B.MOL_URL], CACHE / "mols.tar")
if not (CACHE / "mols").is_dir():
    sementara = CACHE / "mols.ekstrak"
    shutil.rmtree(sementara, ignore_errors=True)
    print("Mengekstrak mols.tar", flush=True)
    with tarfile.open(CACHE / "mols.tar") as tar:
        tar.extractall(sementara, filter="data")
    (sementara / "mols").replace(CACHE / "mols")
    shutil.rmtree(sementara, ignore_errors=True)
unduh(B.BOLTZ2_URL_WITH_FALLBACK, CACHE / "boltz2_conf.ckpt")
unduh(B.BOLTZ2_AFFINITY_URL_WITH_FALLBACK, CACHE / "boltz2_aff.ckpt")
print("BOBOT_SELESAI", flush=True)
