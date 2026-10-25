"""Bandingkan daftar komponen di LISENSI_PIHAK_KETIGA.txt dengan isi build yang benar-benar didistribusikan.

Kewajiban lisensi berlaku atas apa yang dikirim ke pengguna, bukan atas daftar yang pernah ditulis. Skrip ini
memeriksa dua arah: paket/program di build yang belum tercatat, dan catatan yang programnya sudah tidak ada.
Versi paket Python juga dicocokkan dengan .dist-info di build.

  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/cek_lisensi.py [folder-build]
Bawaan folder build: dist/VirmoLab (hasil PyInstaller terakhir).
"""
import re
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
BUILD = Path(sys.argv[1]) if len(sys.argv) > 1 else AKAR / "dist" / "VirmoLab"
TEKS = (AKAR / "LISENSI_PIHAK_KETIGA.txt").read_text(encoding="utf-8")
gagal = []


def cek(ok, pesan):
    print(("OK    " if ok else "PERIKSA ") + pesan, flush=True)
    if not ok:
        gagal.append(pesan)


_TEKS_RATA = re.sub(r"[-_ ]", "", TEKS.lower())


def disebut(nama):
    """Nama komponen muncul di berkas lisensi (abaikan huruf besar/kecil, -, _, dan spasi: 'openff_units'
    dicatat sebagai 'OpenFF Units')."""
    return re.sub(r"[-_ ]", "", nama.lower()) in _TEKS_RATA


# Paket Python yang ikut dibundel: dari .dist-info di _internal (nama + versi yang sebenarnya dikirim)
dalam = BUILD / "_internal"
if not dalam.is_dir():
    print(f"LEWAT: build tidak ada di {BUILD}. Jalankan build_tools/rilis.py dulu.")
    sys.exit(0)

# paket yang memang bagian dari Python itu sendiri atau tidak punya teks lisensi terpisah
BAWAAN = {"pip", "setuptools", "wheel", "pkg_resources", "virmolab"}
paket = {}
for d in dalam.glob("*.dist-info"):
    nama, _, versi = d.name[: -len(".dist-info")].rpartition("-")
    if nama.lower() not in BAWAAN:
        paket[nama] = versi
print(f"{len(paket)} paket Python ber-.dist-info di build\n")

tak_dicatat = sorted(n for n in paket if not disebut(n))
cek(not tak_dicatat, f"semua paket Python yang dibundel tercatat di LISENSI_PIHAK_KETIGA.txt ({tak_dicatat})")

beda = []
for nama, versi in sorted(paket.items()):
    if not versi or not disebut(nama):
        continue
    # baris catatan untuk paket ini: "Nama  versi  lisensi ..."
    for baris in TEKS.splitlines():
        if re.match(rf"\s*{re.escape(nama)}\s", baris, re.I):
            m = re.search(r"\s(\d+[\w.]*)\s", baris)
            if m and m.group(1) != versi:
                beda.append(f"{nama}: build {versi}, catatan {m.group(1)}")
            break
cek(not beda, f"versi paket di catatan cocok dengan build ({beda})")

# Program terpisah yang dipanggil VirmoLab. Program bawaan komponen yang sudah tercatat sebagai satu kesatuan
# (JRE Temurin, Qt/PySide6, torch) tidak diperiksa satu per satu.
INDUK = ("/jre/", "/PySide6/", "/torch/", "/p2rank/")
semua = list((AKAR / "vendor" / "bin").rglob("*.exe")) + list(dalam.rglob("*.exe"))
program = sorted({x.stem for x in semua if not any(pola in x.as_posix() for pola in INDUK)})
tak_dicatat = [n for n in program if not disebut(n)]
cek(not tak_dicatat, f"semua program .exe yang dibundel tercatat ({tak_dicatat})")

# Berkas lisensi yang dirujuk harus benar-benar ada
rujukan = sorted(set(re.findall(r"licenses/([\w.+*-]+\.txt)", TEKS)))
hilang = [f for f in rujukan if not list((AKAR / "licenses").glob(f))]        # catatan boleh memakai pola *
cek(not hilang, f"{len(rujukan)} berkas licenses/ yang dirujuk ada semua ({hilang})")

# Sebaliknya: berkas di licenses/ yang tidak pernah dirujuk (biasanya catatan yang terlupa diperbarui)
dirujuk = {q.name for f in rujukan for q in (AKAR / "licenses").glob(f)}
yatim = sorted(x.name for x in (AKAR / "licenses").glob("*.txt") if x.name not in dirujuk)
cek(not yatim, f"tidak ada berkas licenses/ yang tak dirujuk ({yatim})")

# Lisensi harus ikut terkirim
for nama in ("LICENSE", "LISENSI_PIHAK_KETIGA.txt"):
    cek((dalam / nama).exists(), f"{nama} ikut dalam build")
cek((BUILD / "_internal" / "licenses").is_dir() or (BUILD / "licenses").is_dir(),
    "folder licenses/ ikut dalam build")

print("\nLULUS" if not gagal else f"\n{len(gagal)} hal perlu diperiksa")
sys.exit(1 if gagal else 0)
