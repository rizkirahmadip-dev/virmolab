"""Pustaka ligan: obat disetujui (snapshot ChEMBL, dibundel), COCONUT bahan alam (unduh sekali, CC0), ZINC (situs).

- Obat disetujui: virmodock/aset/obat_disetujui.tsv.gz (ChEMBL max_phase 4, molekul kecil; CC BY-SA 3.0).
- COCONUT 2.0 (Chandrasekhar et al. 2025, Nucleic Acids Res 53:D634; data CC0): berkas CSV 'lite' ±200 MB
  diunduh secara streaming (zip didekompresi sambil jalan, tidak disimpan) lalu diindeks ke SQLite di APPDATA
  (±700 ribu senyawa). Pencarian: nama/ID, kelas kimia, sifat (MW, logP, TPSA, Lipinski, QED), kemiripan.
- ZINC22: situs memakai verifikasi bot, jadi tidak diakses otomatis; pengguna membuka situs lalu mengimpor berkas.
"""
import codecs
from contextlib import closing
import csv
import gzip
import io
import sqlite3
import ssl
import struct
import threading
import time
import urllib.request
import zlib

from . import paths

FILE_OBAT = paths.PAKET / "aset" / "obat_disetujui.tsv.gz"
URL_COCONUT = "https://coconut.s3.uni-jena.de/prod/downloads/2026-10/coconut_csv_lite-10-2026.zip"
HALAMAN_COCONUT = "https://coconut.naturalproducts.net/download"
URL_ZINC = "https://cartblanche22.docking.org/"
ATC = {"A": "Saluran cerna & metabolisme", "B": "Darah", "C": "Kardiovaskular", "D": "Dermatologi",
       "G": "Genitourinari & hormon seks", "H": "Hormon sistemik", "J": "Antiinfeksi sistemik",
       "L": "Antineoplastik & imunomodulator", "M": "Muskuloskeletal", "N": "Sistem saraf", "P": "Antiparasit",
       "R": "Pernapasan", "S": "Organ sensorik", "V": "Lain-lain"}
SITASI_COCONUT = ("Chandrasekhar V, Rajan K, Kanakam SRS, et al. COCONUT 2.0: a comprehensive overhaul and curation "
                  "of the collection of open natural products database. Nucleic Acids Res. 2025;53(D1):D634–D643.")


def _db():
    return paths.APPDATA / "pustaka" / "coconut.sqlite"


# ------------------------------------------------------------------ obat disetujui
_obat = None


def obat():
    """[{id, nama, smiles, tahun, oral, topikal, parenteral, atc, bahan_alam}] dari snapshot ChEMBL."""
    global _obat
    if _obat is None:
        with gzip.open(FILE_OBAT, "rt", encoding="utf-8") as f:
            baris = [b for b in f.read().splitlines() if b and not b.startswith("#")]
        kol = baris[0].split("\t")
        _obat = []
        for b in baris[1:]:
            d = dict(zip(kol, b.split("\t")))
            _obat.append({"id": d["chembl"], "nama": d["nama"].title() if d["nama"] else d["chembl"],
                          "smiles": d["smiles"], "tahun": int(d["tahun_setuju"]) if d["tahun_setuju"] else None,
                          "oral": d["oral"] == "1", "topikal": d["topikal"] == "1",
                          "parenteral": d["parenteral"] == "1", "atc": d["atc"], "bahan_alam": d["bahan_alam"] == "1"})
    return _obat


def info_obat():
    with gzip.open(FILE_OBAT, "rt", encoding="utf-8") as f:
        return f.readline().lstrip("# ").strip()


def saring_obat(nama="", atc="", rute="", bahan_alam=False):
    q = nama.strip().lower()
    out = []
    for o in obat():
        if q and q not in o["nama"].lower() and q not in o["id"].lower():
            continue
        if atc and atc not in o["atc"]:
            continue
        if rute and not o.get(rute):
            continue
        if bahan_alam and not o["bahan_alam"]:
            continue
        out.append(o)
    return out


