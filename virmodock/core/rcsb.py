"""Pencarian struktur di RCSB PDB (Search API v2 + Data API GraphQL; data PDB CC0).

Cari berdasarkan teks bebas (nama protein, gen, ligan, kode), saring organisme / "hanya dengan ligan" / resolusi
maksimum, lalu beri saran struktur terbaik untuk docking: metode difraksi sinar-X, ada ligan kristal (bukan aditif
kristalisasi atau ion), resolusi terkecil.
"""
import json
import urllib.error
import urllib.request

SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
GRAPHQL = "https://data.rcsb.org/graphql"


class GalatRCSB(Exception):
    pass


def _post(url, data, timeout=40):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={
        "Content-Type": "application/json", "User-Agent": "VirmoDock/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        raise GalatRCSB(f"RCSB menolak permintaan ({e.code}).")
    return json.loads(body) if body else {}


def _kueri(teks, organisme=None, hanya_ligan=False, resolusi_maks=None):
    simpul = [{"type": "terminal", "service": "full_text", "parameters": {"value": teks}}]
    if organisme:
        simpul.append({"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_entity_source_organism.scientific_name", "operator": "exact_match", "value": organisme}})
    if hanya_ligan:
        simpul.append({"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_entry_info.nonpolymer_entity_count", "operator": "greater", "value": 0}})
    if resolusi_maks:
        simpul.append({"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_entry_info.resolution_combined", "operator": "less_or_equal", "value": float(resolusi_maks)}})
    return simpul[0] if len(simpul) == 1 else {"type": "group", "logical_operator": "and", "nodes": simpul}


def cari(teks, organisme=None, hanya_ligan=False, resolusi_maks=None, urut="skor", n=50):
    """-> (total, [entri]) dengan entri = {kode, judul, resolusi, metode, tanggal, organisme, protein, ligan, aditif}."""
    teks = (teks or "").strip()
    if not teks:
        return 0, []
    urutan = [{"sort_by": "score", "direction": "desc"}] if urut == "skor" else \
        [{"sort_by": "rcsb_entry_info.resolution_combined", "direction": "asc"}]
    q = {"query": _kueri(teks, organisme, hanya_ligan, resolusi_maks), "return_type": "entry",
         "request_options": {"paginate": {"start": 0, "rows": int(n)}, "results_content_type": ["experimental"],
                             "sort": urutan}}
    d = _post(SEARCH, q)
    ids = [x["identifier"] for x in d.get("result_set", [])]
    total = int(d.get("total_count", 0) or 0)
    if not ids:
        return total, []
    g = ("{entries(entry_ids:%s){rcsb_id struct{title} rcsb_entry_info{resolution_combined experimental_method} "
         "rcsb_accession_info{initial_release_date} polymer_entities{rcsb_entity_source_organism{scientific_name} "
         "rcsb_polymer_entity{pdbx_description}} nonpolymer_entities{nonpolymer_comp{chem_comp{id name}}}}}") % json.dumps(ids)
    rinci = {e["rcsb_id"]: e for e in (_post(GRAPHQL, {"query": g}).get("data") or {}).get("entries") or [] if e}
    from .molekul import ADITIF, AIR, ION
    hasil = []
    for k in ids:
        e = rinci.get(k)
        if not e:
            continue
        info = e.get("rcsb_entry_info") or {}
        res = info.get("resolution_combined") or []
        ligan, aditif = [], []
        for ne in e.get("nonpolymer_entities") or []:
            cc = ((ne or {}).get("nonpolymer_comp") or {}).get("chem_comp") or {}
            cid = (cc.get("id") or "").upper()
            if not cid or cid in AIR:
                continue
            (aditif if cid in ADITIF or cid in ION else ligan).append((cid, (cc.get("name") or "").lower()))
        org = sorted({o.get("scientific_name", "") for pe in e.get("polymer_entities") or []
                      for o in (pe.get("rcsb_entity_source_organism") or []) if o and o.get("scientific_name")})
        prot = [((pe.get("rcsb_polymer_entity") or {}).get("pdbx_description") or "") for pe in e.get("polymer_entities") or []]
        hasil.append({"kode": k, "judul": (e.get("struct") or {}).get("title") or "", "resolusi": res[0] if res else None,
                      "metode": info.get("experimental_method") or "",
                      "tanggal": ((e.get("rcsb_accession_info") or {}).get("initial_release_date") or "")[:10],
                      "organisme": ", ".join(o.capitalize() if o.isupper() else o for o in org),
                      "protein": "; ".join(p for p in prot if p)[:120], "ligan": ligan, "aditif": aditif})
    return total, hasil


def skor_saran(e):
    """Makin kecil makin disarankan untuk docking: X-ray, ada ligan kristal, resolusi kecil."""
    if e.get("resolusi") is None:
        return 99.0
    s = e["resolusi"]
    if not e.get("ligan"):
        s += 5.0
    if "X-ray" not in (e.get("metode") or ""):
        s += 2.0
    return s


def saran(entri):
    """Kode entri yang disarankan (atau None) + alasan singkat."""
    calon = [e for e in entri if e.get("resolusi") is not None]
    if not calon:
        return None, ""
    b = min(calon, key=skor_saran)
    alasan = [f"resolusi {b['resolusi']:.2f} Å".replace(".", ",")]
    alasan.append(f"ligan kristal {', '.join(c for c, _ in b['ligan'][:3])}" if b["ligan"] else "tanpa ligan kristal")
    alasan.append(b["metode"] or "")
    return b["kode"], "; ".join(a for a in alasan if a)
