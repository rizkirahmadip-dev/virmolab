"""Konservasi residu (rencana B4 #10).

Persen identitas dihitung di komputer ini: tiap homolog disejajarkan ke sekuens rantai
(Needleman-Wunsch, BLOSUM62). Homolog bisa ditempel sebagai FASTA, dicari lewat nama di UniProt,
atau diminta dari BLAST NCBI, UniProt, atau EBI (basis Swiss-Prot). Pencarian itu mengirim
sekuens keluar dari komputer ini. Hasilnya potongan yang lolos ambang, bukan profil ConSurf.
"""
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from . import catat

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
    """Needleman-Wunsch. Kembalikan (sekuens a ber-celah, sekuens b ber-celah)."""
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
    """Tulis persen identitas (0-100) ke kolom B-faktor atom residu yang sama urutannya dengan sekuens."""
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


def urai_fasta(teks):
    """[(judul, sekuens)] dari FASTA. Celah dan karakter selain asam amino dibuang."""
    judul, potong, out = None, [], []

    def tutup():
        if not judul:
            return
        seq = "".join(c for c in "".join(potong).upper() if c in AA)
        if seq:
            out.append((judul[:80], seq))

    for b in (teks or "").splitlines():
        if b.startswith(">"):
            tutup()
            judul, potong = b[1:].strip() or "homolog", []
        else:
            potong.append(b.strip())
    tutup()
    return out


