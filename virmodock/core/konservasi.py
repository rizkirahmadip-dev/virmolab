"""Konservasi residu (rencana B4 #10).

Persen identitas dihitung di komputer ini: tiap homolog disejajarkan ke sekuens rantai
(Needleman–Wunsch, BLOSUM62). Homolog bisa ditempel sebagai FASTA, dicari lewat nama di UniProt,
atau diminta dari BLAST NCBI (basis Swiss-Prot). BLAST mengirim sekuens ke peladen NCBI.
Hasil BLAST adalah potongan yang lolos ambang, bukan profil ConSurf.
"""
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

AA = "ARNDCQEGHILKMFPSTWYV"
# BLOSUM62, urutan AA di atas. Sumber: Henikoff & Henikoff 1992.
_B = """
 4 -1 -2 -2  0 -1 -1  0 -2 -1 -1 -1 -1 -2 -1  1  0 -3 -2  0
-1  5  0 -2 -3  1  0 -2  0 -3 -2  2 -1 -3 -2 -1 -1 -3 -2 -3
-2  0  6  1 -3  0  0  0  1 -3 -3  0 -2 -3 -2  1  0 -4 -2 -3
-2 -2  1  6 -3  0  2 -1 -1 -3 -4 -1 -3 -3 -1  0 -1 -4 -3 -3
 0 -3 -3 -3  9 -3 -4 -3 -3 -1 -1 -3 -1 -2 -3 -1 -1 -2 -2 -1
-1  1  0  0 -3  5  2 -2  0 -3 -2  1  0 -3 -1  0 -1 -2 -1 -2
-1  0  0  2 -4  2  5 -2  0 -3 -3  1 -2 -3 -1  0 -1 -3 -2 -2
 0 -2  0 -1 -3 -2 -2  6 -2 -4 -4 -2 -3 -3 -2  0 -2 -2 -3 -3
-2  0  1 -1 -3  0  0 -2  8 -3 -3 -1 -2 -1 -2 -1 -2 -2  2 -3
-1 -3 -3 -3 -1 -3 -3 -4 -3  4  2 -3  1  0 -3 -2 -1 -3 -1  3
-1 -2 -3 -4 -1 -2 -3 -4 -3  2  4 -2  2  0 -3 -2 -1 -2 -1  1
-1  2  0 -1 -3  1  1 -2 -1 -3 -2  5 -1 -3 -1  0 -1 -3 -2 -2
-1 -1 -2 -3 -1  0 -2 -3 -2  1  2 -1  5  0 -2 -1 -1 -1 -1  1
-2 -3 -3 -3 -2 -3 -3 -3 -1  0  0 -3  0  6 -4 -2 -2  1  3 -1
-1 -2 -2 -1 -3 -1 -1 -2 -2 -3 -3 -1 -2 -4  7 -1 -1 -4 -3 -2
 1 -1  1  0 -1  0  0  0 -1 -2 -2  0 -1 -2 -1  4  1 -3 -2 -2
 0 -1  0 -1 -1 -1 -1 -2 -2 -1 -1 -1 -1 -2 -1  1  5 -2 -2  0
-3 -3 -4 -4 -2 -2 -3 -2 -2 -3 -2 -3 -1  1 -4 -3 -2 11  2 -3
-2 -2 -2 -3 -2 -1 -2 -3  2 -1 -1 -2 -1  3 -3 -2 -2  2  7 -1
 0 -3 -3 -3 -1 -2 -2 -3 -3  3  1 -2  1 -1 -2 -2  0 -3 -1  4
"""
BLOSUM = {}
for i, baris in enumerate(b for b in _B.splitlines() if b.strip()):
    for j, v in enumerate(baris.split()):
        BLOSUM[(AA[i], AA[j])] = int(v)
CELAH = -8


