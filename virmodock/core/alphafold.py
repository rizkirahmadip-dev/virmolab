"""Struktur prediksi AlphaFold DB (EMBL-EBI & Google DeepMind, CC BY 4.0) lewat kode UniProt.

pLDDT (0-100, keyakinan per residu) disimpan model AlphaFold di kolom B-factor. Pita resmi:
  > 90 sangat tinggi · 70-90 yakin · 50-70 rendah · < 50 sangat rendah (sering daerah tak beraturan).
Pencarian nama protein/gen memakai UniProt REST (CC BY 4.0).
Kutip: Jumper dkk. 2021, Nature 596:583; Varadi dkk. 2024, Nucleic Acids Res 52:D368.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://alphafold.ebi.ac.uk/api/prediction/"
UNIPROT = "https://rest.uniprot.org/uniprotkb/search"
# aksesi UniProt (pola resmi) mis. P00918, Q9BYF1, A0A023GPI8
POLA_AKSESI = re.compile(r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$")
PITA = [(90, "sangat tinggi", "#0053D6"), (70, "yakin", "#65CBF3"), (50, "rendah", "#FFDB13"),
        (0, "sangat rendah", "#FF7D45")]


class GalatAlphaFold(Exception):
    pass


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "VirmoDock/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def aksesi_sah(teks):
    return bool(POLA_AKSESI.match((teks or "").strip().upper()))


def cari(kueri, organisme=None, hanya_ditinjau=True, n=25):
    """Cari UniProt: aksesi langsung, atau nama protein/gen. -> [{aksesi, nama, gen, organisme, panjang, ditinjau}]."""
    kueri = (kueri or "").strip()
    if not kueri:
        return []
    if aksesi_sah(kueri):
        q = f"accession:{kueri.upper()}"
    else:
        q = f"({kueri})"
        if hanya_ditinjau:
            q += " AND reviewed:true"
    if organisme:
        q += f" AND organism_id:{int(organisme)}"
    url = (f"{UNIPROT}?query={urllib.parse.quote(q)}&format=json&size={int(n)}"
           "&fields=accession,protein_name,gene_primary,organism_name,organism_id,length,reviewed")
    try:
        data = json.loads(_get(url))
    except urllib.error.HTTPError as e:
        raise GalatAlphaFold(f"UniProt menolak permintaan ({e.code}).")
    hasil = []
    for r in data.get("results", []):
        pd = r.get("proteinDescription", {})
        nama = ((pd.get("recommendedName") or {}).get("fullName") or {}).get("value") \
            or next(((x.get("fullName") or {}).get("value") for x in pd.get("submissionNames", [])), "") or ""
        gen = next(((g.get("geneName") or {}).get("value") for g in r.get("genes", []) if g.get("geneName")), "")
        org = r.get("organism", {})
        hasil.append({"aksesi": r.get("primaryAccession", ""), "nama": nama, "gen": gen or "",
                      "organisme": org.get("scientificName", ""), "taxon": org.get("taxonId"),
                      "panjang": (r.get("sequence") or {}).get("length"),
                      "ditinjau": "reviewed" in (r.get("entryType") or "").lower()
                      and "unreviewed" not in (r.get("entryType") or "").lower()})
    return hasil


def info(aksesi):
    """Metadata model AlphaFold untuk satu aksesi (fragmen pertama, F1)."""
    aksesi = aksesi.strip().upper()
    try:
        data = json.loads(_get(API + urllib.parse.quote(aksesi)))
    except urllib.error.HTTPError as e:
        if e.code in (400, 404, 422):
            raise GalatAlphaFold(f"Tidak ada model AlphaFold untuk {aksesi}.")
        raise GalatAlphaFold(f"AlphaFold DB menolak permintaan ({e.code}).")
    if not data:
        raise GalatAlphaFold(f"Tidak ada model AlphaFold untuk {aksesi}.")
    m = next((d for d in data if d.get("uniprotAccession", "").upper() == aksesi), data[0])
    return m


def plddt_residu(teks_pdb):
    """[(rantai, resi, resn, pLDDT)] urut berkas - pLDDT dari B-factor atom CA (atau atom pertama residu)."""
    out, kunci_lalu, ca = [], None, {}
    for b in teks_pdb.splitlines():
        if not b.startswith("ATOM"):
            continue
        try:
            k = (b[21].strip(), int(b[22:26]), b[17:20].strip())
            nilai = float(b[60:66])
        except ValueError:
            continue
        if k != kunci_lalu:
            out.append([*k, nilai])
            kunci_lalu = k
        if b[12:16].strip() == "CA":
            ca[k] = nilai
    for r in out:
        r[3] = ca.get(tuple(r[:3]), r[3])
    return [tuple(r) for r in out]


def ringkas(plddt):
    """Rata-rata dan fraksi per pita dari daftar plddt_residu."""
    v = [r[3] for r in plddt]
    if not v:
        return {"rerata": None, "n": 0, "fraksi": {}}
    fr = {nama: 0 for _, nama, _ in PITA}
    for x in v:
        fr[pita(x)[0]] += 1
    return {"rerata": round(sum(v) / len(v), 1), "n": len(v), "fraksi": {k: n / len(v) for k, n in fr.items()}}


def pita(x):
    for batas, nama, warna in PITA:
        if x > batas or batas == 0:
            return nama, warna
    return PITA[-1][1], PITA[-1][2]


def segmen_buang(plddt, ambang=50.0, hanya_ujung=True, min_panjang=1):
    """Residu yang dibuang: pLDDT < ambang. hanya_ujung = hanya rentang di ujung N/C tiap rantai
    (aman: tidak memotong loop di tengah yang bisa jadi bagian kantong). -> set {(rantai, resi)}."""
    buang = set()
    per_rantai = {}
    for r in plddt:
        per_rantai.setdefault(r[0], []).append(r)
    for c, rs in per_rantai.items():
        rendah = [r[3] < ambang for r in rs]
        if hanya_ujung:
            i = 0
            while i < len(rs) and rendah[i]:
                i += 1
            j = len(rs)
            while j > i and rendah[j - 1]:
                j -= 1
            idx = list(range(0, i)) + list(range(j, len(rs)))
            if len(idx) == len(rs):   # seluruh rantai rendah: jangan buang semuanya
                idx = []
        else:
            idx = [k for k, x in enumerate(rendah) if x]
            if len(idx) == len(rs):
                idx = []
        if len(idx) >= min_panjang:
            buang.update((c, rs[k][1]) for k in idx)
    return buang


def pangkas(teks_pdb, buang):
    """Hapus residu {(rantai, resi)} dari teks PDB (baris ATOM/HETATM/ANISOU)."""
    keluar = []
    for b in teks_pdb.splitlines():
        if b.startswith(("ATOM", "HETATM", "ANISOU")):
            try:
                if (b[21].strip(), int(b[22:26])) in buang:
                    continue
            except ValueError:
                pass
        keluar.append(b)
    return "\n".join(keluar) + "\n"


def rentang(buang):
    """{(rantai, resi)} -> 'A1-24, A250-260' untuk laporan."""
    per = {}
    for c, i in sorted(buang):
        per.setdefault(c, []).append(i)
    teks = []
    for c, xs in per.items():
        awal = lalu = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == lalu + 1:
                lalu = x
                continue
            teks.append(f"{c}{awal}" + (f"-{lalu}" if lalu != awal else ""))
            if x is not None:
                awal = lalu = x
    return ", ".join(teks)


def unduh(aksesi, ambang=50.0, hanya_ujung=True, pangkas_aktif=True, lapor=None):
    """Unduh model PDB -> (objek-objek VirmoDock, teks PDB asli, metadata)."""
    from . import molekul
    m = info(aksesi)
    url = m.get("pdbUrl")
    if not url:
        raise GalatAlphaFold("Metadata AlphaFold tidak memuat tautan berkas PDB.")
    if lapor:
        lapor.log.emit(f"AlphaFold DB: mengunduh {m.get('entryId')} v{m.get('latestVersion')}…")
    teks = _get(url, timeout=120).decode("utf-8", "replace")
    plddt = plddt_residu(teks)
    r_asli = ringkas(plddt)
    buang = segmen_buang(plddt, ambang, hanya_ujung) if pangkas_aktif else set()
    teks_pakai = pangkas(teks, buang) if buang else teks
    gen = m.get("gene") or ""
    nama = f"AF-{m.get('uniprotAccession', aksesi.upper())}" + (f" {gen}" if gen else "")
    sumber = f"AlphaFold DB {m.get('entryId')} v{m.get('latestVersion')}"
    objs = molekul.baca_teks_struktur(teks_pakai, nama, "pdb", sumber)
    meta = {"aksesi": m.get("uniprotAccession", aksesi.upper()), "entri": m.get("entryId"),
            "versi": m.get("latestVersion"), "nama": m.get("uniprotDescription", ""), "gen": gen,
            "organisme": m.get("organismScientificName", ""), "plddt_rerata": r_asli["rerata"],
            "plddt_global": m.get("globalMetricValue"), "fraksi": r_asli["fraksi"], "n_residu": r_asli["n"],
            "dibuang": rentang(buang), "n_dibuang": len(buang), "ambang": ambang if buang else None,
            "url": f"https://alphafold.ebi.ac.uk/entry/{m.get('uniprotAccession', aksesi.upper())}"}
    for o in objs:
        if o.jenis == "protein":
            o.info["alphafold"] = meta
            o.info["plddt"] = r_asli["rerata"]
            o.gaya["warna"] = {"mode": "plddt"}
    return objs, teks, meta


def plddt_di_kotak(teks_pdb, pusat, ukuran, margin=0.0):
    """Residu (CA) di dalam grid box -> (rerata pLDDT, n residu, n residu < 70) atau None bila kosong."""
    nilai = []
    for b in teks_pdb.splitlines():
        if not (b.startswith("ATOM") and b[12:16].strip() == "CA"):
            continue
        try:
            xyz = (float(b[30:38]), float(b[38:46]), float(b[46:54]))
            v = float(b[60:66])
        except ValueError:
            continue
        if all(abs(xyz[k] - pusat[k]) <= ukuran[k] / 2 + margin for k in range(3)):
            nilai.append(v)
    if not nilai:
        return None
    return round(sum(nilai) / len(nilai), 1), len(nilai), sum(1 for v in nilai if v < 70)


def salin_plddt(teks_tujuan, teks_asal):
    """Tulis pLDDT per residu dari model asal ke kolom B-factor teks PDB tujuan (mis. reseptor siap docking)."""
    peta = {(c, i): v for c, i, _n, v in plddt_residu(teks_asal)}
    keluar = []
    for b in teks_tujuan.splitlines():
        if b.startswith(("ATOM", "HETATM")) and len(b) >= 54:
            try:
                v = peta.get((b[21].strip(), int(b[22:26])))
            except ValueError:
                v = None
            if v is not None:
                b = b[:54].ljust(54) + b[54:60].ljust(60 - 54) + f"{v:6.2f}" + b[66:]
        keluar.append(b)
    return "\n".join(keluar) + ("\n" if teks_tujuan.endswith("\n") else "")
