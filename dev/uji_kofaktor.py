"""Uji preparasi kofaktor (core/kofaktor.py) dan pemilihan ligan asli di samping kofaktor.

Struktur nyata dari RCSB, disimpan di dev/uji/kofaktor/ (diunduh sekali):
  2V0M  CYP3A4 + ketokonazol (KLN) + HEM: dulu HEM terpilih sebagai ligan asli dan ikut dibuang
  1G9V  hemoglobin, 4 HEM: dulu preparasi dengan "Pertahankan kofaktor" gagal total (Meeko + Open Babel)
  6T88  protein ber-FAD: fosfat harus terdeprotonasi, cincin isoaloksazin aromatik

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_kofaktor.py
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from virmolab.core import air, molekul, prep_reseptor  # noqa: E402

D = Path("dev/uji/kofaktor")
D.mkdir(parents=True, exist_ok=True)
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def ambil(kode):
    f = D / f"{kode}.pdb"
    if not f.exists():
        req = urllib.request.Request(f"https://files.rcsb.org/download/{kode}.pdb", headers={"User-Agent": "VirmoLab"})
        f.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return f.read_text(encoding="utf-8", errors="replace")


def tipe(pdbqt, resn):
    t = {}
    for b in pdbqt.splitlines():
        if b.startswith("HETATM") and b[17:20].strip() == resn:
            k = b[77:79].strip()
            t[k] = t.get(k, 0) + 1
    return t


def muatan(pdbqt, resn, rantai=None):
    return sum(float(b[70:76]) for b in pdbqt.splitlines() if b.startswith("HETATM") and b[17:20].strip() == resn
               and (rantai is None or b[21] == rantai))


# --- 1. CYP3A4 + ketokonazol: ligan asli harus KLN, HEM tetap kofaktor
teks = ambil("2V0M")
lig = {o.info["resn"]: o for o in molekul.baca_teks_struktur(teks, "2V0M", "pdb") if o.jenis == "ligan"}
cek("KLN" in lig and lig["KLN"].info["ligan_asli"], "2V0M: ketokonazol (KLN) ditandai ligan asli")
cek("HEM" in lig and not lig["HEM"].info["ligan_asli"] and lig["HEM"].info.get("kofaktor"),
    "2V0M: HEM bukan ligan asli, ditandai kofaktor")
t = air.telaah(prep_reseptor.baca_struktur(teks))
cek(t["ligan"] and t["ligan"]["resn"] == "KLN", f"2V0M telaah: ligan utama {t['ligan'] and t['ligan']['resn']}")
cek(any(k["resn"] == "HEM" for k in t["kofaktor"]), "2V0M telaah: HEM masuk daftar kofaktor")
h = prep_reseptor.siapkan(teks, prep_reseptor.OpsiReseptor(protonasi="templat", kofaktor=True))
cek(tipe(h.pdbqt, "HEM").get("A", 0) >= 16, f"2V0M: karbon aromatik heme bertipe A ({tipe(h.pdbqt, 'HEM')})")
cek(not any(b[17:20].strip() == "KLN" for b in h.pdbqt.splitlines()), "2V0M: ketokonazol dibuang dari reseptor")
cek(any(l.startswith("FE") for l in h.logam), f"2V0M: Fe heme ditulis sebagai ion ({h.logam})")
q = muatan(h.pdbqt, "HEM", rantai="A")
cek(-4.3 < q < -3.7, f"2V0M: muatan bagian organik heme {q:+.2f} (porfirin dianion + 2 propionat)")
cek(not any(b[17:20].strip() == "HEM" and b[77:79].strip() == "HD" for b in h.pdbqt.splitlines()
            if any(abs(float(b[30:38]) - float(c[30:38])) < 3 for c in h.pdbqt.splitlines() if c[12:16].strip() == "FE")),
    "2V0M: tidak ada H donor pada N pengikat Fe")
h0 = prep_reseptor.siapkan(teks, prep_reseptor.OpsiReseptor(protonasi="templat", kofaktor=False))
cek(not any(b[17:20].strip() == "HEM" for b in h0.pdbqt.splitlines()), "2V0M: tanpa opsi kofaktor, heme dibuang")

# --- 2. Hemoglobin: empat HEM, dulu gagal total
teks = ambil("1G9V")
h = prep_reseptor.siapkan(teks, prep_reseptor.OpsiReseptor(protonasi="templat", kofaktor=True, radius_logam=0.0))
n_hem = len({(b[21], b[22:26]) for b in h.pdbqt.splitlines() if b.startswith("HETATM") and b[17:20] == "HEM"})
cek(n_hem >= 4 and h.metode.startswith("Meeko"), f"1G9V: {n_hem} heme disiapkan, polimer tetap Meeko ({h.metode})")
cek("templat CCD" in h.laporan, "1G9V: laporan menyebut kofaktor memakai templat CCD")

# --- 3. Fleksibel: HETATM (kofaktor + ion) ikut ke reseptor kaku baru
rig, flex, ok, gg = prep_reseptor.buat_fleksibel(h.pdb_meeko, h.pdbqt, ["A:58"],
                                                 prep_reseptor.OpsiReseptor(kofaktor=True))
cek(sum(1 for b in rig.splitlines() if b[17:20] == "HEM") == sum(1 for b in h.pdbqt.splitlines() if b[17:20] == "HEM"),
    "1G9V fleksibel: semua atom heme tetap di reseptor kaku")

# --- 4. FAD: fosfat terdeprotonasi, isoaloksazin aromatik
teks = ambil("6T88")
h = prep_reseptor.siapkan(teks, prep_reseptor.OpsiReseptor(protonasi="templat", kofaktor=True))
tf = tipe(h.pdbqt, "FAD")
qf = muatan(h.pdbqt, "FAD", rantai=next(b[21] for b in h.pdbqt.splitlines() if b[17:20] == "FAD"))
cek(tf.get("A", 0) >= 10, f"6T88: FAD punya ≥ 10 atom aromatik ({tf})")
cek(-2.4 < qf < -1.6, f"6T88: muatan FAD {qf:+.2f} (difosfat −2 pada pH 7,4)")
print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
sys.exit(1 if gagal else 0)