def baca_fasta(teks):
    """[(judul, sekuens)] dari FASTA. Baris tanpa judul dianggap satu sekuens."""
    out, judul, pot = [], "", []
    for b in (teks or "").splitlines():
        b = b.strip()
        if not b:
            continue
        if b.startswith(">"):
            if pot:
                out.append((judul, "".join(pot)))
            judul, pot = b[1:].strip(), []
        else:
            pot.append("".join(c for c in b.upper() if c in AA))
    if pot:
        out.append((judul or "sekuens", "".join(pot)))
    return [(j, s) for j, s in out if s]


def sejajar(a, b):
    """Needleman–Wunsch. Kembalikan (sekuens a ber-celah, sekuens b ber-celah)."""
    n, m = len(a), len(b)
    F = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        F[i][0] = i * CELAH
    for j in range(1, m + 1):
        F[0][j] = j * CELAH
    for i in range(1, n + 1):
        ai = a[i - 1]
        for j in range(1, m + 1):
            cocok = F[i - 1][j - 1] + BLOSUM.get((ai, b[j - 1]), -4)
            F[i][j] = max(cocok, F[i - 1][j] + CELAH, F[i][j - 1] + CELAH)
    i, j, xa, xb = n, m, [], []
    while i or j:
        if i and j and F[i][j] == F[i - 1][j - 1] + BLOSUM.get((a[i - 1], b[j - 1]), -4):
            xa.append(a[i - 1])
            xb.append(b[j - 1])
            i, j = i - 1, j - 1
        elif i and F[i][j] == F[i - 1][j] + CELAH:
            xa.append(a[i - 1])
            xb.append("-")
            i -= 1
        else:
            xa.append("-")
            xb.append(b[j - 1])
            j -= 1
    return "".join(reversed(xa)), "".join(reversed(xb))


def skor(query, homolog):
    """[(indeks, aa, persen identitas, n homolog yang menutupi posisi)]. query = sekuens rantai."""
    query = "".join(c for c in query.upper() if c in AA)
    lain = [s for _, s in homolog] if homolog and isinstance(homolog[0], tuple) else list(homolog)
    lain = ["".join(c for c in s.upper() if c in AA) for s in lain if s]
    if not query or not lain:
        raise ValueError("Sekuens rantai dan minimal satu homolog (FASTA) wajib diisi.")
    kolom = [[] for _ in query]
    for s in lain:
        qa, sa = sejajar(query, s)
        qi = 0
        for x, y in zip(qa, sa):
            if x == "-":
                continue
            if y != "-":
                kolom[qi].append(y)
            qi += 1
    hasil = []
    for i, aa in enumerate(query):
        k = kolom[i]
        ident = (sum(1 for x in k if x == aa) / len(k)) if k else 0.0
        hasil.append({"i": i + 1, "aa": aa, "identitas": round(ident, 3), "n": len(k)})
    return hasil


def sekuens_rantai(teks_pdb, rantai):
    """Sekuens satu huruf dari ATOM protein (bukan HETATM) pada satu rantai."""
    TIGA = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G",
            "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S",
            "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V"}
    urut, lihat = [], set()
    for b in teks_pdb.splitlines():
        if not b.startswith("ATOM") or len(b) < 26:
            continue
        if rantai and b[21].strip() != rantai:
            continue
        resn, resi = b[17:20].strip().upper(), b[22:26].strip()
        if resn not in TIGA or (b[21], resi) in lihat:
            continue
        lihat.add((b[21], resi))
        urut.append((int(resi) if resi.lstrip("-").isdigit() else 0, TIGA[resn], b[21].strip(), resi))
    return urut


def terapkan_bfaktor(teks_pdb, rantai, skor_posisi):
    """Tulis persen identitas (0–100) ke kolom B-faktor atom residu yang sama urutannya dengan sekuens."""
    urut = sekuens_rantai(teks_pdb, rantai)
    peta = {}
    for (resi_i, _aa, ch, resi_t), s in zip(urut, skor_posisi):
        peta[(ch, resi_t)] = max(0.0, min(100.0, 100 * s["identitas"]))
    baris = []
    for b in teks_pdb.splitlines():
        if b.startswith(("ATOM", "HETATM")) and len(b) >= 66:
            k = (b[21].strip(), b[22:26].strip())
            if k in peta:
                b = b[:60] + f"{peta[k]:6.2f}" + b[66:]
        baris.append(b)
    return "\n".join(baris) + ("\n" if teks_pdb.endswith("\n") else "")