def kirim_uniprot_blast(sekuens, timeout=60):
    """Kirim BLAST protein ke UniProt Swiss-Prot. Mengembalikan nomor pekerjaan."""
    seq = "".join(c for c in (sekuens or "").upper() if c in AA)
    if len(seq) < 10:
        raise ValueError("Sekuens terlalu pendek untuk BLAST.")
    data = urllib.parse.urlencode({
        "sequence": seq, "database": "uniprotkb_swissprot", "program": "blastp",
        "threshold": "10", "matrix": "BLOSUM62", "hits": "12",
    }).encode()
    req = urllib.request.Request(
        "https://rest.uniprot.org/blast/run", data=data,
        headers={"User-Agent": "VirmoDock", "Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            job = r.read().decode("utf-8", "replace").strip()
    except Exception as e:
        raise ConnectionError(f"UniProt tidak menjawab ({type(e).__name__}).") from e
    if not job or any(c.isspace() for c in job) or len(job) > 80:
        raise ConnectionError("UniProt tidak memberi nomor pekerjaan BLAST.")
    return job


def status_uniprot_blast(job, timeout=45):
    req = urllib.request.Request(
        f"https://rest.uniprot.org/blast/status/{urllib.parse.quote(job)}",
        headers={"User-Agent": "VirmoDock", "Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace").strip().upper() or "UNKNOWN"
    except Exception as e:
        raise ConnectionError(f"UniProt tidak menjawab ({type(e).__name__}).") from e


def ambil_uniprot_blast(job, timeout=90):
    url = "https://rest.uniprot.org/blast/results/" + urllib.parse.quote(job) + "?format=fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "VirmoDock", "Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        raise ConnectionError(f"UniProt tidak menjawab ({type(e).__name__}).") from e


_EBI = "https://www.ebi.ac.uk/Tools/services/rest/ncbiblast"
# Alamat publik repositori, hanya untuk syarat layanan EBI. Tidak ditulis ke laporan.
_SUREL_EBI = "268803002+rizkirahmadip-dev@users.noreply.github.com"


def _ebi(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "VirmoDock", "Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise ConnectionError(f"EBI menolak permintaan ({e.code}).") from e
    except Exception as e:
        raise ConnectionError(f"EBI tidak menjawab ({type(e).__name__}).") from e


def kirim_ebi_blast(sekuens, timeout=60):
    """Kirim BLAST protein ke EBI, basis Swiss-Prot. Mengembalikan nomor pekerjaan."""
    seq = "".join(c for c in (sekuens or "").upper() if c in AA)
    if len(seq) < 10:
        raise ValueError("Sekuens terlalu pendek untuk BLAST.")
    data = urllib.parse.urlencode({
        "email": _SUREL_EBI, "title": "VirmoDock", "program": "blastp", "stype": "protein",
        "sequence": seq, "database": "uniprotkb_swissprot", "alignments": "12",
        "scores": "12", "exp": "0.001",
    }).encode()
    job = _ebi(_EBI + "/run", data, timeout).strip()
    if not job or any(c.isspace() for c in job) or len(job) > 80:
        raise ConnectionError("EBI tidak memberi nomor pekerjaan BLAST.")
    return job


def status_ebi_blast(job, timeout=45):
    return _ebi(f"{_EBI}/status/{urllib.parse.quote(job)}", timeout=timeout).strip().upper() or "UNKNOWN"


def ambil_ebi_blast(job, jenis="xml", timeout=90):
    return _ebi(f"{_EBI}/result/{urllib.parse.quote(job)}/{jenis}", timeout=timeout)


def urai_ebi(teks):
    """[(judul, sekuens)] dari XML NCBI, XML EBI, atau FASTA."""
    if "<Hsp_hseq>" in (teks or "") or "<Hit_def>" in (teks or ""):
        return urai_blast_xml(teks)
    if (teks or "").lstrip().startswith(">"):
        return urai_fasta(teks)
    try:
        akar = ET.fromstring(teks)
    except ET.ParseError:
        return []
    out = []
    for hit in akar.iter("hit"):
        judul = (hit.findtext("description") or hit.findtext("id") or "homolog").strip()
        terbaik = ""
        for aln in hit.iter("alignment"):
            seq = "".join(c for c in (aln.findtext("matchSeq") or "").upper() if c in AA)
            if len(seq) > len(terbaik):
                terbaik = seq
        if terbaik:
            out.append((judul[:80], terbaik))
    return out


def ebi_blast_fasta(sekuens, tunggu=240, jeda=5):
    """(nomor pekerjaan, [(judul, sekuens)]). Sekuens dikirim ke EBI."""
    job = kirim_ebi_blast(sekuens)
    batas = time.time() + tunggu
    while time.time() < batas:
        st = status_ebi_blast(job)
        if st == "FINISHED":
            daftar = []
            for jenis in ("xml", "out"):
                try:
                    daftar = urai_ebi(ambil_ebi_blast(job, jenis))
                except ConnectionError:
                    daftar = []
                if daftar:
                    break
            if not daftar:
                raise RuntimeError(f"BLAST EBI {job} selesai tanpa homolog yang terbaca.")
            return job, daftar
        if st in ("ERROR", "FAILED", "FAILURE", "NOT_FOUND"):
            raise RuntimeError(f"BLAST EBI {job} berstatus {st}.")
        time.sleep(jeda)
    raise TimeoutError(f"BLAST EBI masih berjalan. Nomor {job}.")


def blast_pengganti(sekuens, tunggu=240):
    """Homolog. UniProt dicoba dulu, lalu EBI, lalu pencarian sekuens RCSB PDB.

    Mengembalikan (sumber, nomor, daftar). Sekuens meninggalkan komputer ini.
    """
    try:
        job, daftar = uniprot_blast_fasta(sekuens, tunggu=tunggu)
        return "UniProt", job, daftar
    except (ConnectionError, TimeoutError, OSError, RuntimeError):
        pass
    try:
        job, daftar = ebi_blast_fasta(sekuens, tunggu=tunggu)
        return "EBI", job, daftar
    except (ConnectionError, TimeoutError, OSError, RuntimeError):
        daftar = rcsb_sekuens(sekuens)
        return "RCSB PDB", "sekuens", daftar


def rcsb_sekuens(sekuens, n=12, timeout=60):
    """Homolog dari pencarian sekuens RCSB (PDB). Sekuens dikirim ke RCSB. Bukan Swiss-Prot."""
    import json
    seq = "".join(c for c in (sekuens or "").upper() if c in AA)
    if len(seq) < 10:
        raise ValueError("Sekuens terlalu pendek untuk pencarian.")
    body = json.dumps({
        "query": {"type": "terminal", "service": "sequence", "parameters": {
            "evalue_cutoff": 0.001, "identity_cutoff": 0.3, "sequence_type": "protein", "value": seq}},
        "return_type": "polymer_entity",
        "request_options": {"paginate": {"start": 0, "rows": 200}},
    }).encode()
    req = urllib.request.Request(
        "https://search.rcsb.org/rcsbsearch/v2/query", data=body,
        headers={"User-Agent": "VirmoDock", "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        raise ConnectionError(f"RCSB tidak menjawab ({type(e).__name__}).") from e
    ident = [str(item.get("identifier") or "") for item in data.get("result_set") or [] if "_" in str(item.get("identifier") or "")]
    if not ident:
        raise RuntimeError("Pencarian sekuens RCSB tidak menemukan homolog.")
    # Sebar pilihan supaya tidak hanya salinan yang nyaris sama di puncak daftar.
    langkah = max(1, len(ident) // max(n * 3, 1))
    urut_ambil = []
    for i in range(0, len(ident), langkah):
        urut_ambil.append(ident[i])
    urut_ambil.extend(ident)
    unik, lihat, sudah = [], {seq}, set()
    for kode in urut_ambil:
        if kode in sudah or len(sudah) >= 36:
            continue
        sudah.add(kode)
        pdbid, ent = kode.rsplit("_", 1)
        try:
            judul, urutan = _rcsb_satu(pdbid, ent, timeout)
        except Exception as e:
            catat.log.debug(f"Gagal mengambil sekuens RCSB {pdbid}_{ent}: {e}")
            continue
        if not urutan or urutan in lihat:
            continue
        lihat.add(urutan)
        unik.append((judul, urutan))
        if len(unik) >= n:
            break
    if not unik:
        raise RuntimeError("Pencarian sekuens RCSB tidak menemukan homolog yang berbeda dari rantai ini.")
    return unik


def _rcsb_satu(pdbid, ent, timeout):
    import json
    url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdbid}/{ent}"
    req = urllib.request.Request(url, headers={"User-Agent": "VirmoDock", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    poly = data.get("entity_poly") or {}
    mentah = poly.get("pdbx_seq_one_letter_code_can") or poly.get("pdbx_seq_one_letter_code") or ""
    urutan = "".join(c for c in mentah.upper() if c in AA)
    desk = ((data.get("rcsb_polymer_entity") or {}).get("pdbx_description") or "protein").strip()
    return (f"{pdbid} {desk}"[:80], urutan)


def uniprot_blast_fasta(sekuens, tunggu=180, jeda=5):
    """(nomor pekerjaan, [(judul, sekuens)]). Sekuens dikirim ke UniProt."""
    job = kirim_uniprot_blast(sekuens)
    batas = time.time() + tunggu
    while time.time() < batas:
        st = status_uniprot_blast(job)
        if st in ("FINISHED", "SUCCESS", "DONE"):
            daftar = urai_fasta(ambil_uniprot_blast(job))
            if not daftar:
                raise RuntimeError(f"BLAST UniProt {job} selesai tanpa homolog.")
            return job, daftar
        if st in ("ERROR", "FAILED", "FAILURE", "NOT_FOUND"):
            raise RuntimeError(f"BLAST UniProt {job} berstatus {st}.")
        time.sleep(jeda)
    raise TimeoutError(f"BLAST UniProt masih berjalan. Nomor {job}.")


def blast_fasta(sekuens, tunggu=240, jeda=12, basis="swissprot"):
    """Tunggu BLAST NCBI. (rid, [(judul, sekuens)]). TimeoutError menyertakan RID."""
    rid = kirim_blast(sekuens, basis=basis)
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