# ------------------------------------------------------------------ COCONUT
def coconut_ada():
    p = _db()
    if not p.exists():
        return None
    try:
        with closing(sqlite3.connect(p)) as c:
            n = c.execute("SELECT nilai FROM meta WHERE kunci='jumlah'").fetchone()
            w = c.execute("SELECT nilai FROM meta WHERE kunci='waktu'").fetchone()
        return {"jumlah": int(n[0]), "waktu": w[0], "ukuran": p.stat().st_size}
    except Exception:
        return None


def _konteks_ssl():
    """Server S3 Jena tidak mengirim rantai sertifikat lengkap: pakai bundel certifi bila ada (tetap diverifikasi)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


KOLOM = [("identifier", "id"), ("name", "nama"), ("canonical_smiles", "smiles"), ("molecular_weight", "mw"),
         ("alogp", "logp"), ("topological_polar_surface_area", "tpsa"), ("hydrogen_bond_donors_lipinski", "hbd"),
         ("hydrogen_bond_acceptors_lipinski", "hba"), ("rotatable_bond_count", "rotb"),
         ("lipinski_rule_of_five_violations", "lipinski"), ("qed_drug_likeliness", "qed"), ("np_likeness", "np"),
         ("heavy_atom_count", "atom_berat"), ("chemical_super_class", "superkelas"), ("chemical_class", "kelas"),
         ("np_classifier_pathway", "jalur"), ("annotation_level", "anotasi")]
ANGKA = {"mw", "logp", "tpsa", "hbd", "hba", "rotb", "lipinski", "qed", "np", "atom_berat", "anotasi"}


def unduh_coconut(url=URL_COCONUT, batal=None, lapor=None, maks_byte=None):
    """Unduh zip COCONUT secara streaming, dekompresi entri CSV pertama sambil jalan, tulis SQLite di APPDATA.

    batal: threading.Event. maks_byte: berhenti lebih awal (hanya untuk uji). Kembalikan jumlah senyawa."""
    log = (lambda s: lapor.log.emit(s)) if lapor else (lambda s: None)
    batal = batal or threading.Event()
    tujuan = _db()
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    sementara = tujuan.with_suffix(".tmp")
    sementara.unlink(missing_ok=True)
    con = sqlite3.connect(sementara)
    kol_sql = ", ".join(f"{k} {'REAL' if k in ANGKA else 'TEXT'}" for _, k in KOLOM)
    con.execute(f"CREATE TABLE senyawa ({kol_sql})")
    con.execute("CREATE TABLE meta (kunci TEXT PRIMARY KEY, nilai TEXT)")
    req = urllib.request.Request(url, headers={"User-Agent": "VirmoDock/1.0"})
    resp = urllib.request.urlopen(req, timeout=60, context=_konteks_ssl())
    total = int(resp.headers.get("Content-Length") or 0)
    dibaca = 0
    kepala = b""
    while len(kepala) < 30:
        kepala += resp.read(30 - len(kepala))
    sig, _v, flag, metode, _t, _d, _crc, _cs, _us, nl, el = struct.unpack("<IHHHHHIIIHH", kepala[:30])
    if sig != 0x04034B50 or metode != 8:
        raise RuntimeError("Format arsip COCONUT tidak dikenali")
    sisa = nl + el
    while sisa > 0:
        sisa -= len(resp.read(sisa))
    dibaca = 30 + nl + el
    dek = zlib.decompressobj(-15)
    dekode = codecs.getincrementaldecoder("utf-8")("replace")
    teks_sisa = ""
    idx = None
    n = 0
    batch = []
    t0 = time.time()
    ins = f"INSERT INTO senyawa VALUES ({', '.join('?' * len(KOLOM))})"
    while True:
        if batal.is_set():
            con.close()
            sementara.unlink(missing_ok=True)
            raise RuntimeError("Unduhan dibatalkan")
        blok = resp.read(1 << 20)
        if not blok:
            break
        dibaca += len(blok)
        teks_sisa += dekode.decode(dek.decompress(blok), final=dek.eof)
        akhir = dek.eof or (maks_byte and dibaca >= maks_byte)
        baris = teks_sisa.split("\n")
        teks_sisa = "" if dek.eof else baris.pop()
        for r in csv.reader(baris):
            if not r:
                continue
            if idx is None:
                pos = {k: i for i, k in enumerate(r)}
                idx = [pos.get(a) for a, _ in KOLOM]
                continue
            v = []
            for i, (_, k) in zip(idx, KOLOM):
                x = r[i] if i is not None and i < len(r) else ""
                if k in ANGKA:
                    try:
                        x = float(x)
                    except ValueError:
                        x = None
                v.append(x)
            batch.append(v)
        if len(batch) >= 20000:
            con.executemany(ins, batch)
            n += len(batch)
            batch = []
        if lapor:
            lapor.progres.emit(dibaca, total or dibaca, f"{n:,} senyawa".replace(",", "."))
        if akhir:
            break
    resp.close()
    if batch:
        con.executemany(ins, batch)
        n += len(batch)
    log(f"COCONUT: {n} senyawa dibaca ({time.time() - t0:.0f} s); membuat indeks…")
    con.execute("CREATE INDEX i_nama ON senyawa(nama COLLATE NOCASE)")
    con.execute("CREATE INDEX i_mw ON senyawa(mw)")
    con.executemany("INSERT INTO meta VALUES (?, ?)", [("jumlah", str(n)), ("waktu", time.strftime("%d-%m-%Y")),
                                                      ("url", url)])
    con.commit()
    con.close()
    tujuan.unlink(missing_ok=True)
    sementara.rename(tujuan)
    return n


def hapus_coconut():
    _db().unlink(missing_ok=True)


def cari_coconut(nama="", kelas="", mw=(0, 2000), lipinski_maks=None, qed_min=0.0, atom_min=6, batas=500,
                 urut="anotasi", acak=False):
    """Query COCONUT lokal. urut: anotasi (kualitas data) | qed | np | mw."""
    syarat, arg = ["mw BETWEEN ? AND ?", "atom_berat >= ?"], [mw[0], mw[1], atom_min]
    if nama.strip():
        syarat.append("(nama LIKE ? OR id LIKE ?)")
        arg += [f"%{nama.strip()}%", f"{nama.strip()}%"]
    if kelas.strip():
        syarat.append("(superkelas LIKE ? OR kelas LIKE ? OR jalur LIKE ?)")
        arg += [f"%{kelas.strip()}%"] * 3
    if lipinski_maks is not None:
        syarat.append("lipinski <= ?")
        arg.append(lipinski_maks)
    if qed_min:
        syarat.append("qed >= ?")
        arg.append(qed_min)
    urutan = "RANDOM()" if acak else {"anotasi": "anotasi DESC, qed DESC", "qed": "qed DESC", "np": "np DESC",
                                      "mw": "mw"}.get(urut, "anotasi DESC")
    sql = f"SELECT * FROM senyawa WHERE {' AND '.join(syarat)} ORDER BY {urutan} LIMIT ?"
    with closing(sqlite3.connect(_db())) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute(sql, arg + [batas])]


# ------------------------------------------------------------------ kemiripan
def urut_mirip(daftar, smiles, batas=200, lapor=None):
    """Urutkan daftar (punya 'smiles') menurut Tanimoto ECFP4 ke SMILES acuan; tambah kunci 'mirip'."""
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import rdFingerprintGenerator as G
    RDLogger.DisableLog("rdApp.*")
    acuan = Chem.MolFromSmiles(smiles)
    if acuan is None:
        raise ValueError("SMILES acuan tidak valid")
    gen = G.GetMorganGenerator(radius=2, fpSize=2048)
    fa = gen.GetFingerprint(acuan)
    out = []
    for i, d in enumerate(daftar):
        m = Chem.MolFromSmiles(d["smiles"])
        if m is None:
            continue
        out.append(dict(d, mirip=round(DataStructs.TanimotoSimilarity(fa, gen.GetFingerprint(m)), 3)))
        if lapor and i % 5000 == 0:
            lapor.progres.emit(i, len(daftar), "")
    out.sort(key=lambda d: -d["mirip"])
    return out[:batas]


def cari_coconut_mirip(smiles, kandidat=100000, batas=200, lapor=None, **saring):
    """Kemiripan di COCONUT: ambil ≤ kandidat baris sesuai saringan sifat, lalu urutkan Tanimoto."""
    saring.setdefault("batas", kandidat)
    return urut_mirip(cari_coconut(**saring), smiles, batas, lapor)