def unduh_fasta(kueri, n=12, timeout=25):
    """FASTA dari pencarian nama UniProt. Kosong bila layanan tidak menjawab."""
    q = urllib.parse.urlencode({"query": kueri, "format": "fasta", "size": str(n)})
    req = urllib.request.Request("https://rest.uniprot.org/uniprotkb/search?" + q,
                                 headers={"User-Agent": "VirmoDock"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        raise ConnectionError(f"UniProt tidak menjawab ({type(e).__name__}). Tempel FASTA homolog secara manual.") from e


_BLAST = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"


def _minta(url, data=None, timeout=45):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "VirmoDock"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def kirim_blast(sekuens, basis="swissprot", timeout=45):
    """Kirim BLAST protein ke NCBI. Mengembalikan RID. Sekuens meninggalkan komputer ini."""
    seq = "".join(c for c in (sekuens or "").upper() if c in AA)
    if len(seq) < 10:
        raise ValueError("Sekuens terlalu pendek untuk BLAST.")
    data = urllib.parse.urlencode({
        "CMD": "Put", "PROGRAM": "blastp", "DATABASE": basis,
        "QUERY": seq, "HITLIST_SIZE": "12", "EXPECT": "0.001",
    }).encode()
    teks = _minta(_BLAST, data, timeout)
    m = re.search(r"RID\s*=\s*(\S+)", teks)
    if not m:
        raise ConnectionError("NCBI tidak memberi nomor pekerjaan BLAST.")
    return m.group(1)


def status_blast(rid, timeout=45):
    """WAITING, READY, FAILED, atau UNKNOWN."""
    q = urllib.parse.urlencode({"CMD": "Get", "FORMAT_OBJECT": "SearchInfo", "RID": rid})
    teks = _minta(_BLAST + "?" + q, timeout=timeout)
    m = re.search(r"Status=(\w+)", teks)
    return m.group(1) if m else "UNKNOWN"


def ambil_blast_xml(rid, timeout=90):
    q = urllib.parse.urlencode({"CMD": "Get", "FORMAT_TYPE": "XML", "RID": rid})
    return _minta(_BLAST + "?" + q, timeout=timeout)


def urai_blast_xml(teks):
    """[(judul, sekuens)] dari XML BLAST. Celah pada potongan HSP dibuang."""
    try:
        akar = ET.fromstring(teks)
    except ET.ParseError as e:
        raise ValueError("Jawaban BLAST bukan XML.") from e
    out = []
    for hit in akar.iter("Hit"):
        judul = (hit.findtext("Hit_def") or hit.findtext("Hit_id") or "homolog").strip()
        terbaik = ""
        for hsp in hit.iter("Hsp"):
            seq = "".join(c for c in (hsp.findtext("Hsp_hseq") or "").upper() if c in AA)
            if len(seq) > len(terbaik):
                terbaik = seq
        if terbaik:
            out.append((judul[:80], terbaik))
    return out


def blast_fasta(sekuens, tunggu=240, jeda=12):
    """Tunggu BLAST Swiss-Prot. (rid, [(judul, sekuens)]). TimeoutError menyertakan RID."""
    rid = kirim_blast(sekuens)
    batas = time.time() + tunggu
    while time.time() < batas:
        st = status_blast(rid)
        if st == "READY":
            daftar = urai_blast_xml(ambil_blast_xml(rid))
            if not daftar:
                raise RuntimeError(f"BLAST {rid} selesai tanpa homolog di atas ambang.")
            return rid, daftar
        if st in ("FAILED", "UNKNOWN"):
            raise RuntimeError(f"BLAST {rid} berstatus {st}.")
        time.sleep(jeda)
    raise TimeoutError(f"BLAST masih antre. RID {rid}.")
