"""Pastikan tiap layanan daring yang DIPANGGIL KODE tercatat di LISENSI_PIHAK_KETIGA.txt.

dev/cek_lisensi.py memeriksa apa yang dibundel: paket .dist-info, program .exe, berkas licenses/.
Sumber data daring tidak meninggalkan jejak apa pun di dalam build, jadi skrip itu tidak akan pernah
menangkapnya berapa kali pun dijalankan - padahal kewajiban sitasi dan batasan pemakaiannya nyata
(CTD melarang pemakaian komersial tanpa izin, misalnya). Celah itu yang ditutup di sini.

Host yang hanya dibuka di peramban pengguna lewat QDesktopServices.openUrl tidak melahirkan kewajiban
lisensi bagi aplikasi: pengguna sendiri yang mengunjunginya. Host semacam itu didaftar di PERAMBAN.

  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe dev/cek_sumber_daring.py
"""
import re
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
TEKS = (AKAR / "LISENSI_PIHAK_KETIGA.txt").read_text(encoding="utf-8").lower()

# Host yang dipanggil kode -> kata kunci yang dianggap bukti host itu tercatat di berkas lisensi.
# Menambah layanan daring baru tanpa menambah barisnya di sini akan membuat skrip ini GAGAL.
SUMBER = {
    "alphafold.ebi.ac.uk": ["alphafold"],
    "api.platform.opentargets.org": ["open targets"],
    "blast.ncbi.nlm.nih.gov": ["blast"],
    "cartblanche22.docking.org": ["zinc", "cartblanche"],
    "coconut.naturalproducts.net": ["coconut"],
    "coconut.s3.uni-jena.de": ["coconut"],
    "ctdbase.org": ["ctd", "comparative toxicogenomics"],
    "data.rcsb.org": ["rcsb", "protein data bank"],
    "files.rcsb.org": ["rcsb", "protein data bank"],
    "search.rcsb.org": ["rcsb", "protein data bank"],
    "pubchem.ncbi.nlm.nih.gov": ["pubchem"],
    "query-scholarly.wikidata.org": ["wikidata"],
    "query.wikidata.org": ["wikidata"],
    "rest.uniprot.org": ["uniprot"],
    "string-db.org": ["string"],
    "zenodo.org": ["coconut"],      # inang unduhan COCONUT lengkap (core/pustaka.py)
}

# Hanya dibuka di peramban pengguna, atau bukan sumber data sama sekali (situs produk, dokumentasi,
# pranala sitasi, pembaruan aplikasi sendiri).
PERAMBAN = {
    "3dmol.org", "amd.com", "api.github.com", "cluspro.bu.edu", "conda.anaconda.org", "doi.org",
    "ebi.ac.uk", "github.com", "intel.com", "jcheminf.com", "knapsackfamily.com", "nvidia.com",
    "purl.org", "rdkit.org", "wikidata.org",
}

gagal = []


def cek(ok, pesan):
    print(("OK    " if ok else "PERIKSA ") + pesan, flush=True)
    if not ok:
        gagal.append(pesan)


# 1. Tiap host yang didaftar sebagai sumber data harus benar-benar tercatat di berkas lisensi.
belum = []
for host, kunci in sorted(SUMBER.items()):
    if not any(re.search(r"\b" + re.escape(k), TEKS) for k in kunci):
        belum.append(host)
cek(not belum, f"semua sumber data daring tercatat di LISENSI_PIHAK_KETIGA.txt ({belum})")

# 2. Host baru di dalam kode yang belum masuk salah satu daftar di atas: entah ia sumber data yang
#    perlu dicatat lisensinya, entah ia hanya pranala peramban. Keduanya butuh keputusan manusia.
pola = re.compile(r"https?://([A-Za-z0-9.-]+)")
ditemukan = set()
for berkas in (AKAR / "virmolab").rglob("*.py"):
    for host in pola.findall(berkas.read_text(encoding="utf-8", errors="replace")):
        host = re.sub(r"^www\.", "", host.lower().rstrip("."))
        if host and not host.startswith(("localhost", "127.", "0.0.")) and "." in host:
            ditemukan.add(host)

# Ruang nama XML dan skema: muncul sebagai URL di dalam berkas yang ditulis aplikasi, tidak pernah diambil.
abaikan = {"schemas.xmlsoap.org", "schemas.openxmlformats.org", "w3.org", "example.com"}
baru = sorted(h for h in ditemukan
              if h not in SUMBER and h not in PERAMBAN and h not in abaikan
              and not h.endswith("w3.org") and "rizkirahmadip-dev" not in h)
cek(not baru, f"tidak ada host baru yang belum diputuskan ({baru})")

print("\nLULUS" if not gagal else f"\n{len(gagal)} hal perlu diperiksa")
sys.exit(1 if gagal else 0)
